"""Reusable OpenAPI ``responses=`` fragments for FastAPI routes."""

from __future__ import annotations

from typing import Any

from app.core.auth_policies import (
    AUTH_UNAUTHORIZED_DETAIL,
    CURRENT_PASSWORD_INCORRECT_DETAIL,
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
                "loc": ["body", "account"],
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

STUDENT_COURSE_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Student privileges required",
        "Student privileges required",
    ),
}

STUDENT_COURSE_JOIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Join rejected",
        {
            "invalid_invite_format": "Invalid invitation code format",
            "already_a_member": "Already a member of this course",
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

STUDENT_COURSE_LEAVE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Student privileges required",
        "Student privileges required",
    ),
}

TEACHER_COURSE_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Teacher privileges required",
        "Teacher privileges required",
    ),
}

TEACHER_COURSE_CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
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

TEACHER_COURSE_STUDENT_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Teacher privileges required",
        "Teacher privileges required",
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
}

TEACHER_COURSE_STUDENT_ADD_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_example(
        "Student is already in this course",
        "Student is already in this course",
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Teacher privileges required",
        "Teacher privileges required",
    ),
    404: json_detail_examples(
        "Course or student not found",
        {
            "course_not_found": "Course not found",
            "student_not_found": "Student not found",
        },
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

TEACHER_COURSE_DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Delete denied",
        {
            "not_teacher": "Teacher privileges required",
            "not_creator": "Only the course creator can delete this course",
        },
    ),
}

TEACHER_COURSE_STUDENT_REMOVE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Teacher privileges required",
        "Teacher privileges required",
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

TEACHER_TOPIC_CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Create denied",
        {
            "not_teacher": "Teacher privileges required",
            "not_instructor": "Course instructor required",
        },
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
    422: _TOPIC_TITLE_TOO_SHORT_422,
}

TEACHER_TOPIC_UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Update denied",
        {
            "not_teacher": "Teacher privileges required",
            "not_instructor": "Course instructor required",
        },
    ),
    404: json_detail_example(
        "Topic not found",
        "Topic not found",
    ),
    422: _TOPIC_TITLE_TOO_SHORT_422,
}

TEACHER_TOPIC_DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Delete denied",
        {
            "not_teacher": "Teacher privileges required",
            "not_instructor": "Course instructor required",
        },
    ),
}

TEACHER_COURSE_TOPIC_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "List denied",
        {
            "not_teacher": "Teacher privileges required",
            "not_instructor": "Course instructor required",
        },
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
}

STUDENT_COURSE_TOPIC_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "List denied",
        {
            "not_student": "Student privileges required",
            "not_member": "Course membership required",
        },
    ),
    404: json_detail_example(
        "Course not found",
        "Course not found",
    ),
}

STUDENT_TOPIC_EXPLANATION_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_examples(
        "Read denied",
        {
            "not_student": "Student privileges required",
            "not_member": "Course membership required",
        },
    ),
    404: json_detail_example(
        "Topic not found",
        "Topic not found",
    ),
}
