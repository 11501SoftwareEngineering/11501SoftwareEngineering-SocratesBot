from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.enums import MessageSender
from app.core.prompts import PromptStage, prompt_for
from app.models.message import DialogueMessage
from app.services.dialogue_progress import empty_progress
from app.services.dialogue_turn import (
    TurnPrompts,
    catch_up_progress,
    run_turn,
    unrelated_reply,
)
from app.services.model_client import ModelCallError

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class ScriptedClient:
    """Returns one scripted object per call, in order, and records the call names."""

    def __init__(self, *responses: dict) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    async def complete_object(self, *, name: str, **_: Any) -> dict:
        self.calls.append(name)
        return self._responses.pop(0)


def _ready_progress() -> dict:
    progress = empty_progress()
    progress["position"] = {"met": True, "evidenceExchange": 1, "summary": "s"}
    progress["reason"] = {"met": True, "evidenceExchange": 1, "summary": "s"}
    progress["examination"] = {"met": True, "evidenceExchange": 2, "summary": "s"}
    progress["response"] = {"met": True, "evidenceExchange": 3, "summary": "s"}
    return progress


def _status(status: str = "ready") -> dict:
    return {"progress": _ready_progress(), "status": status, "safetyLevel": "normal"}


VALIDITY_YES = {"thinkingProgress": "on topic", "validity": "YES"}
VALIDITY_NO = {"thinkingProgress": "off topic", "validity": "NO"}
PLANNING = {"method": "present_counterexample", "content": "Consider a case where..."}


def _topic() -> SimpleNamespace:
    return SimpleNamespace(
        content_language="en",
        age_band="16-18",
        max_turns=10,
        inquiry_topic="Who should decide",
        core_question="Should the teacher decide?",
        inquiry_focus="reasons",
        background_info=None,
        exclusions=None,
        opening_message=None,
    )


def _prompts() -> TurnPrompts:
    return TurnPrompts(
        validity=prompt_for(PromptStage.VALIDITY),
        status=prompt_for(PromptStage.STATUS),
        dialogue=prompt_for(PromptStage.DIALOGUE),
    )


async def _run(client: ScriptedClient, exchange: int = 3):
    return await run_turn(
        client,
        prompts=_prompts(),
        topic=_topic(),
        question="Why?",
        latest="Because it is fair.",
        transcript_material="transcript",
        previous_progress=None,
        exchange=exchange,
        model_id="openai/gpt-6-luna",
        validity_model="openai/gpt-6-luna",
    )


async def test_off_topic_answer_stops_at_the_validity_gate() -> None:
    client = ScriptedClient(VALIDITY_NO)

    turn = await _run(client)

    assert client.calls == ["dialogue_validity"]
    assert turn.reply == unrelated_reply("en")
    assert turn.goal_reached is False


async def test_on_topic_answer_runs_all_three_stages() -> None:
    client = ScriptedClient(VALIDITY_YES, _status(), PLANNING)

    turn = await _run(client)

    assert client.calls == ["dialogue_validity", "dialogue_status", "dialogue_planning"]
    assert turn.reply == PLANNING["content"]
    assert set(turn.prompt_versions) == {"validity", "status", "dialogue"}


@pytest.mark.parametrize(
    ("exchange", "status", "expected"),
    [
        (3, "ready", True),  # structure and model agree
        (2, "ready", False),  # too early, whatever the model says
        (3, "continue", False),  # structure is met but the model is not ready
    ],
)
async def test_goal_needs_both_structure_and_the_model(
    exchange: int, status: str, expected: bool
) -> None:
    client = ScriptedClient(VALIDITY_YES, _status(status), PLANNING)

    turn = await _run(client, exchange=exchange)

    assert turn.goal_reached is expected


async def test_malformed_status_is_a_model_failure() -> None:
    client = ScriptedClient(VALIDITY_YES, {"status": "ready"}, PLANNING)

    with pytest.raises(ModelCallError):
        await _run(client)


async def test_legacy_session_catches_up_with_one_status_call() -> None:
    client = ScriptedClient(_status())
    messages = [
        DialogueMessage(sender=MessageSender.AI, content="Why?"),
        DialogueMessage(sender=MessageSender.STUDENT, content="Fair."),
    ]

    progress = await catch_up_progress(
        client,
        prompt=prompt_for(PromptStage.STATUS),
        topic=_topic(),
        messages=messages,
        model_id="openai/gpt-6-luna",
    )

    assert client.calls == ["dialogue_status"]
    assert progress["response"]["met"] is True
