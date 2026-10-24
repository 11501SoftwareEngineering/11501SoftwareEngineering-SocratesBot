"""Business rules for student topic browsing."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import topic as topic_crud
from app.models.user import User
from app.schemas.topic import (
    StudentCourseTopicsResponse,
    StudentTopicListItem,
    TopicExplanationResponse,
)


async def _require_course_member(
    db: AsyncSession, student: User, course_id: UUID
) -> None:
    if not await session_crud.is_course_member(
        db, user_id=student.id, course_id=course_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Course membership required",
        )


async def list_student_course_topics(
    db: AsyncSession, student: User, course_id: UUID
) -> StudentCourseTopicsResponse:
    """Return course info and topics with the student's own session state.

    Raises:
        HTTPException: 404 if the course is missing; 403 if not a member.
    """
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    await _require_course_member(db, student, course.id)
    rows = await topic_crud.list_topics_with_user_session(
        db, course_id=course.id, user_id=student.id
    )
    return StudentCourseTopicsResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
        topics=[
            StudentTopicListItem(
                topic_id=topic.id,
                title=topic.title,
                description=topic.description,
                status=SessionStatus(session_status) if session_status else None,
                session_id=session_id,
            )
            for topic, session_status, session_id in rows
        ],
    )


async def get_topic_explanation(
    db: AsyncSession, student: User, topic_id: UUID
) -> TopicExplanationResponse:
    """Return the topic's title and description.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not a member.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    await _require_course_member(db, student, topic.course_id)
    return TopicExplanationResponse(
        topic_id=topic.id,
        title=topic.title,
        description=topic.description,
    )
