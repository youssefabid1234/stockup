# Amine Khalil – "The Right Command" (Intelligence)

**Journal Criterion**: Intelligent — "the right order in the ERP, the right product, the right customer. It never invents."
**Interruptor**: `TEAM_ORDER_RULES`. **Branche**: `amine-khalil/<sujet>`.

## Real Life
Nadine says "as usual, and put me 10 of tradi for Thursday." Lucie knows that "10 of tradi" = **10 bags of 25 kg**
T55 tradition (not 10 kilos), that "as usual" = the usual bakery basket, that Sarrailh is delivered
Tuesday / Thursday / Saturday, that after 17h is for the next day. If Nadine says "finally 12", Lucie ** modifies** the
line. Before validating, it **relit** everything. At the Petrin of Balma (blocked account), it promises nothing.

## Your files
| File | Role |
|---|---|
| `apps/ai/app/agent/rules_order.py` | **to you** : `ORDER_RULES` (text of the prompt) + deterministic functions |
| `apps/ai/tests/test_team_todo.py` | your "Amine Khalil" section: remove the `@TODO`s and pass through |
| `apps/ai/app/tools/delivery.py` (to be created if needed) | **to you**: a "delivery date" tool if the rules are not enough (add import in `tools/__init__.py`, one line) |
| `data/context/*.md` | reading; an addition is discussed (everything is read every turn: it costs in speed) |

Read first: `data/context/01-entreprise.md` ("House Rules"), `02-journee-type.md` (time limits),
`03-glossaire-produits.md` ("It's said"), `04-playbook-clients.md` ("Take an order"), `ERP.md` (lifecycle)
of a command, alerts), `METIER.md` (ordering), [interfaces.md](../interfaces.md) §4.

Your experience of our first repo applies directly: "as usual", corrections in the same message,
units and conversions, "never invent".

## Your tasks, in order
| # | Task | No more when |
|---|---|---|
| T0 | `run_scenarios.py --owner amine-khalil` (S02, S03) + S01, S07: rate what fails and why | baseline noted in your status |
| T1 | `ORDER_RULES` v1: units (bags, plates, cartons, bricks), "chocolaline", "as usual", change of opinion = **modify** line, oral revision **avant** `confirm_order`, spoken quantities; `TEAM_ORDER_RULES=1` | S01, S02, S07 green |
| T2 | **Delivery dates**: Customer delivery days, time limit 17h (Lauragais-Tarn: the day before 12h), never a day undelivered; `next_delivery_date` determinist + tests (or a tool `delivery.py`) | green tests; "for Wednesday" to Sarrailh → the agent proposes Thursday |
| T3 | **ERP** Alerts: after `create_draft_order`, read the `warnings` (client_blocked, no_route...) and say them simply; account blocked = take the message, nothing promises | S03 green without "internal" sentence |
| T4 | Franco 150 € excl. VAT (other than delivery 12 €): say if the order is small; unusual quantities (10× habit): confirm | one S3x scenario of each |
| T5 | (extension) claims: record with `log_client_event` + the order concerned | S08 green (with Youssef) |

**Tes scenarios** (S30–S39, at least 2): e.g. yeast troubleshooting on the same day (possible up to 9h if the
tour is not party), an order under the franco, an abnormal quantity.

## Who to coordinate with
- **Daycem**: both of you write prompt rules. You: **what is ordered** (product, quantity, date,
  Daycem : **how we sell and how we talk** (alternatives, promotions, tone). If in doubt, ask yourself.
- **Youssef**: what you want to find in the preloaded file (`CallContext`).

## Traps
- The rules of price, stock and credit remain in the backend: on **lit** the ERP, they are not recoded.
- The prompt is reread at each stage: short and clear rules, not a novel.
- The reference date is that of the pack (Tuesday 24/11/2026, 6h30), never the actual clock.

## The first message to give to your AI code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md and docs/team/tasks/amine-khalil.md. I am Amine Khalil.
> Explain to me T0 and T1 in simple words, propose a plan, and wait for Mon chord before coding.
