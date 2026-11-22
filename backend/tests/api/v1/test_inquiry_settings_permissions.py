"""Course-scoped setup authorization and explicit model/language persistence."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.enums import UserRole
from app.crud import course as course_crud
from app.crud import inquiry_model as model_crud
from app.crud import teacher_ai_settings as settings_crud
from app.crud import topic as topic_crud
from app.services import inquiry
from tests.api.v1.conftest import stage1_output
from tests.api.v1.test_inquiry import GENERATED, _ready, _topic
from tests.api.v1.test_report_routes import _login


@pytest.mark.parametrize(
    "role,allowed",
    [
        ("TEACHER", True),
        ("TA", True),
        ("TA_NO_EDIT", False),
        ("STUDENT", False),
        ("OTHER_TEACHER", False),
        ("NONMEMBER", False),
    ],
)
@pytest.mark.parametrize(
    "method,suffix,payload",
    [
        ("get", "setup", None),
        ("put", "setup", {"setup": GENERATED}),
        (
            "post",
            "setup/generate",
            {
                "age_band": "16-18",
                "max_turns": 10,
                "content_language": "en",
                "course_description": "Compare public access and the cost of transit",
                "model_id": "openai/gpt-6-luna",
            },
        ),
        (
            "post",
            "setup/refine",
            {"setup": GENERATED, "feedback": "Use a city transit example"},
        ),
        ("post", "setup/opening-message", {"setup": GENERATED}),
    ],
)
def test_setup_permissions(
    auth_client,
    store,
    course_route_db,
    monkeypatch,
    role,
    allowed,
    method,
    suffix,
    payload,
):
    global_role = UserRole.TEACHER if "TEACHER" in role else UserRole.USER
    bearer, user = _login(auth_client, store, "caller", global_role)
    topic = _topic()
    _ready(monkeypatch, topic, instructor_id=user.id if role == "TEACHER" else uuid4())
    monkeypatch.setattr(
        course_crud,
        "get_course_by_id",
        AsyncMock(return_value=SimpleNamespace(id=topic.course_id, created_by=uuid4())),
    )
    db_role = (
        "TA" if role.startswith("TA") else ("STUDENT" if role == "STUDENT" else None)
    )
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=db_role))
    monkeypatch.setattr(
        course_crud,
        "get_ta_permissions",
        AsyncMock(return_value=["edit_topics"] if role == "TA" else []),
    )
    monkeypatch.setattr(
        model_crud,
        "get_inquiry_model",
        AsyncMock(return_value=SimpleNamespace(model_id="openai/gpt-6-luna")),
    )
    monkeypatch.setattr(
        inquiry, "openrouter_api_key", AsyncMock(return_value="test-only")
    )
    monkeypatch.setattr(
        inquiry, "_design_json", AsyncMock(return_value=stage1_output(GENERATED))
    )
    monkeypatch.setattr(
        inquiry,
        "_model_json",
        AsyncMock(return_value={"opening_message": "A new opening"}),
    )
    key_lookup = AsyncMock(return_value="course-owner-key")
    monkeypatch.setattr(inquiry, "course_api_key", key_lookup)
    kwargs = {"headers": {"Authorization": bearer}}
    if payload is not None:
        kwargs["json"] = payload
    response = getattr(auth_client, method)(
        f"/api/v1/topics/{topic.id}/{suffix}", **kwargs
    )
    assert response.status_code == (200 if allowed else 403), response.text
    if allowed and suffix in {
        "setup/generate",
        "setup/refine",
        "setup/opening-message",
    }:
        key_lookup.assert_awaited_once_with(course_route_db, topic.course_id)
    else:
        key_lookup.assert_not_awaited()


def test_ta_cannot_publish(auth_client, store, course_route_db, monkeypatch):
    bearer, _ = _login(auth_client, store, "ta", UserRole.USER)
    publish = AsyncMock()
    monkeypatch.setattr(inquiry, "publish_inquiry", publish)
    response = auth_client.post(
        f"/api/v1/topics/{uuid4()}/publish",
        headers={"Authorization": bearer},
        json={"setup": GENERATED},
    )
    assert response.status_code == 403
    publish.assert_not_awaited()


@pytest.mark.parametrize("suffix,method", [("setup", "put"), ("publish", "post")])
def test_explicit_settings_saved_or_published(
    auth_client, store, course_route_db, monkeypatch, suffix, method
):
    bearer, user = _login(auth_client, store, "teacher", UserRole.TEACHER)
    topic = _topic(content_language="zh-TW")
    _ready(monkeypatch, topic, instructor_id=user.id)
    monkeypatch.setattr(
        model_crud,
        "get_inquiry_model",
        AsyncMock(return_value=SimpleNamespace(model_id="openai/gpt-6-luna")),
    )
    response = getattr(auth_client, method)(
        f"/api/v1/topics/{topic.id}/{suffix}",
        headers={"Authorization": bearer},
        json={
            "setup": GENERATED,
            "model_id": "openai/gpt-6-luna",
            "content_language": "en",
        },
    )
    assert response.status_code == 200, response.text
    assert topic.model_id == "openai/gpt-6-luna" and topic.content_language == "en"
    assert response.json()["content_language"] == "en"
    assert topic_crud.inquiry_snapshot(topic)["model_id"] == "openai/gpt-6-luna"


def test_omitted_settings_preserved_and_invalid_model_rejected(
    auth_client, store, course_route_db, monkeypatch
):
    bearer, user = _login(auth_client, store, "teacher", UserRole.TEACHER)
    topic = _topic(content_language="en")
    _ready(monkeypatch, topic, instructor_id=user.id)
    headers = {"Authorization": bearer}
    path = f"/api/v1/topics/{topic.id}/setup"
    assert (
        auth_client.put(path, headers=headers, json={"setup": GENERATED}).status_code
        == 200
    )
    assert topic.content_language == "en" and topic.model_id == "openai/gpt-4o-mini"
    monkeypatch.setattr(model_crud, "get_inquiry_model", AsyncMock(return_value=None))
    response = auth_client.put(
        path,
        headers=headers,
        json={"setup": GENERATED, "model_id": "unknown", "content_language": "zh-TW"},
    )
    assert response.status_code == 422
    assert topic.content_language == "en" and topic.model_id == "openai/gpt-4o-mini"
    for key in ["model_id", "content_language"]:
        assert (
            auth_client.put(
                path, headers=headers, json={"setup": GENERATED, key: None}
            ).status_code
            == 422
        )


@pytest.mark.parametrize("role", ["TEACHER", "TA"])
def test_creation_uses_course_owner_default(
    auth_client, store, course_route_db, monkeypatch, role
):
    bearer, user = _login(
        auth_client,
        store,
        "creator",
        UserRole.TEACHER if role == "TEACHER" else UserRole.USER,
    )
    owner = user.id if role == "TEACHER" else uuid4()
    course = SimpleNamespace(id=uuid4(), created_by=owner)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=role))
    monkeypatch.setattr(
        course_crud, "get_ta_permissions", AsyncMock(return_value=["edit_topics"])
    )
    loaded = AsyncMock(
        return_value=SimpleNamespace(default_model_id="gemini-3.1-flash-lite")
    )
    monkeypatch.setattr(settings_crud, "get_settings", loaded)
    monkeypatch.setattr(
        settings_crud,
        "get_inquiry_model",
        AsyncMock(return_value=SimpleNamespace(model_id="gemini-3.1-flash-lite")),
    )
    monkeypatch.setattr(
        inquiry, "openrouter_api_key", AsyncMock(return_value="test-only")
    )
    generated = AsyncMock(return_value=stage1_output(GENERATED))
    monkeypatch.setattr(inquiry, "_design_json", generated)
    topic = _topic()
    monkeypatch.setattr(topic_crud, "create_topic", AsyncMock(return_value=topic))
    monkeypatch.setattr(topic_crud, "record_inquiry_change", AsyncMock())
    response = auth_client.post(
        f"/api/v1/courses/{course.id}/topics",
        headers={"Authorization": bearer},
        json={
            "age_band": "16-18",
            "max_turns": 10,
            "course_description": "Who should pay for public transit?",
            "content_language": "en",
        },
    )
    assert response.status_code == 200, response.text
    loaded.assert_awaited_once_with(course_route_db, owner)
    assert generated.call_args.args[0] == "gemini-3.1-flash-lite"
    assert topic.model_id == "gemini-3.1-flash-lite" and topic.content_language == "en"


@pytest.mark.parametrize(
    "saved,exists", [(None, False), ("removed/model", False), ("valid/model", True)]
)
def test_default_resolution_fallback_and_stale_selection(monkeypatch, saved, exists):
    import asyncio

    from app.services.teacher_ai_settings import effective_default_model

    db = AsyncMock()
    monkeypatch.setattr(
        settings_crud,
        "get_settings",
        AsyncMock(
            return_value=None
            if saved is None
            else SimpleNamespace(default_model_id=saved)
        ),
    )
    lookup = AsyncMock(return_value=object() if exists else None)
    monkeypatch.setattr(settings_crud, "get_inquiry_model", lookup)
    assert asyncio.run(effective_default_model(db, uuid4())) == "gemini-3.1-flash-lite"
    if saved is None:
        lookup.assert_not_awaited()
