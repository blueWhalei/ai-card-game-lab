#!/usr/bin/env bash
# CardLab — start frontend (Vite)
# Usage: ./scripts/start-frontend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/web"

echo "========================================"
echo "  CardLab - Frontend Server"
echo "========================================"
echo

if ! command -v node >/dev/null 2>&1; then
  echo "[ERROR] Node.js not found. Please install Node.js first." >&2
  exit 1
fi

cd "$WEB"

if [[ ! -d node_modules ]]; then
  echo "Installing dependencies..."
  npm install
fi

echo
echo "Starting frontend server on http://localhost:5173"
echo "Press Ctrl+C to stop"
echo

exec npm run dev
