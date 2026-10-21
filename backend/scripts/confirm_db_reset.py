"""Guard for ``make db-reset``: interactive yes, or ``CONFIRM=1``."""

from __future__ import annotations

import os
import sys

from app.core.config import settings


def confirm_db_reset(
    *,
    confirm_env: str | None = None,
    stdin=None,
    stdout=None,
    stderr=None,
) -> bool:
    """Return True if wipe+rebuild is allowed.

    Refuses unless ``APP_ENV=development`` (even with ``CONFIRM=1``).
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr

    if settings.APP_ENV != "development":
        print(
            f"aborted: db-reset refused APP_ENV={settings.APP_ENV!r} "
            "(development only)",
            file=stderr,
        )
        return False

    host = settings.POSTGRES_HOST.get_secret_value()
    db_name = settings.POSTGRES_DB.get_secret_value()
    target = f"APP_ENV={settings.APP_ENV} POSTGRES_HOST={host} POSTGRES_DB={db_name}"

    raw = confirm_env if confirm_env is not None else os.environ.get("CONFIRM", "")
    if raw.strip() == "1":
        print(f"db-reset confirmed via CONFIRM=1 ({target})", file=stdout)
        return True

    print(
        "WARNING: db-reset will Alembic downgrade to base (wipe schema), "
        "upgrade head, then seed.\n"
        f"Target: {target}\n"
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
