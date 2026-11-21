"""Cross-stage routing, credential isolation and frozen model regressions."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import settings
from app.services import report_runner, summary_runner
from app.services import teacher_ai_settings as keys
from app.services.model_client import ModelCallError, OpenAIChatClient

pytestmark = pytest.mark.anyio


async def test_all_turn_stages_forward_selected_model_and_key():
    from app.services.dialogue_progress import empty_progress
    from app.services.dialogue_turn import catch_up_progress, run_turn
    from tests.unit.test_dialogue_turn import (
        PLANNING,
        VALIDITY_YES,
        _prompts,
        _status,
        _topic,
    )

    provider = AsyncMock(side_effect=[VALIDITY_YES, _status(), PLANNING])
    client = SimpleNamespace(complete_object=provider)
    await run_turn(
        client,
        prompts=_prompts(),
        topic=_topic(),
        question="Why?",
        latest="Fairness",
        transcript_material="record",
        previous_progress=None,
        exchange=3,
        model_id="openai/gpt-4o-mini",
        validity_model="openai/gpt-4o-mini",
        api_key="teacher-secret",
    )
    assert provider.await_count == 3
    for call in provider.call_args_list:
        assert call.kwargs["model"] == "openai/gpt-4o-mini"
        assert call.kwargs["api_key"] == "teacher-secret"
    provider.reset_mock(side_effect=True)
    provider.return_value = {
        "progress": empty_progress(),
        "status": "continue",
        "safetyLevel": "normal",
    }
    await catch_up_progress(
        client,
        prompt=_prompts().status,
        topic=_topic(),
        messages=[],
        model_id="openai/gpt-4o-mini",
        api_key="teacher-secret",
    )
    assert provider.call_args.kwargs["api_key"] == "teacher-secret"


async def test_historical_report_model_upgrade_preserves_evidence(monkeypatch):
    from app.services.report_adapter import source_digest
    from tests.unit.test_report_adapter import source

    snapshot = source()
    snapshot.pop("model_id")
    session_id, attempt_id = uuid4(), uuid4()
    attempt = SimpleNamespace(
        session_id=session_id,
        generation_meta={
            "report_source": snapshot,
            "source_digest": source_digest(snapshot),
        },
    )
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.get.side_effect = [
        SimpleNamespace(topic_id=uuid4()),
        SimpleNamespace(model_id="openai/gpt-4o-mini"),
    ]
    monkeypatch.setattr(report_runner, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        report_runner.report_crud, "get_attempt", AsyncMock(return_value=attempt)
    )
    save = AsyncMock()
    monkeypatch.setattr(report_runner.report_crud, "save_source", save)
    result = await report_runner._source(attempt_id, session_id, None)
    assert result == {**snapshot, "model_id": "openai/gpt-4o-mini"}
    assert "model_id" not in snapshot
    save.assert_awaited_once_with(db, attempt_id, result, source_digest(result))
    db.commit.assert_awaited_once()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("stored", [None, "encrypted"])
async def test_course_owner_not_caller_selects_key(monkeypatch, stored):
    owner, course_id = uuid4(), uuid4()
    db = AsyncMock()
    monkeypatch.setattr(
        keys.course_crud,
        "get_course_by_id",
        AsyncMock(return_value=SimpleNamespace(created_by=owner)),
    )
    lookup = AsyncMock(return_value=SimpleNamespace(api_key_ciphertext=stored))
    monkeypatch.setattr(keys.settings_crud, "get_settings", lookup)
    monkeypatch.setattr(keys, "decrypt_api_key", lambda value: "teacher-secret")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("server-secret"))
    assert await keys.course_api_key(db, course_id) == (
        "teacher-secret" if stored else "server-secret"
    )
    lookup.assert_awaited_once_with(db, owner)


@pytest.mark.parametrize("missing", [True, False])
async def test_missing_course_or_unreadable_key_fails_closed(monkeypatch, missing):
    monkeypatch.setattr(
        keys.course_crud,
        "get_course_by_id",
        AsyncMock(
            return_value=None if missing else SimpleNamespace(created_by=uuid4())
        ),
    )
    monkeypatch.setattr(
        keys.settings_crud,
        "get_settings",
        AsyncMock(return_value=SimpleNamespace(api_key_ciphertext="broken")),
    )
    monkeypatch.setattr(
        keys, "decrypt_api_key", Mock(side_effect=RuntimeError("private ciphertext"))
    )
    with pytest.raises(HTTPException) as caught:
        await keys.course_api_key(AsyncMock(), uuid4())
    assert caught.value.status_code == 503
    assert "private" not in caught.value.detail


@pytest.mark.parametrize(
    "method",
    ["complete_design", "complete_opening", "complete_object", "complete_reply"],
)
@pytest.mark.parametrize("status", [200, 402])
async def test_actual_provider_payload_preserves_model_and_teacher_key(
    monkeypatch, method, status
):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("server-secret"))
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            status,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"reply": "Why?", "goal_reached": False}
                            )
                        }
                    }
                ]
            },
        )

    client = OpenAIChatClient(transport=httpx.MockTransport(handler))
    kwargs = {
        "instructions": "rules",
        "material": "evidence",
        "model": "openai/gpt-4o-mini",
        "api_key": "teacher-secret",
    }
    if method == "complete_object":
        kwargs.update(name="class_summary", schema={"type": "object"})
    if status == 402:
        with pytest.raises(ModelCallError):
            await getattr(client, method)(**kwargs)
    else:
        await getattr(client, method)(**kwargs)
    assert len(seen) == 1
    assert seen[0].headers["authorization"] == "Bearer teacher-secret"
    assert json.loads(seen[0].content)["model"] == "openai/gpt-4o-mini"
    assert b"teacher-secret" not in seen[0].content
    assert b"server-secret" not in seen[0].content


async def test_summary_begin_pins_legacy_model_once_without_keys(monkeypatch):
    attempt = SimpleNamespace(
        status="pending", topic_id=uuid4(), request_json={"material": [], "labels": {}}
    )
    db = AsyncMock()
    db.__aenter__.return_value = db
    monkeypatch.setattr(summary_runner, "AsyncSessionLocal", lambda: db)
    monkeypatch.setattr(
        summary_runner.summary_crud, "get_attempt", AsyncMock(return_value=attempt)
    )
    monkeypatch.setattr(summary_runner.summary_crud, "mark_processing", AsyncMock())
    topic = SimpleNamespace(model_id="openai/gpt-4o-mini", content_language="en")
    lookup = AsyncMock(return_value=topic)
    monkeypatch.setattr(summary_runner.topic_crud, "get_topic_by_id", lookup)
    first = await summary_runner._begin(uuid4())
    topic.model_id = "different-model"
    second = await summary_runner._begin(uuid4())
    assert first["model_id"] == second["model_id"] == "openai/gpt-4o-mini"
    assert lookup.await_count == 1
    assert set(attempt.request_json) == {
        "material",
        "labels",
        "model_id",
        "content_language",
    }


@pytest.mark.parametrize("failure", [None, "key", "provider"])
async def test_summary_runner_uses_pinned_model_and_private_key(monkeypatch, failure):
    request = {
        "topic_id": uuid4(),
        "model_id": "openai/gpt-4o-mini",
        "material": [],
        "labels": {},
    }
    monkeypatch.setattr(summary_runner, "_begin", AsyncMock(return_value=request))
    monkeypatch.setattr(summary_runner, "refresh", AsyncMock())
    monkeypatch.setattr(
        summary_runner,
        "_api_key",
        AsyncMock(
            return_value="teacher-secret",
            side_effect=HTTPException(503) if failure == "key" else None,
        ),
    )
    provider = AsyncMock(
        return_value={},
        side_effect=ModelCallError(402) if failure == "provider" else None,
    )
    monkeypatch.setattr(
        summary_runner, "client", SimpleNamespace(complete_object=provider)
    )
    monkeypatch.setattr(
        summary_runner, "validate_summary", lambda *args: {"overview": "safe"}
    )
    ready, failed = AsyncMock(), AsyncMock()
    monkeypatch.setattr(summary_runner, "_ready", ready)
    monkeypatch.setattr(summary_runner, "_fail", failed)
    await summary_runner.run_summary(uuid4())
    if failure:
        failed.assert_awaited_once()
        ready.assert_not_awaited()
    else:
        failed.assert_not_awaited()
        ready.assert_awaited_once()
        assert "teacher-secret" not in str(ready.call_args)
    if failure == "key":
        provider.assert_not_awaited()
    else:
        assert provider.call_args.kwargs["model"] == request["model_id"]
        assert provider.call_args.kwargs["api_key"] == "teacher-secret"


@pytest.mark.parametrize(
    "runner,missing",
    [
        (report_runner, False),
        (report_runner, True),
        (summary_runner, False),
        (summary_runner, True),
    ],
)
async def test_background_key_lookup_uses_course_and_rejects_missing_topic(
    monkeypatch, runner, missing
):
    db = AsyncMock()
    db.__aenter__.return_value = db
    monkeypatch.setattr(runner, "AsyncSessionLocal", lambda: db)
    topic = SimpleNamespace(course_id=uuid4())
    if runner is report_runner:
        db.get.side_effect = [
            SimpleNamespace(topic_id=uuid4()),
            None if missing else topic,
        ]
    else:
        monkeypatch.setattr(
            runner.topic_crud,
            "get_topic_by_id",
            AsyncMock(return_value=None if missing else topic),
        )
    lookup = AsyncMock(return_value="teacher-secret")
    monkeypatch.setattr(runner, "course_api_key", lookup)
    if missing:
        with pytest.raises(ValueError):
            await runner._api_key(uuid4())
        lookup.assert_not_awaited()
    else:
        assert await runner._api_key(uuid4()) == "teacher-secret"
        lookup.assert_awaited_once_with(db, topic.course_id)
