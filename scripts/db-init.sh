#!/usr/bin/env bash
set -euo pipefail

echo "======================================="
echo "  Lewis AI System - Database Init"
echo "======================================="

if [[ ! -f ".env" ]]; then
  echo "[error] .env file not found. Please create it and configure DATABASE_URL." >&2
  exit 1
fi

echo "[info] Checking database service status..."

# Check if PostgreSQL is running
postgres_state=$(docker compose ps postgres --format json 2>/dev/null | grep -o '"State":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
if [[ "$postgres_state" != "running" ]]; then
  echo "[error] PostgreSQL service is not running" >&2
  echo "[info] Please run: ./scripts/start-databases.sh" >&2
  exit 1
fi

echo "[success] PostgreSQL service is running"

# Wait for database to be ready
echo "[info] Waiting for database connection..."
max_retries=20
retry_count=0
db_ready=false

while [[ $retry_count -lt $max_retries ]]; do
  if docker compose exec -T postgres pg_isready -U lewis >/dev/null 2>&1; then
    db_ready=true
    break
  fi
  retry_count=$((retry_count + 1))
  sleep 1
done

if [[ "$db_ready" != "true" ]]; then
  echo "[error] Database did not become ready in time" >&2
  exit 1
fi

echo "[success] Database connection is ready"
echo ""

# Check if image needs to be built
echo "[info] Checking application image..."
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "lewis-ai-system-lewis-api"; then
  echo "[info] Building application image (for database initialization)..."
  docker compose build lewis-api
  if [[ $? -ne 0 ]]; then
    echo "[error] Image build failed" >&2
    exit 1
  fi
fi

echo "[success] Application image is ready"
echo ""

# Run database initialization
echo "[info] Running database table initialization..."
echo ""

docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 -m lewis_ai_system.cli init-db

if [[ $? -ne 0 ]]; then
  echo ""
  echo "[error] Database initialization failed" >&2
  echo "[info] Check logs: docker compose logs postgres" >&2
  exit 1
fi

echo ""
echo "======================================="
echo "  ✅ Database initialization complete!"
echo "======================================="
echo ""
echo "[info] Database is ready, you can now start the application services"
echo ""

