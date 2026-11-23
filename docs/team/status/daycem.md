# Daycem – « Le bon vendeur »  ·  mis à jour lun. 23/11, 22h30

- Fait depuis la dernière sync :
  - T0 : photo de départ de S04 et S05 (tous les `TEAM_*` éteints, ERP remis à zéro avant chaque scénario). Détail plus bas.
  - T1 : `SALES_RULES` écrit dans `agent/rules_sales.py`, rejoué 3 fois (T1, T1b, T1c). Les règles sont générales
    (aucun nom de client, de produit ou de personne) ; un test le vérifie (`test_sales_rules_stay_general`).
  - Dernière correction (pas encore rejouée) : la date de retour est donnée telle qu'elle est écrite dans les
    documents, sans la transformer ni la déduire.
- En cours : T2 (naturel).
- Bloqué / j'attends : rien.
- J'ai besoin de (qui, quoi) :
  - **Amine K. : brouillon orphelin sur S05** (2 rejeux sur 2). Au tour 3 l'agent crée un brouillon, au tour 4 il en
    recrée un et confirme le second : CMD-2026-007543 reste en brouillon à côté de CMD-2026-007544 confirmée. Cause
    probable : le runner ne rejoue que le texte, l'id du brouillon est perdu. Non vérifié en vrai appel vocal.
  - Youssef : `load_call_context` n'est appelé nulle part (ni `voice_session.py` ni `/chat`), donc la fiche n'est
    jamais préchargée. Aujourd'hui l'agent relit la fiche avec `search` + `get_client` + `get_context` à chaque tour.
  - Youssef (T3 / `product_insight`) : `GET /api/products/prd_0025/alternatives` classe par prix proche :
    demi-sel, beurre doux AOP, puis seulement le tourage 82 %. `rank_alternatives` devra classer par usage.
  - Mohamed Amine : « Je regarde. » n'est dit que si le modèle y pense (tour 1 seulement sur S05) ; aux autres tours,
    5,8 à 8,3 s de silence. Les phrases d'attente automatiques sont nécessaires.
- Interrupteur(s) : TEAM_SALES_RULES = on sur ma branche · prêt à allumer sur main ? oui (S04 et S05 passent)
- Mesure (scénarios, ms) : voir les tableaux ci-dessous.
- Changement de contrat demandé (interfaces.md) : aucun.

## Photo de départ T0 (kit seul, Sonnet, via `POST /chat`)

| Scénario · tour | Résultat | Appels modèle | Premier mot | Total | Tokens (sortie · cache écrit · cache lu) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 7 536 ms | 7 491 ms | 417 · 28 696 · 51 387 |
| S05 · 1 | PASS | 3 | 5 625 ms | 5 624 ms | 483 · 2 334 · 76 446 |
| S05 · 2 | PASS | 3 | 956 ms | 5 991 ms | 643 · 3 143 · 77 250 |
| S05 · 3 | PASS | 4 | 1 126 ms | 7 062 ms | 828 · 5 387 · 108 193 |
| S05 · 4 | PASS | 4 | 1 851 ms | 8 195 ms | 860 · 5 360 · 109 013 |

Total : 17 appels au modèle, 3 231 tokens de sortie. Le prompt système fait environ 25 000 tokens, presque tout vient
de `data/context/*.md`. Les tours 2 à 4 commencent vite (~1 s) parce que le modèle dit « Je regarde. » avant ses
outils. Le runner ne rejoue que le texte des tours précédents : l'agent refait `search` et `get_client` à chaque tour.
En vrai appel vocal, l'historique garde les résultats des outils.

Tout passe, mais en écoutant :
- Trop long (3 à 5 phrases au lieu de 1 ou 2).
- Il raconte des causes internes (« grève à la collecte ») et son raisonnement (« je ne vous mets rien de substitué,
  je sais que c'est exclu chez vous », « je vérifie votre dossier avant de confirmer »).
- Il ne donne pas la date de retour (« fin novembre », pourtant dans `01-entreprise.md`) : il dit « aucun arrivage
  prévu ».
- Il promet sans agir : « Je préviens Julien », sans `log_client_event`.
- S05 : il propose le 82 % sans argument d'usage (« feuillette très bien pour vos croissants »). Il appelle le client
  « Monsieur Dumont » alors que l'appelant ne s'est pas nommé (à traiter en T2).
- Bon point : il lit la note « fermé le mercredi » (alors que la fiche dit « livré lun., mer. ») et livre lundi.
  Domaine d'Amine K. (jours de livraison).

Résultats bruts : `scenarios/results/*-baseline.json` (ignoré par git).

## Rejeu T1 (`TEAM_SALES_RULES=1`, SALES_RULES v1 + 1-2 phrases / pas de raisonnement / pas de nom deviné)

| Scénario · tour | Résultat | Appels modèle | Premier mot | Total | Tokens (sortie · cache écrit · cache lu) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 6 591 ms | 6 586 ms | 408 · 31 618 · 53 353 |

Réponse : « Nadine, je n'ai plus de tourage AOP en stock pour jeudi et je n'ai pas encore de date de retour. Voulez-vous
que je note votre demande de 2 cartons ? » Mieux : 2 phrases, aucun remplaçant ni raisonnement, aucune cause
interne, `get_client` bien appelé. Reste : il ne donne pas « fin novembre » (lu dans `01-entreprise.md` comme une
fin de grève, pas comme une date de retour).

## Rejeu T1b (+ règle « date de fin de rupture dans les documents = date de retour »)

| Scénario · tour | Résultat | Appels modèle | Premier mot | Total | Tokens (sortie · cache écrit · cache lu) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 4 751 ms | 4 743 ms | 407 · 31 680 · 53 477 |
| S05 · 1 | PASS | 4 | 9 476 ms | 9 475 ms | 692 · 4 659 · 109 984 |
| S05 · 2 | PASS | 3 | 2 160 ms | 6 158 ms | 501 · 2 425 · 79 891 |
| S05 · 3 | PASS | 4 | 2 401 ms | 9 670 ms | 826 · 4 892 · 111 533 |
| S05 · 4 | PASS | 4 | 8 747 ms | 8 747 ms | 668 · 1 773 · 109 363 |

- S04 : « Nadine, le tourage AOP est en rupture pour l'instant. Le retour à la normale est estimé à fin novembre, sans
  promesse. Je note votre demande de 2 cartons pour jeudi ? » → date donnée, mais « sans promesse » sonne mécanique.
- S05 : argument d'usage présent (« sert aussi pour vos chocolatines »), plus de raisonnement ni de cause interne.
- Problèmes :
  - la date n'est pas stable : S05 tour 1 dit « pas encore de date de retour » avec le même document ;
  - le tour 1 de S05 pose deux questions (jour + accord) et donne le prix avant qu'on le demande ;
  - le premier mot arrive plus tard aux tours 1 et 4 (9,5 s et 8,7 s) : le modèle ne dit plus « Je regarde. » ;
  - **commande en double** : au tour 4, l'agent recrée un brouillon puis le confirme ; CMD-2026-007543 reste en
    brouillon orphelin à côté de CMD-2026-007544 confirmée. Cause probable : le runner ne rejoue que le texte, l'agent
    perd l'id du brouillon. Non vérifié en vrai appel vocal. → Amine K. (commande) et Youssef (runner).

Corrections écrites ensuite (pas encore rejouées) : date dite naturellement (« normalement en fin de mois »), sans
« sans promesse » ; une seule question à la fois (d'abord l'accord sur le remplaçant) ; une courte phrase d'attente
neutre (« Je regarde. ») est autorisée, seul l'explication de ce qu'on vérifie est interdite.

## Rejeu T1c (date dite naturellement, une seule question, « Je regarde. » autorisé)

| Scénario · tour | Résultat | Appels modèle | Premier mot | Total | Tokens (sortie · cache écrit · cache lu) |
|---|---|---|---|---|---|
| S04 · 1 | PASS | 3 | 734 ms | 5 695 ms | 477 · 27 077 · 58 496 |
| S05 · 1 | PASS | 4 | 1 015 ms | 8 311 ms | 738 · 4 751 · 110 534 |
| S05 · 2 | PASS | 3 | 5 761 ms | 5 761 ms | 498 · 2 928 · 80 756 |
| S05 · 3 | PASS | 4 | 8 297 ms | 8 302 ms | 701 · 4 569 · 111 404 |
| S05 · 4 | PASS | 4 | 7 068 ms | 7 094 ms | 468 · 1 107 · 108 623 |

- S04 : « Je regarde. Pour jeudi, je n'ai plus de tourage AOP en stock. Il devrait revenir normalement à partir de
  début décembre. Voulez-vous que je note votre demande de 2 cartons ? » → premier mot à 0,7 s. Mais « début
  décembre » n'est écrit nulle part (le document dit « jusqu'à fin novembre ») : date déduite.
- S05 tour 1 : « Je regarde. Le tourage AOP est en rupture, il devrait revenir normalement en fin de mois. Je peux
  vous proposer le beurre de tourage 82 %, en plaques de 2 kilos, qui convient bien pour vos chocolatines, à 9 euros
  20 le kilo. Il est disponible, ça vous va ? » → une seule question, argument d'usage, date donnée.
- Restes : « Je regarde. » seulement au tour 1 de S05 (5,8 à 8,3 s de silence ensuite) ; tour 2 en 3 phrases avec
  un début d'explication (« je ne peux pas vous promettre de livraison ce jour-là ») ; date formulée différemment
  entre S04 et S05 ; **brouillon orphelin toujours présent** (CMD-2026-007543).

Correction écrite ensuite (pas encore rejouée) : la date de retour est donnée telle qu'elle est écrite dans les
documents, sans la transformer ni en déduire une autre.
