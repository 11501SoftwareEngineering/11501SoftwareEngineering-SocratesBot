"""Integration: the migration seeds the catalog teachers and TAs can read."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException

from app.core.database import AsyncSessionLocal, engine
from app.core.enums import TaPermission, UserRole
from app.core.migration import run_migrations
from app.crud import course as course_crud
from app.crud import user as user_crud
from app.schemas.course import TaAssignRequest
from app.schemas.inquiry import InquiryModelResponse
from app.services import courses as courses_service
from app.services import inquiry as inquiry_service

EXPECTED = [
    ("openai/gpt-6.2-sol", "GPT-6.2 Sol", 2, 10),
    ("openai/gpt-6.1-sol", "GPT-6.1 Sol", 2, 10),
    ("openai/gpt-6.1-terra", "GPT-6.1 Terra", 1, 5),
    ("openai/gpt-6-luna", "GPT-6 Luna", 0.1, 0.5),
    ("openai/gpt-6.2-sol-pro", "GPT-6.2 Sol Pro", 2, 10),
    ("openai/gpt-6.1-sol-pro", "GPT-6.1 Sol Pro", 2, 10),
    ("openai/gpt-6.1-terra-pro", "GPT-6.1 Terra Pro", 1, 5),
    ("openai/gpt-6-luna-pro", "GPT-6 Luna Pro", 0.1, 0.5),
]
LUNA = (
    "GPT-6 Luna is the fast, cost-efficient model in OpenAI's GPT-6 series, "
    "positioned below GPT-6 Sol. It is suited for high-volume and latency-sensitive "
    "workloads such as chat, classification, and lightweight agentic tasks, and at "
    "higher reasoning effort it can take on complex software engineering and "
    "computer-use tasks that previously called for a Sol-tier model. It shares the "
    "GPT-6 family's gains in factual reliability and its clearer, more concise "
    "communication style."
)
LUNA_PRO = (
    "GPT-6 Luna Pro is the same underlying model as GPT-6 Luna, served with "
    "reasoning.mode set to pro for higher-quality responses on complex tasks. Pro "
    "mode spends far more reasoning tokens per request, so a typical request costs "
    "several times more than the same request on GPT-6 Luna and takes much longer "
    "to complete. It is intended for hard, high-stakes problems where the extra "
    "accuracy justifies the cost. For everyday coding, agentic, and chat "
    "workloads, use GPT-6 Luna instead."
)


def _json(models) -> list[dict]:
    return [
        InquiryModelResponse.model_validate(m).model_dump(mode="json") for m in models
    ]


@pytest.mark.integration
def test_teacher_and_ta_read_seeded_catalog_and_student_is_denied() -> None:
    async def _run() -> None:
        await engine.dispose()
        await run_migrations()

        suffix = uuid.uuid4().hex[:10]
        async with AsyncSessionLocal() as db:
            teacher = await user_crud.create_user(
                db,
                account_id=f"im-t-{suffix}",
                name="Teacher",
                password="password1",
                role=UserRole.TEACHER,
            )
            ta = await user_crud.create_user(
                db,
                account_id=f"im-ta-{suffix}",
                name="TA",
                password="password1",
                role=UserRole.USER,
            )
            student = await user_crud.create_user(
                db,
                account_id=f"im-s-{suffix}",
                name="Student",
                password="password1",
                role=UserRole.USER,
            )
            course = await course_crud.create_course_with_instructor(
                db,
                name="Models",
                description=None,
                created_by=teacher.id,
                invitation_code=f"M{suffix[:7]}".upper(),
            )
            course_id = uuid.UUID(str(course.id))
            for user_id in (ta.id, student.id):
                await course_crud.add_student_membership(
                    db, course_id=course_id, user_id=user_id
                )
            await db.commit()
            await courses_service.assign_course_ta(
                db,
                teacher,
                course_id,
                TaAssignRequest(
                    account_id=ta.account_id,
                    permissions=[TaPermission.VIEW_MEMBERS],
                ),
            )

            teacher_view = _json(await inquiry_service.list_inquiry_models(db, teacher))
            assert len(teacher_view) == 1
            assert teacher_view[0]["model_id"] == "gemini-3.1-flash-lite"
            assert teacher_view[0]["provider_id"] == "google"
            assert teacher_view[0]["input_price_usd"] == 0.25
            assert teacher_view[0]["output_price_usd"] == 1.50

            assert _json(await inquiry_service.list_inquiry_models(db, ta)) == (
                teacher_view
            )

            with pytest.raises(HTTPException) as denied:
                await inquiry_service.list_inquiry_models(db, student)
            assert denied.value.status_code == 403

        await engine.dispose()

    asyncio.run(_run())
