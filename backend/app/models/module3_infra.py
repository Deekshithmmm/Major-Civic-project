"""
Module 3 - civic infrastructure reporting (spec 2.4). Fully built.

Privacy: reports hold no uploader identifier by default (spec: "anonymous by default"). The
*optional* status-update phone number lives in IssueContactPhone, a separate table joined by a
one-way token, purged on issue resolution (spec 2.6, "Privacy by design") - never joined
directly to InfrastructureIssue and never displayed publicly.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, Geometry, UTCDateTime


class IssueStatus(str, enum.Enum):
    REPORTED = "reported"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    OVERDUE = "overdue"


class IssueCategory(Base):
    """
    Category + default SLA + escalation chain, read from config (spec: "Amounts and the ladder
    itself must live in a configuration table, never hard-coded" - same principle applies to
    SLA hours here). Seeded from the spec's table in seed/seed_data.py.
    """

    __tablename__ = "issue_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_department: Mapped[str] = mapped_column(String(255), nullable=False)
    escalation_department_tier2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duplicate_radius_meters: Mapped[int] = mapped_column(Integer, default=50, nullable=False)


class InfrastructureIssue(Base):
    __tablename__ = "infrastructure_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("issue_categories.id"), nullable=False
    )
    category: Mapped[IssueCategory] = relationship()

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    ward_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status"), default=IssueStatus.REPORTED, nullable=False
    )
    upvote_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Opaque media ID(s) returned by the shared media pipeline. Nullable: a report is valid
    # without a photo (e.g. phoned-in style reports in future), though the UI requires one.
    media_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tracking_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Matches IssueContactPhone.contact_token when the citizen opted in to SMS status updates.
    # Not a foreign key: this is the only linkage between the two tables, so a raw dump of either
    # table alone does not reveal which issue a phone number belongs to (spec 2.6).
    contact_token: Mapped[str | None] = mapped_column(String(64), nullable=True)

    sla_deadline: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolution_proof_media_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now()
    )


class IssueStatusHistory(Base):
    """Append-style history of status transitions, for the public status board's timeline."""

    __tablename__ = "issue_status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("infrastructure_issues.id"), nullable=False, index=True
    )
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus, name="issue_status_history_status"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class IssueContactPhone(Base):
    """
    Optional citizen phone number for status updates only (spec 2.4, step 1). Deliberately not
    a foreign key - joined to InfrastructureIssue.contact_token only, a random token generated
    at submission time, so a table dump of either table alone does not reveal the link. Row is
    deleted (not just status-flagged) on issue resolution (spec 2.6).
    """

    __tablename__ = "issue_contact_phones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())
