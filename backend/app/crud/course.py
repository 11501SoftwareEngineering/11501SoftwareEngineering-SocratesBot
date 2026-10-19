from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course

_INVITE_CODE_ALPHABET = string.ascii_uppercase + string.digits
_INVITE_CODE_LENGTH = 8
_MAX_CREATE_ATTEMPTS = 10


async def create_course(
    db: AsyncSession,
    *,
    owner_id,
    name: str,
    description: str | None,
) -> Course:
    """Create a course with a unique invitation code."""

    for _ in range(_MAX_CREATE_ATTEMPTS):
        invitation_code = "".join(
            secrets.choice(_INVITE_CODE_ALPHABET) for _ in range(_INVITE_CODE_LENGTH)
        )

        existing_id = await db.scalar(
            select(Course.id).where(Course.invitation_code == invitation_code)
        )
        if existing_id is not None:
            continue

        course = Course(
            owner_id=owner_id,
            name=name,
            description=description,
            invitation_code=invitation_code,
        )
        db.add(course)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

            # Retry only when the invitation code collided with another row.
            collision_id = await db.scalar(
                select(Course.id).where(Course.invitation_code == invitation_code)
            )
            if collision_id is not None:
                continue

            raise

        await db.refresh(course)
        return course

    raise RuntimeError("Could not generate a unique course invitation code.")
