"""Redis-backed login brute-force limits (per account).

Fail-open: Redis errors skip enforcement so login stays available when Redis is down.
"""

from __future__ import annotations

import logging
from typing import Protocol

from fastapi import HTTPException, status

from app.core.auth_policies import LOGIN_RATE_LIMITED_DETAIL
from app.core.config import settings

logger = logging.getLogger(__name__)

_ACCOUNT_KEY = "login:fail:account:{account}"


class RedisCounter(Protocol):
    async def incr(self, name: str) -> int: ...

    async def decr(self, name: str) -> int: ...

    async def expire(self, name: str, time: int) -> bool | int: ...

    async def delete(self, *names: str) -> int: ...

    async def ttl(self, name: str) -> int: ...


def _account_key(account: str) -> str:
    return _ACCOUNT_KEY.format(account=account)


async def _bump(redis: RedisCounter, key: str, window: int) -> int:
    """INCR and ensure a TTL exists (repairs keys that lost expire)."""
    count = await redis.incr(key)
    ttl = await redis.ttl(key)
    if ttl < 0:
        await redis.expire(key, window)
    return count


async def begin_login_attempt(
    redis: RedisCounter,
    *,
    account: str,
) -> None:
    """Reserve one attempt (INCR account); raise 429 when it exceeds max.

    Counts the in-flight attempt before password verify so concurrent callers
    cannot all observe an under-limit snapshot. Redis errors fail open.
    """
    max_attempts = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    account_key = _account_key(account)

    try:
        account_count = await _bump(redis, account_key, window)
    except Exception:
        logger.warning("login rate-limit begin failed; allowing attempt", exc_info=True)
        return

    if account_count <= max_attempts:
        return

    retry_after = 1
    try:
        ttl = await redis.ttl(account_key)
        if ttl > retry_after:
            retry_after = ttl
    except Exception:
        logger.warning("login rate-limit ttl read failed", exc_info=True)

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=LOGIN_RATE_LIMITED_DETAIL,
        headers={"Retry-After": str(retry_after)},
    )


async def clear_login_failures(
    redis: RedisCounter,
    *,
    account: str,
) -> None:
    """After success: wipe account counter.

    Redis errors fail open (success path continues).
    """
    try:
        await redis.delete(_account_key(account))
    except Exception:
        logger.warning("login rate-limit clear failed; continuing", exc_info=True)
