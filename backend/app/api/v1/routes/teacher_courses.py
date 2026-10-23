"""Teacher course and roster routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TeacherUser, get_db
from app.api.openapi_responses import (
    TEACHER_COURSE_CREATE_RESPONSES,
    TEACHER_COURSE_DELETE_RESPONSES,
    TEACHER_COURSE_STUDENT_ADD_RESPONSES,
    TEACHER_COURSE_STUDENT_LIST_RESPONSES,
    TEACHER_COURSE_STUDENT_REMOVE_RESPONSES,
)
from app.schemas.course import (
    CourseCreateRequest,
    CourseCreateResponse,
    CourseStudentAddRequest,
    CourseStudentListItem,
    MessageResponse,
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


@router.get(
    "/{courseId}/students",
    response_model=list[CourseStudentListItem],
    responses=TEACHER_COURSE_STUDENT_LIST_RESPONSES,
)
async def list_students(
    courseId: UUID,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CourseStudentListItem]:
    return await courses_service.list_course_students(db, current_user, courseId)


@router.post(
    "/{courseId}/students",
    response_model=MessageResponse,
    responses=TEACHER_COURSE_STUDENT_ADD_RESPONSES,
)
async def add_student(
    courseId: UUID,
    payload: CourseStudentAddRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    return await courses_service.add_course_student(db, current_user, courseId, payload)


@router.delete(
    "/{courseId}/students/{studentId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TEACHER_COURSE_STUDENT_REMOVE_RESPONSES,
)
async def remove_student(
    courseId: UUID,
    studentId: UUID,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a student from the course (204). Idempotent if already removed."""
    await courses_service.remove_course_student(db, current_user, courseId, studentId)
