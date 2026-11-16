"""Integration: promote a student to TA, change permissions, revoke, cascade."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
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
        .join(
            CourseMembership,
            CourseMembership.id == CourseTaPermission.course_membership_id,
        )
        .where(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user_id,
        )
    )


@pytest.mark.integration
def test_student_promoted_to_ta_then_revoked_leaves_course_without_sessions() -> None:
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
            # Someone else's session on the same topic must survive the revoke.
            db.add(Session(topic_id=topic_id, user_id=teacher.id))
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
            membership = await db.scalar(
                select(CourseMembership)
                .where(
                    CourseMembership.course_id == course_id,
                    CourseMembership.user_id == student_id,
                )
                .execution_options(populate_existing=True)
            )
            assert membership is not None
            assert membership.role == "STUDENT"
            assert membership.left_at is not None
            assert (
                await course_crud.get_course_role(
                    db, course_id=course_id, user_id=student_id
                )
                is None
            )
            assert (
                await _permission_rows(db, course_id=course_id, user_id=student_id) == 0
            )
            sessions = await db.scalar(
                select(func.count())
                .select_from(Session)
                .where(Session.user_id == student_id, Session.topic_id == topic_id)
            )
            assert sessions == 0
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Session)
                    .where(Session.topic_id == topic_id)
                )
                == 1
            )

            with pytest.raises(HTTPException) as exc_info:
                await courses_service.revoke_course_ta(
                    db, teacher, course_id, student_id
                )
            assert exc_info.value.status_code == 404

            # Like any removed student, they can be enrolled again.
            rejoined = await course_crud.add_student_membership(
                db, course_id=course_id, user_id=student_id
            )
            await db.commit()
            assert rejoined.id == membership.id
            assert rejoined.left_at is None
            assert (
                await course_crud.get_course_role(
                    db, course_id=course_id, user_id=student_id
                )
                == "STUDENT"
            )

    asyncio.run(_run())


@pytest.mark.integration
def test_revoked_ta_can_be_assigned_again() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        async with AsyncSessionLocal() as db:
            teacher, student, course_id = await _setup_course(db, "ta-again")
            student_id = uuid.UUID(str(student.id))
            request = TaAssignRequest(
                account_id=student.account_id,
                permissions=[TaPermission.VIEW_REPORTS],
            )
            await courses_service.assign_course_ta(db, teacher, course_id, request)
            await courses_service.revoke_course_ta(db, teacher, course_id, student_id)

            await courses_service.assign_course_ta(db, teacher, course_id, request)

            membership = await _membership_row(
                db, course_id=course_id, user_id=student_id
            )
            assert membership is not None
            assert membership.role == "TA"
            assert membership.left_at is None
            assert (
                await _permission_rows(db, course_id=course_id, user_id=student_id) == 1
            )

    asyncio.run(_run())


@pytest.mark.integration
def test_any_account_can_be_assigned_and_course_delete_cascades() -> None:
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

            # The course's own teacher cannot be a TA of it.
            with pytest.raises(HTTPException) as exc_info:
                await courses_service.assign_course_ta(
                    db,
                    teacher,
                    course_id,
                    TaAssignRequest(account_id=teacher.account_id),
                )
            assert exc_info.value.status_code == 400

            # Someone outside the course joins it as a TA.
            await courses_service.assign_course_ta(
                db,
                teacher,
                course_id,
                TaAssignRequest(
                    account_id=outsider.account_id,
                    permissions=[TaPermission.EDIT_TOPICS],
                ),
            )
            assert (
                await course_crud.get_course_role(
                    db, course_id=course_id, user_id=outsider.id
                )
                == "TA"
            )
            assert (
                await _permission_rows(db, course_id=course_id, user_id=outsider.id)
                == 1
            )

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
            assert (
                await _permission_rows(db, course_id=course_id, user_id=outsider.id)
                == 0
            )

    asyncio.run(_run())


async def _wait_until_lock_waiter(timeout: float = 5.0) -> None:
    """Return once some backend in this database waits on a row lock."""
    async with AsyncSessionLocal() as probe:
        for _ in range(int(timeout / 0.05)):
            waiting = await probe.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock'"
                )
            )
            await probe.rollback()
            if waiting:
                return
            await asyncio.sleep(0.05)
    raise AssertionError("no transaction ended up waiting on the row lock")


async def _membership_row(
    db: AsyncSession, *, course_id: uuid.UUID, user_id: uuid.UUID
) -> CourseMembership | None:
    return await db.scalar(
        select(CourseMembership)
        .where(
            CourseMembership.course_id == course_id,
            CourseMembership.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )


@pytest.mark.integration
def test_assign_waits_for_concurrent_removal_then_reactivates_as_ta() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        async with AsyncSessionLocal() as remover, AsyncSessionLocal() as assigner:
            teacher, student, course_id = await _setup_course(remover, "ta-race-a")
            teacher_id = uuid.UUID(str(teacher.id))
            student_id = uuid.UUID(str(student.id))
            account_id = student.account_id

            # The removal holds the row lock until it commits.
            removed = await course_crud.soft_delete_student_membership_by_ids(
                remover, course_id=course_id, user_id=student_id
            )
            assert removed

            assigning_teacher = await assigner.get(User, teacher_id)
            assert assigning_teacher is not None
            assign = asyncio.create_task(
                courses_service.assign_course_ta(
                    assigner,
                    assigning_teacher,
                    course_id,
                    TaAssignRequest(
                        account_id=account_id,
                        permissions=[TaPermission.VIEW_MEMBERS],
                    ),
                )
            )
            await _wait_until_lock_waiter()
            assert not assign.done()
            await remover.commit()

            # The assign sees the committed removal and brings the row back as
            # an active TA, never a TA that has left.
            assigned = await assign
            assert assigned.permissions == ["view_members"]

            membership = await _membership_row(
                remover, course_id=course_id, user_id=student_id
            )
            assert membership is not None
            assert membership.role == "TA"
            assert membership.left_at is None
            assert (
                await _permission_rows(remover, course_id=course_id, user_id=student_id)
                == 1
            )

    asyncio.run(_run())


@pytest.mark.integration
def test_permission_update_waits_for_concurrent_revoke_and_is_404() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        async with AsyncSessionLocal() as revoker, AsyncSessionLocal() as updater:
            teacher, student, course_id = await _setup_course(revoker, "ta-race-u")
            teacher_id = uuid.UUID(str(teacher.id))
            student_id = uuid.UUID(str(student.id))
            await courses_service.assign_course_ta(
                revoker,
                teacher,
                course_id,
                TaAssignRequest(
                    account_id=student.account_id,
                    permissions=[TaPermission.EDIT_TOPICS],
                ),
            )

            # Same steps as revoke_course_ta, with the commit held back.
            membership = await course_crud.get_active_membership(
                revoker, course_id=course_id, user_id=student_id, for_update=True
            )
            assert membership is not None
            await course_crud.remove_ta_from_course(revoker, membership)

            updating_teacher = await updater.get(User, teacher_id)
            assert updating_teacher is not None
            update = asyncio.create_task(
                courses_service.update_course_ta_permissions(
                    updater,
                    updating_teacher,
                    course_id,
                    student_id,
                    TaPermissionsUpdateRequest(
                        permissions=[TaPermission.VIEW_REPORTS],
                    ),
                )
            )
            await _wait_until_lock_waiter()
            assert not update.done()
            await revoker.commit()

            with pytest.raises(HTTPException) as exc_info:
                await update
            assert exc_info.value.status_code == 404

            membership = await _membership_row(
                revoker, course_id=course_id, user_id=student_id
            )
            assert membership is not None
            assert membership.role == "STUDENT"
            assert (
                await _permission_rows(revoker, course_id=course_id, user_id=student_id)
                == 0
            )

    asyncio.run(_run())
