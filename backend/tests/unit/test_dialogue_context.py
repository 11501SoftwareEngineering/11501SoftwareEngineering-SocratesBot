from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import Settings, settings
from app.core.prompts import PromptStage, prompt_for
from app.models.message import DialogueMessage
from app.models.topic import Topic
from app.services.dialogue_context import (
    ContextWindowExceeded,
    DialogueContextCheckpoint,
    DialogueContextPrompts,
    build_bounded_context,
)
from app.services.model_client import ModelCallError
from app.services.token_budget import (
    UnsupportedModelTokenizerError,
    estimate_total_request_tokens,
)

pytestmark = pytest.mark.anyio

MODEL_ID = "openai/gpt-4o-mini"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class SummaryClient:
    def __init__(self) -> None:
        self.summary_inputs: list[str] = []

    async def complete_object(self, **kwargs):
        self.summary_inputs.append(kwargs["material"])
        return {"summary": "Student weighed access against public cost."}

    async def complete_reply(self, **kwargs):
        return "What evidence would help compare those effects?", False


def _topic() -> Topic:
    return Topic(
        id=uuid4(),
        course_id=uuid4(),
        created_by=uuid4(),
        title="Course",
        content_language="en",
        inquiry_topic="Public transit",
        core_question="Should transit be free?",
        inquiry_focus="Compare access and public cost",
        exclusions="unspecified",
    )


def _history(turns: int) -> list[DialogueMessage]:
    now = datetime.now(UTC)
    session_id = uuid4()
    result = []
    for turn in range(turns):
        result.extend(
            [
                DialogueMessage(
                    id=uuid4(),
                    session_id=session_id,
                    sender="student",
                    content=f"reason-{turn}: " + "access evidence " * 140,
                    created_at=now,
                ),
                DialogueMessage(
                    id=uuid4(),
                    session_id=session_id,
                    sender="ai",
                    content=f"followup-{turn}: " + "what supports this " * 140,
                    created_at=now,
                ),
            ]
        )
    return result


async def test_old_complete_turns_are_summarized_and_latest_input_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", 3_000)
    client = SummaryClient()
    topic = _topic()
    messages = _history(10)
    reply_prompt = prompt_for(PromptStage.DIALOGUE)
    summary_prompt = prompt_for(PromptStage.DIALOGUE_CONTEXT_SUMMARY)
    checkpoint = DialogueContextCheckpoint(
        summary=None,
        summarized_message_count=0,
        prompt_stage=None,
        prompt_version=None,
    )
    prompts = DialogueContextPrompts(
        reply=reply_prompt,
        summary=summary_prompt,
    )

    context = await build_bounded_context(
        client=client,
        topic=topic,
        messages=messages,
        latest="I want to compare who benefits with who pays.",
        checkpoint=checkpoint,
        model_id=MODEL_ID,
        prompts=prompts,
    )

    assert client.summary_inputs
    assert context.summarized_message_count > 0
    assert context.summary == "Student weighed access against public cost."
    assert context.summary_prompt_stage == PromptStage.DIALOGUE_CONTEXT_SUMMARY.value
    assert context.summary_prompt_version == summary_prompt.version
    assert "earlier_context_summary:" in context.material
    assert "I want to compare who benefits with who pays." in context.material
    assert "reason-9:" in context.material
    assert "reason-0:" not in context.material
    assert str(topic.id) not in client.summary_inputs[0]
    assert str(topic.created_by) not in client.summary_inputs[0]
    assert str(messages[0].session_id) not in client.summary_inputs[0]


async def test_oversized_latest_message_is_rejected_before_summary_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", 3_000)
    client = SummaryClient()

    with pytest.raises(ContextWindowExceeded, match="Latest message"):
        await build_bounded_context(
            client=client,
            topic=_topic(),
            messages=_history(10),
            latest="oversized " * 30_000,
            checkpoint=DialogueContextCheckpoint(
                summary=None,
                summarized_message_count=0,
                prompt_stage=None,
                prompt_version=None,
            ),
            model_id=MODEL_ID,
            prompts=DialogueContextPrompts(
                reply=prompt_for(PromptStage.DIALOGUE),
                summary=prompt_for(PromptStage.DIALOGUE_CONTEXT_SUMMARY),
            ),
        )

    assert client.summary_inputs == []


def test_unknown_model_fails_closed_before_any_estimate() -> None:
    with pytest.raises(UnsupportedModelTokenizerError):
        estimate_total_request_tokens(
            model_id="provider/unmapped-model",
            instructions="instructions",
            material="material",
            schema={"type": "object"},
            output_tokens=100,
        )


async def test_invalid_summary_output_is_a_model_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", 3_000)

    class InvalidSummaryClient(SummaryClient):
        async def complete_object(self, **kwargs):
            self.summary_inputs.append(kwargs["material"])
            return {"summary": "  "}

    client = InvalidSummaryClient()
    with pytest.raises(ModelCallError):
        await build_bounded_context(
            client=client,
            topic=_topic(),
            messages=_history(10),
            latest="Compare who benefits and who pays.",
            checkpoint=DialogueContextCheckpoint(
                summary=None,
                summarized_message_count=0,
                prompt_stage=None,
                prompt_version=None,
            ),
            model_id=MODEL_ID,
            prompts=DialogueContextPrompts(
                reply=prompt_for(PromptStage.DIALOGUE),
                summary=prompt_for(PromptStage.DIALOGUE_CONTEXT_SUMMARY),
            ),
        )


async def test_default_model_builds_the_full_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_model = Settings.model_fields["OPENAI_MODEL"].default
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", 3_000)
    client = SummaryClient()

    context = await build_bounded_context(
        client=client,
        topic=_topic(),
        messages=_history(10),
        latest="I want to compare who benefits with who pays.",
        checkpoint=DialogueContextCheckpoint(
            summary=None,
            summarized_message_count=0,
            prompt_stage=None,
            prompt_version=None,
        ),
        model_id=default_model,
        prompts=DialogueContextPrompts(
            reply=prompt_for(PromptStage.DIALOGUE),
            summary=prompt_for(PromptStage.DIALOGUE_CONTEXT_SUMMARY),
        ),
    )

    assert default_model == "openai/gpt-6-luna"
    assert client.summary_inputs
    assert "compare who benefits" in context.material


async def test_summary_call_sends_the_course_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", 3_000)
    keys: list[str | None] = []

    class KeyedClient(SummaryClient):
        async def complete_object(self, **kwargs):
            keys.append(kwargs.get("api_key"))
            return await super().complete_object(**kwargs)

    await build_bounded_context(
        client=KeyedClient(),
        topic=_topic(),
        messages=_history(10),
        latest="Compare who benefits and who pays.",
        checkpoint=DialogueContextCheckpoint(
            summary=None,
            summarized_message_count=0,
            prompt_stage=None,
            prompt_version=None,
        ),
        model_id=MODEL_ID,
        prompts=DialogueContextPrompts(
            reply=prompt_for(PromptStage.DIALOGUE),
            summary=prompt_for(PromptStage.DIALOGUE_CONTEXT_SUMMARY),
        ),
        api_key="sk-or-course-teacher",
    )

    assert keys
    assert set(keys) == {"sk-or-course-teacher"}
