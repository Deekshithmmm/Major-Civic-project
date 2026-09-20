"""
Module 1 - violation detection & enforcement assist (spec 2.2). Officer review queue, citizen
upload, and challan issuance/appeal are implemented against seeded cases. The camera-feed
ingestion + YOLOv8 detection + ANPR OCR pipeline is NOT implemented - see
docs/spec-summary.md. Citizen-uploaded evidence runs through the same shared media pipeline
(metadata strip; face blur on photos only) as Modules 2-3 and lands in the same officer review queue a
camera-detected case would, satisfying "Same pipeline, same officer review, no auto-fine"
(spec 2.2, step 8) even without the CV pipeline behind it.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models.audit import AuditAction, AuditLogEntry
from app.models.module1_violations import (
    Challan,
    ChallanStatus,
    FineLadderConfig,
    IdentityPath,
    ViolationCase,
    ViolationCaseStatus,
    ViolationClassConfig,
)
from app.models.users import User, UserRole
from app.schemas.module1_violations import (
    ChallanResponse,
    DisputeRequest,
    ReclassifyRequest,
    ViolationCaseResponse,
    ViolationClassResponse,
    ViolationStatsResponse,
)
from app.services.media_pipeline import IMAGE_CONTENT_TYPES, VIDEO_CONTENT_TYPES, process_and_store
from app.services.notifications import send_email, send_sms
from app.services.storage import media_kind

router = APIRouter(prefix="/api/violations", tags=["module1-violations"])

officer_roles = require_roles(UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)


def _case_to_response(case: ViolationCase) -> ViolationCaseResponse:
    point = to_shape(case.location)
    return ViolationCaseResponse(
        id=case.id,
        violation_class_slug=case.violation_class.slug,
        violation_class_label=case.violation_class.label,
        confidence_score=float(case.confidence_score) if case.confidence_score is not None else None,
        lat=point.y,
        lng=point.x,
        media_id=case.media_id,
        media_kind=media_kind(case.media_id),
        identity_path=case.identity_path,
        resolved_plate_number=case.resolved_plate_number,
        status=case.status,
        source=case.source,
        created_at=case.created_at,
    )


@router.get("/classes", response_model=list[ViolationClassResponse])
def list_violation_classes(db: Session = Depends(get_db)):
    return db.execute(select(ViolationClassConfig).order_by(ViolationClassConfig.label)).scalars().all()


@router.get("/stats", response_model=ViolationStatsResponse)
def public_stats(db: Session = Depends(get_db)):
    """Public aggregate. Never returns evidence, location or a plate - see the schema docstring."""
    cases = db.execute(select(ViolationCase)).scalars().all()
    return ViolationStatsResponse(
        pending_review=len([c for c in cases if c.status == ViolationCaseStatus.PENDING_REVIEW]),
        confirmed=len([c for c in cases if c.status == ViolationCaseStatus.CONFIRMED]),
        dismissed=len([c for c in cases if c.status == ViolationCaseStatus.DISMISSED]),
        challans_issued=len(db.execute(select(Challan)).scalars().all()),
    )


@router.post("/citizen/upload", response_model=ViolationCaseResponse, status_code=status.HTTP_201_CREATED)
def citizen_upload(
    violation_class_slug: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Citizen-submitted violation evidence (spec 2.2, step 8). Anonymous - no account or
    identifier is collected from the citizen uploader. Number-plate OCR is not implemented in
    this build, so ANPR-path cases are created with `resolved_plate_number=None` and left for
    an officer to resolve manually or dismiss as unidentified; this is a real gap against the
    spec (real ANPR should auto-populate it), not a shortcut taken silently - flagged here and
    in docs/spec-summary.md.
    """
    violation_class = db.execute(
        select(ViolationClassConfig).where(ViolationClassConfig.slug == violation_class_slug)
    ).scalars().first()
    if not violation_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown violation class")

    content_type = file.content_type or ""
    if content_type not in IMAGE_CONTENT_TYPES | VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")

    data = file.file.read()
    processed = process_and_store(data, content_type, key_prefix="module1/citizen")

    case = ViolationCase(
        violation_class_id=violation_class.id,
        location=f"SRID=4326;POINT({lng} {lat})",
        media_id=processed.media_id,
        identity_path=violation_class.identity_path,
        source="citizen_upload",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _case_to_response(case)


@router.get("/officer/queue", response_model=list[ViolationCaseResponse])
def officer_queue(user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    cases = db.execute(
        select(ViolationCase)
        .where(ViolationCase.status == ViolationCaseStatus.PENDING_REVIEW)
        .order_by(ViolationCase.created_at.asc())
    ).scalars().all()
    return [_case_to_response(c) for c in cases]


def _fine_amount(db: Session, violation_class_id: uuid.UUID, occurrence_number: int) -> int:
    """Reads the configured fine ladder (spec 2.2: never hard-coded); falls back to the highest
    configured tier for occurrence counts beyond what's configured."""
    rows = db.execute(
        select(FineLadderConfig)
        .where(FineLadderConfig.violation_class_id == violation_class_id)
        .order_by(FineLadderConfig.occurrence_number.asc())
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=500, detail="No fine ladder configured for this violation class")
    for row in rows:
        if row.occurrence_number == occurrence_number:
            return row.amount_rupees
    return rows[-1].amount_rupees


@router.post("/officer/cases/{case_id}/confirm", response_model=ChallanResponse)
def confirm_case(case_id: uuid.UUID, user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    case = db.get(ViolationCase, case_id)
    if not case or case.status != ViolationCaseStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending case with that ID")

    # Repeat-offence escalation: count prior confirmed cases against the same plate in the
    # rolling 12-month window (spec 2.2, step 6). Unidentified cases never escalate a fine -
    # there's no registry identifier to count against.
    occurrence_number = 1
    if case.identity_path == IdentityPath.ANPR and case.resolved_plate_number:
        window_start = datetime.now(timezone.utc) - timedelta(days=365)
        prior_count = db.execute(
            select(ViolationCase).where(
                ViolationCase.resolved_plate_number == case.resolved_plate_number,
                ViolationCase.status == ViolationCaseStatus.CONFIRMED,
                ViolationCase.created_at >= window_start,
            )
        ).scalars().all()
        occurrence_number = len(prior_count) + 1

    amount = _fine_amount(db, case.violation_class_id, occurrence_number)

    case.status = ViolationCaseStatus.CONFIRMED
    case.reviewed_by_user_id = user.id
    case.reviewed_at = datetime.now(timezone.utc)

    challan = Challan(
        case_id=case.id,
        statutory_section=case.violation_class.statutory_section,
        amount_rupees=amount,
        due_date=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(challan)
    db.add(
        AuditLogEntry(
            actor_user_id=user.id,
            action=AuditAction.CONFIRM,
            entity_type="violation_case",
            entity_id=str(case.id),
            detail=f"occurrence #{occurrence_number}, Rs.{amount}",
        )
    )
    db.commit()
    db.refresh(challan)

    if case.identity_path == IdentityPath.ANPR:
        # In the real system this reads the registry contact resolved by the VAHAN-style
        # adapter. Left as a console log here since no registry lookup is wired to this route yet.
        send_sms(to="registered-contact", body=f"Challan issued: Rs.{amount}, due {challan.due_date.date()}")

    return challan


@router.post("/officer/cases/{case_id}/reclassify", response_model=ViolationCaseResponse)
def reclassify_case(
    case_id: uuid.UUID,
    payload: ReclassifyRequest,
    user: User = Depends(officer_roles),
    db: Session = Depends(get_db),
):
    case = db.get(ViolationCase, case_id)
    if not case or case.status != ViolationCaseStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending case with that ID")

    new_class = db.execute(
        select(ViolationClassConfig).where(ViolationClassConfig.slug == payload.new_violation_class_slug)
    ).scalars().first()
    if not new_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown violation class")

    case.violation_class_id = new_class.id
    case.identity_path = new_class.identity_path
    db.add(
        AuditLogEntry(
            actor_user_id=user.id,
            action=AuditAction.RECLASSIFY,
            entity_type="violation_case",
            entity_id=str(case.id),
            detail=f"-> {new_class.slug}",
        )
    )
    db.commit()
    db.refresh(case)
    return _case_to_response(case)


@router.post("/officer/cases/{case_id}/dismiss", response_model=ViolationCaseResponse)
def dismiss_case(case_id: uuid.UUID, user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    case = db.get(ViolationCase, case_id)
    if not case or case.status != ViolationCaseStatus.PENDING_REVIEW:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending case with that ID")

    case.status = ViolationCaseStatus.DISMISSED
    case.reviewed_by_user_id = user.id
    case.reviewed_at = datetime.now(timezone.utc)
    db.add(
        AuditLogEntry(
            actor_user_id=user.id, action=AuditAction.DISMISS, entity_type="violation_case", entity_id=str(case.id)
        )
    )
    db.commit()
    db.refresh(case)
    return _case_to_response(case)


@router.post("/challans/{challan_id}/dispute", response_model=ChallanResponse)
def dispute_challan(challan_id: uuid.UUID, payload: DisputeRequest, db: Session = Depends(get_db)):
    """
    No auth required: the citizen reaches this via the dispute link sent with the challan (spec
    2.2, step 7 - "Every challan carries a dispute link"). Holds the challan for a second
    officer's review; an unappealable automated fine is not deployable per the spec.
    """
    challan = db.get(Challan, challan_id)
    if not challan or challan.status != ChallanStatus.ISSUED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No disputable challan with that ID")

    challan.status = ChallanStatus.DISPUTED
    challan.dispute_reason = payload.reason
    db.commit()
    db.refresh(challan)
    return challan


@router.get("/officer/disputes", response_model=list[ChallanResponse])
def list_disputes(user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    challans = db.execute(select(Challan).where(Challan.status == ChallanStatus.DISPUTED)).scalars().all()
    return challans


@router.post("/officer/disputes/{challan_id}/uphold", response_model=ChallanResponse)
def uphold_dispute(challan_id: uuid.UUID, user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    challan = db.get(Challan, challan_id)
    if not challan or challan.status != ChallanStatus.DISPUTED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No disputed challan with that ID")
    if challan.case.reviewed_by_user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The original reviewing officer cannot rule on this appeal"
        )

    challan.status = ChallanStatus.UPHELD_ON_APPEAL
    challan.second_reviewer_user_id = user.id
    db.commit()
    db.refresh(challan)
    return challan


@router.post("/officer/disputes/{challan_id}/overturn", response_model=ChallanResponse)
def overturn_dispute(challan_id: uuid.UUID, user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    challan = db.get(Challan, challan_id)
    if not challan or challan.status != ChallanStatus.DISPUTED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No disputed challan with that ID")
    if challan.case.reviewed_by_user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The original reviewing officer cannot rule on this appeal"
        )

    challan.status = ChallanStatus.OVERTURNED_ON_APPEAL
    challan.second_reviewer_user_id = user.id
    db.commit()
    db.refresh(challan)
    return challan
