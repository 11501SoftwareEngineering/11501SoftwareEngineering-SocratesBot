from app.services.summary_text import (
    leaked_identifier,
    public_summary,
    ready_effects,
    validate_summary,
)


def test_ready_summary_closes_only_open_dialogues() -> None:
    stage, closed = ready_effects(
        "conversation",
        ["open", "completed", "abandoned", "open"],
    )

    assert stage == "summary"
    assert closed == [0, 3]


def test_failed_summary_does_not_move_the_topic() -> None:
    # A failed attempt never calls ready_effects. Other stages stay put.
    stage, closed = ready_effects("setup", ["open"])

    assert stage == "setup"
    assert closed == [0]


def test_published_text_omits_identifiers_and_rejects_a_name() -> None:
    draft = validate_summary(
        {
            "overview": "The class compared two accounts.",
            "viewpoint_summary": "Most revised the first claim.",
            "denominator": 2,
            "groups": [
                {
                    "name": "revised",
                    "conditions": "changed the claim",
                    "count": 1,
                    "percentage": 50,
                    "members": ["r1"],
                }
            ],
            "ungrouped": ["r2"],
        },
        {"r1": "report-1", "r2": "report-2"},
    )
    public = public_summary(draft)

    assert "report_ids" not in str(public)
    assert public["ungrouped_count"] == 1
    assert (
        leaked_identifier(
            {**draft, "overview": "Ada changed her claim."},
            names=["Ada"],
            identifiers=["report-1"],
        )
        == "Ada"
    )
