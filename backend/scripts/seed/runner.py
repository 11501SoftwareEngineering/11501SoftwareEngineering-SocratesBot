"""Resolve packs and run DB-only development seed."""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.yaml_config import yaml_config
from scripts.seed.catalog import (
    ACCOUNT_ADMIN,
    DEFAULT_PACKS,
    KNOWN_PACKS,
    credential_summary_lines,
)
from scripts.seed.packs.auth import seed_auth
from scripts.seed.packs.course_graph import seed_course_graph

logger = logging.getLogger(__name__)

PackFn = Callable[[AsyncSession], Awaitable[None]]

PACK_REGISTRY: dict[str, PackFn] = {
    "auth": seed_auth,
    "course_graph": seed_course_graph,
}


class SeedError(Exception):
    """Seed aborted due to environment or pack selection."""


def resolve_packs(seed_packs_env: str | None = None) -> tuple[str, ...]:
    """Return pack names to run.

    Unset/empty ``SEED_PACKS`` → default core packs.
    Set → comma-separated list replaces the default set.
    """
    raw = seed_packs_env if seed_packs_env is not None else os.environ.get("SEED_PACKS")
    if raw is None or raw.strip() == "":
        return DEFAULT_PACKS

    names = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not names:
        return DEFAULT_PACKS

    unknown = [name for name in names if name not in KNOWN_PACKS]
    if unknown:
        known = ", ".join(sorted(KNOWN_PACKS))
        msg = f"unknown seed pack(s): {', '.join(unknown)} (known: {known})"
        raise SeedError(msg)
    return names


def require_development() -> None:
    if settings.APP_ENV != "development":
        msg = f"seed refused: APP_ENV={settings.APP_ENV!r} (development only)"
        raise SeedError(msg)


def warn_if_admin_not_elevated() -> None:
    if ACCOUNT_ADMIN.account_id not in yaml_config.SUPER_ADMIN_ACCOUNTS:
        logger.warning(
            "%s is not in SUPER_ADMIN_ACCOUNTS; "
            "run `make -C backend seed` (config assist) or edit config.yaml, "
            "then restart the server",
            ACCOUNT_ADMIN.account_id,
        )


async def run_seed_db(
    *,
    packs: Sequence[str] | None = None,
    print_summary: bool = True,
) -> None:
    """Insert selected packs. Caller must already enforce development when needed."""
    selected = tuple(packs) if packs is not None else resolve_packs()
    async with AsyncSessionLocal() as db:
        try:
            for name in selected:
                pack_fn = PACK_REGISTRY[name]
                await pack_fn(db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    warn_if_admin_not_elevated()
    if print_summary:
        for line in credential_summary_lines():
            print(line)


async def run_seed_for_cli() -> None:
    require_development()
    await run_seed_db(print_summary=True)
