"""Server key pool tests. Keys rotate, and a cooldown holds per model."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services.key_pool import KeyPool, parse_keys, server_key_pool

MODEL = "model-x"
OTHER = "model-y"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_parse_trims_and_drops_blanks_and_repeats() -> None:
    assert parse_keys("a, b,,a , c") == ("a", "b", "c")


def test_parse_keeps_a_single_key() -> None:
    assert parse_keys(" k ") == ("k",)


def test_parse_of_nothing_is_empty() -> None:
    assert parse_keys("") == ()
    assert parse_keys(" , ") == ()


def test_picks_rotate_round_robin() -> None:
    pool = KeyPool(["A", "B"])

    assert pool.pick(MODEL) == (0, "A")
    assert pool.pick(MODEL) == (1, "B")
    assert pool.pick(MODEL) == (0, "A")


def test_a_cooled_key_is_skipped_for_its_model() -> None:
    pool = KeyPool(["A", "B"], clock=Clock())
    pool.cool(0, MODEL, 30)

    assert pool.pick(MODEL) == (1, "B")
    assert pool.pick(MODEL) == (1, "B")


def test_a_cooled_key_still_serves_another_model() -> None:
    pool = KeyPool(["A", "B"], clock=Clock())
    pool.cool(0, MODEL, 30)

    assert pool.pick(OTHER) == (0, "A")


def test_a_key_returns_after_its_cooldown() -> None:
    clock = Clock()
    pool = KeyPool(["A"], clock=clock)
    pool.cool(0, MODEL, 60)

    assert pool.pick(MODEL) is None
    clock.now += 61
    assert pool.pick(MODEL) == (0, "A")


def test_cooldown_is_capped_at_one_hour() -> None:
    clock = Clock()
    pool = KeyPool(["A"], clock=clock)
    pool.cool(0, MODEL, 7200)

    clock.now += 3599
    assert pool.pick(MODEL) is None
    clock.now += 2
    assert pool.pick(MODEL) == (0, "A")


def test_excluded_keys_are_not_picked() -> None:
    pool = KeyPool(["A", "B"])

    assert pool.pick(MODEL, exclude={0}) == (1, "B")
    assert pool.pick(MODEL, exclude={0, 1}) is None


def test_no_healthy_key_when_all_cool() -> None:
    pool = KeyPool(["A", "B"], clock=Clock())
    pool.cool(0, MODEL, 30)
    assert pool.any_healthy(MODEL)

    pool.cool(1, MODEL, 30)
    assert not pool.any_healthy(MODEL)
    assert pool.pick(MODEL) is None
    assert pool.any_healthy(OTHER)


def test_empty_pool_picks_nothing() -> None:
    pool = KeyPool([])

    assert len(pool) == 0
    assert pool.pick(MODEL) is None
    assert not pool.any_healthy(MODEL)


def test_representation_hides_the_keys() -> None:
    pool = KeyPool(["sk-secret-one", "sk-secret-two"])

    assert "sk-secret" not in repr(pool)
    assert "sk-secret" not in str(pool)
    assert "2" in repr(pool)


def test_shared_pool_follows_the_configured_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEYS", SecretStr("a,b,c"))

    first = server_key_pool()
    assert server_key_pool() is first
    assert len(first) == 3

    monkeypatch.setattr(settings, "OPENAI_API_KEYS", SecretStr("c"))
    second = server_key_pool()
    assert second is not first
    assert len(second) == 1
