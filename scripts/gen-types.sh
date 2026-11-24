#!/usr/bin/env bash
# Regenerate the frontend's TypeScript types from the Python services' OpenAPI schemas.
# The Python Pydantic schemas are the source of truth; run this after changing them (services must be running).
set -euo pipefail
cd "$(dirname "$0")/.."
API="http://localhost:${API_PORT:-4000}"; AI="http://localhost:${AI_PORT:-4100}"
OUT=packages/shared/src/generated
mkdir -p "$OUT"
pnpm exec openapi-typescript "$API/openapi.json" -o "$OUT/backend.ts"
pnpm exec openapi-typescript "$AI/openapi.json" -o "$OUT/ai.ts"
echo "types written to $OUT/"
