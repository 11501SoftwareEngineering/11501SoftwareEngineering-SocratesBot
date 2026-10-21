"""Make-path helper: ensure ``dev-admin`` is in ``SUPER_ADMIN_ACCOUNTS``."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from scripts.seed.catalog import ACCOUNT_ADMIN

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BACKEND_DIR / "config.yaml"
EXAMPLE_PATH = BACKEND_DIR / "config.yaml.example"
ADMIN_ID = ACCOUNT_ADMIN.account_id


def _load_mapping(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        msg = f"{path.name} must be a YAML mapping"
        raise ValueError(msg)
    return raw


def _write_mapping(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def ensure_dev_admin_elevated(
    *,
    config_path: Path = CONFIG_PATH,
    example_path: Path = EXAMPLE_PATH,
    prompt: bool = True,
    stdin=None,
    stdout=None,
) -> str:
    """Ensure ``dev-admin`` is listed in ``SUPER_ADMIN_ACCOUNTS``.

    Returns a short status: ``created`` | ``unchanged`` | ``appended`` |
    ``skipped`` | ``wrote_empty``.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    if not config_path.is_file():
        data = _load_mapping(example_path) if example_path.is_file() else {}
        data["SUPER_ADMIN_ACCOUNTS"] = [ADMIN_ID]
        _write_mapping(config_path, data)
        print(
            f"wrote {config_path.name} with SUPER_ADMIN_ACCOUNTS=[{ADMIN_ID}]",
            file=stdout,
        )
        return "created"

    data = _load_mapping(config_path)
    accounts = data.get("SUPER_ADMIN_ACCOUNTS", [])
    if not isinstance(accounts, list):
        msg = "SUPER_ADMIN_ACCOUNTS must be a list"
        raise ValueError(msg)
    accounts = [str(item) for item in accounts]

    if ADMIN_ID in accounts:
        print(f"{ADMIN_ID} already in SUPER_ADMIN_ACCOUNTS", file=stdout)
        return "unchanged"

    if not accounts:
        data["SUPER_ADMIN_ACCOUNTS"] = [ADMIN_ID]
        _write_mapping(config_path, data)
        print(f"set SUPER_ADMIN_ACCOUNTS=[{ADMIN_ID}]", file=stdout)
        return "wrote_empty"

    if not prompt:
        print(
            f"SUPER_ADMIN_ACCOUNTS already has values; not adding {ADMIN_ID} "
            "(non-interactive)",
            file=stdout,
        )
        return "skipped"

    print(
        f"SUPER_ADMIN_ACCOUNTS currently: {accounts}\nAppend {ADMIN_ID}? y/[N] ",
        end="",
        file=stdout,
        flush=True,
    )
    answer = stdin.read(1).lower()
    if answer != "y":
        print(f"left config unchanged (declined adding {ADMIN_ID})", file=stdout)
        return "skipped"

    accounts.append(ADMIN_ID)
    data["SUPER_ADMIN_ACCOUNTS"] = accounts
    _write_mapping(config_path, data)
    print(f"appended {ADMIN_ID} to SUPER_ADMIN_ACCOUNTS", file=stdout)
    return "appended"


def main() -> None:
    try:
        ensure_dev_admin_elevated(prompt=True)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
