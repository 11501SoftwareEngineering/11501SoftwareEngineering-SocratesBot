"""Topic API tests: list / create / delete / explanation (mocked CRUD)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.enums import SessionStatus, UserRole
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import topic as topic_crud
from app.schemas.topic import TopicUpdateRequest
from app.services import topics as topics_service
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login(
    client: TestClient,
    store: FakeStore,
    account: str = "user1",
    role: UserRole = UserRole.USER,
) -> tuple[str, object]:
    user = seed_user(store, account_id=account, role=role)
    login = client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), user


def _course(**overrides):
    base = {"id": uuid4(), "name": "SE", "invitation_code": "ABCD2345"}
    base.update(overrides)
    return SimpleNamespace(**base)


def _topic(course_id, **overrides):
    base = {
        "id": uuid4(),
        "course_id": course_id,
        "title": "T1",
        "description": "Background",
        "stage": "conversation",
        "age_band": "16-18",
        "max_turns": 10,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_role(monkeypatch, db_role: str | None, course=None):
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=db_role))
    monkeypatch.setattr(
        course_crud,
        "is_course_instructor",
        AsyncMock(return_value=db_role == "TEACHER"),
    )


def test_student_topic_list_has_session_fields(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store)
    course = _course()
    _patch_role(monkeypatch, "STUDENT", course)
    started = _topic(course.id, title="Started")
    fresh = _topic(course.id, title="Fresh", description=None)
    session_id = uuid4()
    list_mock = AsyncMock(
        return_value=[
            (started, "IN_PROGRESS", session_id),
            (fresh, None, None),
        ]
    )
    monkeypatch.setattr(topic_crud, "list_topics_with_user_session", list_mock)

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/topics", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "my_role": "student",
        "my_permissions": [],
        "topics": [
            {
                "topic_id": str(started.id),
                "title": "Started",
                "description": "Background",
                "topic_status": "conversation",
                "age_band": "16-18",
                "max_turns": 10,
                "session_status": "IN_PROGRESS",
                "session_id": str(session_id),
            },
            {
                "topic_id": str(fresh.id),
                "title": "Fresh",
                "description": None,
                "topic_status": "conversation",
                "age_band": "16-18",
                "max_turns": 10,
                "session_status": None,
                "session_id": None,
            },
        ],
    }
    list_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, user_id=user.id
    )


def test_student_topic_list_shows_only_conversation_and_summary(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    _patch_role(monkeypatch, "STUDENT", course)
    setup = _topic(course.id, title="Setup", stage="setup")
    talking = _topic(course.id, title="Talking", stage="conversation")
    summing = _topic(course.id, title="Summing", stage="summary")
    monkeypatch.setattr(
        topic_crud,
        "list_topics_with_user_session",
        AsyncMock(
            return_value=[
                (setup, None, None),
                (talking, None, None),
                (summing, SessionStatus.COMPLETED.value, uuid4()),
            ]
        ),
    )

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/topics", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    topics = response.json()["topics"]
    assert [(t["title"], t["topic_status"]) for t in topics] == [
        ("Talking", "conversation"),
        ("Summing", "summary"),
    ]


def test_teacher_topic_list_has_counts(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    _patch_role(monkeypatch, "TEACHER", course)
    topic = _topic(course.id)
    monkeypatch.setattr(
        topic_crud,
        "list_topics_with_completed_count",
        AsyncMock(return_value=[(topic, 3)]),
    )
    monkeypatch.setattr(course_crud, "count_active_students", AsyncMock(return_value=8))

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/topics", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["my_role"] == "teacher"
    assert body["topics"] == [
        {
            "topic_id": str(topic.id),
            "title": "T1",
            "description": "Background",
            "topic_status": "conversation",
            "age_band": "16-18",
            "max_turns": 10,
            "answered_count": 3,
            "student_count": 8,
        }
    ]


def test_ta_topic_list_has_counts_and_own_permissions(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "assist")
    course = _course()
    _patch_role(monkeypatch, "TA", course)
    monkeypatch.setattr(
        course_crud,
        "get_ta_permissions",
        AsyncMock(return_value=["view_members", "edit_topics"]),
    )
    monkeypatch.setattr(
        topic_crud,
        "list_topics_with_completed_count",
        AsyncMock(return_value=[(_topic(course.id, stage="setup"), 1)]),
    )
    monkeypatch.setattr(course_crud, "count_active_students", AsyncMock(return_value=4))

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/topics", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["my_role"] == "ta"
    assert body["my_permissions"] == ["edit_topics", "view_members"]
    assert body["topics"][0]["answered_count"] == 1
    assert body["topics"][0]["student_count"] == 4
    # Staff see setup topics too.
    assert body["topics"][0]["topic_status"] == "setup"


@pytest.mark.parametrize("exists", [True, False])
def test_topic_list_non_member_or_missing_is_404(
    exists: bool,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    _patch_role(monkeypatch, None, _course() if exists else None)
    response = auth_client.get(
        f"/api/v1/courses/{uuid4()}/topics", headers={"Authorization": bearer}
    )
    assert response.status_code == 404


_CREATE_BODY = {
    "age_band": "16-18",
    "max_turns": 10,
    "course_description": "Compare two accounts of who should decide.",
}
_GENERATED = {
    "age_band": "16-18",
    "max_turns": 10,
    "topic": "generated topic",
    "core_question": "generated question",
    "inquiry_focus": "compare the two accounts",
    "background_info": "a published case",
    "exclusions": "unspecified",
    "opening_message": "Where should we start?",
}


def test_create_topic_fills_eight_fields_from_the_description(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    _patch_role(monkeypatch, "TEACHER", course)
    created = _topic(course.id, title="", description=None, stage="setup")
    create_mock = AsyncMock(return_value=created)
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)
    monkeypatch.setattr(topic_crud, "record_inquiry_change", AsyncMock())

    async def complete(self, *, instructions, material, model=None, **_extra):
        assert "course_description" in material
        return _GENERATED

    monkeypatch.setattr(
        "app.services.model_client.OpenAIChatClient.complete_json", complete
    )

    response = auth_client.post(
        f"/api/v1/courses/{course.id}/topics",
        headers={"Authorization": bearer},
        json=_CREATE_BODY,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic_id"] == str(created.id)
    assert body["course_id"] == str(course.id)
    assert body["topic_status"] == "setup"
    assert body["setup"]["topic"] == "generated topic"
    assert body["setup"]["core_question"] == "generated question"
    create_mock.assert_awaited_once_with(
        course_route_db,
        course_id=course.id,
        created_by=user.id,
        title="generated topic",
        description=_CREATE_BODY["course_description"],
    )
    course_route_db.commit.assert_awaited_once()


def test_ta_with_edit_topics_can_create_a_topic(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "assist", UserRole.TEACHER)
    course = _course()
    _patch_role(monkeypatch, "TA", course)
    monkeypatch.setattr(
        course_crud, "get_ta_permissions", AsyncMock(return_value=["edit_topics"])
    )
    created = _topic(course.id, stage="setup")
    monkeypatch.setattr(topic_crud, "create_topic", AsyncMock(return_value=created))
    monkeypatch.setattr(topic_crud, "record_inquiry_change", AsyncMock())

    async def complete(self, *, instructions, material, model=None, **_extra):
        return _GENERATED

    monkeypatch.setattr(
        "app.services.model_client.OpenAIChatClient.complete_json", complete
    )

    response = auth_client.post(
        f"/api/v1/courses/{course.id}/topics",
        headers={"Authorization": bearer},
        json=_CREATE_BODY,
    )

    assert response.status_code == 200
    assert response.json()["topic_status"] == "setup"


def test_create_topic_does_not_store_a_row_when_the_model_fails(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    _patch_role(monkeypatch, "TEACHER", _course())
    create_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)

    async def fail(self, *, instructions, material, model=None, **_extra):
        from app.services.model_client import ModelCallError

        raise ModelCallError(503)

    monkeypatch.setattr(
        "app.services.model_client.OpenAIChatClient.complete_json", fail
    )

    response = auth_client.post(
        f"/api/v1/courses/{uuid4()}/topics",
        headers={"Authorization": bearer},
        json=_CREATE_BODY,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Inquiry generation failed"
    create_mock.assert_not_awaited()


@pytest.mark.parametrize(
    ("db_role", "exists", "permissions", "body", "expected"),
    [
        ("STUDENT", True, [], _CREATE_BODY, 403),
        ("TA", True, ["view_members"], _CREATE_BODY, 403),
        (None, True, [], _CREATE_BODY, 403),
        ("TEACHER", False, [], _CREATE_BODY, 404),
        ("TEACHER", True, [], {"age_band": "16-18", "max_turns": 10}, 422),
        (
            "TEACHER",
            True,
            [],
            {**_CREATE_BODY, "course_description": "   "},
            422,
        ),
        ("TEACHER", True, [], {**_CREATE_BODY, "age_band": "adults"}, 422),
    ],
)
def test_create_topic_errors(
    db_role: str | None,
    exists: bool,
    permissions: list[str],
    body: dict,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    _patch_role(monkeypatch, db_role, _course() if exists else None)
    monkeypatch.setattr(
        course_crud, "get_ta_permissions", AsyncMock(return_value=permissions)
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)
    response = auth_client.post(
        f"/api/v1/courses/{uuid4()}/topics",
        headers={"Authorization": bearer},
        json=body,
    )
    assert response.status_code == expected
    create_mock.assert_not_awaited()


def test_teacher_update_topic_still_works(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route is gone; the service stays until the topic create rework (#171)."""
    teacher = seed_user(store, account_id="teach", role=UserRole.TEACHER)
    course = _course()
    topic = _topic(course.id)
    _patch_role(monkeypatch, "TEACHER", course)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    updated = _topic(course.id, id=topic.id, title="New", description=None)
    monkeypatch.setattr(topic_crud, "update_topic", AsyncMock(return_value=updated))

    response = asyncio.run(
        topics_service.update_topic(
            course_route_db, teacher, topic.id, TopicUpdateRequest(title="New")
        )
    )

    assert response.message == "Topic updated"
    course_route_db.commit.assert_awaited_once()


def test_update_topic_endpoint_is_removed(
    auth_client: TestClient, store: FakeStore
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    response = auth_client.put(
        f"/api/v1/topics/{uuid4()}",
        headers={"Authorization": bearer},
        json={"title": "x"},
    )
    assert response.status_code == 405


def test_delete_topic_by_teacher(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    topic = _topic(course.id)
    _patch_role(monkeypatch, "TEACHER", course)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    delete_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "delete_topic", delete_mock)

    response = auth_client.delete(
        f"/api/v1/topics/{topic.id}", headers={"Authorization": bearer}
    )

    assert response.status_code == 204
    delete_mock.assert_awaited_once_with(course_route_db, topic)
    course_route_db.commit.assert_awaited_once()


def test_delete_topic_by_non_teacher_is_403(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    _patch_role(monkeypatch, "STUDENT", course)
    monkeypatch.setattr(
        topic_crud, "get_topic_by_id", AsyncMock(return_value=_topic(course.id))
    )
    delete_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "delete_topic", delete_mock)
    response = auth_client.delete(
        f"/api/v1/topics/{uuid4()}", headers={"Authorization": bearer}
    )
    assert response.status_code == 403
    delete_mock.assert_not_awaited()


def test_delete_missing_topic_is_idempotent(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=None))
    response = auth_client.delete(
        f"/api/v1/topics/{uuid4()}", headers={"Authorization": bearer}
    )
    assert response.status_code == 204
    course_route_db.commit.assert_not_awaited()


def test_explanation_for_course_member(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    topic = _topic(course.id)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    monkeypatch.setattr(session_crud, "is_course_member", AsyncMock(return_value=True))

    response = auth_client.get(
        f"/api/v1/topics/{topic.id}/explanation", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "topic_id": str(topic.id),
        "title": "T1",
        "background": "Background",
        "key_terms": [],
    }


@pytest.mark.parametrize(("topic_exists", "expected"), [(True, 403), (False, 404)])
def test_explanation_non_member_or_missing(
    topic_exists: bool,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    monkeypatch.setattr(
        topic_crud,
        "get_topic_by_id",
        AsyncMock(return_value=_topic(course.id) if topic_exists else None),
    )
    monkeypatch.setattr(session_crud, "is_course_member", AsyncMock(return_value=False))
    response = auth_client.get(
        f"/api/v1/topics/{uuid4()}/explanation", headers={"Authorization": bearer}
    )
    assert response.status_code == expected
