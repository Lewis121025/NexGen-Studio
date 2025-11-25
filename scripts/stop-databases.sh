#!/usr/bin/env bash
set -euo pipefail

echo "======================================="
echo "  Lewis AI System - Stop Databases"
echo "======================================="

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] Docker is not installed or not on PATH." >&2
  exit 1
fi

# Check if any database services are running
running_services=$(docker compose ps postgres redis weaviate --format json 2>/dev/null | grep -o '"State":"running"' | head -1 || echo "")

if [[ -z "$running_services" ]]; then
  echo "[info] No database services are currently running"
  exit 0
fi

echo "[info] Currently running services:"
docker compose ps postgres redis weaviate
echo ""

echo "[info] Stopping database services (volumes preserved)..."
docker compose stop postgres redis weaviate || {
  echo "[warn] docker compose stop failed, attempting docker compose down (volumes preserved)..."
  docker compose down
}

if [[ $? -ne 0 ]]; then
  echo "[error] Failed to stop services" >&2
  exit 1
fi

echo ""
echo "======================================="
echo "  ✅ Database services stopped"
echo "======================================="
echo ""

echo "[info] Data volumes preserved, data is safe"
echo "[info] Restart with: ./scripts/start-databases.sh"
echo ""
