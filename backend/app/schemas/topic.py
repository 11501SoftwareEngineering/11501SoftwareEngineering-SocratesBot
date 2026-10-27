"""Pydantic schemas for teacher/student topic APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

_EXAMPLE_COURSE_ID = UUID("11111111-1111-1111-1111-111111111111")
_EXAMPLE_TOPIC_ID = UUID("33333333-3333-3333-3333-333333333333")
_EXAMPLE_TITLE = "Should AI replace teachers?"
_EXAMPLE_DESCRIPTION = "Discuss the role of AI in education"


class TopicCreateRequest(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
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


class TeacherTopicListItem(BaseModel):
    topic_id: UUID = Field(examples=[_EXAMPLE_TOPIC_ID])
    title: str = Field(examples=[_EXAMPLE_TITLE])
    description: str | None = Field(default=None, examples=[_EXAMPLE_DESCRIPTION])
    # Students whose session for this topic is COMPLETED.
    answered_count: int = Field(examples=[12])


class TeacherCourseTopicsResponse(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    invite_code: str = Field(examples=["ABCD2345"])
    topics: list[TeacherTopicListItem]
