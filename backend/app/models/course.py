import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    invitation_code: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CourseMembership(Base):
    __tablename__ = "course_memberships"

    __table_args__ = (
        CheckConstraint(
            "role IN ('STUDENT', 'TA')",
            name="role",
        ),
        UniqueConstraint("course_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # Null = active member; set on student leave / teacher remove (soft delete).
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class CourseInstructor(Base):
    __tablename__ = "course_instructors"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )


class CourseTaPermission(Base):
    """One granted permission of a course TA (one row per permission)."""

    __tablename__ = "course_ta_permissions"

    __table_args__ = (
        CheckConstraint(
            "permission IN "
            "('edit_topics', 'view_reports', 'edit_summary', 'view_members')",
            name="permission",
        ),
    )

    course_membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # Named explicitly: the naming-convention name exceeds 63 characters.
        ForeignKey(
            "course_memberships.id",
            name="fk_course_ta_permissions_course_membership_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    permission: Mapped[str] = mapped_column(String(32), primary_key=True)
