# GUIDE-VOIX.md — faire un agent vocal rapide et naturel

Ce guide explique comment marche un agent vocal « au téléphone », ce que le kit fait aujourd'hui, ce qu'il mesure,
et **où changer le kit** pour aller plus vite et sonner plus humain. Le jury juge sur *smart, fast, natural*, avec
un prix spécial pour le plus rapide (fin de parole → premier son, mesuré en démo) : ce guide couvre surtout *fast*
et *natural*.

Ce que ce guide ne répète pas : l'installation ([SETUP.md](SETUP.md)), le défi ([BRIEF.md](BRIEF.md)), le détail du
code ([TECH.md](TECH.md), sections 1.3, 4 et 9), les concepts d'agent LLM (boucle, outils, contexte, cache,
modèles, Jev : [GUIDE-AGENTS.md](GUIDE-AGENTS.md)), le protocole WebSocket ([apps/ai/README.md](apps/ai/README.md#ws-voice-protocol)).

Règle de lecture des chiffres : les nombres **mesurés** viennent d'un test réel sur le kit (novembre 2026). Tout
autre nombre est marqué **ordre de grandeur** : c'est une hypothèse à mesurer chez vous, pas une promesse.

## Sommaire

1. [Anatomie d'un tour de parole](#anatomie)
2. [Les métriques](#metriques)
3. [Ce que le kit mesure aujourd'hui](#mesures)
4. [Accélérer, technique par technique](#accelerer)
5. [Sonner naturel](#naturel)
6. [Robustesse](#robustesse)
7. [Fournisseurs du kit](#fournisseurs)
8. [Plan d'attaque pour 24 h](#plan)

## Je veux… → section

| Je veux… | Section | Fichiers |
|---|---|---|
| comprendre où part le temps d'un tour | [1](#anatomie), [3](#mesures) | `apps/ai/app/services/voice_session.py` |
| savoir quoi mesurer et comment le prouver au jury | [2](#metriques), [8](#plan) | `apps/web/src/pages/voice/metrics.tsx`, `DECISIONS.md` |
| transcrire pendant que l'appelant parle (fait) | [4.1](#stt-streaming) | `services/utterance.py`, `services/vocabulary.py`, `clients/soniox.py` |
| supprimer le push-to-talk (VAD) | [4.2](#vad) | `apps/web/src/features/assistant/useVoiceSession.ts` |
| réduire le temps du modèle | [4.4](#cache) à [4.6](#outils) | `clients/anthropic.py`, `clients/factory.py`, `tools/` |
| faire patienter sans blanc | [4.7](#fillers) | `voice_session.py` (`Speaker`) |
| que les chiffres et les dates soient bien dits | [4.10](#deterministe), [5](#naturel) | `agent/prompts.py`, `tools/` |
| gérer les interruptions | [5.2](#barge-in) | `voice_session.py` (`interrupt`), `useVoiceSession.ts` |
| changer de voix ou de fournisseur | [7](#fournisseurs) | `.env`, `clients/factory.py` |

---

<a id="anatomie"></a>
## 1. Anatomie d'un tour de parole

### Deux architectures

**En cascade** (ce que fait le kit) : trois modèles à la suite.

```
voix de l'appelant ─▶ STT (parole → texte) ─▶ LLM (+ outils ERP) ─▶ TTS (texte → parole) ─▶ haut-parleur
```

**Speech-to-speech** (modèles « realtime » audio natifs) : un seul modèle écoute l'audio et produit de l'audio.

| | Cascade | Speech-to-speech |
|---|---|---|
| Latence | somme des étapes, sauf si on les chevauche (streaming) | une étape de moins, souvent plus court |
| Contrôle | on lit et on corrige chaque étape (transcript, texte, appels d'outils) | boîte plus noire ; texte disponible selon le fournisseur |
| Outils / ERP | n'importe quel LLM avec appels d'outils | dépend du modèle realtime |
| Voix | on choisit la meilleure voix française du marché | la voix du modèle |
| Dans le kit | prêt, avec vos clés | **non fourni**, et aucune clé realtime n'est distribuée |

Conseil pour 24 h : gardez la cascade et **chevauchez les étapes**. C'est là que se gagnent les secondes.

### Le pipeline du kit, en temps

Tour vocal de la page Voix (`WS /ai/voice`, `services/voice_session.py`, `VoiceConnection.run_turn`) :

```
temps ─────────────────────────────────────────────────────────────────────────────────▶
appelant  [■■■■ parle (Espace enfoncé) ■■■■]│relâche = t0
navigateur MediaRecorder webm/opus, trame toutes les 100 ms ─▶ serveur ─▶ STT en flux (Soniox)
          ◀── transcription partielle affichée en direct ──│
serveur                                    │[finalize]│ texte final
                                           │          │[── LLM ─▶ outil(s) ERP ─▶ LLM ──]
                                           │          │                     texte ─▶ Speaker
                                           │          │                     │[TTS phrase 1]─▶ 1er octet mp3
navigateur                                 │          │                     │   SegmentPlayer (MediaSource) joue
          ◀──────────────── totalMs : t0 → premier octet audio envoyé par le serveur ─────────▶
```

Points clés du code :

- **Push-to-talk** : Espace enfoncé = `audio_start`, relâché = `audio_end` (`useVoiceSession.ts`, `startTalking` /
  `stopTalking`). Pas de détection de fin de parole : c'est le relâchement qui la donne.
- **STT en direct** : à `audio_start`, la session ouvre une `Utterance` (`services/utterance.py`) qui ouvre le flux
  du STT ; chaque trame de 100 ms (`rec.start(100)` dans `useVoiceSession.ts`) lui est transmise dès réception.
  Les transcriptions partielles s'affichent pendant l'appui. Au relâchement, Soniox reçoit `finalize` et rend les
  derniers mots ; `run_turn` démarre l'agent sur ce texte final. Si le flux casse, l'enregistrement complet est
  transcrit comme avant (`transcribe`). Les noms de clients et de produits sont ajoutés à l'indice STT
  (`services/vocabulary.py`).
- **LLM en streaming** : `run_agent(..., mode="voice")` (`agent/loop.py`) émet le texte au fil de l'eau ; les outils
  d'une même étape tournent en parallèle (`asyncio.gather`).
- **TTS phrase par phrase** : `Speaker.push` découpe dès qu'une phrase finit par `. ! ? …` suivi d'un espace
  (`Speaker.SENTENCE`) et l'envoie au TTS ; un worker synthétise les phrases dans l'ordre ; tout le tour forme un
  seul segment mp3.
- **Lecture** : `SegmentPlayer` (`features/assistant/audio-player.ts`) joue le mp3 dès le premier octet via
  MediaSource.
- **Commande ⌥Espace** (`WS /ai/voice/command` à la voix, `POST /ai/command` au clavier ; `services/command.py`) :
  même STT en direct, agent sans historique, mais le TTS porte sur **toute** la réponse une fois finie (pas de
  découpage par phrase). Sur Windows, Alt+Espace est pris par le système : utilisez l'onglet **Commande** de la page
  Voix (Espace ou le bouton micro).

---

<a id="metriques"></a>
## 2. Les métriques

### Celle que l'utilisateur ressent

**Fin de parole → premier son de l'agent.** C'est celle du prix « le plus rapide ». Tout le reste n'est que sa
décomposition :

| Métrique | Définition | Ce qui la pilote |
|---|---|---|
| Endpointing | fin réelle de la parole → le système *décide* que l'appelant a fini | push-to-talk : 0 (le relâchement) ; VAD : le silence attendu |
| Latence STT | fin de parole → transcription finale disponible | STT en flux ou non, fournisseur |
| TTFT LLM (*time to first token*) | début de l'appel modèle → premier token de texte | taille du prompt, cache, modèle, effort |
| Allers-retours outils | chaque appel d'outil = un appel modèle de plus + l'appel ERP | nombre d'étapes, outils composites |
| TTFB TTS (*time to first byte*) | texte envoyé au TTS → premier octet audio | fournisseur, connexion chaude, longueur de la 1re phrase |
| Lecture | premier octet reçu → son audible | buffer du lecteur, réseau |

### Tours de parole

- **VAD** (*voice activity detection*) : détecter qu'il y a de la voix. **Endpointing** : décider qu'un tour est fini
  (silence assez long, phrase complète). Trop court = on coupe l'appelant ; trop long = blanc gênant.
- **Barge-in** : l'appelant parle pendant que l'agent parle. Il faut couper l'audio de l'agent immédiatement,
  annuler le travail en cours et écouter.

### Comment le kit les mesure

`TurnTimings` (`apps/ai/app/schemas/chat.py`) est rempli à chaque tour et envoyé dans `agent_done` (voix) ou `done`
(commande) :

| Champ | Mesuré où | Sens |
|---|---|---|
| `sttMs` | `run_turn` / `run_command` | relâchement (t0) → transcription finale |
| `llmFirstTokenMs` | premier `TextEvent` | début de l'agent → premier token **de texte** (outils compris s'ils passent avant) |
| `llmTotalMs` | fin de `run_agent` | tout l'agent, outils compris |
| `ttsFirstByteMs` | `Speaker._speak_queued` | appel TTS de la 1re phrase → premier octet |
| `totalMs` | `Speaker.first_byte_at - t0` | **t0 → premier octet audio envoyé** (voix) ; en commande : t0 → fin de tout |
| `perceivedMs` (navigateur) | `useVoiceSession.ts`, `markPerceived` | relâchement → l'audio **joue** dans le navigateur |

La page **Voix** affiche ces valeurs par tour et leur moyenne (`pages/voice/metrics.tsx`) : vert sous 1,5 s, orange
sous 3 s, rouge au-delà pour `Total` et `Perçu`.

Attention : en mode `commande`, `totalMs` inclut tout le TTS (la synthèse complète), il ne se compare donc pas au
`totalMs` du mode voix.

### Mesurer en démo

- Montrez la colonne **Perçu** de la page Voix : c'est la métrique côté oreille.
- Si vous passez au VAD, **t0 change** : c'est le dernier instant de voix détectée, pas le moment où le VAD décide.
  Comptez le silence d'endpointing dans votre chiffre, sinon le jury le verra.
- Contre-mesure indépendante : enregistrez l'appel (micro + haut-parleur) et mesurez le blanc sur la forme d'onde
  dans n'importe quel éditeur audio.
- Notez médiane **et** pire cas sur vos scénarios (5 à 10 appels), pas le meilleur tour.

---

<a id="mesures"></a>
## 3. Ce que le kit mesure aujourd'hui

Test réel, novembre 2026, **avant la transcription en direct** (4.1) : LLM Anthropic Sonnet 5.5, STT Soniox, TTS
ElevenLabs, phrase de l'appelant d'environ 4 secondes, un appel d'outil. Les totaux ci-dessous comprennent donc
l'ancien STT ; depuis, ils sont plus bas d'à peu près la durée de ce STT.

| Étape | Mesuré | Lecture |
|---|---|---|
| STT | **3,4 à 4,9 s** (avant la transcription en direct) | Soniox ne commençait qu'après `audio_end`. **Depuis 4.1, l'audio part pendant la parole** : au relâchement il ne reste que les derniers mots à finaliser, le texte final arrive quelques centaines de ms après. Pas encore remesuré : mesurez `sttMs` chez vous. |
| LLM, premier token | **≈ 4,2 à 4,4 s**, aller-retour d'outil compris | le modèle appelle un outil avant de dire quoi que ce soit |
| TTS, premier octet | **170 à 370 ms** à chaud ; **≈ 1,9 s** au premier appel (froid) | ElevenLabs est rapide une fois la connexion ouverte |
| Total `/command` | **8,4 s** | |
| Total voix (WS) | **9,6 s** | |
| Prompt | **≈ 27 000 tokens d'entrée par appel modèle**, avant cache | règles + tous les `DATA_DIR/context/*.md` + schémas des outils, renvoyés à chaque étape |

Ce que ça veut dire :

1. **Le texte du LLM arrive presque d'un bloc après les outils** : premier token ≈ dernier token. Le découpage
   phrase par phrase vers le TTS existe déjà mais gagne peu tant que la réponse n'arrive qu'à la fin.
2. Il y avait **deux gros postes** : le STT (≈ 4 s) et le LLM avec ses outils (≈ 4 s). Le STT est traité
   (transcription en direct, 4.1). **Le gros poste restant est le LLM et ses outils.** Le TTS (≈ 0,3 s) est déjà
   bon une fois chaud.
3. Le gain « facile » suivant : faire parler l'agent **avant** les outils (4.7).

---

<a id="accelerer"></a>
## 4. Accélérer, technique par technique

Résumé :

| # | Technique | Gain attendu | Où dans le kit | Difficulté |
|---|---|---|---|---|
| 4.1 | STT en flux pendant la parole — **fait** ; reste : vocabulaire, Finalize Deepgram | la plupart des 3,4–4,9 s du STT (fait) | `services/utterance.py`, `services/vocabulary.py` | facile (le reste) |
| 4.2 | VAD / endpointing au lieu du push-to-talk | naturel ; latence = silence attendu | `useVoiceSession.ts`, ou endpointing du STT | moyenne |
| 4.3 | Lancer le LLM sur un transcript partiel stable | une partie du TTFT | `voice_session.py` | difficile |
| 4.4 | Cache de prompt — **en place** | TTFT et coût sur ≈ 27k tokens | `clients/anthropic.py` (à vérifier) | facile |
| 4.5 | Modèle plus petit / routage | TTFT | `.env`, `clients/factory.py`, Jev | facile à moyenne |
| 4.6 | Moins d'allers-retours d'outils | un appel modèle par outil évité | `tools/`, `agent/prompts.py` | moyenne |
| 4.7 | Fillers pendant les outils | premier son avant les outils | `Speaker`, `agent/prompts.py` | facile |
| 4.8 | TTS en flux et découpage plus tôt | petit aujourd'hui | `Speaker`, `clients/elevenlabs.py` | facile à moyenne |
| 4.9 | Connexions chaudes | ≈ 1,6 s sur le 1er tour (1,9 s froid vs ≈ 0,3 s chaud) | `VoiceConnection.open` | facile |
| 4.10 | Réponses courtes, code déterministe | moins de tokens générés | `agent/prompts.py`, `tools/` | facile |
| 4.11 | Cache de données, préchargement | appels ERP évités | `tools/`, `prompts.py` | moyenne |
| 4.12 | Régions / colocalisation | réseau | infra | dépend |

<a id="stt-streaming"></a>
### 4.1 STT en flux pendant que l'appelant parle

**Fait.** Le navigateur envoie une trame toutes les 100 ms ; le serveur la transmet au STT dès réception
(`services/utterance.py`). Pendant la parole, la page Voix (Appel et Commande) et le HUD ⌥Espace affichent le texte
entendu en direct : mots définitifs en couleur normale, mots provisoires en gris italique (`transcript` avec
`final: false`). Au relâchement, Soniox reçoit `{"type": "finalize"}` et rend les derniers mots aussitôt ; le tour
de l'agent démarre sur ce texte final. Si le flux casse, l'enregistrement complet est transcrit comme avant. Le mock
STT simule des partiels : l'affichage se teste sans clé. Détails : TECH.md, « Transcription en direct ».

**Le vocabulaire compte.** Un STT générique entend « le moine » pour « Lemoine », « turbos » pour « turbot ».
Le serveur ajoute donc à l'indice STT les noms des clients, des produits et leurs alias lus dans l'ERP
(`services/vocabulary.py`) : Soniox les reçoit en `context.terms`, Deepgram en `keyterm`. Les noms propres de vos
clients passent en premier. Un nom mal entendu, c'est un mauvais client ou un mauvais produit dans la commande.

**Ce que vous pouvez encore améliorer.**

- Lancer le LLM sur un partiel stable avant le relâchement ([4.3](#llm-partiel)).
- Mode mains libres : finir le tour sur les jetons `<end>` de Soniox ou un VAD ([4.2](#vad)).
- Vocabulaire plus fin : noms des contacts, panier habituel du client une fois identifié, termes de votre métier.
- Deepgram termine encore par `CloseStream` (attend la fermeture) : `{"type": "Finalize"}` serait plus rapide.

<a id="vad"></a>
### 4.2 Endpointing / VAD au lieu du push-to-talk

**Idée.** Au téléphone, personne n'appuie sur une touche. Deux options :

- **Côté navigateur** : le niveau micro est déjà calculé (`meter()` dans `useVoiceSession.ts`, `AnalyserNode`).
  Démarrer `audio_start` au-dessus d'un seuil, envoyer `audio_end` après N ms de silence.
- **Côté STT** : les STT temps réel savent signaler la fin d'un énoncé (endpointing). Le client Deepgram ignore
  aujourd'hui les messages `UtteranceEnd` ; Soniox renvoie des jetons de contrôle (`<end>`, `<fin>`) que
  `soniox.py` saute. Ce sont les deux points d'entrée.

**Gain.** Surtout *natural*. Pour *fast*, le silence d'attente s'ajoute à la latence : ordre de grandeur
300 à 800 ms selon le réglage. Mesurez avec du bruit (marché, cuisine) : un seuil trop bas ne termine jamais le tour.

**Difficulté.** Moyenne. Gardez Espace comme mode de secours pour la démo.

<a id="llm-partiel"></a>
### 4.3 Démarrer le LLM sur un transcript partiel (spéculatif)

**Idée.** Avec 4.1, le texte est presque complet avant la fin de la parole (les partiels arrivent déjà au serveur :
`on_partial` dans `Utterance`). Quand le partiel ne bouge plus depuis
un court instant, lancer l'agent ; si le transcript final diffère, annuler et relancer.

**Où.** `voice_session.py` : la tâche de tour s'annule déjà proprement (`interrupt()`, annulation asyncio).

**Garde-fou.** Une écriture ERP partie ne s'annule pas (TECH.md, piège 9). Ne spéculez que sur les étapes en
lecture (`search`, `get_product_stock`, `get_price`…), jamais sur `create_draft_order` / `confirm_order`.

**Difficulté.** Difficile ; à faire après 4.7 et la vérification du cache (4.4).

<a id="cache"></a>
### 4.4 Cache de prompt

**Idée.** ≈ 27 000 tokens identiques (règles, contexte entreprise, outils) sont renvoyés à **chaque** appel modèle,
y compris après chaque outil. Le cache de prompt du fournisseur relit ce préfixe au lieu de le retraiter.

**Où.** `clients/anthropic.py` pose maintenant trois points de cache (`cache_control`) : dernier outil, prompt
système, dernier bloc de la conversation. Vérifiez qu'il prend : `cache_read_input_tokens` dans `usage` de
l'événement `done` de `POST /ai/chat` (la session vocale ne renvoie pas `usage` : loggez-le si besoin).

**Ce qui casse le cache** (préfixe octet pour octet) : modifier un `DATA_DIR/context/*.md` pendant l'appel (relus à
chaque tour), ajouter l'heure ou un id dans le prompt système, changer l'ordre ou la liste des outils, changer de
modèle. Le cache expire après quelques minutes sans appel.

**Gain.** Coût certain ; TTFT : à mesurer avant/après sur vos scénarios. Réduire le contexte (ne mettre que ce dont
le tour a besoin) aide en plus.

<a id="modele"></a>
### 4.5 Modèle plus petit, routage

- **Changer de modèle sans code** : `LLM_MODEL=` dans `.env`, puis `make restart`. Défaut Anthropic du kit :
  `claude-sonnet-5-5` (`DEFAULT_MODELS`, `clients/factory.py`). Un Haiku (`claude-haiku-5-5`) répond plus vite et
  moins cher ; vérifiez qu'il appelle bien les outils sur vos scénarios difficiles.
- **`LLM_EFFORT=low`** (défaut du kit) garde la réflexion courte ; ne le montez que si les tours difficiles échouent.
- **Routage** : un petit modèle pour les tours simples (« oui », « c'est tout », « merci »), le gros quand il faut
  raisonner. Pour classer le tour, **Jev** répond à des questions fermées (choix, oui/non, score) avec
  probabilités : `get_jev_client()`, exemples `agent/jev_examples.py` (`pick_product`, `is_yes`). Rien dans
  l'agent par défaut ne l'appelle : à brancher dans `run_turn` avant `run_agent`.

<a id="outils"></a>
### 4.6 Moins d'allers-retours d'outils

Chaque appel d'outil coûte un appel modèle de plus (le modèle relit tout le prompt), plus l'appel ERP.

- **Outils composites** : un outil qui fait « trouver le produit + stock + prix client » en un appel. Exemple
  complet en [TECH.md 5.4](TECH.md#outil-composite).
- **Précharger le client au début de l'appel** : si l'on sait qui appelle, chargez sa fiche (`GET /api/context/for`,
  `get_client`) à `start` et ajoutez-la à `parts` dans `build_system_prompt` (`agent/prompts.py`). Le modèle
  n'a plus besoin de `search` + `get_client` + `get_context` au premier tour. Mettez-la **à la fin** du prompt
  système pour ne pas casser le cache du reste.
- **Outils en parallèle** : la boucle exécute déjà en parallèle les outils demandés dans la même étape
  (`asyncio.gather` dans `loop.py`). Dites-le au modèle dans le prompt (« appelle les outils indépendants
  ensemble »). Le mock LLM n'en appelle qu'un par étape : mesurez avec un vrai modèle.
- **Retours petits** : un outil qui renvoie peu de JSON se relit plus vite à chaque étape.

<a id="fillers"></a>
### 4.7 Fillers et relances pendant les outils

**Idée.** Sans phrase d'attente, l'agent se tait pendant les outils (≈ 4 s mesurées) puis répond d'un bloc. Une phrase courte **avant** les outils
(« Je regarde. », « Deux secondes, je vérifie le stock. ») donne un premier son tôt.

**Où.**

- Par le prompt : `VOICE_RULES` (`agent/prompts.py`) rappelle que tout texte écrit est prononcé dans l'ordre,
  même entre deux appels d'outils. Il autorise **au plus une très courte phrase d'attente avant le premier outil**
  (« Je regarde. »), puis plus rien entre les outils ; la vraie réponse vient une seule fois, à la fin. Ce texte
  d'avant-outil part au TTS dès sa ponctuation (`Speaker`). Le modèle ne le fait pas à chaque fois : mesurez.
- Par le code (plus fiable, plus rapide) : sur le premier `ToolCallEvent` du tour, si rien n'a encore été dit,
  `speaker.speak("Je regarde.")` dans `run_turn`. Encore plus rapide : un petit mp3 **pré-synthétisé** au démarrage
  (aucun appel TTS au moment voulu), à envoyer dans le segment audio du tour.

**Honnêteté.** Un filler compte comme premier son, mais un « euh, je regarde » systématique s'entend. Variez,
gardez-le court, et dites dans `DECISIONS.md` ce que mesure votre chiffre (premier son utile ou filler).

### 4.8 TTS : découper plus tôt, streamer

- **Déjà fait** : phrase par phrase, un segment mp3 par tour, lecture dès le premier octet.
- **Couper plus tôt** : `Speaker.SENTENCE` attend `. ! ? …` suivi d'un espace ; la dernière phrase part seulement à
  `finish()`. Couper aussi aux virgules pour la **première** phrase raccourcit le premier son (au prix d'une
  prosodie parfois hachée : écoutez).
- **TTS par WebSocket** : on ouvre une connexion, on envoie le texte au fil de l'eau, l'audio revient en flux.
  ElevenLabs propose une telle API d'entrée en flux (voir leur documentation) ; le client du kit utilise la route
  REST `/stream` (`clients/elevenlabs.py`). Gain surtout utile quand le LLM streame vraiment son texte (après 4.6
  et 4.7).

### 4.9 Connexions chaudes

**Mesuré** : premier appel TTS ≈ 1,9 s, ensuite 170–370 ms. Le kit partage déjà un client HTTP
(`clients/http.py`, `http_client()`) qui garde les connexions TLS ouvertes.

**Où.** Dans `VoiceConnection.open()`, lancez en tâche de fond une synthèse minuscule (un mot) et, si vous le
voulez, un appel modèle court : le premier vrai tour trouve tout ouvert. Même idée pour l'ERP (`erp_http()` dans
`tools/erp.py`, déjà en keep-alive).

<a id="deterministe"></a>
### 4.10 Réponses courtes et code déterministe

- **Court** : chaque token généré se paie en temps et en audio. `VOICE_RULES` demande 1 à 2 phrases ; tenez-le.
- **Code plutôt que modèle** pour ce qui n'a pas besoin de réflexion : conversion d'unités, calcul de totaux,
  dates (« jeudi prochain » → date ISO à partir du `today` de l'ERP), mise en mots des nombres. Un outil ou une
  fonction Python est plus rapide et ne se trompe pas. Le kit n'a pas de fonction « nombre → français parlé »
  (`format_number` de `tools/catalog.py` ne fait que `5.0 → "5"`) : écrivez-la si vos réponses lisent des prix.

### 4.11 Cache de données, préchargement

Le catalogue et les prix négociés d'un client bougent peu pendant un appel. Gardez en mémoire, pour la session, ce
que l'agent a déjà lu (fiche client, produits cités) et servez-le depuis l'outil sans rappeler l'ERP. Attention au
stock, qui change pendant la démo (l'ERP est vivant).

### 4.12 Régions et colocalisation

Chaque fournisseur ajoute un aller-retour réseau. En démo vous êtes sur le Wi-Fi du lieu : testez sur place, gardez
un partage de connexion en secours. Si un fournisseur propose une région européenne, préférez-la (ordre de
grandeur : dizaines de millisecondes par aller-retour transatlantique).

---

<a id="naturel"></a>
## 5. Sonner naturel

### 5.1 Tours de parole

- Une idée, une question par tour (`VOICE_RULES` : « Une seule question à la fois »).
- Phrases courtes : elles partent plus tôt au TTS **et** s'écoutent mieux.
- Pas de « Autre chose ? » à chaque tour : au téléphone, on laisse l'autre parler.

<a id="barge-in"></a>
### 5.2 Barge-in

**Ce que fait le kit** : un nouvel `audio_start` ou `text` appelle `interrupt()` (`voice_session.py`) : le tour est
annulé, le flux TTS est fermé (`aclosing`), ce qui a été entendu et dit reste dans l'historique avec « … ». Côté
navigateur, `startTalking` coupe la lecture (`stopPlayback`).

**À savoir** :

- En push-to-talk, l'interruption n'existe que si l'appelant appuie sur Espace. Avec un VAD (4.2), il faut détecter
  la voix **pendant** que l'agent parle : le micro est ouvert avec `echoCancellation: true`, mais testez avec un
  haut-parleur, sinon l'agent s'interrompt lui-même.
- L'historique garde le texte **généré**, pas ce qui a été **entendu** : si l'appelant coupe au milieu, le modèle
  croit avoir tout dit. Pour bien faire, ne gardez que les phrases dont l'audio est parti.
- Une écriture ERP déjà partie reste faite : relisez la commande au tour suivant.

### 5.3 Chiffres, unités, dates à l'oral

- « 12 kilos », « 18 euros 50 le kilo », « jeudi 26 », jamais « 18.50 €/kg » ni « 2026-11-26 ».
- Le prompt le demande (`VOICE_RULES`), mais le plus sûr est de **formater dans le code** (4.10) et de donner au
  modèle des valeurs déjà prêtes à dire.
- Les calibres et codes métier (« 30/40 », « T3 ») : dites-les comme le métier les dit (voir [METIER.md](METIER.md)
  et le glossaire de votre `data/context/`).

### 5.4 Relecture et confirmation

- Une commande se crée en brouillon et ne se confirme qu'après accord explicite sur le récapitulatif
  (`BASE_RULES`). À l'oral : récapitulatif **court**, quantités et produits, puis une question fermée.
- « ouais vas-y », « c'est bon », « non attends » : un oui/non fiable est une bonne place pour Jev
  (`is_yes` dans `agent/jev_examples.py`) ; faible confiance = redemander.

### 5.5 Ne jamais lire d'identifiants

`cli_0020`, `prd_…`, `CMD-2026-…` : le modèle les voit dans les résultats d'outils. `VOICE_RULES` interdit les ids
techniques ; pour un numéro de commande utile à l'appelant, dites les derniers chiffres seulement.

### 5.6 Voix et prosodie

- ElevenLabs `eleven_flash_v2_5` (défaut) est le choix rapide. La voix par défaut est une voix prémade
  multilingue : choisissez une voix **française** dans votre bibliothèque ElevenLabs et mettez son id dans
  `TTS_VOICE`.
- Gradium (voix fr-FR, défaut « Armand ») est supporté dans le code, mais vous n'avez pas de clé Gradium (section 7).
- La ponctuation pilote la prosodie : virgules pour les pauses, points pour finir. Évitez les parenthèses, les
  barres obliques, les abréviations.

### 5.7 Ton adapté à l'interlocuteur

Les fiches `data/context/clients/*.md` décrivent chaque client : tempérament, « Comment il/elle parle », tics de
langage (par exemple un patron qui tutoie son commercial depuis dix ans). **Elles ne sont pas dans le prompt par
défaut** (seuls les `*.md` du premier niveau de `data/context/` y vont, TECH.md piège 6). Chargez la fiche de
l'appelant (4.6) et dites au modèle d'adapter registre et tutoiement.

---

<a id="robustesse"></a>
## 6. Robustesse

| Problème | Ce qu'on fait | Où |
|---|---|---|
| Noms mal entendus (« loup » / « bar », noms de clients) | l'**indice STT** contient déjà les noms des clients, produits et alias de l'ERP (`context.terms` Soniox, `keyterm` Deepgram) ; ajoutez vos termes | `services/vocabulary.py`, ou `hint` de `audio_start` |
| Produit ou client ambigu | `search` est flou ; s'il y a plusieurs candidats, demander lequel (`BASE_RULES`) ; Jev `pick_product` donne une confiance | `tools/catalog.py`, `agent/jev_examples.py` |
| Créneau critique douteux (quantité, date, unité) | répéter la valeur et demander confirmation **avant** l'écriture ; « cinq » et « cinquante » se confondent | prompt + outil |
| Rien entendu | le kit renvoie « Rien entendu — réessayez. » ; en VAD, préférez une relance naturelle (« Allô ? Vous m'entendez ? ») | `run_turn` |
| Silence de l'appelant | relance après un délai, puis clôture polie | à ajouter (timer côté session) |
| Erreur fournisseur (401, 429, panne) | message `error` lisible (`provider_error`) ; prévoir un repli : autre modèle, phrase d'excuse pré-enregistrée | `clients/http.py`, `clients/factory.py` |
| Bruit, accents, hésitations | le micro est ouvert avec réduction de bruit et contrôle de gain ; testez vos scénarios avec du bruit de fond réel | `ensureMic` dans `useVoiceSession.ts` |
| Appel coupé en pleine commande | l'historique vit en mémoire, par `sessionId` ; le navigateur se reconnecte avec le même id. La commande brouillon reste dans l'ERP : au retour, la retrouver plutôt qu'en créer une deuxième | `conversations` dans `voice_session.py` |
| Redémarrage du service IA | l'historique vocal est perdu (y compris au rechargement automatique quand vous sauvegardez un fichier de `apps/ai/app`) | TECH.md piège 2 |

---

<a id="fournisseurs"></a>
## 7. Fournisseurs du kit

**Vos clés** : chaque équipe a reçu des clés pour **Soniox** (STT), **ElevenLabs** (TTS), **Anthropic** (LLM) et
**Jev** (décisions). Deepgram, Gradium et OpenAI sont **supportés dans le code** mais **aucune clé n'est fournie**
pour eux : ne comptez pas dessus sans votre propre clé.

| Rôle | Fournisseur | Défaut du kit | Transport | Clé fournie |
|---|---|---|---|---|
| STT | **Soniox** | `stt-rt-v6`, `language_hints: ["fr"]`, termes d'indice | WebSocket temps réel, `transcribe_stream` utilisé en direct, `finalize` au relâchement | oui |
| STT | Deepgram | `nova-3`, `language=fr`, `keyterm` | WebSocket en direct (`transcribe_stream`, fin par `CloseStream`) ; REST en secours | non |
| STT | Gradium | `default` | REST ; webm ré-encapsulé en Ogg (`clients/audio.py`) | non |
| STT | OpenAI | `gpt-4o-mini-transcribe` | REST | non |
| TTS | **ElevenLabs** | `eleven_flash_v2_5`, voix `JBFqnCBsd6RMkjVDRZzb`, `language_code=fr` | REST `/stream`, mp3 | oui |
| TTS | Gradium | `default`, voix fr-FR `F7Iib4MAyHIRed0x` | REST NDJSON, PCM → mp3 (`Mp3Encoder`) | non |
| TTS | OpenAI | `gpt-4o-mini-tts`, `alloy` | REST, mp3 | non |
| LLM | **Anthropic** | `claude-sonnet-5-5`, `LLM_EFFORT=low` | SSE | oui |
| Décision | **Jev** | `jev-latest` | REST | oui |

**Configuration** (`.env`, puis `make restart`) : `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY`, `STT_LANGUAGE` ;
`TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`, `TTS_API_KEY`, `TTS_LANGUAGE` ; `LLM_PROVIDER`, `LLM_MODEL`,
`LLM_API_KEY`, `LLM_EFFORT` ; `JEV_API_KEY`. Détail : [apps/ai/README.md](apps/ai/README.md#environment) et
[SETUP.md](SETUP.md#changer-de-modèle-ou-de-voix).

**Formats audio** :

- Entrée : le navigateur enregistre en `audio/webm;codecs=opus` (Safari : `audio/mp4`). Soniox l'accepte tel quel
  (`audio_format: "auto"`, pas le mp4). Testez sur Chrome.
- Sortie : **tous les TTS rendent `audio/mpeg`** (mp3) : le lecteur concatène les phrases d'un tour en un segment.
  Un nouveau TTS qui rend du PCM doit passer par `audio.Mp3Encoder`.
- Mock : `audio/x-mock-wav`, le navigateur lit le texte avec `speechSynthesis` ; les latences mesurées en mock ne
  disent rien des vrais fournisseurs.

---

<a id="plan"></a>
## 8. Plan d'attaque pour 24 h

### Budget de latence

Cible : **moins de 1,5 s** de la fin de parole au premier son (le vert de la page Voix). Ce tableau est un budget
à **vérifier** chez vous, pas une mesure : seule la colonne « Aujourd'hui » est mesurée, et ces mesures datent
d'avant la transcription en direct.

| Étape | Aujourd'hui (mesuré) | Cible (ordre de grandeur) | Techniques |
|---|---|---|---|
| Endpointing | 0 (push-to-talk) | 0 en push-to-talk ; 300–800 ms en VAD | 4.2 |
| STT après fin de parole | 3,4–4,9 s **avant la transcription en direct** ; maintenant : texte final quelques centaines de ms après le relâchement (à remesurer) | ≈ 0,2–0,5 s | 4.1 (fait), vocabulaire |
| Premier son de l'agent après le transcript | ≈ 4,2–4,4 s (LLM + outil) | ≈ 0,5–0,8 s | filler 4.7, cache 4.4, modèle 4.5, préchargement 4.6 |
| TTS premier octet | 170–370 ms (chaud), 1,9 s (froid) | ≈ 0,2–0,3 s, jamais froid | 4.9 |
| **Total** | **8,4 s (commande), 9,6 s (voix)**, avant la transcription en direct | **< 1,5 s** | |

Lecture : le STT est déjà en flux ; avec une phrase d'attente prononcée **avant** les outils, le premier son ne
dépend plus du temps des outils. La réponse utile arrive ensuite ; réduisez-la avec 4.4 à 4.6.

### Ordre conseillé

1. **Mesurer d'abord** (H3–H8) : vos 5–10 scénarios, vraies clés, notez `sttMs`, `llmFirstTokenMs`,
   `ttsFirstByteMs`, `totalMs`, `perceivedMs` dans `DECISIONS.md`.
2. **Connexions chaudes** (4.9) et **filler** (4.7) : une heure, gain visible tout de suite.
3. **Affiner le STT** (4.1, déjà en flux) : enrichir le vocabulaire (`services/vocabulary.py` : contacts, panier
   habituel, termes métier), passer Deepgram à `Finalize` si vous l'utilisez, puis démarrer le LLM sur les partiels
   stables (4.3).
4. **Préchargement du client + outil composite** (4.6), **vérification du cache** (4.4).
5. **Modèle / routage** (4.5) : seulement si vos scénarios restent justes.
6. **VAD** (4.2) s'il reste du temps ; gardez Espace en secours pour la démo live.
7. Après **chaque** changement : rejouez les scénarios, comparez les chiffres et le taux de réussite. Plus rapide
   mais faux ne gagne pas.

### Prouver en démo

Dans `DECISIONS.md`, un tableau avant/après par technique :

| Technique | sttMs | llmFirstTokenMs | ttsFirstByteMs | totalMs | perceivedMs | scénarios réussis |
|---|---|---|---|---|---|---|
| kit d'origine | | | | | | |
| + … | | | | | | |

Donnez la médiane et le pire cas, dites ce que mesure votre t0 (relâchement ou fin de voix détectée) et si le
premier son est un filler. En live, gardez la page Voix ouverte : les puces **Total** et **Perçu** parlent d'elles-mêmes.
