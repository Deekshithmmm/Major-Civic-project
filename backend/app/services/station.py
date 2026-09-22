"""
Station procedures: routing a report to a station, writing the General Diary, and issuing FIR
numbers. Kept out of the router so the same rules apply wherever a procedure is triggered.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.module4_emergency import OffenceCategory, PoliceStation
from app.models.station import DiaryEntryType, FirRecord, StationDiaryEntry

# How long the investigation has before it shows as overdue. In practice the window follows the
# punishment for the section invoked (BNSS s.187 / CrPC s.167: 60 days, or 90 for offences
# carrying ten years or more), which this build approximates from the category because it does
# not model sections precisely enough to derive it. A real deployment should read this from the
# sections on the FIR.
INVESTIGATION_DAYS_BY_CATEGORY = {
    OffenceCategory.HOMICIDE_OR_BODY_DISCOVERED: 90,
    OffenceCategory.SEXUAL_OFFENCE_ADULT: 90,
    OffenceCategory.HUMAN_TRAFFICKING: 90,
    OffenceCategory.NARCOTICS: 90,
    OffenceCategory.ASSAULT_IN_PROGRESS: 60,
}
DEFAULT_INVESTIGATION_DAYS = 60


def resolve_station(db: Session, lat: float, lng: float) -> PoliceStation | None:
    """
    The station that should receive an incident at this point: the nearest active one, since a
    ward can hold more than one station and the nearest is the one that can actually respond.
    Stations without a mapped location fall back to matching on ward.
    """
    point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
    nearest = db.execute(
        select(PoliceStation)
        .where(PoliceStation.is_active.is_(True), PoliceStation.location.isnot(None))
        .order_by(func.ST_DistanceSphere(PoliceStation.location, point))
        .limit(1)
    ).scalars().first()
    return nearest


def station_distance_km(db: Session, station: PoliceStation, lat: float, lng: float) -> float | None:
    if station.location is None:
        return None
    point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
    metres = db.execute(select(func.ST_DistanceSphere(station.location, point))).scalar()
    return round(metres / 1000, 2) if metres is not None else None


def log_diary(
    db: Session,
    *,
    station_id,
    entry_type: DiaryEntryType,
    detail: str,
    officer_user_id=None,
    report_id=None,
    fir_id=None,
) -> StationDiaryEntry:
    """
    Append a General Diary line. Serial numbers restart each day per station, the way a paper
    Roznamcha does, so "GD 14 of 3 March at Riverside" identifies one entry.

    The caller commits: a diary line and the action it records belong in the same transaction,
    or the station ends up with a diary that disagrees with the case file.
    """
    today = datetime.now(timezone.utc).date()
    last = db.execute(
        select(func.max(StationDiaryEntry.serial_no)).where(
            StationDiaryEntry.station_id == station_id,
            StationDiaryEntry.entry_date == today,
        )
    ).scalar()

    entry = StationDiaryEntry(
        station_id=station_id,
        entry_date=today,
        serial_no=(last or 0) + 1,
        entry_type=entry_type,
        detail=detail,
        officer_user_id=officer_user_id,
        report_id=report_id,
        fir_id=fir_id,
    )
    db.add(entry)
    # Flush so the next call in this transaction sees this serial. Without it, two entries
    # written before a commit - registering an FIR and filing the chargesheet, say - both read
    # the same MAX and collide on the per-station-per-day unique constraint.
    #
    # Two officers writing concurrently can still collide; the constraint rejects the second
    # rather than letting the diary mis-number itself. A busy deployment should allocate the
    # serial from a per-station sequence or behind an advisory lock instead.
    db.flush()
    return entry


def next_fir_number(db: Session, station_id, year: int | None = None) -> tuple[str, int]:
    """Sequential per station per year, in the familiar "0042/2026" form."""
    year = year or datetime.now(timezone.utc).year
    used = db.execute(
        select(FirRecord.fir_number).where(FirRecord.station_id == station_id, FirRecord.year == year)
    ).scalars().all()
    sequence = 0
    for number in used:
        try:
            sequence = max(sequence, int(number.split("/")[0]))
        except (ValueError, IndexError):
            continue
    return f"{sequence + 1:04d}/{year}", year


def investigation_deadline(category: OffenceCategory, registered_at: datetime | None = None) -> datetime:
    days = INVESTIGATION_DAYS_BY_CATEGORY.get(category, DEFAULT_INVESTIGATION_DAYS)
    return (registered_at or datetime.now(timezone.utc)) + timedelta(days=days)
