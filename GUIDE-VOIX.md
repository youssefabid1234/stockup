# GUIDE-VOIX.md — make a fast and natural vocal agent

This guide explains how a voice agent works "on the phone", what the kit does today, what it measures,
and **where to change the kit** to go faster and sound more human. The jury judges on *smart, fast, natural*, with
a special prize for the fastest (end of speech → first sound, measured in demo): this guide mainly covers *fast*
and *natural*

What this guide does not repeat: installation ([SETUP.md](SETUP.md)), challenge ([BRIEF.md](BRIEF.md)), detail of the
code ([TECH.md](TECH.md), sections 1.3, 4 and 9), the concepts of agent LLM (loop, tools, context, cache,
Models, Jev: [GUIDE-AGENTS.md](GUIDE-AGENTS.md)], WebSocket protocol ([apps/ai/README.md](apps/ai/README.md#ws-voice-protocol)).

Number reading rule: ** numbers measured ** come from a real test on the kit (November 2026).
other number is marked ** order of magnitude**: this is a hypothesis to be measured in you, not a promise.

## Contents

1. [Anatomy of a speech tower](#anatomie)
2. [Metrics](#metriques)
3. [What the kit measures today](#mesures)
4. [Accelerate, technical by technique](#accelerer)
5. [Sonner naturel](#naturel)
6. [Robustesse](#robustesse)
7. [Providers of kit](#fournisseurs)
8. [Attachment plan for 24 h](#plan)

## I want... → section

| I want... | Section | Files |
|---|---|---|
| understand where the time of a tour starts | [1](#anatomie), [3](#mesures) | `apps/ai/app/services/voice_session.py` |
| know what to measure and how to prove it to the jury | [2](#metriques), [8](#plan) | `apps/web/src/pages/voice/metrics.tsx`, `DECISIONS.md` |
| transcribe while the appellant speaks (does) | [4.1](#stt-streaming) | `services/utterance.py`, `services/vocabulary.py`, `clients/soniox.py` |
| delete push-to-talk (VAD) | [4.2](#vad) | `apps/web/src/features/assistant/useVoiceSession.ts` |
| reduce model time | [4.4](#cache) à [4.6](#outils) | `clients/anthropic.py`, `clients/factory.py`, `tools/` |
| make to wait without white | [4.7](#fillers) | `voice_session.py` (`Speaker`) |
| that figures and dates are well stated | [4.10](#deterministe), [5](#naturel) | `agent/prompts.py`, `tools/` |
| manage interruptions | [5.2](#barge-in) | `voice_session.py` (`interrupt`), `useVoiceSession.ts` |
| change voice or supplier | [7](#fournisseurs) | `.env`, `clients/factory.py` |

---

<a id="anatomy"></a>
## 1. Anatomy of a speech tower

### Two architectures

**In cascade** (what the kit does): three models in a row.

```
voix de l'appelant ─▶ STT (parole → texte) ─▶ LLM (+ outils ERP) ─▶ TTS (texte → parole) ─▶ haut-parleur
```

**Speech-to-speech** (realtime native audio models): one model listens to audio and produces audio.

| | Cascade | Speech-to-speech |
|---|---|---|
| Latency | sum of the steps, unless they are straddling (streaming) | one step less, often shorter |
| Monitoring | read and correct each step (transcript, text, tool calls) | blacker box; text available according to supplier |
| Tools / ERP | any LLM with tool calls | depends on the realtime model |
| Votes | we choose the best French voice in the market | the voice of the model |
| In the kit | ready, with your keys | **not provided**, and no realtime key is distributed |

Tip for 24 h: Keep the cascade and ** clear the steps**. That's where the seconds are earned.

### The kit pipeline, in time

Voice Tower of the Voice Page (`WS /ai/voice`, `services/voice_session.py`, `VoiceConnection.run_turn`):

```
temps ─────────────────────────────────────────────────────────────────────────────────▶
appelant  [■■■■ parle (Espace enfoncé) ■■■■]│relâche = t0
navigateur MediaRecorder webm/opus, trame toutes les 100 ms ─▶ serveur ─▶ STT en flux (Soniox)
          ◀── transcription partielle affichée en direct ──│
serveur                                    │[finalize]│ texte final
                                           │          │[── LLM ─▶ outil(s) ERP ─▶ LLM ──]
                                           │          │                     texte ─▶ Speaker
                                           │          │                     │[TTS phrase 1]─▶ 1er octet mp3
navigateur                                 │          │                     │   SegmentPlayer (MediaSource) joue
          ◀──────────────── totalMs : t0 → premier octet audio envoyé par le serveur ─────────▶
```

Key points of the code:

- **Push-to-talk**: Low space = `audio_start`, released = `audio_end` (`useVoiceSession.ts`, `startTalking` /
  `stopTalking`). No end of speech detection: it is the release that gives it.
- **STT live**: at `audio_start`, the session opens a `Utterance` (`services/utterance.py`) that opens the stream
  of STT; each frame of 100 ms (`rec.start(100)` in `useVoiceSession.ts`) is transmitted to it upon receipt.
  Partial transcripts are displayed during support. At release, Soniox receives `finalize` and renders the
  last words; `run_turn` starts the agent on this final text. If the stream breaks, the full recording is
  transcribed as before (`transcribe`). Customer and product names are added to the STT index
  (`services/vocabulary.py`).
- **LLM en streaming** : `run_agent(..., mode="voice")` (`agent/loop.py`) émanife le texte au fil de l'eau ; les tools
  of the same stage rotate in parallel (`asyncio.gather`).
- **TTS sentence by phrase**: `Speaker.push` cuts as soon as a sentence ends with `. ! ? …` followed by a space
  (`Speaker.SENTENCE`) and send it to TTS; a worker synthesizes the sentences in order; the whole turn forms a
  only mp3 segment.
- **Reading**: `SegmentPlayer` (`features/assistant/audio-player.ts`) plays mp3 from the first byte via
  MediaSource.
- **Command ** Space (`WS /ai/voice/command` voice, `POST /ai/command` keyboard; `services/command.py`):
  even STT live, agent without history, but the TTS carries on **tote** the response once finished (not
  On Windows, Alt+Space is taken by the system: use the **Order** tab on the page
  Voice (Space or the microphone button).

---

<a id="metrics"></a>
## 2. Metrics

### The one the user feels

**End of speech → first sound of the agent.** This is the "fastest" price. All the rest is only its
decomposition:

| Metric | Definition | What Pilots her |
|---|---|---|
| Endpointing | actual end of speech → the system *decide* that the caller has finished | push-to-talk: 0 (the release); VAD: the silence expected |
| Latency STT | end of speech → final transcript available | STT in flow or not, supplier |
| TTFT LLM (*time to first token*) | start of the model call → first text token | quick size, cache, model, effort |
| Round trip tools | each tool call = one more model call + ERP call | number of steps, composite tools |
| TTFB TTS (*time to first byte*) | text sent to TTS → first audio byte | supplier, hot connection, length of the 1re sentence |
| Reading | first byte received → audible sound | buffer drive, network |

### Speaking tours

- **VAD** (*voice activity detection*): detect voice. **Endpointing**: decide that a turn is over
  (silence rather long, full sentence). Too short = caller cut; too long = troublesome white.
- **Barge-in**: the appellant speaks while the agent is speaking. The audio of the agent must be cut immediately,
  cancel the work in progress and listen.

### How the kit measures them

`TurnTimings` (`apps/ai/app/schemas/chat.py`) is filled at each turn and sent to `agent_done` (voice) or `done`
(command):

| Field | Measured where | Sense |
|---|---|---|
| `sttMs` | `run_turn` / `run_command` | release (t0) → final transcription |
| `llmFirstTokenMs` | first `TextEvent` | start of agent → first token **of text** (tools included if they pass before) |
| `llmTotalMs` | end of `run_agent` | all the agent, including tools |
| `ttsFirstByteMs` | `Speaker._speak_queued` | call TTS of the 1re sentence → first byte |
| `totalMs` | `Speaker.first_byte_at - t0` | **t0 → first audio byte sent** (voice); in command: t0 → end of all |
| `perceivedMs` (navigator) | `useVoiceSession.ts`, `markPerceived` | → release audio **plays** in the browser |

Page **Voix** displays these values per turn and their average (`pages/voice/metrics.tsx`): green under 1,5 s, orange
under 3 s, red beyond for `Total` and `Perçu`.

Note: in `commande` mode, `totalMs` includes all the TTS (the complete synthesis), so it does not compare to the
`totalMs` voice mode.

### Measuring in demo

- Show column **Preview** on the Voice page: this is the ear-side metric.
- If you switch to VAD, **t0 changes**: this is the last moment of voice detected, not the time the VAD decides.
  Count the endpointing silence in your number, otherwise the jury will see it.
- Independent countermeasure: record the call (micro + speaker) and measure the white on the waveform
  in any audio editor.
- Rate median ** and ** worst case on your scenarios (5 to 10 calls), not the best turn.

---

<a id="measures"></a>
## 3. What the kit measures today

Real test, November 2026, **before live transcription** (4.1): LLM Anthropic Sonnet 5.5, STT Soniox, TTS
ElevenLabs, appellant's sentence of approximately 4 seconds, a tool call. The totals below therefore include
the old STT; since then, they are about the duration of this STT.

| Step | Measured | Reading |
|---|---|---|
| STT | **3,4 to 4,9 s** (before live transcription) | Soniox only started after `audio_end`. **Since 4.1, the audio starts during the speech**: at the release only the last words remain to be finalized, the final text arrives a few hundred ms after. Not yet remedied: measure `sttMs` at home. |
| LLM, first token | **≈ 4,2 to 4,4 s** including tool return | the model calls a tool before saying anything |
| TTS, first byte | **170 to 370 ms** hot ; **≈ 1,9 s** at first call (cool) | ElevenLabs is fast once the connection is open |
| Total `/command` | **8,4 s** | |
| Total vote (WS) | **9,6 s** | |
| Prompt | **≈ 27 000 tokens input by call model**, before cache | rules + all `DATA_DIR/context/*.md` + tool diagrams, returned to each step |

What that means is:

1. **The text of the LLM comes from almost a block after the tools**: first token ≈ last token.
   sentence-by-phrase to TTS already exists but does not earn much as long as the answer only arrives at the end.
2. There was ** two major posts** : on STT (≈ 4 (s) and LLM with his tools (≈ 4 (s) The STT is treated
   ( live transcription, 4.1). **The remaining major item is the LLM and its tools.** The TTS (≈ 0,3 (s) is already
   good when hot.
3. The following "easy" gain: make agent ** speak before ** tools (4.7).

---

<a id="accelerate"></a>
## 4. Accelerate, technical by technique

Executive Summary:

| # | Technical | Expected gain | Where in the kit | Difficulty |
|---|---|---|---|---|
| 4.1 | STT streaming during speech — **fait**; rest: vocabulary, Finalize Deepgram | most 3,4–4,9 s of STT (made) | `services/utterance.py`, `services/vocabulary.py` | easy (the rest) |
| 4.2 | VAD / endpointing instead of push-to-talk | natural ; latency = silence expected | `useVoiceSession.ts`, or STT endpointing | Medium |
| 4.3 | Run LLM on a stable partial transcript | part of the TTFT | `voice_session.py` | difficult |
| 4.4 | Quick cache — **in place** | TTFT and cost on 27k tokens | `clients/anthropic.py` (to be checked) | easy |
| 4.5 | Smaller model / routing | TTFT | `.env`, `clients/factory.py`, Jev | easy to medium |
| 4.6 | Less back and forth tools | one model call per tool avoided | `tools/`, `agent/prompts.py` | Medium |
| 4.7 | Fillers during tools | first sound before the tools | `Speaker`, `agent/prompts.py` | easy |
| 4.8 | TTS in flow and cutting earlier | small today | `Speaker`, `clients/elevenlabs.py` | easy to medium |
| 4.9 | Hot connections | 1,6 s on the 1er turn (1,9 s cold vs 0,3 s hot) | `VoiceConnection.open` | easy |
| 4.10 | Short answers, deterministic code | fewer tokens generated | `agent/prompts.py`, `tools/` | easy |
| 4.11 | Data cache, preloading | ERP calls avoided | `tools/`, `prompts.py` | Medium |
| 4.12 | Regions/colocation | network | infra | depends |

<a id="stt-streaming"></a>
### 4.1 STT streaming while the caller speaks

**Fait.** The browser sends a frame every 100 ms; the server forwards it to STT upon receipt
(`services/utterance.py`). During the speech, the Voice page (Call and Command) and the HUD space display the text
heard live: final words in normal color, provisional words in italic grey (`transcript` with
`final: false`). On release, Soniox receives `{"type": "finalize"}` and returns the last words immediately; the turn
the agent starts on this final text. If the stream breaks, the full recording is transcribed as before.
STT simulates partials: the display is tested without a key. Details: TECH.md, "Live Transcript".

**The vocabulary counts.** A generic STT means "the monk" for "Lemoine", " turbos" for " turbot".
The server therefore adds to the STT index the names of customers, products and their aliases read in the ERP
(`services/vocabulary.py`): Soniox receives them in `context.terms`, Deepgram in `keyterm`. The proper names of your
A name misunderstood is a bad customer or a bad product in the order.

**What you can still improve.**

- Launch the LLM on a stable part before release ([4.3](#llm-partiel)).
- Hands-free mode: finish the turn on `<end>` tokens from Soniox or VAD ([4.2](#vad)).
- Finer vocabulary: contact names, customer's usual basket once identified, terms of your profession.
- Deepgram ends again with `CloseStream` (waiting closure): `{"type": "Finalize"}` would be faster.

<a id="vad"></a>
### 4.2 Endpointing / VAD instead of push-to-talk

**Idea.** No one presses a key on the phone. Two options:

- **Browser side**: The micro level is already calculated (`meter()` in `useVoiceSession.ts`, `AnalyserNode`).
  Start `audio_start` above a threshold, send `audio_end` after N ms of silence.
- **STT** side: Real-time STTs know how to report the end of a statement (endpointing).
  today `UtteranceEnd` messages; Soniox returns control chips (`<end>`, `<fin>`) that
  `soniox.py` jumps. These are the two entry points.

**Gain.** Especially *natural*. For *fast*, waiting silence is added to latency: order of magnitude
300 to 800 ms depending on the setting. Measure with noise (market, kitchen): a threshold too low never ends the turn.

**Difficulty.** Medium. Keep Space as backup mode for demo.

<a id="llm-partial"></a>
### 4.3 Start LLM on a partial transcript (speculative)

**Idea.** With 4.1, the text is almost complete before the end of the speech (parts already arrive at the server:
`on_partial` in `Utterance`). When the part has not moved since
for a short moment, throw the agent; if the final transcript differs, cancel and restart.

**Where.** `voice_session.py`: The turn task already cancels clean (`interrupt()`, cancellation asyncio).

**Guarde-fou.** A ERP part write does not cancel (TECH.md, trap 9). Speculate only on the steps in
read (`search`, `get_product_stock`, `get_price`...), never on `create_draft_order` / `confirm_order`.

**Difficulty.** Difficult; to do after 4.7 and cache verification (4.4).

<a id="cache"></a>
### 4.4 Quick cache

**Idea.** ≈ 27 000 tokens identical (rules, company context, tools) are returned to **each** model call,
The supplier's prompt cache rereads this prefix instead of reprocessing it.

**Where.** `clients/anthropic.py` now sets three cache points (`cache_control`): last tool, quick
system, last block of conversation. Check that it takes: `cache_read_input_tokens` in `usage` of
`POST /ai/chat` event `done` (the voice session does not return `usage`: log it if necessary).

**What breaks the cache** (prefix byte for byte): modify a `DATA_DIR/context/*.md` during the call (remarked to
each turn), add the time or id in the prompt system, change the order or list of tools, change from
The cache expires after a few minutes without calling.

**Gain.** Certain cost; TTFT: to be measured before/after on your scenarios. Reduce the context (only put what you need to do)
the tour needs) help in addition.

<a id="model"></a>
### 4.5 Smaller model, routing

- **Change model without code**: `LLM_MODEL=` in `.env`, then `make restart`. Anthropic failure of the kit:
  `claude-sonnet-5-5` (`DEFAULT_MODELS`, `clients/factory.py`). A Haiku (`claude-haiku-5-5`) responds faster and
  cheaper; check that he calls the tools on your difficult scenarios.
- **`LLM_EFFORT=low`** (failure of the kit) keeps the reflection short; only mount it if the tricky tricks fail.
- **Routage**: a small model for single towers ("yes", "that's all", "thank you"), the big one when it comes to
  reason. To classify the round, **Jev** answers closed questions (choice, yes/no, score) with
  probabilities: `get_jev_client()`, examples `agent/jev_examples.py` (`pick_product`, `is_yes`). Nothing in
  the default agent only calls it: to plug in to `run_turn` before `run_agent`.

<a id="tools"></a>
### 4.6 Less tool back and forth

Each tool call costs one more model call (the model repeats all the prompt), plus the ERP call.

- **Composite tools**: a tool that makes "find the product + stock + customer price" in one call. Example
  complete in [TECH.md 5.4](TECH.md#outil-composite).
- **Preload the client at the beginning of the call**: if you know who is calling, load its file (`GET /api/context/for`,
  `get_client`) to `start` and add to `parts` in `build_system_prompt` (`agent/prompts.py`).
  no longer needs `search` + `get_client` + `get_context` in the first round. Put ** at the end** of the prompt
  system not to break the rest cache.
- **In parallel tools**: the loop already runs in parallel the tools requested in the same step
  (`asyncio.gather` in `loop.py`). Tell the model in the prompt ("calls the independent tools)
  The LLM mock only calls for one per step: measure with a real model.
- **Small returns**: A tool that returns little JSON is read more quickly at each step.

<a id="girls"></a>
### 4.7 Fillers and restarts during tools

**Idea.** Without a waiting sentence, the agent was silent during the tooling (-) 4 s measured and then responded with a block. A short sentence ** before ** tools
("I'm looking," "Two seconds, I'm checking the stock.") gives a first sound early.

**Where.**

- By the prompt: `VOICE_RULES` (`agent/prompts.py`) recalls that any written text is pronounced in order,
  even between two tool calls. It allows ** not more than a very short waiting sentence before the first tool**
  ("I look."), then nothing between the tools; the real answer comes only once, at the end. This text
  of the pre-tool goes to TTS as soon as punctuation is completed (`Speaker`). The model does not do this every time: measure.
- By code (more reliable, faster): on the first `ToolCallEvent` of the round, if nothing has yet been said,
  `speaker.speak("Je regarde.")` in `run_turn`. Even faster: a small mp3 **pre-synthesized** at startup
  (no TTS calls at the time required), to be sent in the audio segment of the tour.

**Honesty.** A girl counts as the first sound, but a systematic "uh, I look" gets along.
Keep it short, and tell in `DECISIONS.md` what your number measures (first useful sound or girl).

### 4.8 TTS: cutting earlier, streamer

- **Already done**: sentence by sentence, one mp3 segment per turn, read from the first byte.
- **Copy earlier**: `Speaker.SENTENCE` waits for `. ! ? …` followed by a space; the last sentence only leaves to
  `finish()`. Cut also at commas for the **first** sentence shortens the first sound (at the price of a
  sometimes chopped prosody: listen).
- **TTS by WebSocket**: you open a connection, you send the text to the water, the audio returns in stream.
  ElevenLabs offers such an input API (see their documentation); the kit customer uses the route
  REST `/stream` (`clients/elevenlabs.py`). Earns especially useful when the LLM really streams its text (after 4.6)
  and 4.7).

### 4.9 Hot connections

**Measured**: first call TTS ≈ 1,9 s, then 170–370 ms. The kit already shares a customer HTTP
(`clients/http.py`, `http_client()`) which keeps TLS connections open.

**Where.** In `VoiceConnection.open()`, start a tiny synthesis (a word) and, if you do so
a short model call: the first real turn finds everything open. Same idea for the ERP (`erp_http()` in
`tools/erp.py`, already in keep-alive).

<a id="determinist"></a>
### 4.10 Short Responses and Deterministic Code

- **Court**: Each token generated is paid in time and audio. `VOICE_RULES` requests 1 to 2 sentences; hold it.
- **Code instead of model** for what does not need reflection: unit conversion, total calculation,
  Dates ("Next Thursday" → date ISO from `today` of the ERP), put in numbers words. A tool or a
  Python function is faster and is not wrong. The kit has no function "number → French spoken"
  (`format_number` from `tools/catalog.py` only `5.0 → "5"`): Write it down if your answers read prices.

### 4.11 Data cache, preloading

The catalogue and negotiated prices of a customer move little during a call. Keep in memory, for the session, this
that the agent has already read (customer sheet, quoted products) and serve it from the tool without recalling the ERP.
stock, which changes during demo (ERP is alive).

### 4.12 Regions and co-location

Each provider adds a network round trip. In demo you are on the place's Wi-Fi: test on site, keep
If a supplier offers a European region, prefer it (order of
size: tens of milliseconds per transatlantic return).

---

<a id="natural"></a>
## 5. Natural ringing

### 5.1 Speaking tours

- One idea, one question per turn (`VOICE_RULES`: "One question at a time").
- Short phrases: they leave earlier at TTS ** and ** listen better.
- No "Other thing?" on each turn: on the phone, we let the other talk.

<a id="barge-in"></a>
### 5.2 Barge-in

**What the ** kit does: a new `audio_start` or `text` calls `interrupt()` (`voice_session.py`): the turn is
canceled, the TTS feed is closed (`aclosing`), what has been heard and said remains in the history with "...".
browser, `startTalking` shuts down playback (`stopPlayback`).

**About **:

- In push-to-talk, the interruption only exists if the caller presses Space. With a VAD (4.2), you must detect
  the voice **dependent** that the agent speaks: the microphone is opened with `echoCancellation: true`, but test with a
  Speaker, otherwise the agent interrupts himself.
- The history keeps the text **generated**, not what was **entensified**: if the caller cuts in the middle, the model
  Just keep the sentences from which the audio left.
- A ERP write already left is done: reread the command on the next round.

### 5.3 Figures, units, oral dates

- "12 kilos", "18 euros 50 per kilo", "Thursday 26", never "18.50 €/kg" or "2026-11-26".
- The prompt asks (`VOICE_RULES`), but the safest is **formater in code** (4.10) and give to
  value model already ready to say.
- Sizes and trade codes ("30/40", "T3") say as the trade says (see [METIER.md](METIER.md)
  and the glossary of your `data/context/`).

### 5.4 Review and confirmation

- A command is created in draft and is confirmed only after explicit agreement on the summary
  (`BASE_RULES`). Oral: Summary **court**, quantities and products, then a closed question.
- "yes go," "that's good," "no wait": a yes/unreliable is a good place for Jev
  (`is_yes` in `agent/jev_examples.py`); low confidence = request again.

### 5.5 never read identifiers

`cli_0020`, `prd_…`, `CMD-2026-…`: the model sees them in the tool results. `VOICE_RULES` bans ids
For a command number useful to the caller, just say the last digits.

### 5.6 Voice and Prosody

- ElevenLabs `eleven_flash_v2_5` (default) is the quick choice. The default voice is a premade voice
  Multilingual: Choose a French ** voice** in your ElevenLabs library and put its id in
  `TTS_VOICE`.
- Gradium (voice en-FR, default "Armand") is supported in the code, but you do not have a Gradium key (section 7).
- Punctuation controls prosody: commas for breaks, dots to finish. Avoid parentheses, dots
  oblique bars, abbreviations.

### 5.7 Tone adapted to the contact person

The `data/context/clients/*.md` sheets describe each client: temperament, "How he/she speaks", tics of
**They are not in the quick by
default** (only `*.md` of the first level of `data/context/` go there, TECH.md trap 6).
the caller (4.6) and tell the model to adapt register and tutoire.

---

<a id="robustness"></a>
## 6. Robust

| Problem | What We Do | Where |
|---|---|---|
| Misunderstood names ("wolf" / "bar", customer names) | the ** index STT** already contains the names of the customers, products and alias of the ERP (`context.terms` Soniox, `keyterm` Deepgram); add your terms | `services/vocabulary.py`, or `hint` of `audio_start` |
| Ambiguous product or customer | `search` is blurred; if there are several candidates, ask which one (`BASE_RULES`); Jev `pick_product` gives confidence | `tools/catalog.py`, `agent/jev_examples.py` |
| Suspicious critical cunning (quantity, date, unit) | repeat the value and ask confirmation **before ** write; "five" and "fifty" merge | prompt + tool |
| Not heard. | The kit returns "Nothing heard — try again"; in VAD, prefer a natural revival ("Hello? Can you hear me?") | `run_turn` |
| Silence of the appellant | restart after a delay, then polished closure | to be added (timer session) |
| Supplier error (401, 429, failure) | readable `error` message (`provider_error`); provide a fold: other model, pre-recorded sentence of apology | `clients/http.py`, `clients/factory.py` |
| Noise, accents, hesitations | the microphone is open with noise reduction and gain control; test your scenarios with real background noise | `ensureMic` in `useVoiceSession.ts` |
| Call cut in full order | the history lives in memory, by `sessionId`; the browser reconnects with the same id. The draft command remains in the ERP: on return, find it rather than create a second one | `conversations` in `voice_session.py` |
| Restart service AI | voice history is lost (including automatic reloading when saving a file from `apps/ai/app`) | TECH.md trap 2 |

---

<a id="suppliers"></a>
## 7. Suppliers of the kit

**Keyphones**: Each team received keys for **Soniox** (STT), **ElevenLabs** (TTS), **Anthropic** (LLM) and
**Jev** (decisions). Deepgram, Gradium and OpenAI are ** supported in code** but **no key is provided**
for them: don't count on it without your own key.

| Role | Supplier | Kit failure | Transport | Key provided |
|---|---|---|---|---|
| STT | **Soniox** | `stt-rt-v6`, `language_hints: ["fr"]`, index terms | Real-time WebSocket, `transcribe_stream` used live, `finalize` released | yes |
| STT | Deepgram | `nova-3`, `language=fr`, `keyterm` | WebSocket live (`transcribe_stream`, end by `CloseStream`); REST in rescue | No |
| STT | Gradium | `default` | REST; webm re-encapsulated in Ogg (`clients/audio.py`) | No |
| STT | OpenAI | `gpt-4o-mini-transcribe` | REST | No |
| TTS | **ElevenLabs** | `eleven_flash_v2_5`, voice `JBFqnCBsd6RMkjVDRZzb`, `language_code=fr` | REST `/stream`, mp3 | yes |
| TTS | Gradium | `default`, votes en-FR `F7Iib4MAyHIRed0x` | REST NDJSON, PCM → mp3 (`Mp3Encoder`) | No |
| TTS | OpenAI | `gpt-4o-mini-tts`, `alloy` | REST, mp3 | No |
| LLM | **Anthropic** | `claude-sonnet-5-5`, `LLM_EFFORT=low` | SSE | yes |
| Decision | **Jev** | `jev-latest` | REST | yes |

**Configuration** (`.env`, then `make restart`): `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY`, `STT_LANGUAGE`;
`TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`, `TTS_API_KEY`, `TTS_LANGUAGE` ; `LLM_PROVIDER`, `LLM_MODEL`,
`LLM_API_KEY`, `LLM_EFFORT`; `JEV_API_KEY`. Detail: [apps/ai/README.md](apps/ai/README.md#environment) and
[SETUP.md](SETUP.md#change-model-or-voice).

** Audio formats**:

- Enter: the browser saves in `audio/webm;codecs=opus` (Safari: `audio/mp4`). Soniox accepts it as is
  (`audio_format: "auto"`, not mp4) Test on Chrome.
- Output: **all TTS renders `audio/mpeg`** (mp3): the drive concatenates the sentences of a turn in one segment.
  A new TTS that renders PCM must pass through `audio.Mp3Encoder`.
- Mock: `audio/x-mock-wav`, the browser reads the text with `speechSynthesis`; the latency measured in mock does not
  Tell nothing about the real suppliers.

---

<a id="plan"></a>
## 8. Attack plan for 24 h

### Latency budget

Target: **less than 1,5 s** from end of speech to first sound (the green of the Voice page). This table is a budget
at ** check** in your home, not one measure: only the column "Today" is measured, and these measurements date
before the live transcript.

| Step | Today (measured) | Target (order of magnitude) | Technical |
|---|---|---|---|
| Endpointing | 0 (push-to-talk) | 0 in push-to-talk; 300–800 ms in VAD | 4.2 |
| STT after end of speech | 3,4–4,9 s **before live transcription**; now: final text a few hundred ms after release (to be remeasured) | ≈ 0,2–0,5 s | 4.1 (fact), vocabulary |
| First sound of the agent after the transcript | 4,2–4,4 s (LLM + tool) | ≈ 0,5–0,8 s | girl 4.7, cache 4.4, model 4.5, preload 4.6 |
| TTS first byte | 170–370 ms (hot), 1,9 s (cold) | 0,2–0,3 s, never cold | 4.9 |
| **Total** | **8,4 s (command), 9,6 s (voice)**, before live transcription | **< 1,5 s** | |

Reading: the STT is already in flux; with a pronounced waiting sentence **avant** tools, the first sound does not
Depends more on the time of the tools. The useful answer comes then; reduce it with 4.4 to 4.6.

### Recommended order

1. **First measure** (H3–H8): your 5–10 scenarios, real keys, note `sttMs`, `llmFirstTokenMs`,
   `ttsFirstByteMs`, `totalMs`, `perceivedMs` in `DECISIONS.md`.
2. **Hot connections** (4.9) and **daughter** (4.7): one hour, visible gain immediately.
3. **Affiner le STT** (4.1, déjà en flux): enriching the vocabulary (`services/vocabulary.py`: contacts, cart
   usually, trade terms), switch Deepgram to `Finalize` if you use it, then start the LLM on the partials
   stable (4.3).
4. **Customer preload + composite tool** (4.6), **Cache verification** (4.4).
5. **Model / routing** (4.5): only if your scenarios remain correct.
6. **VAD** (4.2) if there is still time; save Space for live demo.
7. After **each** change: replay the scenarios, compare the numbers and success rate.
   But fake doesn't win.

### Prove in Demo

In `DECISIONS.md`, a table before/after by technique:

| Technical | sttMs | llmFirstTokenMs | ttsFirstByteMs | totalMs | perceivedMs | successful scenarios |
|---|---|---|---|---|---|---|
| original kit | | | | | | |
| + … | | | | | | |

Give the median and worst case, say what your t0 measures (retreading or ending of detected voices) and if the
first sound is a girl. Live, keep the Voice page open: **Total** and **Perçu** chips speak for themselves.
