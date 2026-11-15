from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    TEACHER = "TEACHER"
    # API-facing only (config elevation via SUPER_ADMIN_ACCOUNTS); not stored in DB.
    SUPERADMIN = "SUPERADMIN"


class SessionStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class CourseRole(StrEnum):
    """Caller's identity inside one course (API-facing, lowercase)."""

    TEACHER = "teacher"
    TA = "ta"
    STUDENT = "student"
