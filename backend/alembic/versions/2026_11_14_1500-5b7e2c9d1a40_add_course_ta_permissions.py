"""add course ta permissions

Revision ID: 5b7e2c9d1a40
Revises: 5675a5896ad2
Create Date: 2026-11-14 15:00:00.000000+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b7e2c9d1a40"
down_revision: str | Sequence[str] | None = "5675a5896ad2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``course_ta_permissions`` (one row per granted TA permission)."""
    op.create_table(
        "course_ta_permissions",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "permission IN "
            "('edit_topics', 'view_reports', 'edit_summary', 'view_members')",
            name=op.f("ck_course_ta_permissions_permission"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id", "user_id"],
            ["course_memberships.course_id", "course_memberships.user_id"],
            name="fk_course_ta_permissions_course_id_course_memberships",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "course_id",
            "user_id",
            "permission",
            name=op.f("pk_course_ta_permissions"),
        ),
    )


def downgrade() -> None:
    op.drop_table("course_ta_permissions")
