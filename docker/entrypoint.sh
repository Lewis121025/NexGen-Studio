#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

echo "[$(timestamp)] Lewis AI System container bootstrapping..."

wait_for_database() {
  if [[ -z "${DATABASE_URL:-}" ]]; then
    return 0
  fi

  python3 - <<'PY'
import asyncio
import os
import sys
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get("DATABASE_URL")
retries = int(os.environ.get("DB_WAIT_RETRIES", "10"))
delay = float(os.environ.get("DB_WAIT_DELAY", "3"))

async def wait_for_db() -> None:
    engine = create_async_engine(DATABASE_URL)
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print(f"[{datetime.utcnow().isoformat()}Z] Database reachable (attempt {attempt})")
            await engine.dispose()
            return
        except Exception as exc:  # pragma: no cover - deployment path
            print(f"[{datetime.utcnow().isoformat()}Z] Database not ready (attempt {attempt}/{retries}): {exc}")
            if attempt == retries:
                await engine.dispose()
                raise
            await asyncio.sleep(delay)

asyncio.run(wait_for_db())
PY
}

if [[ "${DATABASE_URL:-}" != "" ]]; then
  echo "[$(timestamp)] Waiting for database connectivity..."
  if ! wait_for_database; then
    echo "[$(timestamp)] Database did not become ready" >&2
    exit 1
  fi

  if [[ "${SKIP_ENTRYPOINT_DB_INIT:-0}" != "1" ]]; then
    echo "[$(timestamp)] Running database migrations..."
    if ! python3 -m lewis_ai_system.cli init-db; then
      echo "[$(timestamp)] Database initialization failed" >&2
      exit 1
    fi
  else
    echo "[$(timestamp)] Skipping automatic database initialization"
  fi
fi

exec "$@"
