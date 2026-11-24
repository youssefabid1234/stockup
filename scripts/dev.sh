#!/usr/bin/env bash
# Run the three services locally (no Docker), with live reload. Ports come from the root .env.
#   backend → uvicorn :API_PORT   ai → uvicorn :AI_PORT   web → vite :WEB_PORT
set -euo pipefail
cd "$(dirname "$0")/.."
# Ports from .env (real env vars win). Not `source <(…)`: macOS's bash 3.2 silently reads nothing from it.
envval() { [[ -f .env ]] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | tr -d '[:space:]'; }
API_PORT="${API_PORT:-$(envval API_PORT || true)}"; API_PORT="${API_PORT:-4000}"
AI_PORT="${AI_PORT:-$(envval AI_PORT || true)}"; AI_PORT="${AI_PORT:-4100}"
exec pnpm exec concurrently -k -n backend,ai,web -c green,magenta,cyan \
  "uv run --directory apps/backend uvicorn app.main:app --reload --reload-dir app --timeout-graceful-shutdown 2 --port $API_PORT" \
  "uv run --directory apps/ai uvicorn app.main:app --reload --reload-dir app --timeout-graceful-shutdown 2 --port $AI_PORT" \
  "pnpm --filter @kit/web dev"
