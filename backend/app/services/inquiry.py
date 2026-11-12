"""Teacher inquiry setup: save, publish, and start a generation attempt."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GenerationStatus, TopicStage
from app.crud import attempt as attempt_crud
from app.crud import topic as topic_crud
from app.models.generation_attempt import GenerationAttempt
from app.models.topic import Topic
from app.models.user import User
from app.schemas.inquiry import (
    GenerateInquiryRequest,
    InquiryAttemptState,
    InquiryFields,
    InquiryGenerationResponse,
    InquirySetupResponse,
    PublishInquiryRequest,
    RefineInquiryRequest,
    SaveInquiryRequest,
    fields_from_mapping,
    first_incomplete_field,
)
from app.services import inquiry_runner
from app.services.topics import get_instructed_topic


def _fields_of(topic: Topic) -> InquiryFields:
    return InquiryFields(
        age_band=topic.age_band,
        max_turns=topic.max_turns,
        topic=topic.inquiry_topic,
        core_question=topic.core_question,
        inquiry_focus=topic.inquiry_focus,
        background_info=topic.background_info,
        exclusions=topic.exclusions,
        opening_message=topic.opening_message,
    )


def _attempt_state(attempt: GenerationAttempt) -> InquiryAttemptState:
    body = None
    if attempt.status == GenerationStatus.READY.value and attempt.result_json:
        body = fields_from_mapping(attempt.result_json)
    return InquiryAttemptState(
        attempt_id=attempt.id,
        status=GenerationStatus(attempt.status),
        body=body,
    )


def _response(
    topic: Topic, attempt: GenerationAttempt | None, message: str | None = None
) -> InquirySetupResponse:
    return InquirySetupResponse(
        topic_id=topic.id,
        course_id=topic.course_id,
        version=topic.version,
        topic_status=topic.stage,
        content_language=topic.content_language,
        setup=_fields_of(topic),
        attempt=_attempt_state(attempt) if attempt is not None else None,
        message=message,
    )


async def _require_setup(topic: Topic) -> None:
    if topic.stage != TopicStage.SETUP.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic is not in setup",
        )


async def _reconcile(
    db: AsyncSession, attempt: GenerationAttempt | None
) -> GenerationAttempt | None:
    if attempt is None:
        return None
    if not inquiry_runner.should_fail_processing(
        status=attempt.status,
        live=inquiry_runner.is_live(attempt.id),
        lease_expires_at=attempt.lease_expires_at,
        now=datetime.now(UTC),
        startup=False,
    ):
        return attempt
    await attempt_crud.mark_failed_if_processing(db, attempt.id)
    await db.commit()
    attempt.status = GenerationStatus.FAILED.value
    attempt.result_json = None
    return attempt


async def get_inquiry_setup(
    db: AsyncSession, teacher: User, topic_id: UUID
) -> InquirySetupResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    attempt = await _reconcile(
        db, await attempt_crud.latest_inquiry_attempt(db, topic.id)
    )
    return _response(topic, attempt)


async def save_inquiry_setup(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: SaveInquiryRequest
) -> InquirySetupResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    await _require_setup(topic)
    if topic.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version conflict",
        )
    try:
        topic = await topic_crud.save_inquiry(
            db,
            topic,
            content_language=payload.content_language,
            age_band=payload.setup.age_band,
            max_turns=payload.setup.max_turns,
            inquiry_topic=payload.setup.topic,
            core_question=payload.setup.core_question,
            inquiry_focus=payload.setup.inquiry_focus,
            background_info=payload.setup.background_info,
            exclusions=payload.setup.exclusions or "unspecified",
            opening_message=payload.setup.opening_message,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    attempt = await attempt_crud.latest_inquiry_attempt(db, topic.id)
    return _response(topic, attempt, "Inquiry saved")


async def publish_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: PublishInquiryRequest
) -> InquirySetupResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    await _require_setup(topic)
    if topic.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version conflict",
        )
    missing = first_incomplete_field(
        age_band=topic.age_band,
        max_turns=topic.max_turns,
        topic=topic.inquiry_topic,
        core_question=topic.core_question,
    )
    if missing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incomplete setup: {missing}",
        )
    try:
        topic = await topic_crud.publish_topic(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    attempt = await attempt_crud.latest_inquiry_attempt(db, topic.id)
    return _response(topic, attempt, "Inquiry published")


async def _start_attempt(
    db: AsyncSession, topic: Topic, request_json: dict
) -> InquiryGenerationResponse:
    await _require_setup(topic)
    try:
        attempt = await attempt_crud.create_inquiry_attempt(
            db, topic_id=topic.id, request_json=request_json
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    inquiry_runner.schedule(attempt.id)
    return InquiryGenerationResponse(
        attempt_id=attempt.id,
        status=GenerationStatus.PENDING,
    )


async def generate_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: GenerateInquiryRequest
) -> InquiryGenerationResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    return await _start_attempt(
        db,
        topic,
        {
            "mode": "generate",
            "age_band": payload.age_band,
            "max_turns": payload.max_turns,
            "content_language": payload.content_language,
            "course_description": payload.course_description,
        },
    )


async def refine_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: RefineInquiryRequest
) -> InquiryGenerationResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    return await _start_attempt(
        db,
        topic,
        {
            "mode": "refine",
            "setup": payload.setup.model_dump(),
            "feedback": payload.feedback,
        },
    )
