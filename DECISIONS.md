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

- Deux annonces très courtes sont préparées à l'ouverture avec la voix configurée. Une frappe de clavier de 0,13 s (MP3 décodé localement) est synthétisée en mémoire. Les sons partagent le segment interruptible de la réponse. Le premier son et le premier octet de synthèse de la réponse utile sont chronométrés séparément.
- Si la transcription ne suffit pas à détecter une demande de recherche, le premier appel ERP confirmé peut déclencher l'annonce. La voix garde le jargon de base si l'ERP est indisponible. Les tests d'intégration couvrent aussi l'arrêt de l'audio après une erreur et les annonces répétées.
- Avec l'orchestrateur actif, sa voix a priorité sur l'annonce préparée. La règle commune reste à valider avec Youssef. Le ton et la consigne contre les doublons sont proposés à Daycem dans le [suivi](docs/team/status/mohamed-amine.md).
- Rejeu local via WebSocket, données de démonstration et trois fournisseurs simulés, avec et sans `TEAM_FILLERS` : **3 répliques sur 10** passent dans les deux configurations. S06 et les deux répliques de S10 passent. S01 et S05 échouent sur leurs attentes métier. Sur S11, le modèle simulé lance une recherche sur « merci ». Un test d'intégration vérifie que même dans ce cas la voix ne joue ni annonce ni clavier. Les mesures de référence au micro, le délai perçu et le premier tour ElevenLabs restent à relever sur le pack du Fournil.
- T7 facultatif est reporté. Espace fournit un point de départ reproductible pour mesurer le délai et interrompre l'agent pendant la démo.

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

**T2 · Fiche client préchargée (`TEAM_PRELOAD`, lun. 23/11 23h50).** Dès que le client est identifié (get_client, ou
une recherche qui ne renvoie qu'un client), sa fiche (statut, jours de livraison ERP, préférences, panier habituel
**avec le stock**, encours, notes) est chargée en arrière-plan, en parallèle, puis ajoutée à la fin du prompt des
répliques suivantes (« n'appelle plus get_client ni get_context »). Les notes « Fermé le <jour> » sont retirées
quand l'ERP livre ce jour (décision : l'ERP et l'historique font foi).

Mesure via /chat, `--reset`, `TEAM_ORDER_RULES=1`, 9 répliques (S01, S02, S05) :

| | Interrupteur éteint | Allumé |
|---|---|---|
| Répliques réussies | 9/9 | 9/9 |
| 1re réplique de chaque appel | 7,6 · 5,7 · 4,7 s | 6,9 · 6,2 · 5,5 s (identique : fiche pas encore connue) |
| Répliques suivantes (médiane) | 2,7 s | 4,4 s (bruit ±1-2 s, pas de gain mesurable) |
| S02 « mettez-en 12 » | recrée un brouillon et relit **tout** l'habituel (11 lignes) | **modifie la ligne** et relit 1 ligne |
| S05 (note « Fermé le mercredi ») | ne parle pas du mercredi | demande « vous êtes bien ouvert mercredi ? » (lu via get_context au 1er tour, avant la fiche) |

Lecture : avec l'historique complet (outil de rejeu corrigé), l'agent **ne recherchait déjà plus le client** après le 1er
tour : la fiche n'enlève donc pas d'appel aux tours suivants. **Le temps se perd au 1er tour** (4 à 6 appels d'outils
avant que le client soit connu). La fiche reste **désactivée par défaut** ; prochaine étape : identifier le client
dès le début du 1er tour (fiche en parallèle de la réflexion) et le super-outil produit.

**Outil de rejeu corrigé** : en /chat il renvoie maintenant l'historique complet (outils appelés + résultats) comme la
page Voix ; avant, l'agent oubliait son brouillon et recommençait (S01·2 : 6 outils, 9,4 s → 1 outil, 2,4 s).
### Commande juste (Amine Khalil)
### Bon vendeur (Daycem)

## 5. Données modifiées pour la démo

(À remplir : ex. promo tourage 82 % créée par `scripts/setup_demo_data.py`.)

## 6. Ce qui n'a pas marché / abandonné
