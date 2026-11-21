"""Response shapes for a personal report and the teaching list."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import GenerationStatus

_STATUS = "pending | processing | ready | failed"
_EVIDENCE = "sufficient | partial | insufficient"

_REPORT = {
    "report_id": "44444444-4444-4444-4444-444444444444",
    "version": 1,
    "session_id": "33333333-3333-3333-3333-333333333333",
    "topic_id": "22222222-2222-2222-2222-222222222222",
    "completed_turns": 4,
    "completion_reason": "completed",
    "viewpoint_summary": "The student narrowed the claim to classroom use.",
    "final_viewpoint": "AI should assist, not replace, teachers.",
    "viewpoint_status": "revised",
    "reasons": ["Students still need a person to ask why."],
    "strongest_reason": "A teacher can follow up on a wrong step.",
    "challenges": [
        {"challenge": "What if the teacher is unavailable?", "responded": True}
    ],
    "revision_or_defense": "Limited the claim to class discussion.",
    "focus_connection": "The inquiry asked who should decide.",
    "other_perspectives": "Some students wanted full automation.",
    "open_questions": ["Who checks the AI's questions?"],
    "evidence_status": "partial",
    "limitations": "Only one class discussion was reviewed.",
    "timeline": [
        {
            "turn": 2,
            "question": "Who is responsible for the answer?",
            "evidence": "The student named the teacher.",
            "viewpoint_before": "AI can replace grading.",
            "viewpoint_after": "AI can draft, the teacher decides.",
            "change_type": "narrowed",
            "attribution": "explicit",
        }
    ],
}


class ReportEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message_id: str
    turn: int = Field(ge=1)
    quote: str


class ReportTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    turn: int = Field(ge=1)
    question: str
    evidence: str
    viewpoint_before: str
    viewpoint_after: str
    change_type: str
    attribution: Literal["explicit", "sequence_only", "none"]
    evidence_reference: ReportEvidence | None = None


class ReportChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    challenge: str
    responded: bool


class ReportProjection(BaseModel):
    """Newly generated body. Legacy stored bodies retain their read compatibility."""

    model_config = ConfigDict(extra="ignore", strict=True)
    viewpoint_summary: str
    final_viewpoint: str
    viewpoint_status: str
    evidence_status: Literal["sufficient", "partial", "insufficient"]
    reasons: list[str] = Field(default_factory=list)
    strongest_reason: str = ""
    challenges: list[ReportChallenge] = Field(default_factory=list)
    revision_or_defense: str = ""
    focus_connection: str = ""
    other_perspectives: str = ""
    open_questions: list[str] = Field(default_factory=list)
    limitations: str = ""
    timeline: list[ReportTimelineItem] = Field(default_factory=list)


class ReportBody(BaseModel):
    """A ready report. Fields stay unset until that attempt is stored."""

    model_config = ConfigDict(extra="allow")

    report_id: str | None = None
    version: int | None = None
    session_id: str | None = None
    topic_id: str | None = None
    completed_turns: int | None = None
    completion_reason: str | None = None
    completed_at: str | None = None
    viewpoint_summary: str | None = None
    final_viewpoint: str | None = None
    viewpoint_status: str | None = None
    reasons: list[str] | None = None
    strongest_reason: str | None = None
    challenges: list[Any] | None = None
    revision_or_defense: str | None = None
    focus_connection: str | None = None
    other_perspectives: str | None = None
    open_questions: list[str] | None = None
    evidence_status: str | None = Field(default=None, description=_EVIDENCE)
    limitations: str | None = None
    timeline: list[ReportTimelineItem | Any] | None = Field(
        default=None,
        description="New reports contain validated student-message evidence references. Unvalidated legacy stored items remain readable.",
    )


class StudentReportResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"report_status": "ready", "report": _REPORT}}
    )

    report_status: GenerationStatus = Field(description=_STATUS)
    report: ReportBody | None = None


class TeachingReportItem(StudentReportResponse):
    student_display_name: str


class TeachingReportsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "class_size": 28,
                "completed_count": 20,
                "ready_count": 18,
                "processing_count": 1,
                "failed_count": 1,
                "reports": [
                    {
                        "report_status": "ready",
                        "report": _REPORT,
                        "student_display_name": "Ada",
                    }
                ],
            }
        }
    )

    class_size: int
    completed_count: int
    ready_count: int
    processing_count: int
    failed_count: int
    reports: list[TeachingReportItem]
