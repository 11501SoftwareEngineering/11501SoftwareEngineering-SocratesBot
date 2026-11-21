"""Personal report and teaching-report routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, get_db
from app.api.openapi_responses import (
    REPORT_READ_RESPONSES,
    REPORT_START_RESPONSES,
    TEACHING_REPORT_READ_RESPONSES,
    TEACHING_REPORT_RETRY_RESPONSES,
)
from app.schemas.report import StudentReportResponse, TeachingReportsResponse
from app.services import reports as report_service

router = APIRouter(tags=["reports"])


@router.get(
    "/sessions/{sessionId}/report",
    response_model_exclude_unset=True,
    responses=REPORT_READ_RESPONSES,
)
async def read_student_report(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentReportResponse:
    """Poll the owner's report-eligible dialogue report; never starts generation.

    Before any attempt exists this returns 404. report_status describes the latest
    attempt; report can retain an older ready body during a later failed retry.
    """
    return await report_service.read_student_report(
        db, user_id=current_user.id, session_id=sessionId
    )


@router.post(
    "/sessions/{sessionId}/report",
    response_model_exclude_unset=True,
    responses=REPORT_START_RESPONSES,
)
async def start_student_report(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentReportResponse:
    """Start or reuse a report for an outcome=completed or ended dialogue.

    Reuse ready or unexpired pending/processing attempts. Insert and schedule an
    attempt when none exists, the newest failed, or its running lease expired.
    Returns 200 with report_status; poll GET on this path. Does not force a new
    report when a ready attempt already exists.
    """
    return await report_service.start_student_report(
        db, user_id=current_user.id, session_id=sessionId
    )


@router.get(
    "/topics/{topicId}/reports",
    response_model_exclude_unset=True,
    responses=TEACHING_REPORT_READ_RESPONSES,
)
async def read_teaching_reports(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeachingReportsResponse:
    """Return this topic's per-student reports for an instructor."""
    return await report_service.read_teaching_reports(
        db, teacher=teacher, topic_id=topicId
    )


@router.post(
    "/topics/{topicId}/reports/{sessionId}",
    response_model_exclude_unset=True,
    responses=TEACHING_REPORT_RETRY_RESPONSES,
)
async def retry_teaching_report(
    topicId: UUID,
    sessionId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentReportResponse:
    """Retry or reuse a completed dialogue report under the same rules as student POST.

    This does not force regeneration of a ready report. A new progress snapshot
    is taken only when a new attempt is inserted.
    """
    return await report_service.start_teacher_retry(
        db, teacher=teacher, topic_id=topicId, session_id=sessionId
    )
