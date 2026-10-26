from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import SessionStatus


@dataclass(frozen=True)
class SessionResultData:
    id: UUID
    topic_id: UUID
    user_id: UUID
    status: SessionStatus


class SessionResultResponse(BaseModel):
    session_id: UUID
    topic_id: UUID
