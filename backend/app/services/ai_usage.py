"""Durable provider metering without secrets, content or estimated prices."""

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.enums import AiUsageStage
from app.models.ai_usage import AiUsageEvent
from app.schemas.ai_usage import AiStageUsage, AiUsageResponse

logger = logging.getLogger("app.model")


class AttributedKey(str):
    """Internal credential metadata. Only its string value goes to the provider."""

    def __new__(cls, value: str, teacher_id: UUID, source: str):
        obj = super().__new__(cls, value)
        obj.teacher_id = teacher_id
        obj.source = source
        return obj


def task_stage(name: str) -> str:
    if name.startswith("inquiry_"):
        return "setup"
    if name.startswith("dialogue_"):
        return "dialogue"
    if name == "personal_report":
        return "report"
    if name == "class_summary":
        return "summary"
    raise ValueError("Unmapped AI task")


async def begin(key: str | None, task: str, model_id: str) -> UUID | None:
    if not isinstance(key, AttributedKey):
        return None
    async with AsyncSessionLocal() as db:
        row = AiUsageEvent(
            teacher_id=key.teacher_id,
            stage=task_stage(task),
            task=task,
            model_id=model_id,
            credential_source=key.source,
        )
        db.add(row)
        await db.commit()
        return row.id


def usage_fields(response: httpx.Response | None) -> dict:
    fields = {"http_status": None if response is None else response.status_code}
    try:
        body = response.json() if response is not None else {}
        usage = body.get("usage", {}) if isinstance(body, dict) else {}
        if not isinstance(usage, dict):
            return fields
        for target, original in (
            ("input_tokens", "prompt_tokens"),
            ("output_tokens", "completion_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            value = usage.get(original)
            if type(value) is int and 0 <= value <= 2**63 - 1:
                fields[target] = value
        value = usage.get("cost")
        if type(value) in (int, float, str):
            cost = Decimal(str(value))
            if cost.is_finite() and 0 <= cost < 100_000_000:
                fields["cost_usd"] = cost
    except (ValueError, TypeError, InvalidOperation):
        pass
    return fields


async def finish(event_id: UUID | None, response: httpx.Response | None) -> None:
    if event_id is None:
        return
    # A missing completion write leaves a durable unknown row, never false zeros.
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AiUsageEvent)
                .where(AiUsageEvent.id == event_id)
                .values(finished_at=datetime.now(UTC), **usage_fields(response))
            )
            await db.commit()
    except Exception:
        logger.error("ai_usage_completion_unavailable event_id=%s", event_id)


def aggregate(rows, month: str) -> AiUsageResponse:
    def totals(selected):
        result = {"request_count": len(selected)}
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            values = [getattr(row, field) for row in selected]
            result[field] = sum(values) if all(v is not None for v in values) else None
        costs = [row.cost_usd for row in selected]
        result["cost_usd"] = (
            float(sum(costs)) if costs and all(v is not None for v in costs) else None
        )
        return result

    combined = totals(rows)
    return AiUsageResponse(
        month=month,
        **combined,
        cost_source="openrouter" if combined["cost_usd"] is not None else None,
        updated_at=max(
            (row.finished_at or row.started_at for row in rows), default=None
        ),
        by_stage=[
            AiStageUsage(
                stage=stage, **totals([row for row in rows if row.stage == stage.value])
            )
            for stage in AiUsageStage
        ],
    )


async def read_month(
    db: AsyncSession, teacher_id: UUID, *, now: datetime | None = None
) -> AiUsageResponse:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    rows = list(
        await db.scalars(
            select(AiUsageEvent).where(
                AiUsageEvent.teacher_id == teacher_id,
                AiUsageEvent.started_at >= start,
                AiUsageEvent.started_at < end,
            )
        )
    )
    return aggregate(rows, start.strftime("%Y-%m"))
