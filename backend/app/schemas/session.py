"""Schemas for student sessions."""

from uuid import UUID

from pydantic import BaseModel

from app.core.enums import SessionStatus


class CreateSessionResponse(BaseModel):
    """Response returned when a student creates a session."""

    session_id: UUID
    topic_id: UUID
    session_status: SessionStatus
