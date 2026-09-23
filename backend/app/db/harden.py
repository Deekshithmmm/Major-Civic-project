"""
Grants the application account exactly the privileges it needs, and not one more.

    python -m app.db.harden

Run this once after `alembic upgrade head`, and again after any migration that adds a table.

**This script is what makes the audit log append-only on MySQL.** On PostgreSQL a statement-level
`BEFORE TRUNCATE` trigger could refuse the one statement that erases a table in a single shot.
MySQL has no such thing — triggers do not fire on TRUNCATE at all, and the table empties with no
error. Verified on MySQL 8.0.46 before this was written.

What stops it instead is the privilege system: TRUNCATE requires the DROP privilege on the table,
so an account that has never been granted DROP cannot issue one. The triggers created by the
migration still block UPDATE and DELETE for *every* account including the schema owner; this
script closes the remaining hole for the account that actually serves traffic.

The result is two layers rather than one:

    UPDATE / DELETE   -> refused by trigger, for everyone
    TRUNCATE / DROP   -> refused by privilege, for the application account
    ALTER             -> refused by privilege, for the application account

A connection as `civic_migrate` can still truncate the audit log, exactly as a PostgreSQL
superuser could drop the trigger and do the same. The boundary is that the credentials the
application holds cannot do it, and those are the ones exposed if the application is compromised.
"""

import sys

from sqlalchemy import create_engine, text

from app.config import get_settings

settings = get_settings()

# The account the application connects as. Matches docker/mysql-init/01-app-user.sql.
APP_USER = "civic"
APP_HOST = "%"

# Tables the application may only ever add rows to. Each also carries UPDATE/DELETE triggers
# from the migration; withholding the privilege is what additionally rules out TRUNCATE.
APPEND_ONLY_TABLES = (
    "audit_log",
    "chain_of_custody_entries",
    "station_diary_entries",
    "case_diary_entries",
)

# Alembic's bookkeeping. The seed script reads it to refuse an unmigrated database; nothing in
# the application writes it.
READ_ONLY_TABLES = ("alembic_version",)


def harden() -> int:
    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    schema = engine.url.database

    # pymysql runs `statement % args` on everything it sends, and this account's host is
    # literally "%", so it has to be doubled or the driver reads it as a format specifier and
    # raises before MySQL ever sees the statement. Everything interpolated below is a constant
    # in this file or a table name read from information_schema - none of it is user input.
    account = f"'{APP_USER}'@'{APP_HOST}'"
    account_sql = account.replace("%", "%%")

    with engine.begin() as conn:
        tables = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name"
                ),
                {"schema": schema},
            )
        ]
        if not tables:
            print(f"No tables in `{schema}`. Run `alembic upgrade head` first.", file=sys.stderr)
            return 1

        # Start from nothing every time, so this is idempotent and so a privilege granted by
        # hand during debugging does not survive quietly.
        conn.exec_driver_sql(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {account_sql}")

        appended, written, readable, missing = [], [], [], []
        for table in tables:
            ref = f"`{schema}`.`{table}`"
            if table in APPEND_ONLY_TABLES:
                conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {ref} TO {account_sql}")
                appended.append(table)
            elif table in READ_ONLY_TABLES:
                conn.exec_driver_sql(f"GRANT SELECT ON {ref} TO {account_sql}")
                readable.append(table)
            else:
                conn.exec_driver_sql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {ref} TO {account_sql}")
                written.append(table)

        conn.exec_driver_sql("FLUSH PRIVILEGES")

        missing = [t for t in APPEND_ONLY_TABLES if t not in tables]

    print(f"Hardened `{schema}` for {account}:")
    print(f"  append-only (SELECT, INSERT)          {len(appended)}: {', '.join(appended) or '-'}")
    print(f"  read-only   (SELECT)                  {len(readable)}: {', '.join(readable) or '-'}")
    print(f"  read/write  (SELECT, INSERT, UPDATE, DELETE)  {len(written)} tables")
    print("  no DDL granted, so TRUNCATE, DROP and ALTER are all refused for this account.")

    if missing:
        # Loud, because silently skipping one means that table is writable after all.
        print(
            f"\nWARNING: expected append-only tables not found in the schema: {', '.join(missing)}.\n"
            "They were not hardened. Check the migration ran and the names here are current.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(harden())
