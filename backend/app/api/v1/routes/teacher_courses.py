"""Teacher add-student route (kept until the course member APIs replace it)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TeacherUser, get_db
from app.api.openapi_responses import TEACHER_COURSE_STUDENT_ADD_RESPONSES
from app.schemas.course import CourseStudentAddRequest, MessageResponse
from app.services import courses as courses_service

router = APIRouter(prefix="/teacher/courses", tags=["teacher-courses"])


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
