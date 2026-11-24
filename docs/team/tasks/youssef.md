# Youssef – "Multi-brain parallel" (speed + architecture)

** Selection criteria** : Quick (< 1,5 (s) and Intelligent. **Council of the CTO** : several agents at once.
** Switches**: `TEAM_ORCHESTRATOR`, `TEAM_PRELOAD`, `TEAM_PRODUCT_INSIGHT`, `TEAM_FAST_MODEL`.
**Branche**: `youssef/<sujet>`.

## Real Life
Lucie recognizes Nadine from the "Hello" and opens her card (habits, preferences, account) ** once**. During
she talks with Nadine, a colleague looks at the stock. A single glance at the screen gives her stock + price + replacement.
Today the agent chain the tools one by one (search → get_client → get_product_stock → get_price →
find_alternatives) : 4 to 6 round-trip ≈ 1 Each, before saying a word.

## Your files
| File | Role |
|---|---|
| `apps/ai/app/agent/orchestrator.py` | **to you**: fast agent + brain agent |
| `apps/ai/app/agent/call_context.py` | **à toi**: the preloaded customer data sheet (v0 that already works: plug + context in parallel) |
| `apps/ai/app/tools/product_insight.py` | **to you**: the super tool |
| `apps/ai/app/agent/loop.py` | shared, kit file: touch it only for orchestration, by warning Mohamed Amine |
| `scripts/run_scenarios.py` | **to you**: the replay of scenarios (goes already, via /chat or `--voice`) |

Read first: `apps/ai/README.md` (loop, tools), `GUIDE-AGENTS.md` (tools, context, quick cache, models,
Jev), `GUIDE-VOIX.md` §4.3-4.6, [interfaces.md](../interfaces.md) §1-3.

## Your tasks, in order
| # | Task | No more when |
|---|---|---|
| T0 | Run `run_scenarios.py --only S01 S05`: Record the number of tools called and the times (baseline in DECISIONS.md) | baseline noted |
| T1 | **Super tool** `product_insight` : product + stock + customer price + replacements (stock, price, promo) in one call, in parallel (`asyncio.gather`); test ; `TEAM_PRODUCT_INSIGHT=1` | S04/S05: fewer tools called, same result; green `test_product_insight_…` test |
| T2 | **Preloaded sheet**: complete `load_call_context` (stock of usual products, active promotions); load it as soon as the customer is identified (result of `get_client`, or `search` with only one customer) and keep it on the `Conversation`; `TEAM_PRELOAD=1` | from the 2e turn, more call to get_client / get_context; `loaded_ms` < 300 |
| T3 | **Cache of prompt**: check that the large static context is read from the Anthropic cache (`cache_read_input_tokens` in `usage`); the customer record remains at the end | cache_read > 0 from the 2th round |
| T4 | **Orchestrator**: fast agent (`get_fast_llm_client`, Haiku) in parallel to the brain agent; simple tricks (yes / no / thank you / that's all) fast only (Jev or rules to rank); never contradiction, never number fast side; `TEAM_ORCHESTRATOR=1` | S06: first text < 1,5 s; all scenarios still green |
| T5 | Measurements: at each sync, complete `run_scenarios.py` and one row in the table of DECISIONS.md | updated table |
| T6 | (extension, after case 1) S08: claim + order in same call | S08 green |

**Tes Scenarios** (S20–S29, at least 2): e.g. a call to several products including one broken, and one customer
who does not name himself ("I am, as usual") → the agent must ask who is calling.

## Who to coordinate with
- **Mohamed Amine**: who speaks first (quick agent or waiting phrase) → interfaces §1, to H+2.
- **Daycem**: the replacement format (`rank_alternatives`) and demo promo.
- **Amine Khalil**: what its part reads in the plug (`CallContext`).

## Traps
- Faster but fake doesn't win: replay **tous** scenarios after each step.
- The Quick Agent does not have tools: he must never declare a stock, price or date.
- The prompt gets bigger with the plug: keep it short (top N inputs, truncated bodies).

## The first message to give to your AI code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md and docs/team/tasks/Youssef.md. I am Youssef.
> Explain to me T0 and T1 in simple words, propose a plan, and wait for Mon chord before coding.
