"""Wire/OpenAPI regression checks: no external services or provider calls."""

import json
from uuid import uuid4

import pytest

from app.api.v1.routes.student_sessions import _sse
from app.main import app
from app.schemas.dialogue import StreamDone, StreamDoneEvent


def decode_events(wire: str) -> list[tuple[str, str]]:
    events = []
    for block in wire.split("\n\n"):
        if not block:
            continue
        event = "message"
        data = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].removeprefix(" ")
            elif line.startswith("data:"):
                data.append(line[5:].removeprefix(" "))
        events.append((event, "\n".join(data)))
    return events


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Hello",
        "first\nsecond",
        "last\n",
        "\n\n",
        "甲\u2028乙\u2029丙",
        "a\r\nb\rc",
        "event: done\ndata: literal",
    ],
)
def test_sse_preserves_text_and_has_one_terminal_event(text):
    done = StreamDone(
        message_id=uuid4(),
        text=text,
        completed_turns=2,
        is_completed=False,
        awaiting_end_consent=True,
    )
    events = decode_events("".join(_sse(done)))
    assert events[0] == ("message", text.replace("\r\n", "\n").replace("\r", "\n"))
    assert len(events) == 2 and events[1][0] == "done"
    assert json.loads(events[1][1]) == StreamDoneEvent.model_validate(
        done.model_dump()
    ).model_dump(mode="json")


def test_openapi_matches_sse_transport_and_terminal_payload():
    response = app.openapi()["paths"]["/api/v1/sessions/{sessionId}/messages/stream"][
        "post"
    ]["responses"]["200"]
    assert set(response["content"]) == {"text/event-stream"}
    assert response["content"]["text/event-stream"]["schema"] == {"type": "string"}
    event_schema = response["x-sse-events"]["done"]["schema"]
    assert event_schema == StreamDoneEvent.model_json_schema()
    events = decode_events(response["content"]["text/event-stream"]["example"])
    StreamDoneEvent.model_validate(json.loads(events[1][1]))


@pytest.mark.parametrize(
    ("path", "method", "codes"),
    [
        ("/topics/{topicId}/sessions", "post", {400, 401, 403, 404, 422}),
        ("/sessions/{sessionId}/messages", "get", {401, 403, 404, 422}),
        (
            "/sessions/{sessionId}/messages/stream",
            "post",
            {400, 401, 403, 404, 409, 413, 422, 502, 503},
        ),
        ("/sessions/{sessionId}/end", "post", {400, 401, 403, 404, 409, 422}),
        ("/sessions/{sessionId}/report", "post", {401, 403, 404, 409, 422}),
        ("/sessions/{sessionId}/report", "get", {401, 403, 404, 409, 422}),
        ("/topics/{topicId}/reports", "get", {401, 403, 404, 422}),
        ("/topics/{topicId}/reports/{sessionId}", "post", {401, 403, 404, 409, 422}),
        ("/courses/{courseId}/topics", "post", {401, 403, 404, 422, 502, 503, 504}),
        (
            "/topics/{topicId}/setup/generate",
            "post",
            {400, 401, 403, 404, 422, 502, 503, 504},
        ),
    ],
)
def test_openapi_covers_existing_error_statuses(path, method, codes):
    responses = app.openapi()["paths"]["/api/v1" + path][method]["responses"]
    assert {str(code) for code in codes} <= responses.keys()


def test_session_status_is_endpoint_specific():
    schemas = app.openapi()["components"]["schemas"]
    assert set(schemas["DialogueOutcome"]["enum"]) == {
        "open",
        "completed",
        "abandoned",
        "closed_by_summary",
    }
    assert set(schemas["SessionStatus"]["enum"]) == {"IN_PROGRESS", "COMPLETED"}
