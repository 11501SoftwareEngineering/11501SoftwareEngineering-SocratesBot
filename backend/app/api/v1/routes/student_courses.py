"""Student course list / join / leave routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import StudentUser, get_db
from app.api.openapi_responses import (
    STUDENT_COURSE_JOIN_RESPONSES,
    STUDENT_COURSE_LEAVE_RESPONSES,
    STUDENT_COURSE_LIST_RESPONSES,
)
from app.schemas.course import (
    StudentCourseListItem,
    StudentJoinRequest,
    StudentJoinResponse,
)
from app.services import courses as courses_service

router = APIRouter(prefix="/student/courses", tags=["student-courses"])


@router.get(
    "",
    response_model=list[StudentCourseListItem],
    responses=STUDENT_COURSE_LIST_RESPONSES,
)
async def list_courses(
    current_user: StudentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StudentCourseListItem]:
    return await courses_service.list_student_courses(db, current_user)


@router.post(
    "/join",
    response_model=StudentJoinResponse,
    responses=STUDENT_COURSE_JOIN_RESPONSES,
)
async def join_course(
    payload: StudentJoinRequest,
    current_user: StudentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentJoinResponse:
    return await courses_service.join_course(db, current_user, payload)


@router.delete(
    "/{courseId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=STUDENT_COURSE_LEAVE_RESPONSES,
)
async def leave_course(
    courseId: UUID,
    current_user: StudentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Leave a course (204). Idempotent if already left or not a member."""
    await courses_service.leave_course(db, current_user, courseId)
