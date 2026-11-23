# Daycem – « Le bon vendeur »  ·  mis à jour mar. 24/11, 0h30

- Fait depuis la dernière sync :
  - T1 : `SALES_RULES` complet (rupture, un seul remplaçant argumenté avec accord, date de retour telle qu'écrite,
    pas de remise, pas de raisonnement à voix haute, 1-2 phrases, une seule question, notes internes privées ;
    client qui refuse : solution sans autre produit + demande notée avec `log_client_event`). Règles générales,
    vérifiées par `test_sales_rules_stay_general`. Les deux dernières règles ne sont pas encore rejouées.
  - T3 (début) : `substitution_policy` (mots-clés : refuse / accepte / demander / inconnu) et `decide_substitution`
    (Jev seulement si « inconnu », toute erreur → demander). 13 tests sur de vraies fiches ; les 104 fiches vérifiées
    sans anomalie. `refuses_substitution` garde le contrat d'interfaces.md §5.
  - Test Jev seul sur 10 fiches : 6/10 puis 5/10, ~150-170 ms → `docs/team/jev-substitution-test.md` (pour DECISIONS.md).
- En cours : T3 `rank_alternatives` (substituts listés dans les documents d'abord), plan à valider.
- Bloqué / j'attends : rien.
- J'ai besoin de (qui, quoi) :
  - **Youssef** : brancher `decide_substitution` / `rank_alternatives` dans `product_insight` (encore `NotImplementedError`).
  - **Amine K. / Youssef** : brouillon orphelin vu 2 fois sur S05 (CMD-2026-007543 en brouillon à côté de la
    commande confirmée). Le runner rejoue maintenant tout l'historique (PR #4) et `order_edit` existe (PR #3) :
    **à revérifier** au prochain rejeu.
  - **Mohamed Amine** : sa proposition « donne directement le résultat, le lecteur vocal fait patienter » (quand
    `TEAM_FILLERS=1`) contredit ma règle « Je regarde. est autorisé » : à trancher ensemble avant d'allumer les deux.
- Interrupteur(s) : TEAM_SALES_RULES = on sur ma branche · prêt à allumer sur main ? oui (S04 et S05 passent)
- Mesure (scénarios, ms) : voir les tableaux ci-dessous (T0 → T1c : S04 premier mot 7,5 s → 0,7 s).
- Changement de contrat demandé (interfaces.md) : aucun ; ajout de `substitution_policy` et `decide_substitution`.

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
