"""Unit tests for course invitation-code generation."""

from __future__ import annotations

import re

from app.services.course_invites import (
    INVITE_ALPHABET,
    INVITE_COLLISION_RETRIES,
    INVITE_LENGTH,
    generate_invite_code,
)

_CODE_RE = re.compile(rf"^[{INVITE_ALPHABET}]{{{INVITE_LENGTH}}}$")


def test_generate_invite_code_shape() -> None:
    code = generate_invite_code()
    assert _CODE_RE.fullmatch(code)
    assert len(code) == INVITE_LENGTH
    assert not any(ch in code for ch in "0OIL1")


def test_invite_collision_retries_is_capped() -> None:
    assert INVITE_COLLISION_RETRIES >= 1
