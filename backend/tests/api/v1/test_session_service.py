"""Service tests with fake storage; no real database or HTTP calls."""

from uuid import UUID, uuid4

import pytest

from app.core.enums import SessionStatus
from app.services.session import (
    CourseAccessDeniedError,
    SessionAlreadyExistsError,
    TopicNotFoundError,
    create_session,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeSessionStore:
    """Test-only in-memory storage, never used by production routes."""

    def __init__(self) -> None:
        self.user_id = uuid4()
        self.topic_id = uuid4()
        self.course_id = uuid4()
        self.topics = {self.topic_id: self.course_id}
        self.students = {(self.user_id, self.course_id)}
        self.sessions: dict[tuple[UUID, UUID], UUID] = {}
        self.create_calls = 0

    async def get_topic_course_id(self, topic_id: UUID) -> UUID | None:
        return self.topics.get(topic_id)

    async def is_course_student(self, user_id: UUID, course_id: UUID) -> bool:
        return (user_id, course_id) in self.students

    async def create_session_id(self, user_id: UUID, topic_id: UUID) -> UUID | None:
        self.create_calls += 1
        key = (user_id, topic_id)
        if key in self.sessions:
            return None
        self.sessions[key] = uuid4()
        return self.sessions[key]


@pytest.fixture
def store() -> FakeSessionStore:
    return FakeSessionStore()


async def test_first_entry_creates_session(store: FakeSessionStore) -> None:
    result = await create_session(
        user_id=store.user_id, topic_id=store.topic_id, store=store
    )

    assert result.session_id == store.sessions[(store.user_id, store.topic_id)]
    assert result.topic_id == store.topic_id
    assert result.session_status is SessionStatus.IN_PROGRESS
    assert store.create_calls == 1


async def test_second_creation_is_rejected(store: FakeSessionStore) -> None:
    first_id = (
        await create_session(
            user_id=store.user_id, topic_id=store.topic_id, store=store
        )
    ).session_id

    with pytest.raises(SessionAlreadyExistsError):
        await create_session(
            user_id=store.user_id, topic_id=store.topic_id, store=store
        )

    assert store.sessions == {(store.user_id, store.topic_id): first_id}


async def test_different_users_get_separate_sessions(store: FakeSessionStore) -> None:
    other_user_id = uuid4()
    store.students.add((other_user_id, store.course_id))

    first = await create_session(
        user_id=store.user_id, topic_id=store.topic_id, store=store
    )
    second = await create_session(
        user_id=other_user_id, topic_id=store.topic_id, store=store
    )

    assert first.session_id != second.session_id
    assert len(store.sessions) == 2


async def test_different_topics_get_separate_sessions(store: FakeSessionStore) -> None:
    other_topic_id = uuid4()
    store.topics[other_topic_id] = store.course_id

    first = await create_session(
        user_id=store.user_id, topic_id=store.topic_id, store=store
    )
    second = await create_session(
        user_id=store.user_id, topic_id=other_topic_id, store=store
    )

    assert first.session_id != second.session_id
    assert second.topic_id == other_topic_id


async def test_missing_topic_is_rejected(store: FakeSessionStore) -> None:
    with pytest.raises(TopicNotFoundError):
        await create_session(user_id=store.user_id, topic_id=uuid4(), store=store)

    assert store.create_calls == 0


async def test_non_student_is_rejected(store: FakeSessionStore) -> None:
    store.students.clear()

    with pytest.raises(CourseAccessDeniedError):
        await create_session(
            user_id=store.user_id, topic_id=store.topic_id, store=store
        )

    assert store.create_calls == 0
