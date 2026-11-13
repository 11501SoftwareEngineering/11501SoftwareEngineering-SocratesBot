from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, get_db
from app.services import reports as report_service

router = APIRouter(tags=["reports"])


@router.get("/sessions/{sessionId}/report")
async def read_student_report(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await report_service.read_student_report(
        db, user_id=current_user.id, session_id=sessionId
    )


@router.post("/sessions/{sessionId}/report")
async def start_student_report(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await report_service.start_student_report(
        db, user_id=current_user.id, session_id=sessionId
    )


@router.get("/topics/{topicId}/reports")
async def read_teaching_reports(
    topicId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await report_service.read_teaching_reports(
        db, teacher=teacher, topic_id=topicId
    )


@router.post("/topics/{topicId}/reports/{sessionId}")
async def retry_teaching_report(
    topicId: UUID,
    sessionId: UUID,
    teacher: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await report_service.start_teacher_retry(
        db, teacher=teacher, topic_id=topicId, session_id=sessionId
    )
