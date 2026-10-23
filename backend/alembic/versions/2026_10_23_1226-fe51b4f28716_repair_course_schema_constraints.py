"""Repair course schema constraints.

Revision ID: fe51b4f28716
Revises: a7f4c2d91e60
Create Date: 2026-10-23 12:26:16.673034+08:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe51b4f28716"
down_revision: str | Sequence[str] | None = "a7f4c2d91e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Repair course ownership and reconcile legacy enrollment records."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _tables()

    if "courses" not in tables:
        raise RuntimeError("Expected the courses table.")

    course_columns = {
        column["name"] for column in inspector.get_columns("courses")
    }
    if "created_by" not in course_columns:
        raise RuntimeError("Expected courses.created_by.")

    # Match the ORM relationship:
    # courses.created_by -> users.id ON DELETE CASCADE.
    course_fks = inspector.get_foreign_keys("courses")
    matching_fks = [
        fk
        for fk in course_fks
        if fk.get("constrained_columns") == ["created_by"]
        and fk.get("referred_table") == "users"
        and fk.get("referred_columns") == ["id"]
    ]

    expected_fk_exists = any(
        fk.get("name") == "fk_courses_created_by_users"
        and fk.get("options", {}).get("ondelete", "").upper() == "CASCADE"
        for fk in matching_fks
    )

    if not expected_fk_exists:
        for fk in matching_fks:
            if not fk.get("name"):
                raise RuntimeError(
                    "Cannot safely replace an unnamed course owner foreign key."
                )

            op.drop_constraint(
                fk["name"],
                "courses",
                type_="foreignkey",
            )

        op.create_foreign_key(
            "fk_courses_created_by_users",
            "courses",
            "users",
            ["created_by"],
            ["id"],
            ondelete="CASCADE",
        )

    # Reconcile the legacy enrollment table before removing it.
    tables = _tables()
    if "course_enrollments" in tables:
        if "course_memberships" not in tables:
            raise RuntimeError(
                "course_enrollments exists but course_memberships does not; "
                "manual reconciliation is required."
            )

        inspector = sa.inspect(bind)
        legacy_columns = {
            column["name"]
            for column in inspector.get_columns("course_enrollments")
        }
        membership_columns = {
            column["name"]
            for column in inspector.get_columns("course_memberships")
        }

        required_legacy_columns = {"course_id", "user_id", "joined_at"}
        required_membership_columns = {
            "course_id",
            "user_id",
            "role",
            "joined_at",
        }

        if not required_legacy_columns.issubset(legacy_columns):
            raise RuntimeError(
                "Unexpected course_enrollments schema; "
                "manual reconciliation is required."
            )

        if not required_membership_columns.issubset(membership_columns):
            raise RuntimeError(
                "Unexpected course_memberships schema; "
                "manual reconciliation is required."
            )

        # Preserve existing memberships and their roles.
        # Copy legacy rows that do not already have a matching membership.
        bind.execute(
            sa.text(
                """
                INSERT INTO course_memberships
                    (course_id, user_id, role, joined_at)
                SELECT e.course_id, e.user_id, 'STUDENT', e.joined_at
                FROM course_enrollments AS e
                ON CONFLICT (course_id, user_id) DO NOTHING
                """
            )
        )

        # Do not remove the legacy table unless every legacy enrollment
        # has a corresponding course/user pair in the new table.
        missing_count = bind.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM course_enrollments AS e
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM course_memberships AS m
                    WHERE m.course_id = e.course_id
                      AND m.user_id = e.user_id
                )
                """
            )
        ).scalar_one()

        if missing_count:
            raise RuntimeError(
                "Enrollment reconciliation incomplete: "
                f"{missing_count} legacy enrollment(s) have no matching "
                "course_memberships record. The migration must not remove "
                "course_enrollments."
            )
        # Stop if an existing membership has a different join timestamp.
        mismatch_count = bind.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM course_enrollments AS e
                JOIN course_memberships AS m
                  ON m.course_id = e.course_id
                 AND m.user_id = e.user_id
                WHERE m.joined_at IS DISTINCT FROM e.joined_at
                """
            )
        ).scalar_one()

        if mismatch_count:
            raise RuntimeError(
                "Enrollment reconciliation found "
                f"{mismatch_count} conflicting joined_at value(s). "
                "Keep course_enrollments and reconcile these records manually."
            )

        # Remove the legacy table only after reconciliation succeeds.
        op.drop_table("course_enrollments")


def downgrade() -> None:
    """Require manual review before reversing enrollment reconciliation."""
    raise RuntimeError(
        "This migration removes course_enrollments after copying its records "
        "to course_memberships. Review the data and schema before manually "
        "reversing this migration."
    )