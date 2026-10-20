from uuid import UUID

from pydantic import BaseModel


class SessionResultResponse(BaseModel):
    session_id: UUID
    topic_id: UUID
    conclusion: str
    is_anonymous: bool
