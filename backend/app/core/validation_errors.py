"""Sanitize request-validation payloads so secrets are not echoed."""

from __future__ import annotations

from typing import Any

_SENSITIVE_FIELDS = frozenset({"password", "old_password", "new_password"})


def sanitize_validation_errors(errors: list[Any]) -> list[dict[str, Any]]:
    """Keep field names in ``loc``; drop password ``input`` values."""
    sanitized: list[dict[str, Any]] = []
    for raw in errors:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        loc = item.get("loc", ())
        loc_parts = list(loc) if isinstance(loc, (list, tuple)) else [loc]
        if any(
            isinstance(part, str) and part in _SENSITIVE_FIELDS for part in loc_parts
        ):
            item.pop("input", None)
        sanitized.append(item)
    return sanitized
