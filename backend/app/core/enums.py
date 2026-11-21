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


class MessageSender(StrEnum):
    """ai | student"""

    AI = "ai"
    STUDENT = "student"


class DialogueAction(StrEnum):
    """complete | continue | abandon"""

    COMPLETE = "complete"
    CONTINUE = "continue"
    ABANDON = "abandon"


class DialogueOutcome(StrEnum):
    """open | completed | abandoned | closed_by_summary"""

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


class AiUsageStage(StrEnum):
    """AI usage stages (declaration order = response order)."""

    SETUP = "setup"
    DIALOGUE = "dialogue"
    REPORT = "report"
    SUMMARY = "summary"


class AgeBand(StrEnum):
    AGE_13_15 = "13-15"
    AGE_16_18 = "16-18"
    UNIVERSITY_PLUS = "university_plus"


ALLOWED_MAX_TURNS = frozenset({5, 10, 15})
