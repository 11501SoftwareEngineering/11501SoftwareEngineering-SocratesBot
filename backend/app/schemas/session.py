"""Schemas for student sessions."""

from uuid import UUID

from pydantic import BaseModel


class CreateSessionResponse(BaseModel):
    """Response returned when a student creates a dialogue."""

    session_id: UUID
    topic_id: UUID
    session_status: str
