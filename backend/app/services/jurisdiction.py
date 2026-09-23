"""
Jurisdiction resolution (spec 2.4, step 3): map a lat/lng pin to a ward, then look up the
responsible desk(s) from the officials registry.

Runs on MySQL 8 spatial. `contains_point` builds the point latitude-first, which is what SRID
4326 means in MySQL - see app/database.py before changing anything here.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import contains_point
from app.models.jurisdiction import Ward
from app.models.officials import ResponsibleDesk


def resolve_ward(db: Session, lat: float, lng: float) -> Ward | None:
    stmt = select(Ward).where(contains_point(Ward.boundary, lat, lng))
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
