# AI service (Python · FastAPI) — LLM · STT · TTS · agent

Port **4100** (`AI_PORT`). Talks to the ERP API (`ERP_API_URL`, port 4000) over plain HTTP, like any other client.
No vendor SDKs: every provider call is a readable `httpx` request, so you can see how streaming works and swap providers.

Usually you start everything from the repo root (`make up` with Docker, `make dev` without: see
[SETUP.md](../../SETUP.md)). To run this service alone, from `apps/ai`:

```bash
uv sync                                         # Python 3.12, deps from uv.lock
uv run python -m app.main                       # the service (AI_PORT, default 4100)
uv run uvicorn app.main:app --reload --port 4100   # same, reloads on save
uv run python -m app.cli                        # chat with the agent in your terminal (--voice: spoken style)
uv run pytest                                   # offline tests (provider adapters, tools, mock)
```

With no keys at all (`LLM_PROVIDER=mock`, `STT_PROVIDER=mock`, `TTS_PROVIDER=mock`) everything runs: the mock LLM
understands a few French intents and calls the real ERP tools. API docs: <http://localhost:4100/docs>.

## Architecture

```
            web app (React)                                   ERP API (:4000)
   /ai/chat   /ai/command   /ai/voice (WS)                         ▲
       │            │             │                                │ HTTP, header x-actor
┌──────▼────────────▼─────────────▼───────────┐                    │
│ routers/   chat · command · voice · speech · health  (thin: parse, call, stream)
│ services/  command.py (one-shot)   voice_session.py (push-to-talk, barge-in, TTS per sentence)
│ agent/     loop.py  ── model ⇄ tools loop ──►  tools/  @tool functions ─┘
│            prompts.py (rules + company context .md + ERP "today")
│ clients/   LLMClient · STTClient · TTSClient  ──►  OpenAI · Anthropic · Gemini · Deepgram · Soniox · ElevenLabs · Gradium · mock
│ schemas/   THE wire contract (Pydantic, camelCase JSON) → /openapi.json
└─────────────────────────────────────────────┘
```

```
app/
  main.py        FastAPI app, CORS, 400 error shape, OpenAPI (incl. event / WS message unions)
  config.py      env vars (+ repo-root .env), defaults
  cli.py         terminal chat
  schemas/       chat.py (messages, ChatStreamEvent), command.py, voice.py (WS messages), service.py
  clients/       base.py (interfaces), factory.py, one file per provider, mock_llm.py, mock_speech.py, http.py, ws.py, audio.py
  agent/         loop.py (run_agent), prompts.py, jev_examples.py (copyable Jev helpers, not wired in)
  tools/         registry.py (@tool), erp.py, catalog.py, context.py, history.py, orders.py
  routers/       health.py, chat.py, command.py, speech.py, voice.py, sse.py
  services/      command.py, voice_session.py
tests/           adapters against recorded-style SSE, tool schemas, mock parsing
```

## The agent loop (`agent/loop.py`)

```
system prompt + conversation ──► model ──► text? ──────────────► stream it ──► done
                                   │
                                   └► tool calls ─► run them in parallel (ERP API) ─► append results ─► model again …
```

`run_agent(messages, llm=…, tools=…, mode=…)` is an async generator of `ChatStreamEvent`
(`text`, `tool_call`, `tool_result`, `done`, `error`) — exactly what `POST /chat` streams.
It appends the new assistant / tool messages to `messages`, so whoever keeps that list keeps the full history.
At most `AGENT_MAX_STEPS` (8) model calls per turn. A tool that raises becomes `{"error": "..."}` for the model.
To stop a turn (barge-in, client gone), cancel the asyncio task that iterates it.

The system prompt (`agent/prompts.py`) = rules + mode rules (`chat` | `voice` | `command`) + company and "today"
from `GET /api/meta` (the data pack has its own simulated date) + every `DATA_DIR/context/*.md`, re-read on each turn.

## Add a tool (about 10 lines)

In `tools/` (an existing domain file, or a new one imported in `tools/__init__.py`):

```python
from pydantic import Field
from .registry import ToolContext, tool

@tool
async def list_overdue_invoices(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> list[dict]:
    """Factures en retard d'un client. Overdue invoices of a client."""
    invoices = await ctx.erp.get("/api/invoices", {"clientId": client_id, "status": "overdue"})
    return [{"number": i["number"], "balance": i["balance"]} for i in invoices]
```

- The **docstring** is the description the model reads: say *when* to use the tool.
- The **parameters** become the JSON schema (`client_id` → `clientId` for the model). Optional: `x: str | None = None`;
  enums: `Literal["a", "b"]`; nested objects: a `ToolArgs` subclass (see `OrderLine` in `orders.py`). Arguments are validated.
- Return **small** JSON (the model re-reads it on every step). Raise to report an error.
- `ctx.erp` already sends `x-actor: ai_chat | voice_agent`, so the ERP activity feed shows what the AI did, plus
  `x-actor-name` percent-encoded (accents OK). It has `get`, `post`, `patch` and `delete` over one shared connection pool.
- The function must be `async` with annotated parameters; `@tool` replaces it with a `Tool` object (call
  `await TOOLS["name"].run({...}, ctx)` in tests). Use `@tool(name="…")` to rename it.
- The return value must be JSON-serializable: a non-JSON value (datetime, set, object…) becomes `{"error": …}` for that
  call only (`execute_tool`), so the model sees a failed tool, not a failed turn. Return plain dicts / lists / strings.
- Check it: `curl localhost:4100/tools`.

Full walkthrough (decorator internals, the 16 tools, a composite tool, best practices): [TECH.md, section 5](../../TECH.md#outils).

## Add a provider

Implement one interface from `clients/base.py` in a new file, then add a `case` in `clients/factory.py`:

- **LLM** — `LLMClient.stream(request)`: an `async def` generator yielding `LLMText(delta)`, `LLMToolCall(call)`,
  `LLMUsage(...)`. Convert the `ChatMessage` list (user / assistant with `tool_calls` / tool with `tool_call_id` + `name`)
  to the provider's format. Anything that speaks the OpenAI chat-completions format needs no code: `LLM_PROVIDER=openai-compatible`.
- **STT** — `STTClient.transcribe(audio, mime, hint)` → text. **TTS** — `TTSClient.synthesize(text, voice)` → `TTSResult(mime, chunks)`;
  stream the bytes so the first sentence plays early.

### Speech providers

| | STT | TTS | Transport | Browser audio |
|---|---|---|---|---|
| **Deepgram** | `nova-3`, `language=fr`, keyterms from the hint | | REST `/v1/listen`; live WS in `transcribe_stream` | webm/opus as is |
| **Soniox** | `stt-rt-v6`, `language_hints: ["fr"]`, `context.terms` | | real-time WS (also for push-to-talk) | webm/opus as is (`audio_format: auto`) |
| **Gradium** | `default`, `json_config.language = fr`, keyword boosting | `default`, French voice | REST, NDJSON streams | STT: webm re-wrapped to Ogg/Opus (`clients/audio.py`, no re-encode); Safari mp4 refused. TTS: PCM → mp3 on the fly |
| **ElevenLabs** | | `eleven_flash_v2_5`, `language_code=fr` | REST `/stream` | mp3 |
| **OpenAI** | `gpt-4o-mini-transcribe` | `gpt-4o-mini-tts` | REST | webm / mp3 |

- **Every TTS returns `audio/mpeg`**: the web player streams mp3 through MediaSource and plays a turn's sentences as one
  segment (concatenated mp3 plays; concatenated WAV / Ogg would not). Raw PCM from a provider → `audio.Mp3Encoder`.
- **Errors** read `"<provider> HTTP <status>: <body> — <hint>"`; the hint names the usual cause (bad key, rate limit / quota,
  audio format) and the voice UI shows the message as is.
- **Barge-in** cancels the turn: TTS streams are closed (`aclosing`), WebSockets close when their `async with` exits.
- **Live transcription**: `STTClient.transcribe_stream(audio_chunks, mime, hint)` yields `STTUpdate(text, final, stable)` (whole
  text so far; `stable` = its final words). Clients with `streams = True` (Soniox, Deepgram, mock) get the push-to-talk audio
  WHILE it is recorded (`services/utterance.py`): partial transcripts go to the browser, and at `audio_end` Soniox only has to
  finalize the last words (`{"type": "finalize"}` → `<fin>`). If the live stream breaks or gives no final words within
  `FINAL_TIMEOUT_S`, the whole recording is transcribed the classic way. The others transcribe after the release.
- **Company vocabulary** (`services/vocabulary.py`): client names, product names and aliases from the ERP (`/api/clients`,
  `/api/products`, cached 5 min) are added to the STT hint → Soniox `context.terms`, Deepgram `keyterm`. Not for the mock STT.

Provider notes: the Anthropic adapter keeps the model's `thinking` blocks and sends them back with the tool-calling turn
(required by recent Claude models); the Gemini adapter does the same for `thoughtSignature` (in-memory, keyed by tool-call id).

## Endpoints

| Route | What |
|---|---|
| `GET /health` | `{ ok, llm: {provider, model}, stt: {provider}, tts: {provider}, erpApiUrl }` |
| `GET /tools` | `ToolInfo[]` |
| `POST /chat` | `ChatRequest` → SSE, one `ChatStreamEvent` JSON per `data:` line |
| `POST /command[?speak=1]` | one stateless, act-first voice command: raw audio body (header `x-mock-text` for the mock STT) or JSON `{text}` → SSE of `CommandStreamEvent`: `transcript` → tool/text events → `navigate` (when the user asked to see something) → `speech` (base64, `speak=1`) → `done` with `timings` |
| `POST /stt` | raw audio body (`content-type` = mime) → `{text, ms}`; header `x-stt-hint` (or `x-mock-text`) |
| `POST /tts` | `{text, voice?}` → audio bytes (streamed), header `x-ms` = time to first byte |
| `WS /voice` | push-to-talk sessions, below |

Errors: `400 {error: {code: "bad_request", message}}` (invalid body), `502` for STT/TTS provider failures.
Every body, event and WS message is a Pydantic model in `app/schemas/` and is published in `/openapi.json`
(`ChatStreamEvent`, `CommandStreamEvent`, `VoiceClientMessage`, `VoiceServerMessage` are discriminated unions on `type`).

### WS /voice protocol

```
client                                         server
start {sessionId?, actorName?}           ──►
                                         ◄──   ready {sessionId, stt, tts, llm}
audio_start {mime, hint?}                ──►   (a new utterance interrupts the agent: barge-in; hint = STT hint, mock STT returns it)
<binary audio frames, every 100–250 ms>  ──►   streamed to the STT as they arrive
                                         ◄──   transcript {track: "caller", text, final: false, stable} …   (live, while speaking)
audio_end                                ──►   (or: text {text} to type instead)
                                         ◄──   transcript {track: "caller", text, final: true}
                                         ◄──   agent_text {delta} …   agent_tool {name, args} / {name, ok, ms}
                                         ◄──   agent_audio_start {mime}, <binary audio chunks>, agent_audio_end
                                         ◄──   agent_done {text, timings}
reset                                    ──►   history cleared, ready again
```

- `WS /voice/command[?speak=1]`: the same live audio for ONE voice command (the ⌥Space HUD): `audio_start`, frames,
  `audio_end` (or one `text`) → `transcript {final: false}` while speaking, then the `POST /command` events as JSON
  messages; closed after `done` / `error`. Closing it earlier cancels the command.
- Each finished sentence goes to TTS right away; the audio of one turn is **one segment** (mp3 chunks concatenate fine).
- `timings` = `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`, `totalMs` (end of caller speech → first agent audio byte).
- Reconnecting with the same `sessionId` keeps the history (in memory, last ~40 messages). An interrupted turn keeps
  what was heard and what the agent had started to say (`… …`).
- **Mock TTS** sends mime `audio/x-mock-wav` (a short silent WAV): the web app ignores the bytes and speaks the text
  with the browser's `speechSynthesis`.

## Jev (decision model)

Jev (TypeSafe AI, model `jev-latest`) is **not an LLM**: it writes no text. You send a `state` (a string or any JSON)
and named, typed questions; it answers each with probabilities, fast. Use it *next to* the LLM for the small decisions
of a voice turn: routing, slot choice, "which product did the caller mean", "is that a yes?". Low confidence = ask the
caller back instead of guessing.

```python
from app.clients import get_jev_client

jev = get_jev_client()                    # JevClient, or None when JEV_API_KEY is empty
if jev:
    d = await jev.choose("5 kilos de bar de ligne", "Quel produit ?", {"prd_1": "Bar d'élevage", "prd_2": "Bar de ligne"})
    d.choice, d.confidence, d.probabilities           # "prd_2", 0.91, {"prd_1": 0.09, "prd_2": 0.91}
    s = await jev.score(message, "Urgence ?", ["peut attendre", "aujourd'hui", "tout de suite"])   # s.score: 0..2
    p = await jev.yes_no({"question": "Je vous mets 5 kg ?", "reponse": "ouais vas-y"}, "Le client accepte.")  # 0..1
    raw = await jev.ask(state, {"intent": choice_question(...), "angry": yes_no_question(...)})       # several at once
```

- Wire format: `POST {JEV_BASE_URL}/v1/systemone`, `Authorization: Bearer <JEV_API_KEY>`, body `{model, state, questions}`,
  answer `{model, answers: {name: {type, …}}, usage}`. Question types: `choice` (criteria = {option: description}),
  `score` (criteria = ordered levels), `noul` (yes/no, answer = probability of yes), `box` (image, use `ask`).
  Full schema: <https://api.typesafe.ai/openapi.json>, docs <https://docs.typesafe.ai>.
- Copyable examples in `agent/jev_examples.py`: `pick_product(jev, utterance, search_results)` → product id or None,
  `is_yes(jev, question, answer)` → True / False / None. The default agent does not use Jev: wire it where you want.

## Environment

| Var | Default | Notes |
|---|---|---|
| `AI_PORT` | 4100 | |
| `ERP_API_URL` | http://localhost:4000 | local mode; Docker sets `http://backend:4000` |
| `DATA_DIR` | `./data` (team zip) | relative to the repo root; company context in `DATA_DIR/context/*.md`. Docker mounts it at `/data` |
| `LLM_PROVIDER` | mock | `openai` \| `openai-compatible` \| `anthropic` \| `gemini` \| `mock` |
| `LLM_MODEL` | per provider | openai `gpt-4.1-mini`, anthropic `claude-sonnet-5-5`, gemini `gemini-2.5-flash`; required for openai-compatible |
| `LLM_API_KEY` | | optional for local openai-compatible servers |
| `LLM_BASE_URL` | provider default | required for openai-compatible: Groq `https://api.groq.com/openai/v1`, Mistral `https://api.mistral.ai/v1`, OpenRouter `https://openrouter.ai/api/v1`, Ollama `http://localhost:11434/v1` |
| `LLM_EFFORT` | low | anthropic only (`output_config.effort`): low keeps latency down |
| `AGENT_MAX_STEPS` | 8 | model ↔ tools round-trips per turn |
| `JEV_API_KEY` | | optional; empty → `get_jev_client()` is None |
| `JEV_BASE_URL` / `JEV_MODEL` | `https://api.typesafe.ai` / `jev-latest` | Jev decision model (see above) |
| `STT_PROVIDER` | mock | `deepgram` \| `soniox` \| `gradium` \| `openai` \| `mock` |
| `STT_API_KEY` / `STT_MODEL` | per provider | deepgram `nova-3`, soniox `stt-rt-v6`, gradium `default`, openai `gpt-4o-mini-transcribe` |
| `STT_LANGUAGE` | fr | language of the caller |
| `MOCK_STT_TEXT` | "Bonjour, il vous reste du bar ?" | what the mock STT "hears" whatever is said (`POST /stt` and `/command` use the `x-mock-text` header instead when given, WS `/voice` the `hint` of `audio_start`) |
| `TTS_PROVIDER` | mock | `elevenlabs` \| `gradium` \| `openai` \| `mock` |
| `TTS_API_KEY` / `TTS_MODEL` / `TTS_VOICE` | per provider | elevenlabs `eleven_flash_v2_5` / `JBFqnCBsd6RMkjVDRZzb`; gradium `default` / `F7Iib4MAyHIRed0x` (Armand, fr-FR); openai `gpt-4o-mini-tts` / `alloy` |
| `TTS_LANGUAGE` | fr | elevenlabs `language_code` (Gradium / OpenAI follow the voice) |

## Ideas to make it smarter, faster, more natural

- One tool that resolves a product and returns stock + client price (saves a round-trip).
- Prefetch the caller's client sheet at `start` and put it in the system prompt.
- Starting the LLM on a stable partial transcript before the caller releases the key; hands-free mode on Soniox `<end>` tokens.
- Filler audio ("je regarde…") while tools run; voice activity detection instead of push-to-talk.
