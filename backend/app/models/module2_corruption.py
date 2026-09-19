"""
Module 2 - anonymous corruption reporting (spec 2.3). SCHEMA + upload/routing model only in
this build; the moderation dashboard UI is not built yet (see docs/spec-summary.md).

Hard privacy constraints encoded here, not just documented:
  - No uploader_id, account_id, or IP column exists on CorruptionReport, deliberately. There is
    nothing to delete because nothing is collected (spec 2.6).
  - `tracking_token` is the *only* handle either the uploader or anyone else has on this report.
  - `geohash` is coarse (ward/500m) and user-chosen on a map client-side, never raw device GPS.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccusedPartyType(str, enum.Enum):
    STATE_GOVT_EMPLOYEE = "state_govt_employee"
    CENTRAL_GOVT_EMPLOYEE = "central_govt_employee"
    POLICE_PERSONNEL = "police_personnel"
    MUNICIPAL_OR_DEPT_STAFF = "municipal_or_dept_staff"


class RoutingRule(Base):
    """
    Auditable rules table mapping accused party type + jurisdiction to an oversight body (spec
    2.3, "Routing rules"). A city reconfigures this without a code change. Seeded from the
    spec's table. `notify_local_police` is a hard False for POLICE_PERSONNEL, enforced again in
    the router (never trust config alone for the one rule where a mistake endangers someone).
    """

    __tablename__ = "corruption_routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    accused_party_type: Mapped[AccusedPartyType] = mapped_column(
        Enum(AccusedPartyType, name="accused_party_type"), unique=True, nullable=False
    )
    primary_route_body: Mapped[str] = mapped_column(String(255), nullable=False)
    notify_local_police: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ModerationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicStatusBadge(str, enum.Enum):
    UNVERIFIED_ALLEGATION = "unverified_allegation"
    UNDER_INVESTIGATION = "under_investigation"
    ACTION_TAKEN = "action_taken"
    DISMISSED = "dismissed"


class CorruptionReport(Base):
    __tablename__ = "corruption_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    accused_department: Mapped[str] = mapped_column(String(255), nullable=False)
    accused_designation: Mapped[str] = mapped_column(String(255), nullable=False)
    accused_party_type: Mapped[AccusedPartyType] = mapped_column(
        Enum(AccusedPartyType, name="corruption_accused_party_type"), nullable=False
    )
    # Never a name field, by design. The platform never names an accused individual (spec 2.3).

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geohash: Mapped[str] = mapped_column(String(20), nullable=False)  # ward/500m precision, user-chosen
    media_id: Mapped[str] = mapped_column(String(255), nullable=False)  # bystanders blurred in photos, not video

    moderation_status: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus, name="moderation_status"), default=ModerationStatus.PENDING
    )
    public_status_badge: Mapped[PublicStatusBadge] = mapped_column(
        Enum(PublicStatusBadge, name="public_status_badge"), default=PublicStatusBadge.UNVERIFIED_ALLEGATION
    )

    tracking_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Explicitly absent, on purpose: uploader_id, ip_address, device_account, phone, email.
