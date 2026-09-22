"""
The transparency layer (spec 2.5): what Module 4 publishes *instead of* footage.

Two rules govern everything here, and both are applied in this module rather than left to each
caller:

  - Sexual-offence and minor-involved reports are excluded from every public surface, at every
    stage, including aggregate counts. `PUBLIC_CATEGORIES` is the allowlist.
  - The hotspot map runs a quarter behind and suppresses any ward-quarter cell below five
    reports. A live map of narcotics reports is an intelligence feed for the people being
    reported, and a cell of one points at the person who filmed.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.jurisdiction import Ward
from app.models.module4_emergency import EmergencyReport, OffenceCategory, PoliceStation
from app.models.station import FirRecord

# Never public, at any stage, in any form - including counts (spec 2.5).
PUBLIC_CATEGORIES = [
    OffenceCategory.ASSAULT_IN_PROGRESS,
    OffenceCategory.HOMICIDE_OR_BODY_DISCOVERED,
    OffenceCategory.NARCOTICS,
]

K_ANONYMITY_THRESHOLD = 5

# Time-driven escalation (spec 2.5, "Escalation ladder"). No human decides that a report has
# been ignored; these thresholds do.
ACK_SLA_HOURS = 24
FIR_SLA_DAYS = 7


@dataclass
class StationLedgerRow:
    station_id: str
    station_name: str
    station_code: str
    reports_30d: int
    reports_90d: int
    unacknowledged_past_sla: int
    firs_registered: int
    fir_conversion_rate: float | None
    median_ack_hours: float | None
    open_past_fir_sla: int
    closed_without_fir: int
    flagged_red: bool


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def station_ledger(db: Session) -> list[StationLedgerRow]:
    """
    Published per station, computed from timestamps so inaction shows up without anyone
    deciding to report it. Restricted categories are counted nowhere here.
    """
    now = datetime.now(timezone.utc)
    stations = db.execute(select(PoliceStation).order_by(PoliceStation.name)).scalars().all()

    rows: list[StationLedgerRow] = []
    for station in stations:
        reports = db.execute(
            select(EmergencyReport).where(
                EmergencyReport.station_id == station.id,
                EmergencyReport.category.in_(PUBLIC_CATEGORIES),
            )
        ).scalars().all()

        in_30d = [r for r in reports if r.created_at >= now - timedelta(days=30)]
        in_90d = [r for r in reports if r.created_at >= now - timedelta(days=90)]

        unacknowledged = [
            r for r in reports
            if r.acknowledged_at is None and r.created_at < now - timedelta(hours=ACK_SLA_HOURS)
        ]
        # An FIR counts when the station actually registered one in its register.
        fir_report_ids = set(
            db.execute(select(FirRecord.report_id).where(FirRecord.station_id == station.id)).scalars().all()
        )
        firs = [r for r in reports if r.id in fir_report_ids]
        ack_hours = [
            (r.acknowledged_at - r.created_at).total_seconds() / 3600
            for r in reports
            if r.acknowledged_at
        ]
        open_past_fir_sla = [
            r for r in reports
            if r.id not in fir_report_ids and r.closed_at is None and r.created_at < now - timedelta(days=FIR_SLA_DAYS)
        ]
        closed_without_fir = [r for r in reports if r.closed_at and r.id not in fir_report_ids]

        rows.append(
            StationLedgerRow(
                station_id=str(station.id),
                station_name=station.name,
                station_code=station.code,
                reports_30d=len(in_30d),
                reports_90d=len(in_90d),
                unacknowledged_past_sla=len(unacknowledged),
                firs_registered=len(firs),
                fir_conversion_rate=round(len(firs) / len(reports), 2) if reports else None,
                median_ack_hours=_median(ack_hours),
                open_past_fir_sla=len(open_past_fir_sla),
                closed_without_fir=len(closed_without_fir),
                # A cognizable offence with no FIR after seven days is a legal question under
                # Lalita Kumari (2014), not an opinion - so the station is flagged, not ranked.
                flagged_red=len(open_past_fir_sla) > 0,
            )
        )
    return rows


@dataclass
class HotspotCell:
    ward_name: str
    quarter: str
    category: str
    report_count: int
    firs_registered: int


def _quarter_of(moment: datetime) -> tuple[int, int]:
    return moment.year, (moment.month - 1) // 3 + 1


def hotspot_map(db: Session) -> list[HotspotCell]:
    """
    Reports per ward per quarter per category, shown against FIRs for the same cell. Runs a
    quarter behind and suppresses cells below the k-anonymity threshold, so no single incident
    can be reverse-engineered and nothing here is current enough to act as a tip-off.
    """
    now = datetime.now(timezone.utc)
    current_quarter = _quarter_of(now)

    wards = {w.id: w.name for w in db.execute(select(Ward)).scalars().all()}
    reports = db.execute(
        select(EmergencyReport).where(EmergencyReport.category.in_(PUBLIC_CATEGORIES))
    ).scalars().all()
    fir_report_ids = set(db.execute(select(FirRecord.report_id)).scalars().all())

    buckets: dict[tuple[str, str, str], list[EmergencyReport]] = {}
    for report in reports:
        quarter = _quarter_of(report.created_at)
        if quarter >= current_quarter:
            continue  # quarterly lag: the current quarter is never published
        key = (
            wards.get(report.ward_id, "Unassigned"),
            f"{quarter[0]} Q{quarter[1]}",
            report.category.value,
        )
        buckets.setdefault(key, []).append(report)

    cells = [
        HotspotCell(
            ward_name=ward,
            quarter=quarter,
            category=category,
            report_count=len(group),
            firs_registered=len([r for r in group if r.id in fir_report_ids]),
        )
        for (ward, quarter, category), group in buckets.items()
        if len(group) >= K_ANONYMITY_THRESHOLD
    ]
    return sorted(cells, key=lambda c: (c.quarter, c.ward_name, c.category))
