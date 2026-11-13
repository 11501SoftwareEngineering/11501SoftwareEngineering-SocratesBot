"""Business rules for topics (permissions follow the caller's in-course role)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CourseRole, SessionStatus
from app.crud import course as course_crud
from app.crud import topic as topic_crud
from app.models.user import User
from app.schemas.topic import (
    CourseTopicsResponse,
    TopicCreateRequest,
    TopicExplanationResponse,
    TopicListItem,
    TopicWriteResponse,
)
from app.services import courses as courses_service


def _topic_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Topic not found",
    )


async def create_topic(
    db: AsyncSession, user: User, course_id: UUID, payload: TopicCreateRequest
) -> TopicWriteResponse:
    """Create a topic in a course.

    Raises:
        HTTPException: 404 if the course is missing; 403 if not its teacher.
    """
    course = await courses_service.require_course_teacher(db, user, course_id)
    try:
        topic = await topic_crud.create_topic(
            db,
            course_id=course.id,
            created_by=user.id,
            title=payload.title,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return TopicWriteResponse(
        topic_id=topic.id,
        course_id=topic.course_id,
        title=topic.title,
        message="Topic created",
    )


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


async def list_course_topics(
    db: AsyncSession, user: User, course_id: UUID
) -> CourseTopicsResponse:
    """List a course's topics; fields depend on the caller's role.

    Raises:
        HTTPException: 404 if the course is missing or ``user`` is not a member.
    """
    course = await course_crud.get_course_by_id(db, course_id)
    role = (
        await courses_service.get_my_course_role(db, user, course_id)
        if course
        else None
    )
    if course is None or role is None:
        raise courses_service.course_not_found()

    topics: list[TopicListItem]
    if role is CourseRole.STUDENT:
        session_rows = await topic_crud.list_topics_with_user_session(
            db, course_id=course.id, user_id=user.id
        )
        topics = [
            TopicListItem(
                topic_id=topic.id,
                title=topic.title,
                description=topic.description,
                session_status=SessionStatus(session_status)
                if session_status
                else None,
                session_id=session_id,
            )
            for topic, session_status, session_id in session_rows
        ]
    else:
        student_count = await course_crud.count_active_students(db, course.id)
        count_rows = await topic_crud.list_topics_with_completed_count(db, course.id)
        topics = [
            TopicListItem(
                topic_id=topic.id,
                title=topic.title,
                description=topic.description,
                answered_count=answered_count,
                student_count=student_count,
            )
            for topic, answered_count in count_rows
        ]
    return CourseTopicsResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
        my_role=role,
        my_permissions=[],
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
