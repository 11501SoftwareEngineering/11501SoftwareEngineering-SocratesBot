"""Teacher topic routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TeacherUser, get_db
from app.api.openapi_responses import (
    TEACHER_COURSE_TOPIC_LIST_RESPONSES,
    TEACHER_TOPIC_CREATE_RESPONSES,
    TEACHER_TOPIC_DELETE_RESPONSES,
    TEACHER_TOPIC_UPDATE_RESPONSES,
)
from app.schemas.topic import (
    TeacherCourseTopicsResponse,
    TopicCreateRequest,
    TopicUpdateRequest,
    TopicWriteResponse,
)
from app.services import topics as topics_service

router = APIRouter(prefix="/teacher", tags=["teacher-topics"])


@router.get(
    "/courses/{courseId}/topics",
    response_model=TeacherCourseTopicsResponse,
    responses=TEACHER_COURSE_TOPIC_LIST_RESPONSES,
)
async def list_course_topics(
    courseId: UUID,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeacherCourseTopicsResponse:
    """List a course's topics with completed-session counts."""
    return await topics_service.list_teacher_course_topics(db, current_user, courseId)


@router.post(
    "/topics",
    response_model=TopicWriteResponse,
    responses=TEACHER_TOPIC_CREATE_RESPONSES,
)
async def create_topic(
    payload: TopicCreateRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopicWriteResponse:
    """Create a topic in a course the teacher instructs."""
    return await topics_service.create_topic(db, current_user, payload)


@router.put(
    "/topics/{topicId}",
    response_model=TopicWriteResponse,
    responses=TEACHER_TOPIC_UPDATE_RESPONSES,
)
async def update_topic(
    topicId: UUID,
    payload: TopicUpdateRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopicWriteResponse:
    """Replace a topic's title and description."""
    return await topics_service.update_topic(db, current_user, topicId, payload)


@router.delete(
    "/topics/{topicId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TEACHER_TOPIC_DELETE_RESPONSES,
)
async def delete_topic(
    topicId: UUID,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a topic by id (204). Idempotent if already gone; instructors only."""
    await topics_service.delete_topic(db, current_user, topicId)
