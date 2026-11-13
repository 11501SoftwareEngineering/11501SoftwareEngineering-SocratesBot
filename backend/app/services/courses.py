"""Business rules for course management (permissions follow in-course role)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CourseRole
from app.crud import course as course_crud
from app.models.course import Course
from app.models.user import User
from app.schemas.course import (
    CourseCreateRequest,
    CourseCreateResponse,
    CourseDetailResponse,
    CourseJoinRequest,
    CourseJoinResponse,
    CourseListItem,
    CourseMemberListItem,
    CourseUpdateRequest,
    CourseUpdateResponse,
)
from app.services.course_invites import (
    INVITE_ALPHABET,
    INVITE_COLLISION_RETRIES,
    INVITE_LENGTH,
    generate_invite_code,
)

_INVITE_RE = re.compile(rf"^[{INVITE_ALPHABET}]{{{INVITE_LENGTH}}}$")
_INVITE_UNIQUE_CONSTRAINT = "uq_courses_invitation_code"
_MEMBERSHIP_PK = "pk_course_memberships"


def _integrity_constraint_name(exc: IntegrityError) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    constraint = getattr(orig, "constraint_name", None)
    if constraint is None:
        diag = getattr(orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)
    return constraint


def _is_invite_unique_violation(exc: IntegrityError) -> bool:
    """True only for courses.invitation_code UNIQUE conflicts."""
    constraint = _integrity_constraint_name(exc)
    if constraint == _INVITE_UNIQUE_CONSTRAINT:
        return True
    text = str(getattr(exc, "orig", None) or exc).lower()
    return _INVITE_UNIQUE_CONSTRAINT in text


def _is_membership_duplicate_violation(exc: IntegrityError) -> bool:
    """True only for course_memberships primary-key conflicts."""
    constraint = _integrity_constraint_name(exc)
    if constraint == _MEMBERSHIP_PK:
        return True
    text = str(getattr(exc, "orig", None) or exc).lower()
    return _MEMBERSHIP_PK in text


_ROLE_BY_DB_VALUE = {
    "TEACHER": CourseRole.TEACHER,
    "TA": CourseRole.TA,
    "STUDENT": CourseRole.STUDENT,
}


async def get_my_course_role(
    db: AsyncSession, user: User, course_id: UUID
) -> CourseRole | None:
    """Return the caller's identity in the course, or None if not a member."""
    db_role = await course_crud.get_course_role(
        db, course_id=course_id, user_id=user.id
    )
    return _ROLE_BY_DB_VALUE.get(db_role) if db_role else None


def course_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Course not found",
    )


async def _require_course(db: AsyncSession, course_id: UUID) -> Course:
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        raise course_not_found()
    return course


async def require_course_teacher(
    db: AsyncSession, user: User, course_id: UUID
) -> Course:
    """404 if the course is missing; 403 if ``user`` is not its teacher."""
    course = await _require_course(db, course_id)
    if not await course_crud.is_course_instructor(
        db, course_id=course_id, teacher_id=user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Course teacher required",
        )
    return course


async def create_course(
    db: AsyncSession, teacher: User, payload: CourseCreateRequest
) -> CourseCreateResponse:
    """Create a course; retry insert on invitation_code UNIQUE collisions."""
    teacher_id = teacher.id
    last_invite_collision: IntegrityError | None = None
    for _ in range(INVITE_COLLISION_RETRIES):
        try:
            course = await course_crud.create_course_with_instructor(
                db,
                name=payload.name,
                description=payload.description,
                created_by=teacher_id,
                invitation_code=generate_invite_code(),
            )
            await db.commit()
            return CourseCreateResponse(
                course_id=course.id,
                name=course.name,
                description=course.description,
                invite_code=course.invitation_code,
                my_role=CourseRole.TEACHER,
                message="Course created",
            )
        except IntegrityError as exc:
            await db.rollback()
            if not _is_invite_unique_violation(exc):
                raise
            last_invite_collision = exc
            continue
        except Exception:
            await db.rollback()
            raise
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate invitation code; retry later",
    ) from last_invite_collision


async def list_my_courses(db: AsyncSession, user: User) -> list[CourseListItem]:
    """Courses the caller teaches, assists in, or studies in (one merged list)."""
    items: list[CourseListItem] = []
    for (
        course,
        teacher_name,
        topic_count,
        student_count,
    ) in await course_crud.list_instructed_courses(db, user.id):
        items.append(
            CourseListItem(
                course_id=course.id,
                name=course.name,
                description=course.description,
                teacher_name=teacher_name,
                topic_count=topic_count,
                my_role=CourseRole.TEACHER,
                my_permissions=[],
                invite_code=course.invitation_code,
                student_count=student_count,
            )
        )
    seen = {item.course_id for item in items}
    for (
        course,
        teacher_name,
        topic_count,
        _,
    ), db_role in await course_crud.list_member_courses(db, user.id):
        if course.id in seen:
            continue
        # ``student_count`` is left unset (omitted) for students and, until TA
        # permissions exist, for TAs.
        items.append(
            CourseListItem(
                course_id=course.id,
                name=course.name,
                description=course.description,
                teacher_name=teacher_name,
                topic_count=topic_count,
                my_role=_ROLE_BY_DB_VALUE[db_role],
                my_permissions=[],
                invite_code=course.invitation_code,
            )
        )
    items.sort(key=lambda item: (item.name, str(item.course_id)))
    return items


async def get_course(
    db: AsyncSession, user: User, course_id: UUID
) -> CourseDetailResponse:
    """Course info for a member; non-members get 404 like a missing course."""
    course = await course_crud.get_course_by_id(db, course_id)
    role = await get_my_course_role(db, user, course_id) if course else None
    if course is None or role is None:
        raise course_not_found()
    return CourseDetailResponse(
        course_id=course.id,
        name=course.name,
        description=course.description,
        teacher_name=await course_crud.get_user_name(db, course.created_by),
        my_role=role,
        my_permissions=[],
        invite_code=course.invitation_code,
    )


async def update_course(
    db: AsyncSession, teacher: User, course_id: UUID, payload: CourseUpdateRequest
) -> CourseUpdateResponse:
    course = await require_course_teacher(db, teacher, course_id)
    try:
        course = await course_crud.update_course(
            db, course, name=payload.name, description=payload.description
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return CourseUpdateResponse(
        course_id=course.id,
        name=course.name,
        description=course.description,
        invite_code=course.invitation_code,
        message="Course updated",
    )


async def delete_course(db: AsyncSession, teacher: User, course_id: UUID) -> None:
    """Hard-delete a course; idempotent when already gone (no 404)."""
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        return
    if course.created_by != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the course creator can delete this course",
        )
    try:
        await course_crud.delete_course(db, course)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def _commit_student_enrollment(
    db: AsyncSession,
    *,
    course_id: UUID,
    user_id: UUID,
    duplicate_detail: str,
    missing_course_detail: str,
) -> None:
    try:
        await course_crud.add_student_membership(
            db, course_id=course_id, user_id=user_id
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_membership_duplicate_violation(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=duplicate_detail,
            ) from None
        course = await course_crud.get_course_by_id(db, course_id)
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=missing_course_detail,
            ) from None
        raise
    except Exception:
        await db.rollback()
        raise


async def join_course(
    db: AsyncSession, user: User, payload: CourseJoinRequest
) -> CourseJoinResponse:
    code = payload.invite_code.strip().upper()
    if not _INVITE_RE.fullmatch(code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation code format",
        )
    course = await course_crud.get_course_by_invitation_code(db, code)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found for this invitation code",
        )
    role = await get_my_course_role(db, user, course.id)
    if role in (CourseRole.TEACHER, CourseRole.TA):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already a teacher or TA of this course",
        )
    if role is CourseRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already a member of this course",
        )
    prior = await course_crud.get_student_membership_row(
        db, course_id=course.id, user_id=user.id
    )
    if prior is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rejoin after leaving this course",
        )
    await _commit_student_enrollment(
        db,
        course_id=course.id,
        user_id=user.id,
        duplicate_detail="Already a member of this course",
        missing_course_detail="Course not found for this invitation code",
    )

    return CourseJoinResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
        my_role=CourseRole.STUDENT,
        message="Joined course",
    )


async def leave_course(db: AsyncSession, user: User, course_id: UUID) -> None:
    """Student soft-leave; idempotent when already left (no 404).

    Raises:
        HTTPException: 403 if ``user`` teaches or assists in the course.
    """
    role = await get_my_course_role(db, user, course_id)
    if role in (CourseRole.TEACHER, CourseRole.TA):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teachers and TAs cannot leave a course this way",
        )
    try:
        removed = await course_crud.soft_delete_student_membership_by_ids(
            db, course_id=course_id, user_id=user.id
        )
        if removed:
            await db.commit()
    except Exception:
        await db.rollback()
        raise


async def list_course_members(
    db: AsyncSession, user: User, course_id: UUID, role: CourseRole | None
) -> list[CourseMemberListItem]:
    """List students and/or TAs. Teacher only for now (TA ``view_members`` later)."""
    await require_course_teacher(db, user, course_id)
    if role is CourseRole.STUDENT:
        db_roles = (course_crud.MEMBERSHIP_STUDENT,)
    elif role is CourseRole.TA:
        db_roles = (course_crud.MEMBERSHIP_TA,)
    else:
        db_roles = (course_crud.MEMBERSHIP_STUDENT, course_crud.MEMBERSHIP_TA)
    rows = await course_crud.list_course_members(db, course_id, roles=db_roles)
    return [
        CourseMemberListItem(
            user_id=member.id,
            account_id=member.account_id,
            name=member.name,
            role=_ROLE_BY_DB_VALUE[membership.role],
            joined_at=membership.joined_at,
            permissions=[],
        )
        for member, membership in rows
    ]


async def remove_course_student(
    db: AsyncSession, teacher: User, course_id: UUID, user_id: UUID
) -> None:
    """Soft-remove a student; idempotent when already left."""
    await require_course_teacher(db, teacher, course_id)
    try:
        removed = await course_crud.soft_delete_student_membership_by_ids(
            db, course_id=course_id, user_id=user_id
        )
        if removed:
            await db.commit()
    except Exception:
        await db.rollback()
        raise
