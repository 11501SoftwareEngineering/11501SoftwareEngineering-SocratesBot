"""Teacher course routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TeacherUser, get_db
from app.api.openapi_responses import (
    TEACHER_COURSE_CREATE_RESPONSES,
    TEACHER_COURSE_DELETE_RESPONSES,
)
from app.schemas.course import (
    CourseCreateRequest,
    CourseCreateResponse,
    TeacherCourseListItem,
)
from app.services import courses as courses_service

router = APIRouter(prefix="/teacher/courses", tags=["teacher-courses"])


@router.get("", response_model=list[TeacherCourseListItem])
async def list_courses(
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TeacherCourseListItem]:
    return await courses_service.list_teacher_courses(db, current_user)


@router.post(
    "",
    response_model=CourseCreateResponse,
    responses=TEACHER_COURSE_CREATE_RESPONSES,
)
async def create_course(
    payload: CourseCreateRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseCreateResponse:
    return await courses_service.create_course(db, current_user, payload)


@router.delete(
    "/{courseId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TEACHER_COURSE_DELETE_RESPONSES,
)
async def delete_course(
    courseId: UUID,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a course by id (204). Idempotent if already gone; creator only."""
    await courses_service.delete_teacher_course(db, current_user, courseId)
