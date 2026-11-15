"""key course memberships by id

Revision ID: 8f3a1c6d2e57
Revises: 5b7e2c9d1a40
Create Date: 2026-11-15 20:00:00.000000+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f3a1c6d2e57"
down_revision: str | Sequence[str] | None = "5b7e2c9d1a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_TA_FK = "fk_course_ta_permissions_course_id_course_memberships"
_NEW_TA_FK = "fk_course_ta_permissions_course_membership_id"


def upgrade() -> None:
    """Give memberships an ``id`` key and point TA permissions at it.

    Existing memberships get a random id and existing TA permissions are
    moved onto their membership's id, so no data is lost.
    """
    op.add_column("course_memberships", sa.Column("id", sa.UUID(), nullable=True))
    op.execute("UPDATE course_memberships SET id = gen_random_uuid()")
    op.alter_column("course_memberships", "id", nullable=False)

    op.add_column(
        "course_ta_permissions",
        sa.Column("course_membership_id", sa.UUID(), nullable=True),
    )
    op.execute(
        """
        UPDATE course_ta_permissions AS p
        SET course_membership_id = m.id
        FROM course_memberships AS m
        WHERE m.course_id = p.course_id AND m.user_id = p.user_id
        """
    )
    op.alter_column("course_ta_permissions", "course_membership_id", nullable=False)
    op.drop_constraint(_OLD_TA_FK, "course_ta_permissions", type_="foreignkey")
    op.drop_constraint(
        op.f("pk_course_ta_permissions"), "course_ta_permissions", type_="primary"
    )

    op.drop_constraint(
        op.f("pk_course_memberships"), "course_memberships", type_="primary"
    )
    op.create_primary_key(op.f("pk_course_memberships"), "course_memberships", ["id"])
    op.create_unique_constraint(
        op.f("uq_course_memberships_course_id"),
        "course_memberships",
        ["course_id", "user_id"],
    )

    op.drop_column("course_ta_permissions", "course_id")
    op.drop_column("course_ta_permissions", "user_id")
    op.create_primary_key(
        op.f("pk_course_ta_permissions"),
        "course_ta_permissions",
        ["course_membership_id", "permission"],
    )
    op.create_foreign_key(
        _NEW_TA_FK,
        "course_ta_permissions",
        "course_memberships",
        ["course_membership_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Restore the ``(course_id, user_id)`` keys, keeping TA permissions."""
    op.add_column(
        "course_ta_permissions", sa.Column("course_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "course_ta_permissions", sa.Column("user_id", sa.UUID(), nullable=True)
    )
    op.execute(
        """
        UPDATE course_ta_permissions AS p
        SET course_id = m.course_id, user_id = m.user_id
        FROM course_memberships AS m
        WHERE m.id = p.course_membership_id
        """
    )
    op.alter_column("course_ta_permissions", "course_id", nullable=False)
    op.alter_column("course_ta_permissions", "user_id", nullable=False)
    op.drop_constraint(_NEW_TA_FK, "course_ta_permissions", type_="foreignkey")
    op.drop_constraint(
        op.f("pk_course_ta_permissions"), "course_ta_permissions", type_="primary"
    )

    op.drop_constraint(
        op.f("uq_course_memberships_course_id"), "course_memberships", type_="unique"
    )
    op.drop_constraint(
        op.f("pk_course_memberships"), "course_memberships", type_="primary"
    )
    op.create_primary_key(
        op.f("pk_course_memberships"), "course_memberships", ["course_id", "user_id"]
    )

    op.drop_column("course_ta_permissions", "course_membership_id")
    op.create_primary_key(
        op.f("pk_course_ta_permissions"),
        "course_ta_permissions",
        ["course_id", "user_id", "permission"],
    )
    op.create_foreign_key(
        _OLD_TA_FK,
        "course_ta_permissions",
        "course_memberships",
        ["course_id", "user_id"],
        ["course_id", "user_id"],
        ondelete="CASCADE",
    )
    op.drop_column("course_memberships", "id")
