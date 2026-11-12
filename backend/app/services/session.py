"""Business rules for entering a student's single session per topic."""

from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogueOutcome, TopicStage
from app.crud.session import SQLAlchemySessionStore
from app.schemas.session import CreateSessionResponse


class TopicNotFoundError(Exception):
    """The requested topic does not exist."""


class TopicNotOpenError(Exception):
    """The topic is still in setup, so a new dialogue is not created."""


class TopicClosedError(Exception):
    """The topic is in summary, so a new dialogue is not created."""


class DialogueExistsError(Exception):
    """This student already has the one dialogue for the topic."""

    def __init__(self, session_id: UUID, session_status: str) -> None:
        self.session_id = session_id
        self.session_status = session_status
        super().__init__("Dialogue already exists")


class CourseAccessDeniedError(Exception):
    """The user is not a member of the topic's course."""


class SessionStore(Protocol):
    """Storage operations to be implemented by the CRUD layer."""

    async def get_topic_course_id(self, topic_id: UUID) -> UUID | None:
        """Return the course ID, or None when the topic does not exist."""
        ...

    async def get_topic_stage(self, topic_id: UUID) -> str | None:
        """Return the topic stage, or None when the topic does not exist."""
        ...

    async def is_course_member(self, user_id: UUID, course_id: UUID) -> bool:
        """Return whether the user currently belongs to the course."""
        ...

    async def get_session_id(self, user_id: UUID, topic_id: UUID) -> UUID | None:
        """Find an existing session regardless of completion status."""
        ...

    async def get_session_outcome(self, user_id: UUID, topic_id: UUID) -> str | None:
        """Return the dialogue outcome, or None when the pair does not exist."""
        ...

    async def insert_session_id(self, user_id: UUID, topic_id: UUID) -> UUID | None:
        """Insert one dialogue. Return None when the unique pair already exists."""
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

    stage = await store.get_topic_stage(topic_id)
    if stage == TopicStage.SETUP.value:
        raise TopicNotOpenError("Topic is still in setup")

    session_id = await store.get_session_id(user_id, topic_id)
    if session_id is not None:
        outcome = await store.get_session_outcome(user_id, topic_id)
        raise DialogueExistsError(
            session_id,
            outcome or DialogueOutcome.OPEN.value,
        )
    if stage == TopicStage.SUMMARY.value:
        raise TopicClosedError("Topic is in summary")

    session_id = await store.insert_session_id(user_id, topic_id)
    if session_id is None:
        session_id = await store.get_session_id(user_id, topic_id)
        if session_id is None:
            raise RuntimeError("Session was not found after an insert conflict")
        outcome = await store.get_session_outcome(user_id, topic_id)
        raise DialogueExistsError(
            session_id,
            outcome or DialogueOutcome.OPEN.value,
        )

    return CreateSessionResponse(
        session_id=session_id,
        topic_id=topic_id,
        session_status=DialogueOutcome.OPEN.value,
    )


async def create_or_enter_student_session(
    db: AsyncSession,
    user_id: UUID,
    topic_id: UUID,
) -> CreateSessionResponse:
    """Enter a student session and handle transactions and HTTP errors."""
    store = SQLAlchemySessionStore(db)

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
    except TopicNotOpenError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic is still in setup",
        ) from exc
    except TopicClosedError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic is in summary",
        ) from exc
    except DialogueExistsError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Dialogue already exists",
                "session_id": str(exc.session_id),
                "session_status": exc.session_status,
            },
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
