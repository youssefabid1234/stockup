# Amine Khalil – 🧠 « La commande juste »  ·  mis à jour lun. 23/11 22h40

- Fait depuis la dernière sync :
  - **T0** baseline (ci-dessous).
  - **T2** `next_delivery_date` + `sacks_from_words` (déterministes, `agent/rules_order.py`) + outil
    **`check_delivery_date`** (`tools/delivery.py`, enregistré seulement si `TEAM_ORDER_RULES=1`).
    Tests : `tests/test_rules_order.py` (8 tests) + mes 2 tests de `test_team_todo.py` dé-skippés → verts.
  - **T1** `ORDER_RULES` v1 (9 règles courtes : pas de « pensée tout haut », unités, chocolatine, comme d'hab = panier
    habituel, dates via l'outil, brouillon puis **modifier** la ligne, relecture puis `confirm_order` direct au oui,
    compte bloqué = message + `log_client_event`, alertes dites seulement s'il y en a).
  - S02 reformulé : « pour la tradi mettez-en 12 sacs » (l'habitude de Sarrailh est ~21 sacs, pas 10).
- En cours : T3 (alertes ERP en détail), T4 (franco 150 €, quantité anormale), mes scénarios S30–S31.
- Bloqué / j'attends : rien.
- J'ai besoin de (qui, quoi) :
  - **Youssef** : `CallContext.delivery_days` = champ ERP tel quel (décision ci-dessous : l'ERP fait foi, pas la note
    « Fermé le mercredi »). Idéalement, ne pas mettre ces notes « Fermé le … » dans `render_for_prompt`.
  - **Youssef** : `run_scenarios.py` en mode /chat ne rejoue pas les ids des outils → l'agent recrée un brouillon à
    chaque tour (vu en S01/S02 : `create_draft_order` rappelé au tour 2/3). En `--voice` tout est juste (1 seule
    commande). À savoir pour lire les résultats /chat.
  - **Tout le monde** : une ligne ajoutée dans `tools/__init__.py` (partagé) pour enregistrer `delivery.py` derrière
    mon interrupteur.
- Interrupteur(s) : TEAM_ORDER_RULES = **on** sur ma branche · prêt à allumer sur main ? **oui** (4/4 scénarios verts)
- Mesure (scénarios, ms) : voir tableau « Avec TEAM_ORDER_RULES=1 ».
- Changement de contrat demandé (interfaces.md) : aucun (j'ajoute l'outil `check_delivery_date`, prévu par ma fiche).

## Avec TEAM_ORDER_RULES=1 (lun. 22h30, /chat sauf mention)

| Scénario | Avant | Après | Ce qui a changé |
|---|---|---|---|
| S01 | PASS · 11 078 / 9 394 ms | PASS · 7 291 / 5 915 ms | Plus de « jeudi est bien un jour de livraison » avant le bonjour ; dit « jeudi 26 novembre » via l'outil. |
| S02 | **FAIL** 2/3 | **PASS 3/3** · `--voice` : 8 927 / 7 306 / **3 527 ms** (fin de parole → 1er son) | Panier habituel (pas la dernière commande), 1 seul brouillon modifié à 12 tradi, `confirm_order` direct au « validez ». 1 seule commande dans l'ERP. Signale la rupture AOP sans substituer. |
| S03 | PASS · 4 907 ms | PASS · 6 324 ms | Plus de « vous êtes fermé mercredi », plus de règle comptable interne ; **message enregistré** (`log_client_event`) et Sandrine citée. |
| S07 | PASS · 6 470 ms | PASS · 7 071 ms | Plus de fuite « jeudi est un jour de livraison » ; « dix sacs de tradi et deux pains de levure ». |

Limites connues : la relecture d'un « comme d'hab » complet reste longue à l'oral (9 produits) ; les temps restent à
5–9 s par tour (chantiers latence de Mohamed Amine et Youssef).

## Baseline T0 (kit d'origine)

| Scénario | Résultat | Temps des tours (/chat, tour complet) | Ce qui ne va pas |
|---|---|---|---|
| S01 commande simple Sarrailh | PASS 2/2 | 11 078 ms · 9 394 ms | Dit tout haut sa vérification interne avant de saluer (« Jeudi est bien un jour de livraison (jeudi 26 novembre). Bonjour Nadine… »). Au « oui », rappelle 6 outils (search, get_client, get_price…) avant `confirm_order` : 9,4 s pour valider. Phrase « Je vérifie et je valide » parasite. |
| S02 comme d'hab + changement d'avis | **FAIL** 2/3 | 8 799 · 3 411 · 3 166 ms | « Comme d'hab » = recopie la **dernière** commande (21 tradi, 10 gruau…) au lieu du panier habituel, et la lit en entier (trop long à l'oral). Aucun brouillon créé. Au tour 3 (« validez ») redemande au lieu de conclure → pas de `confirm_order`. Cause partielle : le scénario dit « au lieu de 10 » alors que l'habitude est 21. |
| S03 client bloqué (Pétrin de Balma) | PASS 1/1 | 4 907 ms | Refuse bien. Mais : (1) dit « demain mercredi vous êtes fermé » alors que l'ERP le livre mer/sam (voir ci-dessous) ; (2) donne une règle interne (« après règlement d'au moins la moitié de l'échu ») ; (3) ne prend **pas** le message (aucun `log_client_event`). |
| S07 phrase hésitante | PASS 1/1 | 6 470 ms | Même fuite « Jeudi est un jour de livraison (26/11). » avant le bonjour. Sinon juste : 10 sacs + 2 levures, relecture, pas de confirmation. |

**Ce que j'en retiens pour T1–T3**
1. Interdire les phrases de vérification interne à voix haute (ce qui est dit avant / entre les outils est prononcé).
2. « Comme d'hab » = le **panier habituel** de la fiche (`usual`), résumé en 2-3 produits principaux + « comme d'habitude pour le reste ? », pas la dernière commande lue en entier.
3. Créer le brouillon dès que la commande est claire ; un changement d'avis **modifie** la ligne.
4. « Validez / c'est bon / oui » après une relecture = `confirm_order` directement, sans re-vérifier tout le catalogue.
5. Compte bloqué : refuser sans détail comptable interne + **enregistrer le message** (`log_client_event`).

## Données contradictoires : « Fermé le mercredi »

9 clients ont une note commerciale « Fermé le mercredi : jamais de livraison ce jour-là » alors que le mercredi est
dans leurs jours de livraison ERP (Pétrin de Muret, Pétrin de Balma, Pétrin de Colomiers, Au Fournil de Mélanie,
Au Fournil de Didier, Au Pain de Guilhem, Au Fournil de Philippe, La Mie d'Arnaud-Bernard, Au Fournil de Brigitte).
**L'historique tranche** : ces clients sont **effectivement livrés le mercredi** après la date de la note (ex. Pétrin
de Muret : 12 livraisons le mercredi depuis septembre ; Au Fournil de Philippe n'est livré **que** le mercredi).
L'agent d'origine croit la note et refuse à tort (vu en S03 et dans un test S1 du kit).
→ À décider : faire foi aux **jours de livraison de l'ERP** (confirmés par l'historique) et ignorer la note.
