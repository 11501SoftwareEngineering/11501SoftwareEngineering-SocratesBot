"""Class summary draft, publish, and the student read. A2 is not granted."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GenerationStatus, TopicStage
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import summary as summary_crud
from app.models.class_summary import ClassSummaryVersion
from app.models.topic import Topic
from app.models.user import User
from app.services import summary_runner
from app.services.summary_text import leaked_identifier, public_summary


def _request(bodies: list[tuple[str, dict]]) -> dict:
    labels = {
        f"r{index}": report_id
        for index, (report_id, _body) in enumerate(bodies, start=1)
    }
    material = [
        {"label": label, "report": body}
        for label, (_report_id, body) in zip(labels, bodies, strict=True)
    ]
    return {"labels": labels, "material": material}


def _attempt_running(latest) -> bool:
    if latest is None or latest.status not in {
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }:
        return False
    lease = latest.lease_expires_at
    return lease is not None and lease >= datetime.now(UTC)


async def _enqueue(
    db: AsyncSession, topic_id: UUID, bodies: list[tuple[str, dict]]
) -> None:
    await db.execute(select(Topic).where(Topic.id == topic_id).with_for_update())
    latest = await summary_crud.latest_attempt(db, topic_id)
    if _attempt_running(latest):
        return
    created = await summary_crud.insert_attempt(
        db, topic_id=topic_id, request_json=_request(bodies)
    )
    await db.commit()
    summary_runner.schedule(created.id)


def _started(topic: Topic, published_version: int | None) -> dict:
    return {
        "topic_status": topic.stage,
        "published_version": published_version,
        "summary": None,
        "preparation_status": GenerationStatus.PENDING.value,
    }


async def start_summary(db: AsyncSession, *, teacher: User, topic_id: UUID) -> dict:
    """Start a class summary from ready reports, unless one is already running.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if the caller does
            not instruct the course; 400 if the topic is still in setup or
            there are no ready reports.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    if topic.stage == TopicStage.SETUP.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Topic is still in setup"
        )
    bodies = await summary_crud.ready_report_bodies(db, topic.id)
    if not bodies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No ready reports"
        )
    await _enqueue(db, topic.id, bodies)
    return _started(topic, await summary_crud.published_version(db, topic.id))


async def read_teacher_summary(
    db: AsyncSession,
    *,
    teacher: User,
    topic_id: UUID,
    version: int | None = None,
) -> dict:
    """Return the instructor view of the latest summary, or one stored version.

    Raises:
        HTTPException: 404 if the topic or requested version is missing; 403
            if the caller does not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    if version is None:
        return await _teacher_body(db, topic)
    stored = await summary_crud.summary_version(db, topic.id, version)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )
    body = await _teacher_body(db, topic)
    body["summary"] = _draft(stored)
    return body


async def edit_summary(
    db: AsyncSession,
    *,
    teacher: User,
    topic_id: UUID,
    overview: str,
    viewpoint_summary: str,
) -> dict:
    """Replace the overview and viewpoint, and set the status back to draft.

    Raises:
        HTTPException: 404 if the topic or summary is missing; 403 if the
            caller does not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    current = await _current_summary(db, topic.id)
    row = await _write_text(
        db,
        current,
        overview=overview,
        viewpoint_summary=viewpoint_summary,
        summary_status="draft",
    )
    await db.commit()
    return {"summary": _draft(row)}


async def review_summary(
    db: AsyncSession,
    *,
    teacher: User,
    topic_id: UUID,
    overview: str,
    viewpoint_summary: str,
) -> dict:
    """Store the visible text when it changed, then mark that version reviewed.

    An earlier reviewed version is withdrawn. This review is left in place.

    Raises:
        HTTPException: 404 if the topic or summary is missing; 403 if the
            caller does not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    current = await _current_summary(db, topic.id)
    row = await _write_text(
        db,
        current,
        overview=overview,
        viewpoint_summary=viewpoint_summary,
        summary_status="reviewed",
    )
    await _withdraw_other_reviews(db, topic.id, keep=row.version)
    await db.commit()
    return {
        "version": row.version,
        "summary_status": "reviewed",
        "message": "Summary reviewed",
    }


async def publish_summary(db: AsyncSession, *, teacher: User, topic_id: UUID) -> dict:
    """Publish the latest summary when that version is reviewed.

    A newer version that is not reviewed blocks publishing an older review.

    Raises:
        HTTPException: 404 if the topic or summary is missing; 403 if the
            caller does not instruct the course; 400 if the latest version
            is not reviewed or the text contains a name or identifier.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    row = await _reviewed_summary(db, topic.id)
    draft = _draft_dict(row)
    names, identifiers = _identity_values(draft, await report_crud_names(db, topic.id))
    if leaked_identifier(draft, names=names, identifiers=identifiers):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Summary contains a name or identifier",
        )
    await summary_crud.upsert_summary_version(
        db,
        topic_id=row.topic_id,
        version=row.version,
        body={
            **draft,
            "published": public_summary(draft),
            "published_version": row.version,
            "status": "published",
        },
    )
    await db.commit()
    return {
        "version": row.version,
        "summary_status": "published",
        "message": "Summary published",
    }


async def withdraw_summary(db: AsyncSession, *, teacher: User, topic_id: UUID) -> dict:
    """Withdraw the published summary for this topic.

    Raises:
        HTTPException: 404 if the topic is missing or nothing is published;
            403 if the caller does not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    row = await summary_crud.latest_summary(db, topic.id)
    if row is None or not row.body.get("published"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No published summary"
        )
    await summary_crud.upsert_summary_version(
        db,
        topic_id=row.topic_id,
        version=row.version,
        body={
            **row.body,
            "published": None,
            "published_version": None,
            "status": "withdrawn",
        },
    )
    await db.commit()
    return {"summary_status": "withdrawn", "message": "Summary withdrawn"}


async def read_published(db: AsyncSession, *, user: User, topic_id: UUID) -> dict:
    """Return the published summary for a course member.

    Raises:
        HTTPException: 404 if the topic is missing or the caller is not a
            member of the course.
    """
    topic = await _visible_topic(db, user, topic_id)
    return {"summary": await summary_crud.published_document(db, topic.id)}


async def report_crud_names(db: AsyncSession, topic_id: UUID):
    """Return this topic's dialogues with each student's display name."""
    from app.crud import report as report_crud

    return await report_crud.topic_dialogues(db, topic_id)


async def _teacher_body(db: AsyncSession, topic: Topic) -> dict:
    latest = await summary_crud.latest_summary(db, topic.id)
    attempt = await summary_crud.latest_attempt(db, topic.id)
    summary = (
        _draft(latest)
        if latest is not None and topic.stage == TopicStage.SUMMARY.value
        else None
    )
    return {
        "topic_status": topic.stage,
        "published_version": await summary_crud.published_version(db, topic.id),
        "summary": summary,
        "preparation_status": None if attempt is None else attempt.status,
    }


def _draft(row: ClassSummaryVersion) -> dict:
    fields = _fields(row.body)
    return {
        "summary_id": str(row.id),
        "version": row.version,
        "summary_status": fields["status"],
        "overview": fields["overview"],
        "viewpoint_summary": fields["viewpoint_summary"],
        "denominator": fields["denominator"],
        "groups": fields["groups"],
        "ungrouped_report_ids": fields["ungrouped_report_ids"],
    }


async def _current_summary(db: AsyncSession, topic_id: UUID) -> ClassSummaryVersion:
    row = await summary_crud.latest_summary(db, topic_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )
    return row


async def _write_text(
    db: AsyncSession,
    row: ClassSummaryVersion,
    *,
    overview: str,
    viewpoint_summary: str,
    summary_status: str,
) -> ClassSummaryVersion:
    changed = (
        row.body.get("overview") != overview
        or row.body.get("viewpoint_summary") != viewpoint_summary
    )
    body = {
        **row.body,
        "overview": overview,
        "viewpoint_summary": viewpoint_summary,
        "status": summary_status,
    }
    return await summary_crud.upsert_summary_version(
        db,
        topic_id=row.topic_id,
        version=row.version + (1 if changed else 0),
        body=body,
    )


def _identity_values(draft: dict, pairs) -> tuple[list[str], list[str]]:
    names = [name for _session, name in pairs]
    identifiers = [str(session.id) for session, _name in pairs]
    identifiers.extend(
        item for group in draft["groups"] for item in group["report_ids"]
    )
    identifiers.extend(draft["ungrouped_report_ids"])
    return names, identifiers


async def _visible_topic(db: AsyncSession, user: User, topic_id: UUID) -> Topic:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    member = await session_crud.is_course_member(
        db, user_id=user.id, course_id=topic.course_id
    )
    instructor = await course_crud.is_course_instructor(
        db, course_id=topic.course_id, teacher_id=user.id
    )
    if not member and not instructor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    return topic


def _draft_dict(row: ClassSummaryVersion) -> dict:
    return _fields(row.body)


def _fields(body: dict) -> dict:
    return {
        "status": body.get("status"),
        "overview": body.get("overview"),
        "viewpoint_summary": body.get("viewpoint_summary"),
        "denominator": body.get("denominator"),
        "groups": body.get("groups") or [],
        "ungrouped_report_ids": body.get("ungrouped_report_ids") or [],
    }


async def _reviewed_summary(db: AsyncSession, topic_id: UUID) -> ClassSummaryVersion:
    row = await summary_crud.latest_summary(db, topic_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )
    if row.body.get("status") != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "version": row.version,
                "summary_status": row.body.get("status"),
                "message": "Summary is not reviewed",
            },
        )
    return row


async def _withdraw_other_reviews(
    db: AsyncSession, topic_id: UUID, *, keep: int
) -> None:
    for old in await summary_crud.summary_versions(db, topic_id):
        if old.version == keep or old.body.get("status") != "reviewed":
            continue
        await summary_crud.upsert_summary_version(
            db,
            topic_id=topic_id,
            version=old.version,
            body={**old.body, "status": "withdrawn"},
        )


async def _instructor_topic(db: AsyncSession, teacher: User, topic_id: UUID) -> Topic:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    if not await course_crud.is_course_instructor(
        db, course_id=topic.course_id, teacher_id=teacher.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Course instructor required"
        )
    return topic
