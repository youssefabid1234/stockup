# Youssef – ⚡ « Plusieurs cerveaux en parallèle » (vitesse + architecture)

**Critères du jury** : Rapide (< 1,5 s) et Intelligent. **Conseil du CTO** : plusieurs agents à la fois.
**Interrupteurs** : `TEAM_ORCHESTRATOR`, `TEAM_PRELOAD`, `TEAM_PRODUCT_INSIGHT`, `TEAM_FAST_MODEL`.
**Branche** : `youssef/<sujet>`.

## La vraie vie
Lucie reconnaît Nadine dès le « Bonjour » et ouvre sa fiche (habitudes, préférences, compte) **une fois**. Pendant
qu'elle parle avec Nadine, un collègue regarde le stock. Un seul coup d'œil à l'écran lui donne stock + prix + remplaçant.
Aujourd'hui l'agent enchaîne les outils un par un (search → get_client → get_product_stock → get_price →
find_alternatives) : 4 à 6 allers-retours ≈ 1 s chacun, avant de dire un mot.

## Tes fichiers
| Fichier | Rôle |
|---|---|
| `apps/ai/app/agent/orchestrator.py` | **à toi** : agent rapide + agent cerveau |
| `apps/ai/app/agent/call_context.py` | **à toi** : la fiche client préchargée (v0 qui marche déjà : fiche + contexte en parallèle) |
| `apps/ai/app/tools/product_insight.py` | **à toi** : le super-outil |
| `apps/ai/app/agent/loop.py` | partagé, fichier du kit : n'y touche que pour l'orchestration, en prévenant Mohamed Amine |
| `scripts/run_scenarios.py` | **à toi** : le rejeu des scénarios (marche déjà, via /chat ou `--voice`) |

Lis d'abord : `apps/ai/README.md` (boucle, outils), `GUIDE-AGENTS.md` (outils, contexte, cache de prompt, modèles,
Jev), `GUIDE-VOIX.md` §4.3-4.6, [interfaces.md](../interfaces.md) §1-3.

## Tes tâches, dans l'ordre
| # | Tâche | Fini quand |
|---|---|---|
| T0 | Lancer `run_scenarios.py --only S01 S05` : noter le nombre d'outils appelés et les temps (baseline dans DECISIONS.md) | baseline notée |
| T1 | **Super-outil** `product_insight` : produit + stock + prix client + remplaçants (stock, prix, promo) en un seul appel, en parallèle (`asyncio.gather`) ; test ; `TEAM_PRODUCT_INSIGHT=1` | S04/S05 : moins d'outils appelés, même résultat ; test `test_product_insight_…` vert |
| T2 | **Fiche préchargée** : compléter `load_call_context` (stock des produits habituels, promos actives) ; la charger dès que le client est identifié (résultat de `get_client`, ou `search` avec un seul client) et la garder sur la `Conversation` ; `TEAM_PRELOAD=1` | à partir du 2e tour, plus d'appel à get_client / get_context ; `loaded_ms` < 300 |
| T3 | **Cache de prompt** : vérifier que le gros contexte statique est lu depuis le cache Anthropic (`cache_read_input_tokens` dans `usage`) ; la fiche client reste à la fin | cache_read > 0 dès le 2e tour |
| T4 | **Orchestrateur** : agent rapide (`get_fast_llm_client`, Haiku) en parallèle de l'agent cerveau ; tours simples (oui / non / merci / c'est tout) au rapide seul (Jev ou règles pour classer) ; jamais de contradiction, jamais de chiffre côté rapide ; `TEAM_ORCHESTRATOR=1` | S06 : premier texte < 1,5 s ; tous les scénarios toujours verts |
| T5 | Mesures : à chaque sync, `run_scenarios.py` complet et une ligne dans le tableau de DECISIONS.md | tableau à jour |
| T6 | (extension, après le cas 1) S08 : réclamation + commande dans le même appel | S08 vert |

**Tes scénarios** (S20–S29, au moins 2) : par exemple un appel à plusieurs produits dont un en rupture, et un client
qui ne se nomme pas (« c'est moi, comme d'hab ») → l'agent doit demander qui appelle.

## Avec qui te coordonner
- **Mohamed Amine** : qui parle en premier (agent rapide ou phrase d'attente) → interfaces §1, à H+2.
- **Daycem** : le format des remplaçants (`rank_alternatives`) et la promo de démo.
- **Amine Khalil** : ce que sa partie lit dans la fiche (`CallContext`).

## Pièges
- Plus rapide mais faux ne gagne pas : rejouer **tous** les scénarios après chaque étape.
- L'agent rapide n'a pas d'outils : il ne doit jamais affirmer un stock, un prix ou une date.
- Le prompt grossit avec la fiche : la garder courte (top N entrées, corps tronqués).

## Le premier message à donner à ton IA de code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md et docs/team/tasks/youssef.md. Je suis Youssef.
> Explique-moi T0 et T1 en mots simples, propose un plan, et attends mon accord avant de coder.
