from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models.user import Language, User, UserLanguage, UserPassword


async def get_language_by_code(db: AsyncSession, code: str) -> Language | None:
    """Look up a language row by its BCP-47-style code.

    Args:
        db: Async SQLAlchemy session.
        code: Language code (for example ``zh-TW``).

    Returns:
        Matching ``Language`` row, or ``None`` if not found.
    """
    result = await db.execute(select(Language).where(Language.code == code))
    return result.scalar_one_or_none()


async def ensure_default_language(db: AsyncSession) -> Language:
    """Return the configured default language, creating it if missing.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        ``Language`` for ``settings.DEFAULT_LANGUAGE_CODE`` (existing or new).
    """
    code = settings.DEFAULT_LANGUAGE_CODE
    language = await get_language_by_code(db, code)
    if language is not None:
        return language
    language = Language(code=code, name=code)
    db.add(language)
    await db.flush()
    return language


async def get_user_by_account(db: AsyncSession, account_id: str) -> User | None:
    """Load a user by account_id with password and languages eagerly loaded.

    Args:
        db: Async SQLAlchemy session.
        account_id: Unique login account identifier.

    Returns:
        Matching ``User``, or ``None`` if not found.
    """
    result = await db.execute(
        select(User)
        .where(User.account_id == account_id)
        .options(
            selectinload(User.password),
            selectinload(User.languages).selectinload(UserLanguage.language),
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Load a user by id with password and languages eagerly loaded.

    Args:
        db: Async SQLAlchemy session.
        user_id: Primary key of the user.

    Returns:
        Matching ``User``, or ``None`` if not found.
    """
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.password),
            selectinload(User.languages).selectinload(UserLanguage.language),
        )
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    *,
    account_id: str,
    name: str,
    password: str,
    role: UserRole = UserRole.USER,
    must_change_password: bool = False,
) -> User:
    """Persist a new user with hashed password and default language preference.

    Args:
        db: Async SQLAlchemy session.
        account_id: Unique login account identifier.
        name: Display name.
        password: Plaintext password (hashed before storage).
        role: System role to assign (default ``USER``).
        must_change_password: When ``True``, non-exempt routes return 403.

    Returns:
        Reloaded ``User`` with password and languages loaded.

    Raises:
        RuntimeError: If the user cannot be reloaded after commit.
    """
    language = await ensure_default_language(db)
    user = User(account_id=account_id, name=name, role=role.value)
    user.password = UserPassword(
        password_hash=hash_password(password),
        must_change_password=must_change_password,
    )
    user.languages = [UserLanguage(language=language)]
    db.add(user)
    await db.commit()
    loaded = await get_user_by_id(db, user.id)
    if loaded is None:
        raise RuntimeError("failed to reload created user")
    return loaded


def preferred_language_code(user: User) -> str:
    """Return the user's first language code, or the configured default.

    Args:
        user: User with ``languages`` (and nested ``language``) available.

    Returns:
        Preferred language code string (for example ``zh-TW``).
    """
    if user.languages:
        return user.languages[0].language.code
    return settings.DEFAULT_LANGUAGE_CODE
