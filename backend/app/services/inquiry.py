"""Teacher inquiry setup. Create, refine, and the opening line wait for the model."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TopicStage
from app.crud import topic as topic_crud
from app.models.topic import Topic
from app.models.user import User
from app.schemas.inquiry import (
    CreateInquiryTopicRequest,
    GeneratedInquiry,
    InquiryFields,
    InquirySetupResponse,
    InquirySetupWriteResponse,
    OpeningMessageDraft,
    OpeningMessageRequest,
    OpeningMessageResponse,
    RefineInquiryRequest,
    SaveInquiryRequest,
    first_incomplete_field,
)
from app.services import courses as courses_service
from app.services.model_client import ModelCallError, OpenAIChatClient
from app.services.topics import get_instructed_topic

_INSTRUCTIONS = (
    "Turn the teacher's notes into an eight-field inquiry. "
    "Return only the JSON object. Do not name a student. "
    "inquiry_focus must not prescribe a conclusion the student must accept. "
    "background_info must not state unverified claims as facts. "
    "Use exclusions 'unspecified' when the teacher gave no exclusion. "
    "opening_message may be empty."
)
_OPENING_INSTRUCTIONS = (
    "Write one opening message for this inquiry. "
    "Return it in opening_message and keep the other fields unchanged. "
    "The opening message may be empty. Do not name a student."
)


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


def _response(topic: Topic) -> InquirySetupResponse:
    return InquirySetupResponse(
        topic_id=topic.id,
        course_id=topic.course_id,
        topic_status=topic.stage,
        opening_message=topic.opening_message,
        model_id=topic.model_id,
        setup=_fields_of(topic),
    )


def _written(topic: Topic, message: str) -> InquirySetupWriteResponse:
    return InquirySetupWriteResponse(**_response(topic).model_dump(), message=message)


async def _require_setup(topic: Topic) -> None:
    if topic.stage != TopicStage.SETUP.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic is not in setup",
        )


async def _locked_setup(db: AsyncSession, topic_id: UUID) -> Topic:
    """Reload the topic under a row lock and refuse it unless it is still setup."""
    topic = await topic_crud.lock_topic(db, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    await _require_setup(topic)
    return topic


def _model_failure(exc: ModelCallError) -> HTTPException:
    code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if exc.status_code in {429, 503}
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(status_code=code, detail="Inquiry generation failed")


async def _model_json(model_id: str, instructions: str, material: str) -> dict:
    try:
        return await OpenAIChatClient().complete_json(
            instructions=instructions,
            material=material,
            model=model_id,
        )
    except ModelCallError as exc:
        raise _model_failure(exc) from None


def _validated(raw: dict, schema: type[GeneratedInquiry] | type[OpeningMessageDraft]):
    try:
        return schema.model_validate(raw)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Inquiry generation failed",
        ) from None


async def _complete(
    model_id: str, instructions: str, material: str
) -> GeneratedInquiry:
    raw = await _model_json(model_id, instructions, material)
    return _validated(raw, GeneratedInquiry)


def _material(topic: Topic, *, feedback: str | None = None) -> str:
    fields = _fields_of(topic)
    lines = [
        f"content_language: {topic.content_language}",
        f"age_band: {fields.age_band}",
        f"max_turns: {fields.max_turns}",
        f"topic: {fields.topic}",
        f"core_question: {fields.core_question}",
        f"inquiry_focus: {fields.inquiry_focus}",
        f"background_info: {fields.background_info}",
        f"exclusions: {fields.exclusions}",
        f"opening_message: {fields.opening_message}",
    ]
    if feedback is not None:
        lines.append(f"feedback:\n{feedback}")
    return "\n".join(lines)


def _apply(topic: Topic, generated: GeneratedInquiry) -> None:
    topic.title = generated.topic
    topic.age_band = generated.age_band
    topic.max_turns = generated.max_turns
    topic.inquiry_topic = generated.topic
    topic.core_question = generated.core_question
    topic.inquiry_focus = generated.inquiry_focus or None
    topic.background_info = generated.background_info or None
    topic.exclusions = generated.exclusions
    topic.opening_message = generated.opening_message or None


async def get_inquiry_setup(
    db: AsyncSession, teacher: User, topic_id: UUID
) -> InquirySetupResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    return _response(topic)


async def create_inquiry_topic(
    db: AsyncSession,
    user: User,
    course_id: UUID,
    payload: CreateInquiryTopicRequest,
) -> InquirySetupResponse:
    course = await courses_service.require_course_teacher(db, user, course_id)
    generated = await _complete(
        payload.model_id,
        _INSTRUCTIONS,
        (
            f"content_language: {payload.content_language}\n"
            f"age_band: {payload.age_band}\n"
            f"max_turns: {payload.max_turns}\n"
            f"course_description:\n{payload.course_description}"
        ),
    )
    try:
        topic = await topic_crud.create_topic(
            db,
            course_id=course.id,
            created_by=user.id,
            title=generated.topic,
            description=payload.course_description,
        )
        topic.content_language = payload.content_language
        topic.model_id = payload.model_id
        topic.stage = TopicStage.SETUP.value
        _apply(topic, generated)
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _response(topic)


async def save_inquiry_setup(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: SaveInquiryRequest
) -> InquirySetupWriteResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    try:
        topic = await _locked_setup(db, topic.id)
        topic = await topic_crud.save_inquiry(
            db,
            topic,
            content_language=topic.content_language,
            age_band=payload.setup.age_band,
            max_turns=payload.setup.max_turns,
            inquiry_topic=payload.setup.topic,
            core_question=payload.setup.core_question,
            inquiry_focus=payload.setup.inquiry_focus,
            background_info=payload.setup.background_info,
            exclusions=payload.setup.exclusions or "unspecified",
            opening_message=payload.setup.opening_message,
        )
        if payload.setup.topic:
            topic.title = payload.setup.topic
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _written(topic, "Inquiry saved")


async def publish_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID
) -> InquirySetupWriteResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    try:
        topic = await _locked_setup(db, topic.id)
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
        topic = await topic_crud.publish_topic(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _written(topic, "Inquiry published")


async def refine_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: RefineInquiryRequest
) -> InquirySetupResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    await _require_setup(topic)
    generated = await _complete(
        topic.model_id or settings.OPENAI_MODEL,
        _INSTRUCTIONS,
        _material(topic, feedback=payload.feedback),
    )
    try:
        topic = await _locked_setup(db, topic.id)
        _apply(topic, generated)
        await topic_crud.save_inquiry(
            db,
            topic,
            content_language=topic.content_language,
            age_band=topic.age_band,
            max_turns=topic.max_turns,
            inquiry_topic=topic.inquiry_topic,
            core_question=topic.core_question,
            inquiry_focus=topic.inquiry_focus,
            background_info=topic.background_info,
            exclusions=topic.exclusions,
            opening_message=topic.opening_message,
        )
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _response(topic)


async def opening_message(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: OpeningMessageRequest
) -> OpeningMessageResponse:
    topic = await get_instructed_topic(db, teacher, topic_id)
    await _require_setup(topic)
    draft = payload.setup
    raw = await _model_json(
        topic.model_id or settings.OPENAI_MODEL,
        _OPENING_INSTRUCTIONS,
        (
            f"age_band: {draft.age_band}\n"
            f"max_turns: {draft.max_turns}\n"
            f"topic: {draft.topic}\n"
            f"core_question: {draft.core_question}\n"
            f"inquiry_focus: {draft.inquiry_focus}\n"
            f"background_info: {draft.background_info}\n"
            f"exclusions: {draft.exclusions}\n"
            f"opening_message: {draft.opening_message}"
        ),
    )
    generated = _validated(raw, OpeningMessageDraft)
    return OpeningMessageResponse(opening_message=generated.opening_message)
