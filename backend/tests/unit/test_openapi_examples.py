"""OpenAPI examples for report responses."""

from app.main import app
from app.schemas.report import StudentReportResponse, TeachingReportsResponse


def test_report_examples_are_concrete() -> None:
    """Swagger shows a real 200 body instead of an empty additional property."""
    schemas = app.openapi()["components"]["schemas"]
    for name, field in (
        ("StudentReportResponse", "report_status"),
        ("TeachingReportsResponse", "class_size"),
    ):
        example = schemas[name]["example"]
        assert field in example
        assert "additionalProp1" not in example


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
