from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SuperAdminUser, get_db
from app.schemas.admin import (
    TeacherCreateRequest,
    TeacherCreateResponse,
    TeacherDeleteResponse,
    TeacherListItem,
)
from app.services import admin_teachers as admin_teachers_service

router = APIRouter(prefix="/admin/teachers", tags=["admin-teachers"])


@router.get("", response_model=list[TeacherListItem])
async def list_teachers(
    _admin: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TeacherListItem]:
    """List all teacher accounts (config-elevated admin only)."""
    return await admin_teachers_service.list_teachers(db)


@router.post("", response_model=TeacherCreateResponse)
async def create_teacher(
    payload: TeacherCreateRequest,
    _admin: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeacherCreateResponse:
    """Create a teacher with ``must_change_password=true``."""
    return await admin_teachers_service.create_teacher(db, payload)


@router.delete("/{teacherId}", response_model=TeacherDeleteResponse)
async def delete_teacher(
    teacherId: UUID,
    _admin: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeacherDeleteResponse:
    """Delete a teacher by user UUID."""
    return await admin_teachers_service.delete_teacher(db, teacherId)
