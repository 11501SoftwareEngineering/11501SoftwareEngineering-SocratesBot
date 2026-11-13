from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.models.course import CourseMembership
from app.models.session import Session
from app.models.topic import Topic

_STUDENT_ROLE = "STUDENT"


async def get_topic_course_id(
    db: AsyncSession,
    topic_id: UUID,
) -> UUID | None:
    statement = select(Topic.course_id).where(Topic.id == topic_id)
    return await db.scalar(statement)


async def is_course_student(
    db: AsyncSession,
    *,
    user_id: UUID,
    course_id: UUID,
) -> bool:
    """Whether the user is an active STUDENT of the course (not teacher/TA)."""
    statement = select(CourseMembership.user_id).where(
        CourseMembership.user_id == user_id,
        CourseMembership.course_id == course_id,
        CourseMembership.role == _STUDENT_ROLE,
        CourseMembership.left_at.is_(None),
    )
    return await db.scalar(statement) is not None


async def create_session_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    topic_id: UUID,
    is_anonymous: bool,
) -> UUID | None:
    """Insert an IN_PROGRESS session; ``None`` if the user already has one."""
    statement = (
        insert(Session)
        .values(
            user_id=user_id,
            topic_id=topic_id,
            status=SessionStatus.IN_PROGRESS.value,
            is_anonymous=is_anonymous,
        )
        .on_conflict_do_nothing(
            constraint="uq_sessions_user_id_topic_id",
        )
        .returning(Session.id)
    )
    return await db.scalar(statement)


class SQLAlchemySessionStore:
    def __init__(
        self,
        db: AsyncSession,
        *,
        initial_is_anonymous: bool = False,
    ) -> None:
        self._db = db
        self._initial_is_anonymous = initial_is_anonymous

    async def get_topic_course_id(self, topic_id: UUID) -> UUID | None:
        return await get_topic_course_id(self._db, topic_id)

    async def is_course_student(
        self,
        user_id: UUID,
        course_id: UUID,
    ) -> bool:
        return await is_course_student(
            self._db,
            user_id=user_id,
            course_id=course_id,
        )

    async def create_session_id(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> UUID | None:
        return await create_session_id(
            self._db,
            user_id=user_id,
            topic_id=topic_id,
            is_anonymous=self._initial_is_anonymous,
        )
