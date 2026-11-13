from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, get_db
from app.services import summaries as summary_service

router = APIRouter(tags=["summaries"])


class SummaryEditRequest(BaseModel):
    version: int
    overview: str = Field(min_length=1)
    viewpoint_summary: str = Field(min_length=1)


class SummaryVersionRequest(BaseModel):
    version: int


@router.post("/topics/{topicId}/summary")
async def start_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.start_summary(db, teacher=teacher, topic_id=topicId)


@router.get("/topics/{topicId}/summary")
async def read_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.read_teacher_summary(
        db, teacher=teacher, topic_id=topicId
    )


@router.patch("/topics/{topicId}/summary")
async def edit_summary(
    topicId: UUID,
    payload: SummaryEditRequest,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.edit_summary(
        db,
        teacher=teacher,
        topic_id=topicId,
        version=payload.version,
        overview=payload.overview,
        viewpoint_summary=payload.viewpoint_summary,
    )


@router.post("/topics/{topicId}/summary/review")
async def review_summary(
    topicId: UUID,
    payload: SummaryVersionRequest,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.review_summary(
        db, teacher=teacher, topic_id=topicId, version=payload.version
    )


@router.post("/topics/{topicId}/summary/publish")
async def publish_summary(
    topicId: UUID,
    payload: SummaryVersionRequest,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.publish_summary(
        db, teacher=teacher, topic_id=topicId, version=payload.version
    )


@router.post("/topics/{topicId}/summary/withdraw")
async def withdraw_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.withdraw_summary(db, teacher=teacher, topic_id=topicId)


@router.get("/topics/{topicId}/summary/published")
async def read_published_summary(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await summary_service.read_published(db, user=current_user, topic_id=topicId)
