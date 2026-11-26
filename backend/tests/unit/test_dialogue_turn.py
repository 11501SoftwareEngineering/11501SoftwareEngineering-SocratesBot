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
    previous_reason_answers,
    question_before,
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


VALIDITY_YES = {"thinkingProgress": "on topic", "validity": "valid"}
VALIDITY_NO = {"thinkingProgress": "off topic", "validity": "off_topic"}
VALIDITY_NO_REASON = {"thinkingProgress": "no reason", "validity": "no_reason"}
HINT = {"hint": "What makes you think that?"}
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
        ask_for_reason=prompt_for(PromptStage.ASK_FOR_REASON),
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
    assert turn.reply == unrelated_reply("en", "off topic")
    assert turn.reply.endswith("Reason: off topic")
    assert turn.goal_reached is False


@pytest.mark.parametrize(
    ("language", "label"),
    [("zh-TW", "判斷理由\uff1a"), ("en", "Reason: "), ("es", "Motivo: ")],
)
def test_unrelated_reply_uses_localized_reason_label(language, label):
    assert unrelated_reply(language, "  Example\nreason  ").endswith(
        f"{label}Example reason"
    )
    assert unrelated_reply(language, "  \n ") == unrelated_reply(language)
    assert unrelated_reply(language, "a" * 300).endswith(f"{label}{'a' * 240}")


async def test_on_topic_answer_runs_all_three_stages() -> None:
    client = ScriptedClient(VALIDITY_YES, _status(), PLANNING)

    turn = await _run(client)

    assert client.calls == ["dialogue_validity", "dialogue_status", "dialogue_planning"]
    assert turn.reply == PLANNING["content"]
    assert set(turn.prompt_versions) == {"validity", "status", "dialogue"}


async def test_relevant_answer_without_reason_can_continue_without_reaching_goal() -> (
    None
):
    # The model's relevance decision is scripted: this verifies orchestration,
    # not whether a live model interprets the revised prompt correctly.
    progress = empty_progress()
    progress["position"] = {"met": True, "evidenceExchange": 3, "summary": "Allow it."}
    client = ScriptedClient(
        VALIDITY_NO_REASON,
        HINT,
    )
    turn = await run_turn(
        client,
        prompts=_prompts(),
        topic=_topic(),
        question="Should the teacher decide?",
        latest="No.",
        transcript_material="Student disagrees but has not given a reason.",
        previous_progress=None,
        exchange=3,
        model_id="openai/gpt-6-luna",
        validity_model="openai/gpt-6-luna",
    )
    assert client.calls == [
        "dialogue_validity",
        "dialogue_ask_for_reason",
    ]
    assert turn.reply == HINT["hint"]
    assert turn.move == "ask_for_reason"
    assert turn.progress["position"]["met"] is False
    assert set(turn.prompt_versions) == {"validity", "ask_for_reason"}
    assert turn.progress["reason"]["met"] is False
    assert turn.goal_reached is False


async def test_no_reason_cannot_award_new_goal_even_if_status_says_ready():
    turn = await _run(ScriptedClient(VALIDITY_NO_REASON, HINT))
    assert turn.move == "ask_for_reason"
    assert turn.status == "continue"
    assert turn.goal_reached is False


async def test_reason_hint_must_be_nonblank():
    with pytest.raises(ModelCallError):
        await _run(ScriptedClient(VALIDITY_NO_REASON, {"hint": "  "}))


async def test_no_reason_does_not_request_status_or_change_prior_summary():
    prior = _ready_progress()
    client = ScriptedClient(VALIDITY_NO_REASON, HINT)
    turn = await run_turn(
        client,
        prompts=_prompts(),
        topic=_topic(),
        question="Why?",
        latest="No.",
        transcript_material="record",
        previous_progress=prior,
        exchange=4,
        model_id="openai/gpt-6-luna",
        validity_model="openai/gpt-6-luna",
    )
    assert client.calls == ["dialogue_validity", "dialogue_ask_for_reason"]
    assert turn.progress["currentPosition"] == prior["currentPosition"]
    for name in ("position", "reason", "examination", "response"):
        assert turn.progress[name] == {
            "met": False,
            "evidenceExchange": None,
            "summary": "",
        }
        assert prior[name]["met"] is True
    assert not turn.goal_reached


def _ai(content: str, move: str) -> DialogueMessage:
    return DialogueMessage(
        sender=MessageSender.AI,
        content=content,
        generation_meta={"analysis": {"move": move}},
    )


def test_clarification_keeps_original_question_and_relevant_answers():
    messages = [
        _ai("Should the teacher decide?", "change_one_condition"),
        DialogueMessage(sender=MessageSender.STUDENT, content="No."),
        _ai("Why not?", "ask_for_reason"),
        DialogueMessage(sender=MessageSender.STUDENT, content="Weather."),
        _ai("Please answer the question.", "unrelated_response"),
        DialogueMessage(sender=MessageSender.STUDENT, content="Students should."),
        _ai("What is your reason?", "ask_for_reason"),
    ]
    assert question_before(messages, "Fallback?") == "Should the teacher decide?"
    assert previous_reason_answers(messages) == [
        {"exchange": 1, "answer": "No."},
        {"exchange": 3, "answer": "Students should."},
    ]
    messages.append(_ai("What if there is an emergency?", "present_counterexample"))
    assert question_before(messages, "Fallback?") == "What if there is an emergency?"
    assert previous_reason_answers(messages) == []


async def test_reason_followup_receives_previous_answers_and_uses_course_model():
    import json
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=[VALIDITY_NO_REASON, HINT])
    await run_turn(
        SimpleNamespace(complete_object=provider),
        prompts=_prompts(),
        topic=_topic(),
        question="Should the teacher decide?",
        latest="Students should.",
        previous_answers=[{"exchange": 1, "answer": "No."}],
        transcript_material="record",
        previous_progress=None,
        exchange=3,
        model_id="openai/gpt-4o-mini",
        validity_model="openai/gpt-4o-mini",
        api_key="test-key",
    )
    validity, hint = [call.kwargs for call in provider.call_args_list]
    for request in (validity, hint):
        material = json.loads(request["material"])
        assert material["previousAnswers"] == [{"exchange": 1, "answer": "No."}]
        assert material["answer"] == "Students should."
        assert material["interfaceLanguage"] == "en"
    for request in (validity, hint):
        assert request["model"] == "openai/gpt-4o-mini"
        assert request["api_key"] == "test-key"


async def test_supplied_reason_resumes_status_with_original_evidence_exchange():
    import json
    from unittest.mock import AsyncMock

    provider = AsyncMock(side_effect=[VALIDITY_YES, _status("continue"), PLANNING])
    await run_turn(
        SimpleNamespace(complete_object=provider),
        prompts=_prompts(),
        topic=_topic(),
        question="Should the teacher decide?",
        latest="Because students are affected by the decision.",
        previous_answers=[{"exchange": 1, "answer": "No."}],
        transcript_material="record",
        previous_progress=empty_progress(),
        exchange=3,
        model_id="openai/gpt-6-luna",
        validity_model="openai/gpt-6-luna",
    )
    requests = [call.kwargs for call in provider.call_args_list]
    assert [request["name"] for request in requests] == [
        "dialogue_validity",
        "dialogue_status",
        "dialogue_planning",
    ]
    material = json.loads(requests[1]["material"])
    assert material["currentExchange"] == 3
    assert material["previousAnswers"] == [{"exchange": 1, "answer": "No."}]


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


@pytest.mark.parametrize("response_exchange", [3, 4])
async def test_unordered_response_continues_without_claiming_ready(
    response_exchange, caplog
):
    import logging

    caplog.set_level(logging.INFO, logger="app.ai")
    status = _status()
    status["progress"]["examination"]["evidenceExchange"] = 4
    status["progress"]["response"]["evidenceExchange"] = response_exchange
    client = ScriptedClient(VALIDITY_YES, status, PLANNING)

    turn = await _run(client, exchange=4)

    assert client.calls == ["dialogue_validity", "dialogue_status", "dialogue_planning"]
    assert turn.reply == PLANNING["content"]
    assert turn.status == "continue"
    assert turn.goal_reached is False
    assert turn.progress["examination"] == status["progress"]["examination"]
    assert turn.progress["response"] == {
        "met": False,
        "evidenceExchange": None,
        "summary": "",
    }
    assert status["progress"]["response"]["met"] is True
    assert "response_milestone_deferred" in caplog.text

    later = _status()
    later["progress"]["examination"]["evidenceExchange"] = 4
    later["progress"]["response"]["evidenceExchange"] = 5
    next_turn = await run_turn(
        ScriptedClient(VALIDITY_YES, later, PLANNING),
        prompts=_prompts(),
        topic=_topic(),
        question="Why?",
        latest="A later defence.",
        transcript_material="transcript",
        previous_progress=turn.progress,
        exchange=5,
        model_id="openai/gpt-6-luna",
        validity_model="openai/gpt-6-luna",
    )
    assert next_turn.goal_reached is True
    assert next_turn.progress["response"]["evidenceExchange"] == 5


@pytest.mark.parametrize(
    "other_error", ["future_milestone", "future_list", "unmet_cites"]
)
async def test_order_recovery_does_not_hide_other_evidence_errors(other_error):
    status = _status()
    progress = status["progress"]
    progress["examination"]["evidenceExchange"] = 4
    progress["response"]["evidenceExchange"] = 4
    if other_error == "future_milestone":
        progress["examination"]["evidenceExchange"] = 5
    elif other_error == "future_list":
        progress["reasons"] = [{"text": "Unsupported", "evidenceExchanges": [5]}]
    else:
        progress["reason"]["met"] = False
    client = ScriptedClient(VALIDITY_YES, status, PLANNING)
    with pytest.raises(ModelCallError) as caught:
        await _run(client, exchange=4)
    assert caught.value.reason == "invalid_progress_evidence"
    assert client.calls == ["dialogue_validity", "dialogue_status"]


async def test_legacy_catchup_defers_unordered_response():
    status = _status()
    status["progress"]["examination"]["evidenceExchange"] = 3
    client = ScriptedClient(status)
    progress = await catch_up_progress(
        client,
        prompt=_prompts().status,
        topic=_topic(),
        messages=[
            DialogueMessage(sender=MessageSender.STUDENT, content="Answer")
            for _ in range(3)
        ],
        model_id="openai/gpt-6-luna",
    )
    assert client.calls == ["dialogue_status"]
    assert progress["examination"]["evidenceExchange"] == 3
    assert progress["response"]["met"] is False
    assert progress["response"]["evidenceExchange"] is None


async def test_recovered_order_saves_one_exchange_without_ending_dialogue(monkeypatch):
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
        goal_reached=False,
        generation_meta={"progress": empty_progress()},
    )
    messages = [
        DialogueMessage(sender=MessageSender.STUDENT, content="Answer")
        for _ in range(3)
    ]
    status = _status()
    status["progress"]["examination"]["evidenceExchange"] = 4
    status["progress"]["response"]["evidenceExchange"] = 4
    client = ScriptedClient(VALIDITY_YES, status, PLANNING)
    monkeypatch.setattr(
        dialogue,
        "build_bounded_context",
        AsyncMock(
            return_value=BoundedDialogueContext("transcript", None, 0, None, None)
        ),
    )
    monkeypatch.setattr(message_crud, "lock_session", AsyncMock(return_value=session))
    monkeypatch.setattr(message_crud, "count_messages", AsyncMock(return_value=3))
    monkeypatch.setattr(message_crud, "count_student_turns", AsyncMock(return_value=3))
    monkeypatch.setattr(message_crud, "merge_session_meta", AsyncMock())
    saved = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(message_crud, "save_exchange", saved)
    db = AsyncMock()

    done = await dialogue._ask_and_store(
        db,
        client,
        session=session,
        topic=topic,
        messages=messages,
        content="A counterexample and an immediate response.",
        request_id=uuid4(),
    )

    saved.assert_awaited_once()
    values = saved.call_args.kwargs
    assert values["analysis"]["status"] == "continue"
    assert values["progress"]["response"]["met"] is False
    assert values["goal_reached"] is False
    assert done.completed_turns == 4
    assert done.session_status == "open"
    assert done.awaiting_end_consent is False
    assert done.text == PLANNING["content"]
    db.rollback.assert_not_awaited()
    assert client.calls == ["dialogue_validity", "dialogue_status", "dialogue_planning"]


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


async def test_reason_hint_persists_its_prompt_stage_and_counts_one_turn(monkeypatch):
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
        generation_meta={"progress": empty_progress()},
    )
    messages = [
        _ai("Should the teacher decide?", "change_one_condition"),
        DialogueMessage(sender=MessageSender.STUDENT, content="No."),
        _ai("Why not?", "ask_for_reason"),
    ]
    bounded = BoundedDialogueContext("transcript", None, 0, None, None)
    monkeypatch.setattr(
        dialogue, "build_bounded_context", AsyncMock(return_value=bounded)
    )
    monkeypatch.setattr(message_crud, "lock_session", AsyncMock(return_value=session))
    monkeypatch.setattr(message_crud, "count_messages", AsyncMock(return_value=3))
    monkeypatch.setattr(message_crud, "count_student_turns", AsyncMock(return_value=1))
    monkeypatch.setattr(message_crud, "merge_session_meta", AsyncMock())
    saved = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(message_crud, "save_exchange", saved)
    progress = empty_progress()
    progress["position"] = {"met": True, "evidenceExchange": 2, "summary": "No."}
    client = ScriptedClient(
        VALIDITY_NO_REASON,
        HINT,
    )
    done = await dialogue._ask_and_store(
        AsyncMock(),
        client,
        session=session,
        topic=topic,
        messages=messages,
        content="Students should decide.",
        request_id=uuid4(),
    )
    saved.assert_awaited_once()
    values = saved.call_args.kwargs
    assert values["prompt_stage"] == PromptStage.ASK_FOR_REASON.value
    assert values["prompt_version"] == _prompts().ask_for_reason.version
    assert values["analysis"]["move"] == "ask_for_reason"
    assert values["goal_reached"] is True  # historical achievement is preserved
    assert done.completed_turns == 2
    assert done.text == HINT["hint"]


@pytest.mark.parametrize(
    "blocked,expected_calls",
    [
        ("dialogue_validity", []),
        ("dialogue_status", ["dialogue_validity"]),
        ("dialogue_planning", ["dialogue_validity", "dialogue_status"]),
        ("dialogue_ask_for_reason", ["dialogue_validity"]),
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
        "dialogue_ask_for_reason": dialogue_turn.ASK_FOR_REASON_SCHEMA,
    }

    def estimate(**request):
        return (
            settings.DIALOGUE_CONTEXT_TOKEN_BUDGET + 1
            if request["schema"] is schemas[blocked]
            else 1
        )

    monkeypatch.setattr(dialogue_turn, "estimate_total_request_tokens", estimate)
    client = ScriptedClient(
        VALIDITY_NO_REASON if blocked == "dialogue_ask_for_reason" else VALIDITY_YES,
        *([HINT] if blocked == "dialogue_ask_for_reason" else [_status(), PLANNING]),
    )
    with pytest.raises(ContextWindowExceeded):
        await _run(client)
    assert client.calls == expected_calls
