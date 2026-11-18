"""Schemas for GET /users/me/ai/usage."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import AiUsageStage


class AiStageUsage(BaseModel):
    stage: AiUsageStage
    request_count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = Field(default=None, description="null = no priced data")


class AiUsageResponse(BaseModel):
    month: str = Field(examples=["2026-11"])
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    cost_usd: float | None = Field(default=None, description="null = no priced data")
    cost_source: str | None = None
    updated_at: datetime | None = None
    by_stage: list[AiStageUsage]
