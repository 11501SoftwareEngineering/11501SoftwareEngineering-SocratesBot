"""CLI entry: ``PYTHONPATH=. uv run --locked python -m scripts.seed_dev``."""

from __future__ import annotations

import asyncio
import logging
import sys

from scripts.seed.runner import SeedError, run_seed_for_cli

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)


def main() -> None:
    try:
        asyncio.run(run_seed_for_cli())
    except SeedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
