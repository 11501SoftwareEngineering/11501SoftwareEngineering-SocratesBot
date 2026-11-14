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


class TaPermission(StrEnum):
    """Per-course TA permissions (declaration order = response order)."""

    EDIT_TOPICS = "edit_topics"
    VIEW_REPORTS = "view_reports"
    EDIT_SUMMARY = "edit_summary"
    VIEW_MEMBERS = "view_members"
