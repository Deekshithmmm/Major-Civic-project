# The database

MySQL 8.0, InnoDB, `utf8mb4_0900_ai_ci`, server time zone pinned to UTC. 24 application tables
plus Alembic's `alembic_version`. The schema is defined by the SQLAlchemy models in
`backend/app/models/` and created by a single Alembic migration; nothing is created by hand.

This document is the map. For the *why* behind a particular table, read its model docstring —
every one states what personal data it holds, if any, and for how long.

---

## Tables by module

### Shared

| Table | Holds |
|---|---|
| `users` | Officials only. Citizens never have an account anywhere in this system. |
| `wards` | Ward boundaries as `POLYGON SRID 4326`, plus zone and constituency. |
| `responsible_desks` | Which desk owns which department in which ward. |
| `audit_log` | Every official action. **Append-only.** |

### Module 1 — violations and enforcement

| Table | Holds |
|---|---|
| `violation_class_configs` | The violation catalogue, configurable per city. |
| `fine_ladder_configs` | Fine amounts by offence count. Read from config, never hard-coded. |
| `violation_cases` | A case awaiting officer review. Location is `POINT SRID 4326`. |
| `challans` | Issued only after an officer confirms. The server never issues one by itself. |
| `synthetic_vehicle_registry` | Fictional plates for the demo. No real registry is contacted. |

### Module 2 — anonymous corruption reporting

| Table | Holds |
|---|---|
| `corruption_reports` | The report. **No uploader column of any kind exists** — not an IP, not an account, not a device. |
| `corruption_routing_rules` | Which oversight body receives which accused-party type. |
| `content_grievances` | IT Rules 2021 complaints asking for a report to come down. |
| `right_of_reply` | Responses from the office an allegation concerns. |

### Module 3 — civic infrastructure

| Table | Holds |
|---|---|
| `issue_categories` | Categories with their SLA hours and duplicate radius. |
| `infrastructure_issues` | The report. Location is `POINT SRID 4326`. |
| `issue_status_history` | Status transitions, for the public timeline. |
| `issue_contact_phones` | Optional update number, deliberately in a separate table, purged on resolution. |

### Module 4 — emergency and the police station network

| Table | Holds |
|---|---|
| `police_stations` | The station network. Location is nullable `POINT SRID 4326`. |
| `emergency_routing_rules` | Offence category to routing behaviour. |
| `emergency_reports` | The report. Carries a coarse geohash, never a precise point. |
| `chain_of_custody_entries` | Every seal and every access of sealed evidence. **Append-only.** |
| `station_diary_entries` | The General Diary (Roznamcha). **Append-only.** |
| `fir_records` | The FIR register, with station-issued numbers and Zero FIR transfers. |
| `case_diary_entries` | The case diary under BNSS s.192. **Append-only.** |

---

## Foreign keys

Fourteen, all `ON DELETE CASCADE` where a child cannot outlive its parent:

```
case_diary_entries.fir_id           -> fir_records.id
chain_of_custody_entries.report_id  -> emergency_reports.id
challans.case_id                    -> violation_cases.id
content_grievances.report_id        -> corruption_reports.id
emergency_reports.station_id        -> police_stations.id
fine_ladder_configs.violation_class_id -> violation_class_configs.id
fir_records.report_id               -> emergency_reports.id
fir_records.station_id              -> police_stations.id
fir_records.transferred_to_station_id  -> police_stations.id
infrastructure_issues.category_id   -> issue_categories.id
issue_status_history.issue_id       -> infrastructure_issues.id
right_of_reply.report_id            -> corruption_reports.id
station_diary_entries.station_id    -> police_stations.id
violation_cases.violation_class_id  -> violation_class_configs.id
```

`users.jurisdiction_ward_id` and `users.police_station_id` are deliberately *not* foreign keys:
an official's posting is work-identity data that should survive a ward being redrawn or a station
being decommissioned, rather than cascading their account away.

---

## Column type decisions

| Concern | Choice | Why |
|---|---|---|
| Primary keys | `CHAR(32)` via SQLAlchemy `Uuid` | MySQL has no native UUID type. Random IDs mean a report ID leaks no ordering and no volume — you cannot tell from one how many others exist. |
| Timestamps | `DATETIME(6)` via `UTCDateTime` | MySQL's DATETIME carries no zone, so the type converts at the driver boundary: naive UTC in the column, timezone-aware UTC in Python. `fsp=6` because whole-second rounding would break same-second ordering such as the diary serial. |
| Geometry | native `POINT` / `POLYGON SRID 4326` | Real spatial types with real spatial indexes, not a pair of floats. |
| Enumerations | MySQL `ENUM` | The value set is part of the schema, so an invalid status cannot be written even by hand. |
| Money | `NUMERIC` | Fines are currency; binary floating point has no business here. |
| Long text | `TEXT` | Descriptions, notes and grievance bodies, capped in the API schemas rather than the column. |

Three spatial indexes exist — on `wards.boundary`, `infrastructure_issues.location` and
`violation_cases.location`. `police_stations.location` has none because MySQL requires a spatial
index column to be `NOT NULL`, and a station may not have a mapped location yet.

---

## Latitude first

**MySQL reads SRID 4326 latitude-first.** It honours the axis order in the EPSG definition;
PostGIS does not. Reverse it and every coordinate remains a plausible-looking number while
pointing somewhere else entirely.

Every WKT string in this codebase is therefore `POINT(lat lng)`, and coordinates are read back
with `ST_Latitude`/`ST_Longitude` rather than `ST_X`/`ST_Y` so the axis is named rather than
implied. `geo_point()` and `parse_point()` in `app/database.py` are the only places a coordinate
pair is built or taken apart.

Two smoke-test checks guard this: one measures a known 1111 m separation, one asserts every
seeded station still falls inside the demo city's bounding box.

---

## Append-only tables, and the three accounts

Four tables may only ever be added to: `audit_log`, `chain_of_custody_entries`,
`station_diary_entries`, `case_diary_entries`. They are the record that makes the rest of the
system checkable, so "append-only" has to be a property of the database rather than a habit of
the code.

MySQL needs two mechanisms to get there, because one is not enough:

**Triggers** — a `BEFORE UPDATE` and a `BEFORE DELETE` on each of the four, raising SQLSTATE
45000. These bind every account, including the schema owner.

**Privileges** — because MySQL triggers *do not fire on TRUNCATE*. The statement empties the
table and returns no error; this was verified against MySQL 8.0.46 on a probe table before the
schema was written. PostgreSQL could refuse it with a statement-level `BEFORE TRUNCATE` trigger
and MySQL has no equivalent. What stops it instead is that TRUNCATE requires the DROP privilege,
which the application's account is never granted.

Hence three accounts:

| Account | Privileges | Used by |
|---|---|---|
| `civic` | Per-table DML. SELECT + INSERT only on the four append-only tables. **No DDL at all.** | The running application |
| `civic_migrate` | Full DDL on this schema, plus `SET_USER_ID` so it can create triggers while binary logging is on | Alembic only |
| `root` | Everything | `python -m app.db.harden`, once, at setup |

`app/db/harden.py` is what applies the per-table grants, and it must be re-run after any
migration that adds a table. Until it runs, `civic` can connect and do nothing — the correct
failure mode for a half-set-up database.

One further guarantee sits alongside these: an `emergency_reports` trigger makes `is_restricted`
irreversible. A report sealed as restricted can never be unsealed, by any account.

Ten smoke-test checks assert all of the above by connecting as each account in turn, rather than
by asking the application whether it thinks the rules hold.

---

## Working with it

```bash
alembic upgrade head        # apply the schema (as civic_migrate)
python -m app.db.harden     # apply privileges (as root) - required
python -m app.seed.seed_data

alembic check               # does the schema still match the models?
alembic revision --autogenerate -m "what changed"
```

`alembic check` is the one to run before committing a model change. It reports drift between the
models and the live database, and it is how the port was verified as complete.

For a reader who does not work with databases, <http://localhost:5173/database> describes all of
this in plain words with live rows — see the README. What follows is the developer's view.

Open it in a browser at <http://localhost:8080> (Adminer, started by `docker compose up -d`):
system **MySQL**, server **db**, database **civic_accountability**. Log in as `root` /
`civic_root_password` to see everything, or as `civic` / `civic_dev_password` to see exactly what
the application can reach — trying `TRUNCATE audit_log` as `civic` is the quickest way to watch
the append-only guarantee work.

Or inspect the running schema from a terminal:

```bash
docker exec -it major-civic-project-db-1 \
  mysql -uroot -pcivic_root_password civic_accountability

SHOW TABLES;
SHOW CREATE TABLE audit_log\G
SELECT trigger_name, event_manipulation, event_object_table
  FROM information_schema.triggers;
SHOW GRANTS FOR 'civic'@'%';
```

Note that DDL in MySQL is **not transactional**. A migration that fails halfway leaves the
tables it already created in place, and rerunning it will fail on the first one that exists. The
recovery is to drop and recreate the schema, then migrate again — which is survivable here
because the data is synthetic, and is worth knowing before it happens during a demo.
