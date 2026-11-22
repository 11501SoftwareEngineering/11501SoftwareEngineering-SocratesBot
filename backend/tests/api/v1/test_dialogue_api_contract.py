"""Real ASGI routes and lifecycle services with in-memory persistence boundaries."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.enums import UserRole
from app.crud import message as message_crud
from app.schemas.inquiry import InquiryFields, InquirySetupResponse
from app.services import dialogue, inquiry
from tests.api.v1.test_report_routes import _install, _login, _Memory
from tests.unit.test_dialogue_contract import decode_events


def test_ready_complete_report_start_poll_and_ready_reuse(
    auth_client, store, course_route_db, monkeypatch
):
    bearer, owner = _login(auth_client, store, "contract-owner", UserRole.USER)
    memory = _Memory()
    memory.session.user_id = owner.id
    memory.session.outcome = "open"
    memory.session.status = "IN_PROGRESS"
    memory.session.goal_reached = True
    memory.session.awaiting_end_consent = True
    _install(monkeypatch, course_route_db, memory)
    monkeypatch.setattr(
        dialogue, "_owned", AsyncMock(return_value=(memory.session, memory.topic, []))
    )

    async def save_end(_db, **values):
        for key in ("outcome", "status", "goal_reached", "awaiting_end_consent"):
            setattr(memory.session, key, values[key])

    monkeypatch.setattr(message_crud, "save_end", save_end)
    headers = {"Authorization": bearer}
    path = f"/api/v1/sessions/{memory.session.id}"
    assert auth_client.post(path + "/report", headers=headers).status_code == 409
    continued = auth_client.post(
        path + "/end", headers=headers, json={"action": "continue"}
    )
    assert continued.json()["session_status"] == "open"
    assert (
        memory.session.goal_reached is True
        and memory.session.awaiting_end_consent is False
    )
    completed = auth_client.post(
        path + "/end", headers=headers, json={"action": "complete"}
    )
    assert completed.json()["session_status"] == "completed"
    assert memory.reports_scheduled == []
    assert auth_client.get(path + "/report", headers=headers).status_code == 404
    started = auth_client.post(path + "/report", headers=headers)
    assert started.json() == {"report_status": "pending", "report": None}
    memory.attempts[-1].lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
    assert auth_client.post(path + "/report", headers=headers).json() == started.json()
    assert len(memory.reports_scheduled) == 1
    memory.attempts[-1].status = "ready"
    memory.attempts[-1].result_json = {
        "viewpoint_summary": "A qualified position",
        "evidence_status": "partial",
    }
    ready = auth_client.get(path + "/report", headers=headers)
    assert ready.json()["report_status"] == "ready"
    assert auth_client.post(path + "/report", headers=headers).json() == ready.json()
    assert len(memory.reports_scheduled) == 1


@pytest.mark.parametrize(
    ("code", "detail"),
    [
        (400, "Turn cap reached"),
        (404, "Session not found"),
        (409, "Another reply is in progress"),
        (413, "Latest message exceeds the dialogue context budget"),
        (502, "Model call failed"),
        (503, "Configured model tokenizer is not supported"),
    ],
)
def test_stream_preflight_errors_are_json_not_sse(
    auth_client, store, course_route_db, monkeypatch, code, detail
):
    bearer, _ = _login(auth_client, store, "errors", UserRole.USER)
    monkeypatch.setattr(
        dialogue, "send_reply", AsyncMock(side_effect=HTTPException(code, detail))
    )
    response = auth_client.post(
        f"/api/v1/sessions/{uuid4()}/messages/stream",
        headers={"Authorization": bearer},
        json={"content": "A reason", "request_id": str(uuid4())},
    )
    assert response.status_code == code
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": detail}


def test_actual_stream_response_and_committed_replay(
    auth_client, store, course_route_db, monkeypatch
):
    bearer, _owner = _login(auth_client, store, "replay", UserRole.USER)
    session_id, request_id, reply_id = uuid4(), uuid4(), uuid4()
    session = SimpleNamespace(id=session_id, outcome="open", awaiting_end_consent=True)
    messages = [
        SimpleNamespace(request_id=request_id, sender="student"),
        SimpleNamespace(
            request_id=None, sender="ai", id=reply_id, content="first\nlast\n"
        ),
    ]
    monkeypatch.setattr(
        message_crud,
        "load_owned_dialogue",
        AsyncMock(return_value=(session, SimpleNamespace(), messages)),
    )
    inference = AsyncMock(side_effect=AssertionError("Replay must not infer"))
    monkeypatch.setattr(dialogue, "_ask_and_store", inference)
    response = auth_client.post(
        f"/api/v1/sessions/{session_id}/messages/stream",
        headers={"Authorization": bearer},
        json={"content": "A reason", "request_id": str(request_id)},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert decode_events(response.text)[0] == ("message", "first\nlast\n")
    inference.assert_not_awaited()


def test_setup_serializes_missing_values_as_omitted(
    auth_client, store, course_route_db, monkeypatch
):
    bearer, _ = _login(auth_client, store, "setup-teacher", UserRole.TEACHER)
    topic_id = uuid4()
    monkeypatch.setattr(
        inquiry,
        "get_inquiry_setup",
        AsyncMock(
            return_value=InquirySetupResponse(
                topic_id=topic_id,
                course_id=uuid4(),
                topic_status="setup",
                setup=InquiryFields(),
            )
        ),
    )
    response = auth_client.get(
        f"/api/v1/topics/{topic_id}/setup", headers={"Authorization": bearer}
    )
    assert response.status_code == 200
    assert response.json()["setup"] == {"exclusions": "unspecified"}
    assert "model_id" not in response.json()
