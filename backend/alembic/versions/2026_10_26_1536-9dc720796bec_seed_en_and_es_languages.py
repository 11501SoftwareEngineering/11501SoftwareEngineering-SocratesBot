"""seed en and es languages

Revision ID: 9dc720796bec
Revises: 4ec9e46f727b
Create Date: 2026-10-26 15:36:57.997843+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9dc720796bec"
down_revision: str | Sequence[str] | None = "4ec9e46f727b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed ``en`` and ``es`` language rows (keep existing ``zh-TW``)."""
    op.execute(
        sa.text(
            "INSERT INTO languages (id, code, name) "
            "VALUES "
            "(gen_random_uuid(), 'en', 'English'), "
            "(gen_random_uuid(), 'es', 'Español') "
            "ON CONFLICT (code) DO NOTHING"
        )
    )


def downgrade() -> None:
    """No-op: do not delete seeded language rows that may already be referenced."""
    pass
