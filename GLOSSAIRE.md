# Glossaire

Les mots que vous croiserez dans le kit, en français simple : d'abord les **termes métier** du négoce alimentaire
(calibre, DLC, franco, encours, tournée…), puis les **termes techniques**. Le métier est expliqué en détail dans
[METIER.md](METIER.md).

Une question pratique plutôt qu'un mot ? [FAQ.md](FAQ.md).

| Thème | Mots |
|---|---|
| [1. Terminal et outils](#terminal) | terminal, dossier, `cd`, `make`, Docker, image, conteneur, port, localhost, `.env` |
| [2. Git et GitHub](#git) | git, repo, commit, push, GitHub |
| [3. Programmes et réseau](#reseau) | frontend, backend, service, API, endpoint, requête HTTP, JSON, WebSocket, SSE, Python, async, FastAPI, React |
| [4. LLM et agents](#llm) | LLM, prompt, token, contexte, cache de prompt, agent, harness, boucle, outil, Jev |
| [5. Voix et latence](#voix) | STT, TTS, streaming, latence, TTFT, premier son, barge-in, VAD |
| [6. Le kit](#kit) | mock, ERP |
| [7. Termes métier](#metier) | calibre, DLC, FEFO, encours, franco, tournée, avoir, mercuriale… |

<a id="terminal"></a>
## 1. Terminal et outils

| Mot | Définition | Dans le kit |
|---|---|---|
| **Terminal** | Fenêtre où l'on tape des commandes au lieu de cliquer. Sur Windows : le terminal **Ubuntu** (WSL), pas PowerShell. | Toutes les commandes `make …` de [SETUP.md](SETUP.md) |
| **Dossier courant**, **`cd`** | Le terminal est toujours « dans » un dossier. `cd voice-erp-kit` y entre, `cd ..` remonte d'un cran, `pwd` affiche où l'on est. | Les commandes `make` se lancent depuis `voice-erp-kit/` (là où est le `Makefile`) |
| **`make`** | Raccourci : `make up` lance une suite de commandes écrite dans le fichier `Makefile`. | `make help` liste tout : `setup`, `up`, `down`, `logs`, `chat`, `reset`… |
| **Docker** | Logiciel qui fait tourner des programmes dans des boîtes isolées, avec tout ce dont ils ont besoin. Rien d'autre à installer. | Docker Desktop, étape 1 de [SETUP.md](SETUP.md) |
| **Image** | Le « modèle » d'une boîte Docker : le programme et ses dépendances, prêts à lancer. | Construites par `make setup` / `make rebuild`, ou chargées depuis la clé USB (`make offline`) |
| **Conteneur** | Une image en train de tourner. Le kit en lance trois : `backend` (ERP), `ai` (agent), `web` (interface). | `make ps` les liste, `make logs` montre ce qu'ils écrivent |
| **Port** | Numéro de « porte » par lequel on parle à un programme sur une machine. | 5173 = interface, 4000 = ERP, 4100 = service IA |
| **localhost** | « Ma propre machine ». `http://localhost:5173` = le programme qui écoute sur le port 5173 de votre ordinateur. | Ouvrez http://localhost:5173 dans Chrome |
| **Variable d'environnement** | Un réglage (nom = valeur) lu par un programme au démarrage, hors du code. | `LLM_PROVIDER=anthropic`, `AI_PORT=4100` |
| **`.env`** | Le fichier qui contient toutes ces variables. Privé : jamais dans git. | Un seul `.env` à la racine pour les trois services ; après modification : `make restart` |
| **Clé API** | Mot de passe qui vous identifie auprès d'un fournisseur (Anthropic, Soniox…) et lui permet de facturer. | `LLM_API_KEY`, `STT_API_KEY`, `TTS_API_KEY`, `JEV_API_KEY` dans `.env` |
| **Logs** | Ce que les programmes écrivent pendant qu'ils tournent : requêtes, erreurs. Premier réflexe quand ça casse. | `make logs` (Ctrl-C pour sortir) |

<a id="git"></a>
## 2. Git et GitHub

| Mot | Définition | Dans le kit |
|---|---|---|
| **git** | Outil qui garde l'historique des versions de votre code, fichier par fichier. | `git init`, étape 4 de [SETUP.md](SETUP.md) |
| **Repo** (dépôt) | Un dossier suivi par git, avec tout son historique. | Votre repo d'équipe = le dossier `voice-erp-kit/` |
| **Commit** | Une photo enregistrée de vos changements, avec un message. | `git add . && git commit -m "filler avant les outils"` |
| **Push** | Envoyer vos commits vers un repo en ligne. | `git push` vers votre repo GitHub privé |
| **GitHub** | Site qui héberge des repos git en ligne et permet de les partager. | Le livrable « repo GitHub » de [BRIEF.md §8](BRIEF.md#8-livrables-et-démo-finale) |
| **`.gitignore`** | Liste des fichiers que git ne suit pas. | `.env` et `data/seed/` y sont, exprès |

<a id="reseau"></a>
## 3. Programmes et réseau

| Mot | Définition | Dans le kit |
|---|---|---|
| **Frontend** | La partie qu'on voit : pages, boutons, dans le navigateur. | `apps/web` (port 5173) |
| **Backend** | La partie serveur, invisible : données, règles, calculs. | `apps/backend` = l'ERP (port 4000) |
| **Service** | Un programme qui tourne en continu et répond à des demandes. | Trois services : ERP, IA, web |
| **API** | La liste des demandes qu'un programme accepte de la part d'autres programmes. | L'API de l'ERP : http://localhost:4000/docs ; celle du service IA : http://localhost:4100/docs |
| **Endpoint** (route) | Une adresse précise de l'API, qui fait une chose. | `GET /api/products`, `POST /ai/chat`, `GET /tools` |
| **Requête HTTP** | Un message envoyé à une adresse web. `GET` = lire, `POST` = créer ou agir, `PATCH` = modifier. | `curl localhost:4100/tools` en envoie une depuis le terminal |
| **JSON** | Format texte pour échanger des données : `{"produit": "bar", "kilos": 5}`. | Ce que renvoient l'ERP et les outils de l'agent |
| **WebSocket** | Connexion qui reste ouverte entre navigateur et serveur, dans les deux sens. Idéal pour envoyer l'audio en continu. | `WS /ai/voice` (page Voix), `WS /ai/voice/command` (⌥Espace) |
| **SSE** (*server-sent events*) | Réponse HTTP qui arrive morceau par morceau, du serveur vers le navigateur. | `POST /ai/chat` : le texte de l'agent s'affiche au fil de l'eau |
| **Python** | Le langage du backend et du service IA. Lisible, beaucoup de bibliothèques. | `apps/backend`, `apps/ai` |
| **async** (asynchrone) | Code qui peut attendre (une réponse réseau) sans tout bloquer : pendant ce temps, autre chose avance. Mots-clés `async def` et `await`. | Tout le service IA : plusieurs outils tournent en parallèle (`asyncio.gather`) |
| **FastAPI** | Bibliothèque Python qui transforme des fonctions en endpoints d'API. | `routers/` de l'ERP et du service IA |
| **React** | Bibliothèque JavaScript pour construire l'interface en composants. | `apps/web/src` (TypeScript) |
| **TypeScript** | JavaScript avec des types vérifiés. | Le frontend ; `make check` vérifie qu'il compile |

<a id="llm"></a>
## 4. LLM et agents

Pour aller plus loin : [GUIDE-AGENTS.md](GUIDE-AGENTS.md).

| Mot | Définition | Dans le kit |
|---|---|---|
| **LLM**, **modèle** | *Large language model* : un programme qui prédit la suite d'un texte, et sait donc répondre, raisonner, appeler des outils. | Anthropic par défaut : `claude-sonnet-5-5` (`LLM_MODEL` dans `.env`) |
| **Prompt** | Le texte envoyé au modèle : instructions + conversation. | Construit par `agent/prompts.py` |
| **Prompt système** | La partie fixe du prompt, qui dit au modèle qui il est et comment se comporter. | `build_system_prompt` : rôle, règles (`BASE_RULES`, `VOICE_RULES`…), contexte entreprise |
| **Token** | Un morceau de mot (≈ ¾ de mot en moyenne). Les modèles lisent, écrivent et facturent en tokens. | Le prompt du kit fait ≈ 27 000 tokens par appel modèle |
| **Contexte** | Tout ce que le modèle voit à un instant : prompt système, historique, résultats d'outils. Il est limité en taille. | `data/context/*.md` (le savoir de votre entreprise) + l'historique de l'appel |
| **Cache de prompt** | Le fournisseur garde en mémoire un début de prompt identique d'un appel à l'autre : moins cher et plus rapide. Un seul octet changé au début le casse. | `clients/anthropic.py` (`cache_control`) ; `cache_read_input_tokens` dans `usage` |
| **Agent** | Un LLM qui agit : il lit la demande, appelle des outils, lit les résultats, recommence, puis répond. | `agent/loop.py` (`run_agent`) |
| **Boucle** | Le cycle « modèle → outils → modèle… » jusqu'à la réponse finale. | `AGENT_MAX_STEPS=8` tours au maximum |
| **Outil** (*tool*) | Une fonction que le modèle peut demander d'appeler, avec un nom, une description et des paramètres. | Fonctions `@tool` dans `apps/ai/app/tools/*.py` (`search`, `get_price`, `create_draft_order`…) |
| **Harness** | Tout le code autour du modèle : la boucle, les outils, le prompt, la gestion des erreurs. C'est là que vous travaillez. | `apps/ai/app/agent/` + `tools/` |
| **Jev** | Modèle de décision de TypeSafe AI : pas un chat, il répond vite à des questions fermées (choix, oui/non, score) avec une probabilité. Utilisé **à côté** du LLM. | `get_jev_client()`, exemples `agent/jev_examples.py` ; clé `JEV_API_KEY` |

<a id="voix"></a>
## 5. Voix et latence

Pour aller plus loin : [GUIDE-VOIX.md](GUIDE-VOIX.md).

| Mot | Définition | Dans le kit |
|---|---|---|
| **STT** (*speech-to-text*) | Transcription : la voix devient du texte. | Soniox par défaut avec vos clés (`STT_PROVIDER`) ; `services/utterance.py` |
| **TTS** (*text-to-speech*) | Synthèse vocale : le texte devient de la voix. | ElevenLabs (`TTS_PROVIDER`) ; `Speaker` dans `services/voice_session.py` |
| **Streaming** (en flux) | Traiter les données au fur et à mesure au lieu d'attendre la fin. | L'audio part au STT pendant que vous parlez ; le texte du LLM part au TTS phrase par phrase |
| **Transcription partielle** | Le texte provisoire que le STT renvoie pendant la parole, corrigé ensuite. | Affichée en gris italique sur la page Voix |
| **Push-to-talk** | On maintient une touche pendant qu'on parle ; le relâchement marque la fin de parole. | Espace sur la page Voix, ⌥Espace partout |
| **VAD** (*voice activity detection*) | Détecter automatiquement quand quelqu'un parle et quand il a fini. | Pas dans le kit : piste 4.2 de [GUIDE-VOIX.md](GUIDE-VOIX.md#vad) |
| **Latence** | Le temps d'attente. Ici : de la fin de votre phrase au premier son de l'agent. | Colonnes **Total** et **Perçu** de la page Voix |
| **TTFT** (*time to first token*) | Temps entre l'envoi au modèle et son premier morceau de réponse. | `llmFirstTokenMs` dans les mesures de chaque tour |
| **Premier son** | Le moment où l'appelant entend l'agent. C'est la métrique du prix « le plus rapide ». | `totalMs` (serveur) et `perceivedMs` (navigateur) |
| **Barge-in** | L'appelant coupe la parole à l'agent : il faut arrêter l'audio et écouter. | `interrupt()` dans `voice_session.py` |

<a id="kit"></a>
## 6. Le kit

| Mot | Définition | Dans le kit |
|---|---|---|
| **Mock** | Un faux fournisseur, gratuit et hors ligne, qui imite le vrai. Pour développer sans clé. | `*_PROVIDER=mock` ; le STT mock entend toujours « Bonjour, il vous reste du bar ? » (`MOCK_STT_TEXT`) |
| **ERP** | Le logiciel de gestion de l'entreprise : clients, produits, stock, commandes, factures. | `apps/backend` + les pages de l'interface ; voir [ERP.md](ERP.md) |
| **Seed** | Les données de départ chargées dans l'ERP. | `data/seed/` ; `make reset` les recharge |
| **`x-actor`** | En-tête qui dit qui a fait une écriture dans l'ERP (`user`, `ai_chat`, `voice_agent`). | En violet dans l'interface : ce que l'agent a fait |

<a id="metier"></a>
## 7. Termes métier

Le vocabulaire du négoce alimentaire, et où il apparaît dans l'ERP (entités, champs, routes).

| Terme | Définition | Dans l'ERP |
|---|---|---|
| Affrètement | Louer un camion ou confier une livraison à un transporteur | absent |
| Alias | Nom courant d'un produit (« loup » pour bar) | `Product.aliases` |
| AOP, Label Rouge | Signes officiels de qualité ou d'origine | `Product.tags` (`labels`) |
| Arrivage, débarque | Marchandise qui arrive, ce que les bateaux ramènent | `PurchaseOrder`, `Lot` |
| Avoir | Facture négative après un retour ou un litige | événement `credit_note` |
| Balance âgée | Encours réparti par ancienneté du retard | `GET /api/receivables` |
| BL (bon de livraison) | Document qui accompagne la livraison | — |
| Bordereau de prix | Prix fixés par un marché public | `ClientPrice`, `PriceRule` (`marche-public`) |
| Bourriche | Panier d'huîtres (ex. 4 douzaines) | unité `dozen` |
| Brouillon, pré-commande | Commande non validée par le client | `Order.status = "draft"` |
| Calibre | Taille d'un produit (1-2 kg, 15/20, n° 3) | `Product.caliber` |
| Chaîne du froid | Maintien continu de la température | — |
| Colis, caisse | Unité d'emballage | unité `box` (≈ 5 kg) |
| Commande d'achat | Commande passée à un fournisseur | `PurchaseOrder` |
| Commercial attitré | Vendeur responsable d'un client | `Client.salesRep` |
| Complément | Reste d'une livraison incomplète, livré plus tard | `partially_received` |
| Couverture | Nombre de jours de ventes que le stock permet de tenir | — |
| Criée | Halle où la pêche est vendue aux enchères | — |
| Cut-off, heure limite | Heure après laquelle la commande part au jour suivant | contexte seulement |
| DDM | Date de durabilité minimale, « de préférence avant » | — |
| Déclassement | Produit vendu moins cher ou transformé car moins beau | — |
| Démarque, perte, casse | Ce qui est jeté | mouvement `waste` |
| DLC | Date limite de consommation, « jusqu'au » | `Lot.expiresAt`, `Product.shelfLifeDays` |
| Disponible | Stock physique moins stock réservé | `StockLevel.available` |
| DSO | Délai moyen de paiement des clients | `GET /api/receivables` |
| Échéance | Date à laquelle la facture doit être payée | `Invoice.dueDate` |
| Échu, en retard | Facture non payée après échéance | statut calculé `overdue` |
| Encours | Total dû par un client, € TTC | `outstanding` |
| Extra | Commande ponctuelle hors habitudes | — |
| FEFO | Premier expiré, premier sorti | `fefo_lots` dans `services/stock.py` |
| Franco | Montant à partir duquel le transport est offert | `Supplier.notes` |
| Geste commercial | Remise accordée pour réparer un problème | événement + `resolution` |
| HACCP | Méthode d'analyse des dangers en hygiène alimentaire | — |
| L'habituel | Ce que le client commande presque toujours | `GET /api/clients/{id}/usual` |
| Lot | Une arrivée d'un produit, avec sa date limite | `Lot` |
| Mareyeur | Premier acheteur du poisson à la criée, qui le prépare et l'expédie | `Supplier.tags` (`mareyeur`) |
| Marché public | Contrat d'achat d'une collectivité après appel d'offres | tag client `marche-public` |
| Mercuriale | Liste de prix du jour d'un fournisseur | `SupplierPrice` |
| MIN | Marché d'intérêt national (Rungis, Lyon, Marseille…) | — |
| Minimum de commande | Montant minimal pour commander à un fournisseur | `Supplier.minOrderAmount` |
| Plafond de crédit | Encours maximal autorisé | `Client.creditLimit` |
| Plan d'apurement | Échéancier pour rembourser une dette | événement `payment_plan` |
| Poids réel | Ce que pèse ce qui est livré | `OrderLine.preparedQty` |
| Prix liste, catalogue | Prix de base | `Product.price` |
| Prix négocié | Prix d'un produit pour un client | `ClientPrice` |
| Prospect | Client potentiel | `Client.status = "prospect"` |
| Relance | Rappel d'une facture impayée | événement `late_payment` |
| Réservé | Stock promis à des commandes confirmées | `StockLevel.reserved` |
| RHD | Restauration hors domicile | — |
| Rupture | Plus de stock disponible | alerte `insufficient_stock` |
| Substitution | Produit livré à la place d'un autre, avec accord | `OrderLine.substituteFor` |
| Tournée | Circuit d'un camion sur une zone, certains jours | `Route`, `RouteRun` |
| Zone | Secteur de livraison d'un client | `Client.zone` = `Route.zone` |
