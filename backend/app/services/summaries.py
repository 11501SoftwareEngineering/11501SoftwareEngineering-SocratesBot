"""Class summary draft, publish, and the student read. A2 is not granted."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import GenerationStatus, TopicStage
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import summary as summary_crud
from app.crud import topic as topic_crud
from app.models.class_summary import ClassSummaryVersion
from app.models.topic import Topic
from app.models.user import User
from app.services import summary_runner
from app.services.central_synthesis import from_native, inquiry_key, validate_reports
from app.services.dialogue_turn import brief_of
from app.services.summary_text import leaked_identifier, public_summary
from app.services.token_budget import UnsupportedModelTokenizerError


def _attempt_running(latest) -> bool:
    if latest is None or latest.status not in {
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }:
        return False
    lease = latest.lease_expires_at
    return lease is not None and lease >= datetime.now(UTC)


async def _enqueue(db: AsyncSession, topic_id: UUID) -> None:
    topic = await topic_crud.lock_topic(db, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if await summary_crud.has_open_dialogues(db, topic_id):
        raise HTTPException(
            status_code=409,
            detail="End all dialogues before generating a class summary",
        )
    latest = await summary_crud.latest_attempt(db, topic_id)
    if _attempt_running(latest):
        return
    request = await native_request(db, topic)
    created = await summary_crud.insert_attempt(
        db, topic_id=topic_id, request_json=request
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
    await _enqueue(db, topic.id)
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
    await topic_crud.lock_topic(db, topic.id)
    row = await _reviewed_summary(db, topic.id)
    draft = _draft_dict(row)
    names, identifiers = _identity_values(draft, await report_crud_names(db, topic.id))
    if leaked_identifier(draft, names=names, identifiers=identifiers):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Summary contains a name or identifier",
        )
    _latest, previous = await _published_row(db, topic.id)
    if previous is not None and previous is not row:
        previous.body = {**previous.body, "status": "withdrawn"}
    row.body = {
        **row.body,
        **draft,
        "published": public_summary(draft),
        "published_version": row.version,
        "status": "published",
    }
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
    await topic_crud.lock_topic(db, topic.id)
    latest, published = await _published_row(db, topic.id)
    if latest is None or published is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No published summary"
        )
    published.body = {**published.body, "status": "withdrawn"}
    if latest is published:
        latest.body = {
            **published.body,
            "published": None,
            "published_version": None,
        }
    else:
        latest.body = {**latest.body, "published": None, "published_version": None}
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
        "published_version": None
        if latest is None
        else latest.body.get("published_version"),
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
    await topic_crud.lock_topic(db, row.topic_id)
    current = await summary_crud.latest_summary(db, row.topic_id)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )
    changed = (
        current.body.get("overview") != overview
        or current.body.get("viewpoint_summary") != viewpoint_summary
    )
    body = {
        **current.body,
        "overview": overview,
        "viewpoint_summary": viewpoint_summary,
        "status": summary_status,
    }
    if not changed:
        current.body = body
        return current
    return await summary_crud.upsert_summary_version(
        db,
        topic_id=current.topic_id,
        version=current.version + 1,
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


async def _published_row(
    db: AsyncSession, topic_id: UUID
) -> tuple[ClassSummaryVersion | None, ClassSummaryVersion | None]:
    """Return the latest row and the row named by its published_version."""
    latest = await summary_crud.latest_summary(db, topic_id)
    if latest is None:
        return None, None
    version = latest.body.get("published_version")
    if version is None or not latest.body.get("published"):
        return latest, None
    if latest.version == int(version):
        return latest, latest
    return latest, await summary_crud.summary_version(db, topic_id, int(version))


async def _withdraw_other_reviews(
    db: AsyncSession, topic_id: UUID, *, keep: int
) -> None:
    for old in await summary_crud.summary_versions(db, topic_id):
        if old.version == keep or old.body.get("status") != "reviewed":
            continue
        old.body = {**old.body, "status": "withdrawn"}


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


async def native_request(
    db: AsyncSession,
    topic: Topic,
    *,
    allow_empty: bool = False,
    model_id: str | None = None,
    language: str | None = None,
) -> dict:
    """Freeze ready native evidence; caller owns topic lock and lifecycle checks."""
    topic_id = topic.id
    try:
        rows = await summary_crud.ready_native_reports(db, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not rows and not allow_empty:
        raise HTTPException(status_code=400, detail="No ready reports")
    if len(rows) > 50:
        raise HTTPException(
            status_code=413, detail="Stage3 supports at most 50 reports per topic"
        )
    try:
        reports = [
            from_native(row["report_id"], row["metadata"]).model_dump() for row in rows
        ]
        validated = validate_reports(reports) if reports else []
        if validated and validated[0].topicKey != inquiry_key(brief_of(topic)):
            raise ValueError("Inquiry revision mismatch")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Regenerate personal reports with matching native evidence before class synthesis",
        ) from exc
    request = {
        "schema_version": "native-central-request-v1",
        "reports": reports,
        "sources": [
            {
                "report_id": row["report_id"],
                "session_id": row["session_id"],
                "source_digest": row["metadata"]["source_digest"],
            }
            for row in rows
        ],
        "model_id": model_id or topic.model_id or settings.OPENAI_MODEL,
        "content_language": language
        or topic.content_language
        or settings.DEFAULT_LANGUAGE_CODE,
    }
    if allow_empty:
        request["allow_empty_cohort"] = True
        request["inquiry"] = brief_of(topic)
    try:
        summary_runner.prepare_request(request)
    except UnsupportedModelTokenizerError as exc:
        raise HTTPException(
            status_code=503, detail="Configured model tokenizer is not supported"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=413,
            detail="Stage3 request exceeds supported size or model budget",
        ) from exc
    return request
