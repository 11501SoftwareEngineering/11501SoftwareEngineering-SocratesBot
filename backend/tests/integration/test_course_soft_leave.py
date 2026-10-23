"""Integration: soft-leave blocks invite rejoin; teacher roster add can re-enroll."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.enums import UserRole
from app.core.migration import run_migrations
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import user as user_crud
from app.models.course import CourseMembership
from app.schemas.course import CourseStudentAddRequest, StudentJoinRequest
from app.services import courses as courses_service


@pytest.mark.integration
def test_soft_leave_blocks_invite_rejoin_teacher_can_readd() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()
        suffix = uuid.uuid4().hex[:10]

        async with AsyncSessionLocal() as db:
            teacher = await user_crud.create_user(
                db,
                account_id=f"soft-t-{suffix}",
                name="Soft Teacher",
                password="password1",
                role=UserRole.TEACHER,
            )
            student = await user_crud.create_user(
                db,
                account_id=f"soft-s-{suffix}",
                name="Soft Student",
                password="password1",
                role=UserRole.USER,
            )
            invite = f"S{suffix[:7]}".upper()
            course = await course_crud.create_course_with_instructor(
                db,
                name="Soft Course",
                description=None,
                created_by=teacher.id,
                invitation_code=invite,
            )
            await course_crud.add_student_membership(
                db, course_id=course.id, user_id=student.id
            )
            await db.commit()

            student_row = await user_crud.get_user_by_id(db, student.id)
            teacher_row = await user_crud.get_user_by_id(db, teacher.id)
            assert student_row is not None and teacher_row is not None

            await courses_service.leave_course(db, student_row, course.id)
            membership = await db.scalar(
                select(CourseMembership).where(
                    CourseMembership.course_id == course.id,
                    CourseMembership.user_id == student.id,
                )
            )
            assert membership is not None
            assert membership.left_at is not None
            assert (
                await session_crud.is_course_member(
                    db, user_id=student.id, course_id=course.id
                )
                is False
            )

            with pytest.raises(HTTPException) as exc_info:
                await courses_service.join_course(
                    db,
                    student_row,
                    StudentJoinRequest(invite_code=invite),
                )
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Cannot rejoin after leaving this course"

            await courses_service.add_course_student(
                db,
                teacher_row,
                course.id,
                CourseStudentAddRequest(account_id=student.account_id),
            )
            active = await course_crud.get_student_membership(
                db, course_id=course.id, user_id=student.id
            )
            assert active is not None
            assert active.left_at is None
            assert active.joined_at.replace(tzinfo=UTC) <= datetime.now(UTC)

    asyncio.run(_run())
