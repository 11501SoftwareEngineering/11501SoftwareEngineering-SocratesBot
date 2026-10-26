"""Short invitation-code generation for courses."""

from __future__ import annotations

import secrets

INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INVITE_LENGTH = 8
# Cap insert retries when invitation_code UNIQUE collides (extremely rare).
INVITE_COLLISION_RETRIES = 16


def generate_invite_code() -> str:
    """Return one CSPRNG invite code (uniqueness enforced by DB UNIQUE)."""
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))
