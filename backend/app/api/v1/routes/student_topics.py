"""Student topic routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import StudentUser, get_db
from app.api.openapi_responses import (
    STUDENT_COURSE_TOPIC_LIST_RESPONSES,
    STUDENT_TOPIC_EXPLANATION_RESPONSES,
)
from app.schemas.topic import StudentCourseTopicsResponse, TopicExplanationResponse
from app.services import topics as topics_service

router = APIRouter(prefix="/student", tags=["student-topics"])


@router.get(
    "/courses/{courseId}/topics",
    response_model=StudentCourseTopicsResponse,
    responses=STUDENT_COURSE_TOPIC_LIST_RESPONSES,
)
async def list_course_topics(
    courseId: UUID,
    current_user: StudentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentCourseTopicsResponse:
    """List a joined course's topics with the student's session state."""
    return await topics_service.list_student_course_topics(db, current_user, courseId)


@router.get(
    "/topics/{topicId}/explanation",
    response_model=TopicExplanationResponse,
    responses=STUDENT_TOPIC_EXPLANATION_RESPONSES,
)
async def get_topic_explanation(
    topicId: UUID,
    current_user: StudentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopicExplanationResponse:
    """Return a topic's background (title and description only for now)."""
    return await topics_service.get_topic_explanation(db, current_user, topicId)
