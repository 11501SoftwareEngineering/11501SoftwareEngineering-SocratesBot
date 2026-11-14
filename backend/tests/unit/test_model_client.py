"""Model client tests. Provider bodies and the key stay out of the log."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services.model_client import ModelCallError, OpenAIChatClient

pytestmark = pytest.mark.anyio

KEY = "sk-test-do-not-leak"
DIALOGUE = "dialogue-do-not-leak"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _client(handler) -> OpenAIChatClient:
    return OpenAIChatClient(transport=httpx.MockTransport(handler))


async def test_provider_error_logs_status_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(KEY))
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-test")
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx.Request) -> httpx.Response:
        assert KEY.encode() not in request.content
        assert request.headers["authorization"] == f"Bearer {KEY}"
        return httpx.Response(
            502,
            json={"error": {"message": KEY}, "echo": DIALOGUE},
        )

    with pytest.raises(ModelCallError) as caught:
        await _client(handler).complete_json(
            instructions="Write JSON", material=DIALOGUE
        )

    assert caught.value.status_code == 502
    assert str(caught.value) == "model call failed"
    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text
    assert "502" in caplog.text


async def test_refusal_is_not_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(KEY))
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-test")
    caplog.set_level(logging.DEBUG)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"refusal": f"{KEY} {DIALOGUE}"}}]},
        )

    with pytest.raises(ModelCallError):
        await _client(handler).complete_json(
            instructions="Write JSON", material=DIALOGUE
        )

    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text


def _completion(content: dict, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {"content": json.dumps(content)},
                }
            ]
        },
    )


async def test_retries_429_only_before_a_completion_body(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(KEY))
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-test")
    caplog.set_level(logging.DEBUG)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["authorization"] == f"Bearer {KEY}"
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"message": f"{KEY} {DIALOGUE}"}},
            )
        return _completion({"topic": "kept"})

    parsed = await _client(handler).complete_json(
        instructions="Write JSON", material=DIALOGUE
    )

    assert parsed == {"topic": "kept"}
    assert calls == 2
    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text


async def test_length_finish_is_failed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(KEY))
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-test")
    caplog.set_level(logging.DEBUG)

    def handler(_request: httpx.Request) -> httpx.Response:
        return _completion({"topic": DIALOGUE}, finish_reason="length")

    with pytest.raises(ModelCallError) as caught:
        await _client(handler).complete_json(
            instructions="Write JSON", material=DIALOGUE
        )

    assert caught.value.status_code == 200
    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text


async def test_retry_after_above_two_seconds_is_not_waited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr(KEY))
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-test")
    slept: list[float] = []

    async def instant(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", instant)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "30"})

    with pytest.raises(ModelCallError) as caught:
        await _client(handler).complete_json(
            instructions="Write JSON", material=DIALOGUE
        )

    assert caught.value.status_code == 429
    assert calls == 1
    assert slept == []
