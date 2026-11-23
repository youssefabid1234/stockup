# Les contrats entre nos 4 chantiers

> Chacun code dans **ses** fichiers. Ces contrats disent ce que chacun donne aux autres et attend d'eux. On ne les
> change **qu'après l'avoir dit dans le groupe** (et prévenu la personne concernée). Le code de référence est indiqué.

## 0. Les interrupteurs (`apps/ai/app/team_flags.py`)

Chaque brique est **éteinte par défaut** : tant qu'elle est éteinte, le kit se comporte exactement comme à l'origine.
On l'allume dans `.env` (à la racine) puis on redémarre le service IA (Ctrl-C dans son terminal, relancer).

| Interrupteur | Brique | Propriétaire |
|---|---|---|
| `TEAM_FILLERS=1` | phrases d'attente + bruit de clavier | Mohamed Amine |
| `TEAM_ORCHESTRATOR=1` | agent rapide + agent cerveau en parallèle | Youssef |
| `TEAM_PRELOAD=1` | fiche client préchargée | Youssef |
| `TEAM_PRODUCT_INSIGHT=1` | super-outil produit (enregistré au démarrage) | Youssef |
| `TEAM_ORDER_RULES=1` | règles « commande juste » dans le prompt | Amine Khalil |
| `TEAM_SALES_RULES=1` | règles « bon vendeur » dans le prompt | Daycem |
| `TEAM_FAST_MODEL=claude-haiku-5-5` | modèle de l'agent rapide | Youssef |

Une brique n'est allumée **par défaut sur `main`** (dans `.env.example`) que quand ses scénarios passent.

## 1. Voix ↔ tour de parole (Mohamed Amine ↔ Youssef)

Fichier : `apps/ai/app/services/voice_session.py` (Mohamed Amine) appelle, dans cet ordre, pour chaque tour :

1. `await fillers.on_turn_start(speaker, heard)` juste après la transcription finale (t0 + quelques ms)
2. l'agent : `run_voice_turn(...)` (orchestrateur de Youssef) si `TEAM_ORCHESTRATOR=1`, sinon `run_agent(...)` du kit
3. `await fillers.on_tool_call(speaker, tool_name)` à chaque appel d'outil

**Règle anti-chevauchement** : si l'agent rapide de Youssef parle déjà (texte qui arrive en < 700 ms), aucune phrase
d'attente. Proposition : l'orchestrateur expose `expects_tools(heard) -> bool` (Jev ou mots-clés) ; `on_turn_start`
ne joue une phrase d'attente que si `True`. À trancher entre vous deux à H+2, puis noter ici.

**`Speaker`** (dans voice_session.py) : Mohamed Amine ajoute `async play_audio(mime, data)` pour jouer un son
préenregistré dans le même segment audio que la réponse.

## 2. Fiche client et super-outil (Youssef → Amine Khalil, Daycem)

**`CallContext`** (`apps/ai/app/agent/call_context.py`) : la fiche du client au téléphone, chargée une fois.
Champs (le contrat) : `client_id, name, status, blocked, delivery_days, preferences, contacts, usual[UsualItem],
outstanding, credit_limit, open_issues, notes, context_entries[{kind,title,body}], active_promos, loaded_ms`.
Elle est ajoutée **à la fin** du prompt (`render_for_prompt`). Amine K. et Daycem peuvent s'appuyer dessus dans leurs
règles (« d'après la fiche du client au téléphone… »).

**`product_insight(client_id, product_id, qty)`** (`apps/ai/app/tools/product_insight.py`) renvoie :

```json
{
  "product": {"id", "name", "unit", "available", "clientPrice", "listPrice", "priceExplanation"},
  "inStock": true,
  "alternatives": [{"id", "name", "unit", "available", "clientPrice", "listPrice", "promo": "−8 % jusqu'au 30/11"}]
}
```

Les `alternatives` sont triées par `rules_sales.rank_alternatives` (Daycem) quand elle existe.

## 3. Orchestrateur (Youssef)

`run_voice_turn(messages, *, llm, tools, mode, actor_name, call_context)` : **même contrat que `run_agent`** (mêmes
événements `text`, `tool_call`, `tool_result`, `done`, `error`, et il ajoute les messages à `messages`). La voix ne voit
pas la différence. L'agent rapide **ne dit jamais** un chiffre, un stock, un prix ou une promesse : seul l'agent cerveau
le fait (« ne jamais inventer »).

## 4. Règles « commande juste » (Amine Khalil)

`apps/ai/app/agent/rules_order.py` : `ORDER_RULES` (texte) inséré dans le prompt par `order_rules_section()` en modes
voix et chat (pas en mode commande). Fonctions déterministes testées (`next_delivery_date`, `sacks_from_words`).
Les règles de prix, stock et crédit restent dans le backend : lire les `warnings` de la commande (`client_blocked`,
`no_route`…) au lieu de les recoder.

## 5. Règles « bon vendeur » (Daycem)

`apps/ai/app/agent/rules_sales.py` : `SALES_RULES` (texte) inséré par `sales_rules_section()`. Fonctions
`refuses_substitution(preferences, product_name)` et `rank_alternatives(alternatives, preferences)` utilisées par
`product_insight` (Youssef). Promo de démo : créée par l'API (`POST /api/price-rules`) par `scripts/setup_demo_data.py`,
parce que `data/seed/` n'est pas dans git.

## 6. Prompt : un seul fichier partagé, chacun sa ligne

`apps/ai/app/agent/prompts.py` assemble : rôle → règles du kit → règles du mode → **règles commande (Amine K.)** →
**règles vente (Daycem)** → date → contexte entreprise (gros, statique, mis en cache) → **fiche client (Youssef,
dynamique)**. Personne ne réécrit `prompts.py` : chacun édite **son** module. Si `VOICE_RULES` ou `BASE_RULES` du kit
doivent changer, on en parle d'abord (Amine K. tranche pour la commande, Daycem pour le ton).

## 7. Scénarios (tous)

`scenarios/S*.json` + `scripts/run_scenarios.py` (Youssef). Numéros réservés : Mohamed Amine S10–S19, Youssef S20–S29,
Amine Khalil S30–S39, Daycem S40–S49. Format : [scenarios/README.md](../../scenarios/README.md).
