"""Business rules for topics (permissions follow the caller's in-course role)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CourseRole, SessionStatus, TopicStage
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import topic as topic_crud
from app.models.course import Course
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


def _write_response(topic: Topic, message: str) -> TopicWriteResponse:
    return TopicWriteResponse(
        topic_id=topic.id,
        course_id=topic.course_id,
        title=topic.title,
        description=topic.description,
        message=message,
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
            description=payload.description,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _write_response(topic, "Topic created")


async def update_topic(
    db: AsyncSession, user: User, topic_id: UUID, payload: TopicUpdateRequest
) -> TopicWriteResponse:
    """Replace a topic's title and description (course cannot change).

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not its teacher.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        raise _topic_not_found()
    await courses_service.require_course_teacher(db, user, topic.course_id)
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


async def _student_topics(
    db: AsyncSession, user: User, course: Course
) -> StudentCourseTopicsResponse:
    """Topics with the student's own session state."""
    session_rows = await topic_crud.list_topics_with_user_session(
        db, course_id=course.id, user_id=user.id
    )
    topics: list[StudentTopicListItem] = []
    for topic, session_status, session_id in session_rows:
        # A setup topic stays hidden until this student already has a session.
        if session_id is None and topic.stage == TopicStage.SETUP.value:
            continue
        topics.append(
            StudentTopicListItem(
                topic_id=topic.id,
                title=topic.title,
                description=topic.description,
                stage=TopicStage(topic.stage),
                status=SessionStatus(session_status) if session_status else None,
                session_id=session_id,
            )
        )
    return StudentCourseTopicsResponse(
        course_id=course.id,
        name=course.name,
        invite_code=course.invitation_code,
        topics=topics,
    )


async def _staff_topics(
    db: AsyncSession, course: Course
) -> TeacherCourseTopicsResponse:
    """Topics with completed-session (answered) counts."""
    count_rows = await topic_crud.list_topics_with_completed_count(db, course.id)
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
            for topic, answered_count in count_rows
        ],
    )


async def list_course_topics(
    db: AsyncSession, user: User, course_id: UUID
) -> TeacherCourseTopicsResponse | StudentCourseTopicsResponse:
    """List a course's topics in the former teacher or student shape.

    Each role is matched explicitly; any other (or no) role is denied, so a
    future role gets no access until it is handled here.

    Raises:
        HTTPException: 404 if the course is missing; 403 if not a member.
    """
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        raise courses_service.course_not_found()
    role = await courses_service.get_my_course_role(db, user, course_id)
    match role:
        case CourseRole.STUDENT:
            return await _student_topics(db, user, course)
        case CourseRole.TEACHER | CourseRole.TA:
            return await _staff_topics(db, course)
        case _:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Course membership required",
            )


async def get_topic_explanation(
    db: AsyncSession, user: User, topic_id: UUID
) -> TopicExplanationResponse:
    """Return the topic's title and background (``key_terms`` not stored yet).

    Raises:
        HTTPException: 404 if the topic is missing; 403 if not a member.
    """
    topic = await topic_crud.get_topic_by_id(db, topic_id)
    if topic is None:
        raise _topic_not_found()
    if not await session_crud.is_course_member(
        db, user_id=user.id, course_id=topic.course_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Course membership required",
        )
    return TopicExplanationResponse(
        topic_id=topic.id,
        title=topic.title,
        background=topic.description,
        key_terms=[],
    )
