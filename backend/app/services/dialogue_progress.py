"""Dialogue progress and structural readiness for Stage 2.

The model proposes progress each turn; the server decides readiness. A dialogue
is ready only when it has at least three student exchanges, all four milestones
are met with evidence from the dialogue so far, and the response milestone
follows the examination milestone. The model's own "ready" is advisory only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MILESTONES = ("position", "reason", "examination", "response")
MIN_READY_EXCHANGE = 3
MAX_EXCHANGE = 15


def _empty_milestone() -> dict[str, Any]:
    return {"met": False, "evidenceExchange": None, "summary": ""}


def empty_progress() -> dict[str, Any]:
    return {
        "position": _empty_milestone(),
        "reason": _empty_milestone(),
        "examination": _empty_milestone(),
        "response": _empty_milestone(),
        "currentPosition": "",
        "reasonedUncertainty": "",
        "definitions": [],
        "reasons": [],
        "assumptions": [],
        "alternatives": [],
        "counterexamples": [],
        "revisionsOrDefences": [],
        "unresolvedQuestions": [],
        "focalTensionConnection": "",
        "dialogueMovement": "",
        "stalledTurns": 0,
    }


@dataclass(frozen=True)
class ProgressCheck:
    structurally_ready: bool
    issues: list[str]


def validate_progress(progress: dict[str, Any], current_exchange: int) -> ProgressCheck:
    issues: list[str] = []
    for name in MILESTONES:
        milestone = progress[name]
        evidence = milestone["evidenceExchange"]
        if milestone["met"] and (
            type(evidence) is not int or not 1 <= evidence <= current_exchange
        ):
            issues.append(f"{name} has no valid student-exchange evidence.")
        if not milestone["met"] and evidence is not None:
            issues.append(f"{name} is unmet but still cites evidence.")
    for name in (
        "definitions",
        "reasons",
        "assumptions",
        "alternatives",
        "counterexamples",
        "revisionsOrDefences",
    ):
        for item in progress.get(name, []):
            refs = item.get("evidenceExchanges", [])
            if any(
                type(ref) is not int or not 1 <= ref <= current_exchange for ref in refs
            ):
                issues.append(f"{name} cites an invalid student exchange.")
    response = progress["response"]
    examination = progress["examination"]
    if (
        response["met"]
        and examination["met"]
        and (response["evidenceExchange"] or 0)
        <= (examination["evidenceExchange"] or 0)
    ):
        issues.append("The response milestone must follow the examination milestone.")
    all_met = all(progress[name]["met"] for name in MILESTONES)
    ready = current_exchange >= MIN_READY_EXCHANGE and all_met and not issues
    return ProgressCheck(structurally_ready=ready, issues=issues)


def reset_milestones(progress: dict[str, Any]) -> dict[str, Any]:
    """Return progress with every milestone unmet, keeping the evidence lists."""
    return {
        **progress,
        **{name: _empty_milestone() for name in MILESTONES},
    }
