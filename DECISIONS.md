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

**Silence entendu par l'appelant** (mar. 24/11 02h00, Maison Sarrailh, 4 répliques : commande, « oui mais mettez-en
douze », prix, « c'est bon, validez » ; vraies clés, WS `/voice` en texte (ajouter ~0,3-0,5 s de transcription au
micro) ; le flux MP3 reçu est rejoué comme le navigateur, durées lues dans les en-têtes MP3 et vérifiées avec ffprobe) :

| Réglage | L'agent ouvre l'appel | 1er son après la phrase (médiane / pire) | Réponse utile prête | Silence entendu avant la fin de la réponse |
|---|---|---|---|---|
| `TEAM_FILLERS=0` (kit) | non | 3,0 s / 5,0 s | 2,2–4,8 s | tout ce temps (2,3–5,0 s) |
| `TEAM_FILLERS=3` | non (« Bonjour » joué après la 1re phrase) | 0,0 s / 0,8 s | 2,1–4,3 s | jusqu'à 1,4–1,9 s d'un bloc |
| **`TEAM_FILLERS=4` (défaut)** · configuration du jury | **oui, 0,3 s** après le formulaire | **0,0 s / 0,0 s** | 2,8–6,3 s | **0,0 s** |
| **+ `TEAM_ROUTER=1` (défaut)** · accusé ciblé + Haiku pour les répliques simples | oui, 0,4 s | 0,0 s / 0,4 s | « c'est bon, validez » **2,2 s** (2,6–3,3 s sur Sonnet) ; « merci, au revoir » **0,7 s** | **0,0 s** |

**Routage du modèle** (`agent/router.py`, `TEAM_ROUTER`) : une réplique faite uniquement de confirmation ou de politesse
(« c'est bon, validez », « oui », « parfait », « merci, au revoir ») part sur le modèle rapide (Haiku, `TEAM_FAST_MODEL`),
tout le reste (produit, quantité, prix, changement d'avis, réclamation) sur Sonnet. Mesuré avec nos réglages : premier mot
0,45–0,57 s (Haiku) contre 1,19–1,33 s (Sonnet). La confirmation reste vérifiée par Jev (accord 0,94 en 190 ms sur
Haiku). Ces répliques ne déclenchent plus « Très bien, je vérifie » (inutile et lent) : l'accusé n'est dit que si l'agent
doit chercher quelque chose. Les codes ERP (« CMD-2026-007543 », `prd_…`) sont retirés du texte prononcé, quel que soit le
modèle (Haiku en avait lu un). Rejeu `--voice` : S01, S30, S31, S32, S33 PASS ; S02 PASS 2 fois sur 3 (la 3e, le modèle
rapide demande la quantité de gruau restée floue au tour 1 au lieu de confirmer : il n'invente pas).

Premier relevé (23/11, via /chat, sans audio) : S03 (client bloqué) PASS, 6 099 ms, premier mot à 4 092 ms ; défaut
noté : l'agent prononce son raisonnement (« Le compte est bloqué ; je ne prends pas de commande… »).

## 4. Choix par chantier

### Vitesse et voix (Mohamed Amine)

- Deux annonces très courtes sont préparées à l'ouverture avec la voix configurée. De courtes rafales de trois frappes sont générées en mémoire et espacées pendant les recherches longues. Une seule relance orale reprend la quantité et le produit entendus si la demande est claire, ou dit « Un instant, je vérifie ». Les sons suivants sont annulés quand la réponse est prête ou si le client interrompt l'agent. Les sons partagent le segment interruptible de la réponse. Le premier son et le premier octet de synthèse de la réponse utile sont chronométrés séparément.
- Si la transcription ne suffit pas à détecter une demande de recherche, le premier appel ERP confirmé peut déclencher l'annonce. La voix garde le jargon de base si l'ERP est indisponible. Les tests d'intégration couvrent aussi l'arrêt de l'audio après une erreur et les annonces répétées.
- L'orchestrateur actuel délègue à l'agent ERP. Les annonces restent actives selon `TEAM_FILLERS` et la réponse finale annule l'attente. Le mode 3 ajoute le clavier pendant la préparation de la reprise rapide. Le ton et la consigne contre les doublons sont proposés à Daycem dans le [suivi](docs/team/status/mohamed-amine.md).
- Rejeu local via WebSocket, données de démonstration et trois fournisseurs simulés, avec et sans `TEAM_FILLERS` : **3 répliques sur 10** passent dans les deux configurations. S06 et les deux répliques de S10 passent. S01 et S05 échouent sur leurs attentes métier. Sur S11, le modèle simulé lance une recherche sur « merci ». Un test d'intégration vérifie que même dans ce cas la voix ne joue ni annonce ni clavier. Les mesures de référence au micro, le délai perçu et le premier tour ElevenLabs restent à relever sur le pack du Fournil.
- T7 facultatif est reporté. Espace fournit un point de départ reproductible pour mesurer le délai et interrompre l'agent pendant la démo.
- **Mode 4 « zéro silence » (repris par Amine Khalil, mar. 24/11 02h00), défaut de l'équipe.** Mesure de départ : en mode 3
  l'agent ne parlait pas en premier et laissait des blancs de 1,4 à 1,9 s (le clavier attendait 1,4 s puis revenait
  toutes les 2,2 s). Ce qui change : (1) **l'agent ouvre l'appel** dès le formulaire « Qui appelle ? » (« Bonjour
  Madame, que puis-je faire pour vous ? », synthétisé pendant le chargement de la fiche, joué dès qu'il est prêt :
  0,2–0,3 s), et sa première réponse ne redit pas « Bonjour » ; (2) **accusé immédiat** à chaque demande (« D'accord,
  je regarde ça », « Ok, je vois ça », « Très bien, je vérifie », préparés à l'ouverture) — rien sur « oui » / « merci » ;
  (3) **clavier continu** : clips de 0,45 s (6 rythmes différents) envoyés juste avant que l'audio déjà envoyé ne
  s'épuise (le navigateur joue un seul flux et ne cale jamais), arrêtés au premier octet audio de la réponse (pas à son
  texte : le temps de synthèse est couvert aussi) ; au plus 0,6 s de clavier encore en file à ce moment. Résultat :
  0,0 s de silence entendu sur les 4 répliques (tableau §3). Les modes 1-3 sont inchangés.
- Tests : `tests/test_no_silence.py` (8 tests) ; `tests/conftest.py` remet `TEAM_FILLERS` à zéro pour chaque test (la
  suite donnait des résultats différents selon le `.env` de chacun) : 232 tests passent avec `TEAM_FILLERS` 0, 1, 3 et 4.

### Plusieurs agents, fiche préchargée, super-outil (Youssef)

**T3 / T4 · Prompt allégé (`TEAM_SLIM_PROMPT=1`, défaut ; repris par Amine Khalil, mar. 24/11 03h00).** Chaque appel au
modèle relisait ≈ 34 400 tokens (le cache Anthropic marche : presque tout est « cache lu »). Décomposition : contexte
entreprise 55 % (les 6 `data/context/*.md`, surtout les tableaux du catalogue), schémas des 25 outils ≈ 24 %, règles et
fiche client le reste. Le catalogue (alias, prix, DLC) est déjà donné à la demande par les outils (`search`,
`resolve_product`, `product_insight`, `quote_line`) et la fiche client couvre statut, habitudes et encours.
`agent/context_digest.py` garde, extraites des mêmes fichiers à chaque tour : règles de la maison, situation du jour,
équipe, heures limites, facturation, alias ambigus, substitutions habituelles, saisonnalité, prise de commande, clients
bloqués, réclamations, prix / règles de prix / crédit, tournées. Contexte 39 016 → 13 996 caractères (−64 %).

| Mesure (`/chat`, Sarrailh, 4 répliques, 3 appels, médianes) | Prompt complet | Allégé |
|---|---|---|
| Tokens relus par appel modèle | ≈ 34 400 | **≈ 21 600 (−37 %)** |
| Commande · « mettez-en douze » · prix · « validez » | 7,2 · 4,6 · 3,5 · 4,0 s | **6,4 · 4,1 · 3,1 · 3,5 s** |
| Somme des 4 répliques | 19,3 s | **17,1 s (−11 %)** |
| Commande juste dans l'ERP | 3/3 | 3/3 |

Le gain de temps est modeste parce que le cache rend la relecture rapide : le temps vient surtout des tokens écrits
(200 à 430 par réplique : appels d'outils + phrase) et du nombre d'allers-retours. Le gain de **coût** est net (−37 % de
tokens lus). Scénarios (`/chat`) : S01, S05 (3/4, attente `get_price`), S30, S31, S32, S33 PASS ; S03 PASS après mise à
jour de l'attente (la fiche préchargée rend `search` inutile) ; S02 instable **avec les deux prompts** (1 réussite
complète sur 3 dans les deux cas : « comme d'hab » + rupture AOP) — avec le prompt allégé l'agent ouvre 2 fois sur 3 par
la rupture plutôt que par le panier habituel. Règle ajoutée : nommer le produit comme le client (« tradi »), jamais le nom
catalogue (sans le glossaire, l'agent disait « farine T cinquante-cinq tradition française »).

**T4 · Un seul aller-retour pour une commande (`place_order`, mar. 24/11 03h40).** Le temps ne venait plus de la relecture
du prompt (cache) mais du nombre d'allers-retours modèle ↔ outils : « dix sacs de tradi pour jeudi » coûtait 3 à 4 appels
au modèle (jour + produit, puis brouillon, puis relecture, puis la phrase). `tools/order_place.py` fait cette chaîne
déterministe dans le code : jour (`delivery_answer`), produits (alias du catalogue, sinon Jev avec les habitudes du
client), unités (« 3 cartons » de tourage → 30 kg ; 1,6 sac → on demande, jamais d'arrondi), écriture (nouveau
brouillon, ou commande en cours modifiée : quantité, ligne à 0 retirée, autre jour), relecture (`review`). Rien n'est
écrit si le jour est impossible, le produit ambigu ou le compte bloqué : « next » dit quoi demander.

| Mesure (`/chat`, Sarrailh, 3 appels, médianes) | Prompt complet | Prompt allégé | **+ `place_order`** |
|---|---|---|---|
| Commande · « mettez-en douze » · prix · « validez » | 7,2 · 4,6 · 3,5 · 4,0 s | 6,4 · 4,1 · 3,1 · 3,5 s | **3,6 · 3,4 · 3,2 · 3,6 s** |
| Somme des 4 répliques | 19,3 s | 17,1 s | **13,8 s (−29 %)** |
| Tokens lus pour la commande (1re réplique) | 137 416 | 86 488 | **43 934 (−68 %)** |
| Commande juste dans l'ERP | 3/3 | 3/3 | 3/3 |

En vocal (configuration du jury, mode 4, routage) : réponse à la commande prête en 3,7 s (6,1–6,3 s avant), validation
2,0 s, au revoir 0,6 s, 0,0 s de silence. Scénarios (`/chat`, `--reset`) : S01 S02 S03 S04 S05 S30 S31 S32 S33 S40 tous
PASS, une seule commande ouverte à chaque fois (S05 4/4 pour la première fois). Les attentes des scénarios acceptent
maintenant `place_order` là où elles demandaient `create_draft_order` / `update_order_line` / `review_order`, et
`quote_line` là où elles demandaient `get_price` ; S05/S40 acceptent « quatre-vingt-deux ».

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

**T1 · Super-outil produit (`TEAM_PRODUCT_INSIGHT`, mar. 24/11 1h30).** Vraie vie : un coup d'œil à l'écran de Lucie
suffit. `product_insight(client, produit, quantité)` lit en parallèle le produit (stock, arrivages), le prix de CE
client, les remplaçants de l'ERP, la fiche et les règles de prix ; si le produit manque, il calcule le prix client de
chaque remplaçant (en parallèle), dit si le client accepte un remplacement (`substitution_policy` de Daycem) et classe
les remplaçants (`rank_alternatives` de Daycem : le substitut des documents d'abord). **Promo** = le prix appliqué vient
d'une règle **datée** (validTo) et est sous le prix catalogue : jamais inventée (une remise de groupe permanente n'est
pas une promo). Client qui refuse : aucun remplaçant renvoyé.

Mesure via /chat, ERP remis à zéro puis promo de démo recréée (`setup_demo_data.py`), `TEAM_ORDER_RULES`,
`TEAM_PRELOAD`, `TEAM_SALES_RULES` = 1, 1re réplique, 2 essais (3 pour S04 après correction) :

| 1re réplique | Éteint | Allumé |
|---|---|---|
| S04 Sarrailh, AOP en rupture, refuse les remplacements | 2 outils · 3,8 / 4,3 s | 2 outils · 3,6 / 3,5 / 3,5 s, 3/3 PASS |
| S05 Pétrin de Colomiers, AOP en rupture | 5 puis 3 outils · 6,6 / 5,8 s | 2 outils (product_insight, date) · 2,8 / 4,9 s |
| S40 scène de démo (promo) | 3 outils · 4,2 / 4,3 s | 2 outils · 3,9 / 2,9 s |
| S40 en **voix** (totalMs) | – | 4,6 s |

Lecture : 1 à 3 allers-retours de moins ; médiane S05 6,2 → 3,9 s, S40 4,3 → 3,4 s, S04 4,1 → 3,5 s. Avec l'outil,
l'agent cite la promo exacte (8,46 €/kg, −8 % jusqu'au 30/11) dans les 4 premières répliques S05/S40. Deux pièges
corrigés pendant la mesure : les notes CRM de l'ERP sont des objets (l'outil plantait, l'agent repassait par les
anciens outils), et sans consigne l'agent enregistrait la demande « premier arrivage » de Sarrailh sans son accord
(+2 s) : l'outil rappelle maintenant de **proposer** d'abord. Les échecs restants des scénarios ne viennent pas de
l'outil (S05·2 attend get_price alors que quote_line d'Amine K. répond ; S05·1 a dit « quatre-vingt-deux » en
lettres ; S40·4 redemande « commande séparée ou ajout ? »). `TEAM_PRODUCT_INSIGHT` passe à 1 dans `.env.example`.
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
| D8 | **Jev décide les deux petites décisions risquées** (`tools/order_jev.py`) : « est-ce un vrai oui ? » avant `confirm_order` (qui garde son nom : les scénarios de l'équipe marchent tels quels) et « quel produit ? » pour un mot ambigu (`resolve_product`) | Recommandé par le CTO. Calibré sur 12 vraies réponses : « oui c'est bon », « bon d'accord » → accord 0,89–0,96 ; « oui mais mettez-en quatre », « et rajoutez du seigle », « attendez », « c'est combien ? » → accord ≤ 0,14. Seuils : ≥ 0,8 confirme, ≤ 0,3 ne confirme pas, entre les deux → redemander. 159–196 ms par décision en appel réel. Produits : nom exact du catalogue d'abord (sans modèle), sinon Jev avec les habitudes du client (« tourage » → AOP chez Sarrailh 0,82 ; demande AOP / 82 % / margarine au Pétrin de Colomiers 0,28) ; sous 0,6 l'agent demande. Sans clé Jev : comportement du kit. |
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
| S33 « oui mais mettez-en douze » (avec Jev) | – | PASS 3/3 · ligne modifiée, confirmation validée par Jev (accord 0,95) | 1 commande, 12 tradi |

Avec Jev (mar. 24/11, 00h50, `--voice`, remise à zéro avant chaque scénario) : S02, S30, S31, S32, S33 PASS ; S05 3/4
(tour 2 : l'agent donne le prix avec `quote_line`, le scénario attend `get_price`) ; 8 confirmations sur 8 validées par
Jev en 159–196 ms ; une seule commande juste dans l'ERP à chaque appel.

S05 enregistré en audio (client = 2e voix ElevenLabs, agent = vraie réponse) : 68 s → 56 s d'appel après D6, prix
juste du premier coup. Tests : 28 tests sur la commande juste (`test_rules_order.py` + `test_team_todo.py`) ; la
suite complète de l'équipe passe (151 tests au mar. 24/11 01h00), interrupteur allumé ou éteint.

**Ce qui n'a pas marché / limites**
- Le script de rejeu en mode `/chat` ne rejouait que le texte : l'agent perdait l'id du brouillon et en recréait un
  (faux doublons sur S05 chez Daycem). Corrigé par Youssef (historique complet) ; nos garde-fous couvrent aussi ce cas.
- La relecture d'un « comme d'hab » complet (9 produits) reste longue à l'oral.
- Les temps restent de 2 à 9 s par réplique selon le nombre d'outils : le gros du gain vient des chantiers de
  Mohamed Amine et Youssef (phrases d'attente, fiche préchargée, agent rapide).
- Mes tests ne couvrent ni la transcription (texte envoyé directement) ni l'écoute de la voix : à valider au micro.
### Bon vendeur (Daycem)

## 5. Données modifiées pour la démo

**Promo de démo sur le tourage 82 % (Daycem, T4), assumée et fictive.** Créée par l'API de l'ERP avec
`scripts/setup_demo_data.py`, parce que `data/seed/` n'est pas dans git :

- règle de prix `Promo tourage 82 % : −8 % jusqu'au 30/11` : groupe « Boulangeries » × Beurre de tourage 82 %
  (`prd_0026`), −8 % sur le prix catalogue, du jour de l'ERP (24/11) à la fin du mois ; la note de la règle dit que
  ce sont des données de démo ;
- effet : 9,20 € → **8,46 €/kg** pour les boulangeries sans prix négocié (ex. Le Pétrin de Colomiers). Un prix négocié
  gagne toujours (La Gerbe d'Or reste à 8,82 €) ; les autres clients restent à 9,20 € ;
- pourquoi : la scène de démo « rupture du tourage AOP → remplaçant **en promo**, argumenté, avec accord ». L'agent ne
  cite la promo que parce que `get_price` la renvoie (règle « jamais de promo inventée ») ;
- **automatique depuis le 24/11 (Youssef)** : l'ERP l'ajoute lui-même à chaque chargement des données (1er démarrage,
  `make reset`, bouton de remise à zéro, `run_scenarios.py --reset`) : `apps/backend/app/core/team_demo.py`, même
  règle, id `prl_0900`. Avant, chaque remise à zéro l'effaçait et la scène de démo tombait (vu pendant les mesures T1).
  Le script de Daycem reste utilisable (il répond « déjà là »).

**Prêt pour le jury (Youssef, 24/11).** Testé sur un clone neuf avec seulement `data/seed/` remis en place et une base
vide : `make setup` échouait (« Permission denied » : les scripts `.sh` étaient enregistrés non exécutables depuis
Windows) → corrigé dans git. `make setup` ajoute aussi au `.env` les interrupteurs `TEAM_*` qui manquent (valeurs de
`.env.example`, sans toucher une ligne existante), pour qu'un `.env` venu d'ailleurs n'éteigne pas nos briques. Résultat :
ERP + promo (8,46 €), 7 interrupteurs, outils de l'équipe enregistrés, site et agent qui répondent.

## 6. Ce qui n'a pas marché / abandonné
