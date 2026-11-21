"""Unprefixed inquiry routes. Setup needs the teacher or a TA with edit_topics; publish and generate need the course teacher."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, get_db
from app.api.openapi_responses import (
    INQUIRY_GENERATE_RESPONSES,
    INQUIRY_MODEL_LIST_RESPONSES,
    INQUIRY_PUBLISH_RESPONSES,
    INQUIRY_REFINE_RESPONSES,
    INQUIRY_SETUP_READ_RESPONSES,
    INQUIRY_SETUP_WRITE_RESPONSES,
)
from app.schemas.inquiry import (
    GenerateInquiryRequest,
    InquiryModelResponse,
    InquirySetupResponse,
    InquirySetupWriteResponse,
    OpeningMessageRequest,
    OpeningMessageResponse,
    RefineInquiryRequest,
    SaveInquiryRequest,
)
from app.services import inquiry as inquiry_service

router = APIRouter(tags=["inquiry"])


@router.get(
    "/inquiry-models",
    response_model=list[InquiryModelResponse],
    responses=INQUIRY_MODEL_LIST_RESPONSES,
)
async def list_inquiry_models(
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InquiryModelResponse]:
    """List the models a teacher or TA can pick, with per-million-token prices."""
    return await inquiry_service.list_inquiry_models(db, current_user)


@router.get(
    "/topics/{topicId}/setup",
    response_model=InquirySetupResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_SETUP_READ_RESPONSES,
)
async def get_inquiry_setup(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupResponse:
    """Read the saved inquiry."""
    return await inquiry_service.get_inquiry_setup(db, current_user, topicId)


@router.put(
    "/topics/{topicId}/setup",
    response_model=InquirySetupWriteResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_SETUP_WRITE_RESPONSES,
)
async def save_inquiry_setup(
    topicId: UUID,
    payload: SaveInquiryRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupWriteResponse:
    """Save the eight fields during setup. This does not publish."""
    return await inquiry_service.save_inquiry_setup(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/setup/generate",
    response_model=InquirySetupResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_GENERATE_RESPONSES,
)
async def generate_inquiry(
    topicId: UUID,
    payload: GenerateInquiryRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupResponse:
    """Suggest eight fields from the course description. This does not save them."""
    return await inquiry_service.generate_inquiry(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/setup/refine",
    response_model=InquirySetupResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_REFINE_RESPONSES,
)
async def refine_inquiry(
    topicId: UUID,
    payload: RefineInquiryRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupResponse:
    """Suggest eight fields from the setup on screen and the feedback. This does not save them."""
    return await inquiry_service.refine_inquiry(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/setup/opening-message",
    response_model=OpeningMessageResponse,
    responses=INQUIRY_REFINE_RESPONSES,
)
async def opening_message(
    topicId: UUID,
    payload: OpeningMessageRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OpeningMessageResponse:
    """Draft an opening line from the supplied setup and store it."""
    return await inquiry_service.opening_message(db, current_user, topicId, payload)


@router.post(
    "/topics/{topicId}/publish",
    response_model=InquirySetupWriteResponse,
    response_model_exclude_none=True,
    responses=INQUIRY_PUBLISH_RESPONSES,
)
async def publish_inquiry(
    topicId: UUID,
    payload: SaveInquiryRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InquirySetupWriteResponse:
    """Store the setup on screen, then move a complete topic to conversation."""
    return await inquiry_service.publish_inquiry(db, current_user, topicId, payload)
