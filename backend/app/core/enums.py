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


class DialogueOutcome(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    CLOSED_BY_SUMMARY = "closed_by_summary"


class TopicStage(StrEnum):
    SETUP = "setup"
    CONVERSATION = "conversation"
    SUMMARY = "summary"


class GenerationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class AgeBand(StrEnum):
    AGE_13_15 = "13-15"
    AGE_16_18 = "16-18"
    UNIVERSITY_PLUS = "university_plus"


ALLOWED_MAX_TURNS = frozenset({5, 10, 15})
