"""Topic and session-entry routes; permissions follow the in-course role."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.api.openapi_responses import (
    COURSE_TOPIC_LIST_RESPONSES,
    SESSION_CREATE_RESPONSES,
    TOPIC_CREATE_RESPONSES,
    TOPIC_DELETE_RESPONSES,
    TOPIC_EXPLANATION_RESPONSES,
)
from app.schemas.session import CreateSessionResponse
from app.schemas.topic import (
    CourseTopicsResponse,
    TopicCreateRequest,
    TopicExplanationResponse,
    TopicWriteResponse,
)
from app.services import session as session_service
from app.services import topics as topics_service

router = APIRouter(tags=["topics"])


@router.get(
    "/courses/{courseId}/topics",
    response_model=CourseTopicsResponse,
    response_model_exclude_unset=True,
    responses=COURSE_TOPIC_LIST_RESPONSES,
)
async def list_course_topics(
    courseId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseTopicsResponse:
    """List a course's topics; fields depend on the caller's role."""
    return await topics_service.list_course_topics(db, current_user, courseId)


@router.post(
    "/courses/{courseId}/topics",
    response_model=TopicWriteResponse,
    responses=TOPIC_CREATE_RESPONSES,
)
async def create_topic(
    courseId: UUID,
    payload: TopicCreateRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopicWriteResponse:
    """Create a topic in a course the caller teaches."""
    return await topics_service.create_topic(db, current_user, courseId, payload)


@router.delete(
    "/topics/{topicId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TOPIC_DELETE_RESPONSES,
)
async def delete_topic(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a topic by id (204). Idempotent if already gone; teacher only."""
    await topics_service.delete_topic(db, current_user, topicId)


@router.get(
    "/topics/{topicId}/explanation",
    response_model=TopicExplanationResponse,
    responses=TOPIC_EXPLANATION_RESPONSES,
)
async def get_topic_explanation(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopicExplanationResponse:
    """Return a topic's background (title and description only for now)."""
    return await topics_service.get_topic_explanation(db, current_user, topicId)


@router.post(
    "/topics/{topicId}/sessions",
    response_model=CreateSessionResponse,
    responses=SESSION_CREATE_RESPONSES,
)
async def create_session(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateSessionResponse:
    """Create the authenticated student's session for a topic."""
    return await session_service.create_student_session(
        db,
        current_user.id,
        topicId,
    )
