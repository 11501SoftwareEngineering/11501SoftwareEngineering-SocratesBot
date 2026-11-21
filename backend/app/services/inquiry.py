"""Teacher inquiry setup. Create, generate, refine, and the opening line wait for the model."""

from __future__ import annotations

import json
import re
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TaPermission, TopicStage, UserRole
from app.core.prompts import PromptDefinition, PromptStage, prompt_for
from app.crud import course as course_crud
from app.crud import inquiry_model as inquiry_model_crud
from app.crud import topic as topic_crud
from app.models.inquiry_model import InquiryModel
from app.models.topic import Topic
from app.models.user import User
from app.schemas.inquiry import (
    CreatedInquiryResponse,
    CreateInquiryTopicRequest,
    DesignOutput,
    GeneratedInquiry,
    GenerateInquiryRequest,
    InquiryFeedback,
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
from app.services.model_client import (
    ModelCallError,
    ModelTimeoutError,
    OpenAIChatClient,
)
from app.services.teacher_ai_settings import (
    course_api_key,
    effective_default_model,
    openrouter_api_key,
)
from app.services.teacher_input import topic_issue, topic_issue_message
from app.services.topics import get_instructed_topic


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
        content_language=topic.content_language,
        setup=_fields_of(topic),
    )


def _suggestion(
    topic: Topic,
    generated: GeneratedInquiry,
    model_id: str | None,
    feedback: InquiryFeedback,
    language: str,
) -> InquirySetupResponse:
    return InquirySetupResponse(
        topic_id=topic.id,
        course_id=topic.course_id,
        topic_status=topic.stage,
        model_id=model_id,
        content_language=language,
        setup=InquiryFields.model_validate(generated.model_dump()),
        **feedback.model_dump(),
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


_PLACEHOLDER = re.compile(
    r"^(未指定|尚未指定|待補|待補充|不適用|n/?a|not specified|unspecified|tbd|none|null)[.!\u3002\uff01]?$",
    re.IGNORECASE,
)
_SETUP_WARNING = (
    "Background or exclusions were not specified. Confirm them before publishing."
)


def _model_failure(exc: ModelCallError) -> HTTPException:
    if isinstance(exc, ModelTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "Course setup took longer than 45 seconds and was stopped. "
                "Your input was kept; try again or shorten the description."
            ),
        )
    code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if exc.status_code in {429, 503}
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(status_code=code, detail="Inquiry generation failed")


async def _model_json(
    model_id: str, prompt: PromptDefinition, material: str, api_key: str
) -> dict:
    try:
        return await OpenAIChatClient().complete_opening(
            instructions=prompt.instructions,
            material=material,
            model=model_id,
            api_key=api_key,
            max_tokens=prompt.max_output_tokens,
        )
    except ModelCallError as exc:
        raise _model_failure(exc) from None


def _validated[Parsed: (GeneratedInquiry, OpeningMessageDraft, DesignOutput)](
    raw: dict, schema: type[Parsed]
) -> Parsed:
    try:
        return schema.model_validate(raw)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Inquiry generation failed",
        ) from None


async def _design_json(
    model_id: str, prompt: PromptDefinition, material: str, api_key: str
) -> dict:
    try:
        return await OpenAIChatClient().complete_design(
            instructions=prompt.instructions,
            material=material,
            model=model_id,
            api_key=api_key,
            max_tokens=prompt.max_output_tokens,
        )
    except ModelCallError as exc:
        raise _model_failure(exc) from None


def _design_material(
    *,
    language: str,
    age_band: str | None,
    max_turns: int | None,
    theme_context: str,
    current: InquiryFields | None = None,
    feedback: str | None = None,
) -> str:
    """Stage 1 input in the shape the inquiry_design prompt describes."""
    material: dict[str, object] = {
        "interfaceLanguage": language,
        "teacherInput": {
            "learnerBand": age_band,
            "targetExchanges": max_turns,
            "themeContext": theme_context,
        },
        "teacherFeedback": feedback or "",
    }
    if current is not None:
        material["currentSetup"] = current.model_dump()
    return json.dumps(material, ensure_ascii=False)


def _revision_message(message: str, language: str) -> str:
    reason = message.strip()
    if language.lower().startswith("en"):
        hint = reason or "State a recognizable topic and what students should examine."
        return f"Please revise the course description. {hint}"
    hint = reason or "請說明可辨識的主題與希望學生思考的問題。"
    return f"請調整課程描述。{hint}"


async def _design(
    model_id: str,
    prompt: PromptDefinition,
    material: str,
    api_key: str,
    *,
    age_band: str | None,
    max_turns: int | None,
    language: str,
) -> tuple[GeneratedInquiry, InquiryFeedback]:
    """Run Stage 1 and return the eight fields with the model's feedback.

    The teacher's age band and turn cap win over the model's copy of them.

    Raises:
        HTTPException: 422 when the model asks for a revised description; 502 when
            the output breaks the Stage 1 contract; 503 when a key field is a
            placeholder; 502, 503, or 504 when the model call fails.
    """
    result = _validated(
        await _design_json(model_id, prompt, material, api_key), DesignOutput
    )
    if result.input_check.status == "needs_revision":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_revision_message(result.input_check.message, language),
        )
    design = result.design
    if design is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Inquiry generation failed",
        )
    brief = design.brief
    generated = _validated(
        {
            "age_band": age_band or brief.learner_band,
            "max_turns": max_turns or brief.target_exchanges,
            "topic": brief.theme,
            "core_question": brief.inquiry_question,
            "inquiry_focus": brief.inquiry_focus,
            "background_info": brief.necessary_context,
            "exclusions": brief.exclusions,
            "opening_message": brief.opening_message,
        },
        GeneratedInquiry,
    )
    _check_complete(generated)
    warnings = list(dict.fromkeys([*design.warnings, *_setup_warnings(generated)]))
    return generated, InquiryFeedback(
        assessments=design.assessments,
        clarification_questions=design.clarification_questions,
        suggestions=design.suggestions,
        warnings=warnings,
    )


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
    topic = await get_instructed_topic(db, teacher, topic_id, allow_ta=True)
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
    issue = topic_issue(payload.course_description)
    if issue is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=topic_issue_message(issue, len(payload.course_description.strip())),
        )
    language = payload.content_language or settings.DEFAULT_LANGUAGE_CODE
    model_id = payload.model_id or await effective_default_model(db, course.created_by)
    if payload.model_id is not None:
        await _require_catalog_model(db, model_id)
    api_key = await openrouter_api_key(db, course.created_by)
    prompt = prompt_for(PromptStage.INQUIRY_DESIGN)
    generated, feedback = await _design(
        model_id,
        prompt,
        _design_material(
            language=language,
            age_band=payload.age_band,
            max_turns=payload.max_turns,
            theme_context=payload.course_description,
        ),
        api_key,
        age_band=payload.age_band,
        max_turns=payload.max_turns,
        language=language,
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
        await topic_crud.record_inquiry_change(
            db,
            topic,
            prompt_stage=prompt.stage.value,
            prompt_version=prompt.version,
            force=True,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return CreatedInquiryResponse.model_validate(
        {**_response(topic).model_dump(), **feedback.model_dump()}
    )


def _check_complete(generated: GeneratedInquiry) -> None:
    """Refuse output whose substantive fields are placeholders, not content."""
    for value in (generated.topic, generated.core_question, generated.inquiry_focus):
        text = value.strip()
        if not text or _PLACEHOLDER.match(text):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Inquiry generation was incomplete. "
                    "Refine the course description and try again."
                ),
            )


def _setup_warnings(generated: GeneratedInquiry) -> list[str]:
    unspecified = not generated.background_info.strip() or bool(
        _PLACEHOLDER.match(generated.background_info.strip())
    )
    unspecified = (
        unspecified
        or not generated.exclusions.strip()
        or bool(_PLACEHOLDER.match(generated.exclusions.strip()))
    )
    return [_SETUP_WARNING] if unspecified else []


async def _require_catalog_model(db: AsyncSession, model_id: str) -> None:
    if await inquiry_model_crud.get_inquiry_model(db, model_id) is None:
        raise HTTPException(status_code=422, detail="Invalid model id")


async def _apply_selection(
    db: AsyncSession, topic: Topic, payload: SaveInquiryRequest
) -> None:
    # Called after the setup row lock. Omitted selections preserve stored values.
    if payload.model_id is not None:
        await _require_catalog_model(db, payload.model_id)
        topic.model_id = payload.model_id
    if payload.content_language is not None:
        topic.content_language = payload.content_language


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
    topic = await get_instructed_topic(db, teacher, topic_id, allow_ta=True)
    try:
        topic = await _locked_setup(db, topic.id)
        await _apply_selection(db, topic, payload)
        topic = await _store_setup(db, topic, payload.setup)
        prompt = prompt_for(PromptStage.INQUIRY_DESIGN)
        await topic_crud.record_inquiry_change(
            db,
            topic,
            prompt_stage=prompt.stage.value,
            prompt_version=prompt.version,
        )
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
        await _apply_selection(db, topic, payload)
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
        prompt = prompt_for(PromptStage.INQUIRY_DESIGN)
        await topic_crud.record_inquiry_change(
            db,
            topic,
            prompt_stage=prompt.stage.value,
            prompt_version=prompt.version,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _written(topic, "Inquiry published")


async def generate_inquiry(
    db: AsyncSession,
    teacher: User,
    topic_id: UUID,
    payload: GenerateInquiryRequest,
) -> InquirySetupResponse:
    """Suggest eight fields. The saved topic is left unchanged.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup; 422 if the model is not in the
            catalog; 502 or 503 if the model call fails.
    """
    topic = await get_instructed_topic(db, teacher, topic_id, allow_ta=True)
    await _require_setup(topic)
    catalog = await inquiry_model_crud.get_inquiry_model(db, payload.model_id)
    if catalog is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid model id",
        )
    api_key = await course_api_key(db, topic.course_id)
    prompt = prompt_for(PromptStage.INQUIRY_DESIGN)
    await db.commit()
    generated, feedback = await _design(
        catalog.model_id,
        prompt,
        _design_material(
            language=payload.content_language,
            age_band=payload.age_band,
            max_turns=payload.max_turns,
            theme_context=payload.course_description,
        ),
        api_key,
        age_band=payload.age_band,
        max_turns=payload.max_turns,
        language=payload.content_language,
    )
    return _suggestion(
        topic, generated, catalog.model_id, feedback, payload.content_language
    )


async def refine_inquiry(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: RefineInquiryRequest
) -> InquirySetupResponse:
    """Suggest eight fields from the screen and the feedback. Nothing is saved.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup; 502 or 503 if the model call fails.
    """
    topic = await get_instructed_topic(db, teacher, topic_id, allow_ta=True)
    await _require_setup(topic)
    model_id = topic.model_id or settings.OPENAI_MODEL
    language = topic.content_language or settings.DEFAULT_LANGUAGE_CODE
    api_key = await course_api_key(db, topic.course_id)
    prompt = prompt_for(PromptStage.INQUIRY_DESIGN)
    await db.commit()
    generated, feedback = await _design(
        model_id,
        prompt,
        _design_material(
            language=language,
            age_band=payload.setup.age_band,
            max_turns=payload.setup.max_turns,
            theme_context=payload.setup.topic or "",
            current=payload.setup,
            feedback=payload.feedback,
        ),
        api_key,
        age_band=payload.setup.age_band,
        max_turns=payload.setup.max_turns,
        language=language,
    )
    return _suggestion(topic, generated, topic.model_id, feedback, language)


async def opening_message(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: OpeningMessageRequest
) -> OpeningMessageResponse:
    """Draft an opening line from the supplied setup and store it.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor;
            400 if the topic is not in setup; 502 or 503 if the model call fails.
    """
    topic = await get_instructed_topic(db, teacher, topic_id, allow_ta=True)
    await _require_setup(topic)
    seen_at = topic.updated_at
    topic_id = topic.id
    model_id = topic.model_id or settings.OPENAI_MODEL
    draft = payload.setup
    api_key = await course_api_key(db, topic.course_id)
    prompt = prompt_for(PromptStage.OPENING)
    await db.commit()
    raw = await _model_json(
        model_id,
        prompt,
        (
            f"content_language: {topic.content_language or settings.DEFAULT_LANGUAGE_CODE}\n"
            f"age_band: {draft.age_band}\n"
            f"max_turns: {draft.max_turns}\n"
            f"topic: {draft.topic}\n"
            f"core_question: {draft.core_question}\n"
            f"inquiry_focus: {draft.inquiry_focus}\n"
            f"background_info: {draft.background_info}\n"
            f"exclusions: {draft.exclusions}\n"
            f"opening_message: {draft.opening_message}"
        ),
        api_key,
    )
    generated = _validated(raw, OpeningMessageDraft)
    try:
        topic = await _locked_setup(db, topic_id)
        _reject_if_stale(topic, seen_at)
        topic.opening_message = generated.opening_message or None
        await topic_crud.record_inquiry_change(
            db,
            topic,
            prompt_stage=prompt.stage.value,
            prompt_version=prompt.version,
            force=True,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return OpeningMessageResponse(opening_message=generated.opening_message)
