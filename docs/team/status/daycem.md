# Daycem – « Le bon vendeur »  ·  mis à jour lun. 23/11, 21h40

- Fait depuis la dernière sync :
  - T0 : photo de départ de S04 et S05 (tous les `TEAM_*` éteints, ERP remis à zéro avant chaque scénario). Détail plus bas.
  - T1 : `SALES_RULES` v1 écrit dans `agent/rules_sales.py`. Les règles sont générales (aucun nom de client, de
    produit ou de personne) ; un test le vérifie (`test_sales_rules_stay_general`).
- En cours : T1, rejouer S04 et S05 avec `TEAM_SALES_RULES=1`.
- Bloqué / j'attends : rien.
- J'ai besoin de (qui, quoi) :
  - Youssef : `load_call_context` n'est appelé nulle part (ni `voice_session.py` ni `/chat`), donc la fiche n'est
    jamais préchargée. Aujourd'hui l'agent relit la fiche avec `search` + `get_client` + `get_context` à chaque tour.
  - Youssef (T3 / `product_insight`) : `GET /api/products/prd_0025/alternatives` classe par prix proche :
    demi-sel, beurre doux AOP, puis seulement le tourage 82 %. `rank_alternatives` devra classer par usage.
  - Mohamed Amine : 5,6 à 7,5 s de silence avant le premier mot au 1er tour (aucune phrase d'attente).
- Interrupteur(s) : TEAM_SALES_RULES = off pour la photo de départ · prêt à allumer sur main ? pas encore (rejeu à faire)
- Mesure (scénarios, ms) : voir le tableau ci-dessous.
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
