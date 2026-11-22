"""Mechanical checks on a teacher's course description, before any model call.

These checks refuse only obvious non-topics: too short, too long, keyboard mash,
repeated filler, or text without letters. Meaning is left to the model, so an
unusual claim or a topic about prompt injection is still allowed.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

TOPIC_MIN = 20
TOPIC_MAX = 6000

TopicIssue = Literal["too_short", "too_long", "unreadable"]

_REPEATED_BLOCK = re.compile(r"^(.{1,10})\1{3,}$")
_KEYBOARD_RUN = re.compile(
    r"^(?:qwerty(?:uiop)?|asdf(?:ghjkl)?|zxcv(?:bnm)?|qazwsx(?:edc)?|wasd)+$"
)


def _compact(text: str) -> str:
    """Lowercase NFKC text without whitespace, punctuation, or symbols."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(
        char
        for char in normalized
        if not char.isspace() and unicodedata.category(char)[0] not in {"P", "S"}
    )


def topic_issue(value: str) -> TopicIssue | None:
    """Return why the description cannot form a course, or None if it may proceed."""
    text = value.strip()
    if len(text) < TOPIC_MIN:
        return "too_short"
    if len(text) > TOPIC_MAX:
        return "too_long"
    compact = _compact(text)
    letters = [char for char in compact if char.isalpha()]
    if not letters:
        return "unreadable"
    if _REPEATED_BLOCK.match(compact) or _KEYBOARD_RUN.match(compact):
        return "unreadable"
    counts: dict[str, int] = {}
    for char in letters:
        counts[char] = counts.get(char, 0) + 1
    if (
        len(letters) >= 12
        and len(counts) <= 3
        and max(counts.values()) / len(letters) >= 0.7
    ):
        return "unreadable"
    return None


def topic_issue_message(issue: TopicIssue, count: int) -> str:
    if issue == "too_short":
        return (
            f"Enter at least {TOPIC_MIN} characters ({count} entered). "
            "Describe the topic or question students should discuss."
        )
    if issue == "too_long":
        return f"Keep the description within {TOPIC_MAX} characters."
    return (
        "Describe a recognizable topic. Repeated characters, keyboard sequences, "
        "or only numbers and symbols cannot form a course setup."
    )
