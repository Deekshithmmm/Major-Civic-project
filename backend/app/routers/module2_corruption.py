"""
Module 2 - anonymous corruption reporting (spec 2.3). Upload flow, routing-table lookup, a
moderation API, and the public feed
are implemented. Audio muting and manual additional-region blurring (spec: "let the uploader
blur additional regions before submitting") are NOT implemented. Automatic bystander face blur
runs on photos only; videos are not blurred (see services/media_pipeline.py), so on this module's
public feed, moderation is the only check for identifiable bystanders in video.

This router must never accept or log the caller's IP address or any account/session identifier
(spec 2.3: "Never persist the uploader's IP address. Exclude this endpoint from access logging
entirely."). If you're adding request logging middleware anywhere in this app, exclude
/api/corruption/reports explicitly.
"""

import secrets
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models.module2_corruption import (
    AccusedPartyType,
    CorruptionReport,
    ModerationStatus,
    PublicStatusBadge,
    RoutingRule,
)
from app.models.users import User, UserRole
from app.schemas.module2_corruption import (
    FeedItemResponse,
    ModerationDecisionRequest,
    ReportCreateResponse,
    ReportStatusResponse,
    RoutingRuleResponse,
)
from app.security import max_bytes_for, rate_limit, read_upload
from app.services.media_pipeline import IMAGE_CONTENT_TYPES, VIDEO_CONTENT_TYPES, process_and_store
from app.services.storage import media_kind
from app.services.notifications import send_email

router = APIRouter(prefix="/api/corruption", tags=["module2-corruption"])

moderator_roles = require_roles(UserRole.MODERATOR, UserRole.ADMIN)


def _feed_item(report: CorruptionReport) -> FeedItemResponse:
    return FeedItemResponse(
        id=report.id,
        accused_department=report.accused_department,
        accused_designation=report.accused_designation,
        description=report.description,
        geohash=report.geohash,
        public_status_badge=report.public_status_badge,
        created_at=report.created_at,
        media_id=report.media_id,
        media_kind=media_kind(report.media_id),
    )


@router.get("/routing-rules", response_model=list[RoutingRuleResponse])
def list_routing_rules(db: Session = Depends(get_db)):
    """Public and auditable by design (spec 2.3: "an auditable rules table")."""
    return db.execute(select(RoutingRule)).scalars().all()


@router.post(
    "/reports",
    response_model=ReportCreateResponse,
    status_code=status.HTTP_201_CREATED,
    # Spec 2.3: rate-limit and fingerprint uploads at device level, not identity level.
    dependencies=[Depends(rate_limit("corruption_report", limit=10, window_seconds=3600))],
)
def submit_report(
    accused_department: str = Form(...),
    accused_designation: str = Form(...),
    accused_party_type: AccusedPartyType = Form(...),
    description: str | None = Form(None),
    geohash: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    No account, no login, no phone, no email (spec 2.3). `geohash` must already be the coarse,
    user-chosen value the client computed - this endpoint does not accept raw lat/lng.
    """
    content_type = file.content_type or ""
    if content_type not in IMAGE_CONTENT_TYPES | VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")

    data = read_upload(file, max_bytes_for(content_type))
    processed = process_and_store(data, content_type, key_prefix="module2")

    tracking_token = secrets.token_urlsafe(24)
    report = CorruptionReport(
        accused_department=accused_department,
        accused_designation=accused_designation,
        accused_party_type=accused_party_type,
        description=description,
        geohash=geohash,
        media_id=processed.media_id,
        tracking_token=tracking_token,
    )
    db.add(report)
    db.commit()

    rule = db.execute(
        select(RoutingRule).where(RoutingRule.accused_party_type == accused_party_type)
    ).scalars().first()
    if rule:
        # Placeholder recipient - a real deployment maps `primary_route_body` to that body's
        # actual intake contact. The one rule that matters most is enforced here again, not just
        # trusted from config: police-personnel reports must never reach local police.
        notify_local_police = rule.notify_local_police and accused_party_type != AccusedPartyType.POLICE_PERSONNEL
        send_email(
            to=f"intake@{rule.primary_route_body.lower().replace(' ', '-')}.gov.in",
            subject=f"New corruption report: {accused_department}",
            body=f"Tracking token: {tracking_token}\nLocal police notified: {notify_local_police}",
        )

    return ReportCreateResponse(tracking_token=tracking_token, moderation_status=report.moderation_status)


@router.get("/reports/track/{tracking_token}", response_model=ReportStatusResponse)
def track_report(tracking_token: str, db: Session = Depends(get_db)):
    report = db.execute(
        select(CorruptionReport).where(CorruptionReport.tracking_token == tracking_token)
    ).scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report found for that tracking token")
    return report


@router.get("/feed", response_model=list[FeedItemResponse])
def public_feed(db: Session = Depends(get_db)):
    """Moderated public feed - only APPROVED reports are ever returned (spec 2.3)."""
    reports = db.execute(
        select(CorruptionReport)
        .where(CorruptionReport.moderation_status == ModerationStatus.APPROVED)
        .order_by(CorruptionReport.created_at.desc())
    ).scalars().all()
    return [_feed_item(r) for r in reports]


@router.get("/moderation/queue", response_model=list[FeedItemResponse])
def moderation_queue(user: User = Depends(moderator_roles), db: Session = Depends(get_db)):
    reports = db.execute(
        select(CorruptionReport)
        .where(CorruptionReport.moderation_status == ModerationStatus.PENDING)
        .order_by(CorruptionReport.created_at.asc())
    ).scalars().all()
    return [_feed_item(r) for r in reports]


@router.post("/moderation/{report_id}/approve", response_model=FeedItemResponse)
def approve_report(
    report_id: uuid.UUID,
    payload: ModerationDecisionRequest,
    user: User = Depends(moderator_roles),
    db: Session = Depends(get_db),
):
    report = db.get(CorruptionReport, report_id)
    if not report or report.moderation_status != ModerationStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending report with that ID")
    report.moderation_status = ModerationStatus.APPROVED
    report.public_status_badge = PublicStatusBadge.UNVERIFIED_ALLEGATION
    db.commit()
    db.refresh(report)
    return _feed_item(report)


@router.post("/moderation/{report_id}/reject", response_model=FeedItemResponse)
def reject_report(
    report_id: uuid.UUID,
    payload: ModerationDecisionRequest,
    user: User = Depends(moderator_roles),
    db: Session = Depends(get_db),
):
    report = db.get(CorruptionReport, report_id)
    if not report or report.moderation_status != ModerationStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending report with that ID")
    report.moderation_status = ModerationStatus.REJECTED
    report.public_status_badge = PublicStatusBadge.DISMISSED
    db.commit()
    db.refresh(report)
    return _feed_item(report)


@router.post("/reports/{report_id}/status", response_model=FeedItemResponse)
def update_status_badge(
    report_id: uuid.UUID,
    badge: PublicStatusBadge,
    user: User = Depends(require_roles(UserRole.VIGILANCE_OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Oversight-body-side status update (Under Investigation / Action Taken / Dismissed)."""
    report = db.get(CorruptionReport, report_id)
    if not report or report.moderation_status != ModerationStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No published report with that ID")
    report.public_status_badge = badge
    db.commit()
    db.refresh(report)
    return _feed_item(report)
