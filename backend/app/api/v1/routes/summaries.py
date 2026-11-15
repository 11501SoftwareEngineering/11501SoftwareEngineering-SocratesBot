"""Class summary draft, review, and published read."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, get_db
from app.api.openapi_responses import SUMMARY_PUBLISH_RESPONSES
from app.schemas.summary import (
    PublishedSummaryResponse,
    PublishSummaryResponse,
    ReviewSummaryResponse,
    SummaryDraftResponse,
    TeacherSummaryResponse,
    WithdrawSummaryResponse,
)
from app.services import summaries as summary_service

router = APIRouter(tags=["summaries"])


class SummaryTextRequest(BaseModel):
    overview: str = Field(min_length=1)
    viewpoint_summary: str = Field(min_length=1)


@router.post("/topics/{topicId}/summary")
async def start_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeacherSummaryResponse:
    """Start a class-summary draft from the ready reports."""
    return await summary_service.start_summary(db, teacher=teacher, topic_id=topicId)


@router.get("/topics/{topicId}/summary")
async def read_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    version: Annotated[int | None, Query(ge=1)] = None,
) -> TeacherSummaryResponse:
    """Return the instructor's summary draft and publish state."""
    return await summary_service.read_teacher_summary(
        db, teacher=teacher, topic_id=topicId, version=version
    )


@router.patch("/topics/{topicId}/summary")
async def edit_summary(
    topicId: UUID,
    payload: SummaryTextRequest,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SummaryDraftResponse:
    """Replace the overview and viewpoint text, and set the status back to draft."""
    return await summary_service.edit_summary(
        db,
        teacher=teacher,
        topic_id=topicId,
        overview=payload.overview,
        viewpoint_summary=payload.viewpoint_summary,
    )


@router.post(
    "/topics/{topicId}/summary/review",
    response_model_exclude_unset=True,
)
async def review_summary(
    topicId: UUID,
    payload: SummaryTextRequest,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewSummaryResponse:
    """Store the visible text when it changed, then mark that version reviewed."""
    return await summary_service.review_summary(
        db,
        teacher=teacher,
        topic_id=topicId,
        overview=payload.overview,
        viewpoint_summary=payload.viewpoint_summary,
    )


@router.post(
    "/topics/{topicId}/summary/publish",
    response_model_exclude_unset=True,
    responses=SUMMARY_PUBLISH_RESPONSES,
)
async def publish_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublishSummaryResponse:
    """Publish the latest summary when that version is reviewed."""
    return await summary_service.publish_summary(db, teacher=teacher, topic_id=topicId)


@router.post(
    "/topics/{topicId}/summary/withdraw",
    response_model_exclude_unset=True,
)
async def withdraw_summary(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WithdrawSummaryResponse:
    """Withdraw the published class summary."""
    return await summary_service.withdraw_summary(db, teacher=teacher, topic_id=topicId)


@router.get("/topics/{topicId}/summary/published")
async def read_published_summary(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublishedSummaryResponse:
    """Return the published summary for a member of the course."""
    return await summary_service.read_published(db, user=current_user, topic_id=topicId)
