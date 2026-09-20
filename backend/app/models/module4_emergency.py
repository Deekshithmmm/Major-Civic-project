"""
Module 4 - emergency incident reporting & evidence custody (spec 2.5).

What holds this module together, and must not be loosened:
  - Any offence involving a minor is a HARD STOP. The upload is refused before a single byte is
    accepted, and the user is routed to 1098/112/CCPWC. Accepting it "to forward it" is itself
    an offence under POCSO and IT Act 67B.
  - Evidence goes to a separate vault bucket, never the media bucket Modules 1-3 use, and is
    never served on any public surface.
  - Only an investigating officer who supplies a case or FIR number may view evidence, and every
    view appends to the chain of custody. Moderators have no route to it at all.
  - Sexual-offence and minor categories never appear in any public surface, at any stage - not
    the ledger's per-category view, not the hotspot map, not a case record.

What is published instead is the transparency layer: a station response ledger whose
unacknowledged-past-SLA counter does the work a public video feed was meant to do, and an
aggregate hotspot map on a quarterly lag with a k-anonymity threshold of five.

Still not built (see README): storage-policy-level separation at the bucket layer rather than in
application code, per-report encryption keys, auto-purge on a retention schedule, and the
irreversible blur that would be required before video could be accepted for a restricted
category - which is why video is refused there today.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class OffenceCategory(str, enum.Enum):
    ASSAULT_IN_PROGRESS = "assault_in_progress"
    HOMICIDE_OR_BODY_DISCOVERED = "homicide_or_body_discovered"
    SEXUAL_OFFENCE_ADULT = "sexual_offence_adult"
    MINOR_INVOLVED = "minor_involved"  # hard stop - see EmergencyReportRoutingRule.is_hard_stop
    NARCOTICS = "narcotics"
    HUMAN_TRAFFICKING = "human_trafficking"


class EmergencyReportRoutingRule(Base):
    """
    Category -> alert routing + public-record policy (spec 2.5, "Offence categories and
    routing"). `is_hard_stop=True` (MINOR_INVOLVED only) means: refuse the upload outright,
    never write it to any store, and redirect the user to 1098/112/CCPWC. That is a product
    behaviour, not just a config flag - if this ever gets a router, the hard-stop check must
    happen before any file bytes are accepted, not after.
    """

    __tablename__ = "emergency_routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[OffenceCategory] = mapped_column(
        Enum(OffenceCategory, name="offence_category"), unique=True, nullable=False
    )
    alert_routed_to: Mapped[str] = mapped_column(String(500), nullable=False)
    has_public_record: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_hard_stop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PoliceStation(Base):
    """
    Jurisdictional station for a ward, and the unit the response ledger is published against.
    Work-contact data only, no personal data. Seeded synthetically.
    """

    __tablename__ = "police_stations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    ward_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EmergencyReport(Base):
    """
    Minimal server record (spec 2.5, step 3): the hash, upload time, coarse geohash and
    category. There is deliberately no column for the uploader's IP, account or device - so
    there is nothing to disclose, and the tracking token is the only handle that exists.

    `is_restricted` carries the sexual-offence hard constraint: once true, no role including
    admin can move it back to false. That is enforced by a database trigger (migration
    3fabf2cb5577), not an application check, exactly as the spec requires - verified by
    attempting the UPDATE directly in SQL and having it rejected.

    Personal data: none by design. Retention: on a documented legal schedule tied to the case;
    the auto-purge job the spec calls for is not built (see README).
    """

    __tablename__ = "emergency_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[OffenceCategory] = mapped_column(
        Enum(OffenceCategory, name="emergency_report_category"), nullable=False
    )
    # Null when the report carries no evidence file - reporting without filming is a first-class
    # path here, not a degraded one (spec: the app must not reward filming over helping).
    original_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # key in the EVIDENCE VAULT bucket

    geohash: Mapped[str] = mapped_column(String(20), nullable=False)
    ward_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("police_stations.id"), nullable=True
    )

    tracking_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # The response ledger is computed from these timestamps, so inaction is visible without
    # anyone deciding to report it (spec 2.5, "Station response ledger").
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fir_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fir_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_without_fir_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChainOfCustodyEntry(Base):
    """
    Append-only record of the evidence's life: the sealing hash at intake, then every access
    with officer ID, case number and timestamp. UPDATE, DELETE and TRUNCATE are blocked at the
    database level by migration 3fabf2cb5577, so a break in the chain cannot be hidden by
    rewriting it - only by a gap, which is itself visible.

    `officer_user_id` and `case_or_fir_number` are null only on the intake entry, which no
    officer performs.
    """

    __tablename__ = "chain_of_custody_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emergency_reports.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # "sealed" | "viewed"
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    officer_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    case_or_fir_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
