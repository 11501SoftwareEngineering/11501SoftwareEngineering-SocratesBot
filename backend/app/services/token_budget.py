"""Conservative token estimates for the OpenRouter-compatible chat request."""

from __future__ import annotations

import json

import tiktoken

from app.core.model_catalog import INQUIRY_CATALOG_MODELS
from app.services.model_client import _outbound

# Keep this explicit: an unknown configured model must not fall back to a
# character-count guess. tiktoken has no GPT-6 entries, so the catalog models use
# o200k_base, the newest OpenAI encoding (GPT-4o, GPT-5, and the o-series). The
# count is an estimate; the safety margin below absorbs small differences.
_OPENAI_MODELS = ("openai/gpt-4o-mini", "openai/gpt-4o", *INQUIRY_CATALOG_MODELS)
MODEL_ENCODINGS = {
    name: "o200k_base"
    for model_id in _OPENAI_MODELS
    for name in (model_id, model_id.removeprefix("openai/"))
}

_CHAT_MESSAGE_OVERHEAD = 4
_CHAT_REPLY_OVERHEAD = 3
_SCHEMA_OVERHEAD = 32
_SAFETY_MARGIN = 64


class ContextWindowExceeded(ValueError):
    """A model request exceeds the configured dialogue budget."""


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
