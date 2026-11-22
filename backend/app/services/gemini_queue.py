"""Shared Redis admission control, scoped by credential fingerprint and model.

Reservations count attempts conservatively, including failures. No keys or
student content enter Redis. Waiting is bounded by the caller's task deadline.
"""

import asyncio
import hashlib
import json
import math
import time
from contextlib import suppress
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.redis import redis_client

# Atomic sliding 60-second window across workers; daily bucket resets at PT
# midnight. Spacing requests prevents a full minute's allowance firing at once.
ADMIT = """
local now = redis.call('TIME')
local ms = now[1] * 1000 + math.floor(now[2] / 1000)
local cool = redis.call('PTTL', KEYS[3])
if cool > 0 then return cool end
if tonumber(redis.call('GET', KEYS[2]) or '0') >= tonumber(ARGV[3]) then
  return tonumber(ARGV[4]) * 1000
end
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ms - 60000)
local rows = redis.call('ZRANGE', KEYS[1], 0, -1, 'WITHSCORES')
local total = 0
for i=1,#rows,2 do total = total + tonumber(string.match(rows[i], ':(%d+)$')) end
if #rows > 0 then
  local last = tonumber(rows[#rows])
  local delay = math.ceil(60000 / tonumber(ARGV[1])) + 100 - (ms-last)
  if delay > 0 then return delay end
  if #rows/2 >= tonumber(ARGV[1]) or total+tonumber(ARGV[5]) > tonumber(ARGV[2]) then
    return math.max(1, tonumber(rows[2])+60001-ms)
  end
end
if tonumber(ARGV[5]) > tonumber(ARGV[2]) then return 60000 end
redis.call('ZADD', KEYS[1], ms, ARGV[6] .. ':' .. ARGV[5])
redis.call('PEXPIRE', KEYS[1], 61000)
redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], ARGV[4])
return 0
"""


class QueueUnavailable(Exception):
    def __init__(self, reason: str, retry_after: float = 5):
        self.reason = reason
        self.retry_after = max(1, math.ceil(retry_after))


def day_bucket():
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    seconds = math.ceil(midnight.timestamp() - now.timestamp())
    return now.date().isoformat(), max(1, seconds)


def scope(credential_id: str, model: str):
    digest = hashlib.sha256(f"{credential_id}:{model}".encode()).hexdigest()
    return f"gemini:{{{digest}}}"


def credential_scope(key: str):
    return "gemini:invalid:" + hashlib.sha256(key.encode()).hexdigest()


async def order_credentials(credentials, *, redis=None):
    """Round-robin successful stages too, shared across backend workers."""
    redis = redis if redis is not None else redis_client
    pool_id = hashlib.sha256(
        "|".join(sorted(slot for slot, _ in credentials)).encode()
    ).hexdigest()
    name = "gemini:rotation:" + pool_id
    try:
        cursor = await redis.incr(name)
        await redis.expire(name, 86400)
    except Exception:
        raise QueueUnavailable("gemini_queue_unavailable") from None
    offset = (cursor - 1) % len(credentials)
    return credentials[offset:] + credentials[:offset]


async def reserve(credentials, model, input_tokens, *, redis=None):
    redis = redis if redis is not None else redis_client
    ticket = uuid4().hex
    try:
        admitted = await redis.eval(
            "local t=redis.call('TIME'); local now=t[1]*1000+math.floor(t[2]/1000); "
            "redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',now-31000); "
            "if redis.call('ZCARD',KEYS[1])>=50 then return 0 end; "
            "redis.call('ZADD',KEYS[1],now,ARGV[1]); redis.call('EXPIRE',KEYS[1],32); return 1",
            1,
            "gemini:queue:waiting",
            ticket,
        )
        if not admitted:
            raise QueueUnavailable("gemini_quota_wait", 5)
    except QueueUnavailable:
        raise
    except Exception:
        raise QueueUnavailable("gemini_queue_unavailable") from None
    try:
        return await _reserve(credentials, model, input_tokens, redis=redis)
    finally:
        # Cancellation releases the waiting slot; the TTL also covers crashes.
        with suppress(Exception):
            await redis.zrem("gemini:queue:waiting", ticket)


async def _reserve(credentials, model, input_tokens, *, redis):
    deadline = time.monotonic() + settings.GEMINI_QUEUE_WAIT_SECONDS
    while True:
        date, reset_seconds = day_bucket()
        waits = []
        try:
            for project, key in credentials:
                invalid = await redis.ttl(credential_scope(key))
                if invalid > 0:
                    waits.append(float(invalid))
                    continue
                base = scope(project, model)
                wait_ms = await redis.eval(
                    ADMIT,
                    3,
                    base + ":minute",
                    base + ":day:" + date,
                    base + ":cool",
                    settings.GEMINI_RPM,
                    settings.GEMINI_TPM,
                    settings.GEMINI_RPD,
                    reset_seconds,
                    input_tokens,
                    uuid4().hex,
                )
                if not wait_ms:
                    return project, key
                waits.append(float(wait_ms) / 1000)
        except Exception:
            raise QueueUnavailable("gemini_queue_unavailable") from None
        delay = min(waits, default=60)
        if time.monotonic() + delay >= deadline:
            raise QueueUnavailable("gemini_quota_wait", delay)
        await asyncio.sleep(max(0.01, delay))


async def cool(project, key, model, response, *, redis=None):
    redis = redis if redis is not None else redis_client
    if response.status_code in {401, 403}:
        await redis.set(credential_scope(key), "1", ex=300)
        return 300
    seconds = 60.0
    with suppress(ValueError):
        seconds = float(response.headers.get("Retry-After", "60"))
    try:
        body = response.json()
        error = body.get("error", {})
        details = error.get("details", []) if isinstance(error, dict) else []
        for detail in details:
            if isinstance(detail, dict) and "retryDelay" in detail:
                seconds = float(str(detail["retryDelay"]).removesuffix("s"))
        # Daily quota errors must not be retried every minute.
        if any(
            word in json.dumps(error).lower() for word in ("perday", "per_day", "daily")
        ):
            seconds = day_bucket()[1]
    except (ValueError, TypeError, AttributeError):
        pass
    seconds = seconds if math.isfinite(seconds) and seconds > 0 else 60
    if response.status_code == 402:
        seconds = day_bucket()[1]
    # Do not shorten a cooldown established by another worker.
    base = scope(project, model) + ":cool"
    await redis.eval(
        "if redis.call('PTTL', KEYS[1]) < tonumber(ARGV[1]) then "
        "redis.call('SET', KEYS[1], '1', 'PX', ARGV[1]) end return 1",
        1,
        base,
        math.ceil(seconds * 1000),
    )
    return seconds
