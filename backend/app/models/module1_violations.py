"""
Module 1 - violation detection & enforcement assist (spec 2.2). SCHEMA + STUBS ONLY in this
build - the officer review queue endpoints exist and work against seeded cases, but there is no
YOLOv8/ANPR pipeline wired in yet (see docs/spec-summary.md). Do not implement face recognition
against any identity database here, and do not add any column that stores or derives an Aadhaar
number - that constraint is load-bearing, not a style preference (spec 1.1).

Evidence referenced by media_id lives in the shared media pipeline's object storage with location
metadata stripped. Photos are face-blurred before write; video clips are NOT - a deliberate
deviation from the spec's hard constraint in 2.2, made for speed (see services/media_pipeline.py).
Retention: deleted once the challan is paid or the appeal window closes, whichever is later
(spec 2.6).
"""

import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class IdentityPath(str, enum.Enum):
    ANPR = "anpr"
    UNIDENTIFIED = "unidentified"


class ViolationClassConfig(Base):
    """Configurable per city (spec 2.2 table). Seeded with the spec's eleven classes."""

    __tablename__ = "violation_class_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_path: Mapped[IdentityPath] = mapped_column(Enum(IdentityPath, name="identity_path"), nullable=False)
    statutory_section: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FineLadderConfig(Base):
    """
    Amount per occurrence-count, per violation class, in a rolling 12-month window. Never
    hard-coded (spec 2.2, "Fine ladder"): real amounts are set by state/municipal by-law and
    differ by city and violation class.
    """

    __tablename__ = "fine_ladder_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    violation_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("violation_class_configs.id"), nullable=False
    )
    occurrence_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1st, 2nd, ...
    amount_rupees: Mapped[int] = mapped_column(Integer, nullable=False)


class SyntheticVehicleRegistry(Base):
    """
    Seeded stand-in for a VAHAN-style registry, behind the same interface a real government API
    adapter would implement (spec: "Build a VAHAN-style adapter behind an interface"). Synthetic
    data only - no real vehicle or owner records.
    """

    __tablename__ = "synthetic_vehicle_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ViolationCaseStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    RECLASSIFIED = "reclassified"
    DISMISSED = "dismissed"


class ViolationCase(Base):
    """
    A candidate case built by the detection pipeline (or a citizen upload). The system never
    issues a fine on its own - `status` only moves out of PENDING_REVIEW via an authenticated
    officer action, recorded in the audit log (spec 2.2, step 4).
    """

    __tablename__ = "violation_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    violation_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("violation_class_configs.id"), nullable=False
    )
    violation_class: Mapped[ViolationClassConfig] = relationship()

    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    camera_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    ward_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    media_id: Mapped[str] = mapped_column(String(255), nullable=False)  # faces blurred in photos, not video

    identity_path: Mapped[IdentityPath] = mapped_column(Enum(IdentityPath, name="case_identity_path"), nullable=False)
    resolved_plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[ViolationCaseStatus] = mapped_column(
        Enum(ViolationCaseStatus, name="violation_case_status"), default=ViolationCaseStatus.PENDING_REVIEW
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="camera_pipeline")  # or "citizen_upload"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChallanStatus(str, enum.Enum):
    ISSUED = "issued"
    DISPUTED = "disputed"
    UPHELD_ON_APPEAL = "upheld_on_appeal"
    OVERTURNED_ON_APPEAL = "overturned_on_appeal"
    PAID = "paid"


class Challan(Base):
    """Created only on officer confirmation of a ViolationCase (spec 2.2, step 5-7)."""

    __tablename__ = "challans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("violation_cases.id"), unique=True, nullable=False
    )
    case: Mapped[ViolationCase] = relationship()
    statutory_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_rupees: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ChallanStatus] = mapped_column(Enum(ChallanStatus, name="challan_status"), default=ChallanStatus.ISSUED)

    dispute_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    second_reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
