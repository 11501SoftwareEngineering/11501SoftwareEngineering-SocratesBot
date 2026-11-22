"""Actual provider attempts, unknown values, retries and current-month aggregation."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.services import ai_usage
from app.services.ai_usage import AttributedKey, aggregate, usage_fields
from app.services.model_client import ModelCallError, OpenAIChatClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def row(stage="dialogue", **overrides):
    return SimpleNamespace(
        stage=stage,
        input_tokens=10,
        output_tokens=3,
        total_tokens=13,
        cost_usd=Decimal("0.0001"),
        finished_at=datetime(2026, 11, 21, tzinfo=UTC),
        started_at=datetime(2026, 11, 21, tzinfo=UTC),
        **overrides,
    )


def test_empty_month_has_zero_tokens_but_no_priced_cost():
    body = aggregate([], "2026-11")
    assert body.request_count == 0 and body.total_tokens == 0 and body.cost_usd is None
    assert [r.stage for r in body.by_stage] == [
        "setup",
        "dialogue",
        "report",
        "summary",
    ]
    assert body.updated_at is None


def test_stage_aggregation_and_unknown_are_not_fabricated_zero():
    a, b = row(), row("report")
    b.cost_usd = None
    b.input_tokens = None
    b.total_tokens = None
    result = aggregate([a, b], "2026-11")
    assert result.request_count == 2 and result.output_tokens == 6
    assert (
        result.input_tokens is None
        and result.total_tokens is None
        and result.cost_usd is None
    )
    assert result.by_stage[1].cost_usd == 0.0001 and result.by_stage[2].cost_usd is None
    a.cost_usd = b.cost_usd = Decimal(0)
    assert aggregate([a, b], "2026-11").cost_usd == 0.0


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {
            "prompt_tokens": -1,
            "completion_tokens": True,
            "total_tokens": "13",
            "cost": "NaN",
        },
        {"cost": "Infinity"},
        [],
    ],
)
def test_bad_or_missing_usage_remains_unknown(usage):
    fields = usage_fields(httpx.Response(200, json={"usage": usage}))
    assert fields == {"http_status": 200}


def test_usage_uses_actual_account_charge_not_upstream_or_catalog_estimates():
    fields = usage_fields(
        httpx.Response(
            200,
            json={
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 5,
                    "total_tokens": 16,
                    "cost": 0,
                    "cost_details": {"upstream_inference_cost": 9},
                }
            },
        )
    )
    assert fields["cost_usd"] == 0 and fields["total_tokens"] == 16
    assert usage_fields(httpx.Response(502, text="private failure")) == {
        "http_status": 502
    }


@pytest.mark.parametrize(
    "task,stage",
    [
        ("inquiry_setup", "setup"),
        ("inquiry_opening", "setup"),
        ("dialogue_context_summary", "dialogue"),
        ("dialogue_validity", "dialogue"),
        ("dialogue_status", "dialogue"),
        ("dialogue_planning", "dialogue"),
        ("personal_report", "report"),
        ("class_summary", "summary"),
    ],
)
def test_all_model_tasks_have_a_usage_stage(task, stage):
    assert ai_usage.task_stage(task) == stage


async def test_retries_each_recorded_even_when_success_output_cannot_parse(monkeypatch):
    key = AttributedKey("sk-test-private", uuid4(), "teacher")
    ids = [uuid4(), uuid4()]
    begin, finish = AsyncMock(side_effect=ids), AsyncMock()
    monkeypatch.setattr(ai_usage, "begin", begin)
    monkeypatch.setattr(ai_usage, "finish", finish)
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"message": "private"}},
            )
        return httpx.Response(
            200,
            json={
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 1000,
                    "total_tokens": 1004,
                    "cost": 0.01,
                },
                "choices": [{"finish_reason": "length", "message": {"content": "{}"}}],
            },
        )

    client = OpenAIChatClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelCallError):
        await client.complete_object(
            name="dialogue_status",
            schema={},
            instructions="private",
            material="private",
            model="test-model",
            api_key=key,
        )
    assert begin.await_count == finish.await_count == 2
    assert begin.await_args.args == (key, "dialogue_status", "test-model")
    assert finish.await_args.args[0] == ids[1]
    assert usage_fields(finish.await_args.args[1])["total_tokens"] == 1004


async def test_start_write_failure_stops_before_provider_call(monkeypatch):
    monkeypatch.setattr(ai_usage, "begin", AsyncMock(side_effect=RuntimeError("db")))
    dispatched = False

    def handler(request):
        nonlocal dispatched
        dispatched = True
        return httpx.Response(200, json={})

    with pytest.raises(ModelCallError) as caught:
        await OpenAIChatClient(transport=httpx.MockTransport(handler)).complete_object(
            name="dialogue_status",
            schema={},
            instructions="x",
            material="x",
            model="openai/gpt-6-luna",
        )
    assert caught.value.status_code == 503 and not dispatched


async def test_transport_failure_keeps_unknown_attempt(monkeypatch):
    ident = uuid4()
    monkeypatch.setattr(ai_usage, "begin", AsyncMock(return_value=ident))
    finish = AsyncMock()
    monkeypatch.setattr(ai_usage, "finish", finish)

    def handler(request):
        raise httpx.ConnectError("private", request=request)

    with pytest.raises(ModelCallError):
        await OpenAIChatClient(transport=httpx.MockTransport(handler)).complete_object(
            name="dialogue_status",
            schema={},
            instructions="x",
            material="x",
            model="openai/gpt-6-luna",
        )
    finish.assert_awaited_once_with(ident, None)


async def test_read_month_filters_owner_and_excludes_next_utc_month():
    teacher_id = uuid4()
    db = AsyncMock()
    db.scalars.return_value = []
    await ai_usage.read_month(
        db, teacher_id, now=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)
    )
    values = db.scalars.await_args.args[0].compile().params.values()
    assert teacher_id in values
    assert (
        datetime(2026, 12, 1, tzinfo=UTC) in values
        and datetime(2027, 1, 1, tzinfo=UTC) in values
    )


async def test_completion_write_failure_does_not_recall_provider_or_expose_body(
    monkeypatch, caplog
):
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.execute.side_effect = RuntimeError("private-secret")
    monkeypatch.setattr(ai_usage, "AsyncSessionLocal", lambda: db)
    await ai_usage.finish(uuid4(), httpx.Response(200, json={"usage": {"cost": 0.3}}))
    assert "ai_usage_completion_unavailable" in caplog.text
    assert "private-secret" not in caplog.text
