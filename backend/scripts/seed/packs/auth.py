"""Core auth pack: fixed student / teacher / admin users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import hash_password
from app.crud.user import ensure_default_language, get_user_by_account
from app.models.user import User, UserLanguage, UserPassword
from scripts.seed.catalog import CORE_ACCOUNTS, SHARED_PASSWORD


async def seed_auth(db: AsyncSession) -> None:
    missing = []
    for account in CORE_ACCOUNTS:
        existing = await get_user_by_account(db, account.account_id)
        if existing is None:
            missing.append(account)
    if not missing:
        return

    language = await ensure_default_language(db)
    password_digest = await run_in_threadpool(hash_password, SHARED_PASSWORD)

    for account in missing:
        user = User(
            account_id=account.account_id,
            name=account.name,
            role=account.role.value,
        )
        user.password = UserPassword(
            password_hash=password_digest,
            must_change_password=False,
        )
        user.languages = [UserLanguage(language=language)]
        db.add(user)

    await db.flush()


async def get_user_id_by_account(db: AsyncSession, account_id: str):
    result = await db.execute(select(User.id).where(User.account_id == account_id))
    return result.scalar_one_or_none()
