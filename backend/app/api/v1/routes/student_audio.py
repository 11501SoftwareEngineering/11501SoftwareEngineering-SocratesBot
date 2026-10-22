"""Student audio transcription (Groq Whisper)."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.formparsers import MultiPartException

from app.api.deps import ActiveUser
from app.api.openapi_responses import TRANSCRIBE_RESPONSES
from app.api.student_audio_errors import (
    STT_AUDIO_TOO_LARGE_DETAIL,
    STT_INVALID_LANGUAGE_DETAIL,
    STT_INVALID_OR_CORRUPT_AUDIO_DETAIL,
    STT_MISSING_GROQ_KEY_DETAIL,
)
from app.core.config import settings
from app.core.locales import DEFAULT_LANGUAGE_CODE, parse_stt_language
from app.crud.user import preferred_language_code
from app.schemas.student_audio import TranscribeResponse
from app.services.audio_sniff import sniff_audio
from app.services.stt import (
    FakeTranscriber,
    Transcriber,
    build_stt_prompt,
    get_transcriber,
)

router = APIRouter(prefix="/student/audio", tags=["student-audio"])

GROQ_API_KEY_HEADER = "X-Groq-Api-Key"
# Multipart wrappers (boundaries/headers) beyond the raw audio part.
_MULTIPART_OVERHEAD_BYTES = 4096


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    responses=TRANSCRIBE_RESPONSES,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Audio upload (webm/wav/ogg/mp3/m4a)",
                            },
                            "language": {
                                "type": "string",
                                "description": "Optional exact locale override (zh-TW/en/es)",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def transcribe_audio(
    request: Request,
    current_user: ActiveUser,
    transcriber: Annotated[Transcriber, Depends(get_transcriber)],
    x_groq_api_key: Annotated[str | None, Header(alias=GROQ_API_KEY_HEADER)] = None,
) -> TranscribeResponse:
    """Transcribe student audio via Groq Whisper (BYO key in header)."""
    api_key = (x_groq_api_key or "").strip()
    # Fake path (tests) may omit the key; real Groq path requires it.
    if not api_key and not isinstance(transcriber, FakeTranscriber):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=STT_MISSING_GROQ_KEY_DETAIL,
        )

    max_bytes = settings.STT_MAX_AUDIO_BYTES
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes + _MULTIPART_OVERHEAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=STT_AUDIO_TOO_LARGE_DETAIL,
                )
        except ValueError:
            pass

    # Parse with the same ceiling as STT_MAX_AUDIO_BYTES (Starlette default is 1MB).
    try:
        form = await request.form(max_part_size=max_bytes)
    except MultiPartException as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=STT_AUDIO_TOO_LARGE_DETAIL,
        ) from exc

    upload = form.get("file")
    if not isinstance(upload, (UploadFile, StarletteUploadFile)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=STT_INVALID_OR_CORRUPT_AUDIO_DETAIL,
        )

    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=STT_AUDIO_TOO_LARGE_DETAIL,
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=STT_INVALID_OR_CORRUPT_AUDIO_DETAIL,
        )

    sniffed = sniff_audio(data)
    if sniffed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=STT_INVALID_OR_CORRUPT_AUDIO_DETAIL,
        )

    language_raw = form.get("language")
    language = language_raw if isinstance(language_raw, str) else None
    if language is not None and language.strip():
        try:
            resolved = parse_stt_language(language)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=STT_INVALID_LANGUAGE_DETAIL,
            ) from exc
    else:
        preferred = preferred_language_code(current_user) or DEFAULT_LANGUAGE_CODE
        try:
            resolved = parse_stt_language(preferred)
        except ValueError:
            resolved = DEFAULT_LANGUAGE_CODE

    prompt = build_stt_prompt(resolved)
    text = await transcriber.transcribe(
        audio_bytes=data,
        filename=sniffed.filename,
        content_type=sniffed.content_type,
        language=resolved,
        prompt=prompt,
        api_key=api_key,
    )
    return TranscribeResponse(text=text)
