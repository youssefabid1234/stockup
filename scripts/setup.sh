#!/usr/bin/env bash
# Voice ERP kit — one-shot setup.
#   ./scripts/setup.sh           → Docker (recommended): builds and starts api + ai + web
#   ./scripts/setup.sh --local   → no Docker: uv (Python 3.12) + Node 22/pnpm for the frontend
# Safe to re-run. A team zip needs no option: its data is in ./data and .env says DATA_DIR=./data.
# Organisers only (full data pack next to the kit, not in team zips):
#   COMPANY=<slug> ./scripts/setup.sh   → use that company of the pack, writes DATA_DIR in .env
#   DATA_REPO=<git url>                 → clone the data pack if it is missing
#   DATA_RELEASE=<url prefix>           → download companies/<slug>.tar.gz if its seed is missing
#   GENERATE=1                          → regenerate the company locally from its recipe (needs Node 22)
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=docker; [[ "${1:-}" == "--local" ]] && MODE=local
DATA_REPO="${DATA_REPO:-}"   # e.g. git@github.com:<org>/hackathon-data.git
COMPANY="${COMPANY:-}"; DATA_RELEASE="${DATA_RELEASE:-}"; GENERATE="${GENERATE:-}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

bold "1. Configuration"
if [[ ! -f .env ]]; then cp .env.example .env; ok ".env created from .env.example (mock providers — add your keys later)"
else ok ".env already there (kept)"; fi
envval() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*$//'; }
DATA_DIR="$(envval DATA_DIR)"; DATA_DIR="${DATA_DIR:-../hackathon-data}"
WEB_PORT="$(envval WEB_PORT)"; WEB_PORT="${WEB_PORT:-5173}"
API_PORT="$(envval API_PORT)"; API_PORT="${API_PORT:-4000}"

setenv() {  # set KEY=VALUE in .env (replace or append)
  if grep -qE "^$1=" .env; then sed -i.bak "s#^$1=.*#$1=$2#" .env && rm -f .env.bak; else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
PACK_ROOT="${DATA_DIR%%/companies/*}"
if [[ -n "$COMPANY" ]]; then DATA_DIR="$PACK_ROOT/companies/$COMPANY"; setenv DATA_DIR "$DATA_DIR"; fi

bold "2. Data pack ($DATA_DIR)"
if [[ ! -d "$PACK_ROOT" ]]; then
  [[ -n "$DATA_REPO" ]] || fail "no data at $PACK_ROOT. Your team zip ships it in ./data: check the folder is there and .env says DATA_DIR=./data"
  git clone "$DATA_REPO" "$PACK_ROOT" && ok "data pack cloned"
fi
if [[ ! -f "$DATA_DIR/seed/meta.json" && -n "$COMPANY" ]]; then
  if [[ -n "$DATA_RELEASE" ]]; then
    echo "  downloading $COMPANY…"
    mkdir -p "$DATA_DIR" && curl -fsSL "$DATA_RELEASE/$COMPANY.tar.gz" | tar -xz -C "$DATA_DIR" && ok "downloaded"
  elif [[ -n "$GENERATE" ]]; then
    command -v node >/dev/null || fail "GENERATE=1 needs Node 22"
    echo "  generating $COMPANY (1–3 min)…"
    (cd "$PACK_ROOT" && npm install --silent && npx tsx engine/cli.ts generate --company "$COMPANY") && ok "generated"
  fi
fi
[[ -f "$DATA_DIR/seed/meta.json" ]] && ok "company: $(grep -o '"company": *"[^"]*"' "$DATA_DIR/seed/meta.json" | cut -d'"' -f4)" \
  || fail "no seed in $DATA_DIR (expected $DATA_DIR/seed/meta.json). Team zip: check DATA_DIR=./data in .env"

port_free() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

if [[ "$MODE" == docker ]]; then
  bold "3. Docker"
  command -v docker >/dev/null || fail "Docker not installed → https://docs.docker.com/get-docker/ (or run: ./scripts/setup.sh --local)"
  docker info >/dev/null 2>&1 || fail "Docker is installed but not running: start Docker Desktop"
  docker compose version >/dev/null 2>&1 || fail "docker compose v2 missing (update Docker)"
  ok "docker $(docker version --format '{{.Server.Version}}')"
  if ! docker compose ps --status running 2>/dev/null | grep -q api; then
    for p in "$WEB_PORT" "$API_PORT" "$(envval AI_PORT)"; do
      [[ -z "$p" ]] || port_free "$p" || fail "port $p is already used (another 'pnpm dev'?). Stop it or change the port in .env"
    done
  fi
  bold "4. Build & start (first build ≈ 2–4 min)"
  docker compose up -d --build
  printf '  waiting for the ERP'
  for _ in $(seq 1 90); do
    curl -fsS "http://localhost:$API_PORT/api/meta" >/dev/null 2>&1 && break; printf '.'; sleep 2
  done; echo
  curl -fsS "http://localhost:$API_PORT/api/meta" >/dev/null 2>&1 || fail "API not answering — see: docker compose logs api"
  ok "api, ai and web are up"
  echo
  bold "Ready → http://localhost:$WEB_PORT"
  echo "  API docs: http://localhost:$API_PORT/docs · http://localhost:$(envval AI_PORT || echo 4100)/docs"
  echo "  make logs · make reset · make down · make chat · make help"
else
  bold "3. Tools"
  command -v uv >/dev/null || { echo "  installing uv (Python package manager)…"; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
  ok "uv $(uv --version | cut -d' ' -f2)"
  command -v node >/dev/null || fail "Node 22+ required for the frontend → https://nodejs.org (or use Docker: ./scripts/setup.sh)"
  [[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 22 ]] || fail "Node $(node -v) is too old: need 22+"
  ok "node $(node -v)"
  if ! command -v pnpm >/dev/null; then corepack enable && corepack prepare pnpm@10.28.0 --activate; fi
  ok "pnpm $(pnpm -v)"
  bold "4. Install (Python 3.12 is fetched by uv if missing)"
  (cd apps/backend && uv sync)
  (cd apps/ai && uv sync)
  pnpm install
  bold "5. Start (Ctrl-C to stop) → http://localhost:$WEB_PORT"
  exec ./scripts/dev.sh
fi
