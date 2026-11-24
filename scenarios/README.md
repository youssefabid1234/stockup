# Call scenarios – our tests all night long

Each `S*.json` file is ** a call** (several replicas of the client) with what is expected of the agent.
Replay after every change: if a passing scenario starts to fail, we've broken something.

```bash
# services lancés, depuis la racine du repo (Windows : apps/ai/.venv/Scripts/python ; Mac/Linux : apps/ai/.venv/bin/python)
apps/ai/.venv/Scripts/python scripts/run_scenarios.py                # tous, via /chat (pas d'audio)
apps/ai/.venv/Scripts/python scripts/run_scenarios.py --owner daycem # ceux d'une personne
apps/ai/.venv/Scripts/python scripts/run_scenarios.py --only S05 --voice  # vrai chemin vocal + vrais temps (coûte du TTS)
apps/ai/.venv/Scripts/python scripts/run_scenarios.py --reset        # remet les données de l'ERP à zéro avant
```

Each replica calls the true LLM (ceiling credits): replay **vos** scenarios (`--owner`), all of them only at
Sync. The results go to `scenarios/results/` (ignored by git).

## Format

```json
{
  "id": "S05",
  "owner": "daycem",
  "title": "Rupture AOP, client qui accepte les remplacements : proposer et argumenter le 82 %",
  "why": "Ce que ce scénario prouve (critère du jury)",
  "client": "cli_0021",
  "turns": [
    {
      "say": "Bonjour, c'est Le Pétrin de Colomiers…",
      "expect": {
        "tools_any": ["search", "get_client"],
        "tools_none": ["confirm_order"],
        "says_any": ["82"],
        "says_none": ["pain au chocolat"],
        "max_ms": 8000
      }
    }
  ]
}
```

| `expect` key | Sense |
|---|---|
| `tools_any` | at least one of these tools has been called |
| `tools_none` | None of these tools were called (e.g. no `confirm_order` before the "yes") |
| `says_any` | the answer contains at least one of these words (excluding capitals) |
| `says_none` | the answer does not contain any of these words |
| `max_ms` | max duration of the replica (via /chat: full turn; `--voice`: end of speech → first sound) |

Stay **tolerant** on the text (several formulations in `says_any`): the agent never says twice the same
Please check what matters: the tools called, the numbers, the prohibitions.

## Who writes what

Each person writes **2 scenarios** of his domain in addition to them (reserved numbers):
Mohamed Amine S10–S19 · Youssef S20–S29 · Amine Khalil S30–S39 · Daycem S40–S49.

## Useful customers (real package data)

| Client | Id | Why? |
|---|---|---|
| Maison Sarrailh (Nadine on the phone) | cli_0001 | Demanding, wants to be read again; **Never substitute on butter**; delivered mar/game/sam |
| Boulangerie Escaich | cli_0006 | Beware, ** price sensitive** ("Garonne Boulange me makes it to 18 the tradi"), delivered mar/ven |
| Le Pétrin de Balma | cli_0007 | **Clocked account** (second LCR rejected) |
| Le Pétrin de Colomiers | cli_0021 | Purchased from AOP laminating butter, ** accepts equivalent substitutions if ** is prevented; delivered on/off |
| La Gerbe d'Or | cli_0013 | **Refuses ** substitutions: call before changes |

Daybreaks (Tuesday 24/11): laminating butter AOP 84 % (`prd_0025`, replacing: laminating butter 82 % `prd_0026`),
Bourbon vanilla (`prd_0022`, replacing: liquid extract).
