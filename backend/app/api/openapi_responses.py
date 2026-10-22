"""Reusable OpenAPI ``responses=`` fragments for FastAPI routes."""

from __future__ import annotations

from typing import Any

from app.api.student_audio_errors import (
    STT_AUDIO_TOO_LARGE_DETAIL,
    STT_CONNECTION_FAILED_DETAIL,
    STT_INVALID_GROQ_KEY_DETAIL,
    STT_INVALID_LANGUAGE_DETAIL,
    STT_INVALID_OR_CORRUPT_AUDIO_DETAIL,
    STT_MISSING_GROQ_KEY_DETAIL,
    STT_PROVIDER_FAILED_DETAIL,
    STT_TIMEOUT_DETAIL,
)
from app.core.auth_policies import (
    AUTH_UNAUTHORIZED_DETAIL,
    CURRENT_PASSWORD_INCORRECT_DETAIL,
    NEW_PASSWORD_SAME_AS_CURRENT_DETAIL,
)

_PASSWORD_CHANGE_REQUIRED_DETAIL = "Password change required"


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

TRANSCRIBE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: json_detail_examples(
        "Transcription rejected (client/input)",
        {
            "missing_groq_api_key": STT_MISSING_GROQ_KEY_DETAIL,
            "invalid_groq_api_key": STT_INVALID_GROQ_KEY_DETAIL,
            "invalid_or_corrupt_audio": STT_INVALID_OR_CORRUPT_AUDIO_DETAIL,
            "invalid_language": STT_INVALID_LANGUAGE_DETAIL,
        },
    ),
    401: json_detail_example(
        AUTH_UNAUTHORIZED_DETAIL,
        AUTH_UNAUTHORIZED_DETAIL,
    ),
    403: json_detail_example(
        "Password change required",
        _PASSWORD_CHANGE_REQUIRED_DETAIL,
    ),
    413: json_detail_example(
        "Audio exceeds size limit",
        STT_AUDIO_TOO_LARGE_DETAIL,
    ),
    422: json_detail_example(
        "Request validation failed",
        [
            {
                "type": "missing",
                "loc": ["body", "file"],
                "msg": "Field required",
            }
        ],
    ),
    502: json_detail_example(
        "Upstream STT provider error",
        STT_PROVIDER_FAILED_DETAIL,
    ),
    504: json_detail_examples(
        "STT provider timeout or connection failure",
        {
            "timeout": STT_TIMEOUT_DETAIL,
            "connection_failed": STT_CONNECTION_FAILED_DETAIL,
        },
    ),
}
