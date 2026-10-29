"""Unit tests for Redis login rate-limit helpers."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.core.auth_policies import LOGIN_RATE_LIMITED_DETAIL
from app.core.config import settings
from app.core.login_rate_limit import (
    begin_login_attempt,
    clear_login_failures,
)


class _MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, name: str) -> int:
        self.values[name] = self.values.get(name, 0) + 1
        return self.values[name]

    async def decr(self, name: str) -> int:
        self.values[name] = self.values.get(name, 0) - 1
        return self.values[name]

    async def expire(self, name: str, time: int) -> bool:
        if name in self.values:
            self.ttls[name] = time
            return True
        return False

    async def delete(self, *names: str) -> int:
        removed = 0
        for name in names:
            if name in self.values:
                del self.values[name]
                removed += 1
            self.ttls.pop(name, None)
        return removed

    async def ttl(self, name: str) -> int:
        if name not in self.values:
            return -2
        return self.ttls.get(name, -1)


def test_begin_and_clear_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)
    redis = _MemoryRedis()

    async def run() -> None:
        await begin_login_attempt(redis, account="Alice", client_ip="1.2.3.4")
        await begin_login_attempt(redis, account="alice", client_ip="1.2.3.4")
        assert redis.values["login:fail:account:alice"] == 2
        assert redis.values["login:fail:ip:1.2.3.4"] == 2
        assert redis.ttls["login:fail:account:alice"] == 60
        await clear_login_failures(redis, account="ALICE", client_ip="1.2.3.4")
        assert "login:fail:account:alice" not in redis.values
        # Success undoes this attempt's IP bump; prior failures remain.
        assert redis.values["login:fail:ip:1.2.3.4"] == 1

    asyncio.run(run())


def test_begin_raises_429_after_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 120)
    redis = _MemoryRedis()

    async def run() -> None:
        await begin_login_attempt(redis, account="bob", client_ip="10.0.0.1")
        await begin_login_attempt(redis, account="bob", client_ip="10.0.0.1")
        with pytest.raises(HTTPException) as exc:
            await begin_login_attempt(redis, account="bob", client_ip="10.0.0.1")
        assert exc.value.status_code == 429
        assert exc.value.detail == LOGIN_RATE_LIMITED_DETAIL
        assert exc.value.headers is not None
        assert exc.value.headers["Retry-After"] == "120"

    asyncio.run(run())


def test_ip_limit_blocks_other_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 90)
    redis = _MemoryRedis()

    async def run() -> None:
        await begin_login_attempt(redis, account="a", client_ip="9.9.9.9")
        await begin_login_attempt(redis, account="b", client_ip="9.9.9.9")
        with pytest.raises(HTTPException) as exc:
            await begin_login_attempt(redis, account="c", client_ip="9.9.9.9")
        assert exc.value.status_code == 429

    asyncio.run(run())


def test_begin_repairs_missing_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)
    redis = _MemoryRedis()
    redis.values["login:fail:account:x"] = 1
    # ttl missing (-1) must be repaired on bump

    async def run() -> None:
        await begin_login_attempt(redis, account="x", client_ip="1.1.1.1")
        assert redis.ttls["login:fail:account:x"] == 60

    asyncio.run(run())


def test_begin_fail_open_on_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 1)

    class _Broken:
        async def incr(self, name: str) -> int:
            raise ConnectionError("redis down")

        async def decr(self, name: str) -> int:
            raise ConnectionError("redis down")

        async def expire(self, name: str, time: int) -> bool:
            raise ConnectionError("redis down")

        async def delete(self, *names: str) -> int:
            raise ConnectionError("redis down")

        async def ttl(self, name: str) -> int:
            raise ConnectionError("redis down")

    async def run() -> None:
        await begin_login_attempt(_Broken(), account="z", client_ip="0.0.0.0")

    asyncio.run(run())
