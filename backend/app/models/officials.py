"""
Officials/desk registry: who is responsible for what, per ward and department. Holds
work-contact data only (name, designation, email, phone at the office) — no citizen data.
Retention: indefinite, updated as postings change. Seeded with dummy contacts (spec 2.6).
"""

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ResponsibleDesk(Base):
    """
    A department's contact point for a given ward — e.g. "Roads Engineer, Ward 14" or
    "Sanitation Inspector, Zone 3". Module 3's jurisdiction resolution looks up rows here after
    resolving a report's ward via PostGIS.
    """

    __tablename__ = "responsible_desks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    ward_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    municipal_zone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grievance_api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
