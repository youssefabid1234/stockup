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

- Deux annonces très courtes sont préparées à l'ouverture avec la voix configurée. De courtes rafales de trois frappes sont générées en mémoire et espacées pendant les recherches longues. Une seule relance orale reprend la quantité et le produit entendus si la demande est claire, ou dit « Un instant, je vérifie ». Les sons suivants sont annulés quand la réponse est prête ou si le client interrompt l'agent. Les sons partagent le segment interruptible de la réponse. Le premier son et le premier octet de synthèse de la réponse utile sont chronométrés séparément.
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

**Identification avant l'appel (« Qui appelle ? », mar. 24/11 0h20).** Vraie vie : le numéro WhatsApp / téléphone
s'affiche, le standard connaît le client avant de décrocher. Démo : sur la page Voix, un formulaire obligatoire (client
choisi dans la liste de l'ERP, recherche par nom / ville / téléphone, contact au téléphone ; ou « Nouveau client ») puis
« Démarrer l'appel » : la fiche est chargée (≈ 0,5 s) **avant** le premier mot et donnée à l'agent dès la 1re réplique.
Nouveau client (provisoire) : l'agent prend la demande sans rien confirmer, l'équipe valide le compte.

Mesure via /chat, `--reset`, `TEAM_ORDER_RULES=1`, client du scénario annoncé avant l'appel :

| 1re réplique | Sans (TEAM_PRELOAD=0) | Avec l'appelant annoncé |
|---|---|---|
| S01 « 10 sacs de tradi pour jeudi » | 6 outils, **7,7 s** | 3 outils (date, brouillon, relecture), **3,5 s** |
| S01 en **voix** (fin de parole → 1er son) | **6,9 s** (T0) | **3,9 s** (LLM 3,75 + TTS 0,16) |
| S02 « comme d'hab pour jeudi » | 4 outils, 5,6 s | 1 outil, **3,9 s** |
| S05 « 3 cartons de tourage AOP » | 4 outils, 5,4 s | 2 outils, 4,7 s |
| S05 réplique 3 (note « Fermé le mercredi ») | demande « mercredi vous convient ? » | ne parle plus du mercredi (note filtrée) |

Lecture : la 1re réplique perd 2 à 4 s et 2 à 3 allers-retours (plus de recherche du client ni de sa fiche) ; la voix
passe de 6,9 à 3,9 s. Les répliques suivantes ne changent pas (bruit ±1-2 s). `TEAM_PRELOAD` passe à 1 dans
`.env.example`.

**Outil de rejeu corrigé** : en /chat il renvoie maintenant l'historique complet (outils appelés + résultats) comme la
page Voix ; avant, l'agent oubliait son brouillon et recommençait (S01·2 : 6 outils, 9,4 s → 1 outil, 2,4 s).
### Commande juste (Amine Khalil)

**Mission** : ce qui finit dans l'ERP est exactement ce que le client voulait (bon produit, bonne quantité, bon jour,
rien de validé sans son accord). Interrupteur `TEAM_ORDER_RULES` (allumé par défaut dans `.env.example`). Code :
`agent/rules_order.py` (règles + fonctions déterministes), `tools/delivery.py`, `tools/order_review.py`,
`tools/order_edit.py`. Principe directeur : **le modèle parle, le code calcule** (dates, unités, prix, alertes).

**Point de départ (T0, kit seul, lun. 23/11 22h20, /chat)** : S01 PASS mais l'agent « pense tout haut » avant de
saluer (« Jeudi est bien un jour de livraison… ») et revérifie 6 outils avant de confirmer (9,4 s) ; **S02 FAIL**
(« comme d'hab » = la dernière commande lue en entière, aucun brouillon, ne confirme jamais) ; S03 PASS mais affirme
« vous êtes fermé mercredi » (faux), cite une règle comptable interne et ne prend pas le message.

**Décisions**

| # | Décision | Pourquoi |
|---|---|---|
| D1 | **Les jours de livraison de l'ERP font foi** ; les notes « Fermé le mercredi » sont ignorées, seul le client peut annoncer une fermeture | 9 clients ont cette note alors que l'ERP les livre le mercredi, et l'historique le confirme (ex. Pétrin de Muret : 10 livraisons le mercredi après la note ; Au Fournil de Philippe n'est livré que le mercredi). L'agent d'origine refusait ou déplaçait à tort (S05 livré lundi 30/11). Youssef retire aussi ces notes de la fiche préchargée. |
| D2 | **Dates calculées par le code** (`next_delivery_date`, outil `check_delivery_date`) | Jours du client, heure limite 17h, Lauragais-Tarn la veille avant 12h, tournée partie à 6h30 : un calendrier, pas une intuition. « mercredi » pour Sarrailh → « pas livré le mercredi, prochain jour : jeudi 26 novembre ». |
| D3 | **Une seule commande par appel** : outils `update_order_line`, `remove_order_line`, `change_delivery_date`, `cancel_draft_order` | Le kit ne savait qu'ajouter des lignes : au « finalement vingt », l'agent créait une 2e commande et laissait le brouillon à 200 sacs dans l'ERP (vu sur S31). |
| D4 | **Relecture calculée avant confirmation** (`review_order`) | Phrase de relecture prête à dire, alertes ERP traduites pour le client (bloqué, plafond, pas de tournée, « il n'en reste que… » ; jamais de chiffre comptable ni de marge), franco 150 € HT (12 € sinon), quantité ≥ 5× l'habitude à faire confirmer, `canConfirm`. L'ERP renvoie des alertes mais ne bloque rien. |
| D5 | **Garde-fou doublons** dans `review_order` (`duplicateDrafts`, `sameDayOrders`) | Un brouillon oublié par l'agent à côté de la bonne commande peut être confirmé par l'ADV → double livraison. Doublon identique → abandonné ; brouillon différent → relu au client qui choisit ; brouillons WhatsApp / e-mail jamais annulés. |
| D6 | **Prix calculés par le code** (outil `quote_line`) | À l'écoute d'un enregistrement de S05, l'agent calculait de tête et se corrigeait en direct (« 92 euros la plaque… pardon, 18 euros 40 »). Le prix client vient de l'ERP (`/api/prices/resolve`) ; le code fait conditionnements et multiplications (« 9 euros 20 le kilo, soit 92 euros le carton de 10 kilos ; 276 euros hors taxes pour 30 kilos »). |
| D7 | **Règles courtes et impératives** (`ORDER_RULES`, ~12 lignes) plutôt qu'un long texte | Le prompt est relu à chaque étape : chaque règle répond à un défaut observé (ne pas penser tout haut, unités, « chocolatine », « comme d'hab » = panier habituel résumé, confirmer directement au « oui », compte bloqué = message enregistré avec `log_client_event`). |

**Mesures** (scénarios rejoués avec les vraies clés ; `--voice` = vrai chemin vocal, temps = fin de la phrase → 1er octet audio)

| Scénario | Kit seul | Avec `TEAM_ORDER_RULES=1` | Dans l'ERP après l'appel |
|---|---|---|---|
| S01 commande simple | PASS · 11,1 s / 9,4 s | PASS · 7,4 s / 2,6 s (`--voice`) | 1 commande confirmée |
| S02 comme d'hab + « mettez-en 12 » | **FAIL** 2/3 | PASS 3/3 · confirmation 3,4 s | 1 commande, 12 tradi |
| S03 client bloqué | PASS (affirmations fausses) | PASS · message enregistré, rien promis | aucune commande |
| S05 rupture AOP → 82 % | **FAIL** 2/4 (livré lundi, brouillon non confirmé) | PASS 4/4 | 1 commande, mercredi 25/11 |
| S30 sous le franco | – | PASS 3/3 (« 12 euros de livraison… il manque 147 euros ») | 1 commande, 153,90 € |
| S31 « 200 sacs » au lieu de 20 | – | PASS 3/3 (« vous dites bien deux cents ? ») | 1 commande, 20 sacs |
| S32 modifier + retirer une ligne | – | PASS 3/3 | 1 commande, 15 tradi, sans seigle |
| Brouillon oublié simulé (200 tradi) | – | relu au client puis annulé à sa demande | 1 confirmée + 1 annulée |

S05 enregistré en audio (client = 2e voix ElevenLabs, agent = vraie réponse) : 68 s → 56 s d'appel après D6, prix
juste du premier coup. Tests : 24 tests sur la commande juste (`test_rules_order.py` + `test_team_todo.py`) ; la
suite complète de l'équipe passe (147 tests au mar. 24/11 00h30), interrupteur allumé ou éteint.

**Ce qui n'a pas marché / limites**
- Le script de rejeu en mode `/chat` ne rejouait que le texte : l'agent perdait l'id du brouillon et en recréait un
  (faux doublons sur S05 chez Daycem). Corrigé par Youssef (historique complet) ; nos garde-fous couvrent aussi ce cas.
- La relecture d'un « comme d'hab » complet (9 produits) reste longue à l'oral.
- Les temps restent de 2 à 9 s par réplique selon le nombre d'outils : le gros du gain vient des chantiers de
  Mohamed Amine et Youssef (phrases d'attente, fiche préchargée, agent rapide).
- Mes tests ne couvrent ni la transcription (texte envoyé directement) ni l'écoute de la voix : à valider au micro.
### Bon vendeur (Daycem)

## 5. Données modifiées pour la démo

(À remplir : ex. promo tourage 82 % créée par `scripts/setup_demo_data.py`.)

## 6. Ce qui n'a pas marché / abandonné
