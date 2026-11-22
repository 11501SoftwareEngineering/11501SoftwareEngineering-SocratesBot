"""Exercise real atomic Redis scripts using disposable project/model scopes."""

import asyncio
from uuid import uuid4

import httpx
import pytest
from redis.asyncio import Redis

from app.core.config import settings
from app.services import gemini_queue as queue

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def redis():
    client = Redis.from_url(
        settings.REDIS_URL.get_secret_value(), decode_responses=True
    )
    await client.ping()
    yield client
    await client.aclose()


@pytest.fixture
async def isolated(redis):
    model = "test-gemini-" + uuid4().hex
    projects = ["project-" + uuid4().hex for _ in range(3)]
    yield model, projects
    keys = []
    for project in projects:
        keys.extend(
            [key async for key in redis.scan_iter(queue.scope(project, model) + ":*")]
        )
    if keys:
        await redis.delete(*keys)


async def test_atomic_spacing_and_failover_across_concurrent_requests(
    redis, isolated, monkeypatch
):
    model, projects = isolated
    monkeypatch.setattr(settings, "GEMINI_QUEUE_WAIT_SECONDS", 0)
    credentials = [(p, "test-key-" + p) for p in projects]

    async def attempt():
        try:
            return await queue.reserve(credentials, model, 100, redis=redis)
        except queue.QueueUnavailable:
            return None

    results = await asyncio.gather(*(attempt() for _ in range(12)))
    admitted = [p for p in results if p]
    assert len(admitted) == 3
    assert len({p[0] for p in admitted}) == 3
    date, _ = queue.day_bucket()
    for project in projects:
        assert await redis.get(queue.scope(project, model) + ":day:" + date) == "1"


async def test_same_project_key_rotation_cannot_reset_daily_budget(
    redis, isolated, monkeypatch
):
    model, projects = isolated
    monkeypatch.setattr(settings, "GEMINI_RPD", 1)
    monkeypatch.setattr(settings, "GEMINI_QUEUE_WAIT_SECONDS", 0)
    assert await queue.reserve([(projects[0], "first")], model, 100, redis=redis)
    with pytest.raises(queue.QueueUnavailable) as exc:
        await queue.reserve([(projects[0], "second")], model, 100, redis=redis)
    assert exc.value.reason == "gemini_quota_wait"
    assert exc.value.retry_after > 60


async def test_tokens_cooldown_and_longer_existing_retry_are_enforced(
    redis, isolated, monkeypatch
):
    model, projects = isolated
    monkeypatch.setattr(settings, "GEMINI_QUEUE_WAIT_SECONDS", 0)
    monkeypatch.setattr(settings, "GEMINI_TPM", 1024)
    with pytest.raises(queue.QueueUnavailable):
        await queue.reserve([(projects[0], "first")], model, 1025, redis=redis)
    response = httpx.Response(429, headers={"Retry-After": "120"})
    await queue.cool(projects[0], "first", model, response, redis=redis)
    await queue.cool(
        projects[0],
        "first",
        model,
        httpx.Response(429, headers={"Retry-After": "3"}),
        redis=redis,
    )
    assert await redis.ttl(queue.scope(projects[0], model) + ":cool") > 110
    result = await queue.reserve(
        [(projects[0], "first"), (projects[1], "second")], model, 100, redis=redis
    )
    assert result[0] == projects[1]


async def test_retry_details_and_daily_cooldown(redis, isolated):
    model, projects = isolated
    await queue.cool(
        projects[0],
        "key",
        model,
        httpx.Response(429, json={"error": {"details": [{"retryDelay": "8.28s"}]}}),
        redis=redis,
    )
    assert 7 <= await redis.ttl(queue.scope(projects[0], model) + ":cool") <= 9
    await queue.cool(
        projects[1],
        "key",
        model,
        httpx.Response(
            429, json={"error": {"message": "RequestsPerDay quota exceeded"}}
        ),
        redis=redis,
    )
    assert (
        abs(
            await redis.ttl(queue.scope(projects[1], model) + ":cool")
            - queue.day_bucket()[1]
        )
        <= 2
    )


async def test_round_robin_order_is_shared_and_cycles(redis, isolated):
    import hashlib

    _, projects = isolated
    credentials = [(p, "synthetic-" + p) for p in projects]
    rotation = (
        "gemini:rotation:"
        + hashlib.sha256("|".join(sorted(projects)).encode()).hexdigest()
    )
    try:
        orders = [
            await queue.order_credentials(credentials, redis=redis) for _ in range(4)
        ]
        assert [order[0][0] for order in orders] == [
            projects[0],
            projects[1],
            projects[2],
            projects[0],
        ]
    finally:
        await redis.delete(rotation)
