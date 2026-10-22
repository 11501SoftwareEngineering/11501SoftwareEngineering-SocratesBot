"""API tests for POST /student/audio/transcribe."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.stt import FakeTranscriber, GroqTranscriber, get_transcriber
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user

# Minimal valid magic bytes (padded) for sniff allowlist.
_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
_WAV = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 64


def _login(auth_client: TestClient, account: str) -> str:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": "password1"},
    )
    assert response.status_code == 200
    return bearer_from(response)


@pytest.fixture
def fake_stt(auth_client: TestClient):
    fake = FakeTranscriber(text="你好 world")
    app.dependency_overrides[get_transcriber] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_transcriber, None)


def test_transcribe_happy_path_fake(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    seed_user(store, account_id="stt-user")
    token = _login(auth_client, "stt-user")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json() == {"text": "你好 world"}
    assert fake_stt.last_call is not None
    assert fake_stt.last_call["filename"] == "audio.webm"
    assert fake_stt.last_call["language"] == "zh-TW"
    assert fake_stt.last_call["whisper_language"] == "zh"
    prompt = fake_stt.last_call["prompt"]
    assert isinstance(prompt, str)
    assert "繁體" in prompt


def test_transcribe_uses_preferred_language(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    user = seed_user(store, account_id="stt-en")
    user.languages[0].language.code = "en"
    token = _login(auth_client, "stt-en")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.wav", io.BytesIO(_WAV), "audio/wav")},
    )
    assert response.status_code == 200
    assert fake_stt.last_call is not None
    assert fake_stt.last_call["language"] == "en"
    assert fake_stt.last_call["whisper_language"] == "en"


def test_transcribe_language_override(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    seed_user(store, account_id="stt-override")
    token = _login(auth_client, "stt-override")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
        data={"language": "es"},
    )
    assert response.status_code == 200
    assert fake_stt.last_call is not None
    assert fake_stt.last_call["language"] == "es"


def test_transcribe_invalid_language_400(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    seed_user(store, account_id="stt-bad-lang")
    token = _login(auth_client, "stt-bad-lang")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
        data={"language": "fr"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid language code"
    assert fake_stt.last_call is None


def test_transcribe_rejects_non_audio(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    seed_user(store, account_id="stt-bad-bytes")
    token = _login(auth_client, "stt-bad-bytes")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={
            "file": (
                "x.bin",
                io.BytesIO(b"not-audio!!!!!!!!"),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 400
    assert fake_stt.last_call is None


def test_transcribe_rejects_oversize(
    auth_client: TestClient,
    store: FakeStore,
    fake_stt: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.routes.student_audio.settings.STT_MAX_AUDIO_BYTES", 32
    )
    seed_user(store, account_id="stt-big")
    token = _login(auth_client, "stt-big")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(_WEBM + b"\x00" * 64), "audio/webm")},
    )
    assert response.status_code == 413
    assert fake_stt.last_call is None


def test_transcribe_accepts_over_one_megabyte_under_stt_cap(
    auth_client: TestClient,
    store: FakeStore,
    fake_stt: FakeTranscriber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starlette default max_part_size is 1MB; route must raise the form ceiling."""
    monkeypatch.setattr(
        "app.api.v1.routes.student_audio.settings.STT_MAX_AUDIO_BYTES",
        2 * 1024 * 1024,
    )
    seed_user(store, account_id="stt-1mb")
    token = _login(auth_client, "stt-1mb")
    # Just over Starlette's 1MiB default part limit, under our STT cap.
    body = _WEBM + b"\x00" * (1024 * 1024)

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(body), "audio/webm")},
    )
    assert response.status_code == 200
    assert fake_stt.last_call is not None
    assert fake_stt.last_call["audio_len"] == len(body)


def test_transcribe_unauthenticated(
    auth_client: TestClient, fake_stt: FakeTranscriber
) -> None:
    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
    )
    assert response.status_code == 401
    assert fake_stt.last_call is None


def test_transcribe_blocked_when_must_change_password(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    seed_user(store, account_id="stt-mcp", must_change_password=True)
    token = _login(auth_client, "stt-mcp")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
    )
    assert response.status_code == 403
    assert fake_stt.last_call is None


def test_transcribe_real_path_requires_groq_key(
    auth_client: TestClient, store: FakeStore
) -> None:
    seed_user(store, account_id="stt-real-key")
    token = _login(auth_client, "stt-real-key")
    app.dependency_overrides[get_transcriber] = lambda: GroqTranscriber()
    try:
        response = auth_client.post(
            "/api/v1/student/audio/transcribe",
            headers={"Authorization": token},
            files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
        )
    finally:
        app.dependency_overrides.pop(get_transcriber, None)
    assert response.status_code == 400
    assert "Groq" in response.json()["detail"]


def test_transcribe_passes_client_key_to_fake(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    seed_user(store, account_id="stt-key-pass")
    token = _login(auth_client, "stt-key-pass")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={
            "Authorization": token,
            "X-Groq-Api-Key": "gsk_test_key",
        },
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
    )
    assert response.status_code == 200
    assert fake_stt.last_call is not None
    assert fake_stt.last_call["api_key"] == "gsk_test_key"


def test_transcribe_retains_mixed_text(
    auth_client: TestClient, store: FakeStore, fake_stt: FakeTranscriber
) -> None:
    fake_stt.text = "你好 Socrates"
    seed_user(store, account_id="stt-mixed")
    token = _login(auth_client, "stt-mixed")

    response = auth_client.post(
        "/api/v1/student/audio/transcribe",
        headers={"Authorization": token},
        files={"file": ("rec.webm", io.BytesIO(_WEBM), "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "你好 Socrates"
