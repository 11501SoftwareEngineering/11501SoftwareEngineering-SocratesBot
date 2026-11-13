from app.services.report_text import (
    report_start,
    student_report,
    validate_report,
    visible_report,
)


def test_uncompleted_dialogue_has_no_report() -> None:
    assert report_start("open", None) == "reject"
    assert report_start("abandoned", None) == "reject"


def test_failed_retry_keeps_the_ready_body() -> None:
    status, body = visible_report(
        [("ready", {"viewpoint_summary": "kept"}), ("failed", None)]
    )

    assert status == "failed"
    assert body == {"viewpoint_summary": "kept"}
    assert report_start("completed", "failed") == "insert"


def test_student_report_has_no_display_name() -> None:
    payload = student_report(
        status="ready",
        body={"viewpoint_summary": "a point"},
        report_id="report-1",
        session_id="session-1",
        topic_id="topic-1",
        completed_turns=2,
    )

    assert "student_display_name" not in payload
    assert "student_display_name" not in payload["report"]


def test_stored_report_drops_a_name() -> None:
    body = validate_report(
        {
            "viewpoint_summary": "compared two accounts",
            "final_viewpoint": "the second is narrower",
            "viewpoint_status": "revised",
            "evidence_status": "partial",
            "student_display_name": "Ada",
        }
    )

    assert "Ada" not in str(body.values())
    assert "student_display_name" not in body
