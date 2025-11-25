"""Lightweight CLI utilities for deployment scripts."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import settings
from .database import init_database
from .instrumentation import get_logger

logger = get_logger()


async def _run_init_db() -> int:
    if not settings.database_url:
        logger.warning("DATABASE_URL is not configured; skipping migrations.")
        return 0

    try:
        await init_database()
        logger.info("Database migrations completed.")
        return 0
    except Exception as exc:  # pragma: no cover - deployment path
        logger.error("Database migration failed: %s", exc)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lewis-cli")
    parser.add_argument("command", choices=["init-db"], help="Command to execute.")
    args = parser.parse_args(argv)

    if args.command == "init-db":
        return asyncio.run(_run_init_db())

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
