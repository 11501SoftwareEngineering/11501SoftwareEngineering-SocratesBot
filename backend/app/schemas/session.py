"""Schemas and shared data for student sessions."""

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, StrictBool

from app.core.enums import SessionStatus


@dataclass(frozen=True)
class SessionData:
    """Session data shared by the CRUD and service layers."""

    id: UUID
    topic_id: UUID
    user_id: UUID
    status: SessionStatus
    is_anonymous: bool


class CreateSessionResponse(BaseModel):
    """Response returned when a student creates or enters a session."""

    session_id: UUID
    topic_id: UUID


class UpdateSessionPrivacyRequest(BaseModel):
    is_anonymous: StrictBool


class UpdateSessionPrivacyResponse(BaseModel):
    session_id: UUID
    is_anonymous: bool
    message: str


class SessionResultResponse(BaseModel):
    session_id: UUID
    topic_id: UUID
