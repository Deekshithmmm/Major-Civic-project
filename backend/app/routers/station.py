"""
The internal police station section: what a station does with a report after it arrives.

The procedure chain mirrors a real station's, because Module 4's public ledger only means
something if the record it measures is the one the station actually keeps:

    report routed to station
        -> General Diary entry on arrival
        -> acknowledged by the duty officer
        -> FIR registered (BNSS s.173) or closed with a stated reason
        -> investigating officer assigned
        -> case diary entries as the investigation runs (BNSS s.192)
        -> chargesheet filed, or a closure report

Every one of those writes a General Diary line in the same transaction. A station cannot take an
action here without it appearing in its diary, and the diary cannot be edited afterwards.

Scope: an officer sees only their own station's work. Zero FIR is the one route across stations,
and it moves the investigation, never the registration.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models.audit import AuditAction, AuditLogEntry
from app.models.jurisdiction import Ward
from app.models.module4_emergency import EmergencyReport, PoliceStation
from app.models.station import CaseDiaryEntry, DiaryEntryType, FirRecord, FirStatus, StationDiaryEntry
from app.models.users import User, UserRole
from app.schemas.station import (
    AssignOfficerRequest,
    CaseDiaryRequest,
    CaseDiaryResponse,
    ChargesheetRequest,
    ClosureRequest,
    DiaryEntryResponse,
    DiaryNoteRequest,
    FirResponse,
    RegisterFirRequest,
    StationDirectoryEntry,
    StationReportRow,
    StationSummary,
    TransferRequest,
)
from app.services.station import (
    investigation_deadline,
    log_diary,
    next_fir_number,
    resolve_station,
    station_distance_km,
)
from app.services.transparency import ACK_SLA_HOURS, FIR_SLA_DAYS

router = APIRouter(prefix="/api/station", tags=["police-station"])

station_officer = require_roles(UserRole.INVESTIGATING_OFFICER, UserRole.ADMIN)


def _directory_entry(db: Session, station: PoliceStation, wards: dict, lat=None, lng=None) -> StationDirectoryEntry:
    point = to_shape(station.location) if station.location is not None else None
    return StationDirectoryEntry(
        id=station.id,
        name=station.name,
        code=station.code,
        address=station.address,
        lat=point.y if point else None,
        lng=point.x if point else None,
        contact_phone=station.contact_phone,
        sho_name=station.sho_name,
        ward_name=wards.get(station.ward_id),
        distance_km=station_distance_km(db, station, lat, lng) if lat is not None and lng is not None else None,
    )


@router.get("/directory", response_model=list[StationDirectoryEntry])
def directory(db: Session = Depends(get_db)):
    """Public: every station, where it is, and how to reach it."""
    wards = {w.id: w.name for w in db.execute(select(Ward)).scalars().all()}
    stations = db.execute(
        select(PoliceStation).where(PoliceStation.is_active.is_(True)).order_by(PoliceStation.name)
    ).scalars().all()
    return [_directory_entry(db, s, wards) for s in stations]


@router.get("/nearest", response_model=StationDirectoryEntry)
def nearest(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """Public: which station covers a point, and how far away it is."""
    station = resolve_station(db, lat=lat, lng=lng)
    if not station:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No station is mapped yet")
    wards = {w.id: w.name for w in db.execute(select(Ward)).scalars().all()}
    return _directory_entry(db, station, wards, lat=lat, lng=lng)


# --- Internal: everything below is station staff only ------------------------


def _my_station(user: User, db: Session) -> PoliceStation:
    if user.police_station_id is None:
        if user.role == UserRole.ADMIN:
            station = db.execute(select(PoliceStation).order_by(PoliceStation.name)).scalars().first()
            if station:
                return station
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not posted to a police station.",
        )
    station = db.get(PoliceStation, user.police_station_id)
    if not station:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Station not found")
    return station


def _fir_for_station(db: Session, fir_id: uuid.UUID, station: PoliceStation) -> FirRecord:
    fir = db.get(FirRecord, fir_id)
    if not fir:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FIR not found")
    # A transferred FIR stays readable at the registering station but is worked by the receiving
    # one, so either may act on it - no third station can.
    if station.id not in (fir.station_id, fir.transferred_to_station_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This FIR belongs to another station")
    return fir


def _fir_response(fir: FirRecord, station_name: str | None = None, category=None) -> FirResponse:
    remaining = (fir.investigation_deadline - datetime.now(timezone.utc)).days
    return FirResponse(
        id=fir.id,
        fir_number=fir.fir_number,
        year=fir.year,
        station_id=fir.station_id,
        station_name=station_name,
        report_id=fir.report_id,
        category=category,
        sections=fir.sections,
        is_zero_fir=fir.is_zero_fir,
        transferred_to_station_id=fir.transferred_to_station_id,
        investigating_officer_id=fir.investigating_officer_id,
        registered_at=fir.registered_at,
        investigation_deadline=fir.investigation_deadline,
        status=fir.status,
        chargesheet_filed_at=fir.chargesheet_filed_at,
        court_name=fir.court_name,
        closure_reason=fir.closure_reason,
        closed_at=fir.closed_at,
        days_remaining=remaining,
    )


def _audit(db: Session, user: User, action: AuditAction, entity_id, detail: str) -> None:
    db.add(
        AuditLogEntry(
            actor_user_id=user.id,
            action=action,
            entity_type="station_procedure",
            entity_id=str(entity_id),
            detail=detail,
        )
    )


@router.get("/me", response_model=StationSummary)
def my_station(user: User = Depends(station_officer), db: Session = Depends(get_db)):
    station = _my_station(user, db)
    return StationSummary(
        id=station.id, name=station.name, code=station.code, address=station.address, sho_name=station.sho_name
    )


@router.get("/diary", response_model=list[DiaryEntryResponse])
def general_diary(
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    station = _my_station(user, db)
    return db.execute(
        select(StationDiaryEntry)
        .where(StationDiaryEntry.station_id == station.id)
        .order_by(StationDiaryEntry.entry_date.desc(), StationDiaryEntry.serial_no.desc())
        .limit(limit)
    ).scalars().all()


@router.post("/diary", response_model=DiaryEntryResponse, status_code=status.HTTP_201_CREATED)
def add_diary_note(
    payload: DiaryNoteRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    station = _my_station(user, db)
    entry = log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.NOTE,
        detail=payload.detail,
        officer_user_id=user.id,
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/reports", response_model=list[StationReportRow])
def station_reports(user: User = Depends(station_officer), db: Session = Depends(get_db)):
    """Reports routed to this station, oldest first - the ones being sat on surface at the top."""
    station = _my_station(user, db)
    reports = db.execute(
        select(EmergencyReport)
        .where(EmergencyReport.station_id == station.id)
        .order_by(EmergencyReport.created_at.asc())
    ).scalars().all()

    firs = {
        f.report_id: f
        for f in db.execute(
            select(FirRecord).where(FirRecord.report_id.in_([r.id for r in reports] or [uuid.uuid4()]))
        ).scalars().all()
    }

    now = datetime.now(timezone.utc)
    rows = []
    for report in reports:
        fir = firs.get(report.id)
        age_hours = (now - report.created_at).total_seconds() / 3600
        rows.append(
            StationReportRow(
                id=report.id,
                category=report.category,
                geohash=report.geohash,
                is_restricted=report.is_restricted,
                has_evidence=report.media_id is not None,
                acknowledged_at=report.acknowledged_at,
                closed_at=report.closed_at,
                closed_without_fir_reason=report.closed_without_fir_reason,
                created_at=report.created_at,
                fir_id=fir.id if fir else None,
                fir_number=fir.fir_number if fir else None,
                hours_since_report=round(age_hours, 1),
                overdue_for_acknowledgement=report.acknowledged_at is None and age_hours > ACK_SLA_HOURS,
                overdue_for_fir=fir is None and report.closed_at is None and age_hours > FIR_SLA_DAYS * 24,
            )
        )
    return rows


@router.post("/reports/{report_id}/acknowledge", response_model=StationReportRow)
def acknowledge(report_id: uuid.UUID, user: User = Depends(station_officer), db: Session = Depends(get_db)):
    station = _my_station(user, db)
    report = db.get(EmergencyReport, report_id)
    if not report or report.station_id != station.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such report at this station")

    if report.acknowledged_at is None:
        report.acknowledged_at = datetime.now(timezone.utc)
        log_diary(
            db,
            station_id=station.id,
            entry_type=DiaryEntryType.ACKNOWLEDGED,
            detail=f"Report {report.tracking_token[:8]}… ({report.category.value}) acknowledged",
            officer_user_id=user.id,
            report_id=report.id,
        )
        _audit(db, user, AuditAction.STATUS_CHANGE, report.id, "acknowledged")
        db.commit()
        db.refresh(report)

    return _row_for(db, report)


def _row_for(db: Session, report: EmergencyReport) -> StationReportRow:
    fir = db.execute(select(FirRecord).where(FirRecord.report_id == report.id)).scalars().first()
    age_hours = (datetime.now(timezone.utc) - report.created_at).total_seconds() / 3600
    return StationReportRow(
        id=report.id,
        category=report.category,
        geohash=report.geohash,
        is_restricted=report.is_restricted,
        has_evidence=report.media_id is not None,
        acknowledged_at=report.acknowledged_at,
        closed_at=report.closed_at,
        closed_without_fir_reason=report.closed_without_fir_reason,
        created_at=report.created_at,
        fir_id=fir.id if fir else None,
        fir_number=fir.fir_number if fir else None,
        hours_since_report=round(age_hours, 1),
        overdue_for_acknowledgement=report.acknowledged_at is None and age_hours > ACK_SLA_HOURS,
        overdue_for_fir=fir is None and report.closed_at is None and age_hours > FIR_SLA_DAYS * 24,
    )


@router.post("/reports/{report_id}/fir", response_model=FirResponse, status_code=status.HTTP_201_CREATED)
def register_fir(
    report_id: uuid.UUID,
    payload: RegisterFirRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    """
    Register an FIR against a report. The number is issued by the station in sequence - it is
    not typed in - so the register cannot be back-dated or have gaps quietly inserted.
    """
    station = _my_station(user, db)
    report = db.get(EmergencyReport, report_id)
    if not report or report.station_id != station.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such report at this station")

    existing = db.execute(select(FirRecord).where(FirRecord.report_id == report.id)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An FIR is already registered for this report: {existing.fir_number}",
        )

    fir_number, year = next_fir_number(db, station.id)
    fir = FirRecord(
        station_id=station.id,
        fir_number=fir_number,
        year=year,
        report_id=report.id,
        sections=payload.sections,
        is_zero_fir=payload.is_zero_fir,
        registered_by_user_id=user.id,
        investigation_deadline=investigation_deadline(report.category),
    )
    db.add(fir)
    db.flush()

    if report.acknowledged_at is None:
        report.acknowledged_at = datetime.now(timezone.utc)

    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.FIR_REGISTERED,
        detail=(
            f"FIR {fir_number} registered u/s {payload.sections} ({report.category.value})"
            + (" — ZERO FIR, pending transfer" if payload.is_zero_fir else "")
        ),
        officer_user_id=user.id,
        report_id=report.id,
        fir_id=fir.id,
    )
    _audit(db, user, AuditAction.STATUS_CHANGE, report.id, f"FIR {fir_number} u/s {payload.sections}")
    db.commit()
    db.refresh(fir)
    return _fir_response(fir, station.name, report.category)


@router.post("/reports/{report_id}/close", response_model=StationReportRow)
def close_without_fir(
    report_id: uuid.UUID,
    payload: ClosureRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    """
    Closing without registering an FIR is legitimate; doing it silently is not. The reason is
    required, recorded in the diary, and published on the station's public ledger.
    """
    station = _my_station(user, db)
    report = db.get(EmergencyReport, report_id)
    if not report or report.station_id != station.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such report at this station")

    if db.execute(select(FirRecord).where(FirRecord.report_id == report.id)).scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An FIR is registered for this report; close the FIR instead.",
        )

    report.closed_at = datetime.now(timezone.utc)
    report.closed_without_fir_reason = payload.reason
    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.CLOSED_WITHOUT_FIR,
        detail=f"Closed without FIR: {payload.reason}",
        officer_user_id=user.id,
        report_id=report.id,
    )
    _audit(db, user, AuditAction.DISMISS, report.id, payload.reason)
    db.commit()
    db.refresh(report)
    return _row_for(db, report)


@router.get("/firs", response_model=list[FirResponse])
def fir_register(user: User = Depends(station_officer), db: Session = Depends(get_db)):
    """This station's FIR register, including any it received on transfer."""
    station = _my_station(user, db)
    firs = db.execute(
        select(FirRecord)
        .where((FirRecord.station_id == station.id) | (FirRecord.transferred_to_station_id == station.id))
        .order_by(FirRecord.registered_at.desc())
    ).scalars().all()

    categories = {
        r.id: r.category
        for r in db.execute(
            select(EmergencyReport).where(EmergencyReport.id.in_([f.report_id for f in firs] or [uuid.uuid4()]))
        ).scalars().all()
    }
    return [_fir_response(f, station.name, categories.get(f.report_id)) for f in firs]


@router.post("/firs/{fir_id}/assign", response_model=FirResponse)
def assign_investigating_officer(
    fir_id: uuid.UUID,
    payload: AssignOfficerRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    station = _my_station(user, db)
    fir = _fir_for_station(db, fir_id, station)

    officer = db.get(User, payload.investigating_officer_id)
    if not officer or officer.role != UserRole.INVESTIGATING_OFFICER:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such investigating officer")
    if officer.police_station_id not in (fir.station_id, fir.transferred_to_station_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That officer is posted to a different station.",
        )

    fir.investigating_officer_id = officer.id
    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.IO_ASSIGNED,
        detail=f"FIR {fir.fir_number}: investigation assigned to {officer.full_name}",
        officer_user_id=user.id,
        fir_id=fir.id,
    )
    _audit(db, user, AuditAction.STATUS_CHANGE, fir.id, f"IO {officer.email}")
    db.commit()
    db.refresh(fir)
    return _fir_response(fir, station.name)


@router.post("/firs/{fir_id}/transfer", response_model=FirResponse)
def transfer_zero_fir(
    fir_id: uuid.UUID,
    payload: TransferRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    """
    Hand a Zero FIR to the station that has jurisdiction. The registration stays here - that is
    the point of a Zero FIR - and only the investigation moves, with both diaries recording it.
    """
    station = _my_station(user, db)
    fir = _fir_for_station(db, fir_id, station)

    destination = db.get(PoliceStation, payload.to_station_id)
    if not destination or not destination.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such station")
    if destination.id == fir.station_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That is the registering station")

    fir.transferred_to_station_id = destination.id
    fir.status = FirStatus.TRANSFERRED
    fir.investigating_officer_id = None

    report = db.get(EmergencyReport, fir.report_id)
    if report:
        report.station_id = destination.id

    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.ZERO_FIR_TRANSFERRED_OUT,
        detail=f"FIR {fir.fir_number} transferred to {destination.name}: {payload.reason}",
        officer_user_id=user.id,
        fir_id=fir.id,
        report_id=fir.report_id,
    )
    log_diary(
        db,
        station_id=destination.id,
        entry_type=DiaryEntryType.TRANSFERRED_IN,
        detail=f"FIR {fir.fir_number} received from {station.name}: {payload.reason}",
        fir_id=fir.id,
        report_id=fir.report_id,
    )
    _audit(db, user, AuditAction.STATUS_CHANGE, fir.id, f"transferred to {destination.code}")
    db.commit()
    db.refresh(fir)
    return _fir_response(fir, station.name)


@router.get("/firs/{fir_id}/case-diary", response_model=list[CaseDiaryResponse])
def read_case_diary(fir_id: uuid.UUID, user: User = Depends(station_officer), db: Session = Depends(get_db)):
    station = _my_station(user, db)
    _fir_for_station(db, fir_id, station)
    return db.execute(
        select(CaseDiaryEntry).where(CaseDiaryEntry.fir_id == fir_id).order_by(CaseDiaryEntry.created_at.asc())
    ).scalars().all()


@router.post("/firs/{fir_id}/case-diary", response_model=CaseDiaryResponse, status_code=status.HTTP_201_CREATED)
def add_case_diary_entry(
    fir_id: uuid.UUID,
    payload: CaseDiaryRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    """Append-only at the database level: an investigation record that can be rewritten is not one."""
    station = _my_station(user, db)
    fir = _fir_for_station(db, fir_id, station)

    entry = CaseDiaryEntry(fir_id=fir.id, officer_user_id=user.id, detail=payload.detail)
    db.add(entry)
    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.CASE_DIARY,
        detail=f"FIR {fir.fir_number}: case diary entry added",
        officer_user_id=user.id,
        fir_id=fir.id,
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/firs/{fir_id}/chargesheet", response_model=FirResponse)
def file_chargesheet(
    fir_id: uuid.UUID,
    payload: ChargesheetRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    """
    Filing the chargesheet is the point the case record becomes public (spec 2.5): proceedings
    are public from here, so the platform mirrors what is already open - and nothing before it.
    """
    station = _my_station(user, db)
    fir = _fir_for_station(db, fir_id, station)
    if fir.status in (FirStatus.CHARGESHEET_FILED, FirStatus.CLOSED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This FIR is already concluded")

    fir.status = FirStatus.CHARGESHEET_FILED
    fir.chargesheet_filed_at = datetime.now(timezone.utc)
    fir.court_name = payload.court_name
    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.CHARGESHEET_FILED,
        detail=f"FIR {fir.fir_number}: chargesheet filed before {payload.court_name}",
        officer_user_id=user.id,
        fir_id=fir.id,
    )
    _audit(db, user, AuditAction.STATUS_CHANGE, fir.id, f"chargesheet at {payload.court_name}")
    db.commit()
    db.refresh(fir)
    return _fir_response(fir, station.name)


@router.post("/firs/{fir_id}/closure", response_model=FirResponse)
def close_fir(
    fir_id: uuid.UUID,
    payload: ClosureRequest,
    user: User = Depends(station_officer),
    db: Session = Depends(get_db),
):
    """A closure report ends the investigation without a chargesheet. The reason is recorded."""
    station = _my_station(user, db)
    fir = _fir_for_station(db, fir_id, station)
    if fir.status in (FirStatus.CHARGESHEET_FILED, FirStatus.CLOSED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This FIR is already concluded")

    fir.status = FirStatus.CLOSED
    fir.closure_reason = payload.reason
    fir.closed_at = datetime.now(timezone.utc)
    log_diary(
        db,
        station_id=station.id,
        entry_type=DiaryEntryType.CASE_CLOSED,
        detail=f"FIR {fir.fir_number}: closure report — {payload.reason}",
        officer_user_id=user.id,
        fir_id=fir.id,
    )
    _audit(db, user, AuditAction.DISMISS, fir.id, payload.reason)
    db.commit()
    db.refresh(fir)
    return _fir_response(fir, station.name)
