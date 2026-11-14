"""Class-summary decisions. Published text stays apart from the draft."""

from __future__ import annotations


def ready_effects(stage: str, outcomes: list[str]) -> tuple[str, list[int]]:
    """Stage moves only when a summary is stored ready. Only open dialogues close."""
    closed = [index for index, outcome in enumerate(outcomes) if outcome == "open"]
    if stage == "conversation":
        return "summary", closed
    return stage, closed


def validate_summary(payload: dict, labels: dict[str, str]) -> dict:
    """Return the stored summary body, or raise ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("invalid summary")
    overview = payload.get("overview")
    viewpoint = payload.get("viewpoint_summary")
    denominator = payload.get("denominator")
    groups = payload.get("groups")
    ungrouped = payload.get("ungrouped")
    if not isinstance(overview, str) or not overview.strip():
        raise ValueError("invalid summary")
    if not isinstance(viewpoint, str) or not viewpoint.strip():
        raise ValueError("invalid summary")
    if not isinstance(denominator, int) or isinstance(denominator, bool):
        raise ValueError("invalid summary")
    if not isinstance(groups, list) or not isinstance(ungrouped, list):
        raise ValueError("invalid summary")
    mapped_groups = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("invalid summary")
        name = group.get("name")
        conditions = group.get("conditions")
        count = group.get("count")
        percentage = group.get("percentage")
        members = group.get("members")
        if not isinstance(name, str) or not isinstance(conditions, str):
            raise ValueError("invalid summary")
        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError("invalid summary")
        if not isinstance(percentage, int | float) or isinstance(percentage, bool):
            raise ValueError("invalid summary")
        if not isinstance(members, list):
            raise ValueError("invalid summary")
        mapped_groups.append(
            {
                "name": name,
                "conditions": conditions,
                "count": count,
                "percentage": percentage,
                "report_ids": [_label(item, labels) for item in members],
            }
        )
    return {
        "overview": overview.strip(),
        "viewpoint_summary": viewpoint.strip(),
        "denominator": denominator,
        "groups": mapped_groups,
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
