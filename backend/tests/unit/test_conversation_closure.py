"""Teacher cutoff, confirmation, report dependencies and zero-answer behavior."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services import conversation_closure as closure
from app.services import report_runner, summary_runner
from app.services.central_synthesis import finalize, from_native, no_evidence_output
from app.services.report_adapter import (
    no_responses_summary,
    source_digest,
)
from tests.unit.test_central_synthesis import metadata, report

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def setup(monkeypatch, stage="conversation", outcomes=("open",)):
    topic = SimpleNamespace(
        id=uuid4(), stage=stage, model_id="openai/gpt-6.1-sol", content_language="en"
    )
    sessions = [
        SimpleNamespace(
            id=uuid4(),
            outcome=value,
            goal_reached=False,
            awaiting_end_consent=True,
            generation_meta={},
            completed_at=None,
        )
        for value in outcomes
    ]
    db = AsyncMock()
    db.scalars.return_value = sessions
    monkeypatch.setattr(
        closure.summaries, "_instructor_topic", AsyncMock(return_value=topic)
    )
    monkeypatch.setattr(closure.topic_crud, "lock_topic", AsyncMock(return_value=topic))
    monkeypatch.setattr(
        closure.summary_crud, "latest_attempt", AsyncMock(return_value=None)
    )
    queue = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(closure.reports, "queue_ending_report", queue)
    insert = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(closure.summary_crud, "insert_attempt", insert)
    report_schedule, summary_schedule = Mock(), Mock()
    monkeypatch.setattr(report_runner, "schedule", report_schedule)
    monkeypatch.setattr(summary_runner, "schedule", summary_schedule)
    monkeypatch.setattr(
        closure, "status_body", AsyncMock(return_value={"stage2_closed": True})
    )
    return topic, sessions, db, queue, insert, report_schedule, summary_schedule


async def test_confirmation_rechecks_current_open_count_and_has_no_side_effect(
    monkeypatch,
):
    topic, sessions, db, queue, insert, rs, ss = setup(
        monkeypatch, outcomes=("open", "open", "ended")
    )
    with pytest.raises(HTTPException) as caught:
        await closure.close(db, teacher=object(), topic_id=topic.id, confirm=False)
    assert caught.value.status_code == 409
    assert caught.value.detail["open_dialogue_count"] == 2
    assert topic.stage == "conversation" and sessions[0].outcome == "open"
    queue.assert_not_awaited()
    insert.assert_not_awaited()
    db.commit.assert_not_awaited()
    rs.assert_not_called()
    ss.assert_not_called()


async def test_confirmed_cutoff_ends_only_open_sessions_preserves_goal_and_queues_after_commit(
    monkeypatch,
):
    topic, sessions, db, queue, insert, rs, ss = setup(
        monkeypatch, outcomes=("open", "open", "completed", "abandoned")
    )
    sessions[1].goal_reached = True

    def scheduled(_id):
        db.commit.assert_awaited_once()

    rs.side_effect = ss.side_effect = scheduled
    await closure.close(db, teacher=object(), topic_id=topic.id, confirm=True)
    assert topic.stage == "summary"
    assert [s.outcome for s in sessions] == ["ended", "ended", "completed", "abandoned"]
    assert not sessions[0].goal_reached and sessions[1].goal_reached
    assert sessions[0].ending_reason == "teacher_ended_stage2"
    assert not sessions[0].awaiting_end_consent and sessions[0].completed_at is None
    assert queue.await_count == 3 and ss.call_count == 1
    assert (
        insert.await_args.kwargs["request_json"]["schema_version"] == "closed-stage2-v1"
    )


@pytest.mark.parametrize("state", ["ready", "processing"])
async def test_repeated_closure_reuses_existing_ready_or_live_job(monkeypatch, state):
    topic, _sessions, db, queue, insert, rs, ss = setup(
        monkeypatch, stage="summary", outcomes=("ended",)
    )
    monkeypatch.setattr(
        closure.summary_crud,
        "latest_attempt",
        AsyncMock(
            return_value=SimpleNamespace(
                status=state, lease_expires_at=datetime.now(UTC) + timedelta(minutes=1)
            )
        ),
    )
    await closure.close(db, teacher=object(), topic_id=topic.id, confirm=False)
    queue.assert_not_awaited()
    insert.assert_not_awaited()
    rs.assert_not_called()
    ss.assert_not_called()


async def test_failed_closure_can_retry_without_reopening_dialogues(monkeypatch):
    topic, sessions, db, _queue, insert, _rs, ss = setup(
        monkeypatch, stage="summary", outcomes=("ended",)
    )
    monkeypatch.setattr(
        closure.summary_crud,
        "latest_attempt",
        AsyncMock(return_value=SimpleNamespace(status="failed")),
    )
    await closure.close(db, teacher=object(), topic_id=topic.id, confirm=False)
    assert topic.stage == "summary" and sessions[0].outcome == "ended"
    insert.assert_awaited_once()
    ss.assert_called_once()


async def test_setup_cannot_close(monkeypatch):
    topic, _, db, _, insert, _, _ = setup(monkeypatch, stage="setup")
    with pytest.raises(HTTPException) as caught:
        await closure.close(db, teacher=object(), topic_id=topic.id, confirm=True)
    assert caught.value.status_code == 400
    insert.assert_not_awaited()


async def test_open_count_read_does_not_close_or_queue(monkeypatch):
    topic = SimpleNamespace(id=uuid4(), stage="conversation")
    db = AsyncMock()
    db.scalars.return_value = ["open", "ended", "open"]
    monkeypatch.setattr(
        closure.summary_crud, "latest_attempt", AsyncMock(return_value=None)
    )
    result = await closure.status_body(db, topic)
    assert result["open_dialogue_count"] == 2 and result["confirmation_required"]
    assert not result["stage2_closed"]
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("state", ["processing", "ready", "failed", "expired"])
async def test_summary_waits_for_reports_and_failure_requires_retry(monkeypatch, state):
    topic, _, db, *_ = setup(monkeypatch, stage="summary", outcomes=())
    attempt_id, session_id = uuid4(), uuid4()
    latest = SimpleNamespace(id=attempt_id, status="processing")
    monkeypatch.setattr(
        closure.summary_crud, "latest_attempt", AsyncMock(return_value=latest)
    )
    db.scalars.return_value = [session_id]
    row = SimpleNamespace(
        session_id=session_id,
        status="processing" if state == "expired" else state,
        result_json={} if state != "ready" else {"ok": True},
        lease_expires_at=datetime.now(UTC)
        + timedelta(seconds=-1 if state == "expired" else 60),
    )
    monkeypatch.setattr(
        closure.report_crud, "list_for_sessions", AsyncMock(return_value=[row])
    )
    frozen = {"reports": [], "model_id": "selected", "content_language": "en"}
    capture = AsyncMock(return_value=frozen)
    monkeypatch.setattr(closure.summaries, "native_request", capture)
    request = {"topic_id": topic.id, "model_id": "selected", "content_language": "en"}
    if state in {"failed", "expired"}:
        with pytest.raises(ValueError):
            await closure.prepare_closed_request(db, attempt_id, request)
        capture.assert_not_awaited()
    else:
        result = await closure.prepare_closed_request(db, attempt_id, request)
        if state == "processing":
            assert result is None
            capture.assert_not_awaited()
        else:
            assert result["model_id"] == "selected" and latest.request_json == frozen
            db.commit.assert_awaited_once()


def zero_metadata():
    data = metadata(False, "inconclusive")
    src = data["report_source"]
    src["exchanges"] = []
    src["material"]["transcript"] = []
    data["native_summary"] = no_responses_summary("en")
    data["source_digest"] = source_digest(src)
    return data


def test_nonparticipants_excluded_but_inconclusive_participants_count():
    zero = from_native(str(uuid4()), zero_metadata())
    partial = report(False, "inconclusive")
    draft = finalize(no_evidence_output("en"), [zero, partial], "en")
    assert draft["denominator"] == 1 and draft["ungrouped_report_ids"] == [partial.id]
    all_zero = finalize(no_evidence_output("en"), [zero], "en")
    assert all_zero["denominator"] == 0 and all_zero["ungrouped_report_ids"] == []
    assert "excluded" in all_zero["viewpoint_summary"]
    assert finalize(no_evidence_output("en"), [], "en")["denominator"] == 0


async def test_zero_answer_report_avoids_model_key_and_tokenizer(monkeypatch):
    source = zero_metadata()["report_source"]
    monkeypatch.setattr(
        report_runner, "_begin", AsyncMock(return_value=(uuid4(), None))
    )
    monkeypatch.setattr(report_runner, "_source", AsyncMock(return_value=source))
    monkeypatch.setattr(report_runner, "refresh", AsyncMock())
    provider, key, tokenizer = (
        AsyncMock(),
        AsyncMock(),
        Mock(side_effect=AssertionError("must not tokenize")),
    )
    monkeypatch.setattr(report_runner.client, "complete_object", provider)
    monkeypatch.setattr(report_runner, "_api_key", key)
    monkeypatch.setattr(report_runner, "estimate_total_request_tokens", tokenizer)
    ready, failed = AsyncMock(), AsyncMock()
    monkeypatch.setattr(report_runner, "_ready", ready)
    monkeypatch.setattr(report_runner, "_fail", failed)
    await report_runner.run_report(uuid4())
    failed.assert_not_awaited()
    ready.assert_awaited_once()
    assert ready.await_args.args[1]["evidence_status"] == "insufficient"
    assert "No student responses" in ready.await_args.args[1]["viewpoint_summary"]
    provider.assert_not_awaited()
    key.assert_not_awaited()
    tokenizer.assert_not_called()


async def test_transition_automatically_waits_and_then_synthesizes(monkeypatch):
    request = {
        "schema_version": "closed-stage2-v1",
        "model_id": "selected",
        "topic_id": uuid4(),
        "content_language": "en",
    }
    frozen = {
        **request,
        "schema_version": "native-central-request-v1",
        "reports": [report(False).model_dump()],
        "sources": [],
    }
    monkeypatch.setattr(summary_runner, "_begin", AsyncMock(return_value=request))
    wait = AsyncMock(return_value=frozen)
    monkeypatch.setattr(summary_runner, "_wait_for_reports", wait)
    monkeypatch.setattr(summary_runner, "refresh", AsyncMock())
    ready, fail, provider = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(summary_runner, "_ready", ready)
    monkeypatch.setattr(summary_runner, "_fail", fail)
    monkeypatch.setattr(summary_runner.client, "complete_object", provider)
    await summary_runner.run_summary(uuid4())
    wait.assert_awaited_once()
    ready.assert_awaited_once()
    fail.assert_not_awaited()
    provider.assert_not_awaited()


def test_empty_cohort_uses_bounded_inquiry_material_without_model(monkeypatch):
    brief = dict.fromkeys(
        (
            "theme",
            "inquiryQuestion",
            "inquiryFocus",
            "backgroundInfo",
            "exclusions",
            "openingMessage",
        ),
        "界" * 8000,
    )
    tokenizer = Mock(side_effect=AssertionError("no model call needed"))
    monkeypatch.setattr(summary_runner, "estimate_total_request_tokens", tokenizer)
    rows, material, _ = summary_runner.prepare_request(
        {
            "reports": [],
            "allow_empty_cohort": True,
            "inquiry": brief,
            "model_id": "unused",
            "content_language": "en",
        }
    )
    assert rows == [] and material["reports"] == []
    assert set(material["inquiry"]) == {"theme", "question", "focus"}
    tokenizer.assert_not_called()


async def test_closing_during_direct_synthesis_permanently_closes_stage2(monkeypatch):
    topic, _, db, queue, insert, rs, ss = setup(
        monkeypatch, stage="conversation", outcomes=("ended",)
    )
    monkeypatch.setattr(
        closure.summary_crud,
        "latest_attempt",
        AsyncMock(
            return_value=SimpleNamespace(
                status="processing",
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        ),
    )
    await closure.close(db, teacher=object(), topic_id=topic.id, confirm=False)
    assert topic.stage == "summary"
    db.commit.assert_awaited_once()
    queue.assert_not_awaited()
    insert.assert_not_awaited()
    rs.assert_not_called()
    ss.assert_not_called()
