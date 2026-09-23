"""
Append-only audit log for every official action: who viewed/confirmed/dismissed what, and when
(spec 2.6, "Audit and access control"). Holds official user IDs and action metadata, never
citizen identifiers (citizens are anonymous by design in Modules 2-4). Retention: indefinite,
kept for the lifetime of the platform for accountability purposes.

INSERT-only at the application layer; migration 3fabf2cb5577 adds DB triggers that reject
UPDATE, DELETE *and* TRUNCATE on this table, so "append-only" is a database guarantee rather
than a convention. TRUNCATE needs its own statement-level trigger - a row-level one does not
fire on it, which would otherwise leave a one-statement hole straight through the audit trail.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AuditAction(str, enum.Enum):
    VIEW = "view"
    CONFIRM = "confirm"
    RECLASSIFY = "reclassify"
    DISMISS = "dismiss"
    UNBLUR_TOGGLE = "unblur_toggle"
    CHALLAN_ISSUED = "challan_issued"
    STATUS_CHANGE = "status_change"
    LOGIN = "login"
    # Module 2 grievance workflow (IT Rules 2021). Distinct values rather than a STATUS_CHANGE
    # with explanatory text, because "what did we remove and on whose say-so" is the first
    # question anyone auditing a takedown power asks, and it should be a WHERE clause.
    GRIEVANCE_DECISION = "grievance_decision"
    TAKEDOWN = "takedown"
    REPLY_PUBLISHED = "reply_published"


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, name="audit_action"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
