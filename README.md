# Voice ERP kit

A small but complete ERP for a food wholesaler, an AI service that reads and writes it through tools, and a
push-to-talk voice harness. Built for the Stockline voice hackathon: make the voice agent **smart, fast and natural**.

**Install and run: [SETUP.md](SETUP.md)** (French, step by step: Mac, Windows/WSL, Linux, without Docker,
troubleshooting). **The challenge: [BRIEF.md](BRIEF.md)** (French). How the food wholesale trade works:
[METIER.md](METIER.md). How the ERP works (pages, business rules, API): [ERP.md](ERP.md). How everything works under the
hood and how to extend it: [TECH.md](TECH.md) (French). Using a coding agent? Point it at [AGENTS.md](AGENTS.md). This
README covers the architecture, the configuration and how to extend the kit.

### Quelle doc lire ?

| Doc | À lire quand… |
|---|---|
| [GLOSSAIRE.md](GLOSSAIRE.md) | un mot technique vous échappe (Docker, port, token, STT, WebSocket…) |
| [FAQ.md](FAQ.md) | vous avez une question pratique : où coder, comment tester, clés, coûts, livrables |
| [SETUP.md](SETUP.md) | vous installez et lancez le kit, ou quelque chose ne démarre pas |
| [BRIEF.md](BRIEF.md) | vous voulez savoir ce qu'on attend de vous : le défi, les livrables, le jury |
| [METIER.md](METIER.md) | vous ne connaissez pas le métier de grossiste alimentaire ou son vocabulaire |
| [ERP.md](ERP.md) | vous cherchez ce que fait l'ERP : pages, cycles de vie, règles métier, aide-mémoire de l'API |
| [TECH.md](TECH.md) | vous codez : comment marchent l'ERP, le service IA, les outils `@tool`, la voix et le web, et comment les étendre |
| [GUIDE-VOIX.md](GUIDE-VOIX.md) | vous voulez un agent vocal plus rapide et plus naturel : métriques, mesures du kit, techniques et où les brancher |
| [GUIDE-AGENTS.md](GUIDE-AGENTS.md) | vous découvrez les agents LLM, ou voulez rendre le vôtre plus smart, rapide et moins cher : concepts, où ils vivent dans le kit, conseils |
| [AGENTS.md](AGENTS.md) | vous donnez le projet à un agent de code (Claude Code, Cursor, Codex…) |
| [DESIGN.md](DESIGN.md) | vous modifiez l'interface web |

Everything runs offline out of the box: with the `mock` providers the LLM, speech-to-text and text-to-speech are
deterministic fakes that still call the real ERP. Add your keys when you are ready.

| Part | Path | Stack | Port |
|---|---|---|---|
| ERP backend | `apps/backend` | Python 3.12 · FastAPI · SQLite | 4000 |
| AI service (LLM / STT / TTS, agent, chat, voice) | `apps/ai` | Python 3.12 · FastAPI · httpx | 4100 |
| Web app | `apps/web` | React · Vite · Tailwind (TypeScript) | 5173 |
| Your company's data (seed, context docs) | `./data` (from your team zip, `DATA_DIR`) | JSON + Markdown | — |

In short: `make setup` the first time (Docker), `make up` / `make down` afterwards, `make local` / `make dev` without
Docker, `make restart` after editing `.env`, `make reset` to reload the ERP data, `make help` for every command.
Code changes reload live in both modes (uvicorn `--reload`, Vite HMR).

---

## Configuration: one `.env`

All three services read the single `.env` at the repo root (your team zip ships it; otherwise `make setup` copies
`.env.example`). Real environment variables win over the file. After a change: `make restart` (Docker) or restart
`make dev` (local). `GET localhost:4100/health` shows which providers are active. Never commit `.env` (it is git-ignored).

| Variable | Meaning |
|---|---|
| `DATA_DIR` | your company's data, relative to the repo root (`./data` in your team zip) |
| `WEB_PORT`, `API_PORT`, `AI_PORT` | ports on your machine (5173 / 4000 / 4100) |
| `ERP_API_URL` | where the AI service reaches the ERP in local mode (`http://localhost:4000`; Docker sets it itself) |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL` | `openai` · `anthropic` · `gemini` · `openai-compatible` (Groq, Mistral, OpenRouter, Ollama… via `LLM_BASE_URL`) · `mock` |
| `LLM_EFFORT` | Anthropic only: `low` (default, fastest) · `medium` · `high` |
| `STT_PROVIDER`, `STT_API_KEY`, `STT_MODEL`, `STT_LANGUAGE` | `soniox` · `deepgram` · `gradium` · `openai` · `mock` |
| `TTS_PROVIDER`, `TTS_API_KEY`, `TTS_MODEL`, `TTS_VOICE`, `TTS_LANGUAGE` | `elevenlabs` · `gradium` · `openai` · `mock` (the browser speaks the text) |
| `JEV_API_KEY`, `JEV_BASE_URL`, `JEV_MODEL` | optional Jev decision model (TypeSafe AI, `jev-latest`), used **next to** the LLM, not instead of it: choice / score / yes-no with probabilities. The default agent does not call it — see [apps/ai/README.md](apps/ai/README.md#jev-decision-model) |
| `AGENT_MAX_STEPS` | max model ↔ tool round-trips per turn (8) |
| `MOCK_STT_TEXT` | what the mock STT "hears", whatever you say (default "Bonjour, il vous reste du bar ?") |

An empty `*_MODEL` / `TTS_VOICE` picks the provider's default; the defaults are listed in
[apps/ai/README.md](apps/ai/README.md#environment). Your team `.env` lists every key your team received as comments at
the bottom: to switch provider, set `*_PROVIDER` and paste the matching key into `*_API_KEY`
([SETUP.md](SETUP.md#changer-de-modèle-ou-de-voix)).

---

## Architecture

```
                 HTTP /api/*  (x-actor: user)                   ┌─────────────────────────────────┐
   ┌──────────┐ ──────────────────────────────────────────────▶ │ apps/backend  :4000  FastAPI    │
   │ apps/web │ ◀──────────── SSE /api/events/stream ────────── │ routers → services → crud       │
   │  :5173   │                                                 │ SQLite + data pack              │
   │  React   │   POST /ai/chat (SSE) · /ai/command · WS /ai/voice └─────────────────────────────────┘
   │          │ ─────────────────────────────┐                                ▲
   └──────────┘                              ▼                                │ tools = HTTP /api/*
                                  ┌─────────────────────────────────┐         │ (x-actor: ai_chat | voice_agent)
                                  │ apps/ai  :4100  FastAPI         │ ────────┘
                                  │ STT → agent loop → TTS          │
                                  │ LLM ⇄ @tool functions           │ ──▶ LLM / STT / TTS providers (or mocks)
                                  └─────────────────────────────────┘
```

- The web app reaches both services through the Vite proxy (`/api` → backend, `/ai` → AI service).
- The AI service is just another ERP client: every tool is an HTTP call to the backend, so business rules live in one place.
- **The Python Pydantic schemas are the contract.** FastAPI publishes them at `/openapi.json`; `make types` generates
  the frontend's TypeScript types from them (`packages/shared/src/generated/`). Change a schema → `make types`.

### Backend (`apps/backend/app`)

| Folder | Role |
|---|---|
| `routers/` | thin FastAPI routers, one per resource (clients, orders, stock, pricing, context…) |
| `services/` | business rules: order lifecycle, FEFO stock reservation, price resolution, credit limits, invoicing, receivables, search |
| `crud/` | generic CRUD over the tables |
| `schemas/` | Pydantic models (camelCase JSON) = the API contract |
| `core/` | config, database, data pack loader, activity log (SSE) |
| `dependencies.py` | shared dependencies (the `x-actor` of each request…) |

### AI service (`apps/ai/app`)

| Folder | Role |
|---|---|
| `clients/` | abstract `LLMClient`, `STTClient`, `TTSClient` + one file per provider + `factory.py` (from `.env`) |
| `agent/` | `loop.py` (the agent loop) and `prompts.py` (rules per mode + company context + business date) |
| `tools/` | the functions the model can call, declared with `@tool` |
| `routers/` | `/chat`, `/command`, `/voice` (WebSocket), `/stt`, `/tts`, `/health`, `/tools` |
| `services/` | `voice_session.py` (push-to-talk, barge-in, sentence-by-sentence TTS, timings), `command.py` |
| `schemas/` | the wire contract (chat events, voice messages) |

Details, protocols and the agent loop: [`apps/ai/README.md`](apps/ai/README.md).

---

## The agent

One turn = **system prompt + conversation → model → (tools in parallel → model)* → answer**, streamed as events
(`text`, `tool_call`, `tool_result`, `done`). Three modes share it:

| Mode | Where | Style |
|---|---|---|
| `chat` | Assistant panel (⌘J) | short markdown answers |
| `voice` | **Voix** page, `WS /voice` | 1–2 spoken sentences, numbers said out loud |
| `command` | ⌥Space anywhere | acts immediately, one-line answer, can open a page |

### Add a tool

Write an async function with `@tool` in `apps/ai/app/tools/` — the signature becomes the JSON schema, the docstring
the description the model reads:

```python
@tool
async def list_overdue_invoices(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> list[dict]:
    """Factures en retard d'un client. Use when the caller asks what they owe or why they are blocked."""
    invoices = await ctx.erp.get("/api/invoices", {"clientId": client_id, "status": "overdue"})
    return [{"number": i["number"], "balance": i["balance"], "daysOverdue": i["daysOverdue"]} for i in invoices]
```

Then import it in `apps/ai/app/tools/__init__.py`. Return small JSON (the model re-reads it every step) and raise on
errors: the loop turns exceptions into `{"error": …}` so the model can explain or retry. If the ERP lacks an
endpoint, add the rule in `apps/backend/app/services/` and the route in `apps/backend/app/routers/`.

### Add a provider

Subclass `LLMClient` / `STTClient` / `TTSClient` from `apps/ai/app/clients/base.py`, then add one line to
`clients/factory.py`. The existing adapters are plain `httpx` calls — read `openai.py` to see streaming end to end.

---

## The data pack

Your team zip ships **your company** in `./data` (`DATA_DIR=./data`): one of 24 fictional food wholesalers
(fish, fruit & veg, meat, dairy, drinks, frozen…), each with ~100 clients, its suppliers and products and 3 years of
history. Every team has a different one.

- `data/seed/*.json`: the ERP data (clients, products, lots, orders, invoices, payments, routes, events, prices, context).
- `data/context/*.md`: company knowledge (playbooks, glossary, pricing, delivery zones) — put whole into the system
  prompt and re-read every turn, so you can edit it live. `data/context/clients/` and `data/context/suppliers/`: persona sheets.

The data is anchored on a fixed business day, `meta.today` (`GET /api/meta`): new records are stamped on that day and
the web app shows relative times on that clock, whatever your real date is.

### Context table

Every piece of business knowledge is also a row of the **context table**, attached to an entity:
`{ id, entityType: company|client|supplier|product|category, entityId, kind, title, body (markdown), tags, source }`.
`kind`: policy · procedure · preference · fact · relationship · pricing · logistics · risk. `source`: seed · user ·
ai_chat · voice_agent.

- **API**: `GET /api/context?entityType=&entityId=&kind=&q=`, `GET /api/context/for?entityType=client&id=cli_0001`
  (its entries + related ones), `POST/PATCH/DELETE /api/context…`.
- **Agent tools**: `get_context`, `search_context`, `save_context` (remember a fact learned during a call).
- **Web**: **Contexte** page, a "Ce que l'agent sait" block on client and supplier pages, a Contexte tab on each.

---

## Voice

- **Voix** page (`/voice`): hold **Space** to talk as the caller, release to send (or type). Shows the transcript,
  streamed answer, tool calls, per-turn timings (STT, first LLM token, first audio byte, total) and the ERP changes live.
  Talking while the agent speaks interrupts it.
- **⌥Space** anywhere: one-shot voice command ("crée une commande pour l'Écume, 5 kilos de bar").
- **Live transcription**: the audio is streamed to the STT while the key is down (Soniox, Deepgram; the mock simulates it),
  so the caller's words appear as they are spoken (grey italic = provisional) and the final text is ready right after the
  release. Client / product names from the ERP are sent as STT vocabulary. See TECH.md « Transcription en direct ».
- Protocol: `WS /voice` and `WS /voice/command` (proxied as `/ai/voice…`), documented in `apps/ai/README.md`. Script it with `{type:"text"}` turns.

## Activity stream

Every ERP write logs an event with its actor from the `x-actor` header (`user` · `ai_chat` · `voice_agent`).
`GET /api/events`, live at `GET /api/events/stream` (SSE). The **Activité** page shows them; rows the agent touches
flash violet in every open page — so the ERP visibly updates during a call.

---

## Where to start

- **Fast**: streaming STT with partial transcripts, start the LLM before the caller finishes, speak the first sentence
  while the rest is generated, parallel and speculative tool calls, a fast model for easy turns.
- **Smart**: load the caller's context at call start (client entries, usual basket, open issues), retrieval or a graph
  over the context table, composite tools, a dialogue state for orders, deterministic code for quantities and dates.
- **Natural**: short turns, barge-in, fillers while tools run, reading back orders, French numbers and units, noise.

## Troubleshooting

Install and run problems (Docker, ports, WSL, mic, keys): [SETUP.md](SETUP.md#en-cas-de-problème). While coding:

| Symptom | Fix |
|---|---|
| New dependency not found | `make rebuild` (Docker) or `uv sync` / `pnpm install` (local) |
| Frontend type errors after a schema change | `make types` |
| A provider error in the voice UI | it reads `<provider> HTTP <status>: …` with a hint (bad key, quota, audio format); `make logs` shows the rest |

Design system of the web app: [`DESIGN.md`](DESIGN.md).
