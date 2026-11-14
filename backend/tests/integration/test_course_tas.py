"""Integration: promote a student to TA, change permissions, revoke, cascade."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.enums import SessionStatus, TaPermission, UserRole
from app.core.migration import run_migrations
from app.crud import course as course_crud
from app.crud import user as user_crud
from app.models.course import CourseMembership, CourseTaPermission
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User
from app.schemas.course import TaAssignRequest, TaPermissionsUpdateRequest
from app.services import courses as courses_service


async def _setup_course(db: AsyncSession, prefix: str) -> tuple[User, User, uuid.UUID]:
    """Create a teacher, a student and a course the student has joined."""
    suffix = uuid.uuid4().hex[:10]
    teacher = await user_crud.create_user(
        db,
        account_id=f"{prefix}-t-{suffix}",
        name="TA Teacher",
        password="password1",
        role=UserRole.TEACHER,
    )
    student = await user_crud.create_user(
        db,
        account_id=f"{prefix}-s-{suffix}",
        name="TA Student",
        password="password1",
        role=UserRole.USER,
    )
    course = await course_crud.create_course_with_instructor(
        db,
        name="TA Course",
        description=None,
        created_by=teacher.id,
        invitation_code=f"T{suffix[:7]}".upper(),
    )
    course_id = uuid.UUID(str(course.id))
    await course_crud.add_student_membership(
        db, course_id=course_id, user_id=student.id
    )
    await db.commit()
    return teacher, student, course_id


async def _permission_rows(
    db: AsyncSession, *, course_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(CourseTaPermission)
        .where(
            CourseTaPermission.course_id == course_id,
            CourseTaPermission.user_id == user_id,
        )
    )


@pytest.mark.integration
def test_student_promoted_to_ta_then_revoked_keeps_sessions() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        async with AsyncSessionLocal() as db:
            teacher, student, course_id = await _setup_course(db, "ta-flow")
            topic = Topic(course_id=course_id, created_by=teacher.id, title="T")
            db.add(topic)
            await db.flush()
            topic_id = uuid.UUID(str(topic.id))
            student_id = uuid.UUID(str(student.id))
            db.add(
                Session(
                    topic_id=topic_id,
                    user_id=student.id,
                    status=SessionStatus.COMPLETED.value,
                )
            )
            await db.commit()

            assigned = await courses_service.assign_course_ta(
                db,
                teacher,
                course_id,
                TaAssignRequest(
                    account_id=student.account_id,
                    permissions=[
                        TaPermission.VIEW_MEMBERS,
                        TaPermission.EDIT_TOPICS,
                    ],
                ),
            )
            assert assigned.permissions == ["edit_topics", "view_members"]
            assert (
                await course_crud.get_course_role(
                    db, course_id=course_id, user_id=student.id
                )
                == "TA"
            )

            # The guard reads permissions on each call: dropping a permission
            # takes effect on the very next check.
            await courses_service.require_course_teacher_or_ta(
                db, student, course_id, TaPermission.VIEW_MEMBERS
            )
            await courses_service.update_course_ta_permissions(
                db,
                teacher,
                course_id,
                student.id,
                TaPermissionsUpdateRequest(permissions=[TaPermission.EDIT_TOPICS]),
            )
            with pytest.raises(HTTPException) as exc_info:
                await courses_service.require_course_teacher_or_ta(
                    db, student, course_id, TaPermission.VIEW_MEMBERS
                )
            assert exc_info.value.status_code == 403
            assert (
                await _permission_rows(db, course_id=course_id, user_id=student.id) == 1
            )

            with pytest.raises(HTTPException) as exc_info:
                await courses_service.assign_course_ta(
                    db,
                    teacher,
                    course_id,
                    TaAssignRequest(account_id=student.account_id),
                )
            assert exc_info.value.status_code == 400

            await courses_service.revoke_course_ta(db, teacher, course_id, student_id)
            membership = await db.get(
                CourseMembership, (course_id, student_id), populate_existing=True
            )
            assert membership is not None
            assert membership.role == "STUDENT"
            assert membership.left_at is None
            assert (
                await _permission_rows(db, course_id=course_id, user_id=student_id) == 0
            )
            sessions = await db.scalar(
                select(func.count())
                .select_from(Session)
                .where(Session.user_id == student_id, Session.topic_id == topic_id)
            )
            assert sessions == 1

            with pytest.raises(HTTPException) as exc_info:
                await courses_service.revoke_course_ta(
                    db, teacher, course_id, student_id
                )
            assert exc_info.value.status_code == 404

    asyncio.run(_run())


@pytest.mark.integration
def test_non_member_cannot_be_assigned_and_course_delete_cascades() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        async with AsyncSessionLocal() as db:
            teacher, student, course_id = await _setup_course(db, "ta-cascade")
            outsider = await user_crud.create_user(
                db,
                account_id=f"ta-out-{uuid.uuid4().hex[:10]}",
                name="Outsider",
                password="password1",
                role=UserRole.USER,
            )
            await db.commit()

            with pytest.raises(HTTPException) as exc_info:
                await courses_service.assign_course_ta(
                    db,
                    teacher,
                    course_id,
                    TaAssignRequest(account_id=outsider.account_id),
                )
            assert exc_info.value.status_code == 400

            await courses_service.assign_course_ta(
                db,
                teacher,
                course_id,
                TaAssignRequest(
                    account_id=student.account_id,
                    permissions=list(TaPermission),
                ),
            )
            assert (
                await _permission_rows(db, course_id=course_id, user_id=student.id) == 4
            )

            await courses_service.delete_course(db, teacher, course_id)
            assert (
                await _permission_rows(db, course_id=course_id, user_id=student.id) == 0
            )

    asyncio.run(_run())
