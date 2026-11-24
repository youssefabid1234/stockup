# Daycem – "The Good Seller" (Commercial Intelligence + Natural)

**Journal Criteria**: Intelligent ("proposes alternatives, knows that this leader refuses substitutions") and Natural.
This is the scene the CTO wants to see: a customer who prefers a broken product → the agent sees a replacement
available, **in promotion**, offers it and **argument** — but only if the customer accepts the replacements.
**Interruptor**: `TEAM_SALES_RULES`. **Branche**: `daycem/<sujet>`.

## Real Life
- **Le Pétrin de Colomiers** (accepts substitutions if notified) requests AOP laminating butter, broken to end
  November. Lucie: "AOP is broken until the end of the month. I have laminating butter 82 %, 9 euros 20 per kilo instead of
  11 euros 40, and it's on a promo this week; for your croissants it leaves very well. I'll put you 3
  She's waiting for the "yes."
- **Maison Sarrailh** asks the same thing. Lucie knows that Guy "prefers to miss": it announces the break and the date
  back, **sans** propose a replacement.
- **Boulangerie Escaich** compares prices ("Garonne Boulange me does it to 18 the tradi") : Lucie does not make a discount
  (only Bernard beyond 5 %), but highlights the negotiated price, Lauragais quality, and proposes to transmit.

## Your files
| File | Role |
|---|---|
| `apps/ai/app/agent/rules_sales.py` | **to you** : `SALES_RULES` (text of the prompt) + `refuses_substitution`, `rank_alternatives` |
| `apps/ai/tests/test_team_todo.py` | your "Daycem" section: remove the `@TODO`s and pass through |
| `scripts/setup_demo_data.py` | **to you** : creates demo promo by the API (data/seed is not in git) |

Read first: `data/context/04-playbook-clients.md` ("Substitutions: never without agreement"), `05-prix-et-credit.md`
(remises, price rules), `data/context/clients/` cards from Sarrailh (c0001), Escaich (c0006), Petron de Colomiers
(c0021), La Gerbe d'Or (c0013): sections "What's annoying them", "How to talk to them", [interfaces.md](../interfaces.md) §5.

## Your tasks, in order
| # | Task | No more when |
|---|---|---|
| T0 | `run_scenarios.py --owner daycem` (S04, S05): Note what fails | baseline noted in your status |
| T1 | `SALES_RULES` v1 : read the preferences before any replacement; → refusal to announce break + return date, nothing else; otherwise UN substitute argumented (use, price, promo) then request the agreement ; no delivery on the phone ; `TEAM_SALES_RULES=1` | Green S04 and S05 |
| T2 | **Naturel**: never say aloud his reasoning (default seen on S03: "The account is blocked; I don't take orders, I write down the message. Hello..."); numbers and units in the speech; tone according to the form (tutoi, "call Nadine, not Guy"; with Mohamed Amine: more "I look" said by the model when waiting sentences are active | listening on S01-S05: it looks like a person |
| T3 | `refuses_substitution` + `rank_alternatives` + tests; plug into `product_insight` with Youssef | green tests |
| T4 | **Demo promo**: `scripts/setup_demo_data.py` creates a price rule (e.g. laminating butter 82 % -8 % to 30/11) via `POST /api/price-rules`; check that `get_price` sees it; write it in DECISIONS.md (changed, assumed data) | S05: Agent quotes promo |
| T5 | Negotiation (Escaich): no discount, value, propose to transmit to Bernard (event `price_negotiation`) | a green S4x scenario |

**Tes scenarios** (S40–S49, at least 2): La Gerbe d'Or (refuses substitutions) requires a broken product;
Escaich negotiates the price of the trade.

## Who to coordinate with
- **Amine Khalil**: he = what is ordered and validated; you = how we sell and how we talk.
- **Youssef**: the format of `product_insight` and the ranking of replacements.
- **Mohamed Amine**: the tone of the waiting phrases.

## Traps
- Never replace **Added** to the command without an explicit "yes" (`substitute_for` in `add_order_line`).
- A promo is only mentioned if the ERP returns it (never invented).
- Stay brief: 1 to 2 sentences per reply; the argument is in one sentence.

## The first message to give to your AI code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md and docs/team/tasks/Daycem.md. I am Daycem.
> Explain to me T0 and T1 in simple words, propose a plan, and wait for Mon chord before coding.
