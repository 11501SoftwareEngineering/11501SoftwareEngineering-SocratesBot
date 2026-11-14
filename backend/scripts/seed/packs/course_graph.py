"""Core course graph: course, topic, student and TA memberships."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import (
    Course,
    CourseInstructor,
    CourseMembership,
    CourseTaPermission,
)
from app.models.topic import Topic
from scripts.seed.catalog import (
    ACCOUNT_STUDENT,
    ACCOUNT_TA,
    ACCOUNT_TEACHER,
    COURSE_ID,
    COURSE_NAME,
    INVITATION_CODE,
    TA_PERMISSIONS,
    TOPIC_ID,
    TOPIC_TITLE,
)
from scripts.seed.errors import SeedError
from scripts.seed.packs.auth import get_user_id_by_account


async def seed_course_graph(db: AsyncSession) -> None:
    teacher_id = await get_user_id_by_account(db, ACCOUNT_TEACHER.account_id)
    student_id = await get_user_id_by_account(db, ACCOUNT_STUDENT.account_id)
    ta_id = await get_user_id_by_account(db, ACCOUNT_TA.account_id)
    if teacher_id is None or student_id is None or ta_id is None:
        msg = "auth pack must run before course_graph (missing teacher, student or TA)"
        raise SeedError(msg)

    course = await db.get(Course, COURSE_ID)
    if course is None:
        by_code = await db.execute(
            select(Course).where(Course.invitation_code == INVITATION_CODE)
        )
        course = by_code.scalar_one_or_none()
        if course is not None and course.id != COURSE_ID:
            msg = (
                f"invitation_code {INVITATION_CODE!r} belongs to course "
                f"{course.id}, expected {COURSE_ID}; "
                "run `make -C backend db-reset` or remove the conflicting row"
            )
            raise SeedError(msg)
    if course is None:
        course = Course(
            id=COURSE_ID,
            name=COURSE_NAME,
            created_by=teacher_id,
            invitation_code=INVITATION_CODE,
        )
        db.add(course)
        await db.flush()

    instructor_key = {"course_id": course.id, "teacher_id": teacher_id}
    if await db.get(CourseInstructor, instructor_key) is None:
        db.add(CourseInstructor(**instructor_key))

    topic = await db.get(Topic, TOPIC_ID)
    if topic is None:
        topic = Topic(
            id=TOPIC_ID,
            course_id=course.id,
            created_by=teacher_id,
            title=TOPIC_TITLE,
        )
        db.add(topic)

    await _ensure_membership(
        db, course_id=course.id, user_id=student_id, role="STUDENT"
    )
    await _ensure_membership(db, course_id=course.id, user_id=ta_id, role="TA")
    await db.flush()
    for permission in TA_PERMISSIONS:
        key = {"course_id": course.id, "user_id": ta_id, "permission": permission}
        if await db.get(CourseTaPermission, key) is None:
            db.add(CourseTaPermission(**key))

    await db.flush()


async def _ensure_membership(
    db: AsyncSession, *, course_id: UUID, user_id: UUID, role: str
) -> None:
    membership = await db.get(
        CourseMembership,
        {"course_id": course_id, "user_id": user_id},
    )
    if membership is None:
        db.add(CourseMembership(course_id=course_id, user_id=user_id, role=role))
