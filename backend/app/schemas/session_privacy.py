from uuid import UUID

from pydantic import BaseModel, StrictBool


class UpdateSessionPrivacyRequest(BaseModel):
    is_anonymous: StrictBool


class UpdateSessionPrivacyResponse(BaseModel):
    session_id: UUID
    is_anonymous: bool
    message: str
