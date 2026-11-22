"""Gemini's teacher-owned 1-3 key pool; no real model calls."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.gemini import GEMINI_MODEL
from app.schemas.teacher_ai_settings import ApiKeyRequest
from app.services import ai_usage, gemini_queue
from app.services.ai_usage import AttributedKey
from app.services.model_client import ModelCallError, OpenAIChatClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [429, 402, 401, 403])
async def test_owner_keys_failover_with_metering_and_fixed_google_route(
    monkeypatch, failure
):
    keys = tuple("AQ.synthetic-key-" + str(n) * 30 for n in range(3))
    key = AttributedKey(keys[0], uuid4(), "teacher")
    key.api_keys = keys
    begin, finish = AsyncMock(return_value=uuid4()), AsyncMock()
    monkeypatch.setattr(ai_usage, "begin", begin)
    monkeypatch.setattr(ai_usage, "finish", finish)
    monkeypatch.setattr(
        gemini_queue, "order_credentials", AsyncMock(side_effect=lambda v: v)
    )
    monkeypatch.setattr(
        gemini_queue, "reserve", AsyncMock(side_effect=lambda v, *_: v[0])
    )
    monkeypatch.setattr(gemini_queue, "cool", AsyncMock(return_value=20))
    sent = []

    def handle(request):
        sent.append(request)
        return (
            httpx.Response(failure)
            if len(sent) < 3
            else httpx.Response(
                200,
                json={
                    "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]
                },
            )
        )

    result = await OpenAIChatClient(httpx.MockTransport(handle)).complete_object(
        name="dialogue_status",
        schema={"type": "object"},
        instructions="test",
        material="test",
        model=GEMINI_MODEL,
        api_key=key,
        max_tokens=3000,
    )
    assert result == {} and len(sent) == 3
    assert begin.await_count == finish.await_count == 3
    assert all(call.args[0] is key for call in begin.await_args_list)
    for index, request in enumerate(sent):
        assert (
            str(request.url)
            == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        )
        assert request.headers["Authorization"] == "Bearer " + keys[index]
        body = json.loads(request.content)
        assert body["model"] == GEMINI_MODEL and body["max_tokens"] == 3000
        assert (
            body["reasoning_effort"] == "minimal"
            and body["response_format"]["json_schema"]["strict"]
        )


@pytest.mark.anyio
async def test_waiting_does_not_dispatch_or_meter(monkeypatch):
    monkeypatch.setattr(
        gemini_queue, "order_credentials", AsyncMock(side_effect=lambda v: v)
    )
    monkeypatch.setattr(
        gemini_queue,
        "reserve",
        AsyncMock(side_effect=gemini_queue.QueueUnavailable("gemini_quota_wait", 80)),
    )
    begin = AsyncMock()
    monkeypatch.setattr(ai_usage, "begin", begin)
    with pytest.raises(ModelCallError) as exc:
        await OpenAIChatClient(
            httpx.MockTransport(lambda _: pytest.fail("Unexpected dispatch"))
        ).complete_object(
            name="dialogue_status",
            schema={},
            instructions="test",
            material="test",
            model=GEMINI_MODEL,
            api_key="AQ.synthetic-not-a-real-key",
        )
    assert exc.value.status_code == 503 and exc.value.retry_after == 80
    begin.assert_not_called()


@pytest.mark.parametrize("prefix", ["AQ.", "AIza"])
def test_bundle_accepts_google_key_types_without_exposing_values(prefix):
    keys = [prefix + "synthetic-key-" + str(n) * 30 for n in range(3)]
    payload = ApiKeyRequest(api_keys=keys)
    assert payload.api_keys == keys
    assert keys[0] not in repr(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"api_keys": []},
        {"api_keys": ["x" * 20] * 2},
        {"api_keys": ["x" * 20, "y" * 20, "z" * 20, "a" * 20]},
        {"api_key": "x" * 20, "api_keys": ["y" * 20]},
        {"api_keys": ["x" * 20 + "\nunsafe"]},
    ],
)
def test_bad_key_bundles_are_rejected(payload):
    with pytest.raises(ValidationError):
        ApiKeyRequest(**payload)
