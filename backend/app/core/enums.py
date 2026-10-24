from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    TEACHER = "TEACHER"
    # API-facing only (config elevation via SUPER_ADMIN_ACCOUNTS); not stored in DB.
    SUPERADMIN = "SUPERADMIN"


class SessionStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
