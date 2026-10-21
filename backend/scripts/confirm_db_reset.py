"""Guard for ``make db-reset``: interactive yes, or ``CONFIRM=1``."""

from __future__ import annotations

import os
import sys


def confirm_db_reset(
    *,
    confirm_env: str | None = None,
    stdin=None,
    stdout=None,
) -> bool:
    """Return True if wipe+rebuild is allowed."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    raw = confirm_env if confirm_env is not None else os.environ.get("CONFIRM", "")
    if raw.strip() == "1":
        return True

    print(
        "WARNING: db-reset will Alembic downgrade to base (wipe schema), "
        "upgrade head, then seed.\n"
        "Confirm this is your local development database. Continue? y/[N] ",
        end="",
        file=stdout,
        flush=True,
    )
    answer = stdin.read(1).lower()
    return answer == "y"


def main() -> None:
    if not confirm_db_reset():
        print("aborted: db-reset not confirmed", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
