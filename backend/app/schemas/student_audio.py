"""Schemas for POST /student/audio/transcribe."""

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    text: str = Field(examples=["蘇格拉底式對話"])
