# Scénarios d'appel – nos tests de toute la nuit

Chaque fichier `S*.json` est **un appel** (plusieurs répliques du client) avec ce qu'on attend de l'agent. On les
rejoue après chaque changement : si un scénario qui passait se met à échouer, on a cassé quelque chose.

```bash
# services lancés, depuis la racine du repo (Windows : apps/ai/.venv/Scripts/python ; Mac/Linux : apps/ai/.venv/bin/python)
apps/ai/.venv/Scripts/python scripts/run_scenarios.py                # tous, via /chat (pas d'audio)
apps/ai/.venv/Scripts/python scripts/run_scenarios.py --owner daycem # ceux d'une personne
apps/ai/.venv/Scripts/python scripts/run_scenarios.py --only S05 --voice  # vrai chemin vocal + vrais temps (coûte du TTS)
apps/ai/.venv/Scripts/python scripts/run_scenarios.py --reset        # remet les données de l'ERP à zéro avant
```

⚠️ Chaque réplique appelle le vrai LLM (crédits plafonnés) : rejouez **vos** scénarios (`--owner`), tous seulement à
la sync. Les résultats vont dans `scenarios/results/` (ignoré par git).

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

| Clé de `expect` | Sens |
|---|---|
| `tools_any` | au moins un de ces outils a été appelé |
| `tools_none` | aucun de ces outils n'a été appelé (ex. pas de `confirm_order` avant le « oui ») |
| `says_any` | la réponse contient au moins un de ces mots (sans tenir compte des majuscules) |
| `says_none` | la réponse ne contient aucun de ces mots |
| `max_ms` | durée max de la réplique (via /chat : tour complet ; `--voice` : fin de parole → premier son) |

Restez **tolérants** sur le texte (plusieurs formulations dans `says_any`) : l'agent ne dit jamais deux fois la même
phrase. Vérifiez surtout ce qui compte : les outils appelés, les chiffres, les interdits.

## Qui écrit quoi

Chacun écrit **2 scénarios** de son domaine en plus de ceux-ci (numéros réservés) :
Mohamed Amine S10–S19 · Youssef S20–S29 · Amine Khalil S30–S39 · Daycem S40–S49.

## Les clients utiles (données réelles du pack)

| Client | Id | Pourquoi |
|---|---|---|
| Maison Sarrailh (Nadine au téléphone) | cli_0001 | Exigeante, veut qu'on lui relise ; **jamais de substitution sur le beurre** ; livrée mar/jeu/sam |
| Boulangerie Escaich | cli_0006 | Méfiant, **sensible au prix** (« Garonne Boulange me la fait à 18 la tradi ») ; livrée mar/ven |
| Le Pétrin de Balma | cli_0007 | **Compte bloqué** (deuxième LCR rejetée) |
| Le Pétrin de Colomiers | cli_0021 | Achète du tourage AOP, **accepte les substitutions équivalentes si on prévient** ; livré lun/mer |
| La Gerbe d'Or | cli_0013 | **Refuse les substitutions** : appeler avant toute modification |

Ruptures du jour (mardi 24/11) : beurre de tourage AOP 84 % (`prd_0025`, remplaçant : tourage 82 % `prd_0026`),
vanille Bourbon (`prd_0022`, remplaçant : extrait liquide).
