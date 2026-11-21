"""add teacher ai settings

Revision ID: 661d37e7b81e
Revises: d7fec49c16de
Create Date: 2026-11-19 01:27:35.338060+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "661d37e7b81e"
down_revision: str | Sequence[str] | None = "d7fec49c16de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``teacher_ai_settings``."""
    op.create_table(
        "teacher_ai_settings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("masked_key", sa.String(length=16), nullable=True),
        sa.Column("key_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("default_model_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["default_model_id"],
            ["inquiry_models.model_id"],
            name=op.f("fk_teacher_ai_settings_default_model_id_inquiry_models"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_teacher_ai_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_teacher_ai_settings")),
    )


def downgrade() -> None:
    """Drop ``teacher_ai_settings``."""
    op.drop_table("teacher_ai_settings")
