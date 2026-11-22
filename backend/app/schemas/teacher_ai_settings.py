"""Schemas for a teacher's provider key and default model."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

_MIN_KEY = 20
_MAX_KEY = 4096


class DefaultModelResponse(BaseModel):
    id: str
    name: str


class AiSettingsResponse(BaseModel):
    configured: bool
    masked_key: str | None = None
    updated_at: datetime | None = None
    default_model: DefaultModelResponse | None = None


class ApiKeyRequest(BaseModel):
    api_key: str | None = Field(default=None, repr=False)
    api_keys: list[str] | None = Field(
        default=None, min_length=1, max_length=3, repr=False
    )

    @model_validator(mode="after")
    def exactly_one_input(self):
        if (self.api_key is None) == (self.api_keys is None):
            raise ValueError("Supply one key or a key list")
        keys = [self.api_key] if self.api_key is not None else self.api_keys
        cleaned = [self.usable_key(key) for key in keys]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Duplicate API keys")
        if self.api_keys is not None:
            self.api_keys = cleaned
        return self

    @field_validator("api_key")
    @classmethod
    def usable_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if (
            not stripped
            or not all(33 <= ord(char) <= 126 for char in stripped)
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
