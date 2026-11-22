"""Replay real, redacted Luna responses from the supplied synthetic dialogue."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.prompts import PromptStage, prompt_for
from app.services.dialogue import _model_http
from app.services.dialogue_progress import validate_progress
from app.services.dialogue_turn import StatusOut, _parse, catch_up_progress
from app.services.model_client import ModelCallError, _parse_completion, limits_for
from tests.unit.test_dialogue_turn import _topic

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ai_status"


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text(encoding="utf-8"))


def test_captured_1000_token_response_reproduces_backend_502():
    raw = fixture("truncated_1000")
    assert raw["choices"][0]["finish_reason"] == "length"
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw["choices"][0]["message"]["content"])
    with pytest.raises(ModelCallError) as caught:
        _parse_completion(httpx.Response(200, json=raw))
    assert caught.value.reason == "output_truncated"
    assert _model_http(caught.value).status_code == 502


def test_larger_budget_response_is_complete_and_evidence_valid():
    raw = fixture("complete_3000")
    result = _parse(StatusOut, _parse_completion(httpx.Response(200, json=raw)))
    assert not validate_progress(result.progress.model_dump(by_alias=True), 2).issues
    cap = prompt_for(PromptStage.STATUS).max_output_tokens
    assert (
        1000
        < raw["usage"]["completion_tokens"]
        <= cap
        <= limits_for("dialogue_status").max_tokens
    )


@pytest.mark.anyio
async def test_catchup_uses_configured_output_reserve_and_identifies_path(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="app.ai")
    raw = _parse_completion(httpx.Response(200, json=fixture("complete_3000")))
    client = type("Client", (), {"complete_object": AsyncMock(return_value=raw)})()
    from types import SimpleNamespace

    messages = [
        SimpleNamespace(sender="student", content="synthetic answer") for _ in range(2)
    ]
    prompt = prompt_for(PromptStage.STATUS)
    await catch_up_progress(
        client,
        prompt=prompt,
        topic=_topic(),
        messages=messages,
        model_id="openai/gpt-6-luna",
    )
    assert (
        client.complete_object.await_args.kwargs["max_tokens"]
        == prompt.max_output_tokens
    )
    assert "progress_catch_up_started" in caplog.text


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_larger_output_reserve_is_checked_before_dispatch(monkeypatch):
    from app.core.config import settings
    from app.services.dialogue_turn import STATUS_SCHEMA, _bounded_object
    from app.services.token_budget import ContextWindowExceeded, estimate_request_tokens

    prompt = prompt_for(PromptStage.STATUS)
    model = "openai/gpt-6-luna"
    material = "{}"
    input_tokens = estimate_request_tokens(
        model_id=model,
        instructions=prompt.instructions,
        material=material,
        schema=STATUS_SCHEMA,
    )
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TOKEN_BUDGET", input_tokens + 1000)
    client = type("Client", (), {"complete_object": AsyncMock()})()
    with pytest.raises(ContextWindowExceeded):
        await _bounded_object(
            client,
            name="dialogue_status",
            schema=STATUS_SCHEMA,
            instructions=prompt.instructions,
            material=material,
            model=model,
            max_tokens=prompt.max_output_tokens,
        )
    client.complete_object.assert_not_awaited()
