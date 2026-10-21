"""Fixed development catalog constants (keep aligned with docs/測試資料.md)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.enums import UserRole

SHARED_PASSWORD = "password1"

COURSE_ID = UUID("00000000-0000-4000-8000-000000000101")
TOPIC_ID = UUID("00000000-0000-4000-8000-000000000201")
INVITATION_CODE = "DEVJOIN01"
COURSE_NAME = "Dev Seed Course"
TOPIC_TITLE = "Dev Seed Topic"


@dataclass(frozen=True, slots=True)
class SeedAccount:
    account_id: str
    name: str
    role: UserRole


ACCOUNT_STUDENT = SeedAccount(
    account_id="dev-student",
    name="Dev Student",
    role=UserRole.USER,
)
ACCOUNT_TEACHER = SeedAccount(
    account_id="dev-teacher",
    name="Dev Teacher",
    role=UserRole.TEACHER,
)
ACCOUNT_ADMIN = SeedAccount(
    account_id="dev-admin",
    name="Dev Admin",
    role=UserRole.USER,
)

CORE_ACCOUNTS: tuple[SeedAccount, ...] = (
    ACCOUNT_STUDENT,
    ACCOUNT_TEACHER,
    ACCOUNT_ADMIN,
)

DEFAULT_PACKS: tuple[str, ...] = ("auth", "course_graph")
KNOWN_PACKS: frozenset[str] = frozenset(DEFAULT_PACKS)


def credential_summary_lines() -> list[str]:
    """Return copy-paste lines for a successful seed run."""
    return [
        "=== Dev seed catalog ===",
        f"password (all): {SHARED_PASSWORD}",
        f"student: {ACCOUNT_STUDENT.account_id}",
        f"teacher: {ACCOUNT_TEACHER.account_id}",
        f"admin:   {ACCOUNT_ADMIN.account_id}  (add to SUPER_ADMIN_ACCOUNTS)",
        f"invitation_code: {INVITATION_CODE}",
        f"course_id: {COURSE_ID}",
        f"topic_id:  {TOPIC_ID}",
        "========================",
    ]
