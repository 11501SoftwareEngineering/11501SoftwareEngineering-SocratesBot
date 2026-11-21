"""Deterministic provider failures: no credentials or paid calls required."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services import ai_diagnostics, ai_usage
from app.services.ai_usage import AttributedKey
from app.services.key_pool import KeyPool, _pool_for, cooldown_seconds, parse_keys
from app.services.model_client import ModelCallError, OpenAIChatClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(
        settings, "OPENAI_API_KEYS", SecretStr("alpha,beta,gamma,delta")
    )
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("legacy"))
    _pool_for.cache_clear()
    yield
    _pool_for.cache_clear()


def completion():
    return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})


async def call(client, key=None):
    return await client.complete_object(
        name="dialogue_status",
        schema={},
        instructions="Return JSON",
        material="test",
        api_key=key,
        model="openai/gpt-6-luna",
        max_tokens=3000,
    )


def test_deduplication_and_secrets_not_in_repr():
    assert parse_keys(" a, b,a, ,b, c ") == ("a", "b", "c")
    assert repr(KeyPool(("secret-value",))) == "KeyPool(size=1)"


def test_round_robin_exclusions_expiry_and_cooldown_never_shortens():
    now = [0]
    pool = KeyPool(("a", "b"), lambda: now[0])
    assert pool.pick(set()) == (0, "a")
    pool.cool(0, 10000)
    pool.cool(0, 2)
    assert pool.pick({1}) is None
    now[0] = 9999
    assert pool.pick({1}) is None
    now[0] = 10000
    assert pool.pick({1}) == (0, "a")
    assert pool.pick(set()) == (1, "b")


def test_thread_safe_round_robin():
    pool = KeyPool(("a", "b", "c"))
    with ThreadPoolExecutor(max_workers=8) as executor:
        picks = list(executor.map(lambda _: pool.pick(set())[0], range(300)))
    assert [picks.count(i) for i in range(3)] == [100, 100, 100]


@pytest.mark.parametrize("raw", [None, "bad", "NaN", "inf", "-1", "1e999"])
def test_invalid_retry_after_uses_status_default(raw):
    assert cooldown_seconds(429, raw) == 60
    assert cooldown_seconds(402, raw) == 300


def test_numeric_and_date_retry_after():
    assert cooldown_seconds(429, "0") == 0
    assert cooldown_seconds(429, "99999") == 99999
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=120))
    assert 118 <= cooldown_seconds(429, future) <= 120


@pytest.mark.anyio
@pytest.mark.parametrize("failed_status", [429, 402])
async def test_failover_same_payload_metered_and_attributed(monkeypatch, failed_status):
    begin = AsyncMock(side_effect=[uuid4(), uuid4()])
    finish = AsyncMock()
    monkeypatch.setattr(ai_usage, "begin", begin)
    monkeypatch.setattr(ai_usage, "finish", finish)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(failed_status) if len(requests) == 1 else completion()

    key = AttributedKey("legacy", uuid4(), "server")
    await call(OpenAIChatClient(transport=httpx.MockTransport(handler)), key)
    assert [r.headers["Authorization"] for r in requests] == [
        "Bearer alpha",
        "Bearer beta",
    ]
    assert requests[0].content == requests[1].content
    assert json.loads(requests[0].content)["model"] == "openai/gpt-6-luna"
    assert all(
        c.args == (key, "dialogue_status", "openai/gpt-6-luna")
        for c in begin.call_args_list
    )
    assert finish.await_count == 2
    assert [c.args[1].status_code for c in finish.call_args_list] == [
        failed_status,
        200,
    ]


@pytest.mark.anyio
async def test_rotation_shared_across_client_instances():
    seen = []

    def handler(request):
        seen.append(request.headers["Authorization"])
        return completion()

    clients = [
        OpenAIChatClient(transport=httpx.MockTransport(handler)) for _ in range(8)
    ]
    await asyncio.gather(*(call(client) for client in clients))
    assert sorted(seen) == sorted(
        [f"Bearer {s}" for s in ("alpha", "beta", "gamma", "delta")] * 2
    )


@pytest.mark.anyio
@pytest.mark.parametrize("size", [1, 2, 4])
async def test_attempts_bounded_no_repeat_all_cooling_rejects_without_dispatch(
    monkeypatch, size
):
    monkeypatch.setattr(settings, "OPENAI_API_KEYS", SecretStr(",".join("abcd"[:size])))
    seen = []

    def handler(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(429, headers={"Retry-After": "99999"})

    client = OpenAIChatClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelCallError) as caught:
        await call(client)
    assert caught.value.status_code == 429
    assert len(seen) == min(size, 3)
    assert len(set(seen)) == len(seen)
    if size == 4:
        with pytest.raises(ModelCallError):
            await call(client)
    before = len(seen)
    with pytest.raises(ModelCallError) as caught:
        await call(client)
    assert caught.value.reason == "no_healthy_server_key"
    assert len(seen) == before


@pytest.mark.anyio
@pytest.mark.parametrize("code", [400, 401, 403, 500, 502, 503])
async def test_other_errors_do_not_rotate(code):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(code, headers={"Retry-After": "0"})

    with pytest.raises(ModelCallError):
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))
    assert len(seen) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("key_kind", ["plain", "teacher"])
@pytest.mark.parametrize("code", [402, 429])
async def test_teacher_or_explicit_key_never_uses_pool(key_kind, code):
    key = (
        "personal"
        if key_kind == "plain"
        else AttributedKey("personal", uuid4(), "teacher")
    )
    seen = []

    def handler(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(code)

    # Avoid database access for synthetic attribution.
    from unittest.mock import patch

    with (
        patch.object(ai_usage, "begin", AsyncMock(return_value=None)),
        pytest.raises(ModelCallError),
    ):
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)), key)
    assert seen == ["Bearer personal"]


@pytest.mark.anyio
async def test_empty_pool_uses_legacy_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEYS", SecretStr(" , , "))

    def handler(request):
        assert request.headers["Authorization"] == "Bearer legacy"
        return completion()

    await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))


@pytest.mark.anyio
async def test_transport_failure_not_replayed_and_metering_finished(monkeypatch):
    finish = AsyncMock()
    monkeypatch.setattr(ai_usage, "finish", finish)
    seen = []

    def handler(request):
        seen.append(request)
        raise httpx.ReadError("uncertain whether provider received request")

    with pytest.raises(ModelCallError) as caught:
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))
    assert caught.value.reason == "transport_error"
    assert len(seen) == 1
    finish.assert_awaited_once_with(None, None)


@pytest.mark.anyio
async def test_metering_failure_prevents_dispatch(monkeypatch):
    monkeypatch.setattr(
        ai_usage, "begin", AsyncMock(side_effect=RuntimeError("db down"))
    )

    def handler(request):
        pytest.fail("must not dispatch without durable accounting")

    with pytest.raises(ModelCallError) as caught:
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))
    assert caught.value.reason == "usage_record_start_failed"


@pytest.mark.anyio
async def test_bad_success_body_is_not_replayed():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{"}}]})

    with pytest.raises(ModelCallError) as caught:
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))
    assert caught.value.reason == "invalid_output_json"
    assert len(seen) == 1


@pytest.mark.anyio
async def test_call_deadline_is_shared_and_not_restarted_on_failover(monkeypatch):
    from app.services import model_client

    original_timeout = asyncio.timeout
    deadlines = []

    def capture_timeout(seconds):
        deadline = original_timeout(seconds)
        deadlines.append(deadline)
        return deadline

    monkeypatch.setattr(model_client.asyncio, "timeout", capture_timeout)
    finish = AsyncMock()
    monkeypatch.setattr(ai_usage, "finish", finish)
    seen = []

    async def handler(request):
        seen.append(request)
        if len(seen) == 2:
            assert len(deadlines) == 1
            # Expire the actual encompassing deadline deterministically,
            # independent of scheduling/CPU load on Windows or in CI.
            deadlines[0].reschedule(asyncio.get_running_loop().time())
            await asyncio.Event().wait()
        return httpx.Response(429)

    with pytest.raises(model_client.ModelTimeoutError):
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))
    assert len(seen) == 2
    assert len(deadlines) == 1
    assert finish.await_count == 2
    assert finish.call_args_list[-1].args[1] is None


@pytest.mark.anyio
async def test_cooling_key_skipped_on_later_call_until_expiry(monkeypatch):
    from app.services import model_client

    now = [0]
    pool = KeyPool(("one", "two"), lambda: now[0])
    monkeypatch.setattr(model_client, "server_key_pool", lambda: pool)
    seen = []

    def handler(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(402) if len(seen) == 1 else completion()

    client = OpenAIChatClient(transport=httpx.MockTransport(handler))
    await call(client)
    await call(client)
    now[0] = 300
    await call(client)
    assert seen == ["Bearer one", "Bearer two", "Bearer two", "Bearer one"]


@pytest.mark.anyio
async def test_logs_and_traces_redact_entire_pool(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "AI_TRACE_ENABLED", True)
    monkeypatch.setattr(ai_diagnostics, "TRACE_DIR", tmp_path)
    caplog.set_level(logging.INFO, logger="app.ai")

    def handler(request):
        return httpx.Response(
            402, json={"error": {"message": "alpha beta gamma delta legacy"}}
        )

    with pytest.raises(ModelCallError):
        await call(OpenAIChatClient(transport=httpx.MockTransport(handler)))
    output = caplog.text + "".join(
        p.read_text(encoding="utf-8") for p in tmp_path.glob("*.jsonl")
    )
    for secret in ("alpha", "beta", "gamma", "delta", "legacy"):
        assert secret not in output
    assert "server_key_cooling" in caplog.text
