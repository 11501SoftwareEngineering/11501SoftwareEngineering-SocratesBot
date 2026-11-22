"""Reusable OpenAPI ``responses=`` fragments for FastAPI routes."""

from __future__ import annotations

from typing import Any

from app.core.auth_policies import (
    AUTH_UNAUTHORIZED_DETAIL,
    CURRENT_PASSWORD_INCORRECT_DETAIL,
    LOGIN_RATE_LIMITED_DETAIL,
    NEW_PASSWORD_SAME_AS_CURRENT_DETAIL,
)
from app.schemas.dialogue import StreamDoneEvent


def json_detail_example(description: str, detail: Any) -> dict[str, Any]:
    """Build an OpenAPI response entry with a JSON ``detail`` example."""
    return {
        "description": description,
        "content": {
            "application/json": {
                "example": {"detail": detail},
            }
        },
    }


def json_detail_examples(description: str, examples: dict[str, Any]) -> dict[str, Any]:
    """Build an OpenAPI response entry with named JSON ``detail`` examples."""
    return {
        "description": description,
        "content": {
            "application/json": {
                "examples": {
                    name: {"value": {"detail": detail}}
                    for name, detail in examples.items()
                },
            }
        },
    }


_ACCOUNT_ALREADY_EXISTS_DETAIL = "Account already exists"
_ACCOUNT_NAME_RESERVED_DETAIL = "Account name reserved"

LOGIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        "Invalid account or password",
        "Invalid account or password",
    ),
    429: {
        **json_detail_example(
            LOGIN_RATE_LIMITED_DETAIL,
            LOGIN_RATE_LIMITED_DETAIL,
        ),
        "headers": {
            "Retry-After": {
                "description": "Seconds until login may be retried",
                "schema": {"type": "integer"},
            }
        },
    },
}

REGISTER_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Registration rejected",
        {
            "account_already_exists": _ACCOUNT_ALREADY_EXISTS_DETAIL,
            "account_name_reserved": _ACCOUNT_NAME_RESERVED_DETAIL,
        },
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 8 characters",
            }
        ],
    ),
}

TEACHER_CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Teacher create rejected",
        {
            "account_already_exists": _ACCOUNT_ALREADY_EXISTS_DETAIL,
            "account_name_reserved": _ACCOUNT_NAME_RESERVED_DETAIL,
        },
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "account_id"],
                "msg": "String should have at least 1 character",
            }
        ],
    ),
}

TEACHER_PASSWORD_RESET_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Teacher password reset forbidden",
        {
            "admin_privileges_required": "Admin privileges required",
            "elevated_admin_account": "Cannot reset elevated admin account password",
        },
    ),
    404: json_detail_example("Teacher not found", "Teacher not found"),
}

PASSWORD_CHANGE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Password change rejected",
        {
            "wrong_current_password": CURRENT_PASSWORD_INCORRECT_DETAIL,
            "same_as_current_password": NEW_PASSWORD_SAME_AS_CURRENT_DETAIL,
        },
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "new_password"],
                "msg": "String should have at least 8 characters",
            }
        ],
    ),
}

COURSE_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
}

COURSE_CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Teacher privileges required",
        "Teacher privileges required",
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "name"],
                "msg": "String should have at least 1 character",
            }
        ],
    ),
    503: json_detail_example(
        "Could not allocate invitation code; retry later",
        "Could not allocate invitation code; retry later",
    ),
}

COURSE_JOIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Join rejected",
        {
            "invalid_invite_format": "Invalid invitation code format",
            "already_a_member": "Already a member of this course",
            "already_teacher_or_ta": "Already a teacher or TA of this course",
            "cannot_rejoin_after_leaving": "Cannot rejoin after leaving this course",
        },
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Student privileges required",
        "Student privileges required",
    ),
    404: json_detail_example(
        "Course not found for this invitation code",
        "Course not found for this invitation code",
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "invite_code"],
                "msg": "String should have at least 8 characters",
            }
        ],
    ),
}

COURSE_GET_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    404: json_detail_example(
        "Not a course member or course not found",
        "Course not found",
    ),
}

COURSE_UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Course teacher required",
        "Course teacher required",
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "name"],
                "msg": "String should have at least 1 character",
            }
        ],
    ),
}

COURSE_DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Only the course creator can delete this course",
        "Only the course creator can delete this course",
    ),
}

COURSE_LEAVE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Teachers and TAs cannot leave a course this way",
        "Teachers and TAs cannot leave a course this way",
    ),
}

COURSE_MEMBER_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        (
            "role=student needs the course teacher or a TA with view_members; "
            "role=ta or no filter needs the course teacher"
        ),
        {
            "students": "Course teacher or TA with view_members permission required",
            "tas": "Course teacher required",
        },
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
    422: json_detail_example(
        "Invalid role query value",
        [
            {
                "type": "literal_error",
                "loc": ["query", "role"],
                "msg": "Input should be 'student' or 'ta'",
            }
        ],
    ),
}

COURSE_STUDENT_REMOVE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Course teacher required",
        "Course teacher required",
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
}

_INVALID_LANGUAGE_DETAIL = "Invalid language code"

PREFERENCES_UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_example(
        "Unsupported preferred language",
        _INVALID_LANGUAGE_DETAIL,
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "string_too_short",
                "loc": ["body", "preferred_language"],
                "msg": "String should have at least 1 character",
            }
        ],
    ),
}

_TOPIC_CREATE_INVALID_422 = json_detail_example(
    "Request validation failed",
    [
        {
            "type": "string_too_short",
            "loc": ["body", "course_description"],
            "msg": "String should have at least 1 character",
        }
    ],
)

TOPIC_CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Course teacher or TA with edit_topics permission required",
        "Course teacher or TA with edit_topics permission required",
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
    422: _TOPIC_CREATE_INVALID_422,
    502: json_detail_example(
        "Inquiry generation failed",
        "Inquiry generation failed",
    ),
    503: json_detail_example(
        "Inquiry generation failed",
        "Inquiry generation failed",
    ),
}

TOPIC_DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Course teacher required",
        "Course teacher required",
    ),
}

COURSE_TOPIC_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    404: json_detail_example(
        "Not a course member or course not found",
        "Course not found",
    ),
}

TOPIC_EXPLANATION_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    404: json_detail_example(
        "Not a course member, topic not found, or a student asking for a setup topic",
        "Topic not found",
    ),
}

SESSION_ENTRY_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: json_detail_example(
        "Class synthesis temporarily blocks new dialogues",
        "Class synthesis is in progress; new dialogues are temporarily closed",
    ),
    400: json_detail_example(
        "New session cannot be created in summary", "Topic is in summary"
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Session entry denied",
        {
            "course_membership_required": "Course membership required",
            "password_change_required": "Password change required",
        },
    ),
    404: json_detail_examples(
        "Topic missing or still in setup",
        {"missing": "Topic not found", "setup": "Topic is still in setup"},
    ),
}

_COURSE_TEACHER_403 = json_detail_example(
    "Course teacher required",
    "Course teacher required",
)
_UNKNOWN_TA_PERMISSION_422 = json_detail_example(
    "Request validation failed",
    [
        {
            "type": "enum",
            "loc": ["body", "permissions", 0],
            "msg": (
                "Input should be 'edit_topics', 'view_reports', "
                "'edit_summary' or 'view_members'"
            ),
        }
    ],
)


_TA_ASSIGN_400 = json_detail_examples(
    (
        "The account is already a TA of this course, is a teacher account, or is "
        "an admin; or its membership changed concurrently (retry)"
    ),
    {
        "already_ta": "Already a TA of this course",
        "teacher_account": "Teacher accounts cannot be TAs",
        "admin": "Admins cannot be TAs",
        "concurrent": "Course membership changed concurrently; retry",
    },
)
_TA_ASSIGN_404 = json_detail_examples(
    "Course or account not found",
    {
        "course_not_found": "Course not found",
        "account_not_found": "Account not found",
    },
)

COURSE_TA_ASSIGN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _TA_ASSIGN_400,
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: _COURSE_TEACHER_403,
    404: _TA_ASSIGN_404,
    422: json_detail_examples(
        "account_id is blank, a permission is unknown, or check is not a boolean",
        {
            "blank_account_id": [
                {
                    "type": "string_too_short",
                    "loc": ["body", "account_id"],
                    "msg": "String should have at least 1 character",
                }
            ],
            "unknown_permission": [
                {
                    "type": "enum",
                    "loc": ["body", "permissions", 0],
                    "msg": (
                        "Input should be 'edit_topics', 'view_reports', "
                        "'edit_summary' or 'view_members'"
                    ),
                }
            ],
        },
    ),
}

COURSE_TA_UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: _COURSE_TEACHER_403,
    404: json_detail_examples(
        "Course or TA not found",
        {
            "course_not_found": "Course not found",
            "ta_not_found": "TA not found",
        },
    ),
    422: _UNKNOWN_TA_PERMISSION_422,
}

COURSE_TA_REVOKE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: _COURSE_TEACHER_403,
    404: json_detail_examples(
        "Course or TA not found",
        {
            "course_not_found": "Course not found",
            "ta_not_found": "TA not found",
        },
    ),
}

_INQUIRY_DENIED = json_detail_examples(
    "Inquiry access denied",
    {
        "not_teacher": "Teacher privileges required",
        "not_instructor": "Course teacher required",
        "missing_setup_permission": "Course teacher or TA with edit_topics permission required",
    },
)
_INQUIRY_MISSING = json_detail_example("Topic not found", "Topic not found")
_INQUIRY_UNAUTHORIZED = json_detail_example(
    AUTH_UNAUTHORIZED_DETAIL,
    AUTH_UNAUTHORIZED_DETAIL,
)

INQUIRY_MODEL_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _INQUIRY_UNAUTHORIZED,
    403: json_detail_example(
        "Teacher or TA privileges required",
        "Teacher or TA privileges required",
    ),
}

INQUIRY_SETUP_READ_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: _INQUIRY_UNAUTHORIZED,
    403: _INQUIRY_DENIED,
    404: _INQUIRY_MISSING,
}

INQUIRY_SETUP_WRITE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Inquiry was not saved",
        {
            "not_in_setup": "Topic is not in setup",
        },
    ),
    401: _INQUIRY_UNAUTHORIZED,
    403: _INQUIRY_DENIED,
    404: _INQUIRY_MISSING,
    422: json_detail_example(
        "Request validation failed",
        "Request validation failed",
    ),
}

_INQUIRY_GENERATION_FAILED = json_detail_example(
    "Inquiry generation failed",
    "Inquiry generation failed",
)

INQUIRY_GENERATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    **INQUIRY_SETUP_WRITE_RESPONSES,
    409: json_detail_example("Inquiry was updated", "Inquiry was updated"),
    502: _INQUIRY_GENERATION_FAILED,
    503: _INQUIRY_GENERATION_FAILED,
}

SUMMARY_PUBLISH_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Summary was not published",
        {
            "not_reviewed": {
                "version": 3,
                "summary_status": "draft",
                "message": "Summary is not reviewed",
            },
            "identifier": "Summary contains a name or identifier",
        },
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Course instructor required",
        "Course instructor required",
    ),
    404: json_detail_examples(
        "Topic or summary not found",
        {
            "topic_not_found": "Topic not found",
            "summary_not_found": "Summary not found",
        },
    ),
}

INQUIRY_PUBLISH_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_example(
        "Topic is not in setup",
        "Topic is not in setup",
    ),
    401: _INQUIRY_UNAUTHORIZED,
    403: _INQUIRY_DENIED,
    404: _INQUIRY_MISSING,
    422: json_detail_examples(
        "Inquiry was not published",
        {
            "incomplete": "Incomplete setup: topic",
            "invalid_model": "Invalid model id",
            "invalid": [
                {
                    "type": "missing",
                    "loc": ["body", "setup", "age_band"],
                    "msg": "Field required",
                }
            ],
        },
    ),
}


# These describe existing runtime branches; they do not change authorization or
# lifecycle rules. Student ownership deliberately returns 404 rather than 403.
_ACTIVE_RESPONSES = {
    401: json_detail_example(AUTH_UNAUTHORIZED_DETAIL, AUTH_UNAUTHORIZED_DETAIL),
    403: json_detail_example("Password change required", "Password change required"),
}
DIALOGUE_READ_RESPONSES = {
    **_ACTIVE_RESPONSES,
    404: json_detail_example("Missing session or another owner", "Session not found"),
}
DIALOGUE_STREAM_RESPONSES = {
    **DIALOGUE_READ_RESPONSES,
    200: {
        "description": "One unnamed text event followed by a named done event. Errors before SSE starts are JSON. CR/CRLF in text normalize to LF.",
        "content": {
            "text/event-stream": {
                "schema": {"type": "string"},
                "example": 'data: What supports that view?\n\nevent: done\ndata: {"message_id":"44444444-4444-4444-4444-444444444444","completed_turns":1,"is_completed":false,"awaiting_end_consent":false}\n\n',
            }
        },
        "x-sse-events": {
            "message": {
                "description": "Unnamed event; join data lines with LF to recover reply text.",
                "schema": {"type": "string"},
            },
            "done": {
                "description": "Terminal event whose data is JSON; not a second reply.",
                "schema": StreamDoneEvent.model_json_schema(),
            },
        },
    },
    400: json_detail_examples(
        "Dialogue cannot accept a new reply",
        {"closed": "Dialogue is not accepting replies", "cap": "Turn cap reached"},
    ),
    409: json_detail_examples(
        "Reply conflicts with concurrent state",
        {
            "busy": "Another reply is in progress",
            "changed": "Dialogue changed while replying",
            "ended_during_reply": "Dialogue is not accepting replies",
        },
    ),
    413: json_detail_example(
        "Context cannot fit the configured token budget; detail explains the limit",
        "Latest message exceeds the dialogue context budget",
    ),
    502: json_detail_example("Provider or model output failure", "Model call failed"),
    503: json_detail_examples(
        "Provider unavailable or unsupported tokenizer",
        {
            "provider": "Model call failed",
            "tokenizer": "Configured model tokenizer is not supported",
        },
    ),
}
DIALOGUE_END_RESPONSES = {
    **DIALOGUE_READ_RESPONSES,
    400: json_detail_example("Dialogue already ended", "Dialogue has already ended"),
    409: json_detail_examples(
        "Cannot apply end action yet",
        {
            "not_ready": "Inquiry goal is not met",
            "too_early": "Finish early requires three student answers",
            "ended": "Dialogue has already ended",
            "busy": "Another reply is in progress",
        },
    ),
}
REPORT_START_RESPONSES = {
    **DIALOGUE_READ_RESPONSES,
    409: json_detail_example(
        "Only completed or ended dialogues can produce a report",
        "Dialogue is not report-eligible",
    ),
}
REPORT_READ_RESPONSES = {
    **REPORT_START_RESPONSES,
    404: json_detail_examples(
        "Missing/other-owner session, or no report attempt",
        {"session": "Session not found", "report": "Report not found"},
    ),
}
TEACHING_REPORT_READ_RESPONSES = {
    **_ACTIVE_RESPONSES,
    403: json_detail_examples(
        "Teacher access denied",
        {
            "password": "Password change required",
            "role": "Teacher privileges required",
            "course": "Course instructor required",
        },
    ),
    404: json_detail_example("Topic not found", "Topic not found"),
}
TEACHING_REPORT_RETRY_RESPONSES = {
    **TEACHING_REPORT_READ_RESPONSES,
    404: json_detail_examples(
        "Topic or matching session missing",
        {"topic": "Topic not found", "session": "Session not found"},
    ),
    409: REPORT_START_RESPONSES[409],
}

# Stage1 now distinguishes semantic rejection (string detail) from request
# validation (list detail). Opening generation also uses the same timeout mapper.
_STAGE1_VALIDATION = json_detail_examples(
    "Invalid request or course description needs revision",
    {
        "validation": [
            {
                "type": "missing",
                "loc": ["body", "course_description"],
                "msg": "Field required",
            }
        ],
        "semantic": "Please revise the course description. Name the topic.",
    },
)
_STAGE1_TIMEOUT = json_detail_example(
    "Model generation timed out",
    "Course setup took longer than 45 seconds and was stopped. Your input was kept; try again or shorten the description.",
)
TOPIC_CREATE_RESPONSES.update({422: _STAGE1_VALIDATION, 504: _STAGE1_TIMEOUT})
INQUIRY_GENERATE_RESPONSES.update({422: _STAGE1_VALIDATION, 504: _STAGE1_TIMEOUT})
# generate/refine do not write and cannot hit the opening write's stale guard.
INQUIRY_SUGGEST_RESPONSES = {
    key: value for key, value in INQUIRY_GENERATE_RESPONSES.items() if key != 409
}
