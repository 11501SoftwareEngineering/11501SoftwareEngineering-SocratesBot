"""Conservative token estimates for the OpenRouter-compatible chat request."""

from __future__ import annotations

import json

import tiktoken

from app.services.model_client import _outbound

# Keep this explicit: an unknown configured model must not fall back to a
# character-count guess. Add an entry when the runtime model catalog changes.
MODEL_ENCODINGS = {
    "gpt-4o-mini": "o200k_base",
    "openai/gpt-4o-mini": "o200k_base",
    "gpt-4o": "o200k_base",
    "openai/gpt-4o": "o200k_base",
    "gpt-6.2-sol": "o200k_base",
    "openai/gpt-6.2-sol": "o200k_base",
}

_CHAT_MESSAGE_OVERHEAD = 4
_CHAT_REPLY_OVERHEAD = 3
_SCHEMA_OVERHEAD = 32
_SAFETY_MARGIN = 64


class UnsupportedModelTokenizerError(ValueError):
    """The selected provider model has no reviewed tokenizer mapping."""


def _encoding_for(model_id: str) -> tiktoken.Encoding:
    encoding_name = MODEL_ENCODINGS.get(model_id)
    if encoding_name is None:
        raise UnsupportedModelTokenizerError(
            f"No tokenizer mapping configured for model {model_id!r}"
        )
    return tiktoken.get_encoding(encoding_name)


def estimate_request_tokens(
    *,
    model_id: str,
    instructions: str,
    material: str,
    schema: dict,
) -> int:
    """Estimate system, user, schema, and message-framing input tokens."""
    encoding = _encoding_for(model_id)

    def count(text: str) -> int:
        return len(encoding.encode(text, disallowed_special=()))

    system, user = _outbound(instructions, material)
    serialized_schema = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    return (
        count(system)
        + count(user)
        + count(serialized_schema)
        + 2 * _CHAT_MESSAGE_OVERHEAD
        + _CHAT_REPLY_OVERHEAD
        + _SCHEMA_OVERHEAD
        + _SAFETY_MARGIN
    )


def estimate_total_request_tokens(
    *,
    model_id: str,
    instructions: str,
    material: str,
    schema: dict,
    output_tokens: int,
) -> int:
    """Include the reserved completion size in the configured context budget."""
    return (
        estimate_request_tokens(
            model_id=model_id,
            instructions=instructions,
            material=material,
            schema=schema,
        )
        + output_tokens
    )
