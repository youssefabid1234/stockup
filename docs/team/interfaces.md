# Contracts between our 4 yards

> Each code in **ses** files. These contracts tell what each one gives to others and expect from them.
> changes ** only after having said it in group** (and notified the data subject). The reference code is indicated.

## 0. Switches (`apps/ai/app/team_flags.py`)

Every brick is ** Defaultly Off** : while it's off, the kit behaves exactly as originally.
It is lit in `.env` (at the root) and restarted the AI service (Ctrl-C in its terminal, restart).

| Switch | carton | Owner |
|---|---|---|
| `TEAM_FILLERS=1` | Waiting phrases + keyboard noise | Mohamed Amine |
| `TEAM_ORCHESTRATOR=1` | fast agent + parallel brain agent | Youssef |
| `TEAM_PRELOAD=1` | preloaded customer form | Youssef |
| `TEAM_PRODUCT_INSIGHT=1` | super-product tool (recorded on startup) | Youssef |
| `TEAM_ORDER_RULES=1` | rules "just command" in the prompt | Amine Khalil |
| `TEAM_SALES_RULES=1` | "Good seller" rules in the prompt | Daycem |
| `TEAM_FAST_MODEL=claude-haiku-5-5` | Quick Agent Model | Youssef |

A brick is not lit ** default on `main`** (in `.env.example`) that when his scenarios pass.

## 1. Votes in the ballot (Mohamed Amine - Youssef)

File: `apps/ai/app/services/voice_session.py` (Mohamed Amine) calls, in this order, for each round:

1. `await fillers.on_turn_start(speaker, heard)` just after the final transcription (t0 + a few ms)
2. the agent: `run_voice_turn(...)` (orchestrator of Youssef) if `TEAM_ORCHESTRATOR=1`, otherwise `run_agent(...)` of the kit
3. `await fillers.on_tool_call(speaker, tool_name)` at each tool call

**** anti-skinning rule: if the Youssef fast agent already speaks (text that arrives in < 700 ms), no sentence
Proposal: the orchestrator exhibits `expects_tools(heard) -> bool` (Jev or keywords); `on_turn_start`
only plays a waiting sentence if `True`. To be decided between you two at H+2, then note here.

**`Speaker`** (in voice_session.py): Mohamed Amine adds `async play_audio(mime, data)` to play a sound
pre-recorded in the same audio segment as the answer.

## 2. Customer details and super tool (Youssef → Amine Khalil, Daycem)

**`CallContext`** (`apps/ai/app/agent/call_context.py`): the customer's card on the phone, loaded once.
Fields (contract): `client_id, name, status, blocked, delivery_days, preferences, contacts, usual[UsualItem],
outstanding, credit_limit, open_issues, notes, context_entries[{kind,title,body}], active_promos, loaded_ms`.
It is added ** to the end** of the prompt (`render_for_prompt`). Amine K. and Daycem can lean on it in their
rules ("according to the customer's card on the phone...").

**`product_insight(client_id, product_id, qty)`** (`apps/ai/app/tools/product_insight.py`) returns:

```json
{
  "product": {"id", "name", "unit", "available", "clientPrice", "listPrice", "priceExplanation",
              "incoming?", "promo?", "betterPriceWithVolume?"},
  "inStock": true,
  "missing?": 6,
  "substitution?": "refuse | accepte | demander | inconnu",
  "note?": "…",
  "alternatives": [{"id", "name", "unit", "available", "clientPrice", "listPrice",
                    "promo?": {"name": "Promo tourage 82 % : −8 % jusqu'au 30/11", "until": "2026-11-30", "pctOff": 8}}]
}
```

`substitution` and `alternatives` only if the product is missing (otherwise `alternatives: []`). The `alternatives` are
sorted by `rules_sales.rank_alternatives` (Daycem), empty if client refuses (`substitution_policy` of Daycem).
Promo = price rule **dated** applied under the catalogue price. Logic : `apps/ai/app/tools/insight.py` (testable
without the switch); instructions added to the prompt when the switch is on (`product_insight_section`).

## 3. Orchestrator (Youssef)

`run_voice_turn(messages, *, llm, tools, mode, actor_name, call_context)`: ** same contract as `run_agent`** (same
events `text`, `tool_call`, `tool_result`, `done`, `error`, and he adds the messages to `messages`).
The fast agent ** never says ** a number, stock, price or promise: only the brain agent
the fact ("never invent").

## 4. Fair Order Rules (Amine Khalil)

`apps/ai/app/agent/rules_order.py`: `ORDER_RULES` (text) inserted in the prompt by `order_rules_section()` in modes
voice and chat (not in command mode).Deterministic functions tested (`next_delivery_date`, `sacks_from_words`).
Price, stock and credit rules remain in the backend: read the order's `warnings` (`client_blocked`,
`no_route`...) instead of recode them.

## 5. Good seller rules (Daycem)

`apps/ai/app/agent/rules_sales.py`: `SALES_RULES` (text) inserted by `sales_rules_section()`.
`refuses_substitution(preferences, product_name)` and `rank_alternatives(alternatives, preferences)` used by
`product_insight` (Youssef). Demo promo: created by API (`POST /api/price-rules`) by `scripts/setup_demo_data.py`,
because `data/seed/` is not in git.

## 6. Prompt: One shared file, each with its own line

`apps/ai/app/agent/prompts.py` assemblage: role → rules of the kit → rules of the mode → **control rules (Amine K.)** →
**Rules of Sale (Daycem)** → date → company context (big, static, cached) → **customer profile (Youssef,
**. Nobody rewrites `prompts.py`: each edits **son** module. If `VOICE_RULES` or `BASE_RULES` of the kit
we have to change, we talk about it first (Amine K. slice for the command, Daycem for the tone).

## 7. Scenarios (all)

`scenarios/S*.json` + `scripts/run_scenarios.py` (Youssef). Reserved numbers: Mohamed Amine S10–S19, Youssef S20–S29,
Amine Khalil S30–S39, Daycem S40–S49. Format: [scenarios/README.md](../../scenarios/README.md).
