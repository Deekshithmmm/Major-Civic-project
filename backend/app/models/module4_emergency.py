"""
Module 4 - emergency incident reporting & evidence custody (spec 2.5). SCHEMA ONLY, NOT WIRED
TO ANY ROUTER in this build. Do not add endpoints against these tables without first building
the storage-policy-level access separation the spec requires (moderators must have zero access;
only an investigating officer with a case/FIR number may view evidence; the vault must be a
physically separate bucket/policy/encryption key from Modules 1-3's object storage). Building
the endpoints before that separation exists would recreate exactly the failure mode the spec
warns about in Part 1.5.

EmergencyReportRoutingRule is populated by seed data so the design is reviewable even though
the capture/vault pipeline isn't built. See docs/spec-summary.md, "Module 4" section, before
touching this file.
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


class EmergencyReport(Base):
    """
    NOT IMPLEMENTED - table shape only, matching spec 2.5's evidence custody pipeline. No
    uploader IP/account/device identifier column exists, matching the spec's requirement. A
    real implementation must write `original_sha256` client-side before any server processing
    (chain-of-custody requirement) and must never expose media outside a separate evidence-vault
    bucket. `is_restricted` models the sexual-offence hard constraint: once true, no role
    including admin can move it back to false. That is enforced by a database trigger
    (migration 3fabf2cb5577), not by an application check, exactly as the spec requires -
    verified by attempting the UPDATE directly in SQL and having it rejected.
    """

    __tablename__ = "emergency_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[OffenceCategory] = mapped_column(
        Enum(OffenceCategory, name="emergency_report_category"), nullable=False
    )
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    geohash: Mapped[str] = mapped_column(String(20), nullable=False)
    tracking_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChainOfCustodyEntry(Base):
    """
    NOT IMPLEMENTED (no routes write to this yet). Append-only record of every access to an
    EmergencyReport's evidence; UPDATE/DELETE/TRUNCATE are already blocked at the database
    level by migration 3fabf2cb5577, so whatever is eventually built on top of this table
    cannot quietly rewrite the chain.
    """

    __tablename__ = "chain_of_custody_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emergency_reports.id"), nullable=False, index=True
    )
    officer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    case_or_fir_number: Mapped[str] = mapped_column(String(100), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
