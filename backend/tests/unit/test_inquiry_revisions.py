"""Inquiry revisions are stored only when the eight fields change."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.crud import topic as topic_crud
from app.crud.topic import inquiry_snapshot, next_revision_version
from app.models.inquiry_revision import InquiryRevision
from app.models.topic import Topic

SAME = {"topic": "Cities", "core_question": "Why?"}
OTHER = {"topic": "Rivers", "core_question": "Why?"}


def test_first_change_is_version_one() -> None:
    assert next_revision_version(None, None, SAME) == 1


def test_unchanged_fields_do_not_allocate_a_version() -> None:
    assert next_revision_version(SAME, 1, dict(SAME)) is None


def test_changed_fields_allocate_the_next_version() -> None:
    assert next_revision_version(SAME, 1, OTHER) == 2


def test_generated_unchanged_inquiry_still_records_prompt_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        topic = Topic(
            id=uuid4(),
            course_id=uuid4(),
            created_by=uuid4(),
            title="Cities",
            inquiry_topic="Cities",
            core_question="Why?",
        )
        snapshot = inquiry_snapshot(topic)
        monkeypatch.setattr(
            topic_crud,
            "_latest_revision",
            AsyncMock(return_value=SimpleNamespace(version=3, body=snapshot)),
        )
        db = AsyncMock()

        await topic_crud.record_inquiry_change(
            db,
            topic,
            prompt_stage="inquiry_design",
            prompt_version="v1",
            force=True,
        )

        revision = db.add.call_args.args[0]
        assert isinstance(revision, InquiryRevision)
        assert revision.version == 4
        assert revision.body == snapshot
        assert revision.generation_meta == {
            "prompt_stage": "inquiry_design",
            "prompt_version": "v1",
        }
        db.flush.assert_awaited_once()

    asyncio.run(run())
