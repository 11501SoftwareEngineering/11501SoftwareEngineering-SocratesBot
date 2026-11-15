"""Read and reply shapes for one student dialogue."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.enums import DialogueAction, DialogueOutcome, MessageSender

_SENDER = "ai | student"
_OUTCOME = "open | completed | abandoned | closed_by_summary"
_ACTION = "complete | continue | abandon"


class DialogueMessageItem(BaseModel):
    message_id: UUID
    sender: MessageSender = Field(description=_SENDER)
    content: str
    created_at: datetime


class DialogueHistoryResponse(BaseModel):
    messages: list[DialogueMessageItem]
    session_status: DialogueOutcome = Field(description=_OUTCOME)
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
    action: DialogueAction = Field(description=_ACTION)


class EndDialogueResponse(BaseModel):
    session_id: UUID
    session_status: DialogueOutcome = Field(description=_OUTCOME)
    message: str
