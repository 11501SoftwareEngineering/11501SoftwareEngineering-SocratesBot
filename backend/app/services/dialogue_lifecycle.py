"""Shared ending/report policy, independent of model judgments."""

MIN_FINISH_TURNS = 3
REPORT_OUTCOMES = frozenset({"completed", "ended"})


def lifecycle_fields(session, turns: int) -> dict:
    return {
        "report_eligible": session.outcome in REPORT_OUTCOMES,
        "ending_reason": getattr(session, "ending_reason", None),
        "can_finish_early": session.outcome == "open" and turns >= MIN_FINISH_TURNS,
    }
