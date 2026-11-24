# Amine Khalil – 🧠 « La commande juste » (intelligence)

**Critère du jury** : Intelligent — « la bonne commande dans l'ERP, le bon produit, le bon client. Il n'invente jamais. »
**Interrupteur** : `TEAM_ORDER_RULES`. **Branche** : `amine-khalil/<sujet>`.

## La vraie vie
Nadine dit « comme d'hab, et mets-moi 10 de tradi pour jeudi ». Lucie sait que « 10 de tradi » = **10 sacs de 25 kg**
de T55 tradition (pas 10 kilos), que « comme d'hab » = le panier habituel de la boulangerie, que Sarrailh est livré
mardi / jeudi / samedi, qu'après 17h c'est pour le surlendemain. Si Nadine dit « finalement 12 », Lucie **modifie** la
ligne. Avant de valider, elle **relit** tout. Au Pétrin de Balma (compte bloqué), elle ne promet rien.

## Tes fichiers
| Fichier | Rôle |
|---|---|
| `apps/ai/app/agent/rules_order.py` | **à toi** : `ORDER_RULES` (texte du prompt) + fonctions déterministes |
| `apps/ai/tests/test_team_todo.py` | ta section « Amine Khalil » : enlève les `@TODO` et fais passer |
| `apps/ai/app/tools/delivery.py` (à créer si besoin) | **à toi** : un outil « date de livraison » si les règles ne suffisent pas (ajouter l'import dans `tools/__init__.py`, une ligne) |
| `data/context/*.md` | lecture ; un ajout se discute (tout est lu à chaque tour : ça coûte en vitesse) |

Lis d'abord : `data/context/01-entreprise.md` (« Règles de la maison »), `02-journee-type.md` (heures limites),
`03-glossaire-produits.md` (« On dit »), `04-playbook-clients.md` (« Prendre une commande »), `ERP.md` (cycle de vie
d'une commande, alertes), `METIER.md` (prise de commande), [interfaces.md](../interfaces.md) §4.

Ton expérience de notre premier repo s'applique directement : « comme d'hab », corrections dans le même message,
unités et conversions, « ne jamais inventer ».

## Tes tâches, dans l'ordre
| # | Tâche | Fini quand |
|---|---|---|
| T0 | `run_scenarios.py --owner amine-khalil` (S02, S03) + S01, S07 : noter ce qui échoue et pourquoi | baseline notée dans ton statut |
| T1 | `ORDER_RULES` v1 : unités (sacs, plaques, cartons, briques), « chocolatine », « comme d'hab », changement d'avis = **modifier** la ligne, relecture orale **avant** `confirm_order`, quantités dites à l'oral ; `TEAM_ORDER_RULES=1` | S01, S02, S07 verts |
| T2 | **Dates de livraison** : jours de livraison du client, heure limite 17h (Lauragais-Tarn : la veille avant 12h), jamais un jour non livré ; `next_delivery_date` déterministe + tests (ou un outil `delivery.py`) | tests verts ; « pour mercredi » à Sarrailh → l'agent propose jeudi |
| T3 | **Alertes de l'ERP** : après `create_draft_order`, lire les `warnings` (client_blocked, no_route…) et les dire simplement ; compte bloqué = prendre le message, rien promettre | S03 vert sans phrase « interne » |
| T4 | Franco 150 € HT (sinon 12 € de livraison) : le dire si la commande est petite ; quantités inhabituelles (10× l'habitude) : faire confirmer | un scénario S3x de chaque |
| T5 | (extension) réclamations : enregistrer avec `log_client_event` + la commande concernée | S08 vert (avec Youssef) |

**Tes scénarios** (S30–S39, au moins 2) : par exemple un dépannage de levure le jour même (possible jusqu'à 9h si la
tournée n'est pas partie), une commande sous le franco, une quantité anormale.

## Avec qui te coordonner
- **Daycem** : vous écrivez tous les deux des règles de prompt. Toi : **ce qui est commandé** (produit, quantité, date,
  validation). Daycem : **comment on vend et comment on parle** (remplaçants, promos, ton). En cas de doute, demandez-vous.
- **Youssef** : ce que tu veux trouver dans la fiche préchargée (`CallContext`).

## Pièges
- Les règles de prix, de stock et de crédit restent dans le backend : on **lit** l'ERP, on ne les recode pas.
- Le prompt est relu à chaque étape : des règles courtes et claires, pas un roman.
- La date de référence est celle du pack (mardi 24/11/2026, 6h30), jamais l'horloge réelle.

## Le premier message à donner à ton IA de code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md et docs/team/tasks/amine-khalil.md. Je suis Amine Khalil.
> Explique-moi T0 et T1 en mots simples, propose un plan, et attends mon accord avant de coder.
