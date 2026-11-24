# Amine Khalil – 🧠 « La commande juste » + ⚡ voix et T3/T4 (repris de Mohamed Amine et Youssef)  ·  mar. 24/11 03h00

- Fait (03h00) – **prompt allégé** (`agent/context_digest.py`, `TEAM_SLIM_PROMPT=1` par défaut) : contexte −64 %, tokens
  relus par appel modèle 34 400 → 21 600 (−37 %), somme des 4 répliques 19,3 → 17,1 s, commande juste 3/3. S03 et S02 :
  attentes mises à jour (fiche préchargée ; « habituel »). S02 reste instable avec les deux prompts. Détail : DECISIONS.md
  (section Youssef, « T3 / T4 »).
- **Pour tous** : ajouter `TEAM_SLIM_PROMPT=1` dans votre `.env`.
- Fait (03h40) – **`place_order`** (T4) : jour + produits + unités + écriture + relecture en UN appel d'outil. Commande
  7,2 → 3,6 s, somme des 4 répliques 19,3 → 13,8 s (−29 %), tokens de la 1re réplique −68 %. En vocal : 3,7 s (au lieu
  de 6,1–6,3). 10 scénarios PASS (dont S05 4/4), une seule commande à chaque fois. 283 tests passent.
- T4 reste (facultatif) : démarrage anticipé sur la transcription partielle (à valider au micro) ; T6 / S08 réclamation.

- Fait (02h40) – **routage Haiku / Sonnet** (`agent/router.py`, `TEAM_ROUTER=1` par défaut) : « c'est bon, validez »,
  « oui », « merci » → Haiku (premier mot 0,5 s au lieu de 1,2-1,3 s) ; le reste → Sonnet. Plus de « Très bien, je
  vérifie » sur une simple confirmation (accusé seulement s'il y a quelque chose à chercher). Codes ERP jamais lus à voix
  haute. Mesuré : validation 2,2 s (2,6-3,3 s avant), « merci, au revoir » 0,7 s. 272 tests passent. S02 : attente
  `get_client` retirée (la fiche est préchargée).
- **Pour tous** : ajouter `TEAM_ROUTER=1` dans votre `.env`.

- Fait (02h10) – **mode 4 « zéro silence »** (`TEAM_FILLERS=4`, défaut dans `.env.example`), tâches voix reprises de
  Mohamed Amine : l'agent **ouvre l'appel** (« Bonjour Madame, que puis-je faire pour vous ? », 0,3 s après le
  formulaire), **accusé immédiat** à chaque demande (« D'accord, je regarde ça »…), **clavier continu** jusqu'au premier
  son de la réponse. Mesuré en configuration jury : 1er son 0,0 s, **0,0 s de silence entendu** (avant : 3,0 s médiane
  sans attente, blancs de 1,4–1,9 s en mode 3). Détail et tableau : DECISIONS.md §3 et « Vitesse et voix ».
- Corrigé : seuil Jev (« C'est bon, validez » après une question de prix : accord 0,95 / change 0,55 → n'était pas
  confirmé). Désormais accord ≥ 0,9 = oui.
- Tests : `conftest.py` rend la suite indépendante du `.env` de chacun ; 232 passent (modes 0, 1, 3, 4).
- **Pour tous** : mettre `TEAM_FILLERS=4` et `TEAM_PRODUCT_INSIGHT=1` dans votre `.env`, redémarrer l'IA, passer par
  « Qui appelle ? » : l'agent parle le premier.
- Reste côté voix : la réponse utile met 2,8–6,3 s (comblée, mais longue) → orchestrateur de Youssef (T4) ou modèle
  plus rapide ; essai au micro réel (transcription + son dans le navigateur).

- Fait (01h00) – **Jev branché** (recommandation du CTO), `tools/order_jev.py`, derrière `TEAM_ORDER_RULES` :
  - `confirm_order` **remplacé** par une version gardée par Jev (même nom → les scénarios de tous marchent tels quels ;
    interrupteur éteint = l'outil du kit). L'agent passe la réponse exacte du client ; Jev dit « vrai oui » ou non.
    Calibrage sur 12 réponses : vrais oui 0,89–0,96 ; « oui mais… », « attendez », questions ≤ 0,14. Bloque aussi sur
    alerte ERP bloquante. Sans clé Jev → comportement du kit. Journal `[jev] …` dans les logs du service IA (pour la démo).
  - `resolve_product` : nom exact du catalogue d'abord (« pains de levure », « la tradi », « du demi-sel » : sans
    modèle), sinon Jev avec les habitudes du client (« tourage » → AOP chez Sarrailh, question chez Pétrin de Colomiers) ;
    sous 0,6 l'agent demande ; mots ambigus du glossaire jamais réglés par un alias seul.
  - Mesures (`--voice`, reset avant chaque) : S02 S30 S31 S32 S33 PASS, S05 3/4 (voir Daycem) ; 8/8 confirmations
    validées par Jev en 159–196 ms ; 1 seule commande juste à chaque fois. Tests : 151 passent (ON et OFF).
  - Nouveau scénario **S33** (« oui mais mettez-en douze »). DECISIONS.md : D8 + mesures.
- Pour **Daycem** : S05 tour 2, ajouter `quote_line` à `tools_any` (l'agent donne le prix avec, c'est juste).

- Fait (00h05) – **prix dits à l'oral calculés par le code** (outil `quote_line`) :
  - Constat à l'écoute d'un enregistrement de S05 : l'agent calculait de tête et se trompait en direct (« 92 euros la
    plaque de 2 kilos… pardon, 18 euros 40 la plaque »).
  - `rules_order.py` : `packaging` (carton 5 plaques de 2 kg → carton = 10 kg, plaque = 2 kg ; carton 6 × 1 L…),
    `to_selling_qty` (« 3 cartons » de tourage → 30 kg), `quote` / `fr_money` (« 9 euros 20 le kilo, soit 92 euros le
    carton de 10 kilos » ; « 276 euros hors taxes pour 30 kilos, soit 3 cartons »). Prix client résolu par l'ERP
    (`/api/prices/resolve`, prix négocié / règles de groupe) : rien n'est recodé.
  - Outil **`quote_line`** (`tools/order_review.py`) + règle « pour un prix, appelle quote_line, ne calcule jamais ».
  - Tests : +5 → 117 passent. S05 réenregistré : prix juste du premier coup, appel de 68 s → 56 s, 1 commande
    confirmée mercredi 25/11.
  - Pour **Daycem** : S05 tour 2 attend `get_price` ou `product_insight` ; ajouter `quote_line` à `tools_any`.
- Pour **tous** : mettre `TEAM_ORDER_RULES=1` dans son `.env` après la fusion (`.env.example` est passé à 1).
- Outil d'enregistrement : un appel complet en MP3 (client = 2e voix ElevenLabs, agent = vraie réponse via WS /voice)
  dans `scenarios/results/audio/` (ignoré par git). Je peux le partager si l'équipe le veut pour la vidéo.

- Fait (23h30) – **garde-fous doublons + note « Fermé le mercredi »**, suite à l'audit de S05 (Daycem) :
  - **S05 audité** (rupture AOP → 82 %, Pétrin de Colomiers) : aucun doublon. Mais **sans** `TEAM_ORDER_RULES` il
    **échoue** (2/4) : l'agent croit la note « fermé le mercredi », déplace la livraison au lundi 30/11 et laisse un
    brouillon jamais confirmé. **Avec** mes règles : 4/4, 1 commande confirmée mercredi 25/11.
  - Règle : les notes « Fermé le … » sont ignorées (l'ERP fait foi), l'agent ne pose plus la question.
  - `review_order` renvoie aussi **`duplicateDrafts`** (autres brouillons créés par l'agent pour ce client, avec leur
    contenu relu et `sameAsThis`) et **`sameDayOrders`** (autres commandes du même jour, ex. un brouillon WhatsApp).
    Règle : doublon identique → abandonné sans en parler ; brouillon différent → relu au client qui choisit annuler ou
    fusionner ; jamais deux commandes ouvertes par l'agent. Les brouillons WhatsApp / e-mail ne sont **jamais** annulés.
  - Test « brouillon oublié » (200 tradi + 3 seigle créé à la main, puis Nadine commande 10 tradi) : avant ce correctif
    l'agent proposait « garder les deux séparées » et le brouillon restait (risque : l'ADV le confirme → double
    livraison) ; maintenant il le relit, insiste, et l'**annule** à la demande → 1 commande confirmée, l'autre annulée.
  - Tests : 112 passent. Rejoué en vocal : S05 4/4, S30 3/3, S31 3/3, S32 3/3 (1 commande juste à chaque fois).
- Pour **Daycem** : S05 passe avec `TEAM_ORDER_RULES=1` ; sans, il échoue sur la fausse fermeture du mercredi.
- Proposition à la sync : **allumer `TEAM_ORDER_RULES=1` par défaut sur main** (`.env.example`).

- Fait (T3 / T4, 22h50) :
  - Outil **`review_order`** (`tools/order_review.py`, logique déterministe `rules_order.review`) : à appeler après
    chaque création / modification de commande. Renvoie la phrase de relecture prête à dire, les **alertes ERP traduites**
    pour le client (bloqué, plafond, pas de tournée, rupture / « il n'en reste que… » ; les alertes internes
    `price_below_cost` / `expiring_soon` ne sont jamais dites, aucun chiffre comptable), la remarque **franco 150 € HT**
    (12 € sinon, avec ce qui manque), les **quantités inhabituelles** (≥ 5× l'habitude) à faire confirmer, et `canConfirm`.
  - Outils de **modification** (`tools/order_edit.py`) : `update_order_line`, `remove_order_line`,
    `change_delivery_date`, `cancel_draft_order` (brouillon seulement). Le kit ne savait qu'**ajouter** des lignes :
    au « finalement vingt » (S31 v1) l'agent créait une 2e commande et laissait le brouillon à 200 sacs dans l'ERP.
  - Règle « ne pense pas tout haut » durcie (une fuite vue en S31 v1 : « Quantité inhabituelle probablement ; je crée… »).
  - Mes scénarios **S30** (franco), **S31** (200 sacs au lieu de 20), **S32** (modifier + retirer une ligne après le brouillon).
  - Tests : +5 (review, alertes, franco, quantité anormale) → 108 passent, interrupteur allumé ou éteint.
  - Tout est derrière `TEAM_ORDER_RULES` (les 6 outils ne sont enregistrés que s'il est allumé).

| Scénario (`--voice`, fin de parole → 1er son) | Résultat | Tours (ms) | Dans l'ERP |
|---|---|---|---|
| S30 franco | PASS 3/3 | 9 257 · 5 002 · 3 720 | 1 commande confirmée, 153,90 € HT ; « 12 euros de frais… il manque 147 euros », puis « vous passez le franco » |
| S31 quantité anormale | PASS 3/3 | 5 162 · 2 984 · 1 879 | « Vous dites bien deux cents ? D'habitude c'est une vingtaine » → 1 commande à 20 sacs, aucun brouillon orphelin |
| S32 changement d'avis | PASS 3/3 | 7 816 · 6 484 · 3 234 | `update_order_line` + `remove_order_line` → 1 commande, 15 tradi, plus de seigle |
| S02 | PASS 3/3 | 8 609 · 7 955 · 3 368 | 1 commande confirmée |
| S03 (/chat) | PASS 1/1 | 5 426 | message enregistré, rien promis |

- Fait (T0–T2, 22h40) :
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
