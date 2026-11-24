# Amine Khalil – 的 "The right command" + 的 voice and T3/T4 (taken from Mohamed Amine and Youssef) · Tue. 24/11 03h00

- Done (03h00) – **prompt lightened** (`agent/context_digest.py`, default `TEAM_SLIM_PROMPT=1`): context -64 %, tokens
  34 400 → 21 600 (−37 %), sum of the 4 replicas 19,3 → 17,1 s, control just 3/3. S03 and S02:
  updated expectations (preloaded sheet; "usual"). S02 remains unstable with both prompts. Detail: DECISIONS.md
  (Section Youssef, "T3 / T4").
- **For all**: add `TEAM_SLIM_PROMPT=1` to your `.env`.
- Done (03h40) – **`place_order`** (T4): day + products + units + writing + editing in UN tool call.
  7,2 → 3,6 s, sum of 4 replicas 19,3 → 13,8 s (−29 %), tokens of the first replica −68 %. Vocal : 3,7 s (instead of
  of the 6,1–6,3). 10 scenarios PASS (of which: S05 4/4), one command each time. 283 tests pass.
- T4 remains (optional): early start on partial transcription (to be validated by the microphone); T6 / S08 claim.

- Done (02h40) – **Haiku / Sonnet** routing (`agent/router.py`, `TEAM_ROUTER=1` by default): "It's good, validate",
  "Yes", "thank you" → Haiku (first word 0,5 s instead of 1,2-1,3 s); the rest → Sonnet. More "Very good, I'm
  check" on a simple confirmation (accused only if there is something to look for). ERP codes never read by voice
  High. Measured: 2,2 s validation (2,6-3,3 s before), "thank you, goodbye" 0,7 s. 272 tests pass. S02: waiting
  `get_client` removed (form is preloaded).
- **For all**: add `TEAM_ROUTER=1` to your `.env`.

- Done (02h10) – **mode 4 "zero silence"** (`TEAM_FILLERS=4`, default in `.env.example`), voice tasks taken from
  Mohamed Amine: Agent ** opens the call** ("Hello Madam, what can I do for you?", 0,3 s after the
  form), ** immediate accused** on each application ("Okay, I'm looking at this"...), ** continuous keyboard** until the first
  the answer sound. Measured in jury configuration: 1er son 0,0 s, **0,0 s silence heard** (before: 3,0 s median
  without waiting, white from 1,4–1,9 s in 3 mode). Detail and table: DECISIONS.md §3 and "Speed and voice".
- Corrected: threshold Jev ("That's good, validate" after a question of price: 0,95 agreement / change 0,55 → was not
  Now agreement ≥ 0,9 = yes.
- Tests: `conftest.py` makes each `.env` independent; 232 passes (modes 0, 1, 3, 4).
- **For all**: set `TEAM_FILLERS=4` and `TEAM_PRODUCT_INSIGHT=1` in your `.env`, restart the AI, go through
  "Who calls?": the agent speaks first.
- Keep your voice on: the useful answer puts 2,8–6,3 s (combled, but long) → orchestrator of Youssef (T4) or model
  faster; real microphone test (transcription + sound in the browser).

- Done (01h00) – **Jev plugged ** (recommendation of CTO), `tools/order_jev.py`, behind `TEAM_ORDER_RULES`:
  - `confirm_order` **replaced** by a version guarded by Jev (same name → all scenarios work as is;
    switch off = kit tool). The agent passes the customer's exact answer; Jev says "true yes" or not.
    Calibration on 12 answers: true yes 0,89–0,96; "yes but...", "wait," questions ≤ 0,14. Also block on
    ERP alarm blocker. Jev → keyless kit behavior. `[jev] …` log in AI service logs (for demo).
  - `resolve_product`: the exact name of the catalogue first ("breads of yeast", "la tradi", "demi-salt" : without
    model), if not Jev with customer habits ("laminating butter" → AOP at Sarrailh, question at Pétrin de Colomiers);
    under 0,6 the agent asks; ambiguous words of the glossary never settled by an alias alone.
  - Measurements (`--voice`, reset before each): S02 S30 S31 S32 S33 PASS, S05 3/4 (see Daycem); 8/8 confirmations
    validated by Jev in 159–196 ms; 1 is the only control just every time. Tests: 151 pass (ON and OFF).
  - New scenario **S33** ("yes but put in twelve"). DECISIONS.md: D8 + measurements.
- For **Daycem**: S05 round 2, add `quote_line` to `tools_any` (the agent gives the price with, that's right).

- Done (00h05) – ** oral prices calculated by code** (tool `quote_line`):
  - Finding listening to a recording of S05: the agent calculated the lead and was mistaken live ("92 euros la
    slab of 2 kilos... pardon, 18 euros 40 the slab").
  - `rules_order.py`: `packaging` (cardboard 5 plates of 2 kg → carton = 10 kg, slab = 2 kg; carton 6 × 1 L...),
    `to_selling_qty` ("3 cartons" of laminating butter → 30 kg), `quote` / `fr_money` ("9 euros 20 per kilo, i.e. 92 euros on
    10 kilos carton"; "276 euros excluding taxes for 30 kilos, that is 3 cartons"). Customer price solved by the ERP
    (`/api/prices/resolve`, negotiated price / group rules): nothing is recoded.
  - Tool **`quote_line`** (`tools/order_review.py`) + rule "for a price, call quote_line, never calculate".
  - Tests: +5 → 117 pass. S05 re-recorded: price just the first shot, call of 68 s → 56 s, 1 order
    confirmed Wednesday 25/11.
  - For **Daycem**: S05 round 2 waits for `get_price` or `product_insight`; add `quote_line` to `tools_any`.
- For **tous**: put `TEAM_ORDER_RULES=1` in its `.env` after the merger (`.env.example` is changed to 1).
- Record Tool: a full call in MP3 (client = 2e voice ElevenLabs, agent = true answer via WS /voice)
  in `scenarios/results/audio/` (ignored by git). I can share it if the team wants it for the video.

- Done (23h30) – **Doubl guardback + note "Closed Wednesday"**, following the audit of S05 (Daycem):
  - **S05 audible** (rupture AOP → 82 %, Colomier Petrin): no duplicates. But **sans** `TEAM_ORDER_RULES` it
    **choue** (2/4): the agent believes the note "closed on Wednesday", moves the delivery to Monday 30/11 and leaves a
    **With** my rules: 4/4, 1 order confirmed Wednesday 25/11.
  - Rule: "Closed the ..." notes are ignored (ERP is true), the agent no longer asks the question.
  - `review_order` also returns **`duplicateDrafts`** ( other drafts created by the agent for this client, with their
    reread and `sameAsThis`) and **`sameDayOrders`** (other orders of the same day, e.g. a WhatsApp draft).
    Rule: identical duplicate → abandoned without talking about it; different draft → reread to client who chooses to cancel or
    merge; never two commands opened by the agent. WhatsApp / e-mail drafts are **jamois** cancelled.
  - "Forgotten draft" test (200 tradi + 3 rye created by hand, then Nadine command 10 tradi): before this patch
    the agent proposed "to keep both separate" and the draft remained (risk: ADV confirms it → double
    delivery) ; now it rereads, insists, and the **annule** to demand → 1 confirmed order, the other canceled.
  - Tests: 112 pass. Replayed in vocals: S05 4/4, S30 3/3, S31 3/3, S32 3/3 (1 commands just every time).
- For **Daycem**: S05 goes with `TEAM_ORDER_RULES=1`; without it, it fails on the false closing on Wednesday.
- Sync proposal: ** turn on default `TEAM_ORDER_RULES=1` on hand** (`.env.example`).

- Done (T3 / T4, 22h50):
  - Tool **`review_order`** (`tools/order_review.py`, deterministic logic `rules_order.review`): to call after
    Each command creation/change. Returns the ready-to-say reread sentence, ** alerts ERP translated**
    for the customer (locked, ceiling, no tour, break / "only left..."; internal alerts
    `price_below_cost` / `expiring_soon` are never said, no accounting figures), the remark **franco 150 € excl. VAT**
    (12 € otherwise, with what is missing), unusual **quantities** (≥ 5× habit) to be confirmed, and `canConfirm`.
  - **modification tools** (`tools/order_edit.py`): `update_order_line`, `remove_order_line`,
    `change_delivery_date`, `cancel_draft_order` (brown only). The kit knew only ** add** lines:
    the "finally twenty" (S31 v1) the agent created a 2e command and left the draft to 200 bags in the ERP.
  - Rule "do not think aloud" hardened (a leak seen in S31 v1: "Unusual quantity probably; I create...").
  - My scenarios **S30** (franco), **S31** (200 bags instead of 20), **S32** (change + remove a line after draft).
  - Tests: +5 (review, alerts, frank, abnormal quantity) → 108 switch on or off.
  - Everything is behind `TEAM_ORDER_RULES` (the 6 tools are only saved if it is on).

| Scenario (`--voice`, end of speech → 1er sound) | Result | Towers (ms) | In the ERP |
|---|---|---|---|
| S30 | PASS 3/3 | 9 257 · 5 002 · 3 720 | 1 confirmed order, 153,90 € excl. VAT; "12 euros in fees... it is missing 147 euros", then "you pass the franco" |
| S31 abnormal quantity | PASS 3/3 | 5 162 · 2 984 · 1 879 | "Do you say two hundred? Usually it's about twenty" → 1 orders to 20 bags, no orphan draft |
| S32 change of opinion | PASS 3/3 | 7 816 · 6 484 · 3 234 | `update_order_line` + `remove_order_line` → 1 order, 15 tradi, more rye |
| S02 | PASS 3/3 | 8 609 · 7 955 · 3 368 | 1 confirmed command |
| S03 (/chat) | PASS 1/1 | 5 426 | message saved, nothing promised |

- Done (T0–T2, 22h40):
  - **T0** baseline (below).
  - **T2** `next_delivery_date` + `sacks_from_words` (determinists, `agent/rules_order.py`) + tool
    **`check_delivery_date`** (`tools/delivery.py`, registered only if `TEAM_ORDER_RULES=1`).
    Tests : `tests/test_rules_order.py` (8 + my 2 testing `test_team_todo.py` deskippés → green.
  - **T1** `ORDER_RULES` v1 (9 short rules: no "thinking high", units, chocolate, as usual = basket
    usual, dates via tool, draft then **modify** line, reread then `confirm_order` direct to yes,
    account blocked = message + `log_client_event`, alerts only say if there are any).
  - S02 reformulated: "for the 12 bag processing" (the habit of Sarrailh is ~21 bags, not 10).
- In progress: T3 (detail ERP alerts), T4 (franco 150 €, abnormal quantity), my scenarios S30–S31.
- Blocked / I wait: nothing.
- I need (who, what):
  - **Youssef** : `CallContext.delivery_days` = field ERP as is (decision below: the ERP is true, not the note
    "Closed on Wednesday"). Ideally, do not put these notes "Closed on ..." in `render_for_prompt`.
  - **Youssef**: `run_scenarios.py` in mode /chat does not replay → tool ids the agent recreates a draft to
    each turn (seen in S01/S02: `create_draft_order` recalled in the 2/3 tower). In `--voice` all is right (1 only)
    order). To read the results /chat.
  - **Everyone**: a line added to `tools/__init__.py` (shared) to save `delivery.py` behind
    Mon switch.
- Switch(s): TEAM_ORDER_RULES = **on** on my branch · ready to turn on hand ? **oui** (4/4 green scenarios)
- Measurement (scenarios, ms): see table "With TEAM_ORDER_RULES=1".
- Change of contract requested (interfaces.md): none (I add the tool `check_delivery_date`, provided by my form).

## With TEAM_ORDER_RULES=1 (Mon. 22h30, /chat unless mentioned)

| Scenario | Before | After | What's changed |
|---|---|---|---|
| S01 | PASS · 11 078 / 9 394 ms | PASS · 7 291 / 5 915 ms | More than "Thursday is a day of delivery" before hello; says "Thursday 26 November" via the tool. |
| S02 | **FAIL** 2/3 | **PASS 3/3** · `--voice` : 8 927 / 7 306 / **3 527 ms** (termination → 1er son) | Regular basket (not the last order), 1 only draft modified to 12 tradi, `confirm_order` direct to "validate". 1 only command in the ERP. Report failure AOP without substitute. |
| S03 | PASS · 4 907 ms | PASS · 6 324 ms | More "you are closed on Wednesday", more internal accounting rules; ** registered message** (`log_client_event`) and Sandrine cited. |
| S07 | PASS · 6 470 ms | PASS · 7 071 ms | More leak "Thursday is a day of delivery"; "ten bags of tradi and two loaves of yeast". |

Known limits: the rereading of a complete "as usual" remains long in the oral (9 products); the time remains at
5–9 s per turn (platings of Mohamed Amine and Youssef).

## Baseline T0 (original kit)

| Scenario | Result | Tour times (/chat, full turn) | What's wrong |
|---|---|---|---|
| S01 simple command Sarrailh | PASS 2/2 | 11 078 ms · 9 394 ms | "Thursday is indeed a day of delivery (Thursday 26 November). Hello Nadine..." "Yes," recalls 6 tools (search, get_client, get_price...) before `confirm_order`: 9,4 s to validate. Phrase "I check and validate" parasite. |
| S02 as usual + change of mind | **FAIL** 2/3 | 8 799 · 3 411 · 3 166 ms | "As usual" = copy the **last** command (21 tradi, 10 strong flour...) instead of the usual basket, and the entire bed (too long to the oral). No draft created. On the 3 ("validize") tower asks again instead of concluding → no `confirm_order`. Partial cause: the scenario says "instead of 10" while the habit is 21. |
| S03 customer blocked (Balma's company) | PASS 1/1 | 4 907 ms | Refuses well. But: (1) says "Tomorrow Wednesday you are closed" while the ERP the book sea/sam (see below) ; (2) gives an internal rule ("after payment of at least half of the fallen) ; (3) does not take **pas** the message (no `log_client_event`). |
| S07 hesitant sentence | PASS 1/1 | 6 470 ms | Same leak "Thursday is a day of delivery (26/11)." before hello. Otherwise just: 10 bags + 2 yeasts, rereading, no confirmation. |

**What I remember about T1–T3**
1. Prohibit internal audit phrases out loud (what is said before / between tools is pronounced).
2. "As usual" = the usual **panier** of the sheet (`usual`), summarized in 2-3 main products + "as usual for the rest?", not the last order read in full.
3. Create the draft as soon as the command is clear; a change of opinion ** modifies** the line.
4. "Validate / it's good / yes" after a rereading = `confirm_order` directly, without re-verifying the entire catalog.
5. Locked account: refuse without internal accounting details + ** save message** (`log_client_event`).

## Contradictory data: "Closed on Wednesday"

9 customers have a commercial note "Closed on Wednesday: never delivered that day" while Wednesday is
in their delivery days ERP (Muret Petrin, Balma Petrin, Colomier Petrin, Au Fournil de Mélanie,
Au Fournil de Didier, Au Pain de Guilhem, Au Fournil de Philippe, La Mie d'Arnaud-Bernard, Au Fournil de Brigitte).
**The historical slice**: these customers are ** actually delivered on Wednesday** after the date of the note (e.g. Petrin
of Muret : 12 Wednesday since September ; Au Fournil de Philippe is delivered **that** Wednesday).
The original agent believes the note and wrongly refuses (see S03 and S1 test of the kit).
→ To be decided: authenticate the **delivery days of the ERP** (confirmed by history) and ignore the note.
