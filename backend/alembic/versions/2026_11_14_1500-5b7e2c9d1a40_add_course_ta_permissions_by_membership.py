"""key course memberships by id and add course ta permissions

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
    """Key memberships by ``id`` and create ``course_ta_permissions``.

    Existing memberships get a random id; ``(course_id, user_id)`` stays
    unique. Each TA permission row points at one membership.
    """
    op.add_column("course_memberships", sa.Column("id", sa.UUID(), nullable=True))
    op.execute("UPDATE course_memberships SET id = gen_random_uuid()")
    op.alter_column("course_memberships", "id", nullable=False)
    op.drop_constraint(
        op.f("pk_course_memberships"), "course_memberships", type_="primary"
    )
    op.create_primary_key(op.f("pk_course_memberships"), "course_memberships", ["id"])
    op.create_unique_constraint(
        op.f("uq_course_memberships_course_id"),
        "course_memberships",
        ["course_id", "user_id"],
    )

    op.create_table(
        "course_ta_permissions",
        sa.Column("course_membership_id", sa.UUID(), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "permission IN "
            "('edit_topics', 'view_reports', 'edit_summary', 'view_members')",
            name=op.f("ck_course_ta_permissions_permission"),
        ),
        sa.ForeignKeyConstraint(
            ["course_membership_id"],
            ["course_memberships.id"],
            name="fk_course_ta_permissions_course_membership_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "course_membership_id",
            "permission",
            name=op.f("pk_course_ta_permissions"),
        ),
    )


def downgrade() -> None:
    """Drop TA permissions and key memberships by ``(course_id, user_id)``."""
    op.drop_table("course_ta_permissions")
    op.drop_constraint(
        op.f("uq_course_memberships_course_id"), "course_memberships", type_="unique"
    )
    op.drop_constraint(
        op.f("pk_course_memberships"), "course_memberships", type_="primary"
    )
    op.create_primary_key(
        op.f("pk_course_memberships"), "course_memberships", ["course_id", "user_id"]
    )
    op.drop_column("course_memberships", "id")
