"""CRUD helpers for course topics."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus, TopicStage
from app.models.session import Session
from app.models.topic import Topic

# (topic, completed_session_count)
TopicWithCompletedCountRow = tuple[Topic, int]
# (topic, session_status, session_id); session columns are None if not started
TopicWithUserSessionRow = tuple[Topic, str | None, UUID | None]


async def create_topic(
    db: AsyncSession,
    *,
    course_id: UUID,
    created_by: UUID,
    title: str,
    description: str | None,
) -> Topic:
    topic = Topic(
        course_id=course_id,
        created_by=created_by,
        title=title,
        description=description,
    )
    db.add(topic)
    await db.flush()
    return topic


async def get_topic_by_id(db: AsyncSession, topic_id: UUID) -> Topic | None:
    return await db.get(Topic, topic_id)


async def update_topic(
    db: AsyncSession,
    topic: Topic,
    *,
    title: str,
    description: str | None,
) -> Topic:
    topic.title = title
    topic.description = description
    await db.flush()
    return topic


async def save_inquiry(
    db: AsyncSession,
    topic: Topic,
    *,
    content_language: str | None,
    age_band: str | None,
    max_turns: int | None,
    inquiry_topic: str | None,
    core_question: str | None,
    inquiry_focus: str | None,
    background_info: str | None,
    exclusions: str | None,
    opening_message: str | None,
) -> Topic:
    """Persist the saved inquiry. This does not copy a generation attempt."""
    topic.content_language = content_language
    topic.age_band = age_band
    topic.max_turns = max_turns
    topic.inquiry_topic = inquiry_topic
    topic.core_question = core_question
    topic.inquiry_focus = inquiry_focus
    topic.background_info = background_info
    topic.exclusions = exclusions
    topic.opening_message = opening_message
    topic.version += 1
    await db.flush()
    return topic


async def publish_topic(db: AsyncSession, topic: Topic) -> Topic:
    topic.stage = TopicStage.CONVERSATION.value
    topic.version += 1
    await db.flush()
    return topic


async def delete_topic(db: AsyncSession, topic: Topic) -> None:
    await db.delete(topic)
    await db.flush()


async def list_topics_with_completed_count(
    db: AsyncSession, course_id: UUID
) -> list[TopicWithCompletedCountRow]:
    """List a course's topics with COMPLETED session counts in one query."""
    completed_count = (
        select(func.count())
        .select_from(Session)
        .where(
            Session.topic_id == Topic.id,
            Session.status == SessionStatus.COMPLETED.value,
        )
        .correlate(Topic)
        .scalar_subquery()
    )
    statement = (
        select(Topic, completed_count)
        .where(Topic.course_id == course_id)
        .order_by(Topic.created_at.asc(), Topic.id.asc())
    )
    result = await db.execute(statement)
    return [(topic, int(count or 0)) for topic, count in result.all()]


async def list_topics_with_user_session(
    db: AsyncSession, *, course_id: UUID, user_id: UUID
) -> list[TopicWithUserSessionRow]:
    """List a course's topics joined with ``user_id``'s session, if any."""
    statement = (
        select(Topic, Session.status, Session.id)
        .outerjoin(
            Session,
            (Session.topic_id == Topic.id) & (Session.user_id == user_id),
        )
        .where(
            Topic.course_id == course_id,
            or_(
                Topic.stage.in_(
                    (TopicStage.CONVERSATION.value, TopicStage.SUMMARY.value)
                ),
                Session.id.is_not(None),
            ),
        )
        .order_by(Topic.created_at.asc(), Topic.id.asc())
    )
    result = await db.execute(statement)
    return [
        (topic, session_status, session_id)
        for topic, session_status, session_id in result.all()
    ]
