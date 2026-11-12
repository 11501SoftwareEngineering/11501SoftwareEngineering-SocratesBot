"""Read and reply shapes for one student dialogue."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DialogueMessageItem(BaseModel):
    message_id: UUID
    sender: str
    content: str
    created_at: datetime


class DialogueHistoryResponse(BaseModel):
    messages: list[DialogueMessageItem]
    session_status: str
    max_turns: int | None
    completed_turns: int
    goal_reached: bool
    awaiting_end_consent: bool


class StreamMessageRequest(BaseModel):
    content: str = Field(max_length=6000)
    request_id: UUID

    @field_validator("content")
    @classmethod
    def content_is_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content is empty")
        return cleaned


class StreamDone(BaseModel):
    message_id: UUID
    text: str
    completed_turns: int
    is_completed: bool
    awaiting_end_consent: bool


class EndDialogueRequest(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def action_is_known(cls, value: str) -> str:
        if value not in {"complete", "continue", "abandon"}:
            raise ValueError("invalid action")
        return value


class EndDialogueResponse(BaseModel):
    session_id: UUID
    session_status: str
    message: str
