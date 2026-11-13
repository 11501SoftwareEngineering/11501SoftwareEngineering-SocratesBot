"""Pydantic schemas for teacher/student topic APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import CourseRole, SessionStatus

_EXAMPLE_COURSE_ID = UUID("11111111-1111-1111-1111-111111111111")
_EXAMPLE_TOPIC_ID = UUID("33333333-3333-3333-3333-333333333333")
_EXAMPLE_SESSION_ID = UUID("44444444-4444-4444-4444-444444444444")
_EXAMPLE_TITLE = "Should AI replace teachers?"
_EXAMPLE_DESCRIPTION = "Discuss the role of AI in education"


class TopicCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255, examples=[_EXAMPLE_TITLE])
    description: str | None = Field(default=None, examples=[_EXAMPLE_DESCRIPTION])


class TopicUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255, examples=[_EXAMPLE_TITLE])
    description: str | None = Field(default=None, examples=[_EXAMPLE_DESCRIPTION])


class TopicWriteResponse(BaseModel):
    topic_id: UUID = Field(examples=[_EXAMPLE_TOPIC_ID])
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    title: str = Field(examples=[_EXAMPLE_TITLE])
    description: str | None = Field(default=None, examples=[_EXAMPLE_DESCRIPTION])
    message: str = Field(examples=["Topic created"])


class TopicListItem(BaseModel):
    """Topic row; which optional fields appear depends on the caller's role.

    Students get ``session_status`` / ``session_id`` (null until they enter);
    teachers and TAs get ``answered_count`` / ``student_count``. Unused fields
    are omitted from the response (``response_model_exclude_unset``).
    """

    topic_id: UUID = Field(examples=[_EXAMPLE_TOPIC_ID])
    title: str = Field(examples=[_EXAMPLE_TITLE])
    description: str | None = Field(default=None, examples=[_EXAMPLE_DESCRIPTION])
    session_status: SessionStatus | None = Field(
        default=None,
        examples=[SessionStatus.IN_PROGRESS],
        description="Student only; null until the student enters the topic",
    )
    session_id: UUID | None = Field(
        default=None,
        examples=[_EXAMPLE_SESSION_ID],
        description="Student only; null until the student enters the topic",
    )
    answered_count: int | None = Field(
        default=None,
        examples=[12],
        description="Teacher/TA only; students with a COMPLETED session",
    )
    student_count: int | None = Field(
        default=None,
        examples=[30],
        description="Teacher/TA only; active students in the course",
    )


class CourseTopicsResponse(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    invite_code: str = Field(examples=["ABCD2345"])
    my_role: CourseRole = Field(examples=[CourseRole.STUDENT])
    my_permissions: list[str] = Field(default_factory=list)
    topics: list[TopicListItem]


class TopicExplanationResponse(BaseModel):
    topic_id: UUID = Field(examples=[_EXAMPLE_TOPIC_ID])
    title: str = Field(examples=[_EXAMPLE_TITLE])
    background: str | None = Field(default=None, examples=[_EXAMPLE_DESCRIPTION])
    key_terms: list[str] = Field(default_factory=list, examples=[[]])
