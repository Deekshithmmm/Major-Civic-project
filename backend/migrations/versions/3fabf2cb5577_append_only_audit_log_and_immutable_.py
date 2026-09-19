"""append-only audit log and immutable restricted flag triggers

Three constraints the spec requires to live in the database rather than in application code,
because an application-level check is bypassed by any direct SQL access and by any future
route that forgets it:

  1. audit_log is append-only (spec 2.6: "Officials cannot delete audit entries; the table is
     append-only at the database level").
  2. chain_of_custody_entries is append-only (spec 2.5: "An immutable append-only record ...
     Any break in the chain is visible"). Module 4 is otherwise unimplemented, but the
     constraint is installed now so the table cannot be built on top of without it.
  3. emergency_reports.is_restricted can never go from true back to false (spec 2.5: "The
     report is marked restricted at creation. No role in the system, including admin, can move
     it to public status. Enforce this as a database constraint, not an application check").

Revision ID: 3fabf2cb5577
Revises: a1d2e31c29b2
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "3fabf2cb5577"
down_revision: Union[str, None] = "a1d2e31c29b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APPEND_ONLY_FN = """
CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only: % is not permitted', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

RESTRICTED_FN = """
CREATE OR REPLACE FUNCTION reject_unrestrict() RETURNS trigger AS $$
BEGIN
    IF OLD.is_restricted AND NOT NEW.is_restricted THEN
        RAISE EXCEPTION 'A restricted emergency report can never be made unrestricted';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(APPEND_ONLY_FN)
    op.execute(RESTRICTED_FN)

    for table in ("audit_log", "chain_of_custody_entries"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_mutation();
            """
        )
        # A row-level trigger does not fire on TRUNCATE, so without this second statement-level
        # trigger the whole audit trail can be erased with one TRUNCATE and the "append-only"
        # guarantee is fiction. Verified: TRUNCATE emptied the table before this was added.
        op.execute(
            f"""
            CREATE TRIGGER {table}_no_truncate
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION reject_mutation();
            """
        )

    op.execute(
        """
        CREATE TRIGGER emergency_reports_no_unrestrict
        BEFORE UPDATE ON emergency_reports
        FOR EACH ROW EXECUTE FUNCTION reject_unrestrict();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS emergency_reports_no_unrestrict ON emergency_reports;")
    for table in ("audit_log", "chain_of_custody_entries"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_truncate ON {table};")
    op.execute("DROP FUNCTION IF EXISTS reject_unrestrict();")
    op.execute("DROP FUNCTION IF EXISTS reject_mutation();")
