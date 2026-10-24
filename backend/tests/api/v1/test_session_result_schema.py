from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.session_result import SessionResultResponse


def test_session_result_serializes_expected_fields() -> None:
    session_id = UUID("00000000-0000-0000-0000-000000000001")
    topic_id = UUID("00000000-0000-0000-0000-000000000002")

    result = SessionResultResponse(
        session_id=session_id,
        topic_id=topic_id,
    )

    assert result.model_dump(mode="json") == {
        "session_id": str(session_id),
        "topic_id": str(topic_id),
    }


@pytest.mark.parametrize("missing_field", ["session_id", "topic_id"])
def test_session_result_requires_all_fields(missing_field: str) -> None:
    payload = {
        "session_id": "00000000-0000-0000-0000-000000000001",
        "topic_id": "00000000-0000-0000-0000-000000000002",
    }
    del payload[missing_field]

    with pytest.raises(ValidationError) as exc_info:
        SessionResultResponse.model_validate(payload)

    error = exc_info.value.errors()[0]
    assert error["loc"] == (missing_field,)
    assert error["type"] == "missing"


@pytest.mark.parametrize("invalid_field", ["session_id", "topic_id"])
def test_session_result_rejects_invalid_uuid(invalid_field: str) -> None:
    payload = {
        "session_id": "00000000-0000-0000-0000-000000000001",
        "topic_id": "00000000-0000-0000-0000-000000000002",
    }
    payload[invalid_field] = "not-a-uuid"

    with pytest.raises(ValidationError) as exc_info:
        SessionResultResponse.model_validate(payload)

    error = exc_info.value.errors()[0]
    assert error["loc"] == (invalid_field,)
    assert error["type"] == "uuid_parsing"
