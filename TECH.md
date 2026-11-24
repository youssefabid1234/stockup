# TECH.md — the kit's technical guide

How **tout** works, and how to extend it. For engineers and their code agents. Each name, path and
route quoted here exists in the code; the `fichier:ligne` references point to the extracts.

What this guide does not repeat: installation ([SETUP.md](SETUP.md)), challenge ([BRIEF.md](BRIEF.md)), job
([METIER.md](METIER.md)), the functional functioning of the ERP, its pages and its rules ([ERP.md](ERP.md)), the
Summary configuration ([README.md](README.md)), rules for code agents ([AGENTS.md](AGENTS.md)), design
system ([DESIGN.md](DESIGN.md)), the summary of service AI ([apps/ai/README.md](apps/ai/README.md)).

## Contents

1. [Overview: 3 services, 4 route](#vue-ensemble)
2. [Backend ERP](#backend)
3. [Reference to endpoints](#endpoints)
4. [Service AI](#service-ia)
5. [Tools (`@tool`) in detail](#outils)
6. [Frontend](#frontend)
7. [Data](#donnees)
8. [Tests and quality](#tests)
9. [Known traps and limits](#pieges)

## I want... → where to watch

| I want... | Section | Files |
|---|---|---|
| understand a voice call from end to end | [1.3](#parcours-voix) | `apps/web/src/features/assistant/useVoiceSession.ts`, `apps/ai/app/services/voice_session.py`, `apps/ai/app/agent/loop.py` |
| add tool to agent | [5](#outils) | `apps/ai/app/tools/registry.py`, `apps/ai/app/tools/*.py`, `apps/ai/app/tools/__init__.py` |
| add a composite tool (several calls ERP) | [5.4](#outil-composite) | `apps/ai/app/tools/catalog.py` (model), `apps/ai/app/tools/erp.py` |
| change model, STT or TTS | [4.1](#config-ia) | `.env`, `apps/ai/app/clients/factory.py` |
| add a supplier LLM / STT / TTS | [4.2](#clients) | `apps/ai/app/clients/base.py`, `apps/ai/app/clients/factory.py` |
| transcribe while the caller speaks | [Online transcript](#stt-direct) | `apps/ai/app/services/utterance.py`, `apps/ai/app/services/vocabulary.py`, `apps/ai/app/clients/soniox.py` |
| reduce latency | [4.5](#latence), [9](#pieges) | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/*`, `apps/ai/app/agent/prompts.py`, `apps/ai/app/tools/erp.py` |
| changing what the model reads (prompt) | [4.3](#prompts) | `apps/ai/app/agent/prompts.py`, `DATA_DIR/context/*.md` |
| modify the agent loop | [4.4](#boucle) | `apps/ai/app/agent/loop.py` |
| add an endpoint to the ERP | [2.6](#ajouter-endpoint) | `apps/backend/app/schemas/inputs.py`, `services/`, `routers/`, `packages/shared/src/`, `apps/web/src/lib/api.ts` |
| changing a business rule (price, stock, credit) | [2](#backend) | `apps/backend/app/services/*.py` |
| modify or add a page | [6.6](#ajouter-page) | `apps/web/src/pages/`, `apps/web/src/app/routes.tsx`, `apps/web/src/app/nav.ts` |
| that the UI will update when the agent writes | [6.4](#live) | `apps/web/src/lib/queries.ts` (`INVALIDATE`) |
| edit the chat, the Voice or Space page | [6.5](#surfaces-ia) | `apps/web/src/features/assistant/`, `apps/web/src/features/voice-command/`, `apps/web/src/pages/voice/` |
| test a tool without the UI | [8](#tester-sans-ui) | `make chat`, `curl /chat`, `apps/ai/tests/` |
| reset data to zero | [7](#donnees) | `make reset` → `apps/backend/app/core/datapack.py` |
| use Jev (fast decisions) | [4.7](#jev) | `apps/ai/app/clients/jev.py`, `apps/ai/app/agent/jev_examples.py` |

Each section follows the same plan: **What it is** (2–3 lines), **Key files**, **How it works**,
**Strength**, **Strength**.

---

<a id="view-all"></a>
## 1. Overview: 3 services, 4 route

### What it is

Three processes: the ERP (`apps/backend`, port 4000), the AI service (`apps/ai`, port 4100) and the web (`apps/web`,
port 5173). The service IA is **a customer HTTP of l'ERP like another** : The European Union is a member of the European Union.'ERP.

### Key Files

- `docker-compose.yml`: 3 services, volumes (live-mounted code, `DATA_DIR` read-only, base in volume `erp-db`).
- `scripts/dev.sh`: the same thing without Docker (`uvicorn --reload` ×2 + `vite`).
- `apps/web/vite.config.ts:24-29`: the proxy `/api` → ERP, `/ai` → AI, `/ai/voice` → WebSocket AI.
- `Makefile`: All commands (`make help`).

### How it works

```
 navigateur :5173 (React)
   │  /api/*  (fetch, x-actor: user)            ┌──────────────────────────────────────┐
   ├──────────────────────────────────────────▶ │ ERP  apps/backend  :4000             │
   │  /api/events/stream (SSE, ActivityEvent) ◀─┤ routers → services → crud → db       │
   │                                            │ mémoire + SQLite (write-through)     │
   │  /ai/chat (SSE)   /ai/command (SSE)        └──────────────────────────────────────┘
   │  /ai/voice (WebSocket)                                   ▲ HTTP /api/*
   ▼                                                          │ x-actor: ai_chat | voice_agent
 ┌─────────────────────────────────────────┐                  │
 │ IA  apps/ai  :4100                      │──────────────────┘ (chaque outil = 1+ appel HTTP)
 │ routers → services → agent/loop → tools │
 │ clients/ : LLM · STT · TTS · Jev        │────▶ fournisseurs (OpenAI, Anthropic, Gemini,
 └─────────────────────────────────────────┘      Soniox, Deepgram, ElevenLabs, Gradium) ou mocks
```

Ports and URL: `WEB_PORT`, `API_PORT`, `AI_PORT` in `.env`. In Docker, the AI joins the ERP in
`http://backend:4000` and Rapid proxifies to `backend` / `ai` (`VITE_API_TARGET`, `VITE_AI_TARGET`).
`ERP_API_URL=http://localhost:4000`.

<a id="terminal-click"></a>
#### 1.1 A click in the UI (e.g. "Confirm" a command)

```
Bouton → useApiMutation(api.orders.confirm)            apps/web/src/lib/queries.ts:205
  → fetch POST /api/orders/{id}/confirm                 apps/web/src/lib/api.ts:47 (x-actor: user, x-actor-name: Moi)
  → Vite proxy → ERP router confirm_order               apps/backend/app/routers/orders.py:58
  → get_ctx() lit x-actor → Ctx(actor="user")           apps/backend/app/dependencies.py:20
  → services.orders.confirm_order (@transactional)      apps/backend/app/services/orders.py:273
      crud.orders.put(...)  → mémoire + SQLite
      log_event(ctx, "order.confirmed", …)              apps/backend/app/core/activity.py:71
  → COMMIT → bus.publish(ev) → SSE "activity" à tous les onglets
  → réponse OrderDetail (avec warnings) → toast + invalidations react-query
```

<a id="terminal-chat"></a>
#### 1.2 A message in the assistant (的J)

```
chat.send(text)                                       apps/web/src/features/assistant/chat-store.ts:67
  → POST /ai/chat {messages: historique complet + nouveau, mode:"chat"}   ai-client.ts:38
  → routers/chat.py:16 → run_agent(messages, mode="chat")                 apps/ai/app/agent/loop.py:41
      build_system_prompt("chat")  (règles + date métier + DATA_DIR/context/*.md)
      LLM.stream → text… / tool_call…
      outils en parallèle → ErpClient("ai_chat") → /api/*                 apps/ai/app/tools/erp.py:44
      … jusqu'à une réponse sans appel d'outil (max AGENT_MAX_STEPS=8)
  ← SSE : text · tool_call · tool_result · done | error   (une ligne data: JSON par événement)
  → TurnRecorder reconstruit les messages assistant/tool  ai-client.ts:82
  → l'historique reste côté navigateur et est renvoyé en entier au tour suivant
```

<a id="terminal-voice"></a>
#### 1.3 A push-to-talk vocal tower (Voice page) from end to end

```
NAVIGATEUR (useVoiceSession.ts)                SERVICE IA (voice_session.py)                         ERP
ws = new WebSocket(/ai/voice)          :192
onopen → {type:"start", sessionId, actorName:"Agent vocal"} ──▶ open() → ReadyMessage {sessionId, stt, tts, llm}
Espace enfoncé:
  MediaRecorder(webm/opus).start(100)
  {type:"audio_start", mime}           ──▶ interrupt() (barge-in), recording = Utterance(...)  → flux STT ouvert
  frames binaires toutes les 100 ms    ──▶ utterance.feed(frame) → envoyée au STT tout de suite
                                      ◀── transcript {final:false, text, stable}  (texte en direct, gris/italique)
Espace relâché:
  {type:"audio_end"}                   ──▶ start_turn(utterance) → asyncio.Task run_turn()
                                           1. STT: await utterance.text()  (finalize : seuls les derniers mots)
                                      ◀── transcript {track:"caller", text, final:true}
                                           2. run_agent(working, mode="voice")                   :190
                                      ◀── agent_text {delta}  (chaque delta)
                                           Speaker.push(delta) → phrase finie ? → file TTS        :241
                                      ◀── agent_tool {name, args}   …outil → HTTP ──────────────▶ /api/*
                                      ◀── agent_tool {name, ok, ms}                 ◀── JSON ── (log_event → SSE)
                                           worker TTS : synthesize(phrase) en streaming          :273
                                      ◀── agent_audio_start {mime}  (une fois par tour)
                                      ◀── octets audio mp3 (binaire), phrase après phrase
                                           3. speaker.finish() → reste du buffer                 :208
                                      ◀── agent_audio_end
                                      ◀── agent_done {text, timings}
SegmentPlayer (MediaSource) joue le mp3 dès le premier octet ; mime mock → speechSynthesis fr-FR
En parallèle, l'onglet reçoit les ActivityEvent par /api/events/stream → colonne de droite, lignes violettes.
```

`timings` (`apps/ai/app/schemas/chat.py:55`) : `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`,
`totalMs` = end of speech → first audio byte of the agent. The browser adds `perceivedMs` (release → audio played).

**Barge-in**: a new `audio_start` or `text` during a round calls `interrupt()`
(`voice_session.py:158`): the task is cancelled, the current TTS is closed (`aclosing`), which has been heard and
said is kept in history with "...".

<a id="terminal-command"></a>
#### 1.4 One command, Space

```
⌥Espace maintenu (VoiceCommand.tsx:28) → MediaRecorder (trames de 100 ms) → WS /ai/voice/command?speak=1
  ← transcript {final:false} pendant la parole (texte en direct dans le HUD) → relâché → audio_end
  (commande tapée : POST /ai/command?speak=1, JSON {text}, réponse en SSE)
  → services/command.py:73 run_command
      STT → TranscriptEvent
      run_agent([un seul message user], mode="command")   (aucun historique)
      ToolResultEvent → entity_of(result) mémorise la dernière entité vue
      si la phrase contient montre/affiche/ouvre/voir… → NavigateEvent {path:"/products/prd_…"}   :40, :121
      speak=1 → TTS de toute la réponse → SpeechEvent (base64)
      DoneEvent {timings}
  ← SSE : transcript · text · tool_call · tool_result · navigate? · speech? · done | error
  → le web navigue (sauf sur /voice) et joue l'audio
```

<a id="activite"></a>
#### 1.5 Business Flow and `x-actor`

- Each ERP write calls `log_event(ctx, type, entity, entity_id, summary)` in the service
  (`core/activity.py:71`). The event is published on the ** bus after the COMMIT** (`on_commit`, `core/db.py:153`).
- `GET /api/events/stream` (`routers/system.py:54`): `event: ready` once, then `event: activity` + JSON by
  Writing, `event: ping` every 15 s.
- The actor comes from the header `x-actor` (`user` | `ai_chat` | `voice_agent`, if not `user`) and optional name
  `x-actor-name` (URI-encoded): `dependencies.py:20-26`. The web sends `user`/"Me"; the tools of the AI send
  `ai_chat` (cat mode) or `voice_agent` (voice mode and command mode): `agent/loop.py:51-52`.
- On the web side, `useActivityStream()` (mounted once in `AppShell`) invalidates the requests of the affected entity and
  flashes the line in purple (`lib/queries.ts:259-299`).

### Traps

- The AI service does not have a database: everything it "knows" comes from the ERP or the prompt.
- The agent's writings are **pas** cancelled by a barge-in: a HTTP call already left remains.

---

<a id="backend"></a>
## 2. Backend ERP (`apps/backend/app`)

### What it is

A API FastAPI JSON in `/api`. Data are JSON (camelCase) documents stored and written in
same time in SQLite. Business rules are in `services/`.

### Key Files

| File | Role |
|---|---|
| `main.py` | FastAPI app, boot loading (`lifespan`, `:44`), router list (`:72`), error format (`:97-154`), Clean OpenAPI (`:160-196`) |
| `dependencies.py` | `get_ctx` / `CtxDep` (actor), `data(body)`, `iso_date_query`, `ERROR_RESPONSES` |
| `core/listing.py` | Paginated lists: `ListDep` (`limit`, `offset`, `sort`, `order`, `envelope`), `apply_sort`, `respond`, `Page[T]` ([Pagination](#pagination)) |
| `core/config.py` | `DATA_DIR`, `SEED_DIR`, `DB_PATH`, `API_PORT` (bed the `.env` root) |
| `core/db.py` | `JsonTable`, `transaction()` / `@transactional`, `on_commit`, `get_meta`, id sequences, `@per_data_version` (cache of aggregates invalidated each writing) |
| `core/datapack.py` | read pack (`DATA_DIR/seed/*.json`), `reset_from_pack()` |
| `core/activity.py` | `Ctx`, `today()` / `now()` (business clock), `EventBus`, `log_event`, `list_events` |
| `core/errors.py` | `HttpError`, `not_found`, `bad_request`, `conflict`, `validation_error` |
| `crud/__init__.py`, `crud/base.py` | one `CRUDBase` per table (`crud.orders`, `crud.clients`...), `PACK` (file saw → table) |
| `schemas/domain.py` · `views.py` · `inputs.py` | stored entities · calculated responses · request body |
| `routers/*.py` | thin roads, one per resource |
| `services/*.py` | trade rules, one by field |

### How it works

**** Layers — Each layer calls only the layer below:

```
routers/orders.py      parse la requête (Query alias camelCase, body Input), injecte ctx: CtxDep, déclare response_model
   ↓
services/orders.py     règles métier, @transactional, log_event(...) ; renvoie des dicts (Doc)
   ↓
crud (crud.orders)     get / require (404) / all / filter / put / delete / next_id / next_number
   ↓
core/db.py JsonTable   rows: dict en mémoire  +  SQLite (id TEXT PRIMARY KEY, data TEXT JSON)
```

Actual example, command creation:

```python
# apps/backend/app/routers/orders.py:31-34
@router.post("", response_model=OrderDetail, status_code=201)
async def create_order(body: OrderInput, ctx: CtxDep):
    """Draft order; line prices resolved (client price > rules > list price)."""
    return orders.create_order(ctx, body.data())
```

```python
# apps/backend/app/services/orders.py:181-201 (extrait)
@transactional
def create_order(ctx: Ctx, input: Doc) -> Doc:
    client = crud.clients.require(input["clientId"])
    t = today()
    order = {
        "id": crud.orders.next_id("ord_"),
        "number": crud.orders.next_number("CMD", t[:4]),
        ...
    }
    saved = _save(order)
    log_event(ctx, "order.created", "order", order["id"], f"Commande {order['number']} créée pour …")
    return order_detail(saved["id"])
```

**Memory Tables + SQLite write-through** (`core/db.py:36-68`). On startup, `lifespan` (`main.py:44`) load
all tables (`load_all`) or, if the database is empty, the data pack (`reset_from_pack`). All readings
touch memory; `put` / `remove` write in memory ** and ** in SQLite. Base: `apps/backend/data/erp.db`
in local, `/db/erp.db` (volume `erp-db`) in Docker.

**`@transactional`** (`core/db.py:117-150`): the function rotates in a SQLite transaction; interlocked blocks
join the most external. In case of exception: `ROLLBACK` ** and ** reloading memory from disk
(`load_all`), so that the two never diverge. `on_commit` callbacks (broadcast SSE) only start at
COMMIT. Any service function that writes takes `ctx` first and carries `@transactional`.

**Ids and numbers**: `crud.X.next_id("ord_")` → `ord_000124` (exceeds the largest existing);
`next_number("CMD", "2026")` → `CMD-2026-000124` (`crud/base.py:62-74`). Line ids (`lin_…`, `pol_…`) are
random.

**Trade watch** (`core/activity.py:33-41`): `today()` = `meta.today` of the pack, never `date.today()`;
`now()` = that day + the actual time. All "late", "tomorrow", "30 last days" is calculated on it.

**Schemas** (`schemas/base.py`): `Schema` serialis in camelCase without `None`; `Input` (body of
query) is **strict** (no `"5"` → 5) and ignores unknown keys; `body.data()` → dict camelCase for the
service. Services handle camelCase dictations, not Pydantic objects.

**Errors**: always `{"error": {"code", "message"}}`.

| Cases | Status | `code` | From which |
|---|---|---|---|
| Invalid body (Pydantic) | 400 | `validation_error` (`"champ: message; …"`) or `invalid_json` | `main.py:132` |
| business rule (`bad_request`) | 400 | choice, e.g. `product_inactive`, `invalid_qty` | `core/errors.py:17` |
| entity absent (`crud.X.require`) | 404 | `not_found` ("Order not found: ord_1") | `crud/base.py:43` |
| unknown road / wrong method | 404 | `not_found` | `main.py:144` |
| transition prohibited (`conflict`) | 409 | e.g. `empty_order`, `invalid_transition` | `core/errors.py:21` |
| exception not provided | 500 | `internal_error` | `main.py:151` |

**Data pack and reset**: `make reset` = `POST /api/admin/reset` (`routers/system.py:80`) → `reset_from_pack()`
(`core/datapack.py:49`): clears all tables and journal, reloads `DATA_DIR/seed/*.json`, emptys the sequences.
Without `DATA_DIR/seed/meta.json`, a small integrated fixture (`core/dev_fixture.json`) is loaded.

<a id="add-endpoint"></a>
### Expand: add an endpoint from end to end (2.6)

Example worked: **"redo the same command"** (`POST /api/orders/{id}/repeat`), useful on the phone
("as the last time").

1. **Input scheme** — `apps/backend/app/schemas/inputs.py` (near `OrderPatch`):

   ```python
   class RepeatOrderInput(Input):
       delivery_date: IsoDateStr | None = None  # défaut : prochain jour de livraison du client
   ```

   If the answer has a new form, add a model in `schemas/views.py`; here `OrderDetail` is reused.

2. **Service** — `apps/backend/app/services/orders.py` (reuse `create_order`, which recalculates daily prices,
   Log `order.created` and join the transaction):

   ```python
   @transactional
   def repeat_order(ctx: Ctx, id: str, input: Doc) -> Doc:
       src = crud.orders.require(id)
       lines = [
           {"productId": l["productId"], "qty": l["qty"], **({"note": l["note"]} if l.get("note") else {})}
           for l in src["lines"]
       ]
       return create_order(ctx, {
           "clientId": src["clientId"],
           "deliveryDate": input.get("deliveryDate"),
           "lines": lines,
           "note": f"Reprise de {src['number']}",
       })
   ```

3. **Route** — `apps/backend/app/routers/orders.py` (import `RepeatOrderInput`):

   ```python
   @router.post("/{id}/repeat", response_model=OrderDetail, status_code=201)
   async def repeat_order(id: str, ctx: CtxDep, body: RepeatOrderInput | None = None):
       """New draft with the same lines as order `id` (prices resolved today)."""
       return orders.repeat_order(ctx, id, data(body))
   ```

   A new router file must be added to the `main.py:72-91` list.

4. **Check**: uvicorn recharges alone. `curl -s -X POST localhost:4000/api/orders/ord_000001/repeat -H 'content-type: application/json' -H 'x-actor: voice_agent' -d '{}'`,
   then http://localhost:4000/docs. The line appears in purple in **Activity**.

5. **Type TypeScript** — web types are ** handwritten** in `packages/shared/src/`
   (`domain.ts`, `api.ts`, `ai.ts`). New body or new response → add the corresponding interface
   (here nothing: `OrderDetail` exists). `make types` also generates `packages/shared/src/generated/` since
   `/openapi.json`, but this folder is not exported by `index.ts`: it serves as a reference (see [Pièges](#pieges)).

6. **Web call** — `apps/web/src/lib/api.ts`, object `orders` (`:137`):

   ```ts
   repeat: (id: Id, body?: { deliveryDate?: IsoDate }) => post<OrderDetail>(`/orders/${id}/repeat`, body),
   ```

   then in a page: `useApiMutation(api.orders.repeat, { success: "Commande dupliquée", invalidate: [qk.orders.all] })`.

7. **Tool for ** agent (optional): see [5.3](#ajouter-outil).

### Traps

- One process: the memory database is not shared between workers. Do not run uvicorn with `--workers`.
- Change `erp.db` by hand while ERP turns the memory out of sync: restart the backend.
- The routes are `async` but the services are synchronous: a long calculation blocks the entire API (including the SSE).
- Do not forget `log_event` in a service that writes: without it, the UI does not update itself live.
- The query parameters arrive in `str` and are converted in the router (`int_param`, `js_number`); lists =
  chains separated by commas (`status=draft,confirmed`). `limit` / `offset` / `sort` / `order` / `envelope`:
  add `lq: ListDep` to the road and return `respond(rows, lq, view, extras)` ([Pagination](#pagination)).
- A new list must never build views of all lines: filter → sort → `respond` (which cuts
  The page then calls `view`). An aggregate on the entire table? `@per_data_version` (never mutate the value into cache).

---

<a id="endpoints"></a>
## 3. Endpoint Reference

### What it is

80 routes of the ERP (generated from `http://localhost:4000/openapi.json`) and 7 routes of the AI service.
Live Testing: http://localhost:4000/docs and http://localhost:4100/docs. Examples Curl and Semantic Profession:
[ERP.md §7 and §8](ERP.md#8-aide-mémoire-de-lapi).

### Key Files

`apps/backend/app/routers/*.py`, `apps/ai/app/routers/*.py`, `apps/ai/app/schemas/*.py`.

### How it works: ERP (`/api`, port 4000)

All scripts accept `x-actor` and `x-actor-name`. Answer = model of `schemas/views.py` or `domain.py`.

<a id="pagination"></a>
**Pagination.** All lists are paginated, filtered and sorted ** side server** (`app/core/listing.py`), as the
Data packs range up to ~48 000 orders, ~25 000 invoices and ~420 000 stock movements per company.
Common parameters (marked "+list" below): `limit` (default **100**, max **500**), `offset` (default 0),
`sort` (a triable road field, listed in its description `/docs` and in `packages/shared/src/api.ts`),
`order` (`asc` | `desc`). Response format :

- **by default, an array JSON** (the requested page): AI tools and existing scripts work without change,
  but an array is ** truncated to `limit`** — pass `limit=500` or `envelope=1` to know how many lines exist;
- **with `envelope=1`** (as sent by UI): `{items, total, limit, offset, …extras}` — `total` = lines that
  match the filters, and extras calculated on **tout** the filtered set (not only the page): `counts`
  (lines by status / tab / category **en ignoring this filter** → tab badges), `sums` (totals of the foot of
  table), `sumsByStatus` (invoices), `countsByType` (historical), `countsBySource` (context), `facets` (options
  Type TS: `Page<T>` in `packages/shared/src/api.ts`.

On the service side: we filter raw documents, sort with a simple key, cut the page, and **only then**
the views (`order_summary`, `invoice_summary`...) of the lines of the page are constructed.
stock, stock by customer, pre-sorted lists, index FEFO, dashboard) are cached by **data version**
(`@per_data_version` in `core/db.py`, invalidated each writing); stock movements (add only) have an index
web side: `useServerList` (page + sorting in URL) → hook `use…Page` → `<DataTable server={{ list, total }}>`
with columns `sortKey` (see `pages/clients/index.tsx`, the reference page). Exceptions bounded by nature, not
paginated: `GET /api/receivables` (one line per customer), `/api/prices/grid` (one line per product), `/api/tags`.

**System** (`routers/system.py`)

| Method | Path | Role | Parameters | Answer |
|---|---|---|---|---|
| GET | `/api/health` | live + business date | — | `Health` |
| GET | `/api/meta` | company, `today`, `trade`, `region` (side bar) | — | `Meta` |
| GET | `/api/categories` | product categories of the company (`seed/categories.json`) | — | `Category[]` (`{id, label}`) |
| GET | `/api/dashboard` | Host KPI | — | `Dashboard` |
| GET | `/api/search` | blurred search (accents, aliases, parasitic words) | `q`, `types`, `limit` (default 20, max 500) | `SearchResult[]` |
| GET | `/api/events` | activity journal, recent first | `actor` (`ai`, `user,system`...), `entity` + list (default `limit` 50); envelope: `counts` {ai, user} | `ActivityEvent[]` |
| GET | `/api/events/stream` | Live journal (SSE) | — | `text/event-stream` |
| POST | `/api/admin/reset` | recharge the data pack | — | `Ok` |

**Clients** (`routers/clients.py`, `routers/client_events.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/clients` | list with KPI | `q`, `type`, `zone`, `status`, `tag` + list; sort `name` `code` `type` `tags` `zone` `rep` `city` `outstanding` `overdue` `last` `revenue30d` `status`; envelope: `counts` by status, `facets.zone`, `facets.salesRep` | `ClientSummary[]` |
| POST | `/api/clients` | create | `ClientInput` | `Client` (201) |
| GET | `/api/clients/{id}` | full sheet (20 latest orders, ≤ 100 Open invoices + `openInvoiceCount`) | — | `ClientDetail` |
| PATCH | `/api/clients/{id}` | modify | `ClientPatch` | `Client` |
| GET | `/api/clients/{id}/usual` | usual basket (60 j) | — | `UsualBasketLine[]` |
| GET | `/api/clients/{id}/events` | client history, recent first (`sort=open`: files opened first) | `type`, `status`, `q` + list | `ClientEventSummary[]` |
| POST | `/api/clients/{id}/events` | add an event | `ClientEventInput` | `ClientEvent` (201) |
| PUT | `/api/clients/{id}/prices/{product_id}` | fixing a negotiated price | `ClientPriceInput` | `ClientPrice` |
| DELETE | `/api/clients/{id}/prices/{product_id}` | withdraw the negotiated price | — | `Ok` |
| POST | `/api/clients/{id}/notes` | add a note | `ClientNoteInput` | `Client` (201) |
| GET | `/api/client-events` | historical all customers | `type`, `status`, `clientId`, `q`, `from`, `to` + list; envelope: `counts` by status, `countsByType`, `sums.amount` | `ClientEventSummary[]` |
| PATCH | `/api/client-events/{id}` | modify, resolve | `ClientEventPatch` | `ClientEvent` |

**Catalogue, suppliers, stock** (`routers/products.py`, `suppliers.py`, `supplier_events.py`, `stock.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/products` | catalogue with stock | `q`, `category`, `tag`, `active` + list; sort `name` `sku` `category` `tags` `price` `cost` `margin` `available` `expiry`; envelope: `counts` by category | `ProductSummary[]` |
| GET | `/api/products/{id}` | sheet, lots, supplier prices, movements, sales 30 j | — | `ProductDetail` |
| PATCH | `/api/products/{id}` | price, cost, tags... | `ProductPatch` | `Product` |
| GET | `/api/products/{id}/alternatives` | replacements in stock | — | `ProductSummary[]` |
| GET | `/api/suppliers` | list | `q`, `category`, `tag` + list; sort `name` `city` `tags` `lead` `terms` `min` | `Supplier[]` |
| GET | `/api/suppliers/{id}` | sheet (60 last purchase orders + `purchaseStats` on all) | — | `SupplierDetail` |
| PATCH | `/api/suppliers/{id}` | modify | `SupplierPatch` | `Supplier` |
| GET | `/api/suppliers/{id}/usual` | regular purchases (60 j) | — | `UsualBasketLine[]` |
| GET | `/api/suppliers/{id}/events` | historical supplier (`sort=open`: open first) | `type`, `status`, `q` + list | `SupplierEventSummary[]` |
| POST | `/api/suppliers/{id}/events` | add an event | `SupplierEventInput` | `SupplierEvent` (201) |
| GET | `/api/supplier-events` | history all suppliers | `type`, `status`, `supplierId`, `q`, `from`, `to` + list; envelope like `/api/client-events` | `SupplierEventSummary[]` |
| PATCH | `/api/supplier-events/{id}` | modify, resolve | `SupplierEventPatch` | `SupplierEvent` |
| GET | `/api/stock` | stock levels | `q`, `tab` (`out` \| `low` \| `expiring`) + list; sort `product` `sku` `category` `onHand` `reserved` `available` `incoming` `expiry` `state`; envelope: `counts` per tab | `StockItem[]` |
| GET | `/api/stock/movements` | movements, recent first (`order=asc`: old first) | `productId` + list | `StockMovement[]` |
| POST | `/api/stock/adjust` | adjustment, loss | `StockAdjustInput` | `StockLevel` |

**Sales** (`routers/orders.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/orders` | list, most recent delivery first | `status`, `clientId`, `date`, `q`, `source`, `ids` + list; sort `number` `client` `date` `createdAt` `lines` `total` `status`; envelope: `counts` by status, `sums.totalHt` | `OrderSummary[]` |
| POST | `/api/orders` | draft | `OrderInput` | `OrderDetail` (201) |
| GET | `/api/orders/{id}` | details + alerts | — | `OrderDetail` |
| PATCH | `/api/orders/{id}` | date, note | `OrderPatch` | `OrderDetail` |
| POST | `/api/orders/{id}/lines` | add a line | `OrderLineInput` | `OrderDetail` (201) |
| PATCH | `/api/orders/{id}/lines/{line_id}` | modify a line | `OrderLinePatch` | `OrderDetail` |
| DELETE | `/api/orders/{id}/lines/{line_id}` | remove a line | — | `OrderDetail` |
| POST | `/api/orders/{id}/confirm` | confirm, book, assign to a tour | — | `OrderDetail` |
| POST | `/api/orders/{id}/prepare` | prepare (actual weight) | `PrepareInput` | `OrderDetail` |
| POST | `/api/orders/{id}/deliver` | deliver (FEFO) | — | `OrderDetail` |
| POST | `/api/orders/{id}/invoice` | bill | — | `InvoiceDetail` (201) |
| POST | `/api/orders/{id}/cancel` | cancel | — | `OrderDetail` |

**Achats** (`routers/purchase_orders.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/purchase-orders` | list, recent first | `status`, `supplierId`, `date` (expected), `q` + list; sort `number` `supplier` `date` `createdAt` `lines` `total` `status`; cover: `counts`, `sums.totalHt` | `PurchaseOrderSummary[]` |
| POST | `/api/purchase-orders` | draft | `PurchaseOrderInput` | `PurchaseOrderDetail` (201) |
| GET | `/api/purchase-orders/{id}` | detail | — | `PurchaseOrderDetail` |
| PATCH | `/api/purchase-orders/{id}` | due date, note | `PurchaseOrderPatch` | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/lines` | add a line | `PurchaseOrderLineInput` | `PurchaseOrderDetail` (201) |
| PATCH | `/api/purchase-orders/{id}/lines/{line_id}` | modify a line | `PurchaseOrderLinePatch` | `PurchaseOrderDetail` |
| DELETE | `/api/purchase-orders/{id}/lines/{line_id}` | remove a line | — | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/send` | send | — | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/receive` | receive (create batches) | `ReceiveInput` | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/cancel` | cancel | — | `PurchaseOrderDetail` |

**Facturation** (`routers/billing.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/invoices` | list without lines (`lineCount`); `status` accepts `open` and `overdue` (calculated) | `status`, `clientId`, `q` + list; sort `number` `client` `issued` `due` `ttc` `paid` `balance` `status`; cover: `counts`, `sums` (totalTtc, amountPaid, balance), `sumsByStatus` | `InvoiceSummary[]` |
| GET | `/api/invoices/{id}` | details + payments | — | `InvoiceDetail` |
| GET | `/api/payments` | list, recent first; each assignment carries `invoiceNumber` | `clientId`, `method`, `q` (customer, reference, invoice number) + list; sort `date` `client` `method` `ref` `amount`; envelope: `sums.amount` | `PaymentSummary[]` |
| POST | `/api/payments` | record (auto assignment to older ones) | `PaymentInput` | `PaymentSummary` (201) |
| GET | `/api/receivables` | age balance, risk, DSO (one line per customer, not paginated) | `q`, `tag`, `rep`, `zone`, `onlyOverdue` | `Receivables` |

**Prices and groups** (`routers/pricing.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/tags` | groups + meters | `scope` | `TagWithCount[]` |
| POST | `/api/tags` | create | `TagInput` | `TagDef` (201) |
| PATCH | `/api/tags/{scope}/{id}` | modify | `TagPatch` | `TagDef` |
| DELETE | `/api/tags/{scope}/{id}` | delete | — | `Ok` |
| GET | `/api/price-rules` | rules | `active`, `clientId`, `productId` + list | `PriceRuleSummary[]` |
| POST | `/api/price-rules` | create | `PriceRuleInput` | `PriceRule` (201) |
| PATCH | `/api/price-rules/{id}` | modify | `PriceRulePatch` | `PriceRule` |
| DELETE | `/api/price-rules/{id}` | delete | — | `Ok` |
| GET | `/api/prices/resolve` | price selected + why + applicants | `clientId`, `productId`, `qty`, `date` | `ResolvedPrice` |
| GET | `/api/prices/grid` | Price grid | `clientId` or `clientTag`, `productTag`, `category`, `q` | `PriceGridRow[]` |

**Logistics** (`routers/logistics.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/routes` | definitions of tours | + list | `Route[]` |
| GET | `/api/route-runs` | passages, the most recent date first (UI still filters by `date`) | `date`, `routeId` + list | `RouteRunDetail[]` |
| POST | `/api/route-runs/plan` | planning a date | `PlanInput` | `RouteRunDetail[]` |
| PATCH | `/api/route-runs/{id}/stops` | reordering the judgments | `ReorderStopsInput` | `RouteRunDetail` |

**Context** (`routers/context.py`)

| Method | Path | Role | Parameters / body | Answer |
|---|---|---|---|---|
| GET | `/api/context` | search / lister (relevance with `q`) | `entityType`, `entityId`, `kind`, `source`, `tag`, `q` + list; sort `title` `entity` `kind` `tags` `source` `updated`; envelope: `counts` by type, `countsBySource` | `ContextEntrySummary[]` |
| POST | `/api/context` | create (`source` = actor) | `ContextEntryInput` | `ContextEntry` (201) |
| GET | `/api/context/for` | the whole context of an entity + related records | `entityType`, `id` | `ContextForEntity` |
| GET | `/api/context/{id}` | one sheet | — | `ContextEntrySummary` |
| PATCH | `/api/context/{id}` | modify | `ContextEntryPatch` | `ContextEntry` |
| DELETE | `/api/context/{id}` | delete | — | `Ok` |

### How it works: AI service (port 4100, proxified in `/ai/*`)

| Road | File | Entry | Output |
|---|---|---|---|
| `GET /health` | `routers/health.py:13` | — | `HealthResponse {ok, llm:{provider,model}, stt:{provider}, tts:{provider}, erpApiUrl}` |
| `GET /tools` | `routers/health.py:25` | — | `ToolInfo[] {name, description, parameters}` |
| `POST /chat` | `routers/chat.py:15` | `ChatRequest {messages, mode?, actorName?}` | SSE of `ChatStreamEvent` |
| `POST /command[?speak=1]` | `routers/command.py:26` | raw audio (`content-type` = mime, `x-mock-text` / `x-stt-hint`) or JSON `CommandRequest {text, actorName?}` | SSE of `CommandStreamEvent` |
| `POST /stt` | `routers/speech.py:18` | raw audio, `x-stt-hint` or `x-mock-text` | `SttResponse {text, ms}` ; 502 `stt_failed` |
| `POST /tts` | `routers/speech.py:37` | `TtsRequest {text, voice?}` | streaming audio bytes, header `x-ms` ; 502 `tts_failed` |
| `WS /voice` | `routers/voice.py:10` | `VoiceClientMessage` + binary frames | `VoiceServerMessage` + binary frames |

Errors: `400 {error: {code: "bad_request", message}}` (invalid body, `main.py:45`).

**Events SSE** (`schemas/chat.py`, `schemas/command.py`) — one line `data: <JSON>` per event, discriminated against by `type`:

| `type` | Fields | `/chat` | `/command` |
|---|---|---|---|
| `transcript` | `text`, `ms` (time STT), `final` (default true), `stable?` | | the final before the others; `WS /voice/command` also sends `final:false`s during the speech |
| `text` | `delta` | ✓ | ✓ |
| `tool_call` | `call {id, name, arguments}` | ✓ | ✓ |
| `tool_result` | `callId`, `name`, `ok`, `result`, `ms` | ✓ | ✓ |
| `navigate` | `path`, `label?` | | if the user wants to *see* |
| `speech` | `mime`, `audio` (base64), `ms` | | if `speak=1` |
| `done` | `message`, `usage?`, `ms`, `timings?` | last | last (with `timings`) |
| `error` | `message` | instead of `done` | Idem |

**Messages WebSocket `/voice`** (`schemas/voice.py`):

| Sense | `type` | Fields | Effect |
|---|---|---|---|
| client → server | `start` | `sessionId?`, `actorName?` | Opens / resumes a conversation |
| | `audio_start` | `mime`, `hint?` (index STT; mock STT: text heard) | interrupts the agent (barge-in), starts recording |
| | *(binar)* | audio frames (all 100–250 ms) | sent to STT upon receipt (live transcript) |
| | `audio_end` | — | Launch the turn |
| | `text` | `text` | turn typed (debug, scripts) |
| | `reset` | — | Clear history, returns `ready` |
| server → client | `ready` | `sessionId`, `stt`, `tts`, `llm` | |
| | `transcript` | `track: "caller"`, `text`, `final`, `stable?` | `final:false` during speech (text heard so far; `stable` = definitive words), then a `final:true` |
| | `agent_text` | `delta` | |
| | `agent_tool` | `name` + `args` (call) then `name`, `ok`, `ms` (end) | |
| | `agent_audio_start` | `mime` | followed by binary frames (one segment per turn) |
| | `agent_audio_end` | — | |
| | `agent_done` | `text`, `timings` | |
| | `error` | `message` | |

All these models are published in `http://localhost:4100/openapi.json` (`main.py:54-81`).

### Extend

An additional ERP endpoint: [2.6](#ajouter-endpoint). An additional SSE event or WS message: add the template in
`apps/ai/app/schemas/` ** and ** in the union (`ChatStreamEvent`, `CommandStreamEvent`, `VoiceServerMessage`...), then
the type in `packages/shared/src/ai.ts`.

### Traps

- `limit`, `qty`, etc. are strings side ERP; lists are separated by commas.
- A list without `envelope=1` is an array **truncated to `limit` (default 100)**: for "all" lines of a
  small table, `limit=500`; for large ones (orders, invoices, movements), filter or paginate.
- `/api/invoices?status=overdue` filter on ** status calculated** (never stored).

---

<a id="service-AI"></a>
## 4. Service AI (`apps/ai/app`)

### What it is

An agent harness: a tool model loop, three modes (`chat`, `voice`, `command`), customers LLM / STT /
Interchangeable TTS written in raw `httpx` (no SDK), and three surfaces (`/chat`, `/command`, `WS /voice`).

### Key Files

| File | Role |
|---|---|
| `config.py` | `settings` (read once on startup) |
| `clients/base.py` | interfaces `LLMClient`, `STTClient`, `TTSClient` + event types |
| `clients/factory.py` | `.env` → one customer of each kind (`get_llm_client()`...), default models |
| `clients/{openai,anthropic,gemini}.py` | LLM adapters |
| `clients/{soniox,deepgram,gradium,elevenlabs}.py` | speech adapters; `openai.py` also has STT + TTS |
| `clients/mock_llm.py`, `mock_speech.py` | fake suppliers offline |
| `clients/jev.py` | decision model Jev |
| `clients/http.py`, `ws.py`, `audio.py` | shared pool HTTP, SSE, errors; WebSocket; webm→ogg, PCM→mp3 |
| `agent/loop.py` | `run_agent` |
| `agent/prompts.py` | `build_system_prompt` |
| `tools/` | tools (section 5) |
| `services/voice_session.py`, `services/command.py` | the push-to-talk voice, the |
| `routers/` | Slim roads |
| `schemas/` | the contract (events, messages WS) |
| `cli.py` | `make chat` |

### How it works

<a id="config-AI"></a>
#### 4.1 Configuration

`config.py` loads the root `.env` (real environment variables win) in `settings`, **one only
times**. Customers are built once (`@cache`, `factory.py:103-121`) and start-up (`main.py:27-36`) : a
missing key makes boot fail with `configuration error`. After a change of `.env`: `make restart`
(Docker) or restart `make dev`.

| Variable | Default | Read in |
|---|---|---|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_BASE_URL` | `mock`; models: `factory.py:24` | `make_llm_client` (`factory.py:44`) |
| `LLM_EFFORT` | `low` | Anthropic (`output_config.effort`) |
| `AGENT_MAX_STEPS` | 8 | `loop.py:60` |
| `STT_*`, `MOCK_STT_TEXT` | `mock`, `fr` | `make_stt_client` (`factory.py:66`) |
| `TTS_*` | `mock`, `fr` | `make_tts_client` (`factory.py:82`) |
| `JEV_*` | → empty key no Jev | `make_jev_client` (`factory.py:97`) |
| `ERP_API_URL`, `DATA_DIR`, `AI_PORT` | `http://localhost:4000`, `../hackathon-data` (team zip: `./data`), 4100 | `config.py:71-75` |

Change model without code: `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL=https://api.groq.com/openai/v1`,
`LLM_MODEL=…`, `LLM_API_KEY=…`. Complete list: [apps/ai/README.md#environment](apps/ai/README.md#environment).

<a id="clients"></a>
#### 4.2 Customers (`clients/`)

**Interfaces** (`clients/base.py`):

```python
# LLM — clients/base.py:51-57
class LLMClient(ABC):
    provider: str
    model: str
    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Stream one model response. Implement it as an `async def` generator (with `yield`)."""
```

- `LLMRequest {system, messages: list[ChatMessage], tools: list[ToolInfo], max_tokens}`; generator emits
  `LLMText(delta)` on the water, `LLMToolCall(call)` (once the arguments are complete) and `LLMUsage`.
  The adapter translates `ChatMessage` (`user`, `assistant` with `tool_calls`, `tool` with `tool_call_id` + `name`)
  in the supplier's format (`to_openai_message`, `to_anthropic_messages`, `to_gemini_contents`).
- `STTClient.transcribe(audio, mime, hint) -> str`; **`transcribe_stream(audio_chunks, mime, hint)`** emits
  `STTUpdate(text, final, stable)` (full text every time). By default: waits for the end and then only one update
  final. Soniox, Deepgram and the mock overload it (`streams = True`): see [Direct transcript](#stt-direct).
- `TTSClient.synthesize(text, voice) -> TTSResult(mime, chunks)`: raises on error HTTP, then streams the bytes.
  All real TTS returns `audio/mpeg` (the web player concatenates the mp3 of a spin); PCM → `audio.Mp3Encoder`.

**Factory** (`factory.py:44-63`): one `match` by type. `DEFAULT_MODELS`, `DEFAULT_STT_MODELS`, `DEFAULT_TTS`
give the defects.

**HTTP shared** (`clients/http.py`): one single `httpx.AsyncClient` (`http_client()`, reuses TLS connections),
`post_stream` (POST without reading the body), `sse_json` (directed by `data:`), `body_chunks`, `parse_args`,
`provider_error` formatting `"<who> HTTP <status>: <body> — <indice>"` (key refused, quota, audio format).

**Strength: add a supplier** (example TTS; LLM and STT follow the same scheme):

1. `apps/ai/app/clients/montts.py` — replace the URL, headers and body with those of the supplier:

   ```python
   from .base import TTSClient, TTSResult
   from .http import body_chunks, http_client, post_stream

   class MonTTS(TTSClient):
       name = "montts"

       def __init__(self, api_key: str, model: str, voice: str):
           self.api_key, self.model, self.voice = api_key, model, voice

       async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
           res = await post_stream(
               http_client(), "https://api.example.com/v1/tts/stream", who="montts tts",
               headers={"authorization": f"Bearer {self.api_key}"},
               json={"text": text, "model": self.model, "voice": voice or self.voice, "format": "mp3"},
           )
           return TTSResult("audio/mpeg", body_chunks(res))   # mp3 obligatoire pour le lecteur web
   ```

2. `factory.py`: Import the class, add a defect in `DEFAULT_TTS` and a `case`:

   ```python
   case "montts":
       return MonTTS(need("TTS_API_KEY", cfg.api_key), model, voice)
   ```

3. `.env`: `TTS_PROVIDER=montts`, `TTS_API_KEY=…`; `make restart`; check `GET /ai/health` and
   `curl -s localhost:4100/tts -H 'content-type: application/json' -d '{"text":"Bonjour"}' -o /tmp/t.mp3`.
4. A LLM "OpenAI compatible" does not require any code (`openai-compatible`). A different LLM: copy
   `anthropic.py` (the shortest with streaming tool calls management). Tests: on the model of
   `tests/test_clients.py` (recorded SSE responses, no network).

<a id="prompts"></a>
#### 4.3 Prompts (`agent/prompts.py`)

```python
# agent/prompts.py:54-67
async def build_system_prompt(mode: ChatMode, actor_name: str | None = None) -> str:
    meta = await get_meta()
    today = meta.get("today") or datetime.now(UTC).date().isoformat()
    company = meta.get("company") or "un grossiste alimentaire"
    trade = meta.get("trade") or company_trade()
    parts = [
        ROLE.format(company=company, trade=f"Activité : {trade}" if trade else "C'est un grossiste alimentaire"),
        BASE_RULES,
        MODE_RULES[mode],
        f"Entreprise : {meta.get('company') or '(ERP injoignable)'}. Aujourd'hui : {french_date(today)} ({today}).",
        f"Interlocuteur : {actor_name}." if actor_name else "",
        f"# Contexte entreprise\n\n{context}" if (context := read_context_files()) else "",
    ]
    return "\n\n".join(p for p in parts if p)
```

| Part | Content | Source |
|---|---|---|
| `ROLE` (`:19-20`) | "ERP assistant from {company}. Activity: {trade}": `company` from `GET /api/meta`, `trade` from `meta.trade` or 1re sentence from `DATA_DIR/context/*entreprise*.md` (`company_trade()`) | ERP + pack |
| `BASE_RULES` (`:22-32`) | "tools for any data", `search` first, `get_price`, `get_context`, draft and then explicit confirmation, alerts, concise French | code |
| `CHAT_RULES` (`:34`) | light markdown | code |
| `VOICE_RULES` (`:36-41`) | 1–2 sentences, no markdown or ids, numbers in all letters, at most "I look." before the first tool then nothing between the tools (every text is pronounced in order), summarize before confirming | code |
| `COMMAND_RULES` (`:43-49`) | to act immediately, a sentence, an explicit request is to be agreed | code |
| company + date | `meta.company`, `meta.today` in French | `GET /api/meta`, cache 60 s (`:64-80`) |
| Interlocutor | `actorName` ("Vocal Agent", "Voice Control", "CLI") | request |
| context | all `DATA_DIR/context/*.md` (first level, sorted), read **each** turn | `read_context_files` (`:83-90`) |

Expand: Change the rules in `prompts.py` or the context in `data/context/*.md` (taken in turn)
to inject the caller's file, add a part to `parts` (e.g., the result of
`GET /api/context/for` for a customer known to the session).

<a id="loop"></a>
#### 4.4 Agent loop (`agent/loop.py`)

```python
# agent/loop.py:60-91 (extrait)
for _step in range(max_steps or settings.max_steps):
    text = ""; calls = []
    async for ev in llm.stream(request):
        match ev:
            case LLMText(delta=delta):      text += delta; yield TextEvent(delta=shown)
            case LLMToolCall(call=call):    calls.append(call); yield ToolCallEvent(call=call)
            case LLMUsage(...):             usage.input_tokens += i or 0 ...
    if not calls:                                            # réponse finale
        messages.append(ChatMessage(role="assistant", content=text))
        yield DoneEvent(message=message, usage=usage, ms=ms_since(started)); return
    messages.append(ChatMessage(role="assistant", content=text, tool_calls=calls))
    results = await asyncio.gather(*(execute_tool(call, tools, ctx) for call in calls))
    for r in results:
        messages.append(ChatMessage(role="tool", tool_call_id=r.call_id, name=r.name, content=to_json(r.result)))
        yield r
```

Step by step:

1. `ctx = ToolContext(erp=ErpClient(actor, actor_name), actor=actor)`; `actor` = `ai_chat` in chat mode, otherwise
   `voice_agent` (`:51-52`).
2. The prompt system is built once per turn; the same `LLMRequest` is returned at each step (it
   refers to the `messages` list, which is growing).
3. The text is streamed **dependent** that the model generates; tool calls are collected.
4. No call → `DoneEvent`, fine. Otherwise the tools spin ** in parallel** (`asyncio.gather`), their results
   are added in `tool` messages (JSON compact, kept accents) and the model is recalled.
5. Beyond `AGENT_MAX_STEPS` (8): message `GIVE_UP` ("I'm sorry, I couldn't get to the end...").
6. `execute_tool` (`:102-112`) never lifts: unknown tool or exception → `ok=false`, `result={"error": "…"}`;
   The model reads the error and explains or tries again.
7. Any other exceptions (supplier failed, key refused) → `ErrorEvent`. Cancellation (`CancelledError`) is not
   not a `Exception`: the loop stops without emitting anything. It is the mechanism of the barge-in and disconnection
   a customer SSE (Starlette cancels the generator, `routers/sse.py:15`).

**`run_agent` changes the `messages` list that is passed to **: the one who keeps the list keeps the history.

| Mode | Who keeps the history | Where |
|---|---|---|
| `chat` | the **navigator**: `history` in `chat-store.ts:23`, returned in full to each `POST /chat` (rebuilt by `TurnRecorder`); lost when reloading the page | `apps/web/src/features/assistant/` |
| `voice` | **service AI**: `conversations: dict[sessionId, Conversation]` in memory (`voice_session.py:68`), work copy validated at the end of turn, cut to ~40 messages by `trim()` (`:296-301`, always starts on a `user` message); lost at restart | `services/voice_session.py` |
| `command` | person: one `user` message per query (`services/command.py:104`) | |
| CLI | `messages` list of `cli.py` (`/reset` empty) | `app/cli.py` |

<a id="latency"></a>
#### 4.5 Latency: where every millisecond is played

| Step | What the kit does | Lever |
|---|---|---|
| STT | **difference** transcription support ([live transcription](#stt-direct)): on release, only the last words remain to be finalized | LLM launched on a stable part, hands-free mode (`<end>`) |
| prompt | rules + all `DATA_DIR/context/*.md` (的 44 Ko in the reference pack) returned to each step; Anthropic: read back to the cache ([4.8](#cache-prompt)) | reduce context, keep prefix stable |
| LLM | one call per step; tools in parallel | composite tool ([5.4](#outil-composite)), fast model, `LLM_EFFORT=low` |
| tools | `ErpClient` reuses shared `httpx.AsyncClient` (`erp_http()`, keep-alive, timeout 10 s, shut down) (`tools/erp.py:23-41`) | composite tool, fewer calls ERP |
| TTS | sentence by sentence: as soon as a sentence ends with `. ! ? …` + space (`Speaker.SENTENCE`, `:230`), it leaves the TTS; only one mp3 segment per turn | cut earlier (virgulate), girl during tools |
| reading | `SegmentPlayer` (MediaSource) plays from the first byte | — |

<a id="session-voice"></a>
#### 4.6 Voice session (`services/voice_session.py`)

- `VoiceConnection.serve()` reads the frames; binary → `recording.feed()` (sent to STT live, see [live transcript](#stt-direct)]; text → `handle_text`.
- Each tower is a `asyncio.Task` (`start_turn`); `interrupt()` cancels it and awaits its cleaning.
- `run_turn` (`:168-229`): STT → `transcript` → `run_agent(mode="voice")` on a copy of the historical → text
  to `Speaker` → `speaker.finish()` → `agent_done`. Errors become `error` messages.
- `Speaker` (`:231-294`): a text buffer, a line of phrases, a worker that synthesizes and sends bytes
  `agent_audio_start` starts on the first byte; `tts_first_byte_ms` is measured there.
- Reconnection with same `sessionId` → same `Conversation`.

<a id="stt-direct"></a>
#### Live Transcript (`services/utterance.py`, `services/vocabulary.py`)

```
audio_start ─▶ Utterance(stt, mime, hint, on_partial)    ouvre le flux STT (si stt.streams)
trame       ─▶ feed(frame) ─▶ fournisseur                 ◀─ on_partial(STTUpdate) ─▶ transcript {final:false}
audio_end   ─▶ await text()   Soniox : {"type":"finalize"} ─▶ jeton <fin> ─▶ transcript {final:true} ─▶ agent
barge-in    ─▶ cancel()       ferme le flux du fournisseur
```

- Each frame is also kept: if the stream breaks or does not render its final words in `FINAL_TIMEOUT_S` (5 s),
  `text()` transcribes the complete record (`transcribe`). The statement is never lost.
- Soniox chips: non-final = returned in full to each message, can change; final = sent once.
  `stable` = the final words. `<end>` (pause detected) and `<fin>` (response to the finalize) are not text.
- Vocabulary: names of customers, then products, then their alias (`/api/clients`, `/api/products`), cache 5 min,
  `MAX_TERMS` = 500 → `context.terms` (Soniox, capped at `MAX_TERMS_CHARS`), `keyterm` (Deepgram). To enrich it:
  `company_terms()` (e.g. contact names, or the customer's usual online basket). The STT mock does not receive one.
- The STT mock simulates partials (one word all the 3 frames): the display is tested without a key.

**Strength**: Launch LLM on a stable partial (GUIDE-VOIX 4.3); Hands-free mode on `<end>` chips;
vocabulary by call (usually the client's identified file).

<a id="Jev"></a>
#### 4.7 Jev (typed)

`get_jev_client()` returns a `JevClient` or `None` without `JEV_API_KEY`. Methods: `choose`, `score`, `yes_no`,
`ask` (several single-call questions). Examples ready to copy: `agent/jev_examples.py` (`pick_product`,
`is_yes`). **Nothing in the default agent calls it.** Format and uses: [apps/ai/README.md#Jev-decision-model](apps/ai/README.md#jev-decision-model).

<a id="cache-prompt"></a>
#### 4.8 Quick cache (Anthropic)

The prefix of a query (tools → quick system → messages) weighs ≈ 27 k tokens in reference pack (≈ 44 Ko of
`DATA_DIR/context/*.md` + tool diagrams). `clients/anthropic.py` poses 3 cache points `cache_control:
{"type": "ephemeral"}` (API accepts 4): on the **last tool**, on the **block system**, and on the **dernier
block of the last message**. The next step of the same turn (after a tool result) and the next turn reread
So all the prefix already seen to the cache: 10 % of the entry price and a first token faster. Shelf life: 5 min
after the last use; writing the cache costs 的 1,25× the normal price once.

- **See Hits**: `POST /chat` event `done` carries `usage.cacheReadInputTokens` (read in cache) and
  `usage.cacheCreationInputTokens` (written); `make chat` displays them ("cache read ... / written ..."). At Anthropic,
  `inputTokens` only counts the part **excluding cache** (total = input + cacheCreation + cacheRead).
- **What breaks the cache** (any byte changed invalids the following): a time stamp, id or counter in the
  prompt system; edit a file from `DATA_DIR/context/` (normal: next turn rewrites cache); add,
  removing or reordering tools, or changing a docstring / argument; changing a model or `LLM_EFFORT`;
  Rewrite an old message from history. The date comes from `GET /api/meta` (stable), not from the clock.

### Traps

See [9](#pieges): memory vocal history, optional STT index (`hint` of `audio_start`, not sent by the
Prompt cover: only the Anthropic adapter poses it ([4.8](#cache-prompt)).

---

<a id="tools"></a>
## 5. Tools (`@tool`) in detail

### What it is

A tool is a Python `async` function that the model can call. The decorator `@tool` takes its name, the
description and schema JSON sent to the model. Each tool calls the ERP in HTTP; it does not contain a rule
trade.

### Key Files

| File | Content |
|---|---|
| `apps/ai/app/tools/registry.py` | `@tool`, `Tool`, `ToolContext`, `ToolArgs`, `TOOLS`, `json_schema` |
| `apps/ai/app/tools/erp.py` | `ErpClient` (`get`, `post`, `patch`, `delete`, shared pool `erp_http()`), `ErpError`, `enc`, `pick` |
| `apps/ai/app/tools/catalog.py` · `context.py` · `history.py` · `orders.py` | 16 tools |
| `apps/ai/app/tools/__init__.py` | imports modules (= saves tools), `all_tools()` |
| `apps/web/src/features/assistant/tools.tsx` | `TOOL_LABEL`: French text displayed in the UI |

### How it works

<a id="decorator"></a>
#### 5.1 Decorator

```python
# apps/ai/app/tools/registry.py:69-83
def tool(fn=None, *, name=None):
    def register(fn) -> Tool:
        params = list(inspect.signature(fn).parameters.values())[1:]  # skip ctx
        fields = {p.name: (p.annotation, ... if p.default is inspect.Parameter.empty else p.default) for p in params}
        args_model = create_model(f"{fn.__name__}_args", __base__=ToolArgs, **fields)
        description = " ".join(line.strip() for line in inspect.cleandoc(fn.__doc__ or "").splitlines() if line.strip())
        t = Tool(name=name or fn.__name__, description=description, args_model=args_model, fn=fn)
        TOOLS[t.name] = t
        return t
    return register(fn) if fn else register
```

| Python element | Becomes for the model | Example |
|---|---|---|
| function name (or `@tool(name="…")`) | name of tool | `get_product_stock` |
| docstring (lines joined by spaces) | `description` | "Inventory of a product: ..." |
| 1er parameter | **rian**: this is the `ToolContext` | `ctx: ToolContext` |
| other parameters | `parameters` (JSON scheme), names in camelCase (`ToolArgs`, `alias_generator=to_camel`) | `product_id` → `productId` |
| without fault, or `= Field(description=…)` without fault | `required` | `client_id: str = Field(description="ex. cli_0012")` |
| `X \| None = None` ou `Field(None, ...)` | optional, without `null` in schema | `qty: float \| None = Field(None, ...)` |
| `Literal["a", "b"]` | `enum` | `entity_type: Literal["client", "supplier", …]` |
| `list[Literal[…]]` | `array` d'`enum` | `types` of `search` |
| subclass of `ToolArgs` | nested, inlined object (no `$ref`) | `lines: list[OrderLine]` (`orders.py:10`) |
| `Field(description=…)` | `description` parameter | |

`json_schema` (`registry.py:89-111`) removes titles, defects, `$defs`/`$ref` and `| null`: the scheme looks like this
Check it with `curl -s localhost:4100/tools`.

**Validation** (`Tool.run`, `registry.py:57-63`): the model arguments are validated by the Pydantic model
camelCase or snake_case accepted. → `ValueError("Arguments invalides : qty: …")` failed, as the loop
refers to the model like `{"error": …}`. The function then receives typed Python values (interlocked objects)
are `ToolArgs` instances, hence `line.to_erp()` in `orders.py`).

**`ToolContext`** (`registry.py:34-37`): `ctx.erp` is a `ErpClient` already marked `x-actor` (`ai_chat` or
`voice_agent`) and `x-actor-name`; `ctx.actor` allows to adapt the behavior (e.g. `source` of a command,
`orders.py:55`). `ctx.erp.get(path, query)` removes `None`/vides; `ctx.erp.post(path, body)`; a
ERP refusal raises `ErpError` with its French message (`erp.py:76-81`), which the model will read.

**Registration**: Importing the module is enough (`tools/__init__.py:14`). `all_tools()` is reread at each request; all
Modes receive all the tools.
A poorly declared tool (not `async def`, no `ctx: ToolContext`, no type parameter, no docstring, name in
double) causes the boot to fail with a French message; the complete trace appears in the server terminal.

**Return**: any serializable value in JSON (dict, list, str, number). It is serializable in JSON
compact and added to the conversation: the model rereads it ** at each next step** of the round, and in voice it remains
That's why `pick(...)` and `[:5]` are everywhere.

#### 5.2 16 tools

| Tool | File | Call | Return (reduced) |
|---|---|---|---|
| `search(query, types?)` | `catalog.py:12` | `GET /api/search` | 8 first `{type, id, label, sublabel}` |
| `get_client(client_id)` | `catalog.py:31` | `GET /api/clients/{id}` | status, conditions, current, 5 notes, 10 lines of the usual, `openIssues`, 5 events, 5 commands |
| `get_product_stock(product_id)` | `catalog.py:55` | `GET /api/products/{id}` | `available`, `onHand`, `reserved`, `incoming`, `nextExpiry`, prices |
| `find_alternatives(product_id)` | `catalog.py:70` | `GET /api/products/{id}/alternatives` | 5 products |
| `get_price(client_id, product_id, qty?)` | `catalog.py:80` | `GET /api/prices/resolve` | `price`, `listPrice`, `source`, `explanation`, `betterPriceWithVolume?` |
| `search_context(query, entity_type?, entity_id?, kind?, limit?)` | `context.py:36` | `GET /api/context?q=` | Compact plugs (body ≤ 500 car.) |
| `get_context(entity_type, id)` | `context.py:56` | `GET /api/context/for` | `{about, entries, related}` |
| `save_context(entity_type, kind, title, body, entity_id?, tags?)` | `context.py:75` | `POST /api/context` | `{id, saved, title}` |
| `get_client_history(client_id, types?, limit?)` | `history.py:49` | `GET /api/clients/{id}/events` | Opened first, ≤ 20 |
| `log_client_event(client_id, type, title, …)` | `history.py:65` | `POST /api/clients/{id}/events` | compact event |
| `get_supplier_history(supplier_id, types?, limit?)` | `history.py:96` | `GET /api/suppliers/{id}/events` | Opened first, ≤ 20 |
| `log_supplier_event(supplier_id, type, title, …)` | `history.py:111` | `POST /api/suppliers/{id}/events` | compact event |
| `create_draft_order(client_id, delivery_date?, lines?, note?)` | `orders.py:38` | `POST /api/orders` | `summarize_order` : id, number, status, lines with `lineId`, `warnings` |
| `add_order_line(order_id, product_id, qty, note?, substitute_for?)` | `orders.py:60` | `POST /api/orders/{id}/lines` | Idem |
| `confirm_order(order_id)` | `orders.py:74` | `POST /api/orders/{id}/confirm` | Idem |
| `get_order(order_id)` | `orders.py:83` | `GET /api/orders/{id}` | Idem |

What the agent can't do due to lack of tool (roads exist): modify/remove a line, change the date,
cancel, prepare, deliver, invoice, cash, buy, manage prices, stock, tours.

<a id="add-tool"></a>
#### 5.3 Expand: add a simple tool

`list_overdue_invoices` — the ERP already calculates `overdue` and `daysOverdue` (`services/invoices.py:25-41`):

```python
# apps/ai/app/tools/billing.py  (nouveau fichier)
"""Billing tools: what a client owes."""

from pydantic import Field

from .erp import pick
from .registry import ToolContext, tool


@tool
async def list_overdue_invoices(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Factures échues (en retard) d'un client, avec le total dû. À utiliser quand le client demande ce qu'il doit,
    pourquoi il est bloqué, ou avant d'accepter une grosse commande. Overdue invoices of a client.
    """
    invoices = await ctx.erp.get("/api/invoices", {"clientId": client_id, "status": "overdue"})
    return {
        "count": len(invoices),
        "totalDue": round(sum(i["balance"] for i in invoices), 2),
        "invoices": [pick(i, "number", "dueDate", "balance", "daysOverdue") for i in invoices[:5]],
    }
```

Then:

1. `apps/ai/app/tools/__init__.py` : `from . import billing, catalog, context, history, orders`.
2. `curl -s localhost:4100/tools | grep -A3 list_overdue` (uvicorn has reloaded).
3. `make chat` → "What does Zinc des Halles owe?".
4. Optional: `TOOL_LABEL.list_overdue_invoices = "Factures en retard"` in `apps/web/src/features/assistant/tools.tsx:21`.
5. If the tool changes the expected behavior, add a rule from a line in `BASE_RULES` (`agent/prompts.py`).

**A writing tool**: `ErpClient` a `get`, `post`, `patch` and `delete`. For `PUT`, add a method in
`tools/erp.py` on the model of `patch`:

```python
async def put(self, path: str, body: Any = None) -> Any:
    return await self._request("PUT", path, json={} if body is None else body)
```

Example: `update_order_line` → `await ctx.erp.patch(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}", {"qty": qty})`.
With road `repeat` of [2.6](#ajouter-endpoint): `await ctx.erp.post(f"/api/orders/{enc(order_id)}/repeat", {})`.

<a id="tool-composite"></a>
#### 5.4 Expand: a composite tool

A model round trip costs much more than a local HTTP call. A tool that runs multiple calls ERP
saves loop steps:

```python
# dans apps/ai/app/tools/catalog.py (search, pick, enc, format_number y sont déjà)
import asyncio

@tool
async def quote_product(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_query: str = Field(description="Ce que le client a dit, ex. « bar de ligne », « loup »"),
    qty: float | None = Field(None, description="Quantité (défaut 1)"),
) -> dict:
    """
    Trouve un produit à partir de ce que dit le client et renvoie en un seul appel son stock et SON prix.
    À utiliser quand un client connu demande « vous avez du … ? » ou « c'est combien le … ? ».
    Product lookup + stock + client price in one call.
    """
    hits = await ctx.erp.get("/api/search", {"q": product_query, "types": "product", "limit": 3})
    if not hits:
        return {"found": False, "query": product_query}
    product_id = hits[0]["id"]
    product, price = await asyncio.gather(
        ctx.erp.get(f"/api/products/{enc(product_id)}"),
        ctx.erp.get("/api/prices/resolve", {"clientId": client_id, "productId": product_id,
                                            "qty": format_number(qty) if qty else None}),
    )
    return {
        "found": True,
        "product": pick(product, "id", "name", "unit", "available", "nextExpiry"),
        "price": pick(price, "price", "source", "explanation"),
        "otherMatches": [pick(h, "id", "label") for h in hits[1:]],
    }
```

Keep `otherMatches`: the model can ask "what?" when the search hesitates.

#### 5.5 Good practices

- **Description = when to use it.** First sentence in French (what the tool does), then "To use when...",
  then a short English sentence (models go better). Citing the neighbouring tools ("not for a claim:
  `log_client_event` », `context.py:87`).
- **Parameters described with an example of id** (`ex. cli_0012`) and `Literal` as soon as the values are closed.
- **Releases small**: `pick` useful fields, cut lists, shorten texts (`compact`,
  `compact_event`). No raw ERP object.
- **Errors**: Raise an exception with a French message; do not return `{"ok": false}` silent.
- **Scripts**: Make them sure to play again when possible (the model tries again after an error), return
  the id created for the next steps, and leave the confirmation to the prompt ("confirms only after explicit agreement",
  `BASE_RULES`) or a separate tool (`create_draft_order` and then `confirm_order`).
- **No business rules in the tool**: if a calculation is missing, add it to `apps/backend/app/services/`.

### Traps

- `@tool` **replaces the function with an object `Tool`**: `await get_price(...)` does not work. Call
  `await TOOLS["get_price"].run({...}, ctx)` or `tool.fn(ctx, ...)`.
- The function must be `async` and its **-annotated parameters** (if not the schema is false).
- Python Order: A defaultless parameter cannot follow a default parameter. `Field(description=…)` without
  value counts as a Python defect but remains required for the model: use it to keep order.
- A non-serializable return to JSON (object, `datetime`) becomes `{"error": "… non sérialisable en JSON …"}` for this
  only call (`execute_tool`, `loop.py`): send back `str` / numbers / lists / dicts.
- Two tools of the same name: the last imported crushes the first in `TOOLS`.

---

<a id="frontend"></a>
## 6. Frontend (`apps/web/src`)

### What it is

A SPA React 18 + Quick + Tailwind + React-router + TanStack Query. She speaks to the ERP (`/api`) and the AI service
(`/ai`) via the Quick Proxy. Shared types: `@kit/shared` (`packages/shared/src`).

### Key Files

| Path | Role |
|---|---|
| `main.tsx` | `QueryClient` (staleTime 15 s, retry 1), business clock loaded before first rendering |
| `app/routes.tsx` | all routes (one page = `pages/<nom>/index.tsx`, default export) |
| `app/nav.ts` | side menu + "Go to" commands from 的K |
| `app/AppShell.tsx` | sidebar · page · Assistant panel ; mount SSE, |
| `lib/api.ts` | typed client: a ERP route function, → toast + `ApiRequestError` errors |
| `lib/queries.ts` | `qk` query keys, one hook per playback, `useApiMutation`, SSE feed, `INVALIDATE` |
| `lib/url-state.ts` | filters in the URL (`useUrlState`, `useUrlPatch`, `useDebounced`) |
| `lib/clock.ts` | `businessNow()` / `businessToday()` aligned to `meta.today` |
| `ui/` | design system (`@/ui`) — [DESIGN.md](DESIGN.md), `ui/README.md` |
| `features/assistant/` | chat, voice session, audio player, tool display |
| `features/voice-command/` | Space: engine, HUD, button |
| `features/document/` | shared blocks of document pages (order, purchase) |
| `pages/voice/` | Voice page (call + command mode, timeline, metric, live activity) |

### How it works

<a id="données-web"></a>
#### 6.1 Read and write data

```ts
// lecture
const { data, isLoading } = useOrders({ status: "draft" });          // lib/queries.ts:148
// écriture
const confirm = useApiMutation(api.orders.confirm, { success: "Commande confirmée", invalidate: [qk.orders.all] });
confirm.mutate(order.id);
```

- `request()` (`lib/api.ts:47-78`) adds `x-actor: user` / `x-actor-name: Moi` to the scriptures, transforms
  `{error:{code,message}}` in `ApiRequestError` and displays a toast (`{silent:true}` to cut it).
- `qk` keys are prefixed: invalidate `qk.orders.all` (`["orders"]`) refreshes all lists and sheets of
  orders.
- `useApiMutation` (`queries.ts:205-221`) toast success, toast each `warnings[]` answer, invalid
  Key data.

#### 6.2 Status in URL

`const [q, setQ] = useUrlState("q")`: filters live in `?q=&type=`, survive reloading, share.
Changing a filter returns the pagination to 1 (except `{keepPage:true}`). Several sets in the same tick merge
(`url-state.ts:15-40`).
The large lists are paginated by the API ([Pagination](#pagination)): `useServerList({ defaultSort })` bed `?page=`
and `?sort=-champ` and gives `params` (`limit`, `offset`, `sort`, `order`) to switch to the hook `use…Page`, which returns
`{items, total, counts, sums…}`; `<DataTable server={{ list, total }}>` displays the page and the pagination bar.
Reference lists (customers, products, suppliers for selectors) are loaded in full with
`useClients()` / `useProducts()` / `useSuppliers()` (`limit=500`, `LIST_MAX` in `lib/api.ts`).

#### 6.3 Clock

Do not use `new Date()` for today: `businessToday()` / `businessNow()` (`lib/clock.ts`).

<a id="live"></a>
#### 6.4 Live Updates

`useActivityStream()` (`queries.ts:273-299`) opens `EventSource("/api/events/stream")`, connects with backoff,
and for each `ActivityEvent`: add it to cached event lists, invalidate `INVALIDATE[entity]` keys
(`queries.ts:232-243`), marks the idea for the purple flash (`useRecentlyChanged`, `DataTable` does it alone) and warns
`useOnActivity` subscribers. Pages never pollling.

<a id="areas-AI"></a>
#### 6.5 The three surfaces AI

| Surface | Code | Transport | State |
|---|---|---|---|
| Assistant () | `features/assistant/AssistantPanel.tsx`, `chat-store.ts`, `ai-client.ts` | `fetch POST /ai/chat`, read SSE by hand (`ai-client.ts:59-75`) | store module: survives the panel closure, not reloading |
| Voice · Call (`/voice`) | `pages/voice/index.tsx`, `features/assistant/useVoiceSession.ts`, `audio-player.ts` | `WebSocket /ai/voice`, MediaRecorder in 100 ms slices (STT live) | `sessionId` in the hook; server-side history |
| Voice · Command (Aspace `/voice?mode=command`) | `features/voice-command/engine.ts`, `VoiceCommand.tsx`, `pages/voice/command.tsx` | voice: `WS /ai/voice/command?speak=1` (tracks of 100 ms, STT live); keyboard: `fetch POST /ai/command?speak=1` (JSON), SSE | singleton shared module HUD / page |

- Audio mock : mime `audio/x-mock-wav` (`MOCK_TTS_MIME`) → the browser reads the text with `speechSynthesis` en-FR.
- Tool calls are displayed with `features/assistant/tools.tsx` (`TOOL_LABEL`, links to entity).
- Space = push-to-talk on `/voice` out of text field (`pages/voice/index.tsx:50-75`);
  field (`VoiceCommand.tsx:23-40`).

<a id="add-page"></a>
### Expand: add a page (6.6)

1. `apps/web/src/pages/overdue/index.tsx` :

   ```tsx
   import { Link } from "react-router-dom";
   import type { InvoiceSummary } from "@kit/shared";
   import { useInvoices } from "@/lib/queries";
   import { DataTable, Money, Page, PageBody, PageHeader, type Column } from "@/ui";

   const columns: Column<InvoiceSummary>[] = [
     { id: "number", header: "Facture", mono: true, cell: (i) => <Link to={`/invoices/${i.id}`}>{i.number}</Link> },
     { id: "client", header: "Client", sortValue: (i) => i.clientName, cell: (i) => i.clientName },
     { id: "days", header: "Retard (j)", numeric: true, sortValue: (i) => i.daysOverdue, cell: (i) => i.daysOverdue },
     { id: "balance", header: "Reste dû", numeric: true, sortValue: (i) => i.balance, cell: (i) => <Money value={i.balance} /> },
   ];

   export default function OverduePage() {
     const { data, isLoading } = useInvoices({ status: "overdue" });
     return (
       <Page>
         <PageHeader title="Retards" count={data?.length} />
         <PageBody flush>
           <DataTable columns={columns} rows={data ?? []} getRowId={(i) => i.id} loading={isLoading} />
         </PageBody>
       </Page>
     );
   }
   ```

2. `app/routes.tsx`: `import OverduePage from "@/pages/overdue";` and `{ path: "overdue", element: <OverduePage /> }`.
3. `app/nav.ts`: an entry into the "Finance" group (`{ to: "/overdue", label: "Retards", icon: … }`).
4. New entity written by ERP ? Add its line in `INVALIDATE` (`queries.ts:232`) and its type of entity in
   `ActivityEvent["entity"]` (`packages/shared/src/domain.ts:316`).
5. `make check` (typecheck + guard). Components: only `@/ui`, never `<select>` or `<input type="date">`.

Reference pages to be copied: `pages/clients` (list), `pages/client-detail` (fiche), `pages/activity` (flux).

### Traps

- A changed type Python side does not break the web compilation: you need to update `packages/shared/src/*.ts` by hand.
- `AppShell` imposes `min-w-[1024px]`: the UI is not made for mobile.
- The chat keeps its history in memory of the module: reloading the page loses it (the AI service does not know it).

---

<a id="donates"></a>
## 7. Data

### What it is

Your company pack: `DATA_DIR/seed/*.json` (the ERP tables) and `DATA_DIR/context/` (documents)
`DATA_DIR=./data` in the team zip; mounted read-only in Docker (`/data`).

### Key Files

`DATA_DIR/seed/*.json`, `DATA_DIR/context/*.md`, `DATA_DIR/context/clients/`, `DATA_DIR/context/suppliers/`,
`apps/backend/app/crud/__init__.py` (`PACK`), `apps/backend/app/core/datapack.py`, `apps/backend/app/services/context.py`.

### How it works

**Files seen → tables** (`crud/__init__.py:31-50`). Reference Pack Size Orders:

| File | Table | Content | 的 lines |
|---|---|---|---|
| `meta.json` | `meta` | `{company, today, currency, generatedAt}` | 1 object |
| `clients.json` | `clients` | contact, zone, delivery days, conditions, ceiling, status, preferences, notes, tags | 46 |
| `products.json` | `products` | catalogue, unit, price, cost, alias, shelf life | 66 |
| `suppliers.json` / `supplierPrices.json` | `suppliers` / `supplier_prices` | | 10 / 94 |
| `clientPrices.json` | `client_prices` (key `clientId\|productId`) | negotiated prices | 63 |
| `priceRules.json` | `price_rules` | price rules (groups, volume) | 16 |
| `lots.json` / `stockMovements.json` | `lots` / `stock_movements` | stock by lot, movements | 3 270 / 15 833 |
| `orders.json` / `purchaseOrders.json` | `orders` / `purchase_orders` | 3 years of sales / purchases | 2 192 / 696 |
| `invoices.json` / `payments.json` | `invoices` / `payments` | | 1 780 / 544 |
| `routes.json` / `routeRuns.json` | `routes` / `route_runs` | tours | 6 / 80 |
| `clientEvents.json` / `supplierEvents.json` | `client_events` / `supplier_events` | historical relational | 2 015 / 500 |
| `tags.json` | `tags` (key\)|(id`) | groups | 23 |
| `contextEntries.json` | `context_entries` | context sheets | 641 |

The activity log (`events`) is not in the pack: it is empty after a reset. File missing = empty table.

**Context table**: one plug = `{id, entityType, entityId?, kind, title, body (markdown), tags, source}`.

- `entityType`: `company` (no `entityId`) - `client` (`cli_…`) - `supplier` (`sup_…`) - `product` (`prd_…`) -
  `category` (an id of `seed/categories.json`, specific to each company; `GET /api/categories`).
  Checked for writing (`services/context.py:_check_target`).
- `kind` : `policy`, `procedure`, `preference`, `fact`, `relationship`, `pricing`, `logistics`, `risk`.
- `source`: `seed` or the actor who wrote it (`user`, `ai_chat`, `voice_agent`, `services/context.py:153`).
- The old packs name `entityType` "`scope`": converted to loading (`datapack.py:32-36`).
- `GET /api/context/for?entityType=client&id=…` = entity records + related records (as load `get_context`).

**Documents `DATA_DIR/context/`**:

- `*.md` of the first level (company, standard day, product glossary, customer playbook, price and credit,
  Deliveries): **collated whole in the fast system** at each turn (`prompts.py:89-96`).
- `clients/*.md`, `suppliers/*.md`: persona cards for ** the human who plays the client** on the phone.
  **pas** read by the agent; what the agent knows about a client is in the context table.

**Reset**: `make reset` (= `POST /api/admin/reset`) reloads the seed and emptys the journal; all entries are
`make clean` also removes the Docker base volume.

### Extend

Adding knowledge for the agent: a plug via the UI **Contexte**, `POST /api/context`, the `save_context` tool, or a
`.md` more in `DATA_DIR/context/` (attention to the size of the prompt). Change the seed then `make reset` to
to leave your own data.

### Traps

- In Docker, `DATA_DIR` is mounted as read-only: modify the seed is done on the host, then `make reset`.
- `make reset` also erases everything the agent has learned (`save_context`) and the activity log.
- The team zip uses `DATA_DIR=./data` (already set in your `.env`).

---

<a id="tests"></a>
## 8. Tests and quality

### What it is

Offline Python tests for AI service, a typecheck and web safeguards.

### Key Files

`apps/ai/tests/` (`test_clients.py`, `test_speech_providers.py`, `test_tools_and_mock.py`, `test_jev.py`),
`scripts/check-no-native-controls.sh`, `scripts/check-no-native-date.sh`, `apps/backend/tests/parity.py`.

### How it works

| Command | Done | Prerequisite |
|---|---|---|
| `make test` | `cd apps/ai && uv run pytest -q`: Registered flow adapters, tool diagrams, mock, Jev — no network | uv on machine |
| `make check` | `pnpm --filter @kit/web typecheck` + `scripts/check-no-native-controls.sh` (no native `<select>` or `<input type="date">`) | Node 22 + pnpm |
| `make types` | generates `packages/shared/src/generated/{backend,ai}.ts` since both `/openapi.json` | services launched, Node + pnpm |

`apps/backend/tests/parity.py` compared the ERP Python to an old API TypeScript: it is not useful during the
There are no backend unit tests.

<a id="tester-noi"></a>
### Expand: Test a tool or agent without the UI

```bash
make chat                                   # terminal : appels d'outils et résultats affichés, /reset, /exit
curl -s localhost:4100/tools | python3 -m json.tool | less          # schémas vus par le modèle
curl -N localhost:4100/chat -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"il reste du bar ?"}],"mode":"voice"}'
curl -N localhost:4100/command -H 'content-type: application/json' -d '{"text":"montre-moi le stock de turbot"}'
curl -s localhost:4100/stt -H 'content-type: audio/webm' -H 'x-mock-text: test' --data-binary @/dev/null
```

A tool alone, in Python (since `apps/ai`, ERP launched):

```python
# uv run python -c "import asyncio; from app.tools import TOOLS, ToolContext, ErpClient; ..."
import asyncio
from app.tools import TOOLS, ErpClient, ToolContext

ctx = ToolContext(erp=ErpClient("ai_chat", "test"), actor="ai_chat")
print(asyncio.run(TOOLS["get_product_stock"].run({"productId": "prd_0001"}, ctx)))
```

A test without ERP: on the model of `test_tool_validates_arguments` (`tests/test_tools_and_mock.py:35`), which calls
`tool.run({...}, ctx=None)` on a tool that does not use `ctx`. WebSocket scripted: send `{"type":"start"}` and
`{"type":"text","text":"…"}` (no microphone required).

**Suppliers mock** (no key): `MockLLM` includes some French intentions ("it's the Poissonerie
Lemoine, "l'il reste du bar?", "4 kg de bar", "confirms the order" ...) and calls the **real** tools, one by
Step (`clients/mock_llm.py`); this is not an agent model. `MockSTT` returns the header `x-mock-text` if it is
provided (`/stt`, `/command`), if not `MOCK_STT_TEXT`. `MockTTS` returns a WAV mime silencer `audio/x-mock-wav`.

---

<a id="pieges"></a>
## 9. Known traps and limits (checked in code)

| # | Trap | Where | Consequences / circumvention |
|---|---|---|---|
| 1 | **Memory voice history** (`conversations`) | `services/voice_session.py:68` | lost each time you restart AI service, including auto reloading of uvicorn when you save a file from `apps/ai/app` |
| 2 | **Warnings do not block anything**: blocked customer, credit ceiling, insufficient stock, unserved area, price below cost = `warnings` | `services/orders.py:85-139`, `:274-276` | `confirm_order` still succeeds; it is to the prompt or a tool to refuse |
| 3 | **Indice STT optional voice**: `audio_start` accepts `hint`, but the Voice page does not send | `services/voice_session.py`, `features/assistant/useVoiceSession.ts` | without `hint`: no vocabulary (customer names, products) and the STT mock hears `MOCK_STT_TEXT`; send `hint` to `audio_start` to activate it |
| 4 | **STT after release**: `transcribe_stream` is not connected | `clients/base.py:81-88` | no partial text while the caller speaks |
| 5 | Only `*.md` **First level** of the `DATA_DIR/context/` go in the quick | `agent/prompts.py:92-94` | `clients/` and `suppliers/` are not seen by the agent |
| 6 | `meta` (company, date) **en cache 60 s** side AI; `settings` read only once | `agent/prompts.py:70-86`, `config.py` | changing `.env` requires restarting |
| 7 | **Types TS handwritten **; `make types` written in `generated/`, not exported | `packages/shared/src/index.ts` | update `domain.ts` / `api.ts` / `ai.ts` with each schema change |
| 8 | **Barge-in without rollback** | `services/voice_session.py:158-164` | a ERP writing part before the interruption remains done |
| 9 | **Max 8 steps** then drop message | `agent/loop.py:38`, `:93-97` | `AGENT_MAX_STEPS` or composite tools |
| 10 | Command **space without memory**; regex navigation of French verbs + last entity seen | `services/command.py:40`, `:121` | "and adds 2 kilos" doesn't know what order we're talking about |
| 11 | The TTS is waiting for a ** in sentence followed by a ** space | `services/voice_session.py:235` | a long first sentence delays the first sound; the last sentence leaves at `finish()` |
| 12 | `thinking` (Anthropic) and `thoughtSignature` (Gemini) blocks kept ** in memory of the ** process, without limit | `clients/anthropic.py:22`, `clients/gemini.py` | After restarting, an old cat history is returned without them |
| 13 | Base ERP **mono-process**, synchronous services | `core/db.py` | no `--workers`; heavy calculation blocks the API |
| 14 | The LLM mock calls ** only one tool per step** | `clients/mock_llm.py` | Mock latency measures don't say anything about real parallelism |
| 15 | The chat history is ** sent integer** to each message | `features/assistant/chat-store.ts:86` | it grows without limit; "New conversation" emptys it |
