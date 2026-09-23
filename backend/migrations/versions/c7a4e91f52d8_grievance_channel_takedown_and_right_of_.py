"""grievance channel, takedown and right of reply (IT Rules 2021)

Revision ID: c7a4e91f52d8
Revises: b489707d2370
Create Date: 2026-09-23 10:12:41.882160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a4e91f52d8'
down_revision: Union[str, None] = 'b489707d2370'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Added to audit_action so a takedown is queryable as its own thing rather than hiding inside a
# generic status change. PostgreSQL 12+ allows ADD VALUE inside a transaction as long as the new
# value is not *used* in the same transaction, which nothing here does.
NEW_AUDIT_ACTIONS = ("GRIEVANCE_DECISION", "TAKEDOWN", "REPLY_PUBLISHED")

OLD_AUDIT_ACTIONS = (
    "VIEW",
    "CONFIRM",
    "RECLASSIFY",
    "DISMISS",
    "UNBLUR_TOGGLE",
    "CHALLAN_ISSUED",
    "STATUS_CHANGE",
    "LOGIN",
)


def upgrade() -> None:
    for value in NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        'content_grievances',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket', sa.String(length=20), nullable=False),
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column(
            'ground',
            sa.Enum(
                'FACTUALLY_INCORRECT',
                'IDENTIFIES_PRIVATE_PERSON',
                'DEFAMATORY',
                'SUB_JUDICE',
                'NOT_MY_DEPARTMENT',
                'OTHER',
                name='grievance_ground',
            ),
            nullable=False,
        ),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('complainant_name', sa.String(length=255), nullable=False),
        sa.Column('complainant_email', sa.String(length=320), nullable=False),
        sa.Column('complainant_designation', sa.String(length=255), nullable=True),
        sa.Column(
            'status',
            sa.Enum('RECEIVED', 'ACKNOWLEDGED', 'UPHELD', 'REJECTED', name='grievance_status'),
            nullable=False,
        ),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('decided_by_user_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['corruption_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_grievances_report_id'), 'content_grievances', ['report_id'], unique=False)
    op.create_index(op.f('ix_content_grievances_ticket'), 'content_grievances', ['ticket'], unique=True)

    op.create_table(
        'right_of_reply',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('author_department', sa.String(length=255), nullable=False),
        sa.Column('author_designation', sa.String(length=255), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('author_contact_email', sa.String(length=320), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'PUBLISHED', 'REJECTED', name='reply_status'),
            nullable=False,
        ),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['corruption_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_right_of_reply_report_id'), 'right_of_reply', ['report_id'], unique=False)

    op.add_column('corruption_reports', sa.Column('taken_down_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('corruption_reports', sa.Column('takedown_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('corruption_reports', 'takedown_reason')
    op.drop_column('corruption_reports', 'taken_down_at')

    op.drop_index(op.f('ix_right_of_reply_report_id'), table_name='right_of_reply')
    op.drop_table('right_of_reply')
    op.drop_index(op.f('ix_content_grievances_ticket'), table_name='content_grievances')
    op.drop_index(op.f('ix_content_grievances_report_id'), table_name='content_grievances')
    op.drop_table('content_grievances')

    # create_table creates these; drop_table does not drop them, and leaving them behind makes a
    # later re-upgrade fail with "type already exists".
    for enum_name in ('grievance_ground', 'grievance_status', 'reply_status'):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    # PostgreSQL cannot remove a value from an enum, so audit_action has to be rebuilt without
    # the three added above. Any row already using one is remapped to STATUS_CHANGE rather than
    # deleted: the detail text says what actually happened, and silently dropping rows out of an
    # append-only audit log during a schema downgrade would be precisely the kind of quiet
    # erasure the triggers on this table exist to prevent. The triggers are lifted only for the
    # length of that remap and restored immediately, inside the same transaction.
    op.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_log_append_only")
    op.execute(
        "UPDATE audit_log SET action = 'STATUS_CHANGE' "
        "WHERE action::text IN ('GRIEVANCE_DECISION', 'TAKEDOWN', 'REPLY_PUBLISHED')"
    )
    op.execute("ALTER TABLE audit_log ENABLE TRIGGER audit_log_append_only")

    values = ", ".join(f"'{v}'" for v in OLD_AUDIT_ACTIONS)
    op.execute("ALTER TYPE audit_action RENAME TO audit_action_old")
    op.execute(f"CREATE TYPE audit_action AS ENUM ({values})")
    op.execute(
        "ALTER TABLE audit_log ALTER COLUMN action TYPE audit_action USING action::text::audit_action"
    )
    op.execute("DROP TYPE audit_action_old")
