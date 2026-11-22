"""Response shapes for the class summary draft and the published read."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_STAGE = "setup | conversation | summary"
_SUMMARY_STATUS = "draft | reviewed | published | withdrawn"
_PREPARATION = "pending | processing | ready | failed"

_GROUP = {
    "name": "Teacher stays in the loop",
    "conditions": "The student keeps a person responsible for the answer.",
    "count": 12,
    "percentage": 60,
    "report_ids": ["44444444-4444-4444-4444-444444444444"],
}
_DRAFT = {
    "summary_id": "55555555-5555-5555-5555-555555555555",
    "version": 1,
    "summary_status": "draft",
    "overview": "The class compared two accounts of who should decide.",
    "viewpoint_summary": "Most students kept the teacher responsible.",
    "denominator": 20,
    "groups": [_GROUP],
    "ungrouped_report_ids": ["66666666-6666-6666-6666-666666666666"],
}
_PUBLISHED = {
    "overview": _DRAFT["overview"],
    "viewpoint_summary": _DRAFT["viewpoint_summary"],
    "groups": [
        {
            "name": _GROUP["name"],
            "conditions": _GROUP["conditions"],
            "count": _GROUP["count"],
            "percentage": _GROUP["percentage"],
        }
    ],
    "ungrouped_count": 1,
    "ungrouped_percentage": 5,
    "denominator": 20,
}


class SummaryGroup(BaseModel):
    name: str
    conditions: str
    count: int
    percentage: int | float
    report_ids: list[str]


class ClassSummaryDraft(BaseModel):
    summary_id: str
    version: int
    summary_status: str = Field(description=_SUMMARY_STATUS)
    overview: str
    viewpoint_summary: str
    denominator: int
    groups: list[SummaryGroup]
    ungrouped_report_ids: list[str]


class PublicSummaryGroup(BaseModel):
    name: str
    conditions: str
    count: int
    percentage: int | float


class PublicSummary(BaseModel):
    overview: str
    viewpoint_summary: str
    groups: list[PublicSummaryGroup]
    ungrouped_count: int
    ungrouped_percentage: int | float
    denominator: int


class TeacherSummaryResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic_status": "summary",
                "published_version": 1,
                "summary": _DRAFT,
                "preparation_status": "ready",
            }
        }
    )

    topic_status: str = Field(description=_STAGE)
    published_version: int | None = None
    summary: ClassSummaryDraft | None = None
    preparation_status: str | None = Field(default=None, description=_PREPARATION)


class SummaryDraftResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"summary": _DRAFT}})

    summary: ClassSummaryDraft


class SummaryStatusResponse(BaseModel):
    version: int | None = None
    summary_status: str = Field(description=_SUMMARY_STATUS)
    message: str


class ReviewSummaryResponse(SummaryStatusResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": 1,
                "summary_status": "reviewed",
                "message": "Summary reviewed",
            }
        }
    )


class PublishSummaryResponse(SummaryStatusResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": 1,
                "summary_status": "published",
                "message": "Summary published",
            }
        }
    )


class WithdrawSummaryResponse(SummaryStatusResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "summary_status": "withdrawn",
                "message": "Summary withdrawn",
            }
        }
    )


class PublishedSummaryResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"summary": _PUBLISHED}})

    summary: PublicSummary | None = None


class EndConversationRequest(BaseModel):
    confirm_open_dialogues: bool = False


class ConversationStatusResponse(BaseModel):
    topic_id: UUID
    topic_status: str
    open_dialogue_count: int
    stage2_closed: bool
    confirmation_required: bool
    ended_dialogue_count: int = 0
    preparation_status: str | None = None
