"""Process-local server credentials. Never log or expose their values."""

import math
import threading
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache

from app.core.config import settings


def parse_keys(raw: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(key.strip() for key in raw.split(",") if key.strip()))


def cooldown_seconds(status: int, retry_after: str | None) -> float:
    default = 300.0 if status == 402 else 60.0
    if retry_after is None:
        return default
    try:
        seconds = float(retry_after)
    except ValueError:
        try:
            deadline = parsedate_to_datetime(retry_after)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            seconds = (deadline - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return default
    return seconds if math.isfinite(seconds) and seconds >= 0 else default


class KeyPool:
    def __init__(self, keys: tuple[str, ...], clock=time.monotonic):
        self._keys = keys
        self._clock = clock
        self._cursor = 0
        self._until = [0.0] * len(keys)
        self._lock = threading.Lock()

    def __repr__(self):
        return f"KeyPool(size={len(self)})"

    def __len__(self):
        return len(self._keys)

    def pick(self, exclude: set[int]) -> tuple[int, str] | None:
        with self._lock:
            now = self._clock()
            for step in range(len(self)):
                index = (self._cursor + step) % len(self)
                if index not in exclude and self._until[index] <= now:
                    self._cursor = (index + 1) % len(self)
                    return index, self._keys[index]
        return None

    def cool(self, index: int, seconds: float):
        with self._lock:
            self._until[index] = max(self._until[index], self._clock() + seconds)


@lru_cache(maxsize=1)
def _pool_for(keys: tuple[str, ...]) -> KeyPool:
    return KeyPool(keys)


def server_key_pool() -> KeyPool | None:
    keys = parse_keys(settings.OPENAI_API_KEYS.get_secret_value())
    return _pool_for(keys) if keys else None
