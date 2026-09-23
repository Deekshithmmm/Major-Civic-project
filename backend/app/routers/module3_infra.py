"""
Module 3 - civic infrastructure reporting (spec 2.4). The only fully end-to-end module in this
build: citizen upload -> shared media pipeline -> spatial jurisdiction resolution -> SLA timer
-> notify responsible desk -> public status board, with 50m duplicate clustering and an
officer-side acknowledge/progress/resolve flow gated on a proof photo.
"""

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import distance_metres, geo_point, get_db, parse_point
from app.models.audit import AuditAction, AuditLogEntry
from app.models.module3_infra import (
    InfrastructureIssue,
    IssueCategory,
    IssueContactPhone,
    IssueStatus,
    IssueStatusHistory,
)
from app.models.users import User, UserRole
from app.schemas.module3_infra import (
    IssueCategoryResponse,
    IssueCreateResponse,
    IssueDetailResponse,
    IssuePublicResponse,
    IssueResolveRequest,
    IssueStatusHistoryItem,
    ShareableCardResponse,
)
from app.security import max_bytes_for, rate_limit, read_upload
from app.services.jurisdiction import resolve_responsible_desk, resolve_ward
from app.services.media_pipeline import IMAGE_CONTENT_TYPES, VIDEO_CONTENT_TYPES, process_and_store
from app.services.notifications import send_email
from app.services.sla import compute_sla_deadline, mark_overdue_issues
from app.services.storage import media_kind
from app.services.tracking import new_tracking_code, normalise_tracking_code

router = APIRouter(prefix="/api/infra", tags=["module3-infrastructure"])

DUPLICATE_LOOKBACK_STATUSES = [IssueStatus.REPORTED, IssueStatus.ACKNOWLEDGED, IssueStatus.IN_PROGRESS, IssueStatus.OVERDUE]


def _issue_to_public(issue: InfrastructureIssue) -> IssuePublicResponse:
    lat, lng = parse_point(issue.location)
    return IssuePublicResponse(
        id=issue.id,
        category_slug=issue.category.slug,
        category_label=issue.category.label,
        description=issue.description,
        lat=lat,
        lng=lng,
        status=issue.status,
        upvote_count=issue.upvote_count,
        sla_deadline=issue.sla_deadline,
        created_at=issue.created_at,
        media_id=issue.media_id,
        media_kind=media_kind(issue.media_id) if issue.media_id else None,
        tracking_token=issue.tracking_token,
    )


@router.get("/categories", response_model=list[IssueCategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.execute(select(IssueCategory).order_by(IssueCategory.label)).scalars().all()


@router.post(
    "/issues",
    response_model=IssueCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("infra_report", limit=20, window_seconds=3600))],
)
def create_issue(
    category_slug: str = Form(...),
    description: str | None = Form(None),
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    phone_number: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Anonymous by default (spec 2.4, step 1). No account, no required identifier. `phone_number`
    is optional and, if given, is written to IssueContactPhone - a separate table joined only by
    a one-way token - never onto InfrastructureIssue itself.
    """
    category = db.execute(select(IssueCategory).where(IssueCategory.slug == category_slug)).scalars().first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown category '{category_slug}'")

    content_type = file.content_type or ""
    if content_type not in IMAGE_CONTENT_TYPES | VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")

    data = read_upload(file, max_bytes_for(content_type))
    processed = process_and_store(data, content_type, key_prefix="module3")

    point_wkt = geo_point(lat, lng)
    ward = resolve_ward(db, lat=lat, lng=lng)

    # Duplicate clustering: same category, open, within the category's radius (spec 2.4 step 7).
    duplicate_stmt = (
        select(InfrastructureIssue)
        .where(
            InfrastructureIssue.category_id == category.id,
            InfrastructureIssue.status.in_(DUPLICATE_LOOKBACK_STATUSES),
            distance_metres(InfrastructureIssue.location, lat, lng) <= category.duplicate_radius_meters,
        )
        .order_by(InfrastructureIssue.created_at.asc())
    )
    existing = db.execute(duplicate_stmt).scalars().first()

    if existing:
        existing.upvote_count += 1
        db.add(
            IssueStatusHistory(
                issue_id=existing.id,
                status=existing.status,
                note="Duplicate report merged (within duplicate radius)",
            )
        )
        if phone_number and not existing.contact_token:
            # Only the first phone opt-in on an issue is retained; contact_token is 1:1 with the
            # issue by design (see model docstring) rather than a subscriber list.
            existing.contact_token = secrets.token_urlsafe(32)
            db.add(IssueContactPhone(contact_token=existing.contact_token, phone_number=phone_number))

        db.commit()
        db.refresh(existing)

        return IssueCreateResponse(
            id=existing.id,
            tracking_token=existing.tracking_token,
            status=existing.status,
            sla_deadline=existing.sla_deadline,
            merged_into_existing=True,
        )

    tracking_token = new_tracking_code(db)
    contact_token = secrets.token_urlsafe(32) if phone_number else None
    issue = InfrastructureIssue(
        category_id=category.id,
        description=description,
        location=point_wkt,
        ward_id=ward.id if ward else None,
        media_id=processed.media_id,
        tracking_token=tracking_token,
        contact_token=contact_token,
        sla_deadline=compute_sla_deadline(category.sla_hours),
    )
    db.add(issue)
    db.flush()
    db.add(IssueStatusHistory(issue_id=issue.id, status=IssueStatus.REPORTED, note="Report received"))

    if phone_number and contact_token:
        db.add(IssueContactPhone(contact_token=contact_token, phone_number=phone_number))

    db.commit()
    db.refresh(issue)

    # Notify the responsible desk through its official grievance channel (spec 2.4, step 4).
    desk = resolve_responsible_desk(db, ward.id if ward else None, category.escalation_department)
    if desk:
        send_email(
            to=desk.contact_email,
            subject=f"New civic issue: {category.label}",
            body=(
                f"A new '{category.label}' issue was reported in ward "
                f"{ward.name if ward else 'unresolved'}.\nSLA deadline: {issue.sla_deadline.isoformat()}\n"
                f"Tracking token: {tracking_token}"
            ),
        )

    return IssueCreateResponse(
        id=issue.id,
        tracking_token=issue.tracking_token,
        status=issue.status,
        sla_deadline=issue.sla_deadline,
        merged_into_existing=False,
    )


@router.get("/issues", response_model=list[IssuePublicResponse])
def list_public_issues(
    status_filter: IssueStatus | None = None,
    category_slug: str | None = None,
    db: Session = Depends(get_db),
):
    """Public status board (spec 2.4, step 6). No auth - this is citizen- and journalist-facing."""
    mark_overdue_issues(db)  # lazy SLA sweep; a real deployment runs this on a schedule instead

    stmt = select(InfrastructureIssue).order_by(InfrastructureIssue.created_at.desc())
    if status_filter:
        stmt = stmt.where(InfrastructureIssue.status == status_filter)
    if category_slug:
        stmt = stmt.join(IssueCategory).where(IssueCategory.slug == category_slug)

    issues = db.execute(stmt).scalars().all()
    return [_issue_to_public(i) for i in issues]


@router.get("/issues/track/{tracking_token}", response_model=IssueDetailResponse)
def track_issue(tracking_token: str, db: Session = Depends(get_db)):
    issue = db.execute(
        select(InfrastructureIssue).where(
            InfrastructureIssue.tracking_token == normalise_tracking_code(tracking_token)
        )
    ).scalars().first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No issue found for that tracking token")
    return _issue_detail(db, issue)


@router.get("/issues/{issue_id}", response_model=IssueDetailResponse)
def get_issue(issue_id: uuid.UUID, db: Session = Depends(get_db)):
    issue = db.get(InfrastructureIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return _issue_detail(db, issue)


def _issue_detail(db: Session, issue: InfrastructureIssue) -> IssueDetailResponse:
    history = db.execute(
        select(IssueStatusHistory)
        .where(IssueStatusHistory.issue_id == issue.id)
        .order_by(IssueStatusHistory.created_at.asc())
    ).scalars().all()
    base = _issue_to_public(issue)
    return IssueDetailResponse(
        **base.model_dump(),
        history=[IssueStatusHistoryItem(status=h.status, note=h.note, created_at=h.created_at) for h in history],
        resolution_proof_media_id=issue.resolution_proof_media_id,
    )


@router.get("/issues/{issue_id}/share-card", response_model=ShareableCardResponse)
def share_card(issue_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Pre-filled shareable text for citizen-initiated escalation once the SLA is breached (spec
    2.4, "Do not auto-post to officials' social media"). The platform never posts this itself.
    """
    issue = db.get(InfrastructureIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if issue.status != IssueStatus.OVERDUE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Issue is not past its SLA yet")

    text = (
        f"This '{issue.category.label}' issue has been open past its {issue.category.sla_hours}h SLA "
        f"with no resolution. Tracking: {issue.tracking_token}. #CivicAccountability"
    )
    return ShareableCardResponse(issue_id=issue.id, share_text=text, share_url=f"/issues/{issue.id}")


# --- Officer-side endpoints -------------------------------------------------

officer_roles = require_roles(UserRole.DEPARTMENT_ENGINEER, UserRole.MUNICIPAL_OFFICER, UserRole.ADMIN)


@router.get("/officer/queue", response_model=list[IssuePublicResponse])
def officer_queue(user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    mark_overdue_issues(db)
    stmt = select(InfrastructureIssue).where(
        InfrastructureIssue.status.in_([IssueStatus.REPORTED, IssueStatus.ACKNOWLEDGED, IssueStatus.IN_PROGRESS, IssueStatus.OVERDUE])
    )
    if user.jurisdiction_ward_id:
        stmt = stmt.where(InfrastructureIssue.ward_id == user.jurisdiction_ward_id)
    stmt = stmt.order_by(InfrastructureIssue.sla_deadline.asc())
    issues = db.execute(stmt).scalars().all()
    return [_issue_to_public(i) for i in issues]


def _transition(db: Session, issue: InfrastructureIssue, user: User, new_status: IssueStatus, note: str | None):
    issue.status = new_status
    db.add(IssueStatusHistory(issue_id=issue.id, status=new_status, actor_user_id=user.id, note=note))
    db.add(
        AuditLogEntry(
            actor_user_id=user.id,
            action=AuditAction.STATUS_CHANGE,
            entity_type="infrastructure_issue",
            entity_id=str(issue.id),
            detail=f"-> {new_status.value}" + (f": {note}" if note else ""),
        )
    )


@router.post("/officer/issues/{issue_id}/acknowledge", response_model=IssuePublicResponse)
def acknowledge_issue(issue_id: uuid.UUID, user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    issue = db.get(InfrastructureIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    _transition(db, issue, user, IssueStatus.ACKNOWLEDGED, None)
    db.commit()
    db.refresh(issue)
    return _issue_to_public(issue)


@router.post("/officer/issues/{issue_id}/start", response_model=IssuePublicResponse)
def start_issue(issue_id: uuid.UUID, user: User = Depends(officer_roles), db: Session = Depends(get_db)):
    issue = db.get(InfrastructureIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    _transition(db, issue, user, IssueStatus.IN_PROGRESS, None)
    db.commit()
    db.refresh(issue)
    return _issue_to_public(issue)


@router.post("/officer/issues/{issue_id}/resolve", response_model=IssuePublicResponse)
def resolve_issue(
    issue_id: uuid.UUID,
    note: str | None = Form(None),
    proof_file: UploadFile = File(...),
    user: User = Depends(officer_roles),
    db: Session = Depends(get_db),
):
    """Marking an issue resolved requires an officer-uploaded proof photo (spec 2.4, step 6)."""
    issue = db.get(InfrastructureIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    content_type = proof_file.content_type or ""
    if content_type not in IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Proof must be a photo")

    data = read_upload(proof_file, max_bytes_for(content_type))
    processed = process_and_store(data, content_type, key_prefix="module3/resolution_proof")

    issue.resolution_proof_media_id = processed.media_id
    issue.resolved_at = datetime.now(timezone.utc)
    _transition(db, issue, user, IssueStatus.RESOLVED, note)

    # Optional phone contact is purged on resolution (spec 2.6, "Privacy by design").
    if issue.contact_token:
        db.execute(
            IssueContactPhone.__table__.delete().where(IssueContactPhone.contact_token == issue.contact_token)
        )
        issue.contact_token = None

    db.commit()
    db.refresh(issue)
    return _issue_to_public(issue)
