"""Business rules for course management (permissions follow in-course role)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import is_super_admin
from app.core.enums import CourseRole, TaPermission
from app.crud import course as course_crud
from app.crud import user as user_crud
from app.models.course import Course, CourseMembership
from app.models.user import User
from app.schemas.course import (
    CourseCreateRequest,
    CourseCreateResponse,
    CourseJoinRequest,
    CourseJoinResponse,
    CourseListItem,
    CourseMemberListItem,
    TaAssignRequest,
    TaAssignResponse,
    TaPermissionsUpdateRequest,
    TaPermissionsUpdateResponse,
)
from app.services.course_invites import (
    INVITE_ALPHABET,
    INVITE_COLLISION_RETRIES,
    INVITE_LENGTH,
    generate_invite_code,
)

_INVITE_RE = re.compile(rf"^[{INVITE_ALPHABET}]{{{INVITE_LENGTH}}}$")
_INVITE_UNIQUE_CONSTRAINT = "uq_courses_invitation_code"
_MEMBERSHIP_UNIQUE = "uq_course_memberships_course_id"
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
    """True only for course_memberships ``(course_id, user_id)`` conflicts."""
    return _is_constraint_violation(exc, _MEMBERSHIP_UNIQUE)


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
        db_role,
        ta_permissions,
    ) in await course_crud.list_my_course_rows(db, user.id):
        role = _ROLE_BY_DB_VALUE[db_role]
        permissions: list[str] = []
        if role is CourseRole.TA:
            permissions = sort_permissions(ta_permissions)
        # ``student_count`` stays unset (omitted) for students and for TAs
        # without view_members.
        extra: dict[str, int] = {}
        if role is CourseRole.TEACHER or TaPermission.VIEW_MEMBERS in permissions:
            extra["student_count"] = student_count
        items.append(
            CourseListItem(
                course_id=course.id,
                name=course.name,
                description=course.description,
                teacher_name=teacher_name,
                topic_count=topic_count,
                my_role=role,
                my_permissions=permissions,
                invite_code=course.invitation_code,
                **extra,
            )
        )
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
    """List students and/or TAs.

    ``role=student`` is open to the teacher and TAs with ``view_members``;
    listing TAs (``role=ta`` or no filter) is teacher only.

    Raises:
        HTTPException: 404 if the course is missing; 403 if not allowed.
    """
    if role is CourseRole.STUDENT:
        await require_course_teacher_or_ta(
            db, user, course_id, TaPermission.VIEW_MEMBERS
        )
        db_roles: tuple[str, ...] = (course_crud.MEMBERSHIP_STUDENT,)
    else:
        await require_course_teacher(db, user, course_id)
        db_roles = (
            (course_crud.MEMBERSHIP_TA,)
            if role is CourseRole.TA
            else (course_crud.MEMBERSHIP_STUDENT, course_crud.MEMBERSHIP_TA)
        )
    rows = await course_crud.list_course_members(db, course_id, roles=db_roles)
    ta_permissions = await course_crud.list_ta_permissions(
        db,
        course_id=course_id,
        user_ids=[
            member.id
            for member, membership in rows
            if membership.role == course_crud.MEMBERSHIP_TA
        ],
    )
    return [
        CourseMemberListItem(
            user_id=member.id,
            account_id=member.account_id,
            name=member.name,
            role=_ROLE_BY_DB_VALUE[membership.role],
            joined_at=membership.joined_at,
            permissions=sort_permissions(ta_permissions.get(member.id, [])),
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


_ALREADY_TA_DETAIL = "Already a TA of this course"
_MEMBERSHIP_RACE_DETAIL = "Course membership changed concurrently; retry"


def _ta_assign_rejected(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def _require_active_ta(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> CourseMembership:
    """Lock the active TA membership; 404 if it is not (or no longer) a TA."""
    membership = await course_crud.get_active_membership(
        db, course_id=course_id, user_id=user_id, for_update=True
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
    """Make any registered account a TA of the course with ``permissions``.

    A student of the course is promoted in place (sessions are kept); someone
    who left or was removed rejoins as a TA; anyone else is added as a TA.

    Raises:
        HTTPException: 404 course / account missing; 403 not the course
            teacher; 400 already a TA here, a teacher of this course, or an
            admin.
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
    if await course_crud.is_course_instructor(
        db, course_id=course_id, teacher_id=target.id
    ):
        raise _ta_assign_rejected("Teachers of this course cannot be TAs")
    # Lock the row (active or soft-left) so a concurrent removal, leave or
    # revoke cannot slip in between this check and the write.
    membership = await course_crud.get_membership(
        db, course_id=course_id, user_id=target.id, for_update=True
    )
    if (
        membership is not None
        and membership.left_at is None
        and membership.role == course_crud.MEMBERSHIP_TA
    ):
        raise _ta_assign_rejected(_ALREADY_TA_DETAIL)

    permissions = sort_permissions(payload.permissions)
    try:
        if membership is None:
            await course_crud.add_ta_membership(
                db, course_id=course_id, user_id=target.id, permissions=permissions
            )
        else:
            await course_crud.promote_to_ta(db, membership, permissions)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint_violation(exc, _TA_PERMISSION_PK):
            raise _ta_assign_rejected(_ALREADY_TA_DETAIL) from None
        # A first-time member joined (or was added) while we were inserting.
        if _is_membership_duplicate_violation(exc):
            raise _ta_assign_rejected(_MEMBERSHIP_RACE_DETAIL) from None
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
    membership = await _require_active_ta(db, course_id=course_id, user_id=user_id)
    permissions = sort_permissions(payload.permissions)
    try:
        await course_crud.set_ta_permissions(db, membership, permissions)
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
    """Revoke a TA, delete their sessions in the course and remove them.

    Like any removed student they cannot rejoin with the invite code; the
    teacher can add them back as a student or assign them as a TA again.
    """
    await require_course_teacher(db, teacher, course_id)
    membership = await _require_active_ta(db, course_id=course_id, user_id=user_id)
    try:
        await course_crud.remove_ta_from_course(db, membership)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
