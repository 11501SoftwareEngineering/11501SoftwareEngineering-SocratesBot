"""Current UTC month usage; unknown counts/cost are null, not fabricated zeros."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import AiUsageStage


class AiStageUsage(BaseModel):
    stage: AiUsageStage
    request_count: int = 0
    input_tokens: int | None = Field(
        default=0, description="null if any request has unknown input usage"
    )
    output_tokens: int | None = Field(
        default=0, description="null if any request has unknown output usage"
    )
    total_tokens: int | None = Field(
        default=0, description="null if any request has unknown total usage"
    )
    cost_usd: float | None = Field(
        default=None,
        description="Provider-reported total, null when absent or incomplete",
    )


class AiUsageResponse(BaseModel):
    month: str = Field(examples=["2026-11"])
    request_count: int = 0
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    total_tokens: int | None = 0
    cost_usd: float | None = None
    cost_source: str | None = None
    updated_at: datetime | None = None
    by_stage: list[AiStageUsage]
