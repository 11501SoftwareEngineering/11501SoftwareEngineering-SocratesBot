"""Integration: course hard-delete cascades memberships, topics, sessions."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, engine
from app.core.enums import SessionStatus, UserRole
from app.core.migration import run_migrations
from app.crud import course as course_crud
from app.crud import user as user_crud
from app.models.course import Course, CourseInstructor, CourseMembership
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User
from app.services import courses as courses_service


@pytest.mark.integration
def test_creator_delete_cascades_memberships_topics_sessions_instructors() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()
        suffix = uuid.uuid4().hex[:10]

        async with AsyncSessionLocal() as db:
            teacher = await user_crud.create_user(
                db,
                account_id=f"course-del-t-{suffix}",
                name="Cascade Teacher",
                password="password1",
                role=UserRole.TEACHER,
            )
            teacher_id = uuid.UUID(str(teacher.id))
            student = await user_crud.create_user(
                db,
                account_id=f"course-del-s-{suffix}",
                name="Cascade Student",
                password="password1",
                role=UserRole.USER,
            )
            student_id = uuid.UUID(str(student.id))
            course = await course_crud.create_course_with_instructor(
                db,
                name="Cascade Course",
                description="gone soon",
                created_by=teacher_id,
                invitation_code=f"C{suffix[:7]}".upper(),
            )
            course_id = uuid.UUID(str(course.id))
            await course_crud.add_student_membership(
                db, course_id=course_id, user_id=student_id
            )
            topic = Topic(
                course_id=course_id,
                created_by=teacher_id,
                title="Cascade Topic",
            )
            db.add(topic)
            await db.flush()
            topic_id = uuid.UUID(str(topic.id))
            session = Session(
                topic_id=topic_id,
                user_id=student_id,
                status=SessionStatus.IN_PROGRESS.value,
                is_anonymous=False,
            )
            db.add(session)
            await db.flush()
            session_id = uuid.UUID(str(session.id))
            await db.commit()

            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(CourseMembership)
                    .where(CourseMembership.course_id == course_id)
                )
                == 1
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(CourseInstructor)
                    .where(CourseInstructor.course_id == course_id)
                )
                == 1
            )

            teacher_row = await user_crud.get_user_by_id(db, teacher_id)
            assert teacher_row is not None
            await courses_service.delete_teacher_course(db, teacher_row, course_id)

            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Course)
                    .where(Course.id == course_id)
                )
                == 0
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(CourseMembership)
                    .where(CourseMembership.course_id == course_id)
                )
                == 0
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(CourseInstructor)
                    .where(CourseInstructor.course_id == course_id)
                )
                == 0
            )
            assert (
                await db.scalar(
                    select(func.count()).select_from(Topic).where(Topic.id == topic_id)
                )
                == 0
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Session)
                    .where(Session.id == session_id)
                )
                == 0
            )
            # Creator / student accounts remain; only course graph is gone.
            assert (
                await db.scalar(
                    select(func.count()).select_from(User).where(User.id == teacher_id)
                )
                == 1
            )
            assert (
                await db.scalar(
                    select(func.count()).select_from(User).where(User.id == student_id)
                )
                == 1
            )

    asyncio.run(_run())
