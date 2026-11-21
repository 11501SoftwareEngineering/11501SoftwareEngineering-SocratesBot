"""Native Stage3 parity and adversarial membership/evidence cases."""

from copy import deepcopy
from uuid import uuid4

import pytest

from app.services.central_synthesis import (
    classifiable,
    finalize,
    from_native,
    inquiry_key,
    model_material,
    no_evidence_output,
    validate_reports,
)
from app.services.dialogue_progress import empty_progress
from app.services.report_adapter import source_digest
from tests.unit.test_report_adapter import source, summary


def metadata(eligible=True, outcome="partial"):
    snapshot = source()
    progress = empty_progress()
    if eligible:
        for key in ("position", "reason"):
            progress[key] = {
                "met": True,
                "evidenceExchange": 1,
                "summary": "Needs differ",
            }
        progress["currentPosition"] = "Uncertain about equal shares"
        progress["reasonedUncertainty"] = "Different needs may justify different shares"
    snapshot["material"]["finalProgress"] = progress
    native = {**summary(), "outcome": outcome}
    return {
        "report_source": snapshot,
        "source_digest": source_digest(snapshot),
        "native_summary": native,
    }


def report(eligible=True, outcome="partial"):
    return from_native(str(uuid4()), metadata(eligible, outcome))


def output(ids=None):
    return {
        "overview": "Students compared need and equality.",
        "groups": []
        if ids is None
        else [
            {
                "label": "Needs matter",
                "description": "Equal shares may not meet unequal needs.",
                "reportIds": ids,
                "commonReasons": ["Needs differ"],
                "values": [],
                "assumptions": [],
                "internalDifferences": [],
            }
        ],
        "discussionQuestions": ["What makes a need relevant?"],
        "limitations": [],
    }


@pytest.mark.parametrize(
    "outcome,eligible",
    [
        ("complete", True),
        ("partial", True),
        ("interrupted", False),
        ("inconclusive", False),
    ],
)
def test_native_eligibility_preserves_partial_uncertainty(outcome, eligible):
    row = report(outcome=outcome)
    assert classifiable(row) is eligible
    assert row.reasonedUncertainty


def test_model_input_excludes_identity_and_raw_evidence():
    rows = [report(), report(False)]
    material = model_material(rows, "en")
    assert [r["reportId"] for r in material["reports"]] == ["report_1"]
    assert rows[0].id not in str(material) and rows[1].id not in str(material)
    assert "transcript" not in str(material) and "source_digest" not in str(material)
    assert material["interfaceLanguage"] == "en"


@pytest.mark.parametrize("ids", [["unknown"], ["report_1", "report_1"], ["report_2"]])
def test_reject_unknown_duplicate_and_ineligible_members(ids):
    with pytest.raises(ValueError):
        finalize(output(ids), [report(), report(False)], "en")


def test_reject_duplicate_across_groups_and_model_arithmetic():
    raw = output(["report_1"])
    raw["groups"].append(deepcopy(raw["groups"][0]))
    with pytest.raises(ValueError):
        finalize(raw, [report()], "en")
    raw = output(["report_1"])
    raw["groups"][0]["count"] = 9000
    with pytest.raises(ValueError):
        finalize(raw, [report()], "en")


def test_backend_counts_all_reports_and_retains_native_details():
    rows = [report(), report(False), report()]
    result = finalize(output(["report_1"]), rows, "en")
    assert result["denominator"] == 3
    assert result["groups"][0]["count"] == 1
    assert result["groups"][0]["percentage"] == 33.3
    assert result["ungrouped_report_ids"] == [r.id for r in rows[1:]]
    native = result["native_synthesis"]
    assert native["groups"][-1]["count"] == 2
    assert native["eligibleReports"] == 2
    assert native["discussionQuestions"] and native["limitations"]


def test_all_inconclusive_yields_honest_result():
    result = finalize(no_evidence_output("en"), [report(False, "inconclusive")], "en")
    assert result["groups"] == []
    assert result["native_synthesis"]["eligibleReports"] == 0
    assert result["native_synthesis"]["groups"][0]["kind"] == "still_exploring"


@pytest.mark.parametrize("failure", ["digest", "future", "missing", "no_turns"])
def test_invalid_frozen_source_rejected(failure):
    value = metadata()
    if failure == "digest":
        value["source_digest"] = "bad"
    elif failure == "missing":
        del value["native_summary"]
    else:
        if failure == "future":
            value["report_source"]["material"]["finalProgress"]["position"][
                "evidenceExchange"
            ] = 9
        else:
            value["report_source"]["material"]["transcript"] = []
        value["source_digest"] = source_digest(value["report_source"])
    with pytest.raises((ValueError, KeyError)):
        from_native("report", value)


def test_mixed_inquiry_duplicate_and_size_rejected():
    first, second = report().model_dump(), report().model_dump()
    second["topicKey"] = "different"
    for rows in ([], [first, first], [first, second], [first] * 51):
        with pytest.raises(ValueError):
            validate_reports(rows)


def test_inquiry_fingerprint_ignores_spacing_but_not_settings():
    brief = source()["material"]["approvedInquiryBrief"]
    assert inquiry_key(brief) == inquiry_key(
        {**brief, "theme": "  " + brief["theme"] + "  "}
    )
    assert inquiry_key(brief) != inquiry_key({**brief, "targetExchanges": 15})
