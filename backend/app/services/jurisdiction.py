"""
PostGIS jurisdiction resolution (spec 2.4, step 3): map a lat/lng pin to a ward, then look up
the responsible desk(s) from the officials registry.
"""

from geoalchemy2.functions import ST_Contains, ST_SetSRID, ST_MakePoint
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.jurisdiction import Ward
from app.models.officials import ResponsibleDesk


def resolve_ward(db: Session, lat: float, lng: float) -> Ward | None:
    point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    stmt = select(Ward).where(ST_Contains(Ward.boundary, point))
    return db.execute(stmt).scalars().first()


def resolve_responsible_desk(db: Session, ward_id, department: str) -> ResponsibleDesk | None:
    stmt = select(ResponsibleDesk).where(
        ResponsibleDesk.department == department,
        ResponsibleDesk.ward_id == ward_id,
    )
    desk = db.execute(stmt).scalars().first()
    if desk:
        return desk
    # Fall back to a zone-level desk if no ward-specific one is registered.
    stmt_zone = select(ResponsibleDesk).where(
        ResponsibleDesk.department == department,
        ResponsibleDesk.ward_id.is_(None),
    )
    return db.execute(stmt_zone).scalars().first()
