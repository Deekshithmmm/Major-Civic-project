"""
PostGIS jurisdiction geometry: wards, municipal zones, and assembly constituencies. No personal
data — this is administrative boundary geometry, seeded from synthetic/fictional polygons for
this build (spec 2.6, "Seed data"). Retention: indefinite (reference data).
"""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ward_number: Mapped[str] = mapped_column(String(50), nullable=False)
    municipal_zone: Mapped[str] = mapped_column(String(255), nullable=False)
    assembly_constituency: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False, default="Demo City")

    # Polygon boundary, WGS84 (SRID 4326)
    boundary: Mapped[str] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
