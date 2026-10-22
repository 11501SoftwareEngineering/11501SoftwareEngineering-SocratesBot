"""Unit tests for STT magic-byte sniffing."""

from __future__ import annotations

from app.services.audio_sniff import sniff_audio


def test_sniff_webm() -> None:
    data = b"\x1a\x45\xdf\xa3" + b"\x00" * 20
    sniffed = sniff_audio(data)
    assert sniffed is not None
    assert sniffed.filename == "audio.webm"
    assert sniffed.content_type == "audio/webm"


def test_sniff_wav() -> None:
    data = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 8
    sniffed = sniff_audio(data)
    assert sniffed is not None
    assert sniffed.filename == "audio.wav"


def test_sniff_mp4_ftyp() -> None:
    data = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8
    sniffed = sniff_audio(data)
    assert sniffed is not None
    assert sniffed.filename == "audio.m4a"
    assert sniffed.content_type == "audio/mp4"


def test_sniff_rejects_heic_ftyp() -> None:
    data = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 8
    assert sniff_audio(data) is None


def test_sniff_rejects_short_and_unknown() -> None:
    assert sniff_audio(b"short") is None
    assert sniff_audio(b"not-an-audio-file!!!!") is None
