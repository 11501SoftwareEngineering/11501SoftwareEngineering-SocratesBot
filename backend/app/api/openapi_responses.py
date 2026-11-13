"""Reusable OpenAPI ``responses=`` fragments for FastAPI routes."""

from __future__ import annotations

from typing import Any

from app.core.auth_policies import (
    AUTH_UNAUTHORIZED_DETAIL,
    CURRENT_PASSWORD_INCORRECT_DETAIL,
    LOGIN_RATE_LIMITED_DETAIL,
    NEW_PASSWORD_SAME_AS_CURRENT_DETAIL,
)


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
    403: json_detail_example(
        "Course teacher required",
        "Course teacher required",
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

_TOPIC_TITLE_TOO_SHORT_422 = json_detail_example(
    "Request validation failed",
    [
        {
            "type": "string_too_short",
            "loc": ["body", "title"],
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
        "Course teacher required",
        "Course teacher required",
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
    422: _TOPIC_TITLE_TOO_SHORT_422,
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
    403: json_detail_example(
        "Course membership required",
        "Course membership required",
    ),
    404: json_detail_example(
        "Topic not found",
        "Topic not found",
    ),
}

SESSION_ENTRY_RESPONSES: dict[int | str, dict[str, Any]] = {
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
    404: json_detail_example(
        "Topic not found",
        "Topic not found",
    ),
}
