"""Gemini key selection with bounded Redis admission and failover.

Only the current teacher's bundle is eligible. Local counters use credential
fingerprints: Google can share quotas across several keys in the same project.
"""

import hashlib
import json
import math

from app.core.config import settings
from app.services import ai_diagnostics, gemini_queue
from app.services.key_pool import parse_keys
from app.services.model_client import ModelCallError


async def send_gemini(client, payload, headers, timeout_s, usage_key, usage_task):
    if usage_key is None or getattr(usage_key, "source", None) == "server":
        keys = parse_keys(settings.GEMINI_API_KEYS.get_secret_value())
        if not keys:
            single = settings.GEMINI_API_KEY.get_secret_value()
            keys = (single,) if single else ()
    else:
        keys = getattr(usage_key, "api_keys", (str(usage_key),))
    if not 1 <= len(keys) <= 3:
        raise ModelCallError(503, reason="gemini_credentials_missing")
    if any(k.startswith(("sk-or-", "gsk_")) for k in keys):
        raise ModelCallError(503, reason="gemini_credentials_rejected")
    # An opaque fingerprint groups the same key across teachers and workers.
    # It is not claimed to identify a Google project or multiply project quota.
    remaining = [(hashlib.sha256(k.encode()).hexdigest(), k) for k in keys]
    try:
        remaining = await gemini_queue.order_credentials(remaining)
    except gemini_queue.QueueUnavailable as exc:
        raise ModelCallError(503, reason=exc.reason) from None
    tokens = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 128
    for attempt in range(1, len(keys) + 1):
        try:
            ai_diagnostics.emit("provider_queue_wait", provider="gemini")
            slot, key = await gemini_queue.reserve(remaining, payload["model"], tokens)
        except gemini_queue.QueueUnavailable as exc:
            error = ModelCallError(503, reason=exc.reason)
            error.retry_after = exc.retry_after
            raise error from None
        response = await client._send_one(
            payload,
            {"Authorization": f"Bearer {key}"},
            timeout_s,
            usage_key,
            usage_task,
            attempt,
        )
        if response.status_code not in {429, 402, 401, 403}:
            return response
        try:
            cooldown = await gemini_queue.cool(slot, key, payload["model"], response)
        except Exception:
            raise ModelCallError(503, reason="gemini_queue_unavailable") from None
        remaining = [(s, k) for s, k in remaining if s != slot]
        ai_diagnostics.emit(
            "credential_cooling",
            provider="gemini",
            attempt=attempt,
            http_status=response.status_code,
        )
        if not remaining:
            error = ModelCallError(503, reason="gemini_quota_wait")
            error.retry_after = max(1, math.ceil(cooldown or 60))
            raise error
    raise ModelCallError(503, reason="gemini_quota_wait")
