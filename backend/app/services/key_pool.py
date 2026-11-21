"""Server OpenRouter keys, picked round-robin, with a cooldown per key and model.

State lives in this process only. No method awaits, so each call runs atomically
on the event loop. Keys never appear in a repr or a log; callers use the index.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Container, Iterable
from functools import lru_cache

from app.core.config import settings

# A provider can ask for a very long pause. A key cools at most one hour.
_MAX_COOLDOWN_SECONDS = 3600.0


def parse_keys(raw_keys: str) -> tuple[str, ...]:
    """Split the comma-separated keys. Blanks and repeats are dropped, order kept."""
    stripped = (raw.strip() for raw in raw_keys.split(","))
    return tuple(dict.fromkeys(key for key in stripped if key))


class KeyPool:
    def __init__(
        self, keys: Iterable[str], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._keys = tuple(keys)
        self._clock = clock
        self._cursor = 0
        self._cooling_until: dict[tuple[int, str], float] = {}

    def __repr__(self) -> str:
        return f"KeyPool(size={len(self._keys)})"

    def __len__(self) -> int:
        return len(self._keys)

    def pick(self, model: str, exclude: Container[int] = ()) -> tuple[int, str] | None:
        """Return the next (index, key) that is healthy for the model."""
        now = self._clock()
        size = len(self._keys)
        for step in range(size):
            index = (self._cursor + step) % size
            if index in exclude or not self._healthy(index, model, now):
                continue
            self._cursor = (index + 1) % size
            return index, self._keys[index]
        return None

    def cool(self, index: int, model: str, seconds: float) -> None:
        cooldown = min(max(seconds, 0.0), _MAX_COOLDOWN_SECONDS)
        self._cooling_until[(index, model)] = self._clock() + cooldown

    def any_healthy(self, model: str, exclude: Container[int] = ()) -> bool:
        now = self._clock()
        return any(
            index not in exclude and self._healthy(index, model, now)
            for index in range(len(self))
        )

    def _healthy(self, index: int, model: str, now: float) -> bool:
        until = self._cooling_until.get((index, model))
        return until is None or until <= now


@lru_cache(maxsize=1)
def _pool_for(keys: tuple[str, ...]) -> KeyPool:
    # One pool per process. A change to the configured keys builds a new pool.
    return KeyPool(keys)


def server_key_pool() -> KeyPool:
    return _pool_for(parse_keys(settings.OPENAI_API_KEYS.get_secret_value()))


def reset_server_key_pool() -> None:
    """Forget cooldowns and rebuild from settings on next use. For tests."""
    _pool_for.cache_clear()
