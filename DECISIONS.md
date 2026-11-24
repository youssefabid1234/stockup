# DECISIONS – Team 12 · Le Fournil Occitan

> Deliverable read by the jury: the problem chosen and why, our technical choices, what worked or not, our measurements.
> Each adds its ** choices to the ** waterline (what, why, tried and abandoned), in its section.

## 1. The problem chosen: the telephone standard

**Qui**: Lucie, the only one at the standard from 5h30 to 13h, and the three salesmen who seize 71 % from the hand controls.
**When**: especially between 12h and 15h (pic to 13h: 4 755 orders over 3 years), when bakers pass their
orders after the morning shot.
**What it costs today**: 45 % orders arrive by phone (11 231 / 24 769) and are all re-typed
in the ERP; one error (10 kg instead of 10 bags, one replacement not accepted, one delivery promised one day of
(a) is immediately paid for products which perish.
**Why the voice**: a baker has his hands in the flour at 13h; he calls, he doesn't type.
**What the agent changes**: it takes the order during the call, checks stock and account, proposes and argues a
replacing only if the client accepts them, rereads them, and the command is in the ERP at the end of the call.
Planned extension: claims and issues in the same appeal.

## 2. Architecture (summary)

Kit base agent + 6 activable bricks (`TEAM_*`): waiting phrases and keyboard noise, agents in parallel
(fast + brain), preloaded customer plug, super-product tool, "just order" rules, "good seller" rules.
Detail: `docs/team/README.md`.

## 3. Measures

Median and worst case on our scenarios (`scripts/run_scenarios.py`, `--voice` for vocal times). t0 = relaxation
the Space key (push-to-talk).

| Version | sttMs | llmFirstTokenMs | ttsFirstByteMs | totalMs | perceivedMs | Successful scenarios | Cost/call |
|---|---|---|---|---|---|---|---|
| Original kit | | | | | | | |
| + … | | | | | | | |

**Silence heard by the caller** (mar. 24/11 02h00, Maison Sarrailh, 4 replicas: command, "yes but put it on
12", price, "it's good, validate"; true keys, WS `/voice` in text (add ~0,3-0,5 s transcription to the
the received MP3 stream is replayed as the browser, durations read in the MP3 headers and checked with ffprobe):

| Adjustment | Agent opens the call | 1er sound after sentence (median / worse) | Useful ready answer | Silence heard before the end of the reply |
|---|---|---|---|---|
| `TEAM_FILLERS=0` (kit) | No | 3,0 s / 5,0 s | 2,2–4,8 s | all this time (2,3–5,0 s) |
| `TEAM_FILLERS=3` | no ("Hello" played after the 1re sentence) | 0,0 s / 0,8 s | 2,1–4,3 s | up to 1,4–1,9 s of a block |
| **`TEAM_FILLERS=4` (default)** · Jury configuration | **yes, 0,3 s** after the form | **0,0 s / 0,0 s** | 2,8–6,3 s | **0,0 s** |
| **+ `TEAM_ROUTER=1` (default)** · Targeted accused + Haiku for single replicas | yes, 0,4 s | 0,0 s / 0,4 s | **2,2 s** (2,6–3,3 s on Sonnet); "thank you, goodbye" **0,7 s** | **0,0 s** |

**Routage of model** (`agent/router.py`, `TEAM_ROUTER`): a replica made solely of confirmation or politeness
("it's good, validate", "yes", "perfect", "thank you, goodbye") leaves on the fast model (Haiku, `TEAM_FAST_MODEL`),
all the rest (product, quantity, price, change of mind, complaint) on Sonnet. Measured with our settings: first word
0,45–0,57 s (Haiku) versus 1,19–1,33 s (Sonnet). Confirmation remains verified by Jev (accord 0,94 in 190 ms on
Haiku). These lines no longer trigger "Very good, I check" (useless and slow): the accused is only said if the agent
Codes ERP ("CMD-2026-007543", `prd_…`) are removed from the pronounced text, regardless of the
Replay `--voice`: S01, S30, S31, S32, S33 PASS; S02 PASS 2 times on 3 (3e, model
fast asks for the amount of strong flour left blurred at the 1 tower instead of confirming: it does not invent).

First reading (23/11, via /chat, without audio): S03 (client blocked) PASS, 6 099 ms, first word at 4 092 ms; default
Note: the agent pronounces his reasoning ("The account is blocked; I do not take orders...").

## 4. Selection by construction site

### Speed and voice (Mohamed Amine)

- Two very short announcements are prepared at the opening with the configured voice. Short gusts of three strokes are generated in memory and spaced during long searches. Only one oral restart resumes the quantity and product heard if the request is clear, or says "One moment, I check". The following sounds are cancelled when the answer is ready or if the client interrupts the agent. The sounds share the interruptible segment of the response. The first sound and the first synthesis byte of the useful response are timed separately.
- If the transcription is not enough to detect a search request, the first confirmed ERP call can trigger the ad. The voice keeps the basic jargon if the ERP is unavailable. Integration tests also cover audio shutdown after an error and repeated ads.
- The current orchestrator delegates to the agent ERP. The ads remain active according to `TEAM_FILLERS` and the final answer cancels the wait. The mode 3 adds the keyboard during the preparation of the quick recovery. The tone and the instruction against duplicates are offered to Daycem in the [follow](docs/team/status/mohamed-amine.md).
- Local replay via WebSocket, demo data and three simulated suppliers, with and without `TEAM_FILLERS`: **3 replicas on 10** pass in both configurations. S06 and the two replicas of S10 pass. S01 and S05 fail on their business expectations. On S11, the simulated model launches a search on "thank you". An integration test checks that even in this case the voice does not play an ad or keyboard. The microphone reference measurements, the perceived delay and the first round ElevenLabs remain to be noted on the pack of the Fournil.
- T7 optional is postponed. Space provides a reproducible starting point to measure the delay and interrupt the agent during demo.
- **Mode 4 "zero silence" (taken by Amine Khalil, Mar. 24/11 02h00), team failure.** Start measurement: in 3 mode
  the agent did not speak first and left blanks from 1,4 to 1,9 s (the keyboard was waiting for 1,4 s then returning
  all 2,2 (s) What changes : (1) **the agent opens the call** from the "Who calls?" form ("Hello
  Ma'am, what can I do for you?", synthesized during the loading of the file, played as soon as it is ready:
  0,2–0,3 s), and its first answer does not say "Hello" again; (2) ** immediate accused** on each request ("Agreed,
  I look at this," "Okay, I see that," "Very good, I check," prepared for opening) — nothing about "yes" / "thank you";
  (3) **Continuous keyboard**: clips from 0,45 s (6 different rhythms) sent just before the audio already sent
  runs out (the browser plays a single stream and never stalls), stopped at the first audio byte of the answer (not to sound)
  text : the synthesis time is covered also) ; at most 0,6 s keyboard still in line at this time. Result :
  0,0 s of silence heard on the 4 replicas (table §3). The 1-3 modes are unchanged.
- Tests: `tests/test_no_silence.py` (8 tests); `tests/conftest.py` resets `TEAM_FILLERS` to zero for each test (the
  follow-up gave different results depending on the `.env` of each): 232 tests pass with `TEAM_FILLERS` 0, 1, 3 and 4.

### Several agents, preloaded plug, super tool (Youssef)

**T3 / T4 · Lightened prompt (`TEAM_SLIM_PROMPT=1`, defect; taken from Amine Khalil, mar. 24/11 03h00).** Each call to the
model was rereading 34 400 tokens (the Anthropic cache works: almost everything is "cache read").
company 55 % (the 6 `data/context/*.md`, especially the catalogue tables), diagrams of the 25 tools 24 %, rules and
the rest. The catalogue (alias, prices, shelf life) is already given on request by the tools (`search`,
`resolve_product`, `product_insight`, `quote_line`) and the customer profile covers status, habits and stock.
`agent/context_digest.py` keeps, extracted from the same files at each turn: house rules, day situation,
team, time limits, billing, ambiguous aliases, usual substitutions, seasonality, order taking, customers
Blocked, claims, prices / price rules / credit, touring. Background 39 016 → 13 996 characters (−64 %).

| Measurement (`/chat`, Sarrailh, 4 replicas, 3 calls, medians) | Full prompt | Alleged |
|---|---|---|
| Tokens read by model call | ≈ 34 400 | **≈ 21 600 (−37 %)** |
| Ordering · « put in twelve » · price · « confirm » | 7,2 · 4,6 · 3,5 · 4,0 s | **6,4 · 4,1 · 3,1 · 3,5 s** |
| Sum of the 4 replicas | 19,3 s | **17,1 s (−11 %)** |
| Command just in the ERP | 3/3 | 3/3 |

Time saving is modest because the cache makes the rereading fast: time comes mainly from the tokens written
(200 to 430 per replica: tool calls + sentence) and the number of return trips. The gain of **cost** is net (−37 % of
Scripts (`/chat`): S01, S05 (3/4, waiting `get_price`), S30, S31, S32, S33 PASS; S03 PASS after setting to
day of waiting (preloaded sheet makes `search` useless); S02 unstable **with both prompts** (1 success)
complete on 3 in both cases: "as usual" + rupture AOP) — with the quick lightened agent opens 2 times on 3 by
the break rather than the usual basket. Rule added: name the product as the customer ("traded"), never the name
catalogue (without the glossary, the agent said "Floor T fifty-five French tradition").

**T4 · One round trip for an order (`place_order`, Mar. 24/11 03h40).** Time was no longer from the rereading
quick (cache) but number of round-trips model tools: "Ten bags of tradi for Thursday" cost 3 to 4 calls
to the model (day + product, then draft, then reread, then sentence). `tools/order_place.py` makes this chain
deterministic in the code : day (`delivery_answer`), products (alias of the catalog, otherwise Jev with the habits of the
customer), units ("3 cartons" of laminating butter → 30 kg; 1,6 sack → one asks, never rounded), writing (new
draft, or modified current order: quantity, line to 0 removed, other day), reread (`review`). Nothing is
written if the day is impossible, the ambiguous product or the account blocked: "next" says what to ask.

| Measurement (`/chat`, Sarrailh, 3 calls, median) | Full prompt | Lightweight prompt | **+ `place_order`** |
|---|---|---|---|
| Ordering · « put in twelve » · price · « confirm » | 7,2 · 4,6 · 3,5 · 4,0 s | 6,4 · 4,1 · 3,1 · 3,5 s | **3,6 · 3,4 · 3,2 · 3,6 s** |
| Sum of the 4 replicas | 19,3 s | 17,1 s | **13,8 s (−29 %)** |
| Tokens read for command (1re replica) | 137 416 | 86 488 | **43 934 (−68 %)** |
| Command just in the ERP | 3/3 | 3/3 | 3/3 |

In voice (board configuration, 4 mode, routing): response to command ready in 3,7 s (6,1–6,3 s before), validation
2,0 s, goodbye 0,6 s, 0,0 s of silence. (`/chat`, `--reset`) : S01 S02 S03 S04 S05 S30 S31 S32 S33 S40 all
PASS, one command opened each time (S05 4/4 for the first time). Scenario expectations accept
now `place_order` where they requested `create_draft_order` / `update_order_line` / `review_order`, and
`quote_line` where they requested `get_price`; S05/S40 accept "eighty-two".

**Start measurement (T0, Mon. 23/11 23h, `TEAM_ORDER_RULES=1`, other bricks extinguished).**
`totalMs` = end of client → first audio byte of agent (`--voice`, sentence typed without STT); this is the
metric of the jury. Via /chat (without audio) we measure the full turn: the text only arriving at the end, it is almost
the same thing (S01·1 : 7 286 ms /chat, 6 883 ms voice).

| Scenario · reply | Tools called (one by one) | /chat | `--voice` totalMs | Result |
|---|---|---|---|---|
| S01·1 "10 Tradi Bags for Thursday" | search, get_context, check_delivery_date, get_product_stock, create_draft_order | 7 286 ms | 6 883 ms (LLM 6 739 + TTS 144) | PASS |
| S01·2 "Yes, confirm" | confirm_order | 2 377 ms | 3 340 ms | PASS |
| S05·1 "3 cartons of AOP laminating butter" | search, get_client, get_context, get_product_stock, check_delivery_date | 7 928 ms | – | PASS |
| S05·2 "How much is the 82?" | get_price | 4 856 ms | – | PASS |
| S05·3 / S05·4 | none | 2 116 / 1 942 ms | – | FAIL (note "Closed Wednesday") |

Play: slow replicas (7-8 s) are those where the model chain 5 tools, one by one; the voice (TTS) weighs only
≈ 0,15 s. Targets: less round-trips (super tool, preloaded plug) and earlier sound (faster agent),
Mohamed Amine waiting phrases).

**T2 · Preloaded customer form (`TEAM_PRELOAD`, Mon. 23/11 23h50).** As soon as the customer is identified (get_client, or
a search that only returns a customer), its card (status, delivery days ERP, preferences, usual shopping cart
**with stock**, stock, notes) is loaded in the background, in parallel, then added at the end of the prompt
The following replicas ("no longer calls get_client or get_context"). The notes "Closed the <day>" are removed
when the ERP delivers today (decision: ERP and history are true).

Measurement via /chat, `--reset`, `TEAM_ORDER_RULES=1`, 9 replicas (S01, S02, S05):

| | Switch off | Lighted |
|---|---|---|
| Successful replicas | 9/9 | 9/9 |
| 1re replica of each call | 7,6 · 5,7 · 4,7 s | 6,9 · 6,2 · 5,5 s (identical: not yet known) |
| Next replicas (median) | 2,7 s | 4,4 s (noise ±1-2 s, no measurable gain) |
| S02 "put in 12" | recreates a draft and rereads **tout** the usual (11 lines) | ** modifies the line** and rereads 1 line |
| S05 (note "Closed Wednesday") | Don't talk about Wednesday | asks "You are well open Wednesday?" (read via get_context on the 1er round, before the card) |

Reading: With the full history (corrected replay tool), the agent **ne was already looking more for the client** after the 1er
turn: the plug does not remove a call to the following turns. **Time is lost at the 1er turn** (4 to 6 tool calls)
before the customer is known). The file remains **deactivated by default**; next step: identify the customer
from the beginning of the 1er round (fiche in parallel to the reflection) and the super-tool produced.

**Identification before the call ("Who calls?", Mar. 24/11 0h20).** True life: WhatsApp number / telephone
The standard is displayed, the customer knows the standard before picking up. Demo: on the Voice page, a mandatory form (client)
selected from the list of the ERP, search by name / city / phone, contact on the phone; or "New customer") then
"Start the call": the file is loaded (-) 0,5 s) **avant** the first word and given to the agent from the 1re replica.
New (temporary) client: the agent takes the request without confirming anything, the team validates the account.

Measurement via /chat, `--reset`, `TEAM_ORDER_RULES=1`, pre-call scenario client:

| 1re replica | Without (TEAM_PRELOAD=0) | With the announced caller |
|---|---|---|
| S01 "10 Tradi Bags for Thursday" | 6 tools, **7,7 s** | 3 tools (date, draft, rereading), **3,5 s** |
| S01 in **voix** (end of speech → 1er sound) | **6,9 s** (T0) | **3,9 s** (LLM 3,75 + TTS 0,16) |
| S02 "as usual for Thursday" | 4 tools, 5,6 s | 1 tool, **3,9 s** |
| S05 "3 cartons of AOP laminating butter" | 4 tools, 5,4 s | 2 tools, 4,7 s |
| S05 replica 3 (note "Closed Wednesday") | asks "Wednesday is right for you?" | no longer speaks of Wednesday (filtered note) |

Reading: the 1re replica loses 2 to 4 s and 2 to 3 round-trips (no more searching for the customer or his card); voice
6,9 to 3,9 s. The following replicas do not change (noise ±1-2 s). `TEAM_PRELOAD` changes to 1 in
`.env.example`.

** fixed game tool**: in /chat it now returns the complete history (tools called + results) as the
Voice page; before, the agent forgot his draft and started again (S01·2: 6 tools, 9,4 s → 1 tool, 2,4 s).

**T1 · Super product tool (`TEAM_PRODUCT_INSIGHT`, mar. 24/11 1h30).** True life: a glance at the screen of Lucie
`product_insight(client, produit, quantité)` reads in parallel the product (stock, arrivals), the price of CE
customer, substitutes for the ERP, the price sheet and rules; if the product is missing, it calculates the customer price of the
each replacement (in parallel), says if the customer accepts a replacement (`substitution_policy` of Daycem) and class
the replacements (`rank_alternatives` of Daycem: the substitute documents first). **Promo** = the price applied comes
a **dated ** (validTo) rule and is below the catalogue price: never invented (a permanent group discount is not
not a promotion). Client who refuses: no substitute returned.

Measurement via /chat, ERP reset and then demo promo recreated (`setup_demo_data.py`), `TEAM_ORDER_RULES`,
`TEAM_PRELOAD`, `TEAM_SALES_RULES` = 1, 1re replica, 2 tests (3 for S04 after correction):

| 1re replica | Turn off | Lighted |
|---|---|---|
| S04 Sarrailh, AOP in rupture, refuses replacements | 2 tools · 3,8 / 4,3 s | 2 tools · 3,6 / 3,5 / 3,5 s, 3/3 PASS |
| S05 Colomier Petrin, AOP in rupture | 5 and 3 tools · 6,6 / 5,8 s | 2 tools (product_insight, date) · 2,8 / 4,9 s |
| S40 demo scene (promo) | 3 tools · 4,2 / 4,3 s | 2 tools · 3,9 / 2,9 s |
| S40 in **voix** (totalMs) | – | 4,6 s |

Play: 1 to 3 return less; median S05 6,2 → 3,9 s, S40 4,3 → 3,4 s, S04 4,1 → 3,5 s. With the tool,
the agent quotes the exact promo (8,46 €/kg, -8 % until 30/11) in the first 4 replicas S05/S40. Two traps
corrected during measurement: notes CRM of the ERP are objects (the tool was crashing, the agent was ironed by the
old tools), and without instructions the agent recorded the "first arrival" request of Sarrailh without his consent
(+2 s) : the tool now reminds **propose** first. The remaining failures of the scenarios do not come from
the tool (S05·2 waits for get_price while quote_line of Amine K. responds; S05·1 said "eighty-two" in
letters; S40·4 requests "separate order or addition?". `TEAM_PRODUCT_INSIGHT` moves to 1 in `.env.example`.
** Robust Hands-Free Listening (Youssef, 24/11).** Test Problem: Speaking multiple times, only the last one
piece counted (a piece cut in full transcription was thrown away). Now: the pieces not yet answered
(`Conversation.pending`) depart in numbered UN message; Soniox separates the voices (`enable_speaker_diarization`) and
gives a word-based confidence → `[appelant] … [autre voix] …` and `mot(?)` for the model only (text displayed and
relu remains raw); sets "Listen" in vocal mode. Verified in real: audio 2 voice → " [other voice] Say, you want a
coffee ?" isolated and "T145(?)" (T55 misunderstood) marked; the agent includes "10... no 12" = 12, ignores coffee,
Ask for the dubious flour again.

### Fair command (Amine Khalil)

**Mission**: what ends up in the ERP is exactly what the customer wanted (good product, good quantity, good day,
`TEAM_ORDER_RULES` switch (set by default in `.env.example`). Code:
`agent/rules_order.py` (rules + deterministic functions), `tools/delivery.py`, `tools/order_review.py`,
`tools/order_edit.py`. Guideline: **The model speaks, the code calculates** (dates, units, prices, alerts).

**Start point (T0, kit only, Mon. 23/11 22h20, /chat)**: S01 PASS but the agent "thinks out loud" before
greet ("Thursday is a delivery day...") and recheck 6 tools before confirming (9,4 s); **S02 FAIL**
("as usual" = the last command read in full, no draft, never confirms); S03 PASS but says
"You are closed on Wednesday" (false), quotes an internal accounting rule and does not take the message.

**Decisions**

| # | Decision | Why? |
|---|---|---|
| D1 | **The delivery days of the ERP are authentic**; the notes "Closed on Wednesday" are ignored, only the customer can announce a closure | 9 customers have this note while the ERP delivers them on Wednesdays, and the history confirms it (e.g. Muret Petrin: 10 deliveries on Wednesdays after the note; Au Fournil de Philippe is only delivered on Wednesdays). The original agent refused or wrongly moved (S05 delivered Monday 30/11). Youssef also removes these notes from the preloaded sheet. |
| D2 | **Dates calculated by code** (`next_delivery_date`, tool `check_delivery_date`) | Customer days, time limit 17h, Lauragais-Tarn the day before 12h, toured part of 6h30: a calendar, not an intuition. "Wednesday" for Sarrailh → "not delivered on Wednesday, next day: Thursday 26 November". |
| D3 | **One single command per call**: tools `update_order_line`, `remove_order_line`, `change_delivery_date`, `cancel_draft_order` | The kit only knew how to add lines: in the "final twenty", the agent created a 2e command and left the draft to 200 bags in the ERP (see S31). |
| D4 | **Ready calculated before confirmation** (`review_order`) | Ready-to-say rereading phrase, translated ERP alerts for the customer (blocked, ceiling, no tour, "there are only..."; never an accounting figure or margin), franco 150 € excl. VAT (12 € otherwise), quantity ≥ 5× the habit to be confirmed, `canConfirm`. The ERP returns alerts but does not block anything. |
| D5 | **Doubl guarantee** in `review_order` (`duplicateDrafts`, `sameDayOrders`) | A draft forgotten by the agent next to the correct order can be confirmed by the ADV → double delivery. Identical duplicate → abandoned; different draft → reread to the customer who chooses; drafts WhatsApp / e-mail never cancelled. |
| D6 | **Prices calculated by code** (tool `quote_line`) | When listening to a S05 recording, the agent calculated his head and corrected himself live ("92 euros the slab... pardon, 18 euros 40"). The customer price comes from the ERP (`/api/prices/resolve`); the code makes packaging and multiplications ("9 euros 20 per kilo, that is 92 euros the carton of 10 kilos; 276 euros excluding taxes for 30 kilos"). |
| D8 | **Jev decides the two small risky decisions** (`tools/order_jev.py`): "Is it a real yes?" before `confirm_order` (which keeps its name: the scenarios of the team work as they do) and "what product?" for an ambiguous word (`resolve_product`) | Recommended by the CTO. Calibrated on 12 true answers: "yes it is good", "good deal" → 0,89–0,96 chord; "yes but put four", "and add rye", "wait", "how much?" → chord ≤ 0,14. Thresholds: ≥ 0,8 confirms, ≤ 0,3 does not confirm, between the two → reapply. 159–196 ms per decision on real appeal. Products: exact name of catalog first (without model), otherwise Jev with customer habits ("laminating butter" → AOP at Sarrailh 0,82; request AOP / 82 % / margarine at Petrin de Colomiers 0,28); under 0,6 the agent asks. Without key Jev: behavior of kit. |
| D7 | **Short and mandatory rules** (`ORDER_RULES`, ~12 lines) rather than long text | The prompt is reread at each step: each rule responds to an observed defect (do not think aloud, units, "chocolatine", "as usual" = usual shopping basket summarized, confirm directly to the "yes", account blocked = message recorded with `log_client_event`). |

**Measurements** (scenarios replayed with real keys; `--voice` = real voice path, time = end of sentence → 1er audio byte)

| Scenario | Kit only | With `TEAM_ORDER_RULES=1` | In the ERP after call |
|---|---|---|---|
| S01 simple command | PASS · 11,1 s / 9,4 s | PASS · 7,4 s / 2,6 s (`--voice`) | 1 confirmed command |
| S02 as usual + "put in 12" | **FAIL** 2/3 | PASS 3/3 · confirmation 3,4 s | 1 order, 12 tradi |
| S03 customer blocked | PASS (false statements) | PASS · registered message, nothing promised | no orders |
| S05 rupture AOP → 82 % | **FAIL** 2/4 (issued Monday, draft unconfirmed) | PASS 4/4 | 1 order, Wednesday 25/11 |
| S30 under Franco | – | PASS 3/3 ("12 euros delivery... 147 euros missing") | 1 command, 153,90 € |
| S31 "200 bags" instead of 20 | – | PASS 3/3 ("You say two cents?") | 1 order, 20 bags |
| S32 modify + remove a line | – | PASS 3/3 | 1 order, 15 tradi, without rye |
| Simulated forgotten draft (200 tradi) | – | reread to the customer and then cancelled at his request | 1 confirmed + 1 cancelled |
| S33 "Yes but put in twelve" (with Jev) | – | PASS 3/3 · modified line, confirmed by Jev (accord 0,95) | 1 order, 12 tradi |

With Jev (Mars. 24/11, 00h50, `--voice`, reset before each scenario): S02, S30, S31, S32, S33 PASS; S05 3/4
(round 2: the agent gives the price with `quote_line`, the scenario awaits `get_price`); 8 confirmations on 8 validated by
Jev in 159–196 ms; one command just in the ERP at each call.

S05 recorded in audio (client = 2e voice ElevenLabs, agent = true answer): 68 s → 56 s call after D6, price
Just the first shot. Tests: 28 tests on the right command (`test_rules_order.py` + `test_team_todo.py`); the
full crew suite passes (151 tests at Mar. 24/11 01h00), switch turned on or off.

**What hasn't worked / limits**
- The `/chat` mode replay script only played the text: the agent lost the draft's id and recreated one
  (false duplicates on S05 at Daycem). Corrected by Youssef (full history); our safeguards also cover this case.
- The rereading of a complete "as usual" (9 products) remains long in the oral.
- The times remain from 2 to 9 s per replica depending on the number of tools: the bulk of the gain comes from the construction sites of the
  Mohamed Amine and Youssef (waiting phrases, preloaded plug, fast agent).
- My tests do not cover the transcription (text sent directly) or listening to the voice: to be validated by the microphone.
### Good seller (Daycem)

## 5. Edited data for demo

**Promo demo on the laminating butter 82 % (Daycem, T4), assumed and fictional.** Created by the API of the ERP with
`scripts/setup_demo_data.py`, because `data/seed/` is not in git:

- price rule `Promo tourage 82 % : −8 % jusqu'au 30/11`: Bakery group × 82% laminating butter
  (`prd_0026`), -8 % on the catalogue price, from the day of the ERP (24/11) to the end of the month; the note of the rule says that
  It's demo data;
- effect: 9,20 € → **8,46 €/kg** for bakeries without negotiated price (e.g. Le Pétrin de Colomiers). A negotiated price
  still wins (La Gerbe d'Or remains at 8,82 €); other customers remain at 9,20 €;
- Why: the demo scene "breaks the AOP laminating butter → replacing **in promo**, argued, with agreement".
  quotes the promo that because `get_price` returns it (rule "never invented promo") ;
- **automatic from 24/11 (Youssef)**: the ERP adds it itself to each data load (1er start,
  `make reset`, reset button, `run_scenarios.py --reset`): `apps/backend/app/core/team_demo.py`, whether or not
  rule, id `prl_0900`. Before, every reset erased it and the demo scene fell (see during the T1 measurements).
  The Daycem script remains usable (it answers "already there").

**Ready for the jury (Youssef, 24/11).** Tested on a new clone with only `data/seed/` reset and a base
empty: `make setup` failed ("Permission Denied": `.sh` scripts were not executable since
Windows) → fixed in git. `make setup` also adds to `.env` the missing `TEAM_*` switches (values of
`.env.example`, without touching an existing line), so that a `.env` from elsewhere does not turn off our bricks.
ERP + promo (8,46 €), 7 switches, registered team tools, site and agent responding.

## 6. What didn't work / gave up
