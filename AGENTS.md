# AGENTS.md — guide for coding agents

Read this first, then the files it points to. It applies to Claude Code, Cursor, Codex and any other coding agent.

## What this repo is

A hackathon kit: an ERP for a food wholesaler, an AI service with a voice agent, and a web UI. The team's goal is
to build the best voice agent on top of it (smart, fast, natural).

| Doc | Read it for |
|---|---|
| [SETUP.md](SETUP.md) | installing and running the project (Docker or local), troubleshooting |
| [GLOSSAIRE.md](GLOSSAIRE.md) | plain-French definitions of the tech terms (the team may have little software background: explain in these words) |
| [FAQ.md](FAQ.md) | the team's frequent questions (French): where to code, how to check a change, keys, cost, deliverables |
| [BRIEF.md](BRIEF.md) | the challenge, deliverables, judging |
| [METIER.md](METIER.md) | how food wholesale works, its vocabulary, and how each concept maps to the ERP |
| [ERP.md](ERP.md) | the ERP itself: pages, lifecycles, business rules (pricing, stock, credit), data model, agent tools, API cheat-sheet |
| [README.md](README.md) | architecture, configuration (`.env`), how to add a tool or a provider |
| [TECH.md](TECH.md) | the detailed technical guide (French): request flows, backend layering, every endpoint, agent loop, `@tool` internals, frontend data flow, known pitfalls, worked extension examples |
| [GUIDE-AGENTS.md](GUIDE-AGENTS.md) | the teaching guide (French): agent concepts (loop, harness, tools, context, prompt caching, models, Jev, evaluation, pitfalls) mapped to the kit's code |
| [apps/ai/README.md](apps/ai/README.md) | the agent loop, tools, providers, the voice WebSocket protocol |
| [GUIDE-VOIX.md](GUIDE-VOIX.md) | voice-agent guide (French): latency metrics, the kit's measured numbers, speed and naturalness techniques mapped to the files to change |
| [DESIGN.md](DESIGN.md) | the web design system (only when touching `apps/web`) |

## Layout

| Path | Stack | Port | Role |
|---|---|---|---|
| `apps/backend` | Python 3.12, FastAPI, SQLite | 4000 | ERP API. `routers/` (thin) → `services/` (business rules) → `crud/`; `schemas/` = Pydantic contract |
| `apps/ai` | Python 3.12, FastAPI, httpx | 4100 | `clients/` (LLM/STT/TTS adapters + factory), `agent/` (loop + prompts), `tools/` (`@tool`), `routers/`, `services/` (voice session, command) |
| `apps/web` | React, Vite, Tailwind, TypeScript | 5173 | UI; talks to both services through the Vite proxy (`/api`, `/ai`) |
| `packages/shared` | TypeScript | — | the frontend's types for both APIs |
| `./data` (`DATA_DIR`) | JSON + Markdown | — | the team's company (from the team zip): seed data (`data/seed`), context docs (`data/context`); `data/seed` is git-ignored |

## Commands

- First run: `make setup` (Docker) or `make local` (no Docker). Then `make up` / `make dev`. Logs: `make logs`. Stop: `make down`.
- After editing `.env`: `make restart` (Docker) or restart `make dev`. After adding a dependency: `make rebuild`.
- Reset the ERP data to the seed: `make reset` (`POST /api/admin/reset`).
- Talk to the agent in a terminal: `make chat`.
- Python tests: `make test` (= `cd apps/ai && uv run pytest`, needs uv on the host). Backend parity tool: `apps/backend/tests/parity.py`.
- Frontend check: `make check` (typecheck + `./scripts/check-no-native-controls.sh`; needs Node 22 + pnpm on the host).
- API docs: http://localhost:4000/docs and http://localhost:4100/docs (`/openapi.json` for the schemas).
- Config: one `.env` at the repo root (see `.env.example`). `*_PROVIDER=mock` = offline fakes (the mock STT always
  hears `MOCK_STT_TEXT`). Never commit keys, never print them.

## Rules

- **Business rules live in the backend** (`apps/backend/app/services/`). The AI service and the web call the API;
  they never reimplement pricing, stock or credit logic.
- **The agent acts through tools only.** A new capability = a backend route (if missing) + an `@tool` function in
  `apps/ai/app/tools/` imported in `tools/__init__.py`. Return small JSON; raise on error.
- **Every ERP write carries an actor**: the `x-actor` header (`user` | `ai_chat` | `voice_agent`). Tools send it
  through `ctx.erp`; keep it so the UI shows agent actions live.
- **JSON is camelCase** on the wire; Python code is snake_case (Pydantic aliases handle it).
- **Changing an API response or request shape**: update the Pydantic schema, then the matching TypeScript type in
  `packages/shared/src/` (or regenerate with `make types` while the services run) so the web keeps compiling.
- **Business date**: the data is anchored on `meta.today` (`GET /api/meta`), not the real date. Use it for any
  "today", "tomorrow" or "late" logic.
- **Context**: business knowledge is in the context table (`/api/context`, rows linked by `entityType` +
  `entityId`) and in `DATA_DIR/context/*.md`. Read it before inventing business rules.
- **Web UI**: use the components in `apps/web/src/ui/` only; never a native `<select>` or `<input type="date">`.
- **Data is fictional.** Don't add real companies, people or personal data.

## Typical tasks

| Task | Where |
|---|---|
| Lower voice latency | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/*` (streaming), `agent/loop.py` |
| Make the agent smarter about a client | `agent/prompts.py` (what goes in the prompt), `tools/context.py`, `/api/context/for` |
| Add a business action (e.g. book a delivery slot) | `apps/backend/app/services/` + `routers/`, then a tool in `apps/ai/app/tools/` |
| Swap the model or voice provider | `.env` (see README "Configuration"); new provider = subclass of a class in `apps/ai/app/clients/base.py` + a `case` in `factory.py` |
| Use Jev for a fast decision (which product, yes/no) | `get_jev_client()` in `apps/ai/app/clients/`, examples in `agent/jev_examples.py`; needs `JEV_API_KEY` |
| Show something new in the UI | `apps/web/src/pages/`, components from `apps/web/src/ui/` |
