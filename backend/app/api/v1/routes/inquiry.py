"""Unprefixed inquiry routes. The caller is the course instructor."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TeacherUser, get_db
from app.api.openapi_responses import (
    INQUIRY_PUBLISH_RESPONSES,
    INQUIRY_SETUP_READ_RESPONSES,
    INQUIRY_SETUP_WRITE_RESPONSES,
)
from app.schemas.inquiry import (
    GenerateInquiryRequest,
    InquiryGenerationResponse,
    InquirySetupResponse,
    PublishInquiryRequest,
    RefineInquiryRequest,
    SaveInquiryRequest,
)
from app.services import inquiry as inquiry_service

router = APIRouter(tags=["inquiry"])


@router.get(
    "/topics/{topicId}/setup",
    response_model=InquirySetupResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_SETUP_READ_RESPONSES,
)
async def get_inquiry_setup(
    topicId: UUID,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupResponse:
    """Read the saved inquiry. The attempt body is included only when ready."""
    return await inquiry_service.get_inquiry_setup(db, current_user, topicId)


@router.put(
    "/topics/{topicId}/setup",
    response_model=InquirySetupResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_SETUP_WRITE_RESPONSES,
)
async def save_inquiry_setup(
    topicId: UUID,
    payload: SaveInquiryRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupResponse:
    """Save the eight fields during setup. This does not publish."""
    return await inquiry_service.save_inquiry_setup(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/setup/generate",
    response_model=InquiryGenerationResponse,
    responses=INQUIRY_SETUP_WRITE_RESPONSES,
)
async def generate_inquiry(
    topicId: UUID,
    payload: GenerateInquiryRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquiryGenerationResponse:
    """Start eight-field generation. The saved inquiry is left unchanged."""
    return await inquiry_service.generate_inquiry(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/setup/refine",
    response_model=InquiryGenerationResponse,
    responses=INQUIRY_SETUP_WRITE_RESPONSES,
)
async def refine_inquiry(
    topicId: UUID,
    payload: RefineInquiryRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquiryGenerationResponse:
    """Regenerate from the current fields and feedback without saving them."""
    return await inquiry_service.refine_inquiry(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/publish",
    response_model=InquirySetupResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_PUBLISH_RESPONSES,
)
async def publish_inquiry(
    topicId: UUID,
    payload: PublishInquiryRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupResponse:
    """Move a complete setup to conversation and freeze the inquiry fields."""
    return await inquiry_service.publish_inquiry(db, current_user, topicId, payload)
