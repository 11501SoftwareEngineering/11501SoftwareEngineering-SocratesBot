"""Business rules for topics (permissions follow the caller's in-course role)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CourseRole, SessionStatus, TopicStage
from app.crud import course as course_crud
from app.crud import topic as topic_crud
from app.models.topic import Topic
from app.models.user import User
from app.schemas.topic import (
    CourseTopicsResponse,
    TopicExplanationResponse,
    TopicListItem,
)
from app.services import courses as courses_service


def _topic_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Topic not found",
    )


async def get_instructed_topic(
    db: AsyncSession, teacher: User, topic_id: UUID
) -> Topic:
    """Return the topic if it exists and ``teacher`` instructs its course.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        raise _topic_not_found()
    await courses_service.require_course_teacher(db, teacher, topic.course_id)
    return topic


async def delete_topic(db: AsyncSession, user: User, topic_id: UUID) -> None:
    """Hard-delete a topic; idempotent when already gone (no 404).

    Sessions go via ``ON DELETE CASCADE``.

    Raises:
        HTTPException: 403 if the topic exists and ``user`` is not its teacher.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        return
    await courses_service.require_course_teacher(db, user, topic.course_id)
    try:
        await topic_crud.delete_topic(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


_STUDENT_VISIBLE_STAGES = frozenset({TopicStage.CONVERSATION, TopicStage.SUMMARY})


def _topic_fields(topic: Topic) -> dict:
    """Fields every caller sees; set explicitly so exclude_unset keeps them."""
    return {
        "topic_id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "topic_status": TopicStage(topic.stage),
        "age_band": topic.age_band,
        "max_turns": topic.max_turns,
    }


async def _student_topics(
    db: AsyncSession, user: User, course_id: UUID
) -> list[TopicListItem]:
    """Conversation and summary topics with the student's own session state."""
    session_rows = await topic_crud.list_topics_with_user_session(
        db, course_id=course_id, user_id=user.id
    )
    return [
        TopicListItem(
            **_topic_fields(topic),
            session_status=SessionStatus(session_status) if session_status else None,
            session_id=session_id,
        )
        for topic, session_status, session_id in session_rows
        if topic.stage in _STUDENT_VISIBLE_STAGES
    ]


async def _staff_topics(db: AsyncSession, course_id: UUID) -> list[TopicListItem]:
    """Topics in every stage with answered and active-student counts."""
    student_count = await course_crud.count_active_students(db, course_id)
    count_rows = await topic_crud.list_topics_with_completed_count(db, course_id)
    return [
        TopicListItem(
            **_topic_fields(topic),
            answered_count=answered_count,
            student_count=student_count,
        )
        for topic, answered_count in count_rows
    ]


async def list_course_topics(
    db: AsyncSession, user: User, course_id: UUID
) -> CourseTopicsResponse:
    """List a course's topics; fields depend on the caller's role.

    Each role is matched explicitly; any other (or no) role is denied, so a
    future role gets no access until it is handled here.

    Raises:
        HTTPException: 404 if the course is missing or ``user`` is not a member.
    """
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        raise courses_service.course_not_found()
    role = await courses_service.get_my_course_role(db, user, course_id)
    match role:
        case CourseRole.STUDENT:
            topics = await _student_topics(db, user, course.id)
        case CourseRole.TEACHER | CourseRole.TA:
            topics = await _staff_topics(db, course.id)
        case _:
            raise courses_service.course_not_found()
    return CourseTopicsResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
        my_role=role,
        my_permissions=await courses_service.get_my_ta_permissions(
            db, user, course.id, role
        ),
        topics=topics,
    )


async def get_topic_explanation(
    db: AsyncSession, user: User, topic_id: UUID
) -> TopicExplanationResponse:
    """Return the topic's title and background (``key_terms`` not stored yet).

    Raises:
        HTTPException: 404 if the topic is missing or ``user`` is not a member
            of its course.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        raise _topic_not_found()
    if await courses_service.get_my_course_role(db, user, topic.course_id) is None:
        raise _topic_not_found()
    return TopicExplanationResponse(
        topic_id=topic.id,
        title=topic.title,
        background=topic.description,
        key_terms=[],
    )
