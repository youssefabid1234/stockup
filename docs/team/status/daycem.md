# Daycem – "The right seller" · updated Mar. 24/11, 0h30

- Done since the last sync:
  - T1: complete `SALES_RULES` (rupture, only one alternative supported, date of return as written,
    no presentation, no reasoning aloud, 1-2 sentences, one question, private internal notes;
    Client who refuses: solution without other product + request noted with `log_client_event`). General rules,
    verified by `test_sales_rules_stay_general`. The last two rules are not yet replayed.
  - T3 (beginning): `substitution_policy` (keywords: refuse / accept / request / unknown) and `decide_substitution`
    (Jev only if "unknown", any → error request). 13 tests on real files; the 104 sheets checked
    `refuses_substitution` keeps the interfaces contract.md §5.
  - Test Jev alone on 10 plugs: 6/10 then 5/10, ~150-170 ms → `docs/team/jev-substitution-test.md` (for DECISIONS.md).
- In progress: T3 `rank_alternatives` (substituts listed in the documents first), plan to be validated.
- Blocked / I wait: nothing.
- I need (who, what):
  - **Youssef**: Plug `decide_substitution` / `rank_alternatives` in `product_insight` (still `NotImplementedError`).
  - **Amine K. / Youssef** : orphan draft seen 2 times on S05 (CMD-2026-007543 in draft next to the
    The runner now replays the entire history (PR #4) and `order_edit` exists (PR #3):
    ** to be checked again** at the next replay.
  - **Mohamed Amine**: its proposal "directly gives the result, the vocal player makes it wait" (when
    `TEAM_FILLERS=1`) contradicts my rule "I look. is allowed": to slic together before turning on both.
- Switch(s): TEAM_SALES_RULES = on my branch · ready to turn on ? yes (S04 and S05 pass)
- Measurement (scenarios, ms): see the tables below (T0 → T1c: S04 first word 7,5 s → 0,7 s).
- Contract change requested (interfaces.md): none; addition of `substitution_policy` and `decide_substitution`.

## Starting photo T0 (kit only, Sonnet, via `POST /chat`)

| Scenario · tour | Result | Model calls | First word | Total | Tokens (exit · written cache · read cache) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 7 536 ms | 7 491 ms | 417 · 28 696 · 51 387 |
| S05 · 1 | PASS | 3 | 5 625 ms | 5 624 ms | 483 · 2 334 · 76 446 |
| S05 · 2 | PASS | 3 | 956 ms | 5 991 ms | 643 · 3 143 · 77 250 |
| S05 · 3 | PASS | 4 | 1 126 ms | 7 062 ms | 828 · 5 387 · 108 193 |
| S05 · 4 | PASS | 4 | 1 851 ms | 8 195 ms | 860 · 5 360 · 109 013 |

Total: 17 model calls, 3 231 output tokens. The quick system makes about 25 000 tokens, almost everything comes
`data/context/*.md`. The 2 to 4 towers start fast (~1 s) because the model says "I look." before its
tools. The runner only replays the text of the previous tricks: the agent redones `search` and `get_client` at each turn.
In real voice call, the history keeps the results of the tools.

It's all over, but listening:
- Too long (3 to 5 sentences instead of 1 or 2).
- He tells of internal causes ("gathering strike") and his reasoning ("I don't put anything in place for you,
  I know it's excluded at your house," "I check your file before confirming").
- It does not give the date of return ("late November", however in `01-entreprise.md`): it says "no arrivals
  planned".
- He promises without acting: "I warn Julien", without `log_client_event`.
- S05: it offers the 82 % without any use arguments ("flip very well for your croissants"). It calls the customer
  "Mr. Dumont" when the appellant did not name himself (to be dealt with in T2).
- Good point: he reads the note "closed on Wednesday" (while the sheet says "delivered Mon., Sea. ") and delivers Monday.
  Field of Amine K. (delivery days).

Gross results: `scenarios/results/*-baseline.json` (ignored by git).

## Replay T1 (`TEAM_SALES_RULES=1`, SALES_RULES v1 + 1-2 sentences / no reasoning / no guess name)

| Scenario · tour | Result | Model calls | First word | Total | Tokens (exit · written cache · read cache) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 6 591 ms | 6 586 ms | 408 · 31 618 · 53 353 |

Answer: "Nadine, I have no more AOP laminating butter in stock for Thursday and I don't have a return date yet. Do you want to
that I note your request for 2 cartons? » Better: 2 sentences, no substitutes or reasoning, no cause
internal, `get_client` well called. Remains: it does not give "late November" (read in `01-entreprise.md` as a
end of strike, not as a date of return).

## T1b game (+ rule "end date of break in documents = date of return")

| Scenario · tour | Result | Model calls | First word | Total | Tokens (exit · written cache · read cache) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 4 751 ms | 4 743 ms | 407 · 31 680 · 53 477 |
| S05 · 1 | PASS | 4 | 9 476 ms | 9 475 ms | 692 · 4 659 · 109 984 |
| S05 · 2 | PASS | 3 | 2 160 ms | 6 158 ms | 501 · 2 425 · 79 891 |
| S05 · 3 | PASS | 4 | 2 401 ms | 9 670 ms | 826 · 4 892 · 111 533 |
| S05 · 4 | PASS | 4 | 8 747 ms | 8 747 ms | 668 · 1 773 · 109 363 |

- S04: "Nadine, the AOP laminating butter is breaking for now. The return to normal is estimated at late November, without
  I note your request for 2 boxes for Thursday?" → date given, but "without promise" sounds mechanical.
- S05: A common argument ("also used for your pains au chocolat"), more reasoning or internal cause.
- Problems:
  - the date is not stable: S05 round 1 says "no return date" with the same document;
  - the 1 round of S05 asks two questions (day + agreement) and gives the price before it is requested;
  - the first word comes later to the towers 1 and 4 (9,5 s and 8,7 s): the model no longer says "I look."
  - ** double control**: in round 4, the agent recreates a draft and then confirms it; CMD-2026-007543 remains in
    Orphan draft next to CMD-2026-007544 confirmed. Probable cause: the runner only plays the text, the agent
    loses the idea of the draft. Not verified in real voice call. → Amine K. (command) and Youssef (runner).

Then written corrections (not yet replayed): date said naturally ("normally at the end of the month"), without
"without promise"; only one question at a time (first the agreement on the replacement); a short waiting sentence
neutral ("I look.") is allowed, only the explanation of what is being checked is prohibited.

## T1c Replay (date said naturally, only one question, "I look." allowed)

| Scenario · tour | Result | Model calls | First word | Total | Tokens (exit · written cache · read cache) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 734 ms | 5 695 ms | 477 · 27 077 · 58 496 |
| S05 · 1 | PASS | 4 | 1 015 ms | 8 311 ms | 738 · 4 751 · 110 534 |
| S05 · 2 | PASS | 3 | 5 761 ms | 5 761 ms | 498 · 2 928 · 80 756 |
| S05 · 3 | PASS | 4 | 8 297 ms | 8 302 ms | 701 · 4 569 · 111 404 |
| S05 · 4 | PASS | 4 | 7 068 ms | 7 094 ms | 468 · 1 107 · 108 623 |

- S04: "I'm looking. By Thursday, I have no more AOP laminating butter in stock. It should normally come back from
  early December. Do you want me to rate your request for 2 cartons?" → first word to 0,7 s. But "start
  December" is not written anywhere (the "up to late November" document): date deducted.
- S05 round 1: "I look. The AOP laminating butter is broken, it should normally come back at the end of the month. I can
  offer you the 82% laminating butter, in plates of 2 kilos, which is suitable for your pains au chocolat, to 9 euros
  20 the kilo. Is it available, is it okay?" → only one question, usual argument, given date.
- Remains: "I look." only in the 1 round of S05 (5,8 to 8,3 s silence afterwards); 2 round in 3 sentences with
  a start of explanation ("I can't promise you delivery that day"; date formulated differently
  between S04 and S05; **orphan sheep still present** (CMD-2026-007543).

Fixed then written (not yet replayed): the date of return is given as written in the
documents, without transforming or deducing another.
