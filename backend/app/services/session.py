"""Business rules for entering a student's single session per topic."""

from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.crud.session import SQLAlchemySessionStore
from app.schemas.session import (
    CreateSessionResponse,
    SessionData,
    SessionResultResponse,
    UpdateSessionPrivacyResponse,
)


class TopicNotFoundError(Exception):
    """The requested topic does not exist."""


class CourseAccessDeniedError(Exception):
    """The user is not a member of the topic's course."""


class SessionStore(Protocol):
    """Storage operations to be implemented by the CRUD layer."""

    async def get_topic_course_id(self, topic_id: UUID) -> UUID | None:
        """Return the course ID, or None when the topic does not exist."""
        ...

    async def is_course_member(self, user_id: UUID, course_id: UUID) -> bool:
        """Return whether the user currently belongs to the course."""
        ...

    async def get_session_id(self, user_id: UUID, topic_id: UUID) -> UUID | None:
        """Find an existing session regardless of completion status."""
        ...

    async def get_or_create_session_id(self, user_id: UUID, topic_id: UUID) -> UUID:
        """Atomically create IN_PROGRESS or reuse an existing session unchanged."""
        ...


async def create_or_enter_session(
    *,
    user_id: UUID,
    topic_id: UUID,
    store: SessionStore,
) -> CreateSessionResponse:
    """Enter a session using the authenticated user's ID supplied by the route."""
    course_id = await store.get_topic_course_id(topic_id)
    if course_id is None:
        raise TopicNotFoundError("Topic not found")

    # Check permission even when an old session already exists.
    if not await store.is_course_member(user_id, course_id):
        raise CourseAccessDeniedError("Course membership required")

    session_id = await store.get_session_id(user_id, topic_id)
    if session_id is None:
        session_id = await store.get_or_create_session_id(user_id, topic_id)

    return CreateSessionResponse(session_id=session_id, topic_id=topic_id)


async def create_or_enter_student_session(
    db: AsyncSession,
    user_id: UUID,
    topic_id: UUID,
) -> CreateSessionResponse:
    """Enter a student session and handle transactions and HTTP errors."""
    store = SQLAlchemySessionStore(
        db,
        initial_is_anonymous=False,
    )

    try:
        result = await create_or_enter_session(
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
            detail="Course membership required",
        ) from exc
    except Exception:
        await db.rollback()
        raise

    return result


class SessionReadStore(Protocol):
    async def get_session(
        self,
        session_id: UUID,
    ) -> SessionData | None:
        """Return session data, or None when the session does not exist."""
        ...


async def _get_owned_session(
    *,
    store: SessionReadStore,
    session_id: UUID,
    current_user_id: UUID,
) -> SessionData:
    session = await store.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the session owner",
        )

    return session


class SessionPrivacyStore(SessionReadStore, Protocol):
    async def set_is_anonymous(
        self,
        session_id: UUID,
        is_anonymous: bool,
    ) -> SessionData | None: ...


async def update_session_privacy(
    *,
    store: SessionPrivacyStore,
    session_id: UUID,
    current_user_id: UUID,
    is_anonymous: bool,
) -> UpdateSessionPrivacyResponse:
    await _get_owned_session(
        store=store,
        session_id=session_id,
        current_user_id=current_user_id,
    )

    updated_session = await store.set_is_anonymous(session_id, is_anonymous)

    if updated_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return UpdateSessionPrivacyResponse(
        session_id=updated_session.id,
        is_anonymous=updated_session.is_anonymous,
        message="匿名分享設定已更新",
    )


async def update_student_session_privacy(
    db: AsyncSession,
    current_user_id: UUID,
    session_id: UUID,
    is_anonymous: bool,
) -> UpdateSessionPrivacyResponse:
    """Update session privacy and manage the database transaction."""
    store = SQLAlchemySessionStore(db)

    try:
        result = await update_session_privacy(
            store=store,
            session_id=session_id,
            current_user_id=current_user_id,
            is_anonymous=is_anonymous,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return result


async def get_session_result(
    *,
    store: SessionReadStore,
    session_id: UUID,
    current_user_id: UUID,
) -> SessionResultResponse:
    session = await _get_owned_session(
        store=store,
        session_id=session_id,
        current_user_id=current_user_id,
    )

    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is not completed",
        )

    return SessionResultResponse(
        session_id=session.id,
        topic_id=session.topic_id,
    )


async def get_student_session_result(
    db: AsyncSession,
    current_user_id: UUID,
    session_id: UUID,
) -> SessionResultResponse:
    """Return the owner's completed session identifiers."""
    store = SQLAlchemySessionStore(db)

    return await get_session_result(
        store=store,
        session_id=session_id,
        current_user_id=current_user_id,
    )
