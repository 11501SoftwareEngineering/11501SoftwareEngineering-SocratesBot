"""Synthetic reproductions distinguish failure causes without live calls or leaked content."""

import json
import logging
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.services import ai_diagnostics as diagnostics
from app.services.dialogue_turn import StatusOut, _parse
from app.services.model_client import ModelCallError, OpenAIChatClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def events(caplog):
    return [
        json.loads(record.message.split("ai_event ", 1)[1])
        for record in caplog.records
        if record.message.startswith("ai_event ")
    ]


@pytest.mark.parametrize("failure", ["length", "json", "schema", "http"])
async def test_log_pinpoints_status_call_and_reason_without_content(
    monkeypatch, caplog, failure
):
    caplog.set_level(logging.INFO, logger="app.ai")
    monkeypatch.setattr(settings, "AI_TRACE_ENABLED", False)
    private = "PRIVATE-STUDENT-TEXT"

    def handler(request):
        return httpx.Response(
            503 if failure == "http" else 200,
            json={
                "id": "gen-synthetic",
                "model": "openai/gpt-6-luna",
                "usage": {
                    "completion_tokens": 1000,
                    "completion_tokens_details": {"reasoning_tokens": 900},
                },
                "choices": [
                    {
                        "finish_reason": "length" if failure == "length" else "stop",
                        "message": {
                            "content": "{" if failure == "json" else "{}",
                            "reasoning": private,
                        },
                    }
                ],
            },
        )

    with (
        diagnostics.scope(http_request_id="test-http-request"),
        pytest.raises(ModelCallError) as caught,
    ):
        parsed = await OpenAIChatClient(
            transport=httpx.MockTransport(handler)
        ).complete_object(
            name="dialogue_status",
            schema={},
            instructions=private,
            material=private,
            api_key="sk-test-secret",
            model="openai/gpt-6-luna",
            max_tokens=1000,
        )
        _parse(StatusOut, parsed)
    expected = {
        "length": "output_truncated",
        "json": "invalid_output_json",
        "schema": "schema_validation",
        "http": "provider_error",
    }[failure]
    assert caught.value.reason == expected
    records = events(caplog)
    start = next(r for r in records if r["event"] == "call_started")
    response = next(r for r in records if r["event"] == "provider_response")
    error = next(r for r in records if r["event"] == "call_failed")
    assert start["max_output_tokens"] == 1000 and start["task"] == "dialogue_status"
    assert start["call_id"] == response["call_id"] == error["call_id"]
    assert (
        error["http_request_id"] == "test-http-request" and error["reason"] == expected
    )
    assert response["reasoning_tokens"] == 900 and response["completion_tokens"] == 1000
    assert private not in caplog.text and "sk-test-secret" not in caplog.text


async def test_raw_trace_opt_in_dev_only_redacts_credentials_and_reasoning(
    monkeypatch, tmp_path, caplog
):
    monkeypatch.setattr(diagnostics, "TRACE_DIR", tmp_path)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "AI_TRACE_ENABLED", False)
    response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": "synthetic visible reply",
                        "reasoning": "hidden reasoning",
                        "api_key": "sk-test-secret",
                    }
                }
            ],
            "sk-test-secret": "echoed key",
            "password": "password-value",
        },
    )
    diagnostics.write_trace(response, {}, "sk-test-secret")
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(settings, "AI_TRACE_ENABLED", True)
    diagnostics.write_trace(response, {}, "sk-test-secret")
    text = next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8")
    assert "synthetic visible reply" in text
    assert (
        "sk-test-secret" not in text
        and "hidden reasoning" not in text
        and "password-value" not in text
    )
    assert "synthetic visible reply" not in caplog.text
    before = len(list(tmp_path.iterdir()))
    monkeypatch.setattr(settings, "APP_ENV", "production")
    diagnostics.write_trace(response, {}, "sk-test-secret")
    assert len(list(tmp_path.iterdir())) == before
    assert next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8") == text


async def test_bad_provider_metadata_does_not_break_valid_completion(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRACE_ENABLED", False)

    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"finish_reason": {}, "message": {"content": "{}"}}]}
        )

    assert (
        await OpenAIChatClient(transport=httpx.MockTransport(handler)).complete_object(
            name="dialogue_status", schema={}, instructions="x", material="x"
        )
        == {}
    )


async def test_async_requests_and_jobs_have_separate_correlation():
    import asyncio

    captured = []

    @diagnostics.job_scope("report")
    async def job(ident):
        await asyncio.sleep(0)
        captured.append(dict(diagnostics._context.get()))

    a, b = uuid4(), uuid4()
    await asyncio.gather(job(a), job(b))
    assert {r["job_id"] for r in captured} == {str(a), str(b)}
    assert diagnostics._context.get() is None


def test_validation_log_does_not_echo_extra_field_text(caplog):
    caplog.set_level(logging.INFO, logger="app.ai")
    try:
        StatusOut.model_validate({"PRIVATE-STUDENT-TEXT": "private"})
    except ValidationError as exc:
        diagnostics.validation_failure("StatusOut", exc)
    assert "PRIVATE-STUDENT-TEXT" not in caplog.text and "extra_field" in caplog.text


def test_sql_logging_is_opt_in():
    assert type(settings).model_fields["SQL_ECHO"].default is False
