"""CRUD helpers for courses, instructors, memberships and TA permissions."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import SessionStatus
from app.models.course import (
    Course,
    CourseInstructor,
    CourseMembership,
    CourseTaPermission,
)
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User

MEMBERSHIP_STUDENT = "STUDENT"
MEMBERSHIP_TA = "TA"

# (course, student_count, topic_count) — topic_count is total topics in the course
InstructorCourseRow = tuple[Course, int, int]
# (course, teacher_name, in_progress_session_count)
StudentCourseRow = tuple[Course, str, int]


def _active_student_filters():
    return (
        CourseMembership.role == MEMBERSHIP_STUDENT,
        CourseMembership.left_at.is_(None),
    )


async def create_course_with_instructor(
    db: AsyncSession,
    *,
    name: str,
    description: str | None,
    created_by: UUID,
    invitation_code: str,
) -> Course:
    course = Course(
        name=name,
        description=description,
        created_by=created_by,
        invitation_code=invitation_code,
    )
    db.add(course)
    await db.flush()
    db.add(CourseInstructor(course_id=course.id, teacher_id=created_by))
    await db.flush()
    return course


async def get_course_by_id(db: AsyncSession, course_id: UUID) -> Course | None:
    return await db.get(Course, course_id)


async def get_course_by_invitation_code(db: AsyncSession, code: str) -> Course | None:
    statement = select(Course).where(Course.invitation_code == code)
    return await db.scalar(statement)


async def is_course_instructor(
    db: AsyncSession, *, course_id: UUID, teacher_id: UUID
) -> bool:
    statement = select(CourseInstructor.course_id).where(
        CourseInstructor.course_id == course_id,
        CourseInstructor.teacher_id == teacher_id,
    )
    return await db.scalar(statement) is not None


async def get_course_role(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> str | None:
    """Return ``"TEACHER"`` / ``"TA"`` / ``"STUDENT"`` for an active member."""
    if await is_course_instructor(db, course_id=course_id, teacher_id=user_id):
        return "TEACHER"
    statement = select(CourseMembership.role).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
        CourseMembership.left_at.is_(None),
    )
    return await db.scalar(statement)


async def list_courses_for_instructor(
    db: AsyncSession, teacher_id: UUID
) -> list[InstructorCourseRow]:
    """List instructed courses with counts in one query (scalar subqueries).

    ``topic_count`` is the total number of topics in the course (not gated on
    session status).
    """
    student_count = (
        select(func.count())
        .select_from(CourseMembership)
        .where(
            CourseMembership.course_id == Course.id,
            *_active_student_filters(),
        )
        .correlate(Course)
        .scalar_subquery()
    )
    topic_count = (
        select(func.count())
        .select_from(Topic)
        .where(Topic.course_id == Course.id)
        .correlate(Course)
        .scalar_subquery()
    )
    statement = (
        select(Course, student_count, topic_count)
        .join(
            CourseInstructor,
            CourseInstructor.course_id == Course.id,
        )
        .where(CourseInstructor.teacher_id == teacher_id)
        .order_by(Course.name.asc())
    )
    result = await db.execute(statement)
    return [
        (course, int(students or 0), int(topics or 0))
        for course, students, topics in result.all()
    ]


async def delete_course(db: AsyncSession, course: Course) -> None:
    await db.delete(course)
    await db.flush()


async def get_student_membership(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> CourseMembership | None:
    """Return the active (not soft-left) STUDENT membership, if any."""
    statement = select(CourseMembership).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
        *_active_student_filters(),
    )
    return await db.scalar(statement)


async def get_student_membership_row(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> CourseMembership | None:
    """Return the STUDENT membership row even if soft-left."""
    statement = select(CourseMembership).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
        CourseMembership.role == MEMBERSHIP_STUDENT,
    )
    return await db.scalar(statement)


async def add_student_membership(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> CourseMembership:
    """Insert a STUDENT membership, or clear ``left_at`` (teacher re-enroll)."""
    existing = await get_student_membership_row(
        db, course_id=course_id, user_id=user_id
    )
    now = datetime.now(UTC)
    if existing is None:
        membership = CourseMembership(
            course_id=course_id,
            user_id=user_id,
            role=MEMBERSHIP_STUDENT,
            left_at=None,
        )
        db.add(membership)
        await db.flush()
        return membership

    if existing.left_at is None:
        return existing

    existing.left_at = None
    existing.joined_at = now
    await db.flush()
    return existing


async def list_student_courses(
    db: AsyncSession, user_id: UUID
) -> list[StudentCourseRow]:
    """List joined courses with teacher name and in-progress session count."""
    creator = aliased(User)
    in_progress_session_count = (
        select(func.count())
        .select_from(Session)
        .join(Topic, Topic.id == Session.topic_id)
        .where(
            Topic.course_id == Course.id,
            Session.user_id == user_id,
            Session.status == SessionStatus.IN_PROGRESS.value,
        )
        .correlate(Course)
        .scalar_subquery()
    )
    statement = (
        select(Course, creator.name, in_progress_session_count)
        .join(
            CourseMembership,
            CourseMembership.course_id == Course.id,
        )
        .join(creator, creator.id == Course.created_by)
        .where(
            CourseMembership.user_id == user_id,
            *_active_student_filters(),
        )
        .order_by(Course.name.asc())
    )
    result = await db.execute(statement)
    return [
        (course, teacher_name or "", int(sessions or 0))
        for course, teacher_name, sessions in result.all()
    ]


async def list_course_students(
    db: AsyncSession, course_id: UUID
) -> list[tuple[User, CourseMembership]]:
    statement = (
        select(User, CourseMembership)
        .join(
            CourseMembership,
            CourseMembership.user_id == User.id,
        )
        .where(
            CourseMembership.course_id == course_id,
            *_active_student_filters(),
        )
        .order_by(User.account_id.asc())
    )
    result = await db.execute(statement)
    return list(result.all())


async def soft_delete_student_membership_by_ids(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> bool:
    statement = (
        update(CourseMembership)
        .where(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user_id,
            *_active_student_filters(),
        )
        .values(left_at=datetime.now(UTC))
    )
    result = await db.execute(statement)
    return (result.rowcount or 0) > 0


async def get_active_membership(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> CourseMembership | None:
    """Return the active (not soft-left) STUDENT or TA membership, if any."""
    statement = select(CourseMembership).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
        CourseMembership.left_at.is_(None),
    )
    return await db.scalar(statement)


async def get_ta_permissions(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> list[str]:
    """Return the permissions granted to a TA (unordered; empty if none)."""
    statement = select(CourseTaPermission.permission).where(
        CourseTaPermission.course_id == course_id,
        CourseTaPermission.user_id == user_id,
    )
    return list((await db.scalars(statement)).all())


async def _insert_ta_permissions(
    db: AsyncSession,
    *,
    course_id: UUID,
    user_id: UUID,
    permissions: Iterable[str],
) -> None:
    db.add_all(
        CourseTaPermission(course_id=course_id, user_id=user_id, permission=p)
        for p in permissions
    )
    await db.flush()


async def _delete_ta_permissions(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> None:
    await db.execute(
        delete(CourseTaPermission).where(
            CourseTaPermission.course_id == course_id,
            CourseTaPermission.user_id == user_id,
        )
    )


async def promote_to_ta(
    db: AsyncSession, membership: CourseMembership, permissions: Iterable[str]
) -> None:
    """Turn a student membership into a TA one (same row keeps its history)."""
    membership.role = MEMBERSHIP_TA
    await db.flush()
    await _insert_ta_permissions(
        db,
        course_id=membership.course_id,
        user_id=membership.user_id,
        permissions=permissions,
    )


async def set_ta_permissions(
    db: AsyncSession, *, course_id: UUID, user_id: UUID, permissions: Iterable[str]
) -> None:
    """Replace a TA's permissions with ``permissions``."""
    await _delete_ta_permissions(db, course_id=course_id, user_id=user_id)
    await _insert_ta_permissions(
        db, course_id=course_id, user_id=user_id, permissions=permissions
    )


async def demote_to_student(db: AsyncSession, membership: CourseMembership) -> None:
    """Drop a TA's permissions and turn the membership back into a student."""
    await _delete_ta_permissions(
        db, course_id=membership.course_id, user_id=membership.user_id
    )
    membership.role = MEMBERSHIP_STUDENT
    await db.flush()
