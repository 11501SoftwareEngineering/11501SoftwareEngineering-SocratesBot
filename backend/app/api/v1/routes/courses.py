"""Course routes; permissions follow the caller's in-course role."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, UserAccount, get_db
from app.api.openapi_responses import (
    COURSE_CREATE_RESPONSES,
    COURSE_DELETE_RESPONSES,
    COURSE_GET_RESPONSES,
    COURSE_JOIN_RESPONSES,
    COURSE_LEAVE_RESPONSES,
    COURSE_LIST_RESPONSES,
    COURSE_MEMBER_LIST_RESPONSES,
    COURSE_STUDENT_REMOVE_RESPONSES,
    COURSE_TA_ASSIGN_RESPONSES,
    COURSE_TA_REVOKE_RESPONSES,
    COURSE_TA_UPDATE_RESPONSES,
    COURSE_UPDATE_RESPONSES,
)
from app.core.enums import CourseRole
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
    TaAssignRequest,
    TaAssignResponse,
    TaPermissionsUpdateRequest,
    TaPermissionsUpdateResponse,
)
from app.services import courses as courses_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get(
    "",
    response_model=list[CourseListItem],
    response_model_exclude_unset=True,
    responses=COURSE_LIST_RESPONSES,
)
async def list_courses(
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CourseListItem]:
    """Courses the caller teaches, assists in, or studies in (merged)."""
    return await courses_service.list_my_courses(db, current_user)


@router.post(
    "",
    response_model=CourseCreateResponse,
    responses=COURSE_CREATE_RESPONSES,
)
async def create_course(
    payload: CourseCreateRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseCreateResponse:
    return await courses_service.create_course(db, current_user, payload)


# Fixed-path routes are declared before ``/{courseId}`` so ``join`` is not
# captured as a course id.
@router.post(
    "/join",
    response_model=CourseJoinResponse,
    responses=COURSE_JOIN_RESPONSES,
)
async def join_course(
    payload: CourseJoinRequest,
    current_user: UserAccount,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseJoinResponse:
    """Join a course as a student with its invite code.

    A student who left, or whom the teacher removed, cannot join again with the
    code (400).
    """
    return await courses_service.join_course(db, current_user, payload)


@router.get(
    "/{courseId}",
    response_model=CourseDetailResponse,
    responses=COURSE_GET_RESPONSES,
)
async def get_course(
    courseId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseDetailResponse:
    return await courses_service.get_course(db, current_user, courseId)


@router.put(
    "/{courseId}",
    response_model=CourseUpdateResponse,
    responses=COURSE_UPDATE_RESPONSES,
)
async def update_course(
    courseId: UUID,
    payload: CourseUpdateRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseUpdateResponse:
    return await courses_service.update_course(db, current_user, courseId, payload)


@router.delete(
    "/{courseId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COURSE_DELETE_RESPONSES,
)
async def delete_course(
    courseId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a course by id (204). Idempotent if already gone; creator only."""
    await courses_service.delete_course(db, current_user, courseId)


@router.delete(
    "/{courseId}/member",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COURSE_LEAVE_RESPONSES,
)
async def leave_course(
    courseId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Student leaves a course (204). Idempotent if already left or not a member.

    After leaving, the student cannot join again with the invite code.
    """
    await courses_service.leave_course(db, current_user, courseId)


@router.get(
    "/{courseId}/members",
    response_model=list[CourseMemberListItem],
    responses=COURSE_MEMBER_LIST_RESPONSES,
)
async def list_members(
    courseId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    role: Annotated[
        Literal["student", "ta"] | None,
        Query(description="`student` or `ta`; omit for both"),
    ] = None,
) -> list[CourseMemberListItem]:
    """List students and/or TAs; an invalid ``role`` is rejected with 422."""
    return await courses_service.list_course_members(
        db, current_user, courseId, CourseRole(role) if role else None
    )


@router.delete(
    "/{courseId}/students/{userId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COURSE_STUDENT_REMOVE_RESPONSES,
)
async def remove_student(
    courseId: UUID,
    userId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a student from the course (204). Idempotent if already removed.

    A removed student cannot join again with the invite code. The teacher can
    still assign the account as a TA.
    """
    await courses_service.remove_course_student(db, current_user, courseId, userId)


@router.post(
    "/{courseId}/tas",
    response_model=TaAssignResponse,
    responses=COURSE_TA_ASSIGN_RESPONSES,
)
async def assign_ta(
    courseId: UUID,
    payload: TaAssignRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaAssignResponse:
    """Assign a student account as a TA, or only check it (course teacher only)."""
    return await courses_service.assign_course_ta(db, current_user, courseId, payload)


@router.put(
    "/{courseId}/tas/{userId}",
    response_model=TaPermissionsUpdateResponse,
    responses=COURSE_TA_UPDATE_RESPONSES,
)
async def update_ta_permissions(
    courseId: UUID,
    userId: UUID,
    payload: TaPermissionsUpdateRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaPermissionsUpdateResponse:
    """Replace a TA's permissions (course teacher only)."""
    return await courses_service.update_course_ta_permissions(
        db, current_user, courseId, userId, payload
    )


@router.delete(
    "/{courseId}/tas/{userId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COURSE_TA_REVOKE_RESPONSES,
)
async def revoke_ta(
    courseId: UUID,
    userId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Revoke a TA, delete their sessions here and remove them (204)."""
    await courses_service.revoke_course_ta(db, current_user, courseId, userId)
