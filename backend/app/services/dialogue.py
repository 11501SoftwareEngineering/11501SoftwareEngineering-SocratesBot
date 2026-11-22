"""One dialogue: history, a waiting reply stream, and end actions."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import DialogueAction, DialogueOutcome, MessageSender, SessionStatus
from app.core.prompts import PromptStage, prompt_for
from app.crud import message as message_crud
from app.models.message import DialogueMessage
from app.models.session import Session
from app.models.topic import Topic
from app.schemas.dialogue import (
    DialogueHistoryResponse,
    DialogueMessageItem,
    EndDialogueResponse,
    StreamDone,
)
from app.services import report_runner
from app.services.dialogue_context import (
    ContextWindowExceeded,
    DialogueContextCheckpoint,
    DialogueContextPrompts,
    UnsupportedModelTokenizerError,
    build_bounded_context,
)
from app.services.dialogue_lifecycle import (
    MIN_FINISH_TURNS,
    REPORT_OUTCOMES,
    lifecycle_fields,
)
from app.services.dialogue_turn import (
    TurnPrompts,
    catch_up_progress,
    question_before,
    run_turn,
)
from app.services.model_client import ModelCallError, ModelClient
from app.services.reports import queue_ending_report
from app.services.teacher_ai_settings import course_api_key

# ponytail: one process. A second worker will not see this lock; a DB lease is the upgrade.
_BUSY: set[UUID] = set()


class ReplyRejected(Exception):
    """A reply or end action this dialogue will not accept."""

    def __init__(
        self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def guard_reply(
    *,
    stage: str,
    outcome: str,
    completed_turns: int,
    max_turns: int | None,
) -> None:
    """Reject a reply when the dialogue is closed or the turn cap is spent.

    Raises:
        ReplyRejected: the dialogue is not accepting replies, or the turn cap is reached.
    """
    if stage != "conversation" or outcome != DialogueOutcome.OPEN.value:
        raise ReplyRejected("Dialogue is not accepting replies")
    if max_turns is not None and completed_turns >= max_turns:
        raise ReplyRejected("Turn cap reached")


_End = tuple[str, str, bool, bool, str]


def _complete(goal_reached: bool) -> _End:
    if not goal_reached:
        raise ReplyRejected("Inquiry goal is not met", status.HTTP_409_CONFLICT)
    return (
        DialogueOutcome.COMPLETED.value,
        SessionStatus.COMPLETED.value,
        True,
        False,
        "Dialogue completed",
    )


def _continue(status_value: str, goal_reached: bool) -> _End:
    return (
        DialogueOutcome.OPEN.value,
        status_value,
        goal_reached,
        False,
        "Dialogue continues",
    )


def _abandon() -> _End:
    return (
        DialogueOutcome.ABANDONED.value,
        SessionStatus.IN_PROGRESS.value,
        False,
        False,
        "Dialogue abandoned",
    )


def apply_end(
    action: str,
    *,
    outcome: str,
    status_value: str,
    goal_reached: bool,
    completed_turns: int = 0,
) -> _End:
    """Return outcome, status, goal_reached, awaiting_end_consent, message."""
    if outcome != DialogueOutcome.OPEN.value:
        raise ReplyRejected("Dialogue has already ended")
    if action == DialogueAction.COMPLETE:
        return _complete(goal_reached)
    if action == DialogueAction.CONTINUE:
        return _continue(status_value, goal_reached)
    if action == DialogueAction.FINISH:
        if completed_turns < MIN_FINISH_TURNS:
            raise ReplyRejected(
                "Finish early requires three student answers", status.HTTP_409_CONFLICT
            )
        return (
            "ended",
            SessionStatus.IN_PROGRESS.value,
            goal_reached,
            False,
            "Dialogue ended early",
        )
    if action == DialogueAction.ABANDON:
        return _abandon()
    raise ReplyRejected("Unknown ending action")


def _progress_of(session: Session) -> dict | None:
    return (session.generation_meta or {}).get("progress")


def _checkpoint_of(session: Session) -> DialogueContextCheckpoint:
    context = (session.generation_meta or {}).get("context_summary") or {}
    return DialogueContextCheckpoint(
        summary=context.get("text"),
        summarized_message_count=context.get("message_count") or 0,
        prompt_stage=context.get("prompt_stage"),
        prompt_version=context.get("prompt_version"),
    )


def _turn_count(messages: list[DialogueMessage]) -> int:
    return sum(message.sender == MessageSender.STUDENT for message in messages)


def _shown(
    session: Session, topic: Topic, messages: list[DialogueMessage]
) -> list[DialogueMessage]:
    opening = (topic.opening_message or "").strip()
    if not opening:
        return messages
    if (
        messages
        and messages[0].sender == MessageSender.AI
        and messages[0].content == opening
    ):
        return messages
    when = (
        messages[0].created_at - timedelta(microseconds=1)
        if messages
        else datetime.now(UTC)
    )
    lead = DialogueMessage(
        id=uuid5(NAMESPACE_URL, f"opening:{session.id}"),
        session_id=session.id,
        sender=MessageSender.AI,
        content=opening,
        created_at=when,
    )
    return [lead, *messages]


def _history(
    session: Session,
    topic: Topic,
    messages: list[DialogueMessage],
) -> DialogueHistoryResponse:
    shown = _shown(session, topic, messages)
    return DialogueHistoryResponse(
        messages=[
            DialogueMessageItem(
                message_id=message.id,
                sender=message.sender,
                content=message.content,
                created_at=message.created_at,
            )
            for message in shown
        ],
        session_status=session.outcome,
        max_turns=topic.max_turns,
        completed_turns=_turn_count(messages),
        goal_reached=session.goal_reached,
        awaiting_end_consent=session.awaiting_end_consent,
        current_progress=_progress_of(session),
        **lifecycle_fields(session, _turn_count(messages)),
    )


def _stream(
    *,
    message_id: UUID,
    text: str,
    completed_turns: int,
    is_completed: bool,
    awaiting_end_consent: bool,
    session_status: str = "open",
    goal_reached: bool = False,
    ending_reason: str | None = None,
) -> StreamDone:
    return StreamDone(
        session_status=session_status,
        goal_reached=goal_reached,
        ending_reason=ending_reason,
        report_eligible=session_status in REPORT_OUTCOMES,
        can_finish_early=session_status == "open"
        and completed_turns >= MIN_FINISH_TURNS,
        message_id=message_id,
        text=text,
        completed_turns=completed_turns,
        is_completed=is_completed,
        awaiting_end_consent=awaiting_end_consent,
    )


def _rejected(exc: ReplyRejected) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _model_http(exc: ModelCallError) -> HTTPException:
    code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if exc.status_code in {429, 503}
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(status_code=code, detail="Model call failed")


async def _owned(
    db: AsyncSession, *, user_id: UUID, session_id: UUID
) -> tuple[Session, Topic, list[DialogueMessage]]:
    loaded = await message_crud.load_owned_dialogue(
        db, session_id=session_id, user_id=user_id
    )
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return loaded


def _hold(session_id: UUID) -> None:
    if session_id in _BUSY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another reply is in progress",
        )
    _BUSY.add(session_id)


def _saved_reply(
    messages: list[DialogueMessage],
    request_id: UUID,
) -> DialogueMessage | None:
    seen = False
    for message in messages:
        if message.request_id == request_id:
            seen = True
            continue
        if seen and message.sender == MessageSender.AI:
            return message
    return None


async def _ask_and_store(
    db: AsyncSession,
    client: ModelClient,
    *,
    session: Session,
    topic: Topic,
    messages: list[DialogueMessage],
    content: str,
    request_id: UUID,
    api_key: str | None = None,
) -> StreamDone:
    reply_prompt = prompt_for(PromptStage.DIALOGUE)
    summary_prompt = prompt_for(PromptStage.DIALOGUE_CONTEXT_SUMMARY)
    turn_prompts = TurnPrompts(
        validity=prompt_for(PromptStage.VALIDITY),
        status=prompt_for(PromptStage.STATUS),
        dialogue=reply_prompt,
    )
    model_id = topic.model_id or settings.OPENAI_MODEL
    try:
        # The loaded ORM objects remain usable because expire_on_commit is false.
        # Close the read transaction before either provider call.
        await db.commit()
        bounded = await build_bounded_context(
            client=client,
            topic=topic,
            messages=messages,
            latest=content,
            checkpoint=_checkpoint_of(session),
            model_id=model_id,
            prompts=DialogueContextPrompts(
                reply=reply_prompt,
                summary=summary_prompt,
            ),
            api_key=api_key,
        )
        previous_progress = _progress_of(session)
        if previous_progress is None and _turn_count(messages) > 0:
            previous_progress = await catch_up_progress(
                client,
                prompt=turn_prompts.status,
                topic=topic,
                messages=messages,
                model_id=model_id,
                api_key=api_key,
            )
        turn = await run_turn(
            client,
            prompts=turn_prompts,
            topic=topic,
            question=question_before(messages, topic.core_question or ""),
            latest=content,
            transcript_material=bounded.material,
            previous_progress=previous_progress,
            exchange=_turn_count(messages) + 1,
            model_id=model_id,
            validity_model=model_id,
            api_key=api_key,
        )
        text, goal_reached = turn.reply, turn.goal_reached
        locked = await message_crud.lock_session(db, session.id)
        if locked is None or locked.outcome != DialogueOutcome.OPEN.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dialogue is not accepting replies",
            )
        current_message_count = await message_crud.count_messages(db, session.id)
        if current_message_count != len(messages) or _checkpoint_of(
            locked
        ) != _checkpoint_of(session):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dialogue changed while replying",
            )
        if topic.max_turns is not None:
            turns = await message_crud.count_student_turns(db, session.id)
            if turns >= topic.max_turns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Turn cap reached",
                )
        goal_reached = bool(locked.goal_reached or goal_reached)
        await message_crud.merge_session_meta(
            db,
            session.id,
            context_summary={
                "text": bounded.summary,
                "message_count": bounded.summarized_message_count,
                "prompt_stage": bounded.summary_prompt_stage,
                "prompt_version": bounded.summary_prompt_version,
            },
        )
        message_id = await message_crud.save_exchange(
            db,
            session_id=session.id,
            content=content,
            request_id=request_id,
            reply=text,
            goal_reached=goal_reached,
            prompt_stage=reply_prompt.stage.value,
            prompt_version=reply_prompt.version,
            analysis={
                "move": turn.move,
                "status": turn.status,
                "safetyLevel": turn.safety_level,
                "promptVersions": turn.prompt_versions,
                "model_id": model_id,
            },
            progress=turn.progress,
        )
        cap_reached = (
            topic.max_turns is not None and _turn_count(messages) + 1 >= topic.max_turns
        )
        pending = None
        if cap_reached:
            await message_crud.save_end(
                db,
                session_id=session.id,
                outcome="ended",
                status=SessionStatus.IN_PROGRESS.value,
                goal_reached=goal_reached,
                awaiting_end_consent=False,
                ending_reason="turn_limit",
            )
            pending = await queue_ending_report(db, session.id, turn.progress)
        await db.commit()
        if pending is not None:
            report_runner.schedule(pending.id)
    except ContextWindowExceeded as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except UnsupportedModelTokenizerError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured model tokenizer is not supported",
        ) from exc
    except ModelCallError as exc:
        await db.rollback()
        raise _model_http(exc) from exc
    except Exception:
        await db.rollback()
        raise
    return _stream(
        message_id=message_id,
        text=text,
        completed_turns=_turn_count(messages) + 1,
        is_completed=False,
        awaiting_end_consent=goal_reached and not cap_reached,
        session_status="ended" if cap_reached else "open",
        goal_reached=goal_reached,
        ending_reason="turn_limit" if cap_reached else None,
    )


async def read_history(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
) -> DialogueHistoryResponse:
    """Return one student's own dialogue.

    Raises:
        HTTPException: 404 if the session is missing or belongs to someone else.
    """
    session, topic, messages = await _owned(db, user_id=user_id, session_id=session_id)
    return _history(session, topic, messages)


async def send_reply(
    db: AsyncSession,
    client: ModelClient,
    *,
    user_id: UUID,
    session_id: UUID,
    content: str,
    request_id: UUID,
) -> StreamDone:
    """Store one student turn and return the model reply.

    Raises:
        HTTPException: 404 if the session is missing; 400 if replies are closed
            or the turn cap is spent; 409 if another reply is in progress;
            502 or 503 if the model call fails.
    """
    session, topic, messages = await _owned(db, user_id=user_id, session_id=session_id)
    saved = _saved_reply(messages, request_id)
    if saved is not None:
        return _stream(
            message_id=saved.id,
            text=saved.content,
            completed_turns=_turn_count(messages),
            is_completed=session.outcome == DialogueOutcome.COMPLETED.value,
            awaiting_end_consent=session.awaiting_end_consent,
            session_status=session.outcome,
            goal_reached=session.goal_reached,
            ending_reason=getattr(session, "ending_reason", None),
        )
    try:
        guard_reply(
            stage=topic.stage,
            outcome=session.outcome,
            completed_turns=_turn_count(messages),
            max_turns=topic.max_turns,
        )
    except ReplyRejected as exc:
        raise _rejected(exc) from exc
    api_key = await course_api_key(db, topic.course_id)
    _hold(session_id)
    try:
        return await _ask_and_store(
            db,
            client,
            session=session,
            topic=topic,
            messages=messages,
            content=content,
            request_id=request_id,
            api_key=api_key,
        )
    finally:
        _BUSY.discard(session_id)


async def end_dialogue(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    action: str,
) -> EndDialogueResponse:
    """Complete, finish early, continue, or abandon this student's dialogue.

    Raises:
        HTTPException: 404 if missing; 409 for a conflicting ending, an unmet
            complete/finish prerequisite, or an in-process reply.
    """
    await _owned(db, user_id=user_id, session_id=session_id)
    if session_id in _BUSY:
        raise HTTPException(status_code=409, detail="Another reply is in progress")
    # The same row lock as reply persistence makes the cutoff stable across workers.
    session = await message_crud.lock_session(db, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    turns = await message_crud.count_student_turns(db, session_id)
    same_end = (
        (action == "complete" and session.outcome == "completed")
        or (action == "finish" and session.outcome == "ended")
        or (action == "abandon" and session.outcome == "abandoned")
    )
    if session.outcome != "open":
        if not same_end:
            raise HTTPException(status_code=409, detail="Dialogue has already ended")
        return EndDialogueResponse(
            session_id=session_id,
            session_status=session.outcome,
            message="Dialogue has already ended",
            goal_reached=session.goal_reached,
            **lifecycle_fields(session, turns),
        )
    try:
        outcome, status_value, goal_reached, awaiting, message = apply_end(
            action,
            outcome=session.outcome,
            status_value=session.status,
            goal_reached=session.goal_reached,
            completed_turns=turns,
        )
    except ReplyRejected as exc:
        raise _rejected(exc) from exc
    reason = {"complete": "goal_reached", "finish": "student_requested_stop"}.get(
        action
    )
    await message_crud.save_end(
        db,
        session_id=session_id,
        outcome=outcome,
        status=status_value,
        goal_reached=goal_reached,
        awaiting_end_consent=awaiting,
        ending_reason=reason,
    )
    pending = None
    if outcome in REPORT_OUTCOMES:
        pending = await queue_ending_report(db, session_id, _progress_of(session))
    await db.commit()
    if pending is not None:
        report_runner.schedule(pending.id)
    return EndDialogueResponse(
        session_id=session_id,
        session_status=outcome,
        message=message,
        goal_reached=goal_reached,
        report_eligible=outcome in REPORT_OUTCOMES,
        ending_reason=reason,
        can_finish_early=outcome == "open" and turns >= MIN_FINISH_TURNS,
    )
