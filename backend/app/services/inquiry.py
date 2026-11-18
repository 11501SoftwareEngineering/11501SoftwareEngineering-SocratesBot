"""Teacher inquiry setup. Create, refine, and the opening line wait for the model."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TaPermission, TopicStage, UserRole
from app.crud import course as course_crud
from app.crud import inquiry_model as inquiry_model_crud
from app.crud import topic as topic_crud
from app.models.inquiry_model import InquiryModel
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


async def list_inquiry_models(db: AsyncSession, user: User) -> list[InquiryModel]:
    """List the model catalog for a global teacher or an active TA of any course.

    Raises:
        HTTPException: 403 for anyone else.
    """
    if user.role != UserRole.TEACHER.value and not (
        await course_crud.is_active_ta_anywhere(db, user.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or TA privileges required",
        )
    return await inquiry_model_crud.list_inquiry_models(db)


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


def _reject_if_stale(topic: Topic, seen_at: object) -> None:
    """Refuse a write when someone saved this topic while the model was running."""
    if topic.updated_at != seen_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inquiry was updated",
        )


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


def _material(
    fields: InquiryFields, *, content_language: str, feedback: str | None = None
) -> str:
    lines = [
        f"content_language: {content_language}",
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
    """Return the saved inquiry for an instructor of the course.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor.
    """
    topic = await get_instructed_topic(db, teacher, topic_id)
    return _response(topic)


async def create_inquiry_topic(
    db: AsyncSession,
    user: User,
    course_id: UUID,
    payload: CreateInquiryTopicRequest,
) -> InquirySetupResponse:
    """Create a setup topic and fill the eight fields from the model.

    Raises:
        HTTPException: 404 if the course is missing; 403 if the caller is not
            the teacher or a TA with edit_topics; 502 or 503 if the model fails.
    """
    course, _role = await courses_service.require_course_teacher_or_ta(
        db, user, course_id, TaPermission.EDIT_TOPICS
    )
    language = settings.DEFAULT_LANGUAGE_CODE
    model_id = settings.OPENAI_MODEL
    generated = await _complete(
        model_id,
        _INSTRUCTIONS,
        (
            f"content_language: {language}\n"
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
        topic.content_language = language
        topic.model_id = model_id
        topic.stage = TopicStage.SETUP.value
        _apply(topic, generated)
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _response(topic)


async def _store_setup(db: AsyncSession, topic: Topic, setup: InquiryFields) -> Topic:
    """Write the eight fields on screen. The caller commits."""
    topic = await topic_crud.save_inquiry(
        db,
        topic,
        content_language=topic.content_language,
        age_band=setup.age_band,
        max_turns=setup.max_turns,
        inquiry_topic=setup.topic,
        core_question=setup.core_question,
        inquiry_focus=setup.inquiry_focus,
        background_info=setup.background_info,
        exclusions=setup.exclusions or "unspecified",
        opening_message=setup.opening_message,
    )
    if setup.topic:
        topic.title = setup.topic
    if setup.core_question:
        topic.description = setup.core_question
    return topic


async def save_inquiry_setup(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: SaveInquiryRequest
) -> InquirySetupWriteResponse:
    """Save the eight fields while the topic is still in setup.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup.
    """
    topic = await get_instructed_topic(db, teacher, topic_id)
    try:
        topic = await _locked_setup(db, topic.id)
        topic = await _store_setup(db, topic, payload.setup)
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _written(topic, "Inquiry saved")


async def publish_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: SaveInquiryRequest
) -> InquirySetupWriteResponse:
    """Store the setup on screen, then move a complete topic to conversation.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup; 422 if setup is incomplete.
    """
    topic = await get_instructed_topic(db, teacher, topic_id)
    try:
        topic = await _locked_setup(db, topic.id)
        topic = await _store_setup(db, topic, payload.setup)
        missing = first_incomplete_field(
            age_band=topic.age_band,
            max_turns=topic.max_turns,
            topic=topic.inquiry_topic,
            core_question=topic.core_question,
        )
        if missing is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Incomplete setup: {missing}",
            )
        topic = await topic_crud.publish_topic(db, topic)
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _written(topic, "Inquiry published")


async def refine_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: RefineInquiryRequest
) -> InquirySetupResponse:
    """Regenerate the eight fields from the setup on screen and store the change.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup; 502 or 503 if the model call fails.
    """
    topic = await get_instructed_topic(db, teacher, topic_id)
    await _require_setup(topic)
    seen_at = topic.updated_at
    topic_id = topic.id
    model_id = topic.model_id or settings.OPENAI_MODEL
    language = topic.content_language or settings.DEFAULT_LANGUAGE_CODE
    await db.commit()
    generated = await _complete(
        model_id,
        _INSTRUCTIONS,
        _material(payload.setup, content_language=language, feedback=payload.feedback),
    )
    try:
        topic = await _locked_setup(db, topic_id)
        _reject_if_stale(topic, seen_at)
        _apply(topic, generated)
        await _store_setup(db, topic, _fields_of(topic))
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _response(topic)


async def opening_message(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: OpeningMessageRequest
) -> OpeningMessageResponse:
    """Draft an opening line from the supplied setup and store it.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup; 502 or 503 if the model call fails.
    """
    topic = await get_instructed_topic(db, teacher, topic_id)
    await _require_setup(topic)
    seen_at = topic.updated_at
    topic_id = topic.id
    model_id = topic.model_id or settings.OPENAI_MODEL
    draft = payload.setup
    await db.commit()
    raw = await _model_json(
        model_id,
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
    try:
        topic = await _locked_setup(db, topic_id)
        _reject_if_stale(topic, seen_at)
        topic.opening_message = generated.opening_message or None
        await topic_crud.record_inquiry_change(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return OpeningMessageResponse(opening_message=generated.opening_message)
