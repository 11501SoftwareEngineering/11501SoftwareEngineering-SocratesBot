"""Integration: who may work on a topic's setup follows the real course roles."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.enums import TaPermission, UserRole
from app.core.migration import run_migrations
from app.crud import course as course_crud
from app.crud import user as user_crud
from app.models.topic import Topic
from app.models.user import User
from app.schemas.course import TaAssignRequest, TaPermissionsUpdateRequest
from app.services import courses as courses_service
from app.services import topics as topics_service


async def _user(db: AsyncSession, account_id: str, role: UserRole) -> User:
    return await user_crud.create_user(
        db,
        account_id=account_id,
        name=account_id,
        password="password1",
        role=role,
    )


@pytest.mark.integration
def test_setup_is_open_to_the_teacher_and_a_ta_with_edit_topics_only() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        suffix = uuid.uuid4().hex[:10]
        async with AsyncSessionLocal() as db:
            teacher = await _user(db, f"setup-t-{suffix}", UserRole.TEACHER)
            ta = await _user(db, f"setup-ta-{suffix}", UserRole.USER)
            student = await _user(db, f"setup-s-{suffix}", UserRole.USER)
            outsider = await _user(db, f"setup-o-{suffix}", UserRole.USER)
            course = await course_crud.create_course_with_instructor(
                db,
                name="Setup access",
                description=None,
                created_by=teacher.id,
                invitation_code=f"S{suffix[:7]}".upper(),
            )
            course_id = uuid.UUID(str(course.id))
            await course_crud.add_student_membership(
                db, course_id=course_id, user_id=student.id
            )
            topic = Topic(course_id=course_id, created_by=teacher.id, title="T")
            db.add(topic)
            await db.commit()
            topic_id = uuid.UUID(str(topic.id))

            await courses_service.assign_course_ta(
                db,
                teacher,
                course_id,
                TaAssignRequest(
                    account_id=ta.account_id,
                    permissions=[TaPermission.EDIT_TOPICS],
                ),
            )

            # The teacher and a TA holding edit_topics may work on the setup.
            for allowed in (teacher, ta):
                found = await topics_service.get_instructed_topic(
                    db, allowed, topic_id, allow_ta=True
                )
                assert found.id == topic_id

            # A student and an outsider may not.
            for denied in (student, outsider):
                with pytest.raises(HTTPException) as exc_info:
                    await topics_service.get_instructed_topic(
                        db, denied, topic_id, allow_ta=True
                    )
                assert exc_info.value.status_code == 403

            # An unknown topic is 404, not 403.
            with pytest.raises(HTTPException) as exc_info:
                await topics_service.get_instructed_topic(
                    db, ta, uuid.uuid4(), allow_ta=True
                )
            assert exc_info.value.status_code == 404

            # Dropping edit_topics takes effect on the very next check.
            await courses_service.update_course_ta_permissions(
                db,
                teacher,
                course_id,
                ta.id,
                TaPermissionsUpdateRequest(permissions=[TaPermission.VIEW_MEMBERS]),
            )
            with pytest.raises(HTTPException) as exc_info:
                await topics_service.get_instructed_topic(
                    db, ta, topic_id, allow_ta=True
                )
            assert exc_info.value.status_code == 403

    asyncio.run(_run())
