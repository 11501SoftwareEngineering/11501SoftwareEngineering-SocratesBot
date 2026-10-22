"""Schemas for PATCH /users/me/preferences."""

from pydantic import BaseModel, Field


class PreferencesUpdateRequest(BaseModel):
    preferred_language: str = Field(
        min_length=1,
        max_length=32,
        examples=["zh-TW", "en", "es"],
    )


class PreferencesUpdateResponse(BaseModel):
    preferred_language: str = Field(examples=["zh-TW"])
    message: str = Field(
        default="Preferences updated",
        examples=["Preferences updated"],
    )
