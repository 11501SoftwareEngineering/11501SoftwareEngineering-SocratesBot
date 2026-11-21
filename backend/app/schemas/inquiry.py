"""Inquiry setup schemas."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import AgeBand

AgeBandValue = Literal["13-15", "16-18", "university_plus"]
TurnCap = Literal[5, 10, 15]
_TEXT = 8000
_AGE_BANDS = {band.value for band in AgeBand}
_TURN_CAPS = {5, 10, 15}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class InquiryModelResponse(BaseModel):
    """One catalog model. Prices are USD per million tokens."""

    model_config = ConfigDict(from_attributes=True)

    model_id: str
    name: str
    description: str
    provider_id: str
    input_price_usd: float
    output_price_usd: float


class InquiryFields(BaseModel):
    """Saved or displayed fields. Illegal stored values stay readable."""

    age_band: str | None = None
    max_turns: int | None = None
    topic: str | None = Field(default=None, max_length=_TEXT)
    core_question: str | None = Field(default=None, max_length=_TEXT)
    inquiry_focus: str | None = Field(default=None, max_length=_TEXT)
    background_info: str | None = Field(default=None, max_length=_TEXT)
    exclusions: str | None = Field(default="unspecified", max_length=_TEXT)
    opening_message: str | None = Field(default=None, max_length=_TEXT)

    @field_validator(
        "topic",
        "core_question",
        "inquiry_focus",
        "background_info",
        "opening_message",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return _clean(value)
        return value

    @field_validator("exclusions", mode="before")
    @classmethod
    def unspecified_when_blank(cls, value: object) -> object:
        if not isinstance(value, str):
            return "unspecified"
        cleaned = value.strip()
        return cleaned or "unspecified"


def _required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("blank")
    return cleaned


def _legal_limits(setup: InquiryFields) -> None:
    band = setup.age_band
    turns = setup.max_turns
    if band is not None and band not in _AGE_BANDS:
        raise ValueError("invalid age band")
    if turns is not None and turns not in _TURN_CAPS:
        raise ValueError("invalid max turns")


AssessedField = Literal[
    "theme",
    "inquiryQuestion",
    "inquiryFocus",
    "necessaryContext",
    "exclusions",
    "openingMessage",
]


class FieldAssessment(BaseModel):
    """The model's check of one generated field. Shown to the teacher, never stored."""

    model_config = ConfigDict(extra="forbid")

    field: AssessedField
    status: Literal["sufficient", "missing", "ambiguous", "conflicted"]
    note: str = Field(max_length=800)


class InquiryFeedback(BaseModel):
    """Stage 1 feedback for the teacher. Nothing here is stored."""

    assessments: list[FieldAssessment] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InquirySetupResponse(BaseModel):
    topic_id: UUID
    course_id: UUID
    topic_status: str
    model_id: str | None = None
    setup: InquiryFields
    assessments: list[FieldAssessment] | None = None
    clarification_questions: list[str] | None = None
    suggestions: list[str] | None = None
    warnings: list[str] | None = None


class InquirySetupWriteResponse(InquirySetupResponse):
    message: str


class CreatedInquiryResponse(InquirySetupResponse):
    """A new setup topic. Warnings tell the teacher what still needs confirming."""

    warnings: list[str] = Field(default_factory=list)


class SaveInquiryRequest(BaseModel):
    setup: InquiryFields

    @model_validator(mode="after")
    def limits_are_legal(self) -> Self:
        _legal_limits(self.setup)
        return self


class CreateInquiryTopicRequest(BaseModel):
    age_band: AgeBandValue
    max_turns: TurnCap
    course_description: str = Field(min_length=1, max_length=6000)

    @field_validator("course_description")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _required_text(value)


class GenerateInquiryRequest(BaseModel):
    age_band: AgeBandValue
    max_turns: TurnCap
    content_language: str = Field(min_length=1, max_length=16)
    course_description: str = Field(min_length=1, max_length=6000)
    model_id: str = Field(min_length=1)

    @field_validator("content_language", "course_description", "model_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _required_text(value)


class RefineInquiryRequest(BaseModel):
    setup: InquiryFields
    feedback: str = Field(min_length=1, max_length=_TEXT)

    @field_validator("feedback")
    @classmethod
    def strip_feedback(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("feedback is blank")
        return cleaned

    @model_validator(mode="after")
    def limits_are_legal(self) -> Self:
        _legal_limits(self.setup)
        return self


class OpeningMessageRequest(BaseModel):
    setup: InquiryFields

    @model_validator(mode="after")
    def limits_are_legal(self) -> Self:
        _legal_limits(self.setup)
        return self


class OpeningMessageResponse(BaseModel):
    opening_message: str


class OpeningMessageDraft(BaseModel):
    """Model reply for an opening message. A blank echoed topic is ignored."""

    model_config = ConfigDict(extra="ignore")

    opening_message: str = Field(default="", max_length=_TEXT)

    @field_validator("opening_message")
    @classmethod
    def keep_model_text(cls, value: str) -> str:
        return value.strip()


class _DesignBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    learner_band: AgeBandValue = Field(alias="learnerBand")
    target_exchanges: TurnCap = Field(alias="targetExchanges")
    theme: str
    inquiry_question: str = Field(alias="inquiryQuestion")
    inquiry_focus: str = Field(alias="inquiryFocus")
    necessary_context: str = Field(alias="necessaryContext")
    exclusions: str
    opening_message: str = Field(alias="openingMessage")


class _Design(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    brief: _DesignBrief
    assessments: list[FieldAssessment]
    clarification_questions: list[str] = Field(alias="clarificationQuestions")
    suggestions: list[str]
    warnings: list[str]


class _InputCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["usable", "needs_revision"]
    message: str


class DesignOutput(BaseModel):
    """Stage 1 model output: the input check, then the design when the input is usable."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    input_check: _InputCheck = Field(alias="inputCheck")
    design: _Design | None


class GeneratedInquiry(BaseModel):
    """Strict model output. Empty exclusions mean the teacher set no limit."""

    model_config = ConfigDict(extra="forbid")

    age_band: AgeBandValue
    max_turns: TurnCap
    topic: str = Field(max_length=_TEXT)
    core_question: str = Field(max_length=_TEXT)
    inquiry_focus: str = Field(max_length=_TEXT)
    background_info: str = Field(max_length=_TEXT)
    exclusions: str = Field(max_length=_TEXT)
    opening_message: str = Field(max_length=_TEXT)

    @field_validator("topic", "core_question")
    @classmethod
    def required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("blank")
        return cleaned

    @field_validator("inquiry_focus", "background_info", "opening_message")
    @classmethod
    def keep_model_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("exclusions")
    @classmethod
    def unrestricted_is_unspecified(cls, value: str) -> str:
        cleaned = value.strip()
        return cleaned or "unspecified"


INCOMPLETE_FIELDS = ("age_band", "max_turns", "topic", "core_question")


def first_incomplete_field(
    *,
    age_band: str | None,
    max_turns: int | None,
    topic: str | None,
    core_question: str | None,
) -> str | None:
    """Return the first required setup field that is missing or illegal."""
    if age_band not in {band.value for band in AgeBand}:
        return "age_band"
    if max_turns not in _TURN_CAPS:
        return "max_turns"
    if topic is None or not topic.strip():
        return "topic"
    if core_question is None or not core_question.strip():
        return "core_question"
    return None
