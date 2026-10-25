"""CRUD helpers for courses, instructors, and student memberships."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import SessionStatus
from app.models.course import Course, CourseInstructor, CourseMembership
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User

MEMBERSHIP_STUDENT = "STUDENT"

# (course, student_count, topic_count)
InstructorCourseRow = tuple[Course, int, int]
# (course, teacher_name, active_topic_count)
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


async def list_courses_for_instructor(
    db: AsyncSession, teacher_id: UUID
) -> list[InstructorCourseRow]:
    """List instructed courses with counts in one query (scalar subqueries)."""
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
        select(func.count(func.distinct(Topic.id)))
        .select_from(Topic)
        .join(Session, Session.topic_id == Topic.id)
        .where(
            Topic.course_id == Course.id,
            Session.status == SessionStatus.IN_PROGRESS.value,
        )
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
    """List joined courses with teacher name and session count in one query."""
    creator = aliased(User)
    active_topic_count = (
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
        select(Course, creator.name, active_topic_count)
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
        (course, teacher_name or "", int(active or 0))
        for course, teacher_name, active in result.all()
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
