"""Stage3 readiness, immutable inputs, failure and publication boundaries."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.crud import summary as crud
from app.services import summaries, summary_runner
from app.services.central_synthesis import finalize, from_native
from tests.unit.test_central_synthesis import metadata, output, report
from tests.unit.test_report_adapter import inputs

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def topic():
    result = inputs()[1]
    result.id, result.stage = uuid4(), "conversation"
    return result


@pytest.mark.parametrize(
    "problem,code",
    [
        ("open", 409),
        ("waiting", 409),
        ("legacy", 409),
        ("mixed", 409),
        ("empty", 400),
        ("large", 413),
        (None, 200),
    ],
)
async def test_enqueue_requires_ended_dialogues_and_valid_complete_cohort(
    monkeypatch, problem, code
):
    current = topic()
    row = {
        "report_id": str(uuid4()),
        "session_id": str(uuid4()),
        "metadata": metadata(),
    }
    rows = [row]
    if problem == "legacy":
        row["metadata"] = {}
    if problem == "mixed":
        current.core_question = "Different inquiry"
    if problem == "empty":
        rows = []
    if problem == "large":
        rows = [row] * 51
    monkeypatch.setattr(
        summaries.topic_crud, "lock_topic", AsyncMock(return_value=current)
    )
    monkeypatch.setattr(
        crud, "has_open_dialogues", AsyncMock(return_value=problem == "open")
    )
    monkeypatch.setattr(crud, "latest_attempt", AsyncMock(return_value=None))
    load = AsyncMock(
        return_value=rows,
        side_effect=ValueError("Wait for reports") if problem == "waiting" else None,
    )
    monkeypatch.setattr(crud, "ready_native_reports", load)
    create = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(crud, "insert_attempt", create)
    schedule = Mock()
    monkeypatch.setattr(summary_runner, "schedule", schedule)
    db = AsyncMock()
    if code != 200:
        with pytest.raises(HTTPException) as caught:
            await summaries._enqueue(db, current.id)
        assert caught.value.status_code == code
        create.assert_not_awaited()
        schedule.assert_not_called()
    else:
        await summaries._enqueue(db, current.id)
        request = create.call_args.kwargs["request_json"]
        assert request["model_id"] == current.model_id
        assert request["sources"][0]["report_id"] == row["report_id"]
        assert request["reports"][0]["reasons"]
        assert "report_source" not in request and "api_key" not in request
        db.commit.assert_awaited_once()
        schedule.assert_called_once()


@pytest.mark.parametrize("status", [None, "pending", "processing", "failed", "ready"])
async def test_cohort_requires_latest_attempt_ready_for_every_eligible_session(status):
    session_id = uuid4()
    db = AsyncMock()
    rows = (
        []
        if status is None
        else [
            SimpleNamespace(
                session_id=session_id,
                id=uuid4(),
                status=status,
                result_json={"report": "body"},
                generation_meta=metadata(),
            )
        ]
    )
    db.scalars.side_effect = [[session_id], rows]
    if status == "ready":
        assert len(await crud.ready_native_reports(db, uuid4())) == 1
    else:
        with pytest.raises(ValueError):
            await crud.ready_native_reports(db, uuid4())


async def test_all_inconclusive_job_never_calls_provider_or_credentials(monkeypatch):
    request = {
        "reports": [report(False, "inconclusive").model_dump()],
        "sources": [],
        "model_id": "openai/gpt-4o-mini",
        "content_language": "en",
        "topic_id": uuid4(),
    }
    monkeypatch.setattr(summary_runner, "_begin", AsyncMock(return_value=request))
    monkeypatch.setattr(summary_runner, "refresh", AsyncMock())
    provider, key = AsyncMock(), AsyncMock()
    monkeypatch.setattr(
        summary_runner, "client", SimpleNamespace(complete_object=provider)
    )
    monkeypatch.setattr(summary_runner, "_api_key", key)
    ready, fail = AsyncMock(), AsyncMock()
    monkeypatch.setattr(summary_runner, "_ready", ready)
    monkeypatch.setattr(summary_runner, "_fail", fail)
    await summary_runner.run_summary(uuid4())
    provider.assert_not_awaited()
    key.assert_not_awaited()
    fail.assert_not_awaited()
    native = ready.call_args.args[2]["native_synthesis"]
    assert native["generation_method"] == "deterministic"
    assert native["totalReports"] == 1 and native["eligibleReports"] == 0


async def test_legacy_pending_summary_fails_without_reinterpreting_input(monkeypatch):
    attempt = SimpleNamespace(status="pending", request_json={"material": []})
    db = AsyncMock()
    db.__aenter__.return_value = db
    monkeypatch.setattr(summary_runner, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(crud, "get_attempt", AsyncMock(return_value=attempt))
    monkeypatch.setattr(crud, "mark_processing", AsyncMock())
    failed = AsyncMock()
    monkeypatch.setattr(crud, "mark_failed", failed)
    attempt_id = uuid4()
    assert await summary_runner._begin(attempt_id) is None
    failed.assert_awaited_once_with(db, attempt_id)


@pytest.mark.parametrize("changed", ["open", "cohort"])
async def test_ready_rechecks_open_dialogues_and_cohort_before_commit(
    monkeypatch, changed
):
    db = AsyncMock()
    attempt_id = uuid4()
    monkeypatch.setattr(
        crud, "latest_attempt", AsyncMock(return_value=SimpleNamespace(id=attempt_id))
    )
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: topic())
    monkeypatch.setattr(
        crud, "has_open_dialogues", AsyncMock(return_value=changed == "open")
    )
    monkeypatch.setattr(
        crud, "ready_native_reports", AsyncMock(return_value=[{"report_id": "new"}])
    )
    mark = AsyncMock()
    monkeypatch.setattr(crud, "_mark_ready", mark)
    with pytest.raises(ValueError):
        await crud.store_ready_summary(
            db,
            attempt_id=attempt_id,
            topic_id=uuid4(),
            draft={"native_synthesis": {"sources": [{"report_id": "old"}]}},
            prompt_stage="class_summary",
            prompt_version="test",
        )
    mark.assert_not_awaited()


async def test_native_result_survives_document_and_public_projection():
    from app.services.summary_text import public_summary

    row = from_native(str(uuid4()), metadata())
    draft = finalize(output(["report_1"]), [row], "en")
    stored = crud._document(
        draft, {"published": {"overview": "previous"}, "published_version": 1}
    )
    assert stored["native_synthesis"] == draft["native_synthesis"]
    assert stored["published"]["overview"] == "previous"
    public = public_summary(stored)
    assert "native_synthesis" not in public
    assert row.id not in str(public)


async def test_request_budget_rejects_before_provider(monkeypatch):
    monkeypatch.setattr(summary_runner.settings, "REPORT_CONTEXT_TOKEN_BUDGET", 1024)
    with pytest.raises(ValueError):
        summary_runner.prepare_request(
            {
                "reports": [report().model_dump()],
                "model_id": "openai/gpt-4o-mini",
                "content_language": "en",
            }
        )


async def test_losing_worker_does_not_generate_duplicate_summary(monkeypatch):
    db = AsyncMock()
    db.__aenter__.return_value = db
    monkeypatch.setattr(summary_runner, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        crud, "get_attempt", AsyncMock(return_value=SimpleNamespace(status="pending"))
    )
    monkeypatch.setattr(crud, "mark_processing", AsyncMock(return_value=False))
    assert await summary_runner._begin(uuid4()) is None


async def test_old_attempt_cannot_replace_a_newer_attempt(monkeypatch):
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: topic())
    monkeypatch.setattr(
        crud, "latest_attempt", AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    )
    failed, ready = AsyncMock(), AsyncMock()
    monkeypatch.setattr(crud, "mark_failed", failed)
    monkeypatch.setattr(crud, "_mark_ready", ready)
    attempt_id = uuid4()
    await crud.store_ready_summary(
        db,
        attempt_id=attempt_id,
        topic_id=uuid4(),
        draft={},
        prompt_stage="class_summary",
        prompt_version="test",
    )
    failed.assert_awaited_once_with(db, attempt_id)
    ready.assert_not_awaited()


@pytest.mark.parametrize("legacy", [True, False])
async def test_teacher_retry_regenerates_only_incompatible_ready_report(
    monkeypatch, legacy
):
    from app.services import reports

    current = topic()
    session = SimpleNamespace(
        id=uuid4(), topic_id=current.id, outcome="ended", generation_meta={}
    )
    db = AsyncMock()
    db.get.return_value = session
    monkeypatch.setattr(reports, "_instructor_topic", AsyncMock(return_value=current))
    row = SimpleNamespace(
        id=uuid4(), status="ready", generation_meta={} if legacy else metadata()
    )
    monkeypatch.setattr(
        reports.report_crud, "list_for_session", AsyncMock(return_value=[row])
    )
    inserted, scheduled = AsyncMock(return_value=SimpleNamespace(id=uuid4())), Mock()
    monkeypatch.setattr(reports.report_crud, "insert_pending", inserted)
    monkeypatch.setattr(reports.report_runner, "schedule", scheduled)
    monkeypatch.setattr(reports, "_payload", AsyncMock(return_value={}))
    await reports.start_teacher_retry(
        db, teacher=object(), topic_id=current.id, session_id=session.id
    )
    assert inserted.await_count == int(legacy)
    assert scheduled.call_count == int(legacy)


async def test_teacher_retry_rechecks_ready_report_after_session_lock(monkeypatch):
    from app.services import reports

    current = topic()
    session = SimpleNamespace(
        id=uuid4(), topic_id=current.id, outcome="ended", generation_meta={}
    )
    db = AsyncMock()
    db.get.return_value = session
    monkeypatch.setattr(reports, "_instructor_topic", AsyncMock(return_value=current))
    rows = [SimpleNamespace(id=uuid4(), status="ready", generation_meta={})]

    async def acquire_lock(*args, **kwargs):
        # Another retry finished while this request waited for the session lock.
        rows.append(
            SimpleNamespace(id=uuid4(), status="ready", generation_meta=metadata())
        )

    db.execute.side_effect = acquire_lock
    monkeypatch.setattr(
        reports.report_crud,
        "list_for_session",
        AsyncMock(side_effect=lambda *args: list(rows)),
    )
    inserted, scheduled = AsyncMock(), Mock()
    monkeypatch.setattr(reports.report_crud, "insert_pending", inserted)
    monkeypatch.setattr(reports.report_runner, "schedule", scheduled)
    payload = AsyncMock(return_value={"report_status": "ready"})
    monkeypatch.setattr(reports, "_payload", payload)
    result = await reports.start_teacher_retry(
        db, teacher=object(), topic_id=current.id, session_id=session.id
    )
    assert result["report_status"] == "ready"
    inserted.assert_not_awaited()
    scheduled.assert_not_called()
    db.commit.assert_not_awaited()
    assert payload.await_args.args[2][-1] is rows[-1]
