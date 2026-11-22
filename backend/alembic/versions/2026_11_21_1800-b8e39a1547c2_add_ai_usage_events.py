"""Record provider usage independently from course transactions.
Revision ID: b8e39a1547c2
Revises: 8ad603f2c910
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b8e39a1547c2"
down_revision = "8ad603f2c910"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "teacher_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("task", sa.String(80), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("credential_source", sa.String(16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("http_status", sa.Integer()),
        sa.Column("input_tokens", sa.BigInteger()),
        sa.Column("output_tokens", sa.BigInteger()),
        sa.Column("total_tokens", sa.BigInteger()),
        sa.Column("cost_usd", sa.Numeric(18, 10)),
    )
    op.create_index(
        "ix_ai_usage_teacher_started", "ai_usage_events", ["teacher_id", "started_at"]
    )


def downgrade():
    op.drop_index("ix_ai_usage_teacher_started", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
