"""Personal-report decisions. The stored body has no student name."""

from __future__ import annotations

from app.core.enums import DialogueOutcome, GenerationStatus

_EVIDENCE = frozenset({"sufficient", "partial", "insufficient"})


def report_start(outcome: str, newest_status: str | None) -> str:
    """Return ``reject``, ``reuse``, or ``insert``."""
    if outcome != DialogueOutcome.COMPLETED.value:
        return "reject"
    if newest_status in {
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }:
        return "reuse"
    if newest_status == GenerationStatus.READY.value:
        return "reuse"
    return "insert"


def visible_report(
    attempts: list[tuple[str, dict | None]],
) -> tuple[str | None, dict | None]:
    """Newest status, plus the latest ready body while a later attempt is unfinished."""
    if not attempts:
        return None, None
    ready = [
        body
        for status, body in attempts
        if status == GenerationStatus.READY.value and body
    ]
    return attempts[-1][0], ready[-1] if ready else None


def validate_report(payload: dict) -> dict:
    """Return the stored report body, or raise ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("invalid report")
    summary = payload.get("viewpoint_summary")
    final = payload.get("final_viewpoint")
    viewpoint_status = payload.get("viewpoint_status")
    evidence = payload.get("evidence_status")
    if not all(
        isinstance(item, str) and item.strip()
        for item in (summary, final, viewpoint_status)
    ):
        raise ValueError("invalid report")
    if evidence not in _EVIDENCE:
        raise ValueError("invalid report")
    challenges = payload.get("challenges")
    timeline = payload.get("timeline")
    return {
        "viewpoint_summary": summary.strip(),
        "final_viewpoint": final.strip(),
        "viewpoint_status": viewpoint_status.strip(),
        "reasons": _strings(payload.get("reasons")),
        "strongest_reason": _text(payload.get("strongest_reason")),
        "challenges": challenges if isinstance(challenges, list) else [],
        "revision_or_defense": _text(payload.get("revision_or_defense")),
        "focus_connection": _text(payload.get("focus_connection")),
        "other_perspectives": _text(payload.get("other_perspectives")),
        "open_questions": _strings(payload.get("open_questions")),
        "evidence_status": evidence,
        "limitations": _text(payload.get("limitations")),
        "timeline": timeline if isinstance(timeline, list) else [],
    }


def student_report(
    *,
    status: str,
    body: dict | None,
    report_id: str | None,
    session_id: str,
    topic_id: str,
    completed_turns: int,
) -> dict:
    """Shape one report attempt for the student read."""
    report = None
    if body is not None and report_id is not None:
        report = {
            "report_id": report_id,
            "version": 1,
            "session_id": session_id,
            "topic_id": topic_id,
            "completed_turns": completed_turns,
            "completion_reason": "completed",
            **body,
        }
    return {"report_status": status, "report": report}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
