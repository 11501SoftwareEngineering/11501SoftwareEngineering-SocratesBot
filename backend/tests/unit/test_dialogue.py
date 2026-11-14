from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.message import DialogueMessage
from app.models.session import Session
from app.models.topic import Topic
from app.services.dialogue import (
    ReplyRejected,
    _history,
    apply_end,
    guard_reply,
    reply_material,
)


def test_complete_before_the_goal_stays_open() -> None:
    with pytest.raises(ReplyRejected) as caught:
        apply_end(
            "complete",
            outcome="open",
            status_value="IN_PROGRESS",
            goal_reached=False,
        )

    assert caught.value.status_code == 409


def test_abandon_does_not_complete() -> None:
    outcome, status_value, goal_reached, awaiting, _message = apply_end(
        "abandon",
        outcome="open",
        status_value="IN_PROGRESS",
        goal_reached=True,
    )

    assert outcome == "abandoned"
    assert status_value == "IN_PROGRESS"
    assert goal_reached is False
    assert awaiting is False


def test_turn_cap_rejects_and_does_not_change_outcome() -> None:
    with pytest.raises(ReplyRejected, match="Turn cap reached"):
        guard_reply(
            stage="conversation",
            outcome="open",
            completed_turns=5,
            max_turns=5,
        )


def test_setup_rejects_a_reply() -> None:
    with pytest.raises(ReplyRejected, match="not accepting replies"):
        guard_reply(
            stage="setup",
            outcome="open",
            completed_turns=0,
            max_turns=5,
        )


def test_history_remains_after_complete() -> None:
    session = Session(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status="COMPLETED",
        outcome="completed",
        goal_reached=True,
        awaiting_end_consent=False,
    )
    topic = Topic(
        id=session.topic_id,
        course_id=uuid4(),
        created_by=uuid4(),
        title="Course",
        max_turns=5,
    )
    message = DialogueMessage(
        id=uuid4(),
        session_id=session.id,
        sender="student",
        content="hello",
        created_at=datetime.now(UTC),
    )

    body = _history(session, topic, [message])

    assert body.session_status == "completed"
    assert body.messages[0].content == "hello"
    assert body.completed_turns == 1


def test_reply_material_omits_the_student_and_uses_unspecified() -> None:
    topic = Topic(
        id=uuid4(),
        course_id=uuid4(),
        created_by=uuid4(),
        title="Course",
        inquiry_topic="Cities",
        core_question="Why?",
        exclusions=None,
    )

    material = reply_material(topic, [])

    assert "exclusions: unspecified" in material
    assert "Cities" in material
    assert str(topic.created_by) not in material
