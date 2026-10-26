"""Business rules for teacher/student topic management."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import topic as topic_crud
from app.models.topic import Topic
from app.models.user import User
from app.schemas.topic import (
    StudentCourseTopicsResponse,
    StudentTopicListItem,
    TeacherCourseTopicsResponse,
    TeacherTopicListItem,
    TopicCreateRequest,
    TopicExplanationResponse,
    TopicUpdateRequest,
    TopicWriteResponse,
)


async def _require_course_instructor(
    db: AsyncSession, teacher: User, course_id: UUID
) -> None:
    if not await course_crud.is_course_instructor(
        db, course_id=course_id, teacher_id=teacher.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Course instructor required",
        )


async def _get_instructed_topic(
    db: AsyncSession, teacher: User, topic_id: UUID
) -> Topic:
    """Return the topic if it exists and ``teacher`` instructs its course.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    await _require_course_instructor(db, teacher, topic.course_id)
    return topic


def _write_response(topic: Topic, message: str) -> TopicWriteResponse:
    return TopicWriteResponse(
        topic_id=topic.id,
        course_id=topic.course_id,
        title=topic.title,
        description=topic.description,
        message=message,
    )


async def create_topic(
    db: AsyncSession, teacher: User, payload: TopicCreateRequest
) -> TopicWriteResponse:
    """Create a topic in a course the teacher instructs.

    Raises:
        HTTPException: 404 if the course is missing; 403 if not an instructor.
    """
    course = await course_crud.get_course_by_id(db, payload.course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    await _require_course_instructor(db, teacher, course.id)
    try:
        topic = await topic_crud.create_topic(
            db,
            course_id=course.id,
            created_by=teacher.id,
            title=payload.title,
            description=payload.description,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _write_response(topic, "Topic created")


async def update_topic(
    db: AsyncSession, teacher: User, topic_id: UUID, payload: TopicUpdateRequest
) -> TopicWriteResponse:
    """Replace a topic's title and description (course cannot change).

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not an instructor.
    """
    topic = await _get_instructed_topic(db, teacher, topic_id)
    try:
        topic = await topic_crud.update_topic(
            db,
            topic,
            title=payload.title,
            description=payload.description,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _write_response(topic, "Topic updated")


async def delete_topic(db: AsyncSession, teacher: User, topic_id: UUID) -> None:
    """Hard-delete a topic; idempotent when already gone (no 404).

    Sessions go via ``ON DELETE CASCADE``.

    Raises:
        HTTPException: 403 if the topic exists and teacher is not an instructor.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        return
    await _require_course_instructor(db, teacher, topic.course_id)
    try:
        await topic_crud.delete_topic(db, topic)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def list_teacher_course_topics(
    db: AsyncSession, teacher: User, course_id: UUID
) -> TeacherCourseTopicsResponse:
    """Return course info and its topics with answered counts.

    Raises:
        HTTPException: 404 if the course is missing; 403 if not an instructor.
    """
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    await _require_course_instructor(db, teacher, course.id)
    rows = await topic_crud.list_topics_with_completed_count(db, course.id)
    return TeacherCourseTopicsResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
        topics=[
            TeacherTopicListItem(
                topic_id=topic.id,
                title=topic.title,
                description=topic.description,
                answered_count=answered_count,
            )
            for topic, answered_count in rows
        ],
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
    """Return the topic's title and background (``key_terms`` not stored yet).

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
        background=topic.description,
        key_terms=[],
    )
