"""
Module 4 - emergency incident reporting and evidence custody (spec 2.5).

Like Module 2, this router must never accept or log the caller's IP address or any account or
device identifier. Run the server with --no-access-log and keep any reverse proxy's logs away
from /api/emergency/*.

Evidence is never returned by any public route here. The only way to reach it is
`/reports/{id}/evidence`, which requires an investigating officer AND a case or FIR number, and
appends to the chain of custody every time.
"""

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models.audit import AuditAction, AuditLogEntry
from app.models.module4_emergency import (
    ChainOfCustodyEntry,
    EmergencyReport,
    EmergencyReportRoutingRule,
    OffenceCategory,
    PoliceStation,
)
from app.models.station import FirRecord
from app.models.users import User, UserRole
from app.schemas.module4_emergency import (
    ChainOfCustodyItem,
    EmergencyRoutingRuleResponse,
    EvidenceAccessRequest,
    EvidenceAccessResponse,
    HotspotCellResponse,
    PublicCaseRecordResponse,
    ReportCreateResponse,
    ReportStatusResponse,
    StationLedgerResponse,
    SupportResource,
)
from app.security import max_bytes_for, rate_limit, read_upload
from app.services.evidence_vault import evidence_url, seal, store_evidence
from app.services.jurisdiction import resolve_ward
from app.services.media_pipeline import IMAGE_CONTENT_TYPES, VIDEO_CONTENT_TYPES, process_and_store
from app.services.notifications import send_sms
from app.services.transparency import hotspot_map, public_case_records, station_ledger

router = APIRouter(prefix="/api/emergency", tags=["module4-emergency"])

investigating_officer = require_roles(UserRole.INVESTIGATING_OFFICER, UserRole.ADMIN)

# Marked restricted at creation, and the database refuses to ever unset that (migration
# 3fabf2cb5577). These never reach a public surface at any stage.
RESTRICTED_CATEGORIES = {OffenceCategory.SEXUAL_OFFENCE_ADULT, OffenceCategory.HUMAN_TRAFFICKING}

CHILD_HELPLINE = SupportResource(label="Childline", number="1098")
EMERGENCY_112 = SupportResource(label="Emergency", number="112")
WOMENS_HELPLINE = SupportResource(label="Women's helpline", number="181")
CYBERCRIME = SupportResource(label="CCPWC cybercrime portal", number="cybercrime.gov.in")

HARD_STOP_MESSAGE = (
    "This platform cannot accept material involving a minor. Transmitting or storing it is "
    "itself an offence under POCSO and IT Act section 67B, including for us. Please contact "
    "these services directly - they can act on this immediately."
)


def _support_resources(category: OffenceCategory) -> list[SupportResource]:
    if category == OffenceCategory.SEXUAL_OFFENCE_ADULT:
        return [
            WOMENS_HELPLINE,
            EMERGENCY_112,
            SupportResource(label="Nearest One Stop Centre", number="181 (ask for your district centre)"),
        ]
    if category == OffenceCategory.HUMAN_TRAFFICKING:
        return [EMERGENCY_112, SupportResource(label="Anti Human Trafficking Unit", number="1098 / 112")]
    return [EMERGENCY_112]


@router.get("/routing-rules", response_model=list[EmergencyRoutingRuleResponse])
def list_routing_rules(db: Session = Depends(get_db)):
    """Public and auditable: shows where each category goes, and which one is refused outright."""
    return db.execute(select(EmergencyReportRoutingRule)).scalars().all()


@router.post(
    "/reports",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("emergency_report", limit=15, window_seconds=3600))],
)
def submit_report(
    category: OffenceCategory = Form(...),
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    geohash: str = Form(...),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """
    Anonymous. Nothing identifying the reporter is accepted or stored - the tracking token is
    the only handle that exists afterwards.

    Reporting without evidence is a first-class path: the alert and the station's clock start
    either way, so nobody is pushed into filming an incident to be taken seriously.
    """
    if category == OffenceCategory.MINOR_INVOLVED:
        # Hard stop BEFORE the upload is read. Accepting the bytes even to forward them would
        # itself be an offence (POCSO, IT Act 67B), so this refuses rather than restricts.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": HARD_STOP_MESSAGE,
                "redirect_to": [r.model_dump() for r in (CHILD_HELPLINE, EMERGENCY_112, CYBERCRIME)],
            },
        )

    is_restricted = category in RESTRICTED_CATEGORIES

    evidence_hash: str | None = None
    media_id: str | None = None
    if file is not None and file.filename:
        content_type = file.content_type or ""
        if content_type not in IMAGE_CONTENT_TYPES | VIDEO_CONTENT_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
        if is_restricted and content_type in VIDEO_CONTENT_TYPES:
            # The spec makes irreversible blurring mandatory before a restricted file is written
            # to the vault. The shared pipeline no longer blurs video, so rather than store an
            # unblurred one, video is refused here until that blur exists. Photos are blurred.
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    "Video cannot be accepted for this category yet, because faces in video are "
                    "not blurred. You can submit a photo, or submit the report with no file - "
                    "the alert reaches investigators either way."
                ),
            )

        data = read_upload(file, max_bytes_for(content_type))
        # Sealed BEFORE any processing: a hash taken after the server re-encoded the file proves
        # nothing about what was submitted (spec 2.5, step 1).
        evidence_hash = seal(data)
        processed = process_and_store(data, content_type, key_prefix="module4")
        media_id = processed.media_id

    ward = resolve_ward(db, lat=lat, lng=lng)
    station = None
    if ward:
        station = db.execute(
            select(PoliceStation).where(PoliceStation.ward_id == ward.id)
        ).scalars().first()

    rule = db.execute(
        select(EmergencyReportRoutingRule).where(EmergencyReportRoutingRule.category == category)
    ).scalars().first()

    report = EmergencyReport(
        category=category,
        original_sha256=evidence_hash,
        media_id=media_id,
        geohash=geohash,  # coarse cell only; the lat/lng above is used for routing and discarded
        ward_id=ward.id if ward else None,
        station_id=station.id if station else None,
        tracking_token=secrets.token_urlsafe(24),
        is_restricted=is_restricted,
    )
    db.add(report)
    db.flush()

    if evidence_hash:
        db.add(
            ChainOfCustodyEntry(
                report_id=report.id,
                action="sealed",
                detail=f"sha256={evidence_hash}",
            )
        )
    db.commit()
    db.refresh(report)

    # The alert carries category, location and a link - never the evidence itself (spec 2.5).
    if station:
        send_sms(
            to=station.contact_phone or station.code,
            body=f"New {category.value} report in {ward.name if ward else 'unknown ward'}. Token {report.tracking_token}.",
        )

    return ReportCreateResponse(
        tracking_token=report.tracking_token,
        category=category,
        is_restricted=is_restricted,
        routed_to=rule.alert_routed_to if rule else "112 control room",
        station_name=station.name if station else None,
        evidence_sealed=evidence_hash is not None,
        evidence_sha256=evidence_hash,
        support_resources=_support_resources(category),
    )


@router.get("/reports/track/{tracking_token}", response_model=ReportStatusResponse)
def track_report(tracking_token: str, db: Session = Depends(get_db)):
    report = db.execute(
        select(EmergencyReport).where(EmergencyReport.tracking_token == tracking_token)
    ).scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report found for that token")

    fir = db.execute(select(FirRecord).where(FirRecord.report_id == report.id)).scalars().first()
    if report.closed_at:
        state = "closed"
    elif fir:
        state = "fir_registered"
    elif report.acknowledged_at:
        state = "acknowledged"
    else:
        state = "received"

    return ReportStatusResponse(
        tracking_token=report.tracking_token,
        category=report.category,
        status=state,
        acknowledged_at=report.acknowledged_at,
        fir_number=fir.fir_number if fir else None,
        created_at=report.created_at,
    )


# --- Investigating officer -------------------------------------------------


def _require_jurisdiction(user: User, report: EmergencyReport) -> None:
    """
    An investigating officer is scoped to a jurisdiction (spec 2.6). Without this, any one of
    them could open evidence for every case in the city, which is the opposite of the separation
    this module exists to enforce. Admin is exempt so the system stays administrable.
    """
    if user.role == UserRole.ADMIN or user.jurisdiction_ward_id is None:
        return
    if report.ward_id != user.jurisdiction_ward_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This report is outside your jurisdiction.",
        )


@router.post("/officer/reports/{report_id}/evidence", response_model=EvidenceAccessResponse)
def access_evidence(
    report_id: uuid.UUID,
    payload: EvidenceAccessRequest,
    user: User = Depends(investigating_officer),
    db: Session = Depends(get_db),
):
    """
    The only route to Module 4 evidence. Requires an investigating officer and a case or FIR
    number, and appends to the chain of custody before the link is handed over.
    """
    if not payload.case_or_fir_number.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A case or FIR number is required to open evidence",
        )

    report = db.get(EmergencyReport, report_id)
    if not report or not report.media_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No evidence held for that report")
    _require_jurisdiction(user, report)

    db.add(
        ChainOfCustodyEntry(
            report_id=report.id,
            action="viewed",
            officer_user_id=user.id,
            case_or_fir_number=payload.case_or_fir_number.strip(),
        )
    )
    db.add(
        AuditLogEntry(
            actor_user_id=user.id,
            action=AuditAction.VIEW,
            entity_type="emergency_evidence",
            entity_id=str(report.id),
            detail=f"case {payload.case_or_fir_number.strip()}",
        )
    )
    db.commit()

    entries = db.execute(
        select(ChainOfCustodyEntry).where(ChainOfCustodyEntry.report_id == report.id)
    ).scalars().all()

    return EvidenceAccessResponse(
        url=evidence_url(report.media_id),
        expires_seconds=120,
        original_sha256=report.original_sha256,
        chain_of_custody_entries=len(entries),
    )


@router.get("/officer/reports/{report_id}/chain-of-custody", response_model=list[ChainOfCustodyItem])
def chain_of_custody(
    report_id: uuid.UUID,
    user: User = Depends(investigating_officer),
    db: Session = Depends(get_db),
):
    entries = db.execute(
        select(ChainOfCustodyEntry)
        .where(ChainOfCustodyEntry.report_id == report_id)
        .order_by(ChainOfCustodyEntry.accessed_at.asc())
    ).scalars().all()
    return entries


# --- Public transparency layer ---------------------------------------------


@router.get("/ledger", response_model=list[StationLedgerResponse])
def ledger(db: Session = Depends(get_db)):
    """Station response ledger. No auth: this is the surface that makes burial visible."""
    return [StationLedgerResponse(**row.__dict__) for row in station_ledger(db)]


@router.get("/hotspots", response_model=list[HotspotCellResponse])
def hotspots(db: Session = Depends(get_db)):
    """Aggregate map: quarterly lag, k-anonymity of five, restricted categories excluded."""
    return [HotspotCellResponse(**cell.__dict__) for cell in hotspot_map(db)]


@router.get("/cases", response_model=list[PublicCaseRecordResponse])
def case_records(db: Session = Depends(get_db)):
    """
    The public case record. Before a chargesheet nothing case-specific is published beyond
    category, ward, date and status; once it is filed, proceedings are public record anyway, so
    the platform mirrors what is already open - and no more.
    """
    return [PublicCaseRecordResponse(**record.__dict__) for record in public_case_records(db)]
