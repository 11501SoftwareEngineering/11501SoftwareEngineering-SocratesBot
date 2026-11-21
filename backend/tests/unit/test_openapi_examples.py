"""OpenAPI examples for report and summary responses."""

from app.main import app
from app.schemas.report import StudentReportResponse, TeachingReportsResponse
from app.schemas.summary import (
    PublishedSummaryResponse,
    SummaryDraftResponse,
    SummaryStatusResponse,
    TeacherSummaryResponse,
)


def test_report_and_summary_examples_are_concrete() -> None:
    """Swagger shows a real 200 body instead of an empty additional property."""
    schemas = app.openapi()["components"]["schemas"]
    for name, field in (
        ("StudentReportResponse", "report_status"),
        ("TeachingReportsResponse", "class_size"),
        ("TeacherSummaryResponse", "topic_status"),
        ("SummaryDraftResponse", "summary"),
        ("ReviewSummaryResponse", "summary_status"),
        ("PublishSummaryResponse", "summary_status"),
        ("WithdrawSummaryResponse", "summary_status"),
        ("PublishedSummaryResponse", "summary"),
    ):
        example = schemas[name]["example"]
        assert field in example
        assert "additionalProp1" not in example
    assert schemas["PublishSummaryResponse"]["example"]["summary_status"] == "published"
    assert schemas["WithdrawSummaryResponse"]["example"] == {
        "summary_status": "withdrawn",
        "message": "Summary withdrawn",
    }


def test_partial_report_omits_fields_that_were_not_stored() -> None:
    """A ready body keeps only the keys it has, including a null report."""
    ready = StudentReportResponse.model_validate(
        {
            "report_status": "ready",
            "report": {
                "report_id": "44444444-4444-4444-4444-444444444444",
                "viewpoint_summary": "narrowed",
                "evidence_status": "partial",
            },
        }
    ).model_dump(mode="json", exclude_unset=True)
    assert ready["report"] == {
        "report_id": "44444444-4444-4444-4444-444444444444",
        "viewpoint_summary": "narrowed",
        "evidence_status": "partial",
    }

    pending = StudentReportResponse.model_validate(
        {"report_status": "pending", "report": None}
    ).model_dump(mode="json", exclude_unset=True)
    assert pending == {"report_status": "pending", "report": None}

    listed = TeachingReportsResponse.model_validate(
        {
            "class_size": 1,
            "completed_count": 1,
            "ready_count": 0,
            "processing_count": 1,
            "failed_count": 0,
            "reports": [{**pending, "student_display_name": "Ada"}],
        }
    ).model_dump(mode="json", exclude_unset=True)
    assert listed["reports"] == [{**pending, "student_display_name": "Ada"}]


def test_summary_null_stays_in_the_response() -> None:
    """A summary that has not been stored is returned as null."""
    started = TeacherSummaryResponse.model_validate(
        {
            "topic_status": "conversation",
            "published_version": None,
            "summary": None,
            "preparation_status": "pending",
        }
    ).model_dump(mode="json")
    assert started["summary"] is None
    assert started["published_version"] is None

    withdrawn = SummaryStatusResponse.model_validate(
        {"summary_status": "withdrawn", "message": "Summary withdrawn"}
    ).model_dump(mode="json", exclude_unset=True)
    assert withdrawn == {
        "summary_status": "withdrawn",
        "message": "Summary withdrawn",
    }

    published = PublishedSummaryResponse.model_validate({"summary": None}).model_dump(
        mode="json"
    )
    assert published == {"summary": None}

    edited = SummaryDraftResponse.model_validate(
        {
            "summary": {
                "summary_id": "55555555-5555-5555-5555-555555555555",
                "version": 1,
                "summary_status": "draft",
                "overview": "Compared two accounts.",
                "viewpoint_summary": "The teacher stays responsible.",
                "denominator": 2,
                "groups": [
                    {
                        "name": "Teacher stays",
                        "conditions": "A person checks the answer.",
                        "count": 2,
                        "percentage": 100,
                        "report_ids": ["44444444-4444-4444-4444-444444444444"],
                    }
                ],
                "ungrouped_report_ids": [],
            }
        }
    ).model_dump(mode="json")
    assert edited["summary"]["groups"][0]["percentage"] == 100
