"""Core course graph: course, topic, student membership."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseMembership
from app.models.topic import Topic
from scripts.seed.catalog import (
    ACCOUNT_STUDENT,
    ACCOUNT_TEACHER,
    COURSE_ID,
    COURSE_NAME,
    INVITATION_CODE,
    TOPIC_ID,
    TOPIC_TITLE,
)
from scripts.seed.packs.auth import get_user_id_by_account


async def seed_course_graph(db: AsyncSession) -> None:
    teacher_id = await get_user_id_by_account(db, ACCOUNT_TEACHER.account_id)
    student_id = await get_user_id_by_account(db, ACCOUNT_STUDENT.account_id)
    if teacher_id is None or student_id is None:
        msg = "auth pack must run before course_graph (missing teacher or student)"
        raise RuntimeError(msg)

    course = await db.get(Course, COURSE_ID)
    if course is None:
        by_code = await db.execute(
            select(Course).where(Course.invitation_code == INVITATION_CODE)
        )
        course = by_code.scalar_one_or_none()
    if course is None:
        course = Course(
            id=COURSE_ID,
            name=COURSE_NAME,
            created_by=teacher_id,
            invitation_code=INVITATION_CODE,
        )
        db.add(course)
        await db.flush()

    topic = await db.get(Topic, TOPIC_ID)
    if topic is None:
        topic = Topic(
            id=TOPIC_ID,
            course_id=course.id,
            created_by=teacher_id,
            title=TOPIC_TITLE,
        )
        db.add(topic)

    membership = await db.get(
        CourseMembership,
        {"course_id": course.id, "user_id": student_id},
    )
    if membership is None:
        db.add(
            CourseMembership(
                course_id=course.id,
                user_id=student_id,
                role="STUDENT",
            )
        )

    await db.flush()
