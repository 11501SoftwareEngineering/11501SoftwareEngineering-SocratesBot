"""CRUD helpers for course topics."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.models.session import Session
from app.models.topic import Topic

# (topic, completed_session_count)
TopicWithCompletedCountRow = tuple[Topic, int]


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
