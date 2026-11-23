# Daycem – 🧠 « Le bon vendeur » (intelligence commerciale + naturel)

**Critères du jury** : Intelligent (« propose des alternatives, sait que ce chef refuse les substitutions ») et Naturel.
C'est la scène que le CTO veut voir : un client qui préfère un produit en rupture → l'agent voit un remplaçant
disponible, **en promotion**, le propose et **argumente** — mais seulement si le client accepte les remplacements.
**Interrupteur** : `TEAM_SALES_RULES`. **Branche** : `daycem/<sujet>`.

## La vraie vie
- **Le Pétrin de Colomiers** (accepte les substitutions si on prévient) demande du tourage AOP, en rupture jusqu'à fin
  novembre. Lucie : « L'AOP est en rupture jusqu'à la fin du mois. J'ai le tourage 82 %, 9 euros 20 le kilo au lieu
  de 11 euros 40, et il est en promo cette semaine ; pour vos croissants il feuillette très bien. Je vous en mets 3
  cartons ? » Elle attend le « oui ».
- **Maison Sarrailh** demande la même chose. Lucie sait que Guy « préfère manquer » : elle annonce la rupture et la date
  de retour, **sans** proposer de remplaçant.
- **Boulangerie Escaich** compare les prix (« Garonne Boulange me la fait à 18 la tradi ») : Lucie ne fait pas de remise
  (seul Bernard au-delà de 5 %), mais met en avant le prix négocié, la qualité Lauragais, et propose de transmettre.

## Tes fichiers
| Fichier | Rôle |
|---|---|
| `apps/ai/app/agent/rules_sales.py` | **à toi** : `SALES_RULES` (texte du prompt) + `refuses_substitution`, `rank_alternatives` |
| `apps/ai/tests/test_team_todo.py` | ta section « Daycem » : enlève les `@TODO` et fais passer |
| `scripts/setup_demo_data.py` | **à toi** : crée la promo de démo par l'API (data/seed n'est pas dans git) |

Lis d'abord : `data/context/04-playbook-clients.md` (« Substitutions : jamais sans accord »), `05-prix-et-credit.md`
(remises, règles de prix), les fiches `data/context/clients/` de Sarrailh (c0001), Escaich (c0006), Pétrin de Colomiers
(c0021), La Gerbe d'Or (c0013) : sections « Ce qui les agace », « Comment leur parler », [interfaces.md](../interfaces.md) §5.

## Tes tâches, dans l'ordre
| # | Tâche | Fini quand |
|---|---|---|
| T0 | `run_scenarios.py --owner daycem` (S04, S05) : noter ce qui échoue | baseline notée dans ton statut |
| T1 | `SALES_RULES` v1 : lire les préférences avant tout remplaçant ; refus → annoncer rupture + date de retour, rien d'autre ; sinon UN remplaçant argumenté (usage, prix, promo) puis demander l'accord ; pas de remise au téléphone ; `TEAM_SALES_RULES=1` | S04 et S05 verts |
| T2 | **Naturel** : ne jamais dire à voix haute son raisonnement (défaut vu sur S03 : « Le compte est bloqué ; je ne prends pas de commande, je note le message. Bonjour… ») ; chiffres et unités à l'oral ; ton selon la fiche (tutoiement, « appeler Nadine, pas Guy ») ; avec Mohamed Amine : plus de « je regarde » dit par le modèle quand les phrases d'attente sont actives | à l'écoute sur S01-S05 : on dirait une personne |
| T3 | `refuses_substitution` + `rank_alternatives` + tests ; brancher dans `product_insight` avec Youssef | tests verts |
| T4 | **Promo de démo** : `scripts/setup_demo_data.py` crée une règle de prix (ex. tourage 82 % −8 % jusqu'au 30/11) via `POST /api/price-rules` ; vérifier que `get_price` la voit ; l'écrire dans DECISIONS.md (données modifiées, assumé) | S05 : l'agent cite la promo |
| T5 | Négociation (Escaich) : pas de remise, valoriser, proposer de transmettre à Bernard (événement `price_negotiation`) | un scénario S4x vert |

**Tes scénarios** (S40–S49, au moins 2) : La Gerbe d'Or (refuse les substitutions) demande un produit en rupture ;
Escaich négocie le prix de la tradi.

## Avec qui te coordonner
- **Amine Khalil** : lui = ce qui est commandé et validé ; toi = comment on vend et comment on parle.
- **Youssef** : le format de `product_insight` et le classement des remplaçants.
- **Mohamed Amine** : le ton des phrases d'attente.

## Pièges
- Jamais de remplacement **ajouté** à la commande sans un « oui » explicite (`substitute_for` dans `add_order_line`).
- Une promo n'est citée que si l'ERP la renvoie (jamais inventée).
- Rester bref : 1 à 2 phrases par réplique ; l'argument tient en une phrase.

## Le premier message à donner à ton IA de code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md et docs/team/tasks/daycem.md. Je suis Daycem.
> Explique-moi T0 et T1 en mots simples, propose un plan, et attends mon accord avant de coder.
