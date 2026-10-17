"""Unit tests for validation-error sanitization."""

from app.core.validation_errors import sanitize_validation_errors


def test_sanitize_strips_password_input_keeps_loc() -> None:
    errors = [
        {
            "type": "string_too_short",
            "loc": ["body", "new_password"],
            "msg": "String should have at least 8 characters",
            "input": "short",
        },
        {
            "type": "missing",
            "loc": ["body", "account"],
            "msg": "Field required",
            "input": None,
        },
    ]
    out = sanitize_validation_errors(errors)
    assert out[0]["loc"] == ["body", "new_password"]
    assert "input" not in out[0]
    assert out[1]["loc"] == ["body", "account"]
    assert out[1]["input"] is None
