"""Store AI prompt provenance and the dialogue context checkpoint in generation_meta.

Each table that records model output gets one JSONB column, generation_meta,
holding only that row's generation details:

- dialogue_messages, inquiry_revisions, summary_attempts, report_attempts:
  {"prompt_stage", "prompt_version"}
- sessions: {"context_summary": {"text", "message_count", "prompt_stage",
  "prompt_version"}}

Each column has a CHECK that the value is a JSON object or NULL.

Revision ID: 7ce5146e1d3a
Revises: 5b7e2c9d1a40
Create Date: 2026-11-20 11:00:00.000000+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7ce5146e1d3a"
down_revision: str | Sequence[str] | None = "5b7e2c9d1a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "dialogue_messages",
    "inquiry_revisions",
    "summary_attempts",
    "report_attempts",
    "sessions",
)
_OBJECT_CHECK = "generation_meta IS NULL OR jsonb_typeof(generation_meta) = 'object'"


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table, sa.Column("generation_meta", postgresql.JSONB(), nullable=True)
        )
        op.create_check_constraint(
            op.f(f"ck_{table}_generation_meta_object"), table, _OBJECT_CHECK
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_constraint(
            op.f(f"ck_{table}_generation_meta_object"), table, type_="check"
        )
        op.drop_column(table, "generation_meta")
