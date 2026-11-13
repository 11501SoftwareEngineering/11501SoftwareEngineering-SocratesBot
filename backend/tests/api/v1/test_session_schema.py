"""Tests for the student session response schema."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import SessionStatus
from app.schemas.session import CreateSessionResponse


def test_session_response_serializes_fields() -> None:
    session_id = uuid4()
    topic_id = uuid4()

    response = CreateSessionResponse(
        session_id=session_id,
        topic_id=topic_id,
        session_status=SessionStatus.IN_PROGRESS,
    )

    assert response.model_dump(mode="json") == {
        "session_id": str(session_id),
        "topic_id": str(topic_id),
        "session_status": "IN_PROGRESS",
    }


@pytest.mark.parametrize("field", ["session_id", "topic_id"])
def test_session_response_rejects_invalid_uuid(field: str) -> None:
    payload = {
        "session_id": str(uuid4()),
        "topic_id": str(uuid4()),
        "session_status": "IN_PROGRESS",
    }
    payload[field] = "not-a-uuid"

    with pytest.raises(ValidationError, match=field):
        CreateSessionResponse.model_validate(payload)


@pytest.mark.parametrize("field", ["session_id", "topic_id", "session_status"])
def test_session_response_requires_fields(field: str) -> None:
    payload = {
        "session_id": str(uuid4()),
        "topic_id": str(uuid4()),
        "session_status": "IN_PROGRESS",
    }
    del payload[field]

    with pytest.raises(ValidationError, match=field):
        CreateSessionResponse.model_validate(payload)
