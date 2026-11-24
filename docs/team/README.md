# Team 12 – Le Fournil Occitan: the plan

> Team entry point. Humans and AI code read it **before** to touch the code, with
> [AGENTS.md](../../AGENTS.md) (rules), [interfaces.md](interfaces.md) (contracts between us) and **sa fiche**
> in [tasks/](tasks/).
> Made: **mardi 24/11 17h30, without exception** (repo + video). Demo in front of the jury at 18h.

---

## 1. What We Build

**The telephone standard of the Fournil Occitan.** A customer (blangery, pastry, restaurant...) calls; the agent
Vocal takes his order as the best standardist would do: he recognizes it, knows what he usually orders,
includes the jargon ("10 of tradi" = 10 bags of 25 kg), checks the stock and account, manages a break by proposing
**and argumenting** a replacement ** only if the client accepts them**, reread the command, then enter it in l'ERP.
Then (if time permits): claims and questions in the same appeal.

**Why (in data)**: 45 % commands arrive by phone (11 231 / 24 769), especially between 12h and 15h,
all hand-cut by the salesmen and the standard. A baker has his hands in the flour: he calls.

**What we aim for** (Journal Criteria): **intelligent** (never false, never invented), **fast** (less than 1,5 s between the
end of customer phrase and first sound), **natural** (it is forgotten that it is a machine). The demo comes **after** the
product.

## 2. The path of a call and who owns what

```
Client parle (page Voix, Espace)
  │
  ├─ STT Soniox (texte en direct) ················ Mohamed Amine : vocabulaire métier (vocabulary.py)
  │
  ▼  fin de phrase (t0)
  ├─ ⚡ 0-300 ms : phrase d'attente / bruit de clavier ··· Mohamed Amine (services/fillers.py)
  │
  ├─ 🧠 Agents en parallèle ························ Youssef (agent/orchestrator.py)
  │     ├─ agent « parole » rapide (Haiku) : répond vite aux tours simples
  │     └─ agent « cerveau » (Sonnet) : outils + décisions
  │
  ├─ Fiche client chargée une seule fois, en parallèle ··· Youssef (agent/call_context.py)
  ├─ Super-outil produit (stock + prix + remplaçants + promos) ··· Youssef (tools/product_insight.py)
  │
  ├─ Règles « commande juste » (jargon, comme d'hab, relecture, blocage, jours) ··· Amine Khalil (agent/rules_order.py)
  ├─ Règles « bon vendeur » (préférences, remplacement avec accord, argumenter, ton) ··· Daycem (agent/rules_sales.py)
  │
  ▼
  ├─ ERP : brouillon → relecture → confirmation (outils du kit) · rien à coder
  └─ TTS ElevenLabs phrase par phrase, connexion chaude ··· Mohamed Amine (voice_session.py / clients TTS)
```

Everything is **deactivated by default** (switches `TEAM_*` in `.env`, see [interfaces.md](interfaces.md)): the kit
of origin rotates until a brick is ready. Each activates its own when it walks.

## 3. The 4 yards

| Who | Building | Criterion | Form |
|---|---|---|---|
| **Mohamed Amine** | "Never white": waiting phrases, keyboard noise, hot TTS, STT vocabulary, measurements | Fast + Natural | [tasks/mohamed-amine.md](tasks/mohamed-amine.md) |
| **Youssef** | « Several brains » : fast orchestrator/brain, preloaded customer data sheet, super-tool, scenario replay | Fast + Intelligent | [tasks/Youssef.md](tasks/youssef.md) |
| **Amine Khalil** | "The right command": jargon and units, as usual, changes of opinion, rereading, blocking / days / time limit | Intelligent | [tasks/amine-khalil.md](tasks/amine-khalil.md) |
| **Daycem** | "The right seller": preferences, agreement replacement, argument an alternative, demo promo, tone per customer | Intelligent + Natural | [tasks/Daycem.md](tasks/daycem.md) |

**For all**: write **2 scenarios** of its domain in [`scenarios/`](../../scenarios/) (the tests of the whole night),
play the customer aloud to test others, record his measurements and choices in `DECISIONS.md`.

## 4. Milestones

| Time (Mar. 24/11 = J) | Jalon | Verified by |
|---|---|---|
| H+1 | Everyone has read their sheet, kit launched on their PC, 2 written scenarios | `scripts/run_scenarios.py` list |
| H+4 | Each carton in v0 behind its switch, green tests | `uv run --group dev pytest` |
| H+8 | A full call (scenario S1) passes with all the active bricks | replay of scenarios + page Voice |
| H+14 | Scenario "break + substitute argumented" and "block client" pass; < 1,5 s perceived | measurements in DECISIONS.md |
| J 13h | Extension claims if ok; otherwise polish | |
| **J 14h30** | **Gel code**: only corrections | |
| J 14h30–17h | Demo: video, slides, README, test `make setup` (Mac/Docker) | |
| **J 17h30** | **Rendu** | |

## 5. Ritual every hour: "sync"

Every hour (or when someone writes "sync" in the group), each one:

1. **Fige**: its code turns (the rest behind its switch), `uv run --group dev pytest -q` is green.
2. **Statut**: Updates `docs/team/status/<prénom>.md` (does / in progress / blocked / needs others / measure).
3. **Explains**: its AI summarizes what has changed; **il validates** (0 rule of AGENTS.md).
4. **Push** its branch, opens / updates its PR to `main`.
5. **Fusionne** if it turns (a teammate takes a look). `main` must always work.
6. **Retrieve** `main` in its branch and read the statutes of the others.

Claude Code: `/sync`. Codex: "sync". Detail in [AGENTS.md](../../AGENTS.md#team-12--team-rules).

## 6. What we keep from our first job (repo amine-ml/Stockline-Hackathon)

| Idea | Where she serves here |
|---|---|
| "never invent", "engage only with a human" | rules_order.py / rules_sales.py |
| "As usual", corrections in the same message, units and conversions (Amine K.) | rules_order.py |
| Quote → "Yes" → confirmed | oral revision before `confirm_order` |
| Customer memory / history | call_context.py (preloaded sheet) |
| Limit Case Tests with Commented Outputs (`try_message.py`) | `scripts/run_scenarios.py` + `scenarios/` |
