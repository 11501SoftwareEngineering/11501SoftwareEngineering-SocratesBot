"""drop sessions is_anonymous

Revision ID: 5675a5896ad2
Revises: 9dc720796bec
Create Date: 2026-11-14 03:03:32.509118+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5675a5896ad2"
down_revision: str | Sequence[str] | None = "9dc720796bec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop ``sessions.is_anonymous``; the anonymous-sharing API is gone."""
    op.drop_column("sessions", "is_anonymous")


def downgrade() -> None:
    """Restore ``sessions.is_anonymous`` (existing rows become ``false``)."""
    op.add_column(
        "sessions",
        sa.Column(
            "is_anonymous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("sessions", "is_anonymous", server_default=None)
