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

One apparent exception, which is not one: the grievance and right-of-reply endpoints at the
bottom of this file do store a real name and email. Those belong to the person *objecting* to a
published report, or to the official answering it - never to the person who filed one. A
complaint cannot be disposed of without a way to write back to the complainant, and Rule 3(2)(a)
of the IT Rules 2021 requires exactly that reply. The anonymity promise covers the uploader, and
it is untouched: nothing in this file ever links a grievance to whoever submitted the report it
concerns.
"""

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.config import get_settings
from app.database import get_db
from app.models.audit import AuditAction, AuditLogEntry
from app.models.module2_corruption import (
    AccusedPartyType,
    CorruptionReport,
    ModerationStatus,
    PublicStatusBadge,
    RoutingRule,
)
from app.models.module2_grievance import (
    Grievance,
    GrievanceStatus,
    ReplyStatus,
    RightOfReply,
)
from app.models.users import User, UserRole
from app.schemas.module2_corruption import (
    FeedItemResponse,
    ModerationDecisionRequest,
    ReportCreateResponse,
    ReportStatusResponse,
    RoutingRuleResponse,
)
from app.schemas.module2_grievance import (
    ComplianceResponse,
    GrievanceCreateRequest,
    GrievanceCreateResponse,
    GrievanceDecisionRequest,
    GrievanceOfficerResponse,
    GrievanceQueueItem,
    GrievanceTicketResponse,
    ReplyCreateRequest,
    ReplyCreateResponse,
    ReplyDecisionRequest,
    ReplyPublic,
    ReplyQueueItem,
)
from app.security import max_bytes_for, rate_limit, read_upload
from app.services.grievance import (
    compliance_stats,
    is_overdue,
    new_ticket,
    resolve_deadline,
)
from app.services.media_pipeline import IMAGE_CONTENT_TYPES, VIDEO_CONTENT_TYPES, process_and_store
from app.services.storage import media_kind
from app.services.notifications import send_email

settings = get_settings()

router = APIRouter(prefix="/api/corruption", tags=["module2-corruption"])

moderator_roles = require_roles(UserRole.MODERATOR, UserRole.ADMIN)


def _feed_item(report: CorruptionReport, replies: list[RightOfReply] | None = None) -> FeedItemResponse:
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
        replies=[
            ReplyPublic(
                id=r.id,
                body=r.body,
                author_department=r.author_department,
                author_designation=r.author_designation,
                published_at=r.published_at,
            )
            for r in (replies or [])
        ],
    )


def _published_report(report_id: uuid.UUID, db: Session) -> CorruptionReport:
    """
    The report a citizen may complain about or reply to: published, and still up.

    Anything else is a 404 rather than a 403, deliberately. A distinct "exists but is not
    published" answer would turn these endpoints into an oracle for probing whether a report
    about a given office is sitting in the moderation queue.
    """
    report = db.get(CorruptionReport, report_id)
    if not report or report.moderation_status != ModerationStatus.APPROVED or report.taken_down_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No published report with that ID")
    return report


def _replies_by_report(report_ids: list[uuid.UUID], db: Session) -> dict[uuid.UUID, list[RightOfReply]]:
    """One query for the whole page rather than one per card."""
    if not report_ids:
        return {}
    rows = db.execute(
        select(RightOfReply)
        .where(RightOfReply.report_id.in_(report_ids), RightOfReply.status == ReplyStatus.PUBLISHED)
        .order_by(RightOfReply.published_at.asc())
    ).scalars().all()
    grouped: dict[uuid.UUID, list[RightOfReply]] = {}
    for row in rows:
        grouped.setdefault(row.report_id, []).append(row)
    return grouped


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
    return ReportStatusResponse(
        tracking_token=report.tracking_token,
        moderation_status=report.moderation_status,
        public_status_badge=report.public_status_badge,
        created_at=report.created_at,
        taken_down=report.taken_down_at is not None,
        takedown_reason=report.takedown_reason,
    )


@router.get("/feed", response_model=list[FeedItemResponse])
def public_feed(db: Session = Depends(get_db)):
    """
    Moderated public feed - only APPROVED reports are ever returned (spec 2.3), and only those
    not withdrawn after an upheld grievance.
    """
    reports = db.execute(
        select(CorruptionReport)
        .where(
            CorruptionReport.moderation_status == ModerationStatus.APPROVED,
            CorruptionReport.taken_down_at.is_(None),
        )
        .order_by(CorruptionReport.created_at.desc())
    ).scalars().all()
    replies = _replies_by_report([r.id for r in reports], db)
    return [_feed_item(r, replies.get(r.id)) for r in reports]


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
    report = _published_report(report_id, db)
    report.public_status_badge = badge
    db.commit()
    db.refresh(report)
    return _feed_item(report)


# ---------------------------------------------------------------------------
# Grievance channel and right of reply (IT Rules 2021, Rule 3(2)).
#
# A moderated feed of accusations makes this platform an intermediary, and an intermediary owes
# the people it publishes about a way to object and a way to answer. Both are open to anyone
# without an account, for the same reason reporting is: requiring a login to object would mean
# only the well-resourced ever objected.
# ---------------------------------------------------------------------------


@router.get("/grievance-officer", response_model=GrievanceOfficerResponse)
def grievance_officer() -> GrievanceOfficerResponse:
    """
    Rule 3(2)(a) requires these details to be published, not merely held on file. Serving them
    from config means the page cannot drift out of date relative to where complaints actually
    go.
    """
    return GrievanceOfficerResponse(
        name=settings.grievance_officer_name,
        designation=settings.grievance_officer_designation,
        email=settings.grievance_officer_email,
        address=settings.grievance_officer_address,
        acknowledgement_deadline_hours=settings.grievance_ack_hours,
        resolution_deadline_days=settings.grievance_resolve_days,
    )


@router.get("/compliance", response_model=ComplianceResponse)
def grievance_compliance(db: Session = Depends(get_db)) -> ComplianceResponse:
    """The platform's own record against its two statutory deadlines. Counts only."""
    return ComplianceResponse(**compliance_stats(db))


@router.post(
    "/grievances",
    response_model=GrievanceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    # Looser than the report limit: a department disputing a run of allegations has a legitimate
    # reason to file several, and throttling objections is exactly the wrong thumb on the scale.
    dependencies=[Depends(rate_limit("grievance", limit=20, window_seconds=3600))],
)
def submit_grievance(payload: GrievanceCreateRequest, db: Session = Depends(get_db)):
    """
    Open to anyone, with no account. The acknowledgement is sent here and now rather than left
    for an officer to click, because Rule 3(2)(a)'s 24 hours start running the moment this row
    is written.
    """
    report = _published_report(payload.report_id, db)

    grievance = Grievance(
        ticket=new_ticket(db),
        report_id=report.id,
        ground=payload.ground,
        body=payload.body,
        complainant_name=payload.complainant_name,
        complainant_email=payload.complainant_email,
        complainant_designation=payload.complainant_designation,
    )
    db.add(grievance)
    db.flush()  # server_default fills received_at, which the deadlines are measured from

    received_at = grievance.received_at or datetime.now(timezone.utc)
    try:
        send_email(
            to=grievance.complainant_email,
            subject=f"Grievance received - ticket {grievance.ticket}",
            body=(
                f"Your complaint about a published report has been received.\n"
                f"Ticket: {grievance.ticket}\n"
                f"It will be disposed of by {resolve_deadline(received_at).date().isoformat()}.\n"
                f"Grievance Officer: {settings.grievance_officer_name}, "
                f"{settings.grievance_officer_email}"
            ),
        )
    except Exception:  # noqa: BLE001 - a dead mail gateway must not swallow the complaint
        # Left unacknowledged on purpose. The complaint is still recorded, and the missed
        # acknowledgement shows up in the published compliance figures instead of being
        # papered over with a timestamp for a mail that never went out.
        pass
    else:
        grievance.acknowledged_at = datetime.now(timezone.utc)
        grievance.status = GrievanceStatus.ACKNOWLEDGED

    # No audit row here: audit_log records what *officials* did, and holds official user IDs
    # only. A citizen filing a grievance is not an official action, and the Grievance row is
    # already its own permanent record of it.
    db.commit()
    db.refresh(grievance)

    return GrievanceCreateResponse(
        ticket=grievance.ticket,
        status=grievance.status,
        acknowledged=grievance.acknowledged_at is not None,
        resolution_due_by=resolve_deadline(grievance.received_at),
    )


@router.get("/grievances/track/{ticket}", response_model=GrievanceTicketResponse)
def track_grievance(ticket: str, db: Session = Depends(get_db)):
    grievance = db.execute(select(Grievance).where(Grievance.ticket == ticket)).scalars().first()
    if not grievance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No grievance with that ticket")
    return GrievanceTicketResponse(
        ticket=grievance.ticket,
        status=grievance.status,
        ground=grievance.ground,
        received_at=grievance.received_at,
        acknowledged_at=grievance.acknowledged_at,
        resolution_due_by=resolve_deadline(grievance.received_at),
        resolved_at=grievance.resolved_at,
        resolution_note=grievance.resolution_note,
        overdue=is_overdue(grievance),
    )


@router.get("/grievances/queue", response_model=list[GrievanceQueueItem])
def grievance_queue(user: User = Depends(moderator_roles), db: Session = Depends(get_db)):
    """Oldest first: the one closest to breaching the 15-day deadline is the one to work next."""
    rows = db.execute(
        select(Grievance, CorruptionReport)
        .join(CorruptionReport, CorruptionReport.id == Grievance.report_id)
        .where(Grievance.resolved_at.is_(None))
        .order_by(Grievance.received_at.asc())
    ).all()
    return [
        GrievanceQueueItem(
            id=g.id,
            ticket=g.ticket,
            report_id=g.report_id,
            ground=g.ground,
            body=g.body,
            complainant_name=g.complainant_name,
            complainant_email=g.complainant_email,
            complainant_designation=g.complainant_designation,
            status=g.status,
            received_at=g.received_at,
            acknowledged_at=g.acknowledged_at,
            resolution_due_by=resolve_deadline(g.received_at),
            overdue=is_overdue(g),
            report_department=r.accused_department,
            report_designation=r.accused_designation,
            report_taken_down=r.taken_down_at is not None,
        )
        for g, r in rows
    ]


@router.post("/grievances/{grievance_id}/acknowledge", response_model=GrievanceTicketResponse)
def acknowledge_grievance(
    grievance_id: uuid.UUID,
    user: User = Depends(moderator_roles),
    db: Session = Depends(get_db),
):
    """
    The manual remedy for when the automatic acknowledgement could not be sent. It records that
    someone has now written to the complainant; it does not rewrite history, so a grievance
    acknowledged late still counts as late in the published figures.
    """
    grievance = db.get(Grievance, grievance_id)
    if not grievance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No grievance with that ID")
    if grievance.acknowledged_at is None:
        grievance.acknowledged_at = datetime.now(timezone.utc)
        if grievance.status == GrievanceStatus.RECEIVED:
            grievance.status = GrievanceStatus.ACKNOWLEDGED
        db.add(
            AuditLogEntry(
                actor_user_id=user.id,
                action=AuditAction.STATUS_CHANGE,
                entity_type="content_grievance",
                entity_id=str(grievance.id),
                detail=f"Grievance {grievance.ticket} acknowledged manually",
            )
        )
        db.commit()
        db.refresh(grievance)
    return GrievanceTicketResponse(
        ticket=grievance.ticket,
        status=grievance.status,
        ground=grievance.ground,
        received_at=grievance.received_at,
        acknowledged_at=grievance.acknowledged_at,
        resolution_due_by=resolve_deadline(grievance.received_at),
        resolved_at=grievance.resolved_at,
        resolution_note=grievance.resolution_note,
        overdue=is_overdue(grievance),
    )


@router.post("/grievances/{grievance_id}/decide", response_model=GrievanceTicketResponse)
def decide_grievance(
    grievance_id: uuid.UUID,
    payload: GrievanceDecisionRequest,
    user: User = Depends(moderator_roles),
    db: Session = Depends(get_db),
):
    """
    Uphold and the report comes down; reject and it stays up. Either way the note goes to the
    complainant and, on a takedown, to the anonymous uploader through their tracking token - so
    it must not contain anything about a third party that neither of them should read.

    Two audit rows on an uphold, not one: the decision and the removal are separate facts, and
    an auditor asking "what has ever been removed from this platform" should be able to answer
    it with a single filter on TAKEDOWN.
    """
    grievance = db.get(Grievance, grievance_id)
    if not grievance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No grievance with that ID")
    if grievance.resolved_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That grievance is already disposed of")

    now = datetime.now(timezone.utc)
    grievance.status = GrievanceStatus.UPHELD if payload.uphold else GrievanceStatus.REJECTED
    grievance.resolution_note = payload.note
    grievance.resolved_at = now
    grievance.decided_by_user_id = user.id

    db.add(
        AuditLogEntry(
            actor_user_id=user.id,
            action=AuditAction.GRIEVANCE_DECISION,
            entity_type="content_grievance",
            entity_id=str(grievance.id),
            detail=f"Ticket {grievance.ticket} {grievance.status.value}: {payload.note}",
        )
    )

    if payload.uphold:
        report = db.get(CorruptionReport, grievance.report_id)
        if report and report.taken_down_at is None:
            report.taken_down_at = now
            report.takedown_reason = payload.note
            db.add(
                AuditLogEntry(
                    actor_user_id=user.id,
                    action=AuditAction.TAKEDOWN,
                    entity_type="corruption_report",
                    entity_id=str(report.id),
                    detail=f"Withdrawn on grievance {grievance.ticket} ({grievance.ground.value})",
                )
            )

    try:
        send_email(
            to=grievance.complainant_email,
            subject=f"Grievance {grievance.ticket} - {grievance.status.value}",
            body=payload.note,
        )
    except Exception:  # noqa: BLE001 - the decision stands whether or not the mail goes out
        pass

    db.commit()
    db.refresh(grievance)
    return GrievanceTicketResponse(
        ticket=grievance.ticket,
        status=grievance.status,
        ground=grievance.ground,
        received_at=grievance.received_at,
        acknowledged_at=grievance.acknowledged_at,
        resolution_due_by=resolve_deadline(grievance.received_at),
        resolved_at=grievance.resolved_at,
        resolution_note=grievance.resolution_note,
        overdue=is_overdue(grievance),
    )


@router.post(
    "/replies",
    response_model=ReplyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("right_of_reply", limit=20, window_seconds=3600))],
)
def submit_reply(payload: ReplyCreateRequest, db: Session = Depends(get_db)):
    """
    The answer side of the channel: a department can respond to an allegation and have the
    response published beneath it.

    Held for moderation, because nothing stops a stranger claiming to be the Commissioner's
    office. Verification is a human step - the moderator writes to `author_contact_email` at the
    department's published address - and this build does not pretend to automate it.
    """
    report = _published_report(payload.report_id, db)
    reply = RightOfReply(
        report_id=report.id,
        body=payload.body,
        author_department=payload.author_department,
        author_designation=payload.author_designation,
        author_name=payload.author_name,
        author_contact_email=payload.author_contact_email,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return ReplyCreateResponse(id=reply.id, status=reply.status)


@router.get("/replies/queue", response_model=list[ReplyQueueItem])
def reply_queue(user: User = Depends(moderator_roles), db: Session = Depends(get_db)):
    rows = db.execute(
        select(RightOfReply, CorruptionReport)
        .join(CorruptionReport, CorruptionReport.id == RightOfReply.report_id)
        .where(RightOfReply.status == ReplyStatus.PENDING)
        .order_by(RightOfReply.submitted_at.asc())
    ).all()
    return [
        ReplyQueueItem(
            id=reply.id,
            report_id=reply.report_id,
            body=reply.body,
            author_department=reply.author_department,
            author_designation=reply.author_designation,
            author_name=reply.author_name,
            author_contact_email=reply.author_contact_email,
            status=reply.status,
            submitted_at=reply.submitted_at,
            report_department=report.accused_department,
            report_designation=report.accused_designation,
        )
        for reply, report in rows
    ]


@router.post("/replies/{reply_id}/decide", response_model=ReplyCreateResponse)
def decide_reply(
    reply_id: uuid.UUID,
    payload: ReplyDecisionRequest,
    user: User = Depends(moderator_roles),
    db: Session = Depends(get_db),
):
    reply = db.get(RightOfReply, reply_id)
    if not reply or reply.status != ReplyStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending reply with that ID")

    reply.status = ReplyStatus.PUBLISHED if payload.publish else ReplyStatus.REJECTED
    reply.reviewed_by_user_id = user.id
    if payload.publish:
        reply.published_at = datetime.now(timezone.utc)
        db.add(
            AuditLogEntry(
                actor_user_id=user.id,
                action=AuditAction.REPLY_PUBLISHED,
                entity_type="right_of_reply",
                entity_id=str(reply.id),
                detail=f"Reply from {reply.author_department} verified and published",
            )
        )
    db.commit()
    db.refresh(reply)
    return ReplyCreateResponse(id=reply.id, status=reply.status)
