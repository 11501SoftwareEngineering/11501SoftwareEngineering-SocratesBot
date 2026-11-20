"""Pydantic schemas for course APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool

from app.core.enums import CourseRole, TaPermission
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


class CourseListItem(BaseModel):
    """One row of ``GET /courses`` (teacher, TA and student courses merged)."""

    course_id: UUID = Field(examples=[_EXAMPLE_COURSE_ID])
    name: str = Field(examples=["Software Engineering"])
    description: str | None = Field(default=None, examples=["Fall 2026"])
    teacher_name: str = Field(examples=["Teacher One"])
    topic_count: int = Field(examples=[2], description="Total topics in the course")
    my_role: CourseRole = Field(examples=[CourseRole.TEACHER])
    invite_code: str = Field(examples=[_EXAMPLE_INVITE])
    student_count: int | None = Field(
        default=None,
        examples=[12],
        description="Active STUDENT memberships; teachers and TAs only",
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


class CourseMemberListItem(BaseModel):
    user_id: UUID = Field(examples=[_EXAMPLE_USER_ID])
    account_id: str = Field(examples=["alice"])
    name: str = Field(examples=["Alice"])
    role: CourseRole = Field(examples=[CourseRole.STUDENT])
    joined_at: datetime = Field(examples=[_EXAMPLE_JOINED_AT])


_EXAMPLE_TA_PERMISSIONS = [TaPermission.EDIT_TOPICS, TaPermission.VIEW_MEMBERS]


class TaAssignRequest(BaseModel):
    """A new TA always gets every permission."""

    account_id: str = Field(min_length=1, max_length=64, examples=["alice"])
    check: StrictBool = Field(
        default=False,
        examples=[False],
        description="true: only run the checks and return the account, no write",
    )


class TaAssignResponse(BaseModel):
    user_id: UUID = Field(examples=[_EXAMPLE_USER_ID])
    account_id: str = Field(examples=["alice"])
    name: str = Field(examples=["Alice"])
    message: str = Field(
        default="TA assigned",
        examples=["TA assigned"],
        description='"TA can be assigned" when check is true',
    )


class TaPermissionsUpdateRequest(BaseModel):
    permissions: list[TaPermission] = Field(
        examples=[_EXAMPLE_TA_PERMISSIONS],
        description="Replaces all current permissions; duplicates are ignored",
    )


class TaPermissionsUpdateResponse(BaseModel):
    user_id: UUID = Field(examples=[_EXAMPLE_USER_ID])
    permissions: list[TaPermission] = Field(examples=[_EXAMPLE_TA_PERMISSIONS])
    message: str = Field(
        default="TA permissions updated", examples=["TA permissions updated"]
    )
