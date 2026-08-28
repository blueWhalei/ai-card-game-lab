#!/usr/bin/env bash
# AI Card Game Lab — E2E pipeline wrapper
# Usage:
#   ./scripts/e2e_pipeline.sh guide
#   ./scripts/e2e_pipeline.sh check
#   ./scripts/e2e_pipeline.sh all --count 1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="$ROOT/server"
CMD="${1:-guide}"
shift || true
cd "$SERVER"
exec poetry run python scripts/e2e_pipeline.py "$CMD" "$@"
