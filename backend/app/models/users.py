"""
Officials-only accounts. Citizens are never required to create an account anywhere in this
system (spec 2.1). This table holds work-identity data for officials only: name, email, role,
jurisdiction scope, and a password hash. No retention limit — this is employment-linked
account data, not a citizen record.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, enum.Enum):
    MUNICIPAL_OFFICER = "municipal_officer"
    VIGILANCE_OFFICER = "vigilance_officer"
    MODERATOR = "moderator"
    DEPARTMENT_ENGINEER = "department_engineer"
    INVESTIGATING_OFFICER = "investigating_officer"
    ADMIN = "admin"


class User(Base):
    """
    Roles are deliberately narrow. Route-level dependencies (see app/auth.py) enforce that,
    e.g., a moderator cannot query Module 1 identity data and a municipal officer cannot query
    Module 2 reports (spec 2.6, "Audit and access control"). This table alone does not enforce
    Module 4's storage-policy-level separation — see docs/spec-summary.md Module 4 notes.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)

    # Scope: which ward/department/jurisdiction this official acts for. Null = citywide (admin).
    jurisdiction_ward_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Police roles are posted to a station; station procedures and the reports queue are scoped
    # by this, so one station's officers cannot work another station's cases.
    police_station_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
