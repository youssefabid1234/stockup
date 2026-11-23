# DECISIONS – Équipe 12 · Le Fournil Occitan

> Livrable lu par le jury : le problème choisi et pourquoi, nos choix techniques, ce qui a marché ou pas, nos mesures.
> Chacun ajoute ses choix **au fil de l'eau** (quoi, pourquoi, essayé et abandonné), dans sa section.

## 1. Le problème choisi : le standard téléphonique

**Qui** : Lucie, seule au standard de 5h30 à 13h, et les trois commerciaux qui saisissent 71 % des commandes à la main.
**Quand** : surtout entre 12h et 15h (pic à 13h : 4 755 commandes sur 3 ans), quand les boulangers passent leurs
commandes après le coup de feu du matin.
**Ce que ça coûte aujourd'hui** : 45 % des commandes arrivent par téléphone (11 231 / 24 769) et sont toutes retapées
dans l'ERP ; une erreur (10 kg au lieu de 10 sacs, un remplacement non accepté, une livraison promise un jour de
fermeture) se paie tout de suite sur des produits qui périssent.
**Pourquoi la voix** : un boulanger a les mains dans la farine à 13h ; il appelle, il ne tape pas.
**Ce que l'agent change** : il prend la commande pendant l'appel, vérifie stock et compte, propose et argumente un
remplaçant seulement si le client les accepte, relit, et la commande est dans l'ERP à la fin de l'appel.
Extension prévue : réclamations et questions dans le même appel.

## 2. Architecture (résumé)

Agent de base du kit + 6 briques activables (`TEAM_*`) : phrases d'attente et bruit de clavier, agents en parallèle
(rapide + cerveau), fiche client préchargée, super-outil produit, règles « commande juste », règles « bon vendeur ».
Détail : `docs/team/README.md`.

## 3. Mesures

Médiane et pire cas sur nos scénarios (`scripts/run_scenarios.py`, `--voice` pour les temps vocaux). t0 = relâchement
de la touche Espace (push-to-talk).

| Version | sttMs | llmFirstTokenMs | ttsFirstByteMs | totalMs | perceivedMs | Scénarios réussis | Coût / appel |
|---|---|---|---|---|---|---|---|
| Kit d'origine | | | | | | | |
| + … | | | | | | | |

Premier relevé (23/11, via /chat, sans audio) : S03 (client bloqué) PASS, 6 099 ms, premier mot à 4 092 ms ; défaut
noté : l'agent prononce son raisonnement (« Le compte est bloqué ; je ne prends pas de commande… »).

## 4. Choix par chantier

### Vitesse et voix (Mohamed Amine)
### Plusieurs agents, fiche préchargée, super-outil (Youssef)

**Mesure de départ (T0, lun. 23/11 23h, `TEAM_ORDER_RULES=1`, autres briques éteintes).**
`totalMs` = fin de parole du client → premier octet audio de l'agent (`--voice`, phrase tapée donc sans STT) ; c'est la
métrique du jury. Via /chat (sans audio) on mesure le tour complet : le texte n'arrivant qu'à la fin, c'est presque
la même chose (S01·1 : 7 286 ms /chat, 6 883 ms voix).

| Scénario · réplique | Outils appelés (un par un) | /chat | `--voice` totalMs | Résultat |
|---|---|---|---|---|
| S01·1 « 10 sacs de tradi pour jeudi » | search, get_context, check_delivery_date, get_product_stock, create_draft_order | 7 286 ms | 6 883 ms (LLM 6 739 + TTS 144) | PASS |
| S01·2 « oui, validez » | confirm_order | 2 377 ms | 3 340 ms | PASS |
| S05·1 « 3 cartons de tourage AOP » | search, get_client, get_context, get_product_stock, check_delivery_date | 7 928 ms | – | PASS |
| S05·2 « il est à combien, le 82 ? » | get_price | 4 856 ms | – | PASS |
| S05·3 / S05·4 | aucun | 2 116 / 1 942 ms | – | FAIL (note « Fermé le mercredi ») |

Lecture : les répliques lentes (7-8 s) sont celles où le modèle enchaîne 5 outils, un par un ; la voix (TTS) ne pèse que
≈ 0,15 s. Cibles : moins d'allers-retours (super-outil, fiche préchargée) et un premier son plus tôt (agent rapide,
phrases d'attente de Mohamed Amine).

**Outil de rejeu corrigé** : en /chat il renvoie maintenant l'historique complet (outils appelés + résultats) comme la
page Voix ; avant, l'agent oubliait son brouillon et recommençait (S01·2 : 6 outils, 9,4 s → 1 outil, 2,4 s).
### Commande juste (Amine Khalil)
### Bon vendeur (Daycem)

## 5. Données modifiées pour la démo

(À remplir : ex. promo tourage 82 % créée par `scripts/setup_demo_data.py`.)

## 6. Ce qui n'a pas marché / abandonné
