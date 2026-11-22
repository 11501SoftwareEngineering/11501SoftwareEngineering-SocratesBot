"""Schemas for student sessions."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DialogueOutcome


class CreateSessionResponse(BaseModel):
    """Response returned when a student creates a dialogue."""

    session_id: UUID
    topic_id: UUID
    session_status: DialogueOutcome = Field(
        description="open | completed | ended | abandoned | closed_by_summary"
    )
