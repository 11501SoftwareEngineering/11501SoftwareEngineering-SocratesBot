"""Business rules for course management (permissions follow in-course role)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_super_admin
from app.core.enums import CourseRole, TaPermission, UserRole
from app.crud import course as course_crud
from app.crud import user as user_crud
from app.models.course import Course, CourseMembership
from app.models.user import User
from app.schemas.course import (
    CourseCreateRequest,
    CourseCreateResponse,
    CourseStudentAddRequest,
    CourseStudentListItem,
    MessageResponse,
    StudentCourseListItem,
    StudentJoinRequest,
    StudentJoinResponse,
    TaAssignRequest,
    TaAssignResponse,
    TaPermissionsUpdateRequest,
    TaPermissionsUpdateResponse,
    TeacherCourseListItem,
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
_TA_PERMISSION_PK = "pk_course_ta_permissions"


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


def _is_constraint_violation(exc: IntegrityError, name: str) -> bool:
    constraint = _integrity_constraint_name(exc)
    if constraint == name:
        return True
    text = str(getattr(exc, "orig", None) or exc).lower()
    return name in text


def _is_membership_duplicate_violation(exc: IntegrityError) -> bool:
    """True only for course_memberships primary-key conflicts."""
    return _is_constraint_violation(exc, _MEMBERSHIP_PK)


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


_PERMISSION_ORDER = {permission: index for index, permission in enumerate(TaPermission)}


def sort_permissions(permissions: Iterable[str]) -> list[str]:
    """Deduplicate TA permissions and order them as declared in ``TaPermission``."""
    return sorted(set(permissions), key=lambda p: _PERMISSION_ORDER[TaPermission(p)])


async def require_course_teacher_or_ta(
    db: AsyncSession, user: User, course_id: UUID, permission: TaPermission
) -> tuple[Course, CourseRole]:
    """Allow the course teacher, or a TA holding ``permission``.

    Permissions are read on every call, so a change applies to the next request.

    Raises:
        HTTPException: 404 if the course is missing; 403 otherwise.
    """
    course = await _require_course(db, course_id)
    role = await get_my_course_role(db, user, course_id)
    if role is CourseRole.TEACHER:
        return course, role
    if role is CourseRole.TA and permission in await course_crud.get_ta_permissions(
        db, course_id=course_id, user_id=user.id
    ):
        return course, role
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Course teacher or TA with {permission} permission required",
    )


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


async def list_my_courses(
    db: AsyncSession, user: User
) -> list[TeacherCourseListItem | StudentCourseListItem]:
    """Courses the caller teaches or studies in, merged and sorted by name.

    Each row keeps the shape of the former teacher / student list.
    """
    teacher_rows = await course_crud.list_courses_for_instructor(db, user.id)
    student_rows = await course_crud.list_student_courses(db, user.id)

    items: list[TeacherCourseListItem | StudentCourseListItem] = [
        TeacherCourseListItem(
            course_id=course.id,
            name=course.name,
            description=course.description,
            invite_code=course.invitation_code,
            student_count=student_count,
            topic_count=topic_count,
        )
        for course, student_count, topic_count in teacher_rows
    ]
    seen = {item.course_id for item in items}
    items.extend(
        StudentCourseListItem(
            course_id=course.id,
            name=course.name,
            invite_code=course.invitation_code,
            teacher_name=teacher_name,
            active_topic_count=session_count,
        )
        for course, teacher_name, session_count in student_rows
        if course.id not in seen
    )
    items.sort(key=lambda item: (item.name, str(item.course_id)))
    return items


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
    db: AsyncSession, student: User, payload: StudentJoinRequest
) -> StudentJoinResponse:
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
    prior = await course_crud.get_student_membership_row(
        db, course_id=course.id, user_id=student.id
    )
    if prior is not None:
        if prior.left_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already a member of this course",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rejoin after leaving this course",
        )
    await _commit_student_enrollment(
        db,
        course_id=course.id,
        user_id=student.id,
        duplicate_detail="Already a member of this course",
        missing_course_detail="Course not found for this invitation code",
    )

    return StudentJoinResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
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


async def _require_instructor(
    db: AsyncSession, *, course_id: UUID, teacher: User
) -> None:
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None or not await course_crud.is_course_instructor(
        db, course_id=course_id, teacher_id=teacher.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )


async def list_course_students(
    db: AsyncSession, teacher: User, course_id: UUID
) -> list[CourseStudentListItem]:
    await require_course_teacher(db, teacher, course_id)
    rows = await course_crud.list_course_students(db, course_id)
    return [
        CourseStudentListItem(
            student_id=user.id,
            account_id=user.account_id,
            name=user.name,
            joined_at=membership.joined_at,
        )
        for user, membership in rows
    ]


async def add_course_student(
    db: AsyncSession,
    teacher: User,
    course_id: UUID,
    payload: CourseStudentAddRequest,
) -> MessageResponse:
    await _require_instructor(db, course_id=course_id, teacher=teacher)
    target = await user_crud.get_user_by_account(db, payload.account_id)
    if target is None or target.role != UserRole.USER.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    existing = await course_crud.get_student_membership(
        db, course_id=course_id, user_id=target.id
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is already in this course",
        )
    await _commit_student_enrollment(
        db,
        course_id=course_id,
        user_id=target.id,
        duplicate_detail="Student is already in this course",
        missing_course_detail="Course not found",
    )
    return MessageResponse(message="Student added")


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


_ALREADY_TA_DETAIL = "Already a TA of this course"


def _ta_assign_rejected(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def _require_active_ta(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> CourseMembership:
    membership = await course_crud.get_active_membership(
        db, course_id=course_id, user_id=user_id
    )
    if membership is None or membership.role != course_crud.MEMBERSHIP_TA:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TA not found",
        )
    return membership


async def assign_course_ta(
    db: AsyncSession, teacher: User, course_id: UUID, payload: TaAssignRequest
) -> TaAssignResponse:
    """Promote an active student of the course to TA with ``permissions``.

    Raises:
        HTTPException: 404 course / account missing; 403 not the course
            teacher; 400 not an active student here, already a TA, or an admin.
    """
    await require_course_teacher(db, teacher, course_id)
    target = await user_crud.get_user_by_account(db, payload.account_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    if is_super_admin(target):
        raise _ta_assign_rejected("Admins cannot be TAs")
    membership = await course_crud.get_active_membership(
        db, course_id=course_id, user_id=target.id
    )
    if membership is not None and membership.role == course_crud.MEMBERSHIP_TA:
        raise _ta_assign_rejected(_ALREADY_TA_DETAIL)
    if membership is None:
        raise _ta_assign_rejected("Account must be a student of this course")

    permissions = sort_permissions(payload.permissions)
    try:
        await course_crud.promote_to_ta(db, membership, permissions)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint_violation(exc, _TA_PERMISSION_PK):
            raise _ta_assign_rejected(_ALREADY_TA_DETAIL) from None
        raise
    except Exception:
        await db.rollback()
        raise
    return TaAssignResponse(
        user_id=target.id,
        account_id=target.account_id,
        name=target.name,
        permissions=permissions,
        message="TA assigned",
    )


async def update_course_ta_permissions(
    db: AsyncSession,
    teacher: User,
    course_id: UUID,
    user_id: UUID,
    payload: TaPermissionsUpdateRequest,
) -> TaPermissionsUpdateResponse:
    """Replace a TA's permissions; a TA editing their own gets 403."""
    await require_course_teacher(db, teacher, course_id)
    await _require_active_ta(db, course_id=course_id, user_id=user_id)
    permissions = sort_permissions(payload.permissions)
    try:
        await course_crud.set_ta_permissions(
            db, course_id=course_id, user_id=user_id, permissions=permissions
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return TaPermissionsUpdateResponse(
        user_id=user_id,
        permissions=permissions,
        message="TA permissions updated",
    )


async def revoke_course_ta(
    db: AsyncSession, teacher: User, course_id: UUID, user_id: UUID
) -> None:
    """Turn a TA back into a student of the course (sessions are kept)."""
    await require_course_teacher(db, teacher, course_id)
    membership = await _require_active_ta(db, course_id=course_id, user_id=user_id)
    try:
        await course_crud.demote_to_student(db, membership)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
