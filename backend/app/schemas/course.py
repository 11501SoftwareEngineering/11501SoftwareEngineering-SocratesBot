"""Pydantic schemas for course APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import CourseRole
from app.services.course_invites import INVITE_ALPHABET, INVITE_LENGTH

_EXAMPLE_COURSE_ID = UUID("11111111-1111-1111-1111-111111111111")
_EXAMPLE_USER_ID = UUID("22222222-2222-2222-2222-222222222222")
_EXAMPLE_INVITE = "ABCD2345"
_EXAMPLE_JOINED_AT = datetime.fromisoformat("2026-10-01T08:00:00+00:00")
_INVITE_PATTERN = rf"(?i)^[{INVITE_ALPHABET}]{{{INVITE_LENGTH}}}$"


class CourseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])


class CourseCreateResponse(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])
    invite_code: str = Field(examples=[_EXAMPLE_INVITE])
    my_role: CourseRole = Field(examples=[CourseRole.TEACHER])
    message: str = Field(default="Course created", examples=["Course created"])


class CourseUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])


class CourseUpdateResponse(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])
    invite_code: str = Field(examples=[_EXAMPLE_INVITE])
    message: str = Field(default="Course updated", examples=["Course updated"])


class CourseDetailResponse(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])
    teacher_name: str = Field(examples=["Teacher One"])
    my_role: CourseRole = Field(examples=[CourseRole.STUDENT])
    my_permissions: list[str] = Field(
        default_factory=list,
        description="TA permissions in this course; empty for other roles",
    )
    invite_code: str = Field(examples=[_EXAMPLE_INVITE])


class MessageResponse(BaseModel):
    message: str = Field(examples=["Student added"])


class CourseListItem(BaseModel):
    """One row of ``GET /courses`` (teacher, TA and student courses merged)."""

    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])
    teacher_name: str = Field(examples=["Teacher One"])
    topic_count: int = Field(examples=[2], description="Total topics in the course")
    my_role: CourseRole = Field(examples=[CourseRole.TEACHER])
    my_permissions: list[str] = Field(default_factory=list)
    invite_code: str = Field(examples=[_EXAMPLE_INVITE])
    # Only set for teachers (and TAs with ``view_members``); omitted otherwise.
    student_count: int | None = Field(
        default=None,
        examples=[12],
        description="Active STUDENT memberships; omitted unless allowed",
    )


class CourseJoinRequest(BaseModel):
    invite_code: str = Field(
        min_length=INVITE_LENGTH,
        max_length=INVITE_LENGTH,
        pattern=_INVITE_PATTERN,
        examples=[_EXAMPLE_INVITE],
    )


class CourseJoinResponse(BaseModel):
    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    invite_code: str = Field(examples=[_EXAMPLE_INVITE])
    my_role: CourseRole = Field(examples=[CourseRole.STUDENT])
    message: str = Field(default="Joined course", examples=["Joined course"])


class CourseStudentListItem(BaseModel):
    student_id: UUID = Field(examples=[_EXAMPLE_USER_ID])
    account_id: str = Field(examples=["alice"])
    name: str = Field(examples=["Alice"])
    joined_at: datetime = Field(examples=[_EXAMPLE_JOINED_AT])


class CourseStudentAddRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=64, examples=["alice"])
