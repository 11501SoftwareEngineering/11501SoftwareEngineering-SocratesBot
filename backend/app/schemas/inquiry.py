"""Inquiry setup schemas. The model id is not part of this contract."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import AgeBand, GenerationStatus
from app.core.locales import SUPPORTED_LOCALES

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


class InquiryAttemptState(BaseModel):
    attempt_id: UUID
    status: GenerationStatus
    body: InquiryFields | None = None


class InquirySetupResponse(BaseModel):
    topic_id: UUID
    course_id: UUID
    version: int
    topic_status: str
    content_language: str | None = None
    setup: InquiryFields
    attempt: InquiryAttemptState | None = None
    message: str | None = None


class SaveInquiryRequest(BaseModel):
    expected_version: int = Field(ge=1)
    content_language: str | None = None
    setup: InquiryFields

    @field_validator("content_language")
    @classmethod
    def language_must_be_supported(cls, value: str | None) -> str | None:
        cleaned = _clean(value)
        if cleaned is None:
            return None
        if cleaned not in SUPPORTED_LOCALES:
            raise ValueError("invalid language")
        return cleaned

    @model_validator(mode="after")
    def limits_are_legal(self) -> Self:
        band = self.setup.age_band
        turns = self.setup.max_turns
        if band is not None and band not in _AGE_BANDS:
            raise ValueError("invalid age band")
        if turns is not None and turns not in _TURN_CAPS:
            raise ValueError("invalid max turns")
        return self


class PublishInquiryRequest(BaseModel):
    expected_version: int = Field(ge=1)


class GenerateInquiryRequest(BaseModel):
    age_band: AgeBandValue | None = None
    max_turns: TurnCap | None = None
    content_language: str | None = None
    course_description: str | None = Field(default=None, max_length=_TEXT)

    @field_validator("content_language")
    @classmethod
    def language_must_be_supported(cls, value: str | None) -> str | None:
        return SaveInquiryRequest.language_must_be_supported(value)

    @field_validator("course_description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _clean(value)


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


class InquiryGenerationResponse(BaseModel):
    attempt_id: UUID
    status: GenerationStatus


class GeneratedInquiry(BaseModel):
    """Strict model output. Empty exclusions mean the teacher set no limit."""

    model_config = ConfigDict(extra="forbid")

    age_band: AgeBandValue
    max_turns: TurnCap
    topic: str
    core_question: str
    inquiry_focus: str
    background_info: str
    exclusions: str
    opening_message: str

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


def fields_from_mapping(payload: dict) -> InquiryFields:
    return InquiryFields(
        age_band=payload.get("age_band"),
        max_turns=payload.get("max_turns"),
        topic=payload.get("topic"),
        core_question=payload.get("core_question"),
        inquiry_focus=payload.get("inquiry_focus"),
        background_info=payload.get("background_info"),
        exclusions=payload.get("exclusions"),
        opening_message=payload.get("opening_message"),
    )


INCOMPLETE_FIELDS = ("age_band", "max_turns", "topic", "core_question")


def first_incomplete_field(
    *,
    age_band: str | None,
    max_turns: int | None,
    topic: str | None,
    core_question: str | None,
) -> str | None:
    if age_band not in {band.value for band in AgeBand}:
        return "age_band"
    if max_turns not in _TURN_CAPS:
        return "max_turns"
    if topic is None or not topic.strip():
        return "topic"
    if core_question is None or not core_question.strip():
        return "core_question"
    return None
