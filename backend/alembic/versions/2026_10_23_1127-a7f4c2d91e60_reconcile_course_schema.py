
"""Reconcile legacy course schema with the main schema.

Revision ID: a7f4c2d91e60
Revises: 22032e425647
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7f4c2d91e60"
down_revision: str | Sequence[str] | None = "22032e425647"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Reconcile legacy and fresh database schemas."""
    tables = _tables()

    if "courses" not in tables:
        raise RuntimeError(
            "Expected the courses table before schema reconciliation."
        )

    course_columns = _columns("courses")


    if "owner_id" in course_columns and "created_by" not in course_columns:
        # Drop the legacy FK before renaming its column.
        op.drop_constraint(
            "fk_courses_owner_id_users",
            "courses",
            type_="foreignkey",
        )
        op.alter_column(
            "courses",
            "owner_id",
            new_column_name="created_by",
            existing_type=sa.UUID(),
            existing_nullable=False,
        )
        op.create_foreign_key(
            "fk_courses_created_by_users",
            "courses",
            "users",
            ["created_by"],
            ["id"],
            ondelete="CASCADE",
        )

    elif "owner_id" in course_columns and "created_by" in course_columns:
        raise RuntimeError(
            "Both owner_id and created_by exist on courses; "
            "manual reconciliation is required."
        )
    elif "created_by" not in course_columns:
        raise RuntimeError(
            "Neither owner_id nor created_by exists on courses."
        )

    # Nullable JSON field; deliberately no default and no backfill.
    if "COURSE_INSTRUCTORS" not in _columns("courses"):
        op.add_column(
            "courses",
            sa.Column("COURSE_INSTRUCTORS", sa.JSON(), nullable=True),
        )

    tables = _tables()

    if "course_memberships" not in tables:
        op.create_table(
            "course_memberships",
            sa.Column("course_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column(
                "joined_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "role IN ('STUDENT', 'TA')",
                name="ck_course_memberships_role",
            ),
            sa.ForeignKeyConstraint(
                ["course_id"],
                ["courses.id"],
                name="fk_course_memberships_course_id_courses",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="fk_course_memberships_user_id_users",
            ),
            sa.PrimaryKeyConstraint(
                "course_id",
                "user_id",
                name="pk_course_memberships",
            ),
        )

    # Preserve the original enrollment table and copy its records.
    if "course_enrollments" in _tables():
        op.get_bind().execute(
            sa.text(
                """
                INSERT INTO course_memberships
                    (course_id, user_id, role, joined_at)
                SELECT course_id, user_id, 'STUDENT', joined_at
                FROM course_enrollments
                ON CONFLICT (course_id, user_id) DO NOTHING
                """
            )
        )

def downgrade() -> None:
    """Require an explicit recovery plan before reversing reconciliation."""
    raise RuntimeError(
        "This compatibility migration cannot be downgraded safely "
        "across both legacy and fresh database schemas."
    )
