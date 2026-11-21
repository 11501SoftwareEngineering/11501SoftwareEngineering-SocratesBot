"""Native lab report and a compatibility projection; no lifecycle decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.services.dialogue_progress import validate_progress
from app.services.dialogue_turn import ProgressOut, brief_of


class NativeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    outcome: Literal["complete", "partial", "interrupted"]
    workingPosition: str = Field(max_length=1800)
    strongestReason: str = Field(max_length=1800)
    challengeExamined: str = Field(max_length=1800)
    revisionOrDefence: str = Field(max_length=1800)
    focalTensionConnection: str = Field(max_length=1800)
    remainingQuestion: str = Field(max_length=1800)
    reflection: str = Field(max_length=3500)
    unmetElements: list[str] = Field(max_length=8)


NATIVE_SCHEMA = NativeSummary.model_json_schema()
NATIVE_SCHEMA["properties"]["unmetElements"]["items"]["maxLength"] = 800


def source_snapshot(session, topic, messages, progress: dict | None) -> dict:
    if session.outcome != "completed":
        raise ValueError("Report source is not completed")
    transcript, exchanges = [], []
    turn, question = 0, topic.opening_message or ""
    seen = set()
    for message in messages:
        if message.session_id != session.id or str(message.id) in seen:
            raise ValueError("Invalid report message ownership or duplicate")
        seen.add(str(message.id))
        if message.sender == "student":
            turn += 1
            exchanges.append(
                {
                    "turn": turn,
                    "message_id": str(message.id),
                    "question": question,
                    "quote": message.content,
                }
            )
            role = "user"
        elif message.sender == "ai":
            question = message.content
            role = "assistant"
        else:
            raise ValueError("Unknown report message role")
        transcript.append(
            {
                "id": f"m{len(transcript) + 1}",
                "role": role,
                "content": message.content,
                "exchange": turn,
            }
        )
    if progress is not None:
        progress = ProgressOut.model_validate(progress).model_dump(by_alias=True)
        if validate_progress(progress, turn).issues:
            raise ValueError("Invalid report progress evidence")
    # JSON round-trip prevents later mutation of ORM JSON dictionaries.
    return json.loads(
        json.dumps(
            {
                "schema_version": "native-report-source-v1",
                "material": {
                    "interfaceLanguage": topic.content_language
                    or settings.DEFAULT_LANGUAGE_CODE,
                    "approvedInquiryBrief": brief_of(topic),
                    "transcript": transcript,
                    "finalProgress": progress,
                    "endingReason": "completed",
                },
                "exchanges": exchanges,
                "completed_at": session.completed_at.isoformat()
                if session.completed_at
                else None,
            },
            ensure_ascii=False,
        )
    )


def source_digest(source: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def project_summary(raw: dict, source: dict) -> tuple[dict, dict]:
    native = NativeSummary.model_validate(raw)
    if any(len(item) > 800 for item in native.unmetElements):
        raise ValueError("Report limitation is too long")
    exchanges = source["exchanges"]
    progress = source["material"]["finalProgress"]
    structurally_ready = bool(
        progress and validate_progress(progress, len(exchanges)).structurally_ready
    )
    evidence = "insufficient" if not exchanges else "partial"
    if (
        structurally_ready
        and native.outcome == "complete"
        and not native.unmetElements
        and all(
            value.strip()
            for value in (
                native.workingPosition,
                native.strongestReason,
                native.challengeExamined,
                native.revisionOrDefence,
            )
        )
    ):
        evidence = "sufficient"
    challenges = []
    if native.challengeExamined and progress and progress["examination"]["met"]:
        challenges = [
            {
                "challenge": native.challengeExamined,
                "responded": progress["response"]["met"],
            }
        ]
    body = {
        "viewpoint_summary": native.reflection or native.workingPosition,
        "final_viewpoint": native.workingPosition,
        "viewpoint_status": "",  # Native summary does not classify viewpoint change.
        "reasons": [native.strongestReason] if native.strongestReason else [],
        "strongest_reason": native.strongestReason,
        "challenges": challenges,
        "revision_or_defense": native.revisionOrDefence,
        "focus_connection": native.focalTensionConnection,
        "other_perspectives": "",  # A personal report has no classmate evidence.
        "open_questions": [native.remainingQuestion]
        if native.remainingQuestion
        else [],
        "evidence_status": evidence,
        "limitations": "\n".join(native.unmetElements),
        "timeline": [
            {
                "turn": row["turn"],
                "question": row["question"],
                "evidence": row["quote"],
                "viewpoint_before": "",
                "viewpoint_after": "",
                "change_type": "",
                "attribution": "none",
                "evidence_reference": {
                    key: row[key] for key in ("message_id", "turn", "quote")
                },
            }
            for row in exchanges
        ],
    }
    return body, native.model_dump()
