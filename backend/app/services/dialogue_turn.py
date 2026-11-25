"""One Stage 2 student turn: validity gate, progress, then the visible reply.

A turn makes up to three model calls:

1. validity: off_topic, no_reason, or valid. Off-topic ends the turn with a
   localized explanation and makes no further turn calls.
2. no_reason: ask for a reason and return, without progress analysis.
3. valid: status analysis followed by the ordinary planning reply.

Readiness is decided by the server from the progress snapshot, not by the model.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from app.core.config import settings
from app.core.enums import MessageSender
from app.core.prompts import PromptDefinition
from app.models.message import DialogueMessage
from app.models.topic import Topic
from app.services import ai_diagnostics
from app.services.dialogue_progress import (
    defer_unordered_response,
    empty_progress,
    reset_milestones,
    validate_progress,
)
from app.services.model_client import ModelCallError, ModelClient
from app.services.token_budget import (
    ContextWindowExceeded,
    estimate_total_request_tokens,
)

_QUESTION_MARKS = ("?", "\uff1f")
_MESSAGES_PATH = Path(__file__).resolve().parents[1] / "core" / "dialogue_messages.toml"
_MESSAGES: dict[str, dict[str, str]] = tomllib.loads(
    _MESSAGES_PATH.read_text(encoding="utf-8")
)

MOVES = (
    "present_counterexample",
    "change_one_condition",
)
STATUSES = (
    "continue",
    "ready",
    "partial_complete",
    "student_requested_stop",
    "safety_interruption",
)
SAFETY_LEVELS = (
    "normal",
    "restricted_request",
    "safeguarding_concern",
    "urgent_risk",
)


class _Output(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )


class MilestoneOut(_Output):
    met: bool
    evidence_exchange: int | None = Field(default=None, ge=1, le=15)
    summary: str = Field(max_length=1000)


class EvidenceOut(_Output):
    text: str = Field(max_length=1000)
    evidence_exchanges: list[Annotated[int, Field(strict=True, ge=1, le=15)]] = Field(
        max_length=6
    )


class ProgressOut(_Output):
    position: MilestoneOut
    reason: MilestoneOut
    examination: MilestoneOut
    response: MilestoneOut
    current_position: str = Field(max_length=1400)
    reasoned_uncertainty: str = Field(max_length=1400)
    definitions: list[EvidenceOut] = Field(max_length=10)
    reasons: list[EvidenceOut] = Field(max_length=10)
    assumptions: list[EvidenceOut] = Field(max_length=10)
    alternatives: list[EvidenceOut] = Field(max_length=10)
    counterexamples: list[EvidenceOut] = Field(max_length=10)
    revisions_or_defences: list[EvidenceOut] = Field(max_length=10)
    unresolved_questions: list[str] = Field(max_length=10)
    focal_tension_connection: str = Field(max_length=1400)
    dialogue_movement: str = Field(max_length=1400)
    stalled_turns: int = Field(ge=0, le=15)


class StatusOut(_Output):
    progress: ProgressOut
    status: Literal[
        "continue",
        "ready",
        "partial_complete",
        "student_requested_stop",
        "safety_interruption",
    ]
    safety_level: Literal[
        "normal",
        "restricted_request",
        "safeguarding_concern",
        "urgent_risk",
    ]


class ValidityOut(_Output):
    thinking_progress: str = Field(max_length=1000)
    validity: Literal["off_topic", "no_reason", "valid"]


class AskForReasonOut(_Output):
    hint: str = Field(min_length=1, max_length=1000)


class PlanningOut(_Output):
    method: Literal["present_counterexample", "change_one_condition"]
    content: str = Field(min_length=1, max_length=1000)


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


_STRING = {"type": "string"}
_INTEGER = {"type": "integer"}
_BOOLEAN = {"type": "boolean"}


def _enum(values: tuple[str, ...]) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


_MILESTONE = _obj(
    {
        "met": _BOOLEAN,
        "evidenceExchange": {"type": ["integer", "null"]},
        "summary": _STRING,
    }
)
_EVIDENCE = _obj(
    {
        "text": _STRING,
        "evidenceExchanges": {"type": "array", "items": _INTEGER},
    }
)
_EVIDENCE_LIST = {"type": "array", "items": _EVIDENCE}
_PROGRESS = _obj(
    {
        "position": _MILESTONE,
        "reason": _MILESTONE,
        "examination": _MILESTONE,
        "response": _MILESTONE,
        "currentPosition": _STRING,
        "reasonedUncertainty": _STRING,
        "definitions": _EVIDENCE_LIST,
        "reasons": _EVIDENCE_LIST,
        "assumptions": _EVIDENCE_LIST,
        "alternatives": _EVIDENCE_LIST,
        "counterexamples": _EVIDENCE_LIST,
        "revisionsOrDefences": _EVIDENCE_LIST,
        "unresolvedQuestions": {"type": "array", "items": _STRING},
        "focalTensionConnection": _STRING,
        "dialogueMovement": _STRING,
        "stalledTurns": _INTEGER,
    }
)
VALIDITY_SCHEMA = _obj(
    {
        "thinkingProgress": _STRING,
        "validity": _enum(("off_topic", "no_reason", "valid")),
    }
)
ASK_FOR_REASON_SCHEMA = _obj({"hint": _STRING})
STATUS_SCHEMA = _obj(
    {
        "progress": _PROGRESS,
        "status": _enum(STATUSES),
        "safetyLevel": _enum(SAFETY_LEVELS),
    }
)
PLANNING_SCHEMA = _obj(
    {
        "method": _enum(MOVES),
        "content": _STRING,
    }
)


@dataclass(frozen=True)
class TurnPrompts:
    validity: PromptDefinition
    status: PromptDefinition
    dialogue: PromptDefinition
    ask_for_reason: PromptDefinition


@dataclass(frozen=True)
class TurnResult:
    reply: str
    move: str
    status: str
    safety_level: str
    progress: dict[str, Any]
    goal_reached: bool
    prompt_versions: dict[str, str]


def unrelated_reply(language: str, reason: str = "") -> str:
    table = _MESSAGES["unrelated_response"]
    reply = table.get(language, table["zh-TW"])
    # The model supplies only a student-facing explanation, not a reasoning trace.
    reason = " ".join(reason.split())[:240]
    if not reason:
        return reply
    labels = _MESSAGES["unrelated_response_reason"]
    return f"{reply}\n{labels.get(language, labels['zh-TW'])}{reason}"


def _move_of(message: DialogueMessage) -> str | None:
    return ((message.generation_meta or {}).get("analysis") or {}).get("move")


def question_before(messages: list[DialogueMessage], fallback: str) -> str:
    """The latest tutor message that asked something, or the inquiry question."""
    for message in reversed(messages):
        if message.sender != MessageSender.AI:
            continue
        if _move_of(message) in {"ask_for_reason", "unrelated_response"}:
            continue
        if any(mark in message.content for mark in _QUESTION_MARKS):
            return message.content
    return fallback


class ReasonAnswer(TypedDict):
    exchange: int
    answer: str


def previous_reason_answers(messages: list[DialogueMessage]) -> list[ReasonAnswer]:
    """Collect relevant answers waiting for reasons to the same tutor question.

    The stored move identifies a clarification; question punctuation alone cannot
    distinguish a new inquiry from a request to explain a previous answer.
    """
    answers: list[ReasonAnswer] = []
    pending: ReasonAnswer | None = None
    exchange = 0
    for message in messages:
        if message.sender == MessageSender.STUDENT:
            exchange += 1
            pending = {"exchange": exchange, "answer": message.content}
            continue
        move = _move_of(message)
        if move == "ask_for_reason" and pending is not None:
            answers.append(pending)
        elif move != "unrelated_response":
            answers.clear()
        pending = None
    return answers


def brief_of(topic: Topic) -> dict[str, Any]:
    return {
        "learnerBand": topic.age_band,
        "targetExchanges": topic.max_turns,
        "theme": topic.inquiry_topic,
        "inquiryQuestion": topic.core_question,
        "inquiryFocus": topic.inquiry_focus or "",
        "necessaryContext": topic.background_info or "",
        "exclusions": topic.exclusions or "",
        "openingMessage": topic.opening_message or "",
    }


def planning_material(topic: Topic, transcript: str) -> str:
    return json.dumps(
        {
            "approvedInquiryBrief": brief_of(topic),
            "interfaceLanguage": topic.content_language
            or settings.DEFAULT_LANGUAGE_CODE,
            "dialogueRecord": transcript,
        },
        ensure_ascii=False,
    )


async def _bounded_object(client: ModelClient, **kwargs) -> dict:
    estimate = estimate_total_request_tokens(
        model_id=kwargs["model"],
        instructions=kwargs["instructions"],
        material=kwargs["material"],
        schema=kwargs["schema"],
        output_tokens=kwargs["max_tokens"],
    )
    if estimate > settings.DIALOGUE_CONTEXT_TOKEN_BUDGET:
        raise ContextWindowExceeded(
            f"{kwargs['name']} exceeds the dialogue context budget"
        )
    return await client.complete_object(**kwargs)


def _parse[T: BaseModel](model: type[T], raw: dict[str, Any]) -> T:
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        ai_diagnostics.validation_failure(model.__name__, exc)
        raise ModelCallError(200, reason="schema_validation") from None


async def run_turn(
    client: ModelClient,
    *,
    prompts: TurnPrompts,
    topic: Topic,
    question: str,
    latest: str,
    transcript_material: str,
    previous_progress: dict[str, Any] | None,
    exchange: int,
    model_id: str,
    validity_model: str,
    api_key: str | None = None,
    previous_answers: list[ReasonAnswer] | None = None,
) -> TurnResult:
    """Run validity, status, and the appropriate reply task."""
    language = topic.content_language or settings.DEFAULT_LANGUAGE_CODE
    answer_material = {
        "interfaceLanguage": language,
        "question": question,
        "previousAnswers": previous_answers or [],
        "answer": latest,
    }
    validity_raw = await _bounded_object(
        client,
        name="dialogue_validity",
        schema=VALIDITY_SCHEMA,
        instructions=prompts.validity.instructions,
        material=json.dumps(answer_material, ensure_ascii=False),
        model=validity_model,
        max_tokens=prompts.validity.max_output_tokens,
        api_key=api_key,
    )
    validity = _parse(ValidityOut, validity_raw)
    base_progress = previous_progress or empty_progress()
    ai_diagnostics.emit(
        "validity_decision", validity=validity.validity, exchange=exchange
    )
    if validity.validity == "off_topic":
        return TurnResult(
            reply=unrelated_reply(language, validity.thinking_progress),
            move="unrelated_response",
            status="continue",
            safety_level="normal",
            progress=reset_milestones(base_progress),
            goal_reached=False,
            prompt_versions={"validity": prompts.validity.version},
        )

    if validity.validity == "no_reason":
        hint_raw = await _bounded_object(
            client,
            name="dialogue_ask_for_reason",
            schema=ASK_FOR_REASON_SCHEMA,
            instructions=prompts.ask_for_reason.instructions,
            material=json.dumps(
                {**answer_material, "learnerBand": topic.age_band}, ensure_ascii=False
            ),
            model=model_id,
            max_tokens=prompts.ask_for_reason.max_output_tokens,
            api_key=api_key,
        )
        hint = _parse(AskForReasonOut, hint_raw).hint.strip()
        if not hint:
            raise ModelCallError(200, reason="schema_validation")
        return TurnResult(
            reply=hint,
            move="ask_for_reason",
            status="continue",
            safety_level="normal",
            progress=reset_milestones(base_progress),
            goal_reached=False,
            prompt_versions={
                "validity": prompts.validity.version,
                "ask_for_reason": prompts.ask_for_reason.version,
            },
        )

    status_raw = await _bounded_object(
        client,
        name="dialogue_status",
        schema=STATUS_SCHEMA,
        instructions=prompts.status.instructions,
        material=json.dumps(
            {
                "approvedInquiryBrief": brief_of(topic),
                "interfaceLanguage": language,
                "previousProgress": base_progress,
                "currentExchange": exchange,
                "question": question,
                "previousAnswers": previous_answers or [],
                "answer": latest,
            },
            ensure_ascii=False,
        ),
        model=model_id,
        max_tokens=prompts.status.max_output_tokens,
        api_key=api_key,
    )
    status = _parse(StatusOut, status_raw)
    proposed_progress = status.progress.model_dump(by_alias=True)
    progress = defer_unordered_response(proposed_progress, exchange)
    if progress is not proposed_progress:
        ai_diagnostics.emit("response_milestone_deferred", exchange=exchange)
    check = validate_progress(progress, exchange)
    if check.issues:
        ai_diagnostics.emit(
            "evidence_validation_failed", issues=check.issues, exchange=exchange
        )
        raise ModelCallError(200, reason="invalid_progress_evidence")

    planning_raw = await _bounded_object(
        client,
        name="dialogue_planning",
        schema=PLANNING_SCHEMA,
        instructions=prompts.dialogue.instructions,
        material=planning_material(topic, transcript_material),
        model=model_id,
        max_tokens=prompts.dialogue.max_output_tokens,
        api_key=api_key,
    )
    planning = _parse(PlanningOut, planning_raw)

    check = validate_progress(progress, exchange)
    return TurnResult(
        reply=planning.content,
        move=planning.method,
        status="continue"
        if progress is not proposed_progress and status.status == "ready"
        else status.status,
        safety_level=status.safety_level,
        progress=progress,
        goal_reached=check.structurally_ready and status.status == "ready",
        prompt_versions={
            "validity": prompts.validity.version,
            "status": prompts.status.version,
            "dialogue": prompts.dialogue.version,
        },
    )


def dialogue_record(messages: list[DialogueMessage]) -> str:
    """The whole dialogue so far, with student exchange numbers."""
    lines: list[str] = []
    exchange = 0
    for message in messages:
        if message.sender == MessageSender.STUDENT:
            exchange += 1
            lines.append(f"exchange {exchange} student: {message.content}")
        else:
            lines.append(f"tutor: {message.content}")
    return "\n".join(lines)


async def catch_up_progress(
    client: ModelClient,
    *,
    prompt: PromptDefinition,
    topic: Topic,
    messages: list[DialogueMessage],
    model_id: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Build the starting progress for a session that began before progress existed.

    One status call over the whole dialogue record. It runs once per such session,
    on its first turn after this change, so older dialogues can become ready on
    the same terms as new ones.
    """
    language = topic.content_language or settings.DEFAULT_LANGUAGE_CODE
    ai_diagnostics.emit(
        "progress_catch_up_started",
        task="dialogue_status",
        call_id=None,
        model=model_id,
        completed_turns=sum(m.sender == MessageSender.STUDENT for m in messages),
    )
    raw = await _bounded_object(
        client,
        name="dialogue_status",
        schema=STATUS_SCHEMA,
        instructions=prompt.instructions,
        material=json.dumps(
            {
                "approvedInquiryBrief": brief_of(topic),
                "interfaceLanguage": language,
                "previousProgress": empty_progress(),
                "dialogueRecord": dialogue_record(messages),
            },
            ensure_ascii=False,
        ),
        model=model_id,
        max_tokens=prompt.max_output_tokens,
        api_key=api_key,
    )
    proposed_progress = _parse(StatusOut, raw).progress.model_dump(by_alias=True)
    exchanges = sum(message.sender == MessageSender.STUDENT for message in messages)
    progress = defer_unordered_response(proposed_progress, exchanges)
    if progress is not proposed_progress:
        ai_diagnostics.emit(
            "response_milestone_deferred", exchange=exchanges, phase="legacy_catch_up"
        )
    if validate_progress(progress, exchanges).issues:
        ai_diagnostics.emit(
            "evidence_validation_failed", exchange=exchanges, phase="legacy_catch_up"
        )
        raise ModelCallError(200, reason="invalid_progress_evidence")
    return progress
