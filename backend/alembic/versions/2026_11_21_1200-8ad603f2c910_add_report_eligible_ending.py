"""Separate report-eligible ending from goal completion.

Revision ID: 8ad603f2c910
Revises: 7ce5146e1d3a
"""

import sqlalchemy as sa
from alembic import op

revision = "8ad603f2c910"
down_revision = "7ce5146e1d3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_sessions_outcome"), "sessions", type_="check")
    op.create_check_constraint(
        op.f("ck_sessions_outcome"),
        "sessions",
        "outcome IN ('open', 'completed', 'ended', 'abandoned', 'closed_by_summary')",
    )
    op.add_column(
        "sessions", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("sessions", sa.Column("ending_reason", sa.String(32), nullable=True))
    op.execute(
        "UPDATE sessions SET ended_at = completed_at, ending_reason = 'goal_reached' WHERE outcome = 'completed'"
    )


def downgrade() -> None:
    # Do not silently relabel unfinished learning as success or destroy reporting semantics.
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM sessions WHERE outcome = 'ended')
        THEN RAISE EXCEPTION 'Cannot downgrade while ended dialogues exist'; END IF; END $$""")
    op.drop_column("sessions", "ending_reason")
    op.drop_column("sessions", "ended_at")
    op.drop_constraint(op.f("ck_sessions_outcome"), "sessions", type_="check")
    op.create_check_constraint(
        op.f("ck_sessions_outcome"),
        "sessions",
        "outcome IN ('open', 'completed', 'abandoned', 'closed_by_summary')",
    )
