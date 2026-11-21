"""Native lab Stage3 conversion/finalization; no database or lifecycle policy.

Ported from Socrates-AI-Testing/lib/lab/central.ts. Internal report IDs never
enter model material. Counts include unclassified reports in the denominator.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inquiry import INQUIRY_TEXT_LIMIT
from app.services.dialogue_progress import empty_progress, validate_progress
from app.services.dialogue_turn import ProgressOut
from app.services.report_adapter import NativeSummary, source_digest

MAX_REPORTS = 50
MAX_PAYLOAD_BYTES = 180_000
MILESTONES = ("position", "reason", "examination", "response")
Text = Annotated[str, Field(max_length=1800)]
Items = Annotated[list[Annotated[str, Field(max_length=1000)]], Field(max_length=10)]
ReportItems = Annotated[list[Text], Field(max_length=10)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CentralReport(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    topicKey: str
    theme: str = Field(max_length=INQUIRY_TEXT_LIMIT)
    inquiryQuestion: str = Field(max_length=INQUIRY_TEXT_LIMIT)
    inquiryFocus: str = Field(max_length=INQUIRY_TEXT_LIMIT)
    outcome: Literal["complete", "partial", "interrupted", "inconclusive"]
    position: Text
    reasonedUncertainty: Text
    reasons: ReportItems
    assumptions: ReportItems
    alternatives: ReportItems
    challenge: Text
    revisionOrDefence: Text
    remainingQuestions: ReportItems
    milestones: dict[str, bool]
    evidenceExchanges: list[Annotated[int, Field(ge=1, le=15)]] = Field(max_length=15)


class CentralGroup(StrictModel):
    label: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=1600)
    reportIds: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        min_length=1, max_length=MAX_REPORTS
    )
    commonReasons: Items
    values: Items
    assumptions: Items
    internalDifferences: Items


class CentralOutput(StrictModel):
    overview: str = Field(max_length=3000)
    groups: list[CentralGroup] = Field(max_length=12)
    discussionQuestions: list[Annotated[str, Field(max_length=600)]] = Field(
        max_length=5
    )
    limitations: list[Annotated[str, Field(max_length=800)]] = Field(max_length=10)


OUTPUT_SCHEMA = CentralOutput.model_json_schema()


def inquiry_key(brief: dict) -> str:
    """Canonical settings fingerprint, not authorization or equal-title matching."""
    values = []
    for key in (
        "learnerBand",
        "targetExchanges",
        "theme",
        "inquiryQuestion",
        "inquiryFocus",
        "necessaryContext",
        "exclusions",
        "openingMessage",
    ):
        value = brief[key]
        if isinstance(value, str):
            value = " ".join(unicodedata.normalize("NFKC", value).split())
        values.append(value)
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))[:10]


def from_native(report_id: str, metadata: dict) -> CentralReport:
    """Use only matching immutable native evidence; never mutable dialogue state."""
    source = metadata["report_source"]
    if source_digest(source) != metadata.get("source_digest"):
        raise ValueError("Report source fingerprint mismatch")
    summary = NativeSummary.model_validate(metadata["native_summary"])
    material = source["material"]
    brief = material["approvedInquiryBrief"]
    exchanges = {
        row["exchange"] for row in material["transcript"] if row["role"] == "user"
    }
    if not exchanges or exchanges != set(range(1, len(exchanges) + 1)):
        raise ValueError("Missing or invalid student exchanges")
    progress = ProgressOut.model_validate(
        material["finalProgress"] or empty_progress()
    ).model_dump(by_alias=True)
    if validate_progress(progress, len(exchanges)).issues:
        raise ValueError("Invalid source progress")
    evidenced = {
        key: bool(
            progress[key]["met"] and progress[key]["evidenceExchange"] in exchanges
        )
        for key in MILESTONES
    }
    references = {
        progress[key]["evidenceExchange"] for key in MILESTONES if evidenced[key]
    }

    def listed(key):
        rows = progress[key]
        for row in rows:
            references.update(
                ref for ref in row["evidenceExchanges"] if ref in exchanges
            )
        return [
            row["text"]
            for row in rows
            if any(ref in exchanges for ref in row["evidenceExchanges"])
        ][:10]

    reasons = listed("reasons")
    assumptions, alternatives = listed("assumptions"), listed("alternatives")
    listed("counterexamples")
    listed("revisionsOrDefences")
    return CentralReport(
        id=report_id,
        topicKey=inquiry_key(brief),
        theme=brief["theme"],
        inquiryQuestion=brief["inquiryQuestion"],
        inquiryFocus=brief["inquiryFocus"],
        outcome=summary.outcome,
        position=(
            summary.workingPosition
            or progress["currentPosition"]
            or progress["position"]["summary"]
        )
        if evidenced["position"]
        else "",
        reasonedUncertainty=progress["reasonedUncertainty"],
        reasons=_unique(
            [summary.strongestReason or progress["reason"]["summary"], *reasons]
        )
        if evidenced["reason"]
        else [],
        assumptions=assumptions,
        alternatives=alternatives,
        challenge=(summary.challengeExamined or progress["examination"]["summary"])
        if evidenced["examination"]
        else "",
        revisionOrDefence=(summary.revisionOrDefence or progress["response"]["summary"])
        if evidenced["response"]
        else "",
        remainingQuestions=_unique(
            [summary.remainingQuestion, *progress["unresolvedQuestions"]]
        ),
        milestones=evidenced,
        evidenceExchanges=sorted(references),
    )


def classifiable(report: CentralReport) -> bool:
    return bool(
        report.outcome not in {"interrupted", "inconclusive"}
        and report.milestones["position"]
        and report.milestones["reason"]
        and report.position.strip()
        and any(reason.strip() for reason in report.reasons)
        and report.evidenceExchanges
    )


def validate_reports(values: list[dict]) -> list[CentralReport]:
    if not 1 <= len(values) <= MAX_REPORTS:
        raise ValueError("Stage3 requires 1-50 reports")
    reports = [CentralReport.model_validate(value) for value in values]
    if len({report.id for report in reports}) != len(reports):
        raise ValueError("Duplicate report IDs")
    if (
        len({(r.topicKey, r.theme, r.inquiryQuestion, r.inquiryFocus) for r in reports})
        != 1
    ):
        raise ValueError("Mismatched inquiry sources")
    if any(set(r.milestones) != set(MILESTONES) for r in reports):
        raise ValueError("Invalid milestone keys")
    return reports


def model_material(reports: list[CentralReport], language: str) -> dict:
    return {
        "interfaceLanguage": language,
        "inquiry": {
            "theme": reports[0].theme,
            "question": reports[0].inquiryQuestion,
            "focus": reports[0].inquiryFocus,
        },
        "reports": [
            {
                "reportId": f"report_{index}",
                **report.model_dump(
                    exclude={
                        "id",
                        "topicKey",
                        "theme",
                        "inquiryQuestion",
                        "inquiryFocus",
                        "milestones",
                        "evidenceExchanges",
                    }
                ),
            }
            for index, report in enumerate(reports, 1)
            if classifiable(report)
        ],
    }


def no_evidence_output(language: str) -> dict:
    english = language == "en"
    return {
        "overview": "Not enough evidence to establish viewpoint groups."
        if english
        else "目前沒有足夠的立場與理由證據可以建立觀點群組。",
        "groups": [],
        "discussionQuestions": [],
        "limitations": [
            "No supported position-and-reason grouping is available; this is not an assessment of ability."
            if english
            else "沒有足夠證據建立立場與理由群組;這不代表能力不足。"
        ],
    }


def percentage(count: int, total: int) -> float:
    return math.floor(count / total * 1000 + 0.5) / 10


def finalize(raw: dict, reports: list[CentralReport], language: str) -> dict:
    """Private rich result plus existing DTO projection; no model arithmetic."""
    reports = validate_reports([r.model_dump() for r in reports])
    output = CentralOutput.model_validate(raw)
    prose = [output.overview, *output.discussionQuestions, *output.limitations]
    for group in output.groups:
        prose.extend(
            [
                group.label,
                group.description,
                *group.commonReasons,
                *group.values,
                *group.assumptions,
                *group.internalDifferences,
            ]
        )
    if any(
        re.search(r"\breport_\d+\b", text) or any(r.id in text for r in reports)
        for text in prose
    ):
        raise ValueError("Report identifier leaked into synthesis prose")

    labels = {f"report_{i}": report for i, report in enumerate(reports, 1)}
    seen, groups, public_groups = set(), [], []
    for index, group in enumerate(output.groups, 1):
        members = []
        if not group.label.strip():
            raise ValueError("Blank group label")
        for label in group.reportIds:
            if label not in labels or not classifiable(labels[label]) or label in seen:
                raise ValueError("Unknown, duplicate or ineligible membership")
            seen.add(label)
            members.append(labels[label].id)
        count = len(members)
        groups.append(
            {
                **group.model_dump(),
                "reportIds": members,
                "id": f"group_{index}",
                "kind": "viewpoint",
                "count": count,
                "percentage": percentage(count, len(reports)),
            }
        )
        public_groups.append(
            {
                "name": group.label,
                "conditions": group.description,
                "report_ids": members,
                "count": count,
                "percentage": percentage(count, len(reports)),
            }
        )
    unassigned = [r.id for label, r in labels.items() if label not in seen]
    limitations = list(output.limitations)
    if any(classifiable(r) and label not in seen for label, r in labels.items()):
        limitations.append(
            "Some classifiable reports remain ungrouped; teacher review is required."
            if language == "en"
            else "部分可分類報告尚未分組,請教師檢查。"
        )
    if unassigned:
        groups.append(
            {
                "id": "still_exploring",
                "kind": "still_exploring",
                "label": "Still exploring" if language == "en" else "尚在探索",
                "description": "Insufficient evidence, interruption, or unassigned grouping."
                if language == "en"
                else "證據不足、對話中斷或尚未形成可靠分組。",
                "reportIds": unassigned,
                "commonReasons": [],
                "values": [],
                "assumptions": [],
                "internalDifferences": [],
                "count": len(unassigned),
                "percentage": percentage(len(unassigned), len(reports)),
            }
        )
    native = {
        "schema_version": "native-central-v1",
        "method": "central_llm",
        "reviewStatus": "needs_teacher_review",
        "theme": reports[0].theme,
        "inquiryQuestion": reports[0].inquiryQuestion,
        "topicKey": reports[0].topicKey,
        "totalReports": len(reports),
        "eligibleReports": sum(classifiable(r) for r in reports),
        "completedReports": sum(r.outcome == "complete" for r in reports),
        "inProgressReports": 0,
        "overview": output.overview,
        "groups": groups,
        "milestones": {
            key: sum(r.milestones[key] for r in reports) for key in MILESTONES
        },
        "discussionQuestions": output.discussionQuestions,
        "limitations": limitations,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    # Existing editable text fields carry useful native details without new DTOs.
    details = []
    for group in output.groups:
        details.append(group.label + ": " + group.description)
        details.extend(
            group.commonReasons
            + group.values
            + group.assumptions
            + group.internalDifferences
        )
    details.extend(output.discussionQuestions)
    details.extend(limitations)
    return {
        "overview": output.overview,
        "viewpoint_summary": "\n".join(details) or output.overview,
        "denominator": len(reports),
        "groups": public_groups,
        "ungrouped_report_ids": unassigned,
        "native_synthesis": native,
    }
