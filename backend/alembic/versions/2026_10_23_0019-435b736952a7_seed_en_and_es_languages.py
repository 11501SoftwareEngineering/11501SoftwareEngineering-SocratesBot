"""seed en and es languages

Revision ID: 435b736952a7
Revises: 22032e425647
Create Date: 2026-10-23 00:19:13.343655+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "435b736952a7"
down_revision: str | Sequence[str] | None = "22032e425647"
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
