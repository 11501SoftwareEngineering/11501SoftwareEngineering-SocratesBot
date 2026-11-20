from app.services.dialogue_progress import empty_progress, validate_progress


def _milestone(met: bool, evidence: int | None) -> dict:
    return {"met": met, "evidenceExchange": evidence, "summary": "s"}


def test_readiness_needs_three_exchanges_and_ordered_evidence() -> None:
    progress = empty_progress()
    progress["position"] = _milestone(True, 1)
    progress["reason"] = _milestone(True, 1)
    progress["examination"] = _milestone(True, 2)
    progress["response"] = _milestone(True, 3)

    assert validate_progress(progress, 3).structurally_ready is True
    assert validate_progress(progress, 2).structurally_ready is False

    progress["response"] = _milestone(True, 2)  # response must follow examination
    assert validate_progress(progress, 3).structurally_ready is False
