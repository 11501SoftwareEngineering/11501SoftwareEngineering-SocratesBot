from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.core.enums import UserRole
from app.crud import course as course_crud
from app.models.course import Course
from app.schemas.course import CourseCreateRequest, CourseCreateResponse

router = APIRouter(prefix="/teacher/courses", tags=["teacher-courses"])


@router.post(
    "",
    response_model=CourseCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher_course(
    payload: CourseCreateRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Course:
    """Create a course owned by the authenticated teacher."""

    if current_user.role != UserRole.TEACHER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher privileges required",
        )

    return await course_crud.create_course(
        db,
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
