"""Class summary draft, publish, and the student read. A2 is not granted."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GenerationStatus, TopicStage
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import summary as summary_crud
from app.models.class_summary import ClassSummary
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
    return latest is not None and latest.status in {
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }


async def _enqueue(
    db: AsyncSession, topic_id: UUID, bodies: list[tuple[str, dict]]
) -> None:
    latest = await summary_crud.latest_attempt(db, topic_id)
    if _attempt_running(latest):
        return
    created = await summary_crud.insert_attempt(
        db, topic_id=topic_id, request_json=_request(bodies)
    )
    await db.commit()
    summary_runner.schedule(created.id)


def _started(topic: Topic, published) -> dict:
    return {
        "topic_status": topic.stage,
        "published_version": None if published is None else published.version,
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
    return _started(topic, await summary_crud.published(db, topic.id))


async def read_teacher_summary(
    db: AsyncSession, *, teacher: User, topic_id: UUID
) -> dict:
    """Return the instructor view of the latest summary.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if the caller does
            not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    return await _teacher_body(db, topic)


async def edit_summary(
    db: AsyncSession,
    *,
    teacher: User,
    topic_id: UUID,
    version: int,
    overview: str,
    viewpoint_summary: str,
) -> dict:
    """Replace the overview and viewpoint, and set the status back to draft.

    Raises:
        HTTPException: 404 if the topic or version is missing; 403 if the
            caller does not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    row = await _version(db, topic.id, version)
    row.overview = overview
    row.viewpoint_summary = viewpoint_summary
    row.status = "draft"
    await db.commit()
    return {"summary": _draft(row)}


async def review_summary(
    db: AsyncSession, *, teacher: User, topic_id: UUID, version: int
) -> dict:
    """Mark one draft version as reviewed.

    Raises:
        HTTPException: 404 if the topic or version is missing; 403 if the
            caller does not instruct the course; 400 if the version is not
            a draft.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    row = await _version(db, topic.id, version)
    if row.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Version mismatch"
        )
    row.status = "reviewed"
    await db.commit()
    return {
        "version": row.version,
        "summary_status": row.status,
        "message": "Summary reviewed",
    }


async def publish_summary(
    db: AsyncSession, *, teacher: User, topic_id: UUID, version: int
) -> dict:
    """Publish a reviewed summary that contains no student identity.

    Raises:
        HTTPException: 404 if the topic or version is missing; 403 if the
            caller does not instruct the course; 400 if it is not reviewed
            or the text contains a name or identifier.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    row = await _version(db, topic.id, version)
    if row.status != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version mismatch or not reviewed",
        )
    draft = _draft_dict(row)
    names, identifiers = _identity_values(draft, await report_crud_names(db, topic.id))
    if leaked_identifier(draft, names=names, identifiers=identifiers):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Summary contains a name or identifier",
        )
    await summary_crud.save_published(
        db, topic_id=topic.id, version=row.version, body=public_summary(draft)
    )
    row.status = "published"
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
    if not await summary_crud.clear_published(db, topic.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No published summary"
        )
    row = await summary_crud.latest_summary(db, topic.id)
    if row is not None:
        row.status = "withdrawn"
    await db.commit()
    return {"summary_status": "withdrawn", "message": "Summary withdrawn"}


async def read_published(db: AsyncSession, *, user: User, topic_id: UUID) -> dict:
    """Return the published summary for a course member.

    Raises:
        HTTPException: 404 if the topic is missing or the caller is not a
            member of the course.
    """
    topic = await _visible_topic(db, user, topic_id)
    row = await summary_crud.published(db, topic.id)
    return {"summary": None if row is None else row.body}


async def report_crud_names(db: AsyncSession, topic_id: UUID):
    """Return this topic's dialogues with each student's display name."""
    from app.crud import report as report_crud

    return await report_crud.topic_dialogues(db, topic_id)


async def _teacher_body(db: AsyncSession, topic: Topic) -> dict:
    published = await summary_crud.published(db, topic.id)
    latest = await summary_crud.latest_summary(db, topic.id)
    attempt = await summary_crud.latest_attempt(db, topic.id)
    summary = (
        _draft(latest)
        if latest is not None and topic.stage == TopicStage.SUMMARY.value
        else None
    )
    return {
        "topic_status": topic.stage,
        "published_version": None if published is None else published.version,
        "summary": summary,
        "preparation_status": None if attempt is None else attempt.status,
    }


def _draft(row: ClassSummary) -> dict:
    return {
        "summary_id": str(row.id),
        "version": row.version,
        "summary_status": row.status,
        **_draft_dict(row),
    }


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


def _draft_dict(row: ClassSummary) -> dict:
    return {
        "overview": row.overview,
        "viewpoint_summary": row.viewpoint_summary,
        "denominator": row.denominator,
        "groups": row.groups,
        "ungrouped_report_ids": row.ungrouped_report_ids,
    }


async def _version(db: AsyncSession, topic_id: UUID, version: int) -> ClassSummary:
    row = await summary_crud.latest_summary(db, topic_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )
    if row.version != version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Version mismatch"
        )
    return row


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
