"""Personal-report decisions. The stored body has no student name."""

from __future__ import annotations

from app.core.enums import DialogueOutcome, GenerationStatus
from app.schemas.report import ReportProjection


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


def validate_report(payload: dict, *, source: dict | None = None) -> dict:
    """Validate new output; source checks bind citations to owned student messages."""
    body = ReportProjection.model_validate(payload).model_dump(exclude_none=True)
    if source is not None:
        exchanges = {row["turn"]: row for row in source["exchanges"]}
        seen = set()
        for item in body["timeline"]:
            row = exchanges.get(item["turn"])
            reference = item.get("evidence_reference")
            if row is None or reference is None or item["turn"] in seen:
                raise ValueError("Invalid report citation")
            expected = {key: row[key] for key in ("message_id", "turn", "quote")}
            if (
                reference != expected
                or item["evidence"] != row["quote"]
                or item["question"] != row["question"]
            ):
                raise ValueError("Report citation does not match the source")
            seen.add(item["turn"])
    return body


def student_report(
    *,
    status: str,
    body: dict | None,
    report_id: str | None,
    session_id: str,
    topic_id: str,
    completed_turns: int,
    completed_at: str | None = None,
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
            **({"completed_at": completed_at} if completed_at else {}),
            **body,
        }
    return {"report_status": status, "report": report}
