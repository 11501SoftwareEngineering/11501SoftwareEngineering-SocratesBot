"""Native report contract, real-source citations and job boundary regressions."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import report_runner
from app.services.dialogue_progress import empty_progress
from app.services.report_adapter import (
    NATIVE_SCHEMA,
    project_summary,
    source_digest,
    source_snapshot,
)
from app.services.report_text import student_report, validate_report


@pytest.fixture
def anyio_backend():
    return "asyncio"


def inputs():
    session = SimpleNamespace(
        id=uuid4(), outcome="completed", completed_at=datetime.now(UTC)
    )
    topic = SimpleNamespace(
        content_language="en",
        model_id="openai/gpt-4o-mini",
        age_band="16-18",
        max_turns=10,
        inquiry_topic="Fairness",
        core_question="What is fair?",
        inquiry_focus="Reasons",
        background_info="A shared resource",
        exclusions="",
        opening_message="Who decides?",
    )
    messages = [
        SimpleNamespace(
            id=uuid4(),
            session_id=session.id,
            sender="student",
            content="I am uncertain because needs differ.",
        ),
        SimpleNamespace(
            id=uuid4(),
            session_id=session.id,
            sender="ai",
            content="What evidence would help?",
        ),
    ]
    return session, topic, messages


def summary():
    return {
        "outcome": "partial",
        "workingPosition": "Uncertain about equal shares.",
        "strongestReason": "Needs differ.",
        "challengeExamined": "",
        "revisionOrDefence": "",
        "focalTensionConnection": "Different standards of fairness.",
        "remainingQuestion": "How should needs be assessed?",
        "reflection": "The student identified a reason for uncertainty.",
        "unmetElements": ["No challenge was examined."],
    }


def source():
    return source_snapshot(*inputs(), empty_progress())


def test_native_contract_and_projection_keep_unknowns_honest():
    snapshot = source()
    body, native = project_summary(summary(), snapshot)
    validated = validate_report(body, source=snapshot)
    assert set(NATIVE_SCHEMA["required"]) == set(summary())
    assert native == summary()
    assert validated["viewpoint_status"] == validated["other_perspectives"] == ""
    assert validated["challenges"] == []
    assert validated["evidence_status"] == "partial"
    assert validated["timeline"][0]["attribution"] == "none"
    assert validated["timeline"][0]["evidence_reference"] == {
        k: snapshot["exchanges"][0][k] for k in ("message_id", "turn", "quote")
    }
    assert (
        "native_summary"
        not in student_report(
            status="ready",
            body=body,
            report_id="r",
            session_id="s",
            topic_id="t",
            completed_turns=1,
        )["report"]
    )


def test_input_snapshot_is_private_frozen_and_has_native_names():
    session, topic, messages = inputs()
    progress = empty_progress()
    snapshot = source_snapshot(session, topic, messages, progress)
    digest = source_digest(snapshot)
    progress["currentPosition"] = "mutated"
    messages[0].content = "mutated"
    assert snapshot["material"]["finalProgress"]["currentPosition"] == ""
    assert set(snapshot["material"]) == {
        "interfaceLanguage",
        "approvedInquiryBrief",
        "transcript",
        "finalProgress",
        "endingReason",
        "goalReached",
    }
    assert snapshot["material"]["transcript"][0]["role"] == "user"
    assert str(session.id) not in str(snapshot["material"])
    assert source_digest(snapshot) == digest


@pytest.mark.parametrize(
    "kind", ["wrong_owner", "duplicate", "open", "future_progress"]
)
def test_source_rejects_invalid_ownership_or_progress(kind):
    session, topic, messages = inputs()
    progress = empty_progress()
    if kind == "wrong_owner":
        messages[0].session_id = uuid4()
    if kind == "duplicate":
        messages.append(messages[0])
    if kind == "open":
        session.outcome = "open"
    if kind == "future_progress":
        progress["reasons"] = [{"text": "r", "evidenceExchanges": [2]}]
    with pytest.raises(ValueError):
        source_snapshot(session, topic, messages, progress)


@pytest.mark.parametrize(
    "kind", ["id", "quote", "turn", "tutor", "attribution", "missing", "duplicate"]
)
def test_forged_or_malformed_citations_rejected(kind):
    snapshot = source()
    body, _ = project_summary(summary(), snapshot)
    item = body["timeline"][0]
    if kind == "id":
        item["evidence_reference"]["message_id"] = str(uuid4())
    if kind == "quote":
        item["evidence_reference"]["quote"] = "Invented"
    if kind == "turn":
        item["turn"] = 2
    if kind == "tutor":
        item["evidence"] = "What evidence would help?"
    if kind == "attribution":
        item["attribution"] = "proved_causation"
    if kind == "missing":
        item.pop("evidence_reference")
    if kind == "duplicate":
        body["timeline"].append(deepcopy(item))
    with pytest.raises(ValueError):
        validate_report(body, source=snapshot)


@pytest.mark.parametrize(
    "kind", ["missing", "wrong_type", "extra", "oversized", "bad_outcome"]
)
def test_native_malformed_output_is_not_silently_coerced(kind):
    raw = summary()
    if kind == "missing":
        raw.pop("workingPosition")
    if kind == "wrong_type":
        raw["workingPosition"] = 3
    if kind == "extra":
        raw["student_name"] = "Should not be stored"
    if kind == "oversized":
        raw["unmetElements"] = ["a" * 801]
    if kind == "bad_outcome":
        raw["outcome"] = "ready"
    with pytest.raises(ValueError):
        project_summary(raw, source())


def test_empty_evidence_can_still_produce_a_report_without_inventing_position():
    session, topic, _ = inputs()
    snapshot = source_snapshot(session, topic, [], None)
    raw = summary()
    for key in raw:
        if key not in ("outcome", "unmetElements"):
            raw[key] = ""
    body, _ = project_summary(raw, snapshot)
    assert validate_report(body, source=snapshot)["final_viewpoint"] == ""
    assert body["evidence_status"] == "insufficient"
    assert body["timeline"] == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure", [None, "invalid_model_output", "provider", "source", "budget"]
)
async def test_runner_persists_native_privately_or_marks_failure(monkeypatch, failure):
    from app.core.config import settings
    from app.services.model_client import ModelCallError

    attempt_id, session_id = uuid4(), uuid4()
    snapshot = source()
    monkeypatch.setattr(
        report_runner, "_api_key", AsyncMock(return_value="private-course-key")
    )
    monkeypatch.setattr(
        report_runner, "_begin", AsyncMock(return_value=(session_id, None))
    )
    monkeypatch.setattr(
        report_runner,
        "_source",
        AsyncMock(
            return_value=snapshot,
            side_effect=RuntimeError("private failure")
            if failure == "source"
            else None,
        ),
    )
    monkeypatch.setattr(report_runner, "refresh", AsyncMock())
    provider = AsyncMock(
        return_value={} if failure == "invalid_model_output" else summary(),
        side_effect=ModelCallError(502) if failure == "provider" else None,
    )
    monkeypatch.setattr(
        report_runner, "client", SimpleNamespace(complete_object=provider)
    )
    ready, failed = AsyncMock(), AsyncMock()
    monkeypatch.setattr(report_runner, "_ready", ready)
    monkeypatch.setattr(report_runner, "_fail", failed)
    if failure == "budget":
        monkeypatch.setattr(settings, "REPORT_CONTEXT_TOKEN_BUDGET", 1)
    await report_runner.run_report(attempt_id)
    if failure:
        failed.assert_awaited_once_with(attempt_id)
        ready.assert_not_awaited()
        if failure in ("source", "budget"):
            provider.assert_not_awaited()
    else:
        failed.assert_not_awaited()
        args = ready.call_args.args
        assert args[4]["native_summary"] == summary()
        assert args[4]["source_digest"] == source_digest(snapshot)
        assert "native_summary" not in args[1]
        assert provider.call_args.kwargs["schema"] == NATIVE_SCHEMA
        assert provider.call_args.kwargs["model"] == snapshot["model_id"]
        assert provider.call_args.kwargs["api_key"] == "private-course-key"
        assert "private-course-key" not in str(ready.call_args)
        assert "finalProgress" in provider.call_args.kwargs["material"]
    assert attempt_id not in report_runner.live_attempts()


@pytest.mark.anyio
async def test_source_is_committed_before_use_and_reused_without_reload(monkeypatch):
    from app.crud import message as message_crud
    from app.crud import report as report_crud

    session, topic, messages = inputs()
    session.user_id = uuid4()
    attempt_id = uuid4()
    attempt = SimpleNamespace(session_id=session.id, generation_meta={})
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.get.return_value = session
    monkeypatch.setattr(report_runner, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(report_crud, "get_attempt", AsyncMock(return_value=attempt))
    load = AsyncMock(return_value=(session, topic, messages))
    monkeypatch.setattr(message_crud, "load_owned_dialogue", load)
    store = AsyncMock()
    monkeypatch.setattr(report_crud, "save_source", store)
    snapshot = await report_runner._source(attempt_id, session.id, None)
    store.assert_awaited_once_with(db, attempt_id, snapshot, source_digest(snapshot))
    db.commit.assert_awaited_once()
    attempt.generation_meta = {
        "report_source": snapshot,
        "source_digest": source_digest(snapshot),
    }
    load.reset_mock()
    assert await report_runner._source(attempt_id, session.id, None) == snapshot
    load.assert_not_awaited()
    attempt.generation_meta["source_digest"] = "tampered"
    with pytest.raises(ValueError):
        await report_runner._source(attempt_id, session.id, None)


@pytest.mark.anyio
async def test_ready_update_keeps_native_metadata_private_and_source_update_checks_state():
    from app.crud import report as report_crud

    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(rowcount=1)
    snapshot = source()
    await report_crud.save_source(db, uuid4(), snapshot, source_digest(snapshot))
    values = db.execute.call_args.args[0].compile().params
    assert {
        "report_source": snapshot,
        "source_digest": source_digest(snapshot),
    } in values.values()
    body, native = project_summary(summary(), snapshot)
    metadata = {"native_summary": native, "model_id": "openai/gpt-6.1-sol"}
    await report_crud.mark_ready(
        db,
        uuid4(),
        body,
        prompt_stage="personal_report",
        prompt_version="test",
        report_metadata=metadata,
    )
    values = db.execute.call_args.args[0].compile().params
    assert body in values.values()
    assert {
        **metadata,
        "prompt_stage": "personal_report",
        "prompt_version": "test",
    } in values.values()
    assert "native_summary" not in body
    db.execute.return_value = SimpleNamespace(rowcount=0)
    with pytest.raises(ValueError):
        await report_crud.save_source(db, uuid4(), snapshot, source_digest(snapshot))


def test_report_completion_timestamp_is_explicit_server_metadata():
    result = student_report(
        status="ready",
        body={"viewpoint_summary": "A view"},
        report_id="r",
        session_id="s",
        topic_id="t",
        completed_turns=1,
        completed_at="2026-11-21T00:00:00+00:00",
    )
    assert result["report"]["completed_at"] == "2026-11-21T00:00:00+00:00"
