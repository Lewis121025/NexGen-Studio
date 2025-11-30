"""Lightweight CLI utilities for deployment scripts."""

from __future__ import annotations

import argparse
import asyncio

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


async def _run_seed_data() -> int:
    """运行种子数据脚本"""
    if not settings.database_url:
        logger.warning("DATABASE_URL is not configured; skipping seed data.")
        return 0

    try:
        # 动态导入以避免循环依赖
        import sys
        import os
        
        # 添加scripts目录到路径
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        from seed_data import main as seed_main
        await seed_main()
        return 0
    except Exception as exc:  # pragma: no cover - deployment path
        logger.error("Seed data failed: %s", exc)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lewis-cli")
    parser.add_argument("command", choices=["init-db", "seed-data"], help="Command to execute.")
    args = parser.parse_args(argv)

    if args.command == "init-db":
        return asyncio.run(_run_init_db())
    elif args.command == "seed-data":
        return asyncio.run(_run_seed_data())

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
