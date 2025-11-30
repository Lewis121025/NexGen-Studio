#!/usr/bin/env bash
set -euo pipefail

echo "======================================="
echo "  Lewis AI System - Docker launcher"
echo "======================================="

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.docker.example" ]]; then
    cp .env.docker.example .env
    echo "[info] Copied .env.docker.example to .env"
  else
    echo "[error] .env file not found and template missing." >&2
    exit 1
  fi
fi

python3 - <<'PY'
import secrets
from pathlib import Path
path = Path(".env")
data = path.read_text(encoding="utf-8")
replacements = {
    "replace_me_with_secure_hex": secrets.token_hex(32),
    "your_secret_key_here": secrets.token_hex(32),
    "your_api_key_salt_here": secrets.token_hex(16),
}
updated = data
for marker, value in replacements.items():
    if marker in updated:
        updated = updated.replace(marker, value, 1)
if updated != data:
    path.write_text(updated, encoding="utf-8")
PY

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] Docker is not installed or not on PATH." >&2
  exit 1
fi

if ! grep -Eq '^DATABASE_URL\s*=\s*\S+' .env; then
  echo "[error] DATABASE_URL is missing in .env. Please configure it before launching." >&2
  exit 1
fi

echo "[info] Stopping existing containers..."
docker compose down >/dev/null 2>&1 || true

echo "[info] Building images..."
docker compose build

echo "[info] Booting postgres for migrations..."
docker compose up -d postgres

echo "[info] Running database migrations via CLI..."
if ! docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 -m lewis_ai_system.cli init-db; then
  echo "[error] Database initialization failed. Check docker compose logs postgres/lewis-api." >&2
  exit 1
fi

echo "[info] Starting full stack..."
docker compose up -d

echo "[info] Waiting for API health..."
for _ in {1..30}; do
  if curl -fs http://localhost:8000/healthz >/dev/null 2>&1; then
    echo "[success] Lewis AI System is up at http://localhost:8000"
    exit 0
  fi
  sleep 2
done

echo "[error] API did not become healthy in time. Check docker compose logs."
exit 1
