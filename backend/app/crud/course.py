"""CRUD helpers for courses, instructors, memberships and TA permissions."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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

# (course, teacher_name, topic_count, student_count)
# topic_count is the total topics in the course; student_count is active students.
MyCourseRow = tuple[Course, str, int, int]


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


def _course_count_subqueries():
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
    return student_count, topic_count


async def _list_course_rows(db: AsyncSession, *membership_filters) -> list[MyCourseRow]:
    creator = aliased(User)
    student_count, topic_count = _course_count_subqueries()
    statement = (
        select(Course, creator.name, topic_count, student_count)
        .join(creator, creator.id == Course.created_by)
        .where(*membership_filters)
        .order_by(Course.name.asc(), Course.id.asc())
    )
    result = await db.execute(statement)
    return [
        (course, teacher_name or "", int(topics or 0), int(students or 0))
        for course, teacher_name, topics, students in result.all()
    ]


async def list_instructed_courses(
    db: AsyncSession, teacher_id: UUID
) -> list[MyCourseRow]:
    """Courses ``teacher_id`` instructs, with teacher name and counts."""
    instructed = select(CourseInstructor.course_id).where(
        CourseInstructor.teacher_id == teacher_id
    )
    return await _list_course_rows(db, Course.id.in_(instructed))


async def list_member_courses(
    db: AsyncSession, user_id: UUID
) -> list[tuple[MyCourseRow, str]]:
    """Courses where ``user_id`` is an active STUDENT/TA, with the DB role."""
    membership_rows = await db.execute(
        select(CourseMembership.course_id, CourseMembership.role).where(
            CourseMembership.user_id == user_id,
            CourseMembership.left_at.is_(None),
        )
    )
    roles = dict(membership_rows.tuples().all())
    if not roles:
        return []
    rows = await _list_course_rows(db, Course.id.in_(list(roles)))
    return [(row, roles[row[0].id]) for row in rows]


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
    db: AsyncSession,
    *,
    course_id: UUID,
    user_id: UUID,
    for_update: bool = False,
) -> CourseMembership | None:
    """Return the active (not soft-left) STUDENT or TA membership, if any.

    With ``for_update`` the row stays locked until the transaction ends, so
    a concurrent leave, removal or role change waits; a row that was soft-left
    while waiting is not returned, and ``role`` is the committed value.
    """
    statement = select(CourseMembership).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
        CourseMembership.left_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )
    return await db.scalar(statement)


async def get_membership(
    db: AsyncSession,
    *,
    course_id: UUID,
    user_id: UUID,
    for_update: bool = False,
) -> CourseMembership | None:
    """Return the membership row in any state (active or soft-left), if any.

    With ``for_update`` the row stays locked until the transaction ends and
    ``role`` / ``left_at`` are the committed values.
    """
    statement = select(CourseMembership).where(
        CourseMembership.course_id == course_id,
        CourseMembership.user_id == user_id,
    )
    if for_update:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )
    return await db.scalar(statement)


async def get_ta_permissions(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> list[str]:
    """Return the permissions granted to a TA (unordered; empty if none)."""
    statement = (
        select(CourseTaPermission.permission)
        .join(
            CourseMembership,
            CourseMembership.id == CourseTaPermission.course_membership_id,
        )
        .where(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user_id,
        )
    )
    return list((await db.scalars(statement)).all())


def _add_ta_permission(
    db: AsyncSession, *, membership_id: UUID, permission: str
) -> None:
    """Stage one TA permission row; the caller flushes."""
    db.add(
        CourseTaPermission(course_membership_id=membership_id, permission=permission)
    )


async def _delete_ta_permissions(db: AsyncSession, *, membership_id: UUID) -> None:
    await db.execute(
        delete(CourseTaPermission).where(
            CourseTaPermission.course_membership_id == membership_id
        )
    )


async def add_ta_membership(
    db: AsyncSession,
    *,
    course_id: UUID,
    user_id: UUID,
    permissions: Iterable[str],
) -> CourseMembership:
    """Add someone who has never been in the course as a TA."""
    membership = CourseMembership(
        course_id=course_id,
        user_id=user_id,
        role=MEMBERSHIP_TA,
        left_at=None,
    )
    db.add(membership)
    await db.flush()
    for permission in permissions:
        _add_ta_permission(db, membership_id=membership.id, permission=permission)
    await db.flush()
    return membership


async def promote_to_ta(
    db: AsyncSession, membership: CourseMembership, permissions: Iterable[str]
) -> None:
    """Turn an existing membership into a TA one (same row keeps its history).

    A soft-left row (left or removed earlier) rejoins the course as of now.
    """
    membership.role = MEMBERSHIP_TA
    if membership.left_at is not None:
        membership.left_at = None
        membership.joined_at = datetime.now(UTC)
    for permission in permissions:
        _add_ta_permission(db, membership_id=membership.id, permission=permission)
    await db.flush()


async def set_ta_permissions(
    db: AsyncSession, membership: CourseMembership, permissions: Iterable[str]
) -> None:
    """Replace a TA's permissions with ``permissions``."""
    await _delete_ta_permissions(db, membership_id=membership.id)
    for permission in permissions:
        _add_ta_permission(db, membership_id=membership.id, permission=permission)
    await db.flush()


async def remove_ta_from_course(db: AsyncSession, membership: CourseMembership) -> None:
    """Drop a TA's permissions and sessions and remove them from the course.

    Their sessions on this course's topics are deleted. The row becomes a
    soft-left STUDENT membership, the same state as a removed student: the
    teacher can add them back as a student or assign them as a TA again.
    """
    await _delete_ta_permissions(db, membership_id=membership.id)
    course_topics = select(Topic.id).where(Topic.course_id == membership.course_id)
    await db.execute(
        delete(Session).where(
            Session.user_id == membership.user_id,
            Session.topic_id.in_(course_topics),
        )
    )
    membership.role = MEMBERSHIP_STUDENT
    membership.left_at = datetime.now(UTC)
    await db.flush()
