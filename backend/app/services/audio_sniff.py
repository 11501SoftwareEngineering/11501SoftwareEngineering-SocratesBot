"""Magic-byte sniff for student STT uploads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SniffedAudio:
    filename: str
    content_type: str


def sniff_audio(data: bytes) -> SniffedAudio | None:
    """Return provider filename/MIME from magic bytes, or ``None`` if unsupported."""
    if len(data) < 12:
        return None
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return SniffedAudio("audio.webm", "audio/webm")
    if data[4:8] == b"ftyp":
        return SniffedAudio("audio.m4a", "audio/mp4")
    if data[:4] == b"OggS":
        return SniffedAudio("audio.ogg", "audio/ogg")
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return SniffedAudio("audio.wav", "audio/wav")
    if data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return SniffedAudio("audio.mp3", "audio/mpeg")
    return None
