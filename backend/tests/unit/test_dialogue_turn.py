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
        DialogueMessage(sender=MessageSender.AI, content="What about exceptions?"),
        DialogueMessage(
            sender=MessageSender.STUDENT, content="There may be exceptions."
        ),
        DialogueMessage(sender=MessageSender.AI, content="How would you revise it?"),
        DialogueMessage(sender=MessageSender.STUDENT, content="Limit the claim."),
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


@pytest.mark.parametrize("reference", [0, -1, 4, True, "1"])
async def test_invalid_evidence_reference_rejected_before_planning(reference):
    status = _status()
    status["progress"]["reasons"] = [
        {"text": "A reason", "evidenceExchanges": [reference]}
    ]
    client = ScriptedClient(VALIDITY_YES, status, PLANNING)
    with pytest.raises(ModelCallError):
        await _run(client)
    assert client.calls == ["dialogue_validity", "dialogue_status"]


async def test_future_milestone_rejected(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="app.ai")
    with pytest.raises(ModelCallError) as caught:
        await _run(ScriptedClient(VALIDITY_YES, _status(), PLANNING), exchange=2)
    assert caught.value.reason == "invalid_progress_evidence"
    assert "evidence_validation_failed" in caplog.text
    assert "student-exchange evidence" in caplog.text


async def test_planner_receives_named_brief_language_and_record():
    import json

    from app.services.dialogue_turn import planning_material

    result = json.loads(planning_material(_topic(), "student: a reason"))
    assert result["interfaceLanguage"] == "en"
    assert result["approvedInquiryBrief"]["targetExchanges"] == 10
    assert result["dialogueRecord"] == "student: a reason"


async def test_phase_request_budget_blocks_before_provider(monkeypatch):
    from app.core.config import settings
    from app.services.token_budget import ContextWindowExceeded

    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", 1)
    client = ScriptedClient(VALIDITY_YES)
    with pytest.raises(ContextWindowExceeded):
        await _run(client)
    assert client.calls == []


async def test_legacy_catchup_rejects_future_evidence():
    client = ScriptedClient(_status())
    with pytest.raises(ModelCallError):
        await catch_up_progress(
            client,
            prompt=_prompts().status,
            topic=_topic(),
            messages=[
                DialogueMessage(sender=MessageSender.STUDENT, content="Only one turn")
            ],
            model_id="openai/gpt-6-luna",
        )


async def test_achieved_goal_survives_off_topic_turn(monkeypatch):
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.crud import message as message_crud
    from app.services import dialogue
    from app.services.dialogue_context import BoundedDialogueContext

    topic = _topic()
    topic.model_id = "openai/gpt-6-luna"
    session = SimpleNamespace(
        id=uuid4(),
        outcome="open",
        goal_reached=True,
        awaiting_end_consent=False,
        generation_meta={"progress": _ready_progress()},
    )
    bounded = BoundedDialogueContext("transcript", None, 0, None, None)
    monkeypatch.setattr(
        dialogue, "build_bounded_context", AsyncMock(return_value=bounded)
    )
    monkeypatch.setattr(message_crud, "lock_session", AsyncMock(return_value=session))
    monkeypatch.setattr(message_crud, "count_messages", AsyncMock(return_value=0))
    monkeypatch.setattr(message_crud, "count_student_turns", AsyncMock(return_value=0))
    monkeypatch.setattr(message_crud, "merge_session_meta", AsyncMock())
    saved = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(message_crud, "save_exchange", saved)
    done = await dialogue._ask_and_store(
        AsyncMock(),
        ScriptedClient(VALIDITY_NO),
        session=session,
        topic=topic,
        messages=[],
        content="Off topic",
        request_id=uuid4(),
    )
    assert saved.call_args.kwargs["goal_reached"] is True
    assert saved.call_args.kwargs["progress"]["position"]["met"] is False
    assert done.awaiting_end_consent is True


@pytest.mark.parametrize(
    "blocked,expected_calls",
    [
        ("dialogue_validity", []),
        ("dialogue_status", ["dialogue_validity"]),
        ("dialogue_planning", ["dialogue_validity", "dialogue_status"]),
    ],
)
async def test_every_phase_checks_its_actual_schema(
    monkeypatch, blocked, expected_calls
):
    from app.core.config import settings
    from app.services import dialogue_turn
    from app.services.token_budget import ContextWindowExceeded

    schemas = {
        "dialogue_validity": dialogue_turn.VALIDITY_SCHEMA,
        "dialogue_status": dialogue_turn.STATUS_SCHEMA,
        "dialogue_planning": dialogue_turn.PLANNING_SCHEMA,
    }

    def estimate(**request):
        return (
            settings.DIALOGUE_CONTEXT_TOKEN_BUDGET + 1
            if request["schema"] is schemas[blocked]
            else 1
        )

    monkeypatch.setattr(dialogue_turn, "estimate_total_request_tokens", estimate)
    client = ScriptedClient(VALIDITY_YES, _status(), PLANNING)
    with pytest.raises(ContextWindowExceeded):
        await _run(client)
    assert client.calls == expected_calls
