"""Teacher topic update route (kept until the topic create/edit rework)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TeacherUser, get_db
from app.api.openapi_responses import TEACHER_TOPIC_UPDATE_RESPONSES
from app.schemas.topic import TopicUpdateRequest, TopicWriteResponse
from app.services import topics as topics_service

router = APIRouter(prefix="/teacher", tags=["teacher-topics"])


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
