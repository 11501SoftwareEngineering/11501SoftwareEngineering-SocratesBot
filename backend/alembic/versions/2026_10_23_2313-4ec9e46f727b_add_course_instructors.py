"""add course_instructors and membership left_at

Revision ID: 4ec9e46f727b
Revises: 22032e425647
Create Date: 2026-10-23 23:13:41.847647+08:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4ec9e46f727b"
down_revision: str | Sequence[str] | None = "22032e425647"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "course_instructors",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_course_instructors_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["users.id"],
            name=op.f("fk_course_instructors_teacher_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "course_id", "teacher_id", name=op.f("pk_course_instructors")
        ),
    )
    op.create_index(
        op.f("ix_course_instructors_teacher_id"),
        "course_instructors",
        ["teacher_id"],
        unique=False,
    )
    # Seed creator as instructor for any courses that predate this table.
    op.execute(
        """
        INSERT INTO course_instructors (course_id, teacher_id)
        SELECT id, created_by FROM courses
        ON CONFLICT DO NOTHING
        """
    )
    op.add_column(
        "course_memberships",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_course_memberships_user_active_student",
        "course_memberships",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("role = 'STUDENT' AND left_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_course_memberships_user_active_student",
        table_name="course_memberships",
    )
    op.drop_column("course_memberships", "left_at", if_exists=True)
    op.drop_index(
        op.f("ix_course_instructors_teacher_id"),
        table_name="course_instructors",
    )
    op.drop_table("course_instructors")
