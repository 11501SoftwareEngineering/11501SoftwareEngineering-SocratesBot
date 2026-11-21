"""Schemas for a teacher's provider key and default model."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_MIN_KEY = 20
_MAX_KEY = 256


class DefaultModelResponse(BaseModel):
    id: str
    name: str


class AiSettingsResponse(BaseModel):
    configured: bool
    masked_key: str | None = None
    updated_at: datetime | None = None
    default_model: DefaultModelResponse | None = None


class ApiKeyRequest(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def usable_key(cls, value: str) -> str:
        stripped = value.strip()
        if (
            not stripped
            or any(char.isspace() for char in stripped)
            or len(stripped) < _MIN_KEY
            or len(stripped) > _MAX_KEY
        ):
            raise ValueError("invalid api key")
        return stripped


class ApiKeyResponse(BaseModel):
    configured: bool
    masked_key: str
    updated_at: datetime


class DefaultModelRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=256)


class DefaultModelUpdateResponse(BaseModel):
    default_model: DefaultModelResponse
    message: str
