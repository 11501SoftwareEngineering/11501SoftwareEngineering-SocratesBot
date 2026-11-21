"""Lifecycle boundaries using deterministic model/persistence doubles."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services import dialogue
from app.services.dialogue import ReplyRejected, apply_end
from app.services.report_adapter import project_summary, source_snapshot
from app.services.report_text import report_start
from tests.unit.test_report_adapter import inputs, summary


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("turns", [0, 1, 2])
def test_early_finish_requires_three_answers(turns):
    with pytest.raises(ReplyRejected) as error:
        apply_end(
            "finish",
            outcome="open",
            status_value="IN_PROGRESS",
            goal_reached=False,
            completed_turns=turns,
        )
    assert error.value.status_code == 409


@pytest.mark.parametrize("goal", [False, True])
def test_finish_preserves_goal_and_enables_report(goal):
    outcome, status, achieved, awaiting, _ = apply_end(
        "finish",
        outcome="open",
        status_value="IN_PROGRESS",
        goal_reached=goal,
        completed_turns=3,
    )
    assert (outcome, status, achieved, awaiting) == (
        "ended",
        "IN_PROGRESS",
        goal,
        False,
    )
    assert report_start(outcome, None) == "insert"
    assert report_start(outcome, "ready") == "reuse"


def test_inconclusive_is_structured_ready_content_not_missing_report():
    session, topic, messages = inputs()
    session.outcome, session.ending_reason, session.goal_reached = (
        "ended",
        "turn_limit",
        False,
    )
    raw = summary()
    raw.update(
        outcome="inconclusive",
        workingPosition="",
        strongestReason="",
        reflection="Only unrelated replies were available.",
        unmetElements=["No interpretable position or reasoning."],
    )
    source = source_snapshot(session, topic, messages, None)
    body, native = project_summary(raw, source)
    assert body["evidence_status"] == "insufficient"
    assert body["viewpoint_summary"] and body["limitations"] and body["timeline"]
    assert native["outcome"] == "inconclusive"
    assert source["material"]["endingReason"] == "turn_limit"
    assert source["material"]["goalReached"] is False


def test_missing_milestones_do_not_make_a_useful_summary_inconclusive():
    session, topic, messages = inputs()
    session.outcome, session.ending_reason = "ended", "student_requested_stop"
    body, _ = project_summary(
        summary(), source_snapshot(session, topic, messages, None)
    )
    assert body["evidence_status"] == "partial"
    assert body["final_viewpoint"] and body["strongest_reason"]


@pytest.mark.anyio
async def test_end_locks_then_queues_before_commit_and_schedules_after(monkeypatch):
    session = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        outcome="open",
        status="IN_PROGRESS",
        goal_reached=False,
        generation_meta={},
        ending_reason=None,
    )
    events = []
    monkeypatch.setattr(dialogue, "_owned", AsyncMock(return_value=(session, None, [])))

    async def lock(*args):
        events.append("lock")
        return session

    monkeypatch.setattr(dialogue.message_crud, "lock_session", lock)
    monkeypatch.setattr(
        dialogue.message_crud, "count_student_turns", AsyncMock(return_value=3)
    )

    async def save(*args, **kwargs):
        events.append("end")
        for key in ("outcome", "goal_reached", "ending_reason"):
            setattr(session, key, kwargs[key])

    monkeypatch.setattr(dialogue.message_crud, "save_end", save)

    async def queue(*args):
        events.append("queue")
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(dialogue, "queue_ending_report", queue)
    monkeypatch.setattr(
        dialogue.report_runner, "schedule", lambda _: events.append("schedule")
    )
    db = AsyncMock()

    async def commit():
        events.append("commit")

    db.commit.side_effect = commit
    result = await dialogue.end_dialogue(
        db, user_id=session.user_id, session_id=session.id, action="finish"
    )
    assert events == ["lock", "end", "queue", "commit", "schedule"]
    assert result.report_eligible and not result.goal_reached
    events.clear()
    replay = await dialogue.end_dialogue(
        db, user_id=session.user_id, session_id=session.id, action="finish"
    )
    assert replay.session_status == "ended" and events == ["lock"]
    with pytest.raises(HTTPException) as error:
        await dialogue.end_dialogue(
            db, user_id=session.user_id, session_id=session.id, action="continue"
        )
    assert error.value.status_code == 409


@pytest.mark.anyio
@pytest.mark.parametrize("goal", [False, True])
async def test_final_reply_atomically_ends_and_queues_even_without_goal(
    monkeypatch, goal
):
    from app.services.dialogue_progress import empty_progress

    session = SimpleNamespace(
        id=uuid4(),
        goal_reached=goal,
        outcome="open",
        generation_meta={"progress": empty_progress()},
    )
    topic = SimpleNamespace(model_id=None, max_turns=5)
    messages = [SimpleNamespace(sender="student") for _ in range(4)]
    bounded = SimpleNamespace(
        material="record",
        summary=None,
        summarized_message_count=0,
        summary_prompt_stage=None,
        summary_prompt_version=None,
    )
    monkeypatch.setattr(
        dialogue, "build_bounded_context", AsyncMock(return_value=bounded)
    )
    monkeypatch.setattr(dialogue, "question_before", lambda *args: "Why?")
    topic.core_question = "Why?"
    turn = SimpleNamespace(
        reply="Final reflection",
        goal_reached=goal,
        move="reflect",
        status="partial",
        safety_level="none",
        prompt_versions={},
        progress=empty_progress(),
    )
    monkeypatch.setattr(dialogue, "run_turn", AsyncMock(return_value=turn))
    monkeypatch.setattr(
        dialogue.message_crud, "lock_session", AsyncMock(return_value=session)
    )
    monkeypatch.setattr(
        dialogue.message_crud, "count_messages", AsyncMock(return_value=4)
    )
    monkeypatch.setattr(
        dialogue.message_crud, "count_student_turns", AsyncMock(return_value=4)
    )
    monkeypatch.setattr(dialogue.message_crud, "merge_session_meta", AsyncMock())
    monkeypatch.setattr(
        dialogue.message_crud, "save_exchange", AsyncMock(return_value=uuid4())
    )
    ended = AsyncMock()
    monkeypatch.setattr(dialogue.message_crud, "save_end", ended)
    queued = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(dialogue, "queue_ending_report", queued)
    scheduled = Mock()
    monkeypatch.setattr(dialogue.report_runner, "schedule", scheduled)
    db = AsyncMock()
    result = await dialogue._ask_and_store(
        db,
        object(),
        session=session,
        topic=topic,
        messages=messages,
        content="Final answer",
        request_id=uuid4(),
    )
    assert result.session_status == "ended" and result.ending_reason == "turn_limit"
    assert (
        result.report_eligible
        and not result.awaiting_end_consent
        and not result.can_finish_early
    )
    assert result.goal_reached == goal
    assert ended.call_args.kwargs["goal_reached"] == goal
    queued.assert_awaited_once()
    scheduled.assert_called_once()
    assert db.commit.await_count == 2
