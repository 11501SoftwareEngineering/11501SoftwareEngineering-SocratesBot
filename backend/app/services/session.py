"""Business rules for creating a student's single session per topic."""

from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.crud.session import SQLAlchemySessionStore
from app.schemas.session import CreateSessionResponse


class TopicNotFoundError(Exception):
    """The requested topic does not exist."""


class CourseAccessDeniedError(Exception):
    """The user is not a student of the topic's course."""


class SessionAlreadyExistsError(Exception):
    """The student already has a session for this topic."""


class SessionStore(Protocol):
    """Storage operations to be implemented by the CRUD layer."""

    async def get_topic_course_id(self, topic_id: UUID) -> UUID | None:
        """Return the course ID, or None when the topic does not exist."""
        ...

    async def is_course_student(self, user_id: UUID, course_id: UUID) -> bool:
        """Return whether the user is currently a student of the course."""
        ...

    async def create_session_id(self, user_id: UUID, topic_id: UUID) -> UUID | None:
        """Atomically create IN_PROGRESS; None if a session already exists."""
        ...


async def create_session(
    *,
    user_id: UUID,
    topic_id: UUID,
    store: SessionStore,
) -> CreateSessionResponse:
    """Create the authenticated student's session for a topic."""
    course_id = await store.get_topic_course_id(topic_id)
    if course_id is None:
        raise TopicNotFoundError("Topic not found")

    if not await store.is_course_student(user_id, course_id):
        raise CourseAccessDeniedError("Course student required")

    session_id = await store.create_session_id(user_id, topic_id)
    if session_id is None:
        raise SessionAlreadyExistsError("Session already exists")

    return CreateSessionResponse(
        session_id=session_id,
        topic_id=topic_id,
        session_status=SessionStatus.IN_PROGRESS,
    )


async def create_student_session(
    db: AsyncSession,
    user_id: UUID,
    topic_id: UUID,
) -> CreateSessionResponse:
    """Create a student session and handle transactions and HTTP errors."""
    store = SQLAlchemySessionStore(
        db,
        initial_is_anonymous=False,
    )

    try:
        result = await create_session(
            user_id=user_id,
            topic_id=topic_id,
            store=store,
        )
        await db.commit()
    except TopicNotFoundError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        ) from exc
    except CourseAccessDeniedError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Course student required",
        ) from exc
    except SessionAlreadyExistsError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already exists for this topic",
        ) from exc
    except Exception:
        await db.rollback()
        raise

    return result
