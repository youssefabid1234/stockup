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
### Commande juste (Amine Khalil)
### Bon vendeur (Daycem)

## 5. Données modifiées pour la démo

(À remplir : ex. promo tourage 82 % créée par `scripts/setup_demo_data.py`.)

## 6. Ce qui n'a pas marché / abandonné
