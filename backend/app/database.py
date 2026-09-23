"""
Engine, session and the three custom column types the MySQL port needs.

MySQL 8 is the database of record. Two of its differences from PostgreSQL are sharp enough that
they are handled here, once, rather than at every call site:

  - **DATETIME carries no time zone.** `UTCDateTime` stores naive UTC and hands back
    timezone-aware UTC, so application code keeps comparing aware datetimes and never has to
    remember which side of the driver it is on.
  - **Geometry is not a first-class SQLAlchemy type.** `Geometry` renders MySQL's native
    `POINT SRID 4326` / `POLYGON SRID 4326`, binds WKT through `ST_GeomFromText` and reads back
    through `ST_AsText`, so a model attribute is an ordinary readable string.

The axis-order trap is the thing to know before touching any of this: **SRID 4326 in MySQL is
latitude-first**, because MySQL honours the axis order in the EPSG definition. PostGIS is
longitude-first. Every WKT string in this codebase is therefore `POINT(lat lng)`, and coordinates
are read back with `ST_Latitude`/`ST_Longitude` rather than `ST_X`/`ST_Y` so that the meaning is
in the function name and cannot be silently transposed. `geo_point()` and `parse_point()` below
are the only places that build or take apart a coordinate pair; use them.
"""

from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator, UserDefinedType

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UTCDateTime(TypeDecorator):
    """
    A timestamp that is always UTC on both sides of the driver.

    MySQL's DATETIME stores no zone, so a naive value written by one code path and an aware one
    written by another would compare wrongly and nobody would notice until an SLA was measured
    against the wrong hour. Binding strips to naive UTC; reading attaches UTC back.

    Fractional seconds are explicit: MySQL's DATETIME defaults to whole seconds, which would
    round every timestamp and break same-second ordering such as the General Diary serial.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # Already naive: the caller's convention in this codebase is UTC.
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Geometry(UserDefinedType):
    """
    MySQL's native spatial types, in the shape the rest of the codebase expects.

    Reading a geometry column gives WKT (`'POINT(12.98 77.6)'`) rather than driver binary, so
    `parse_point()` can take it apart. Writing takes WKT and wraps it in `ST_GeomFromText` with
    the SRID attached — MySQL rejects a geometry whose SRID does not match the column's, which
    is a useful guard rather than an annoyance.
    """

    cache_ok = True

    def __init__(self, geometry_type: str = "POINT", srid: int = 4326):
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **kw) -> str:
        return f"{self.geometry_type} SRID {self.srid}"

    def bind_expression(self, bindvalue):
        return func.ST_GeomFromText(bindvalue, self.srid)

    def column_expression(self, col):
        return func.ST_AsText(col)


def geo_point(lat: float, lng: float) -> str:
    """
    WKT for a point, latitude first.

    Latitude first is not a preference: MySQL reads SRID 4326 in the EPSG axis order, so writing
    `POINT(lng lat)` here would place every report in the wrong hemisphere while still returning
    plausible-looking numbers. `float()` also keeps a non-numeric value from reaching the SQL
    string.
    """
    return f"POINT({float(lat)} {float(lng)})"


def parse_point(wkt: str | None) -> tuple[float, float] | None:
    """Take `'POINT(12.98 77.6)'` back to `(lat, lng)`. Returns None for a null column."""
    if not wkt:
        return None
    inner = wkt[wkt.index("(") + 1 : wkt.rindex(")")]
    lat, lng = inner.split()
    return float(lat), float(lng)


def latitude(col):
    """`ST_Latitude`, not `ST_X`: on a geographic SRS the name says which axis it is."""
    return func.ST_Latitude(col)


def longitude(col):
    return func.ST_Longitude(col)


def distance_metres(col, lat: float, lng: float):
    """Great-circle distance in metres between a geometry column and a lat/lng pair."""
    return func.ST_Distance_Sphere(col, func.ST_GeomFromText(geo_point(lat, lng), 4326))


def contains_point(boundary_col, lat: float, lng: float):
    """Whether a polygon column contains the given point. Boundary itself counts as outside."""
    return func.ST_Contains(boundary_col, func.ST_GeomFromText(geo_point(lat, lng), 4326))
