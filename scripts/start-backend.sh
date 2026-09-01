#!/usr/bin/env bash
# CardLab — start backend (FastAPI)
# Usage: ./scripts/start-backend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="$ROOT/server"

echo "========================================"
echo "  CardLab - Backend Server"
echo "========================================"
echo

if ! command -v poetry >/dev/null 2>&1; then
  echo "[ERROR] Poetry not found. Install: pip install poetry" >&2
  exit 1
fi

mkdir -p "$ROOT/data/db" "$ROOT/data/games" "$ROOT/data/datasets"

cd "$SERVER"
echo "Installing dependencies..."
poetry install

echo
echo "Starting backend server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo

exec poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
