"""Class-summary decisions. Published text stays apart from the draft."""

from __future__ import annotations


def ready_effects(stage: str, outcomes: list[str]) -> tuple[str, list[int]]:
    """Stage moves only when a summary is stored ready. Only open dialogues close."""
    closed = [index for index, outcome in enumerate(outcomes) if outcome == "open"]
    if stage == "conversation":
        return "summary", closed
    return stage, closed


def _invalid() -> ValueError:
    return ValueError("invalid summary")


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid()
    return value.strip()


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid()
    return value


def _number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _invalid()
    return value


def _group(group: object, labels: dict[str, str]) -> dict:
    if not isinstance(group, dict):
        raise _invalid()
    name = group.get("name")
    conditions = group.get("conditions")
    members = group.get("members")
    if not isinstance(name, str) or not isinstance(conditions, str):
        raise _invalid()
    if not isinstance(members, list):
        raise _invalid()
    return {
        "name": name,
        "conditions": conditions,
        "count": _integer(group.get("count")),
        "percentage": _number(group.get("percentage")),
        "report_ids": [_label(item, labels) for item in members],
    }


def validate_summary(payload: dict, labels: dict[str, str]) -> dict:
    """Return the stored summary body, or raise ValueError."""
    if not isinstance(payload, dict):
        raise _invalid()
    overview = _text(payload.get("overview"))
    viewpoint = _text(payload.get("viewpoint_summary"))
    denominator = _integer(payload.get("denominator"))
    groups = payload.get("groups")
    ungrouped = payload.get("ungrouped")
    if not isinstance(groups, list) or not isinstance(ungrouped, list):
        raise _invalid()
    return {
        "overview": overview,
        "viewpoint_summary": viewpoint,
        "denominator": denominator,
        "groups": [_group(group, labels) for group in groups],
        "ungrouped_report_ids": [_label(item, labels) for item in ungrouped],
    }


def public_summary(draft: dict) -> dict:
    """Return the published shape, without report ids inside groups."""
    groups = draft["groups"]
    ungrouped = draft["ungrouped_report_ids"]
    denominator = draft["denominator"] or 0
    ungrouped_count = len(ungrouped)
    return {
        "overview": draft["overview"],
        "viewpoint_summary": draft["viewpoint_summary"],
        "groups": [
            {
                "name": group["name"],
                "conditions": group["conditions"],
                "count": group["count"],
                "percentage": group["percentage"],
            }
            for group in groups
        ],
        "ungrouped_count": ungrouped_count,
        "ungrouped_percentage": (100 * ungrouped_count / denominator)
        if denominator
        else 0,
        "denominator": denominator,
    }


def leaked_identifier(
    draft: dict,
    *,
    names: list[str],
    identifiers: list[str],
) -> str | None:
    """Return the first student name or identifier found in the summary text."""
    blob = f"{draft['overview']}\n{draft['viewpoint_summary']}"
    for name in names:
        if name and name in blob:
            return name
    for identifier in identifiers:
        if identifier and identifier in blob:
            return identifier
    return None


def _label(item: object, labels: dict[str, str]) -> str:
    if not isinstance(item, str) or item not in labels:
        raise ValueError("invalid summary")
    return labels[item]
