"""Token-bounded dialogue context with a rolling summary checkpoint."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.prompts import PromptDefinition
from app.models.message import DialogueMessage
from app.models.topic import Topic
from app.services.dialogue_turn import PLANNING_SCHEMA, planning_material
from app.services.model_client import (
    CONTEXT_SUMMARY_SCHEMA,
    ModelCallError,
    ModelClient,
)
from app.services.token_budget import (
    ContextWindowExceeded,
    UnsupportedModelTokenizerError,
    estimate_total_request_tokens,
)


@dataclass(frozen=True)
class BoundedDialogueContext:
    material: str
    summary: str | None
    summarized_message_count: int
    summary_prompt_stage: str | None
    summary_prompt_version: str | None


@dataclass(frozen=True)
class DialogueContextCheckpoint:
    summary: str | None
    summarized_message_count: int
    prompt_stage: str | None
    prompt_version: str | None


@dataclass(frozen=True)
class DialogueContextPrompts:
    reply: PromptDefinition
    summary: PromptDefinition


def reply_material(
    topic: Topic,
    messages: list[DialogueMessage],
    latest: str | None = None,
    *,
    summary: str | None = None,
) -> str:
    lines = [
        f"topic: {topic.inquiry_topic or ''}",
        f"core_question: {topic.core_question or ''}",
        f"inquiry_focus: {topic.inquiry_focus or ''}",
        f"background_info: {topic.background_info or ''}",
        f"exclusions: {topic.exclusions or 'unspecified'}",
        f"content_language: {topic.content_language or ''}",
        f"age_band: {topic.age_band or ''}",
    ]
    if summary:
        lines.append(f"earlier_context_summary: {summary}")
    opening = (topic.opening_message or "").strip()
    if opening and not _opening_prefix(topic, messages):
        lines.append(f"ai: {opening}")
    lines.extend(f"{message.sender}: {message.content}" for message in messages)
    if latest is not None:
        lines.append(f"student: {latest}")
    return "\n".join(lines)


def _opening_prefix(
    topic: Topic, messages: list[DialogueMessage]
) -> list[DialogueMessage]:
    opening = (topic.opening_message or "").strip()
    if (
        opening
        and messages
        and messages[0].sender == "ai"
        and messages[0].content == opening
    ):
        return messages[:1]
    return []


def _complete_turns(
    messages: list[DialogueMessage], start: int
) -> list[tuple[int, int]]:
    turns: list[tuple[int, int]] = []
    index = start
    while index + 1 < len(messages):
        if messages[index].sender != "student" or messages[index + 1].sender != "ai":
            break
        turns.append((index, index + 2))
        index += 2
    return turns


def _summary_material(
    topic: Topic,
    previous_summary: str | None,
    messages: list[DialogueMessage],
    turns: list[tuple[int, int]],
) -> str:
    lines = [
        f"topic: {topic.inquiry_topic or ''}",
        f"core_question: {topic.core_question or ''}",
        f"inquiry_focus: {topic.inquiry_focus or ''}",
    ]
    if previous_summary:
        lines.append(f"summary_so_far: {previous_summary}")
    lines.append("older_dialogue:")
    for start, end in turns:
        lines.extend(
            f"{messages[index].sender}: {messages[index].content}"
            for index in range(start, end)
        )
    return "\n".join(lines)


def _fits(
    *,
    model_id: str,
    prompt: PromptDefinition,
    material: str,
    schema: dict,
    budget: int,
) -> bool:
    estimate = estimate_total_request_tokens(
        model_id=model_id,
        instructions=prompt.instructions,
        material=material,
        schema=schema,
        output_tokens=prompt.max_output_tokens,
    )
    return estimate <= budget


async def build_bounded_context(
    *,
    client: ModelClient,
    topic: Topic,
    messages: list[DialogueMessage],
    latest: str,
    checkpoint: DialogueContextCheckpoint,
    model_id: str,
    prompts: DialogueContextPrompts,
) -> BoundedDialogueContext:
    """Compact complete older turns until the request, schema, and output reserve fit."""
    budget = settings.DIALOGUE_CONTEXT_TOKEN_BUDGET
    if (
        checkpoint.summarized_message_count < 0
        or checkpoint.summarized_message_count > len(messages)
    ):
        raise ContextWindowExceeded("Dialogue summary cursor is invalid")

    prefix = _opening_prefix(topic, messages)
    cursor = checkpoint.summarized_message_count
    current_summary = checkpoint.summary
    current_stage = checkpoint.prompt_stage
    current_version = checkpoint.prompt_version
    start = max(cursor, len(prefix))

    fixed_material = reply_material(topic, prefix, latest, summary=current_summary)
    if not _fits(
        model_id=model_id,
        prompt=prompts.reply,
        material=planning_material(topic, fixed_material),
        schema=PLANNING_SCHEMA,
        budget=budget,
    ):
        raise ContextWindowExceeded(
            "Latest message exceeds the dialogue context budget"
        )

    while True:
        material = reply_material(
            topic,
            [*prefix, *messages[start:]],
            latest,
            summary=current_summary,
        )
        if _fits(
            model_id=model_id,
            prompt=prompts.reply,
            material=planning_material(topic, material),
            schema=PLANNING_SCHEMA,
            budget=budget,
        ):
            return BoundedDialogueContext(
                material=material,
                summary=current_summary,
                summarized_message_count=cursor,
                summary_prompt_stage=current_stage,
                summary_prompt_version=current_version,
            )

        turns = _complete_turns(messages, start)
        if len(turns) <= 1:
            raise ContextWindowExceeded("Recent dialogue exceeds the context budget")

        # Keep at least the newest complete turn verbatim. Summarize the largest
        # oldest batch that fits the summary request's own token budget.
        candidates = turns[:-1]
        selected: list[tuple[int, int]] = []
        for turn in candidates:
            proposed = [*selected, turn]
            summary_material = _summary_material(
                topic, current_summary, messages, proposed
            )
            if not _fits(
                model_id=model_id,
                prompt=prompts.summary,
                material=summary_material,
                schema=CONTEXT_SUMMARY_SCHEMA,
                budget=budget,
            ):
                break
            selected = proposed
        if not selected:
            raise ContextWindowExceeded(
                "An older dialogue turn exceeds the summary budget"
            )

        summary_material = _summary_material(topic, current_summary, messages, selected)
        result = await client.complete_object(
            name="dialogue_context_summary",
            schema=CONTEXT_SUMMARY_SCHEMA,
            instructions=prompts.summary.instructions,
            material=summary_material,
            model=model_id,
            max_tokens=prompts.summary.max_output_tokens,
        )
        summary = result.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ModelCallError(200)
        current_summary = summary.strip()
        cursor = selected[-1][1]
        start = cursor
        current_stage = prompts.summary.stage.value
        current_version = prompts.summary.version


__all__ = [
    "BoundedDialogueContext",
    "ContextWindowExceeded",
    "DialogueContextCheckpoint",
    "DialogueContextPrompts",
    "UnsupportedModelTokenizerError",
    "build_bounded_context",
    "reply_material",
]
