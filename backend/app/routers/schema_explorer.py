"""
The database, explained, for people who do not read schemas. Serves the /database page.

**This router refuses to load outside development.** It is a readable window onto the database,
and a readable window onto the database is exactly what this system spends the rest of its code
preventing. `main.py` only registers it when ENV=development, and every handler checks again, so
deleting the registration guard by accident does not quietly publish it.

Within development it still does not show everything. Columns listed as masked in
`schema_catalogue` are dropped from the query itself rather than filtered afterwards, so a
whistleblower's tracking token or a resident's phone number is never loaded into memory here at
all. The page tells the reader which columns were withheld and why, because a redaction that is
not visible teaches the reader the wrong thing about the system.
"""

import re
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.schema_catalogue import (
    APPEND_ONLY,
    COLUMN_NOTES,
    EDITABLE,
    GROUPS,
    HIDDEN_TABLES,
    SOFT_REFERENCES,
    TABLES,
    WRITE_BLOCKED,
    humanise,
)

router = APIRouter(prefix="/api/schema", tags=["database-explorer"])
settings = get_settings()

# MySQL reports these for the spatial columns; they need ST_AsText() to come back readable
# rather than as driver binary.
GEOMETRY_TYPES = {"point", "polygon", "geometry", "linestring", "multipolygon"}

ROW_LIMIT = 15

# When a column points at another table, show what it points at rather than its identifier.
# "Category: 73ceca0d…" tells a reader nothing; "Category: Broken or dark street light" is the
# whole answer. Tried in order, first one the referenced table actually has.
DISPLAY_COLUMNS = ("label", "name", "full_name", "code", "slug", "fir_number", "ticket")


def _foreign_keys(db: Session, table: str) -> dict[str, str]:
    """{column: referenced_table} for this table."""
    rows = db.execute(
        text(
            "SELECT column_name, referenced_table_name FROM information_schema.key_column_usage "
            "WHERE table_schema = DATABASE() AND table_name = :t "
            "AND referenced_table_name IS NOT NULL"
        ),
        {"t": table},
    ).all()
    return {r[0]: r[1] for r in rows}


def _label_lookup(db: Session, ref_table: str, ids: set) -> dict:
    """Map identifiers in `ref_table` to something a person can read."""
    if not ids:
        return {}
    available = {c["name"] for c in _columns(db, ref_table)}
    display = next((c for c in DISPLAY_COLUMNS if c in available), None)
    if display is None:
        return {}
    placeholders = ", ".join(f":v{i}" for i in range(len(ids)))
    params = {f"v{i}": v for i, v in enumerate(ids)}
    rows = db.execute(
        text(f"SELECT id, `{display}` FROM `{ref_table}` WHERE id IN ({placeholders})"), params
    ).all()
    return {r[0]: r[1] for r in rows}


def _require_development() -> None:
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available outside development",
        )


def _columns(db: Session, table: str) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT column_name, data_type, is_nullable, column_key, column_type, "
            "column_default, extra "
            "FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t "
            "ORDER BY ordinal_position"
        ),
        {"t": table},
    ).all()
    return [
        {
            "name": r[0],
            "data_type": (r[1] or "").lower(),
            "nullable": r[2] == "YES",
            "is_key": r[3] in ("PRI", "MUL", "UNI"),
            "column_type": r[4] or "",
            # A column the database fills for itself is not something a form has to ask for.
            "has_default": r[5] is not None or bool(r[6]),
        }
        for r in rows
    ]


# Filled in by the database, never by the form.
GENERATED_COLUMNS = {"id", "created_at", "updated_at", "received_at", "submitted_at"}


def _enum_options(column_type: str) -> list[str]:
    """`enum('PENDING','APPROVED')` -> ['PENDING', 'APPROVED']."""
    return re.findall(r"'([^']*)'", column_type or "")


def _field(col: dict, table: str) -> dict | None:
    """One input on the 'add a row' form, or None if the database fills this itself."""
    name = col["name"]
    if name in GENERATED_COLUMNS:
        return None

    t = col["data_type"]
    if t == "point":
        kind = "latlng"
    elif t == "polygon":
        kind = "bbox"
    elif t == "enum":
        kind = "enum"
    elif col["column_type"].startswith("tinyint(1)"):
        kind = "boolean"
    elif t in ("int", "bigint", "smallint", "decimal", "numeric", "float", "double"):
        kind = "number"
    elif t == "date":
        kind = "date"
    elif t in ("datetime", "timestamp"):
        kind = "datetime"
    elif t == "text":
        kind = "longtext"
    else:
        kind = "text"

    length = None
    match = re.search(r"\((\d+)\)", col["column_type"] or "")
    if match and kind == "text":
        length = int(match.group(1))

    return {
        "name": name,
        "label": humanise(name),
        "kind": kind,
        "options": _enum_options(col["column_type"]) if kind == "enum" else [],
        "required": not col["nullable"],
        "max_length": length,
        "help": COLUMN_NOTES.get(f"{table}.{name}"),
    }


def _readable_type(col: dict) -> str:
    """MySQL's own type names mean little to a general reader."""
    t = col["data_type"]
    if t in GEOMETRY_TYPES:
        return "Place on the map"
    if t == "enum":
        return "One of a fixed set"
    if t in ("datetime", "timestamp"):
        return "Date and time"
    if t == "date":
        return "Date"
    if t in ("int", "bigint", "smallint", "tinyint"):
        return "Yes / no" if col["column_type"].startswith("tinyint(1)") else "Number"
    if t in ("decimal", "numeric", "float", "double"):
        return "Amount"
    if t == "char" and "(32)" in col["column_type"]:
        return "Identifier"
    return "Text"


def _format(value, col: dict):
    """Render one cell for a reader rather than for a developer."""
    if value is None:
        return None
    t = col["data_type"]
    if t in GEOMETRY_TYPES:
        # Arrives as WKT because the query asked for ST_AsText.
        inner = str(value)
        if inner.startswith("POINT("):
            lat, lng = inner[6:-1].split()
            return f"{float(lat):.4f}, {float(lng):.4f}"
        return "a mapped area" if inner.startswith("POLYGON") else inner
    if t == "char" and "(32)" in col["column_type"]:
        # Shown in full. Truncating it looked tidier but made the one thing an identifier is for
        # - telling two rows apart, or matching one against another table - impossible.
        return str(value)
    if col["column_type"].startswith("tinyint(1)"):
        return "Yes" if value else "No"
    if t == "enum":
        return str(value).replace("_", " ").capitalize()
    text_value = str(value)
    return text_value if len(text_value) <= 160 else text_value[:157] + "…"


@router.get("/tables")
def list_tables(db: Session = Depends(get_db)):
    """Every table, grouped and named for a reader, with live row counts."""
    _require_development()

    present = {
        r[0]
        for r in db.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'"
            )
        ).all()
    }

    groups = []
    for key, label, blurb in GROUPS:
        tables = []
        for name, meta in TABLES.items():
            if meta["group"] != key or name in HIDDEN_TABLES or name not in present:
                continue
            count = db.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar() or 0
            tables.append(
                {
                    "name": name,
                    "label": meta["label"],
                    "row_is": meta["row_is"],
                    "row_count": count,
                    "append_only": name in APPEND_ONLY,
                    "has_masked": bool(meta.get("masked")),
                }
            )
        if tables:
            groups.append({"key": key, "label": label, "blurb": blurb, "tables": tables})

    unlisted = sorted(present - set(TABLES) - HIDDEN_TABLES)
    return {
        "groups": groups,
        "table_count": sum(len(g["tables"]) for g in groups),
        # If a migration adds a table and nobody writes its entry here, say so rather than
        # letting the page quietly claim to show the whole database.
        "undocumented": unlisted,
    }


@router.get("/tables/{table}")
def describe_table(table: str, db: Session = Depends(get_db)):
    """One table: what a row is, what each column means, and a sample of real rows."""
    _require_development()

    meta = TABLES.get(table)
    if meta is None:
        # Only catalogued tables, so this can never be pointed at an arbitrary table name.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such table")

    columns = _columns(db, table)
    if not columns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such table")

    masked = meta.get("masked", {})
    shown = [c for c in columns if c["name"] not in masked]
    # Identifier last. It is real and worth showing in full, but leading every table with 32
    # characters of hex buries the columns a reader came for.
    shown.sort(key=lambda c: c["name"] == "id")

    # Masked columns are left out of the SELECT entirely - not fetched and then hidden.
    select_parts = []
    for c in shown:
        if c["data_type"] in GEOMETRY_TYPES:
            select_parts.append(f"ST_AsText(`{c['name']}`) AS `{c['name']}`")
        else:
            select_parts.append(f"`{c['name']}`")

    rows = db.execute(text(f"SELECT {', '.join(select_parts)} FROM `{table}` LIMIT {ROW_LIMIT}")).all()
    total = db.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0

    # Replace each foreign key with the name of the row it points at. One small query per
    # referenced table, not one per cell.
    fks = {c: ref for c, ref in _foreign_keys(db, table).items() if c not in masked}
    # Columns that reference another table without a constraint behind them are just as opaque
    # to a reader, so they are resolved the same way.
    for column in (c["name"] for c in shown):
        if column not in fks and column in SOFT_REFERENCES:
            fks[column] = SOFT_REFERENCES[column]
    resolved: dict[str, dict] = {}
    for column, ref_table in fks.items():
        index = next(i for i, c in enumerate(shown) if c["name"] == column)
        ids = {row[index] for row in rows if row[index] is not None}
        resolved[column] = _label_lookup(db, ref_table, ids)

    return {
        "name": table,
        "label": meta["label"],
        "row_is": meta["row_is"],
        "purpose": meta["purpose"],
        "note": meta.get("note"),
        "append_only": table in APPEND_ONLY,
        "row_count": total,
        "showing": len(rows),
        "columns": [
            {
                "name": c["name"],
                "label": humanise(c["name"]),
                "means": COLUMN_NOTES.get(f"{table}.{c['name']}"),
                "type": "Points at another table" if c["name"] in fks else _readable_type(c),
                "optional": c["nullable"],
                "points_at": TABLES.get(fks[c["name"]], {}).get("label") if c["name"] in fks else None,
                # The identifier columns are real, but they are noise to a reader, so the page
                # can push them to the end rather than lead with them.
                "is_identifier": c["name"] == "id",
            }
            for c in shown
        ],
        "rows": [
            [
                resolved.get(col["name"], {}).get(value) or _format(value, col)
                for value, col in zip(row, shown)
            ]
            for row in rows
        ],
        "withheld": [{"column": k, "reason": v} for k, v in masked.items()],
        "editable": table in EDITABLE,
        "blocked_reason": WRITE_BLOCKED.get(table, (None, None))[0],
        "blocked_route": WRITE_BLOCKED.get(table, (None, None))[1],
        "fields": [f for f in (_field(c, table) for c in columns) if f] if table in EDITABLE else [],
    }


@router.post("/tables/{table}", status_code=status.HTTP_201_CREATED)
def create_row(table: str, values: dict = Body(...), db: Session = Depends(get_db)):
    """
    Add a row, for the reference and configuration tables where that is a real thing to do.

    Everything else is refused by name in `schema_catalogue.WRITE_BLOCKED`, and several of those
    refusals are the system's own guarantees restated rather than caution: a challan has to be
    issued by an officer to mean anything, and an audit log anyone can type into proves nothing.
    The page shows the reason and, where the right route is a form elsewhere in the app, links it.
    """
    _require_development()

    if table not in TABLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such table")
    if table not in EDITABLE:
        reason = WRITE_BLOCKED.get(table, ("Rows are not added to this table by hand.", None))[0]
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    columns = {c["name"]: c for c in _columns(db, table)}
    fields = {f["name"]: f for f in (_field(c, table) for c in columns.values()) if f}

    assignments: dict[str, str] = {"id": ":p_id"}
    params: dict[str, object] = {"p_id": uuid.uuid4().hex}

    for name, field in fields.items():
        raw = values.get(name)
        blank = raw is None or (isinstance(raw, str) and not raw.strip())

        if blank:
            if field["required"] and columns[name].get("has_default") is not True:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field['label']} is required",
                )
            continue

        if field["kind"] == "enum" and raw not in field["options"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field['label']} must be one of: {', '.join(field['options'])}",
            )

        if field["kind"] == "latlng":
            # Built here rather than taken as text: the caller supplies two numbers and cannot
            # get the latitude-first axis order wrong, because they never write the WKT.
            try:
                lat, lng = float(raw["lat"]), float(raw["lng"])
            except (TypeError, KeyError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field['label']} needs a latitude and a longitude",
                )
            assignments[name] = f"ST_GeomFromText(:p_{name}, 4326)"
            params[f"p_{name}"] = f"POINT({lat} {lng})"
            continue

        if field["kind"] == "bbox":
            try:
                lat1, lng1 = float(raw["lat1"]), float(raw["lng1"])
                lat2, lng2 = float(raw["lat2"]), float(raw["lng2"])
            except (TypeError, KeyError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field['label']} needs two corners",
                )
            # A closed rectangle: MySQL rejects a ring that does not end where it began.
            ring = (
                f"{lat1} {lng1}, {lat1} {lng2}, {lat2} {lng2}, {lat2} {lng1}, {lat1} {lng1}"
            )
            assignments[name] = f"ST_GeomFromText(:p_{name}, 4326)"
            params[f"p_{name}"] = f"POLYGON(({ring}))"
            continue

        if field["kind"] == "boolean":
            params[f"p_{name}"] = 1 if raw in (True, "true", "1", 1, "yes") else 0
        elif field["kind"] == "number":
            try:
                params[f"p_{name}"] = float(raw) if "." in str(raw) else int(raw)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field['label']} must be a number",
                )
        else:
            params[f"p_{name}"] = raw
        assignments[name] = f":p_{name}"

    column_sql = ", ".join(f"`{c}`" for c in assignments)
    value_sql = ", ".join(assignments.values())

    try:
        db.execute(text(f"INSERT INTO `{table}` ({column_sql}) VALUES ({value_sql})"), params)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Duplicate keys and failed foreign keys are the two a person filling a form will hit,
        # and MySQL's own wording for them is not much help on its own.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The database refused this row: {str(exc.orig)[:200]}",
        ) from exc
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The database refused this row: {str(exc.orig)[:200]}",
        ) from exc

    return {"id": params["p_id"], "table": table}
