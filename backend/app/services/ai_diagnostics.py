"""Content-free correlated AI events; opt-in, redacted development responses."""

import json
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from uuid import uuid4

from app.core.config import BACKEND_DIR, settings

logger = logging.getLogger("app.ai")
_context = ContextVar("ai_diagnostic_context", default=None)
_last_call = ContextVar("ai_last_call", default=None)
TRACE_DIR = BACKEND_DIR / ".local" / "ai-traces"


@contextmanager
def scope(**fields):
    token = _context.set({**(_context.get() or {}), **fields})
    last_token = _last_call.set(None)
    try:
        yield
    finally:
        _last_call.reset(last_token)
        _context.reset(token)


def call_started(task, model, payload, instructions):
    from app.core.prompts import PROMPTS

    fields = {"call_id": uuid4().hex, "task": task, "model": model}
    _last_call.set(fields)
    version = next(
        (p.version for p in PROMPTS.values() if p.instructions == instructions),
        "custom",
    )
    emit(
        "call_started",
        **fields,
        max_output_tokens=payload["max_tokens"],
        prompt_version=version,
        prompt_sha256=sha256(instructions.encode()).hexdigest(),
        schema_sha256=sha256(
            json.dumps(payload["response_format"], sort_keys=True).encode()
        ).hexdigest(),
        request_bytes=len(json.dumps(payload, ensure_ascii=False).encode()),
    )
    return fields


def emit(event, **fields):
    record = {
        "event": event,
        **(_context.get() or {}),
        **(_last_call.get() or {}),
        **fields,
    }
    logger.info("ai_event %s", json.dumps(record, ensure_ascii=False, default=str))


def validation_failure(schema, exc):
    errors = []
    for issue in exc.errors(
        include_input=False, include_context=False, include_url=False
    )[:12]:
        # An extra key can itself contain arbitrary student/provider text.
        location = (
            ["extra_field"]
            if issue["type"] == "extra_forbidden"
            else list(issue["loc"])
        )
        errors.append({"location": location, "type": issue["type"]})
    emit("validation_failed", reason="schema_validation", schema=schema, errors=errors)


def response_received(response, *, attempt, elapsed_ms, event_id, secret):
    metadata = {
        "http_status": response.status_code,
        "attempt": attempt,
        "elapsed_ms": elapsed_ms,
        "response_bytes": len(response.content),
        "usage_event_id": str(event_id) if event_id else None,
    }
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        ident = body.get("id")
        if (
            isinstance(ident, str)
            and re.fullmatch(r"gen-[A-Za-z0-9_-]{1,180}", ident)
            and "sk-" not in ident
        ):
            metadata["provider_request_id"] = ident
        choices = body.get("choices")
        choice = (
            choices[0]
            if isinstance(choices, list) and choices and isinstance(choices[0], dict)
            else {}
        )
        reason = choice.get("finish_reason")
        metadata["finish_reason"] = (
            reason
            if isinstance(reason, str)
            and reason in {"stop", "length", "content_filter", "error", "tool_calls"}
            else (None if reason is None else "other")
        )
        actual_model = body.get("model")
        if (
            isinstance(actual_model, str)
            and re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", actual_model)
            and "sk-" not in actual_model
        ):
            metadata["actual_model"] = actual_model
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        metadata["content_chars"] = len(content) if isinstance(content, str) else None
        usage = body.get("usage")
        if isinstance(usage, dict):
            for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = usage.get(name)
                if type(value) is int and value >= 0:
                    metadata[name] = value
            details = usage.get("completion_tokens_details")
            if (
                isinstance(details, dict)
                and type(details.get("reasoning_tokens")) is int
            ):
                metadata["reasoning_tokens"] = details["reasoning_tokens"]
        metadata["provider_error_present"] = bool(body.get("error"))
    from app.services.ai_usage import usage_fields

    charge = usage_fields(response).get("cost_usd")
    metadata["cost_usd"] = str(charge) if charge is not None else None
    emit("provider_response", **metadata)
    write_trace(response, metadata, secret)


class _TraceHandler(RotatingFileHandler):
    def handleError(self, record):
        logger.warning("ai_trace_write_failed")


def write_trace(response, metadata, secret):
    if not settings.AI_TRACE_ENABLED or settings.APP_ENV != "development":
        return
    try:
        # Raw responses only: no input messages, headers, credentials or reasoning text.
        raw = response.text[:131072]
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"raw_text_prefix": raw, "truncated": len(response.text) > 131072}

        def redact(value):
            if isinstance(value, dict):
                return {
                    redact(key): (
                        "[REDACTED]"
                        if key.lower()
                        in {
                            "authorization",
                            "api_key",
                            "apikey",
                            "password",
                            "token",
                            "refresh_token",
                            "access_token",
                            "cookie",
                            "reasoning",
                            "reasoning_content",
                            "reasoning_details",
                        }
                        else redact(item)
                    )
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, str):
                value = value.replace(secret, "[REDACTED]") if secret else value
                from app.services.key_pool import parse_keys

                secrets = parse_keys(settings.OPENAI_API_KEYS.get_secret_value())
                secrets += (settings.OPENAI_API_KEY.get_secret_value(),)
                for configured_key in sorted(secrets, key=len, reverse=True):
                    if configured_key:
                        value = value.replace(configured_key, "[REDACTED]")
                return re.sub(r"(?:sk-|AIza|AQ\.)[A-Za-z0-9_.-]+", "[REDACTED]", value)
            return value

        record = {
            "event": "raw_provider_response",
            **(_context.get() or {}),
            **(_last_call.get() or {}),
            **metadata,
            "response": redact(body),
        }
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        handler = _TraceHandler(
            TRACE_DIR / f"ai-responses-{os.getpid()}.jsonl",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        try:
            handler.emit(
                logging.makeLogRecord(
                    {
                        "msg": json.dumps(record, ensure_ascii=False),
                        "levelno": logging.INFO,
                        "levelname": "INFO",
                    }
                )
            )
        finally:
            handler.close()
    except Exception:
        logger.warning("ai_trace_write_failed")


def job_scope(kind):
    def decorate(function):
        @wraps(function)
        async def wrapped(attempt_id):
            with scope(job_id=str(attempt_id), job_kind=kind):
                return await function(attempt_id)

        return wrapped

    return decorate
