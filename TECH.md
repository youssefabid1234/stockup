# TECH.md — le guide technique du kit

Comment **tout** fonctionne, et comment l'étendre. Pour les ingénieurs et leurs agents de code. Chaque nom, chemin et
route cité ici existe dans le code ; les références `fichier:ligne` pointent vers les extraits.

Ce que ce guide ne répète pas : l'installation ([SETUP.md](SETUP.md)), le défi ([BRIEF.md](BRIEF.md)), le métier
([METIER.md](METIER.md)), le fonctionnement fonctionnel de l'ERP, ses pages et ses règles ([ERP.md](ERP.md)), la
configuration résumée ([README.md](README.md)), les règles pour agents de code ([AGENTS.md](AGENTS.md)), le design
system ([DESIGN.md](DESIGN.md)), le résumé du service IA ([apps/ai/README.md](apps/ai/README.md)).

## Sommaire

1. [Vue d'ensemble : 3 services, 4 parcours](#vue-ensemble)
2. [Backend ERP](#backend)
3. [Référence des endpoints](#endpoints)
4. [Service IA](#service-ia)
5. [Les outils (`@tool`) en détail](#outils)
6. [Frontend](#frontend)
7. [Données](#donnees)
8. [Tests et qualité](#tests)
9. [Pièges connus et limites](#pieges)

## Je veux… → où regarder

| Je veux… | Section | Fichiers |
|---|---|---|
| comprendre un appel vocal de bout en bout | [1.3](#parcours-voix) | `apps/web/src/features/assistant/useVoiceSession.ts`, `apps/ai/app/services/voice_session.py`, `apps/ai/app/agent/loop.py` |
| ajouter un outil à l'agent | [5](#outils) | `apps/ai/app/tools/registry.py`, `apps/ai/app/tools/*.py`, `apps/ai/app/tools/__init__.py` |
| ajouter un outil composite (plusieurs appels ERP) | [5.4](#outil-composite) | `apps/ai/app/tools/catalog.py` (modèle), `apps/ai/app/tools/erp.py` |
| changer de modèle, de STT ou de TTS | [4.1](#config-ia) | `.env`, `apps/ai/app/clients/factory.py` |
| ajouter un fournisseur LLM / STT / TTS | [4.2](#clients) | `apps/ai/app/clients/base.py`, `apps/ai/app/clients/factory.py` |
| transcrire pendant que l'appelant parle | [Transcription en direct](#stt-direct) | `apps/ai/app/services/utterance.py`, `apps/ai/app/services/vocabulary.py`, `apps/ai/app/clients/soniox.py` |
| réduire la latence | [4.5](#latence), [9](#pieges) | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/*`, `apps/ai/app/agent/prompts.py`, `apps/ai/app/tools/erp.py` |
| changer ce que lit le modèle (prompt) | [4.3](#prompts) | `apps/ai/app/agent/prompts.py`, `DATA_DIR/context/*.md` |
| modifier la boucle de l'agent | [4.4](#boucle) | `apps/ai/app/agent/loop.py` |
| ajouter un endpoint à l'ERP | [2.6](#ajouter-endpoint) | `apps/backend/app/schemas/inputs.py`, `services/`, `routers/`, `packages/shared/src/`, `apps/web/src/lib/api.ts` |
| changer une règle métier (prix, stock, crédit) | [2](#backend) | `apps/backend/app/services/*.py` |
| modifier ou ajouter une page | [6.6](#ajouter-page) | `apps/web/src/pages/`, `apps/web/src/app/routes.tsx`, `apps/web/src/app/nav.ts` |
| que l'UI se mette à jour quand l'agent écrit | [6.4](#live) | `apps/web/src/lib/queries.ts` (`INVALIDATE`) |
| modifier le chat, la page Voix ou ⌥Espace | [6.5](#surfaces-ia) | `apps/web/src/features/assistant/`, `apps/web/src/features/voice-command/`, `apps/web/src/pages/voice/` |
| tester un outil sans l'UI | [8](#tester-sans-ui) | `make chat`, `curl /chat`, `apps/ai/tests/` |
| remettre les données à zéro | [7](#donnees) | `make reset` → `apps/backend/app/core/datapack.py` |
| utiliser Jev (décisions rapides) | [4.7](#jev) | `apps/ai/app/clients/jev.py`, `apps/ai/app/agent/jev_examples.py` |

Chaque section suit le même plan : **Ce que c'est** (2–3 lignes), **Fichiers clés**, **Comment ça marche**,
**Étendre**, **Pièges**.

---

<a id="vue-ensemble"></a>
## 1. Vue d'ensemble : 3 services, 4 parcours

### Ce que c'est

Trois process : l'ERP (`apps/backend`, port 4000), le service IA (`apps/ai`, port 4100) et le web (`apps/web`,
port 5173). Le service IA est **un client HTTP de l'ERP comme un autre** : toute règle métier vit dans l'ERP.

### Fichiers clés

- `docker-compose.yml` : les 3 services, les volumes (code monté en direct, `DATA_DIR` en lecture seule, base dans le volume `erp-db`).
- `scripts/dev.sh` : la même chose sans Docker (`uvicorn --reload` ×2 + `vite`).
- `apps/web/vite.config.ts:24-29` : le proxy `/api` → ERP, `/ai` → IA, `/ai/voice` → WebSocket IA.
- `Makefile` : toutes les commandes (`make help`).

### Comment ça marche

```
 navigateur :5173 (React)
   │  /api/*  (fetch, x-actor: user)            ┌──────────────────────────────────────┐
   ├──────────────────────────────────────────▶ │ ERP  apps/backend  :4000             │
   │  /api/events/stream (SSE, ActivityEvent) ◀─┤ routers → services → crud → db       │
   │                                            │ mémoire + SQLite (write-through)     │
   │  /ai/chat (SSE)   /ai/command (SSE)        └──────────────────────────────────────┘
   │  /ai/voice (WebSocket)                                   ▲ HTTP /api/*
   ▼                                                          │ x-actor: ai_chat | voice_agent
 ┌─────────────────────────────────────────┐                  │
 │ IA  apps/ai  :4100                      │──────────────────┘ (chaque outil = 1+ appel HTTP)
 │ routers → services → agent/loop → tools │
 │ clients/ : LLM · STT · TTS · Jev        │────▶ fournisseurs (OpenAI, Anthropic, Gemini,
 └─────────────────────────────────────────┘      Soniox, Deepgram, ElevenLabs, Gradium) ou mocks
```

Ports et URL : `WEB_PORT`, `API_PORT`, `AI_PORT` dans `.env`. Dans Docker, l'IA joint l'ERP en
`http://backend:4000` et Vite proxifie vers `backend` / `ai` (`VITE_API_TARGET`, `VITE_AI_TARGET`). En local,
`ERP_API_URL=http://localhost:4000`.

<a id="parcours-clic"></a>
#### 1.1 Un clic dans l'UI (ex. « Confirmer » une commande)

```
Bouton → useApiMutation(api.orders.confirm)            apps/web/src/lib/queries.ts:205
  → fetch POST /api/orders/{id}/confirm                 apps/web/src/lib/api.ts:47 (x-actor: user, x-actor-name: Moi)
  → Vite proxy → ERP router confirm_order               apps/backend/app/routers/orders.py:58
  → get_ctx() lit x-actor → Ctx(actor="user")           apps/backend/app/dependencies.py:20
  → services.orders.confirm_order (@transactional)      apps/backend/app/services/orders.py:273
      crud.orders.put(...)  → mémoire + SQLite
      log_event(ctx, "order.confirmed", …)              apps/backend/app/core/activity.py:71
  → COMMIT → bus.publish(ev) → SSE "activity" à tous les onglets
  → réponse OrderDetail (avec warnings) → toast + invalidations react-query
```

<a id="parcours-chat"></a>
#### 1.2 Un message dans l'assistant (⌘J)

```
chat.send(text)                                       apps/web/src/features/assistant/chat-store.ts:67
  → POST /ai/chat {messages: historique complet + nouveau, mode:"chat"}   ai-client.ts:38
  → routers/chat.py:16 → run_agent(messages, mode="chat")                 apps/ai/app/agent/loop.py:41
      build_system_prompt("chat")  (règles + date métier + DATA_DIR/context/*.md)
      LLM.stream → text… / tool_call…
      outils en parallèle → ErpClient("ai_chat") → /api/*                 apps/ai/app/tools/erp.py:44
      … jusqu'à une réponse sans appel d'outil (max AGENT_MAX_STEPS=8)
  ← SSE : text · tool_call · tool_result · done | error   (une ligne data: JSON par événement)
  → TurnRecorder reconstruit les messages assistant/tool  ai-client.ts:82
  → l'historique reste côté navigateur et est renvoyé en entier au tour suivant
```

<a id="parcours-voix"></a>
#### 1.3 Un tour vocal push-to-talk (page Voix) de bout en bout

```
NAVIGATEUR (useVoiceSession.ts)                SERVICE IA (voice_session.py)                         ERP
ws = new WebSocket(/ai/voice)          :192
onopen → {type:"start", sessionId, actorName:"Agent vocal"} ──▶ open() → ReadyMessage {sessionId, stt, tts, llm}
Espace enfoncé:
  MediaRecorder(webm/opus).start(100)
  {type:"audio_start", mime}           ──▶ interrupt() (barge-in), recording = Utterance(...)  → flux STT ouvert
  frames binaires toutes les 100 ms    ──▶ utterance.feed(frame) → envoyée au STT tout de suite
                                      ◀── transcript {final:false, text, stable}  (texte en direct, gris/italique)
Espace relâché:
  {type:"audio_end"}                   ──▶ start_turn(utterance) → asyncio.Task run_turn()
                                           1. STT: await utterance.text()  (finalize : seuls les derniers mots)
                                      ◀── transcript {track:"caller", text, final:true}
                                           2. run_agent(working, mode="voice")                   :190
                                      ◀── agent_text {delta}  (chaque delta)
                                           Speaker.push(delta) → phrase finie ? → file TTS        :241
                                      ◀── agent_tool {name, args}   …outil → HTTP ──────────────▶ /api/*
                                      ◀── agent_tool {name, ok, ms}                 ◀── JSON ── (log_event → SSE)
                                           worker TTS : synthesize(phrase) en streaming          :273
                                      ◀── agent_audio_start {mime}  (une fois par tour)
                                      ◀── octets audio mp3 (binaire), phrase après phrase
                                           3. speaker.finish() → reste du buffer                 :208
                                      ◀── agent_audio_end
                                      ◀── agent_done {text, timings}
SegmentPlayer (MediaSource) joue le mp3 dès le premier octet ; mime mock → speechSynthesis fr-FR
En parallèle, l'onglet reçoit les ActivityEvent par /api/events/stream → colonne de droite, lignes violettes.
```

`timings` (`apps/ai/app/schemas/chat.py:55`) : `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`,
`totalMs` = fin de parole → premier octet audio de l'agent. Le navigateur ajoute `perceivedMs` (relâche → audio joué).

**Barge-in** : un nouveau `audio_start` ou `text` pendant un tour appelle `interrupt()`
(`voice_session.py:158`) : la tâche est annulée, le TTS en cours est fermé (`aclosing`), ce qui a été entendu et
dit est gardé dans l'historique avec « … ».

<a id="parcours-commande"></a>
#### 1.4 Une commande ⌥Espace

```
⌥Espace maintenu (VoiceCommand.tsx:28) → MediaRecorder (trames de 100 ms) → WS /ai/voice/command?speak=1
  ← transcript {final:false} pendant la parole (texte en direct dans le HUD) → relâché → audio_end
  (commande tapée : POST /ai/command?speak=1, JSON {text}, réponse en SSE)
  → services/command.py:73 run_command
      STT → TranscriptEvent
      run_agent([un seul message user], mode="command")   (aucun historique)
      ToolResultEvent → entity_of(result) mémorise la dernière entité vue
      si la phrase contient montre/affiche/ouvre/voir… → NavigateEvent {path:"/products/prd_…"}   :40, :121
      speak=1 → TTS de toute la réponse → SpeechEvent (base64)
      DoneEvent {timings}
  ← SSE : transcript · text · tool_call · tool_result · navigate? · speech? · done | error
  → le web navigue (sauf sur /voice) et joue l'audio
```

<a id="activite"></a>
#### 1.5 Le flux d'activité et `x-actor`

- Chaque écriture ERP appelle `log_event(ctx, type, entity, entity_id, summary)` dans le service
  (`core/activity.py:71`). L'événement est publié sur le bus **après le COMMIT** (`on_commit`, `core/db.py:153`).
- `GET /api/events/stream` (`routers/system.py:54`) : `event: ready` une fois, puis `event: activity` + JSON par
  écriture, `event: ping` toutes les 15 s.
- L'acteur vient de l'en-tête `x-actor` (`user` | `ai_chat` | `voice_agent`, sinon `user`) et du nom optionnel
  `x-actor-name` (URI-encodé) : `dependencies.py:20-26`. Le web envoie `user`/« Moi » ; les outils de l'IA envoient
  `ai_chat` (mode chat) ou `voice_agent` (modes voice et command) : `agent/loop.py:51-52`.
- Côté web, `useActivityStream()` (monté une fois dans `AppShell`) invalide les requêtes de l'entité touchée et
  fait clignoter la ligne en violet (`lib/queries.ts:259-299`).

### Pièges

- Le service IA n'a pas de base de données : tout ce qu'il « sait » vient de l'ERP ou du prompt.
- Les écritures de l'agent ne sont **pas** annulées par un barge-in : un appel HTTP déjà parti reste fait.

---

<a id="backend"></a>
## 2. Backend ERP (`apps/backend/app`)

### Ce que c'est

Une API FastAPI JSON sous `/api`. Les données sont des documents JSON (camelCase) gardés en mémoire et écrits en
même temps dans SQLite. Les règles métier sont dans `services/`.

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `main.py` | app FastAPI, chargement au démarrage (`lifespan`, `:44`), liste des routers (`:72`), format d'erreur (`:97-154`), OpenAPI nettoyé (`:160-196`) |
| `dependencies.py` | `get_ctx` / `CtxDep` (acteur), `data(body)`, `iso_date_query`, `ERROR_RESPONSES` |
| `core/listing.py` | listes paginées : `ListDep` (`limit`, `offset`, `sort`, `order`, `envelope`), `apply_sort`, `respond`, `Page[T]` ([Pagination](#pagination)) |
| `core/config.py` | `DATA_DIR`, `SEED_DIR`, `DB_PATH`, `API_PORT` (lit le `.env` racine) |
| `core/db.py` | `JsonTable`, `transaction()` / `@transactional`, `on_commit`, `get_meta`, séquences d'ids, `@per_data_version` (cache d'agrégats invalidé à chaque écriture) |
| `core/datapack.py` | lecture du pack (`DATA_DIR/seed/*.json`), `reset_from_pack()` |
| `core/activity.py` | `Ctx`, `today()` / `now()` (horloge métier), `EventBus`, `log_event`, `list_events` |
| `core/errors.py` | `HttpError`, `not_found`, `bad_request`, `conflict`, `validation_error` |
| `crud/__init__.py`, `crud/base.py` | un `CRUDBase` par table (`crud.orders`, `crud.clients`…), `PACK` (fichier seed → table) |
| `schemas/domain.py` · `views.py` · `inputs.py` | entités stockées · réponses calculées · corps de requête |
| `routers/*.py` | routes minces, une par ressource |
| `services/*.py` | règles métier, une par domaine |

### Comment ça marche

**Couches** — chaque couche n'appelle que celle du dessous :

```
routers/orders.py      parse la requête (Query alias camelCase, body Input), injecte ctx: CtxDep, déclare response_model
   ↓
services/orders.py     règles métier, @transactional, log_event(...) ; renvoie des dicts (Doc)
   ↓
crud (crud.orders)     get / require (404) / all / filter / put / delete / next_id / next_number
   ↓
core/db.py JsonTable   rows: dict en mémoire  +  SQLite (id TEXT PRIMARY KEY, data TEXT JSON)
```

Exemple réel, création de commande :

```python
# apps/backend/app/routers/orders.py:31-34
@router.post("", response_model=OrderDetail, status_code=201)
async def create_order(body: OrderInput, ctx: CtxDep):
    """Draft order; line prices resolved (client price > rules > list price)."""
    return orders.create_order(ctx, body.data())
```

```python
# apps/backend/app/services/orders.py:181-201 (extrait)
@transactional
def create_order(ctx: Ctx, input: Doc) -> Doc:
    client = crud.clients.require(input["clientId"])
    t = today()
    order = {
        "id": crud.orders.next_id("ord_"),
        "number": crud.orders.next_number("CMD", t[:4]),
        ...
    }
    saved = _save(order)
    log_event(ctx, "order.created", "order", order["id"], f"Commande {order['number']} créée pour …")
    return order_detail(saved["id"])
```

**Tables en mémoire + SQLite write-through** (`core/db.py:36-68`). Au démarrage, `lifespan` (`main.py:44`) charge
toutes les tables (`load_all`) ou, si la base est vide, le pack de données (`reset_from_pack`). Toutes les lectures
touchent la mémoire ; `put` / `remove` écrivent dans la mémoire **et** dans SQLite. Base : `apps/backend/data/erp.db`
en local, `/db/erp.db` (volume `erp-db`) dans Docker.

**`@transactional`** (`core/db.py:117-150`) : la fonction tourne dans une transaction SQLite ; les blocs imbriqués
rejoignent la plus externe. En cas d'exception : `ROLLBACK` **et** rechargement de la mémoire depuis le disque
(`load_all`), pour que les deux ne divergent jamais. Les callbacks `on_commit` (diffusion SSE) ne partent qu'au
COMMIT. Toute fonction de service qui écrit prend `ctx` en premier et porte `@transactional`.

**Ids et numéros** : `crud.X.next_id("ord_")` → `ord_000124` (suit le plus grand existant) ;
`next_number("CMD", "2026")` → `CMD-2026-000124` (`crud/base.py:62-74`). Les ids de lignes (`lin_…`, `pol_…`) sont
aléatoires.

**Horloge métier** (`core/activity.py:33-41`) : `today()` = `meta.today` du pack, jamais `date.today()` ;
`now()` = ce jour-là + l'heure réelle. Tout « en retard », « demain », « 30 derniers jours » se calcule dessus.

**Schémas** (`schemas/base.py`) : `Schema` sérialise en camelCase sans les champs `None` ; `Input` (corps de
requête) est **strict** (pas de `"5"` → 5) et ignore les clés inconnues ; `body.data()` → dict camelCase pour le
service. Les services manipulent des dicts camelCase, pas des objets Pydantic.

**Erreurs** : toujours `{"error": {"code", "message"}}`.

| Cas | Statut | `code` | D'où |
|---|---|---|---|
| corps invalide (Pydantic) | 400 | `validation_error` (`"champ: message; …"`) ou `invalid_json` | `main.py:132` |
| règle métier (`bad_request`) | 400 | au choix, ex. `product_inactive`, `invalid_qty` | `core/errors.py:17` |
| entité absente (`crud.X.require`) | 404 | `not_found` (« Commande introuvable : ord_1 ») | `crud/base.py:43` |
| route inconnue / mauvaise méthode | 404 | `not_found` | `main.py:144` |
| transition interdite (`conflict`) | 409 | ex. `empty_order`, `invalid_transition` | `core/errors.py:21` |
| exception non prévue | 500 | `internal_error` | `main.py:151` |

**Pack de données et reset** : `make reset` = `POST /api/admin/reset` (`routers/system.py:80`) → `reset_from_pack()`
(`core/datapack.py:49`) : vide toutes les tables et le journal, recharge `DATA_DIR/seed/*.json`, vide les séquences.
Sans `DATA_DIR/seed/meta.json`, un petit fixture intégré (`core/dev_fixture.json`) est chargé.

<a id="ajouter-endpoint"></a>
### Étendre : ajouter un endpoint de bout en bout (2.6)

Exemple travaillé : **« refaire la même commande »** (`POST /api/orders/{id}/repeat`), utile au téléphone
(« comme la dernière fois »).

1. **Schéma d'entrée** — `apps/backend/app/schemas/inputs.py` (à côté de `OrderPatch`) :

   ```python
   class RepeatOrderInput(Input):
       delivery_date: IsoDateStr | None = None  # défaut : prochain jour de livraison du client
   ```

   Si la réponse a une forme nouvelle, ajoutez un modèle dans `schemas/views.py` ; ici on réutilise `OrderDetail`.

2. **Service** — `apps/backend/app/services/orders.py` (réutilise `create_order`, qui recalcule les prix du jour,
   journalise `order.created` et rejoint la transaction) :

   ```python
   @transactional
   def repeat_order(ctx: Ctx, id: str, input: Doc) -> Doc:
       src = crud.orders.require(id)
       lines = [
           {"productId": l["productId"], "qty": l["qty"], **({"note": l["note"]} if l.get("note") else {})}
           for l in src["lines"]
       ]
       return create_order(ctx, {
           "clientId": src["clientId"],
           "deliveryDate": input.get("deliveryDate"),
           "lines": lines,
           "note": f"Reprise de {src['number']}",
       })
   ```

3. **Route** — `apps/backend/app/routers/orders.py` (importez `RepeatOrderInput`) :

   ```python
   @router.post("/{id}/repeat", response_model=OrderDetail, status_code=201)
   async def repeat_order(id: str, ctx: CtxDep, body: RepeatOrderInput | None = None):
       """New draft with the same lines as order `id` (prices resolved today)."""
       return orders.repeat_order(ctx, id, data(body))
   ```

   Un nouveau fichier de router doit être ajouté à la liste de `main.py:72-91`.

4. **Vérifier** : uvicorn recharge seul. `curl -s -X POST localhost:4000/api/orders/ord_000001/repeat -H 'content-type: application/json' -H 'x-actor: voice_agent' -d '{}'`,
   puis http://localhost:4000/docs. La ligne apparaît en violet dans **Activité**.

5. **Type TypeScript** — les types du web sont **écrits à la main** dans `packages/shared/src/`
   (`domain.ts`, `api.ts`, `ai.ts`). Nouveau corps ou nouvelle réponse → ajoutez l'interface correspondante
   (ici rien : `OrderDetail` existe). `make types` génère aussi `packages/shared/src/generated/` depuis
   `/openapi.json`, mais ce dossier n'est pas exporté par `index.ts` : il sert de référence (voir [Pièges](#pieges)).

6. **Appel web** — `apps/web/src/lib/api.ts`, objet `orders` (`:137`) :

   ```ts
   repeat: (id: Id, body?: { deliveryDate?: IsoDate }) => post<OrderDetail>(`/orders/${id}/repeat`, body),
   ```

   puis dans une page : `useApiMutation(api.orders.repeat, { success: "Commande dupliquée", invalidate: [qk.orders.all] })`.

7. **Outil pour l'agent** (optionnel) : voir [5.3](#ajouter-outil).

### Pièges

- Un seul process : la base en mémoire n'est pas partagée entre workers. Ne lancez pas uvicorn avec `--workers`.
- Modifier `erp.db` à la main pendant que l'ERP tourne désynchronise la mémoire : redémarrez le backend.
- Les routes sont `async` mais les services sont synchrones : un calcul long bloque toute l'API (y compris le SSE).
- Ne pas oublier `log_event` dans un service qui écrit : sans lui, l'UI ne se met pas à jour en direct.
- Les paramètres de requête arrivent en `str` et sont convertis dans le router (`int_param`, `js_number`) ; listes =
  chaînes séparées par des virgules (`status=draft,confirmed`). `limit` / `offset` / `sort` / `order` / `envelope` :
  ajoutez `lq: ListDep` à la route et renvoyez `respond(rows, lq, view, extras)` ([Pagination](#pagination)).
- Une nouvelle liste ne doit jamais construire les vues de toutes les lignes : filtrer → trier → `respond` (qui découpe
  la page puis appelle `view`). Un agrégat sur toute la table ? `@per_data_version` (jamais muter la valeur en cache).

---

<a id="endpoints"></a>
## 3. Référence des endpoints

### Ce que c'est

Les 80 routes de l'ERP (générées depuis `http://localhost:4000/openapi.json`) et les 7 routes du service IA.
Essai en direct : http://localhost:4000/docs et http://localhost:4100/docs. Exemples curl et sémantique métier :
[ERP.md §7 et §8](ERP.md#8-aide-mémoire-de-lapi).

### Fichiers clés

`apps/backend/app/routers/*.py`, `apps/ai/app/routers/*.py`, `apps/ai/app/schemas/*.py`.

### Comment ça marche : ERP (`/api`, port 4000)

Toutes les écritures acceptent `x-actor` et `x-actor-name`. Réponse = modèle de `schemas/views.py` ou `domain.py`.

<a id="pagination"></a>
**Pagination.** Toutes les listes sont paginées, filtrées et triées **côté serveur** (`app/core/listing.py`), car les
packs de données vont jusqu'à ~48 000 commandes, ~25 000 factures et ~420 000 mouvements de stock par entreprise.
Paramètres communs (marqués « + liste » ci-dessous) : `limit` (défaut **100**, max **500**), `offset` (défaut 0),
`sort` (un champ triable de la route, listé dans sa description `/docs` et dans `packages/shared/src/api.ts`),
`order` (`asc` | `desc`). Format de réponse :

- **par défaut, un tableau JSON** (la page demandée) : les outils IA et les scripts existants fonctionnent sans changement,
  mais un tableau est **tronqué à `limit`** — passez `limit=500` ou `envelope=1` pour savoir combien de lignes existent ;
- **avec `envelope=1`** (ce qu'envoie l'UI) : `{items, total, limit, offset, …extras}` — `total` = lignes qui
  correspondent aux filtres, et des extras calculés sur **tout** l'ensemble filtré (pas seulement la page) : `counts`
  (lignes par statut / onglet / catégorie **en ignorant ce filtre-là** → badges d'onglets), `sums` (totaux du pied de
  tableau), `sumsByStatus` (factures), `countsByType` (historique), `countsBySource` (contexte), `facets` (options
  des menus de filtre). Type TS : `Page<T>` dans `packages/shared/src/api.ts`.

Côté services : on filtre les documents bruts, on trie avec une clé simple, on découpe la page, et **seulement ensuite**
on construit les vues (`order_summary`, `invoice_summary`…) des lignes de la page. Les agrégats coûteux (niveaux de
stock, encours par client, listes pré-triées, index FEFO, tableau de bord) sont mis en cache par **version des données**
(`@per_data_version` dans `core/db.py`, invalidé à chaque écriture) ; les mouvements de stock (ajout seul) ont un index
incrémental. Côté web : `useServerList` (page + tri dans l'URL) → hook `use…Page` → `<DataTable server={{ list, total }}>`
avec des colonnes `sortKey` (voir `pages/clients/index.tsx`, la page de référence). Exceptions bornées par nature, non
paginées : `GET /api/receivables` (une ligne par client), `/api/prices/grid` (une ligne par produit), `/api/tags`.

**Système** (`routers/system.py`)

| Méthode | Chemin | Rôle | Paramètres | Réponse |
|---|---|---|---|---|
| GET | `/api/health` | vivant + date métier | — | `Health` |
| GET | `/api/meta` | entreprise, `today`, `trade`, `region` (barre latérale) | — | `Meta` |
| GET | `/api/categories` | catégories produit de l'entreprise (`seed/categories.json`) | — | `Category[]` (`{id, label}`) |
| GET | `/api/dashboard` | KPI de l'accueil | — | `Dashboard` |
| GET | `/api/search` | recherche floue (accents, alias, mots parasites) | `q`, `types`, `limit` (défaut 20, max 500) | `SearchResult[]` |
| GET | `/api/events` | journal d'activité, récent d'abord | `actor` (`ai`, `user,system`…), `entity` + liste (défaut `limit` 50) ; enveloppe : `counts` {ai, user} | `ActivityEvent[]` |
| GET | `/api/events/stream` | journal en direct (SSE) | — | `text/event-stream` |
| POST | `/api/admin/reset` | recharge le pack de données | — | `Ok` |

**Clients** (`routers/clients.py`, `routers/client_events.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/clients` | liste avec KPI | `q`, `type`, `zone`, `status`, `tag` + liste ; tri `name` `code` `type` `tags` `zone` `rep` `city` `outstanding` `overdue` `last` `revenue30d` `status` ; enveloppe : `counts` par statut, `facets.zone`, `facets.salesRep` | `ClientSummary[]` |
| POST | `/api/clients` | créer | `ClientInput` | `Client` (201) |
| GET | `/api/clients/{id}` | fiche complète (20 dernières commandes, ≤ 100 factures ouvertes + `openInvoiceCount`) | — | `ClientDetail` |
| PATCH | `/api/clients/{id}` | modifier | `ClientPatch` | `Client` |
| GET | `/api/clients/{id}/usual` | panier habituel (60 j) | — | `UsualBasketLine[]` |
| GET | `/api/clients/{id}/events` | historique du client, récent d'abord (`sort=open` : dossiers ouverts d'abord) | `type`, `status`, `q` + liste | `ClientEventSummary[]` |
| POST | `/api/clients/{id}/events` | ajouter un événement | `ClientEventInput` | `ClientEvent` (201) |
| PUT | `/api/clients/{id}/prices/{product_id}` | fixer un prix négocié | `ClientPriceInput` | `ClientPrice` |
| DELETE | `/api/clients/{id}/prices/{product_id}` | retirer le prix négocié | — | `Ok` |
| POST | `/api/clients/{id}/notes` | ajouter une note | `ClientNoteInput` | `Client` (201) |
| GET | `/api/client-events` | historique tous clients | `type`, `status`, `clientId`, `q`, `from`, `to` + liste ; enveloppe : `counts` par statut, `countsByType`, `sums.amount` | `ClientEventSummary[]` |
| PATCH | `/api/client-events/{id}` | modifier, résoudre | `ClientEventPatch` | `ClientEvent` |

**Catalogue, fournisseurs, stock** (`routers/products.py`, `suppliers.py`, `supplier_events.py`, `stock.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/products` | catalogue avec stock | `q`, `category`, `tag`, `active` + liste ; tri `name` `sku` `category` `tags` `price` `cost` `margin` `available` `expiry` ; enveloppe : `counts` par catégorie | `ProductSummary[]` |
| GET | `/api/products/{id}` | fiche, lots, prix fournisseurs, mouvements, ventes 30 j | — | `ProductDetail` |
| PATCH | `/api/products/{id}` | prix, coût, tags… | `ProductPatch` | `Product` |
| GET | `/api/products/{id}/alternatives` | remplaçants en stock | — | `ProductSummary[]` |
| GET | `/api/suppliers` | liste | `q`, `category`, `tag` + liste ; tri `name` `city` `tags` `lead` `terms` `min` | `Supplier[]` |
| GET | `/api/suppliers/{id}` | fiche (60 dernières commandes d'achat + `purchaseStats` sur toutes) | — | `SupplierDetail` |
| PATCH | `/api/suppliers/{id}` | modifier | `SupplierPatch` | `Supplier` |
| GET | `/api/suppliers/{id}/usual` | achats habituels (60 j) | — | `UsualBasketLine[]` |
| GET | `/api/suppliers/{id}/events` | historique fournisseur (`sort=open` : ouverts d'abord) | `type`, `status`, `q` + liste | `SupplierEventSummary[]` |
| POST | `/api/suppliers/{id}/events` | ajouter un événement | `SupplierEventInput` | `SupplierEvent` (201) |
| GET | `/api/supplier-events` | historique tous fournisseurs | `type`, `status`, `supplierId`, `q`, `from`, `to` + liste ; enveloppe comme `/api/client-events` | `SupplierEventSummary[]` |
| PATCH | `/api/supplier-events/{id}` | modifier, résoudre | `SupplierEventPatch` | `SupplierEvent` |
| GET | `/api/stock` | niveaux de stock | `q`, `tab` (`out` \| `low` \| `expiring`) + liste ; tri `product` `sku` `category` `onHand` `reserved` `available` `incoming` `expiry` `state` ; enveloppe : `counts` par onglet | `StockItem[]` |
| GET | `/api/stock/movements` | mouvements, récent d'abord (`order=asc` : anciens d'abord) | `productId` + liste | `StockMovement[]` |
| POST | `/api/stock/adjust` | ajustement, perte | `StockAdjustInput` | `StockLevel` |

**Ventes** (`routers/orders.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/orders` | liste, livraison la plus récente d'abord | `status`, `clientId`, `date`, `q`, `source`, `ids` + liste ; tri `number` `client` `date` `createdAt` `lines` `total` `status` ; enveloppe : `counts` par statut, `sums.totalHt` | `OrderSummary[]` |
| POST | `/api/orders` | brouillon | `OrderInput` | `OrderDetail` (201) |
| GET | `/api/orders/{id}` | détail + alertes | — | `OrderDetail` |
| PATCH | `/api/orders/{id}` | date, note | `OrderPatch` | `OrderDetail` |
| POST | `/api/orders/{id}/lines` | ajouter une ligne | `OrderLineInput` | `OrderDetail` (201) |
| PATCH | `/api/orders/{id}/lines/{line_id}` | modifier une ligne | `OrderLinePatch` | `OrderDetail` |
| DELETE | `/api/orders/{id}/lines/{line_id}` | retirer une ligne | — | `OrderDetail` |
| POST | `/api/orders/{id}/confirm` | confirmer, réserver, affecter à une tournée | — | `OrderDetail` |
| POST | `/api/orders/{id}/prepare` | préparer (poids réels) | `PrepareInput` | `OrderDetail` |
| POST | `/api/orders/{id}/deliver` | livrer (FEFO) | — | `OrderDetail` |
| POST | `/api/orders/{id}/invoice` | facturer | — | `InvoiceDetail` (201) |
| POST | `/api/orders/{id}/cancel` | annuler | — | `OrderDetail` |

**Achats** (`routers/purchase_orders.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/purchase-orders` | liste, récente d'abord | `status`, `supplierId`, `date` (attendue), `q` + liste ; tri `number` `supplier` `date` `createdAt` `lines` `total` `status` ; enveloppe : `counts`, `sums.totalHt` | `PurchaseOrderSummary[]` |
| POST | `/api/purchase-orders` | brouillon | `PurchaseOrderInput` | `PurchaseOrderDetail` (201) |
| GET | `/api/purchase-orders/{id}` | détail | — | `PurchaseOrderDetail` |
| PATCH | `/api/purchase-orders/{id}` | date attendue, note | `PurchaseOrderPatch` | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/lines` | ajouter une ligne | `PurchaseOrderLineInput` | `PurchaseOrderDetail` (201) |
| PATCH | `/api/purchase-orders/{id}/lines/{line_id}` | modifier une ligne | `PurchaseOrderLinePatch` | `PurchaseOrderDetail` |
| DELETE | `/api/purchase-orders/{id}/lines/{line_id}` | retirer une ligne | — | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/send` | envoyer | — | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/receive` | réceptionner (crée des lots) | `ReceiveInput` | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/cancel` | annuler | — | `PurchaseOrderDetail` |

**Facturation** (`routers/billing.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/invoices` | liste sans les lignes (`lineCount`) ; `status` accepte `open` et `overdue` (calculé) | `status`, `clientId`, `q` + liste ; tri `number` `client` `issued` `due` `ttc` `paid` `balance` `status` ; enveloppe : `counts`, `sums` (totalTtc, amountPaid, balance), `sumsByStatus` | `InvoiceSummary[]` |
| GET | `/api/invoices/{id}` | détail + paiements | — | `InvoiceDetail` |
| GET | `/api/payments` | liste, récent d'abord ; chaque affectation porte `invoiceNumber` | `clientId`, `method`, `q` (client, référence, n° de facture) + liste ; tri `date` `client` `method` `ref` `amount` ; enveloppe : `sums.amount` | `PaymentSummary[]` |
| POST | `/api/payments` | enregistrer (affectation auto aux plus anciennes) | `PaymentInput` | `PaymentSummary` (201) |
| GET | `/api/receivables` | balance âgée, risque, DSO (une ligne par client, non paginé) | `q`, `tag`, `rep`, `zone`, `onlyOverdue` | `Receivables` |

**Prix et groupes** (`routers/pricing.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/tags` | groupes + compteurs | `scope` | `TagWithCount[]` |
| POST | `/api/tags` | créer | `TagInput` | `TagDef` (201) |
| PATCH | `/api/tags/{scope}/{id}` | modifier | `TagPatch` | `TagDef` |
| DELETE | `/api/tags/{scope}/{id}` | supprimer | — | `Ok` |
| GET | `/api/price-rules` | règles | `active`, `clientId`, `productId` + liste | `PriceRuleSummary[]` |
| POST | `/api/price-rules` | créer | `PriceRuleInput` | `PriceRule` (201) |
| PATCH | `/api/price-rules/{id}` | modifier | `PriceRulePatch` | `PriceRule` |
| DELETE | `/api/price-rules/{id}` | supprimer | — | `Ok` |
| GET | `/api/prices/resolve` | prix retenu + pourquoi + candidats | `clientId`, `productId`, `qty`, `date` | `ResolvedPrice` |
| GET | `/api/prices/grid` | grille de prix | `clientId` ou `clientTag`, `productTag`, `category`, `q` | `PriceGridRow[]` |

**Logistique** (`routers/logistics.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/routes` | définitions des tournées | + liste | `Route[]` |
| GET | `/api/route-runs` | passages, date la plus récente d'abord (l'UI filtre toujours par `date`) | `date`, `routeId` + liste | `RouteRunDetail[]` |
| POST | `/api/route-runs/plan` | planifier une date | `PlanInput` | `RouteRunDetail[]` |
| PATCH | `/api/route-runs/{id}/stops` | réordonner les arrêts | `ReorderStopsInput` | `RouteRunDetail` |

**Contexte** (`routers/context.py`)

| Méthode | Chemin | Rôle | Paramètres / corps | Réponse |
|---|---|---|---|---|
| GET | `/api/context` | chercher / lister (pertinence avec `q`) | `entityType`, `entityId`, `kind`, `source`, `tag`, `q` + liste ; tri `title` `entity` `kind` `tags` `source` `updated` ; enveloppe : `counts` par type, `countsBySource` | `ContextEntrySummary[]` |
| POST | `/api/context` | créer (`source` = acteur) | `ContextEntryInput` | `ContextEntry` (201) |
| GET | `/api/context/for` | tout le contexte d'une entité + fiches liées | `entityType`, `id` | `ContextForEntity` |
| GET | `/api/context/{id}` | une fiche | — | `ContextEntrySummary` |
| PATCH | `/api/context/{id}` | modifier | `ContextEntryPatch` | `ContextEntry` |
| DELETE | `/api/context/{id}` | supprimer | — | `Ok` |

### Comment ça marche : service IA (port 4100, proxifié en `/ai/*`)

| Route | Fichier | Entrée | Sortie |
|---|---|---|---|
| `GET /health` | `routers/health.py:13` | — | `HealthResponse {ok, llm:{provider,model}, stt:{provider}, tts:{provider}, erpApiUrl}` |
| `GET /tools` | `routers/health.py:25` | — | `ToolInfo[] {name, description, parameters}` |
| `POST /chat` | `routers/chat.py:15` | `ChatRequest {messages, mode?, actorName?}` | SSE de `ChatStreamEvent` |
| `POST /command[?speak=1]` | `routers/command.py:26` | audio brut (`content-type` = mime, `x-mock-text` / `x-stt-hint`) ou JSON `CommandRequest {text, actorName?}` | SSE de `CommandStreamEvent` |
| `POST /stt` | `routers/speech.py:18` | audio brut, `x-stt-hint` ou `x-mock-text` | `SttResponse {text, ms}` ; 502 `stt_failed` |
| `POST /tts` | `routers/speech.py:37` | `TtsRequest {text, voice?}` | octets audio en streaming, en-tête `x-ms` ; 502 `tts_failed` |
| `WS /voice` | `routers/voice.py:10` | `VoiceClientMessage` + trames binaires | `VoiceServerMessage` + trames binaires |

Erreurs : `400 {error: {code: "bad_request", message}}` (corps invalide, `main.py:45`).

**Événements SSE** (`schemas/chat.py`, `schemas/command.py`) — une ligne `data: <JSON>` par événement, discriminé par `type` :

| `type` | Champs | `/chat` | `/command` |
|---|---|---|---|
| `transcript` | `text`, `ms` (temps STT), `final` (défaut true), `stable?` | | le final avant les autres ; `WS /voice/command` envoie aussi des `final:false` pendant la parole |
| `text` | `delta` | ✓ | ✓ |
| `tool_call` | `call {id, name, arguments}` | ✓ | ✓ |
| `tool_result` | `callId`, `name`, `ok`, `result`, `ms` | ✓ | ✓ |
| `navigate` | `path`, `label?` | | si l'utilisateur veut *voir* |
| `speech` | `mime`, `audio` (base64), `ms` | | si `speak=1` |
| `done` | `message`, `usage?`, `ms`, `timings?` | dernier | dernier (avec `timings`) |
| `error` | `message` | à la place de `done` | idem |

**Messages WebSocket `/voice`** (`schemas/voice.py`) :

| Sens | `type` | Champs | Effet |
|---|---|---|---|
| client → serveur | `start` | `sessionId?`, `actorName?` | ouvre / reprend une conversation |
| | `audio_start` | `mime`, `hint?` (indice STT ; mock STT : le texte entendu) | interrompt l'agent (barge-in), commence l'enregistrement |
| | *(binaire)* | trames audio (toutes les 100–250 ms) | envoyées au STT dès réception (transcription en direct) |
| | `audio_end` | — | lance le tour |
| | `text` | `text` | tour tapé (debug, scripts) |
| | `reset` | — | efface l'historique, renvoie `ready` |
| serveur → client | `ready` | `sessionId`, `stt`, `tts`, `llm` | |
| | `transcript` | `track: "caller"`, `text`, `final`, `stable?` | `final:false` pendant la parole (texte entendu jusque-là ; `stable` = mots définitifs), puis un `final:true` |
| | `agent_text` | `delta` | |
| | `agent_tool` | `name` + `args` (appel) puis `name`, `ok`, `ms` (fin) | |
| | `agent_audio_start` | `mime` | suivi de trames binaires (un segment par tour) |
| | `agent_audio_end` | — | |
| | `agent_done` | `text`, `timings` | |
| | `error` | `message` | |

Tous ces modèles sont publiés dans `http://localhost:4100/openapi.json` (`main.py:54-81`).

### Étendre

Un endpoint ERP de plus : [2.6](#ajouter-endpoint). Un événement SSE ou un message WS de plus : ajoutez le modèle dans
`apps/ai/app/schemas/` **et** dans l'union (`ChatStreamEvent`, `CommandStreamEvent`, `VoiceServerMessage`…), puis
le type dans `packages/shared/src/ai.ts`.

### Pièges

- `limit`, `qty`, etc. sont des chaînes côté ERP ; les listes sont séparées par des virgules.
- Une liste sans `envelope=1` est un tableau **tronqué à `limit` (100 par défaut)** : pour « toutes » les lignes d'une
  petite table, `limit=500` ; pour les grosses (commandes, factures, mouvements), filtrez ou paginez.
- `/api/invoices?status=overdue` filtre sur le statut **calculé** (jamais stocké).

---

<a id="service-ia"></a>
## 4. Service IA (`apps/ai/app`)

### Ce que c'est

Un harnais d'agent : une boucle modèle ⇄ outils, trois modes (`chat`, `voice`, `command`), des clients LLM / STT /
TTS interchangeables écrits en `httpx` brut (pas de SDK), et trois surfaces (`/chat`, `/command`, `WS /voice`).

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `config.py` | `settings` (lu une fois au démarrage) |
| `clients/base.py` | interfaces `LLMClient`, `STTClient`, `TTSClient` + types d'événements |
| `clients/factory.py` | `.env` → un client de chaque sorte (`get_llm_client()`…), modèles par défaut |
| `clients/{openai,anthropic,gemini}.py` | adaptateurs LLM |
| `clients/{soniox,deepgram,gradium,elevenlabs}.py` | adaptateurs parole ; `openai.py` a aussi STT + TTS |
| `clients/mock_llm.py`, `mock_speech.py` | faux fournisseurs hors ligne |
| `clients/jev.py` | modèle de décision Jev |
| `clients/http.py`, `ws.py`, `audio.py` | pool HTTP partagé, SSE, erreurs ; WebSocket ; webm→ogg, PCM→mp3 |
| `agent/loop.py` | `run_agent` |
| `agent/prompts.py` | `build_system_prompt` |
| `tools/` | les outils (section 5) |
| `services/voice_session.py`, `services/command.py` | la voix push-to-talk, la commande ⌥Espace |
| `routers/` | routes minces |
| `schemas/` | le contrat (événements, messages WS) |
| `cli.py` | `make chat` |

### Comment ça marche

<a id="config-ia"></a>
#### 4.1 Configuration

`config.py` charge le `.env` racine (les vraies variables d'environnement gagnent) dans `settings`, **une seule
fois**. Les clients sont construits une fois (`@cache`, `factory.py:103-121`) et au démarrage (`main.py:27-36`) : une
clé manquante fait échouer le démarrage avec `configuration error`. Après un changement de `.env` : `make restart`
(Docker) ou relancer `make dev`.

| Variable | Défaut | Lu dans |
|---|---|---|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_BASE_URL` | `mock` ; modèles : `factory.py:24` | `make_llm_client` (`factory.py:44`) |
| `LLM_EFFORT` | `low` | Anthropic (`output_config.effort`) |
| `AGENT_MAX_STEPS` | 8 | `loop.py:60` |
| `STT_*`, `MOCK_STT_TEXT` | `mock`, `fr` | `make_stt_client` (`factory.py:66`) |
| `TTS_*` | `mock`, `fr` | `make_tts_client` (`factory.py:82`) |
| `JEV_*` | clé vide → pas de Jev | `make_jev_client` (`factory.py:97`) |
| `ERP_API_URL`, `DATA_DIR`, `AI_PORT` | `http://localhost:4000`, `../hackathon-data` (zip d'équipe : `./data`), 4100 | `config.py:71-75` |

Changer de modèle sans code : `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL=https://api.groq.com/openai/v1`,
`LLM_MODEL=…`, `LLM_API_KEY=…`. Liste complète : [apps/ai/README.md#environment](apps/ai/README.md#environment).

<a id="clients"></a>
#### 4.2 Les clients (`clients/`)

**Interfaces** (`clients/base.py`) :

```python
# LLM — clients/base.py:51-57
class LLMClient(ABC):
    provider: str
    model: str
    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Stream one model response. Implement it as an `async def` generator (with `yield`)."""
```

- `LLMRequest {system, messages: list[ChatMessage], tools: list[ToolInfo], max_tokens}` ; le générateur émet
  `LLMText(delta)` au fil de l'eau, `LLMToolCall(call)` (une fois les arguments complets) et `LLMUsage`.
  L'adaptateur traduit les `ChatMessage` (`user`, `assistant` avec `tool_calls`, `tool` avec `tool_call_id` + `name`)
  dans le format du fournisseur (`to_openai_message`, `to_anthropic_messages`, `to_gemini_contents`).
- `STTClient.transcribe(audio, mime, hint) -> str` ; **`transcribe_stream(audio_chunks, mime, hint)`** émet des
  `STTUpdate(text, final, stable)` (texte complet à chaque fois). Par défaut : attend la fin puis un seul update
  final. Soniox, Deepgram et le mock le surchargent (`streams = True`) : voir [Transcription en direct](#stt-direct).
- `TTSClient.synthesize(text, voice) -> TTSResult(mime, chunks)` : lève sur erreur HTTP, puis streame les octets.
  Tous les vrais TTS renvoient `audio/mpeg` (le lecteur web concatène le mp3 d'un tour) ; PCM → `audio.Mp3Encoder`.

**Factory** (`factory.py:44-63`) : un `match` par sorte. `DEFAULT_MODELS`, `DEFAULT_STT_MODELS`, `DEFAULT_TTS`
donnent les défauts.

**HTTP partagé** (`clients/http.py`) : un seul `httpx.AsyncClient` (`http_client()`, réutilise les connexions TLS),
`post_stream` (POST sans lire le corps), `sse_json` (itère les `data:`), `body_chunks`, `parse_args`,
`provider_error` qui formate `"<who> HTTP <status>: <body> — <indice>"` (clé refusée, quota, format audio).

**Étendre : ajouter un fournisseur** (exemple TTS ; LLM et STT suivent le même schéma) :

1. `apps/ai/app/clients/montts.py` — remplacez l'URL, les en-têtes et le corps par ceux du fournisseur :

   ```python
   from .base import TTSClient, TTSResult
   from .http import body_chunks, http_client, post_stream

   class MonTTS(TTSClient):
       name = "montts"

       def __init__(self, api_key: str, model: str, voice: str):
           self.api_key, self.model, self.voice = api_key, model, voice

       async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
           res = await post_stream(
               http_client(), "https://api.example.com/v1/tts/stream", who="montts tts",
               headers={"authorization": f"Bearer {self.api_key}"},
               json={"text": text, "model": self.model, "voice": voice or self.voice, "format": "mp3"},
           )
           return TTSResult("audio/mpeg", body_chunks(res))   # mp3 obligatoire pour le lecteur web
   ```

2. `factory.py` : importez la classe, ajoutez un défaut dans `DEFAULT_TTS` et un `case` :

   ```python
   case "montts":
       return MonTTS(need("TTS_API_KEY", cfg.api_key), model, voice)
   ```

3. `.env` : `TTS_PROVIDER=montts`, `TTS_API_KEY=…` ; `make restart` ; vérifiez `GET /ai/health` puis
   `curl -s localhost:4100/tts -H 'content-type: application/json' -d '{"text":"Bonjour"}' -o /tmp/t.mp3`.
4. Un LLM « compatible OpenAI » n'a besoin d'aucun code (`openai-compatible`). Un LLM différent : copiez
   `anthropic.py` (le plus court avec gestion des appels d'outils en streaming). Tests : sur le modèle de
   `tests/test_clients.py` (réponses SSE enregistrées, pas de réseau).

<a id="prompts"></a>
#### 4.3 Les prompts (`agent/prompts.py`)

```python
# agent/prompts.py:54-67
async def build_system_prompt(mode: ChatMode, actor_name: str | None = None) -> str:
    meta = await get_meta()
    today = meta.get("today") or datetime.now(UTC).date().isoformat()
    company = meta.get("company") or "un grossiste alimentaire"
    trade = meta.get("trade") or company_trade()
    parts = [
        ROLE.format(company=company, trade=f"Activité : {trade}" if trade else "C'est un grossiste alimentaire"),
        BASE_RULES,
        MODE_RULES[mode],
        f"Entreprise : {meta.get('company') or '(ERP injoignable)'}. Aujourd'hui : {french_date(today)} ({today}).",
        f"Interlocuteur : {actor_name}." if actor_name else "",
        f"# Contexte entreprise\n\n{context}" if (context := read_context_files()) else "",
    ]
    return "\n\n".join(p for p in parts if p)
```

| Partie | Contenu | Source |
|---|---|---|
| `ROLE` (`:19-20`) | « assistant de l'ERP de {company}. Activité : {trade} » : `company` de `GET /api/meta`, `trade` de `meta.trade` sinon 1re phrase de `DATA_DIR/context/*entreprise*.md` (`company_trade()`) | ERP + pack |
| `BASE_RULES` (`:22-32`) | « outils pour toute donnée », `search` d'abord, `get_price`, `get_context`, brouillon puis confirmation explicite, alertes, français concis | code |
| `CHAT_RULES` (`:34`) | markdown léger | code |
| `VOICE_RULES` (`:36-41`) | 1–2 phrases, pas de markdown ni d'ids, nombres en toutes lettres, au plus « Je regarde. » avant le premier outil puis rien entre les outils (tout texte est prononcé dans l'ordre), récapituler avant de confirmer | code |
| `COMMAND_RULES` (`:43-49`) | agir tout de suite, une phrase, une demande explicite vaut accord | code |
| entreprise + date | `meta.company`, `meta.today` en français | `GET /api/meta`, cache 60 s (`:64-80`) |
| interlocuteur | `actorName` (« Agent vocal », « Commande vocale », « CLI ») | requête |
| contexte entreprise | tous les `DATA_DIR/context/*.md` (premier niveau, triés), relus à **chaque** tour | `read_context_files` (`:83-90`) |

Étendre : changez les règles dans `prompts.py` ou le contexte dans `data/context/*.md` (pris en compte au tour
suivant, sans redémarrage). Pour injecter la fiche de l'appelant, ajoutez une partie à `parts` (par ex. le résultat de
`GET /api/context/for` pour un client connu de la session).

<a id="boucle"></a>
#### 4.4 La boucle de l'agent (`agent/loop.py`)

```python
# agent/loop.py:60-91 (extrait)
for _step in range(max_steps or settings.max_steps):
    text = ""; calls = []
    async for ev in llm.stream(request):
        match ev:
            case LLMText(delta=delta):      text += delta; yield TextEvent(delta=shown)
            case LLMToolCall(call=call):    calls.append(call); yield ToolCallEvent(call=call)
            case LLMUsage(...):             usage.input_tokens += i or 0 ...
    if not calls:                                            # réponse finale
        messages.append(ChatMessage(role="assistant", content=text))
        yield DoneEvent(message=message, usage=usage, ms=ms_since(started)); return
    messages.append(ChatMessage(role="assistant", content=text, tool_calls=calls))
    results = await asyncio.gather(*(execute_tool(call, tools, ctx) for call in calls))
    for r in results:
        messages.append(ChatMessage(role="tool", tool_call_id=r.call_id, name=r.name, content=to_json(r.result)))
        yield r
```

Pas à pas :

1. `ctx = ToolContext(erp=ErpClient(actor, actor_name), actor=actor)` ; `actor` = `ai_chat` en mode chat, sinon
   `voice_agent` (`:51-52`).
2. Le prompt système est construit une fois par tour ; la même `LLMRequest` est renvoyée à chaque étape (elle
   référence la liste `messages`, qui grandit).
3. Le texte est streamé **pendant** que le modèle génère ; les appels d'outils sont collectés.
4. Pas d'appel → `DoneEvent`, fin. Sinon les outils tournent **en parallèle** (`asyncio.gather`), leurs résultats
   sont ajoutés en messages `tool` (JSON compact, accents gardés) et on rappelle le modèle.
5. Au-delà de `AGENT_MAX_STEPS` (8) : message `GIVE_UP` (« Désolé, je n'ai pas réussi à aller au bout… »).
6. `execute_tool` (`:102-112`) ne lève jamais : outil inconnu ou exception → `ok=false`, `result={"error": "…"}` ;
   le modèle lit l'erreur et explique ou réessaie.
7. Toute autre exception (fournisseur en panne, clé refusée) → `ErrorEvent`. L'annulation (`CancelledError`) n'est
   pas une `Exception` : la boucle s'arrête sans rien émettre. C'est le mécanisme du barge-in et de la déconnexion
   d'un client SSE (Starlette annule le générateur, `routers/sse.py:15`).

**`run_agent` modifie la liste `messages` qu'on lui passe** : celui qui garde la liste garde l'historique.

| Mode | Qui garde l'historique | Où |
|---|---|---|
| `chat` | le **navigateur** : `history` dans `chat-store.ts:23`, renvoyé en entier à chaque `POST /chat` (reconstruit par `TurnRecorder`) ; perdu au rechargement de la page | `apps/web/src/features/assistant/` |
| `voice` | le **service IA** : `conversations: dict[sessionId, Conversation]` en mémoire (`voice_session.py:68`), copie de travail validée en fin de tour, coupée à ~40 messages par `trim()` (`:296-301`, commence toujours sur un message `user`) ; perdue au redémarrage | `services/voice_session.py` |
| `command` | personne : un seul message `user` par requête (`services/command.py:104`) | |
| CLI | la liste `messages` de `cli.py` (`/reset` la vide) | `app/cli.py` |

<a id="latence"></a>
#### 4.5 Latence : où se joue chaque milliseconde

| Étape | Ce que fait le kit | Levier |
|---|---|---|
| STT | transcription **pendant** l'appui ([Transcription en direct](#stt-direct)) : au relâchement, seuls les derniers mots restent à finaliser | LLM lancé sur un partiel stable, mode mains libres (`<end>`) |
| prompt | règles + tout `DATA_DIR/context/*.md` (≈ 44 Ko dans le pack de référence) renvoyés à chaque étape ; Anthropic : relus au cache ([4.8](#cache-prompt)) | réduire le contexte, garder le préfixe stable |
| LLM | un appel par étape ; outils en parallèle | outil composite ([5.4](#outil-composite)), modèle rapide, `LLM_EFFORT=low` |
| outils | `ErpClient` réutilise un `httpx.AsyncClient` partagé (`erp_http()`, keep-alive, timeout 10 s, fermé à l'arrêt) (`tools/erp.py:23-41`) | outil composite, moins d'appels ERP |
| TTS | phrase par phrase : dès qu'une phrase se termine par `. ! ? …` + espace (`Speaker.SENTENCE`, `:230`), elle part au TTS ; un seul segment mp3 par tour | couper plus tôt (virgules), filler pendant les outils |
| lecture | `SegmentPlayer` (MediaSource) joue dès le premier octet | — |

<a id="session-voix"></a>
#### 4.6 La session vocale (`services/voice_session.py`)

- `VoiceConnection.serve()` lit les trames ; binaire → `recording.feed()` (envoyée au STT en direct, voir [Transcription en direct](#stt-direct)) ; texte → `handle_text`.
- Chaque tour est une `asyncio.Task` (`start_turn`) ; `interrupt()` l'annule et attend son nettoyage.
- `run_turn` (`:168-229`) : STT → `transcript` → `run_agent(mode="voice")` sur une copie de l'historique → texte
  vers `Speaker` → `speaker.finish()` → `agent_done`. Les erreurs deviennent des messages `error`.
- `Speaker` (`:231-294`) : un buffer de texte, une file de phrases, un worker qui synthétise et envoie les octets
  dans l'ordre. `agent_audio_start` part au premier octet ; `tts_first_byte_ms` est mesuré là.
- Reconnexion avec le même `sessionId` → même `Conversation`.

<a id="stt-direct"></a>
#### Transcription en direct (`services/utterance.py`, `services/vocabulary.py`)

```
audio_start ─▶ Utterance(stt, mime, hint, on_partial)    ouvre le flux STT (si stt.streams)
trame       ─▶ feed(frame) ─▶ fournisseur                 ◀─ on_partial(STTUpdate) ─▶ transcript {final:false}
audio_end   ─▶ await text()   Soniox : {"type":"finalize"} ─▶ jeton <fin> ─▶ transcript {final:true} ─▶ agent
barge-in    ─▶ cancel()       ferme le flux du fournisseur
```

- Chaque trame est aussi gardée : si le flux casse ou ne rend pas ses mots finaux en `FINAL_TIMEOUT_S` (5 s),
  `text()` transcrit l'enregistrement complet (`transcribe`). L'énoncé n'est jamais perdu.
- Jetons Soniox : non finaux = renvoyés en entier à chaque message, peuvent changer ; finaux = envoyés une fois.
  `stable` = les mots finaux. `<end>` (pause détectée) et `<fin>` (réponse au finalize) ne sont pas du texte.
- Vocabulaire : noms des clients, puis des produits, puis leurs alias (`/api/clients`, `/api/products`), cache 5 min,
  `MAX_TERMS` = 500 → `context.terms` (Soniox, plafonné à `MAX_TERMS_CHARS`), `keyterm` (Deepgram). Pour l'enrichir :
  `company_terms()` (ex. noms des contacts, ou le panier habituel du client en ligne). Le mock STT n'en reçoit pas.
- Le mock STT simule des partiels (un mot toutes les 3 trames) : l'affichage se teste sans clé.

**Étendre** : lancer le LLM sur un partiel stable (GUIDE-VOIX 4.3) ; mode mains libres sur les jetons `<end>` ;
vocabulaire par appel (panier habituel du client identifié).

<a id="jev"></a>
#### 4.7 Jev (décisions typées)

`get_jev_client()` renvoie un `JevClient` ou `None` sans `JEV_API_KEY`. Méthodes : `choose`, `score`, `yes_no`,
`ask` (plusieurs questions en un appel). Exemples prêts à copier : `agent/jev_examples.py` (`pick_product`,
`is_yes`). **Rien dans l'agent par défaut ne l'appelle.** Format et usages : [apps/ai/README.md#jev-decision-model](apps/ai/README.md#jev-decision-model).

<a id="cache-prompt"></a>
#### 4.8 Cache de prompt (Anthropic)

Le préfixe d'une requête (outils → prompt système → messages) pèse ≈ 27 k tokens dans le pack de référence (≈ 44 Ko de
`DATA_DIR/context/*.md` + schémas des outils). `clients/anthropic.py` pose 3 points de cache `cache_control:
{"type": "ephemeral"}` (l'API en accepte 4) : sur le **dernier outil**, sur le **bloc système**, et sur le **dernier
bloc du dernier message**. L'étape suivante d'un même tour (après un résultat d'outil) et le tour suivant relisent
donc tout le préfixe déjà vu au cache : ≈ 10 % du prix d'entrée et un premier token plus rapide. Durée de vie : 5 min
après le dernier usage ; écrire le cache coûte ≈ 1,25× le prix normal, une fois.

- **Voir les hits** : l'événement `done` de `POST /chat` porte `usage.cacheReadInputTokens` (lu au cache) et
  `usage.cacheCreationInputTokens` (écrit) ; `make chat` les affiche (« cache lu … / écrit … »). Chez Anthropic,
  `inputTokens` ne compte que la partie **hors cache** (total = input + cacheCreation + cacheRead).
- **Ce qui casse le cache** (tout octet changé invalide ce qui suit) : un horodatage, un id ou un compteur dans le
  prompt système ; modifier un fichier de `DATA_DIR/context/` (normal : le tour suivant réécrit le cache) ; ajouter,
  retirer ou réordonner des outils, ou changer une docstring / un argument ; changer de modèle ou de `LLM_EFFORT` ;
  réécrire un ancien message de l'historique. La date vient de `GET /api/meta` (stable), pas de l'horloge.

### Pièges

Voir [9](#pieges) : historique vocal en mémoire, indice STT optionnel (`hint` de `audio_start`, non envoyé par la
page Voix). Cache de prompt : seul l'adaptateur Anthropic le pose ([4.8](#cache-prompt)).

---

<a id="outils"></a>
## 5. Les outils (`@tool`) en détail

### Ce que c'est

Un outil est une fonction Python `async` que le modèle peut appeler. Le décorateur `@tool` en tire le nom, la
description et le schéma JSON envoyés au modèle. Chaque outil appelle l'ERP en HTTP ; il ne contient pas de règle
métier.

### Fichiers clés

| Fichier | Contenu |
|---|---|
| `apps/ai/app/tools/registry.py` | `@tool`, `Tool`, `ToolContext`, `ToolArgs`, `TOOLS`, `json_schema` |
| `apps/ai/app/tools/erp.py` | `ErpClient` (`get`, `post`, `patch`, `delete`, pool partagé `erp_http()`), `ErpError`, `enc`, `pick` |
| `apps/ai/app/tools/catalog.py` · `context.py` · `history.py` · `orders.py` | les 16 outils |
| `apps/ai/app/tools/__init__.py` | importe les modules (= enregistre les outils), `all_tools()` |
| `apps/web/src/features/assistant/tools.tsx` | `TOOL_LABEL` : libellé français affiché dans l'UI |

### Comment ça marche

<a id="decorateur"></a>
#### 5.1 Le décorateur

```python
# apps/ai/app/tools/registry.py:69-83
def tool(fn=None, *, name=None):
    def register(fn) -> Tool:
        params = list(inspect.signature(fn).parameters.values())[1:]  # skip ctx
        fields = {p.name: (p.annotation, ... if p.default is inspect.Parameter.empty else p.default) for p in params}
        args_model = create_model(f"{fn.__name__}_args", __base__=ToolArgs, **fields)
        description = " ".join(line.strip() for line in inspect.cleandoc(fn.__doc__ or "").splitlines() if line.strip())
        t = Tool(name=name or fn.__name__, description=description, args_model=args_model, fn=fn)
        TOOLS[t.name] = t
        return t
    return register(fn) if fn else register
```

| Élément Python | Devient pour le modèle | Exemple |
|---|---|---|
| nom de la fonction (ou `@tool(name="…")`) | nom de l'outil | `get_product_stock` |
| docstring (lignes jointes par des espaces) | `description` | « Stock d'un produit : … » |
| 1er paramètre | **rien** : c'est le `ToolContext` | `ctx: ToolContext` |
| autres paramètres | `parameters` (JSON schema), noms en camelCase (`ToolArgs`, `alias_generator=to_camel`) | `product_id` → `productId` |
| sans défaut, ou `= Field(description=…)` sans défaut | `required` | `client_id: str = Field(description="ex. cli_0012")` |
| `X \| None = None` ou `Field(None, …)` | optionnel, sans `null` dans le schéma | `qty: float \| None = Field(None, …)` |
| `Literal["a", "b"]` | `enum` | `entity_type: Literal["client", "supplier", …]` |
| `list[Literal[…]]` | `array` d'`enum` | `types` de `search` |
| sous-classe de `ToolArgs` | objet imbriqué, inliné (pas de `$ref`) | `lines: list[OrderLine]` (`orders.py:10`) |
| `Field(description=…)` | `description` du paramètre | |

`json_schema` (`registry.py:89-111`) retire titres, défauts, `$defs`/`$ref` et `| null` : le schéma ressemble à ce
qu'on écrirait à la main. Vérifiez-le avec `curl -s localhost:4100/tools`.

**Validation** (`Tool.run`, `registry.py:57-63`) : les arguments du modèle sont validés par le modèle Pydantic
généré (camelCase ou snake_case acceptés). Échec → `ValueError("Arguments invalides : qty: …")`, que la boucle
renvoie au modèle comme `{"error": …}`. La fonction reçoit ensuite des valeurs Python typées (les objets imbriqués
sont des instances `ToolArgs`, d'où `line.to_erp()` dans `orders.py`).

**`ToolContext`** (`registry.py:34-37`) : `ctx.erp` est un `ErpClient` déjà marqué `x-actor` (`ai_chat` ou
`voice_agent`) et `x-actor-name` ; `ctx.actor` permet d'adapter le comportement (ex. `source` d'une commande,
`orders.py:55`). `ctx.erp.get(path, query)` retire les paramètres `None`/vides ; `ctx.erp.post(path, body)` ; un
refus de l'ERP lève `ErpError` avec son message français (`erp.py:76-81`), que le modèle lira.

**Enregistrement** : importer le module suffit (`tools/__init__.py:14`). `all_tools()` est relu à chaque requête ; tous
les modes reçoivent tous les outils.
Un outil mal déclaré (pas `async def`, pas de `ctx: ToolContext`, paramètre sans type, pas de docstring, nom en
double) fait échouer le démarrage avec un message français ; la trace complète s'affiche dans le terminal du serveur.

**Retour** : n'importe quelle valeur sérialisable en JSON (dict, list, str, nombre). Elle est sérialisée en JSON
compact et ajoutée à la conversation : le modèle la relit **à chaque étape suivante** du tour, et en voix elle reste
dans l'historique. D'où les `pick(...)` et `[:5]` partout.

#### 5.2 Les 16 outils

| Outil | Fichier | Appelle | Renvoie (réduit) |
|---|---|---|---|
| `search(query, types?)` | `catalog.py:12` | `GET /api/search` | 8 premiers `{type, id, label, sublabel}` |
| `get_client(client_id)` | `catalog.py:31` | `GET /api/clients/{id}` | statut, conditions, encours, 5 notes, 10 lignes de l'habituel, `openIssues`, 5 événements, 5 commandes |
| `get_product_stock(product_id)` | `catalog.py:55` | `GET /api/products/{id}` | `available`, `onHand`, `reserved`, `incoming`, `nextExpiry`, prix |
| `find_alternatives(product_id)` | `catalog.py:70` | `GET /api/products/{id}/alternatives` | 5 produits |
| `get_price(client_id, product_id, qty?)` | `catalog.py:80` | `GET /api/prices/resolve` | `price`, `listPrice`, `source`, `explanation`, `betterPriceWithVolume?` |
| `search_context(query, entity_type?, entity_id?, kind?, limit?)` | `context.py:36` | `GET /api/context?q=` | fiches compactes (corps ≤ 500 car.) |
| `get_context(entity_type, id)` | `context.py:56` | `GET /api/context/for` | `{about, entries, related}` |
| `save_context(entity_type, kind, title, body, entity_id?, tags?)` | `context.py:75` | `POST /api/context` | `{id, saved, title}` |
| `get_client_history(client_id, types?, limit?)` | `history.py:49` | `GET /api/clients/{id}/events` | ouverts d'abord, ≤ 20 |
| `log_client_event(client_id, type, title, …)` | `history.py:65` | `POST /api/clients/{id}/events` | l'événement compact |
| `get_supplier_history(supplier_id, types?, limit?)` | `history.py:96` | `GET /api/suppliers/{id}/events` | ouverts d'abord, ≤ 20 |
| `log_supplier_event(supplier_id, type, title, …)` | `history.py:111` | `POST /api/suppliers/{id}/events` | l'événement compact |
| `create_draft_order(client_id, delivery_date?, lines?, note?)` | `orders.py:38` | `POST /api/orders` | `summarize_order` : id, numéro, statut, lignes avec `lineId`, `warnings` |
| `add_order_line(order_id, product_id, qty, note?, substitute_for?)` | `orders.py:60` | `POST /api/orders/{id}/lines` | idem |
| `confirm_order(order_id)` | `orders.py:74` | `POST /api/orders/{id}/confirm` | idem |
| `get_order(order_id)` | `orders.py:83` | `GET /api/orders/{id}` | idem |

Ce que l'agent ne peut pas faire faute d'outil (les routes existent) : modifier/retirer une ligne, changer la date,
annuler, préparer, livrer, facturer, encaisser, acheter, gérer prix, stock, tournées.

<a id="ajouter-outil"></a>
#### 5.3 Étendre : ajouter un outil simple

`list_overdue_invoices` — l'ERP calcule déjà `overdue` et `daysOverdue` (`services/invoices.py:25-41`) :

```python
# apps/ai/app/tools/billing.py  (nouveau fichier)
"""Billing tools: what a client owes."""

from pydantic import Field

from .erp import pick
from .registry import ToolContext, tool


@tool
async def list_overdue_invoices(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Factures échues (en retard) d'un client, avec le total dû. À utiliser quand le client demande ce qu'il doit,
    pourquoi il est bloqué, ou avant d'accepter une grosse commande. Overdue invoices of a client.
    """
    invoices = await ctx.erp.get("/api/invoices", {"clientId": client_id, "status": "overdue"})
    return {
        "count": len(invoices),
        "totalDue": round(sum(i["balance"] for i in invoices), 2),
        "invoices": [pick(i, "number", "dueDate", "balance", "daysOverdue") for i in invoices[:5]],
    }
```

Puis :

1. `apps/ai/app/tools/__init__.py` : `from . import billing, catalog, context, history, orders`.
2. `curl -s localhost:4100/tools | grep -A3 list_overdue` (uvicorn a rechargé).
3. `make chat` → « qu'est-ce que doit le Zinc des Halles ? ».
4. Optionnel : `TOOL_LABEL.list_overdue_invoices = "Factures en retard"` dans `apps/web/src/features/assistant/tools.tsx:21`.
5. Si l'outil change le comportement attendu, ajoutez une règle d'une ligne dans `BASE_RULES` (`agent/prompts.py`).

**Un outil d'écriture** : `ErpClient` a `get`, `post`, `patch` et `delete`. Pour `PUT`, ajoutez une méthode dans
`tools/erp.py` sur le modèle de `patch` :

```python
async def put(self, path: str, body: Any = None) -> Any:
    return await self._request("PUT", path, json={} if body is None else body)
```

Exemple : `update_order_line` → `await ctx.erp.patch(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}", {"qty": qty})`.
Avec la route `repeat` de [2.6](#ajouter-endpoint) : `await ctx.erp.post(f"/api/orders/{enc(order_id)}/repeat", {})`.

<a id="outil-composite"></a>
#### 5.4 Étendre : un outil composite

Un aller-retour modèle coûte bien plus cher qu'un appel HTTP local. Un outil qui enchaîne plusieurs appels ERP
économise des étapes de la boucle :

```python
# dans apps/ai/app/tools/catalog.py (search, pick, enc, format_number y sont déjà)
import asyncio

@tool
async def quote_product(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_query: str = Field(description="Ce que le client a dit, ex. « bar de ligne », « loup »"),
    qty: float | None = Field(None, description="Quantité (défaut 1)"),
) -> dict:
    """
    Trouve un produit à partir de ce que dit le client et renvoie en un seul appel son stock et SON prix.
    À utiliser quand un client connu demande « vous avez du … ? » ou « c'est combien le … ? ».
    Product lookup + stock + client price in one call.
    """
    hits = await ctx.erp.get("/api/search", {"q": product_query, "types": "product", "limit": 3})
    if not hits:
        return {"found": False, "query": product_query}
    product_id = hits[0]["id"]
    product, price = await asyncio.gather(
        ctx.erp.get(f"/api/products/{enc(product_id)}"),
        ctx.erp.get("/api/prices/resolve", {"clientId": client_id, "productId": product_id,
                                            "qty": format_number(qty) if qty else None}),
    )
    return {
        "found": True,
        "product": pick(product, "id", "name", "unit", "available", "nextExpiry"),
        "price": pick(price, "price", "source", "explanation"),
        "otherMatches": [pick(h, "id", "label") for h in hits[1:]],
    }
```

Gardez `otherMatches` : le modèle peut demander « lequel ? » quand la recherche hésite.

#### 5.5 Bonnes pratiques

- **Description = quand l'utiliser.** Première phrase en français (ce que fait l'outil), puis « À utiliser quand… »,
  puis une courte phrase anglaise (les modèles routent mieux). Citez les outils voisins (« pas pour une réclamation :
  `log_client_event` », `context.py:87`).
- **Paramètres décrits avec un exemple d'id** (`ex. cli_0012`) et des `Literal` dès que les valeurs sont fermées.
- **Sorties petites** : `pick` les champs utiles, coupez les listes, raccourcissez les textes (`compact`,
  `compact_event`). Pas d'objet ERP brut.
- **Erreurs** : levez une exception avec un message français ; ne renvoyez pas `{"ok": false}` silencieux.
- **Écritures** : rendez-les sûres à rejouer quand c'est possible (le modèle réessaie après une erreur), renvoyez
  l'id créé pour les étapes suivantes, et laissez la confirmation au prompt (« ne confirme qu'après accord explicite »,
  `BASE_RULES`) ou à un outil séparé (`create_draft_order` puis `confirm_order`).
- **Pas de règle métier dans l'outil** : si un calcul manque, ajoutez-le dans `apps/backend/app/services/`.

### Pièges

- `@tool` **remplace la fonction par un objet `Tool`** : `await get_price(...)` ne marche pas. Appelez
  `await TOOLS["get_price"].run({...}, ctx)` ou `tool.fn(ctx, ...)`.
- La fonction doit être `async` et ses paramètres **annotés** (sinon le schéma est faux).
- Ordre Python : un paramètre sans défaut ne peut pas suivre un paramètre avec défaut. `Field(description=…)` sans
  valeur compte comme un défaut Python mais reste requis pour le modèle : utilisez-le pour garder l'ordre.
- Un retour non sérialisable en JSON (objet, `datetime`) devient `{"error": "… non sérialisable en JSON …"}` pour ce
  seul appel (`execute_tool`, `loop.py`) : renvoyez des `str` / nombres / listes / dicts.
- Deux outils du même nom : le dernier importé écrase le premier dans `TOOLS`.

---

<a id="frontend"></a>
## 6. Frontend (`apps/web/src`)

### Ce que c'est

Une SPA React 18 + Vite + Tailwind + react-router + TanStack Query. Elle parle à l'ERP (`/api`) et au service IA
(`/ai`) via le proxy Vite. Types partagés : `@kit/shared` (`packages/shared/src`).

### Fichiers clés

| Chemin | Rôle |
|---|---|
| `main.tsx` | `QueryClient` (staleTime 15 s, retry 1), horloge métier chargée avant le premier rendu |
| `app/routes.tsx` | toutes les routes (une page = `pages/<nom>/index.tsx`, export par défaut) |
| `app/nav.ts` | menu latéral + commandes « Aller à » de ⌘K |
| `app/AppShell.tsx` | sidebar · page · panneau Assistant ; monte SSE, ⌘K, toasts, commande vocale ; raccourcis ⌘J, ⌘\ / ⌘B |
| `lib/api.ts` | client typé : une fonction par route ERP, erreurs → toast + `ApiRequestError` |
| `lib/queries.ts` | clés de requête `qk`, un hook par lecture, `useApiMutation`, flux SSE, `INVALIDATE` |
| `lib/url-state.ts` | filtres dans l'URL (`useUrlState`, `useUrlPatch`, `useDebounced`) |
| `lib/clock.ts` | `businessNow()` / `businessToday()` alignés sur `meta.today` |
| `ui/` | le design system (`@/ui`) — [DESIGN.md](DESIGN.md), `ui/README.md` |
| `features/assistant/` | chat (⌘J), session vocale, lecteur audio, affichage des outils |
| `features/voice-command/` | ⌥Espace : moteur, HUD, bouton |
| `features/document/` | blocs partagés des pages document (commande, achat) |
| `pages/voice/` | page Voix (appel + mode commande, timeline, métriques, activité live) |

### Comment ça marche

<a id="donnees-web"></a>
#### 6.1 Lire et écrire des données

```ts
// lecture
const { data, isLoading } = useOrders({ status: "draft" });          // lib/queries.ts:148
// écriture
const confirm = useApiMutation(api.orders.confirm, { success: "Commande confirmée", invalidate: [qk.orders.all] });
confirm.mutate(order.id);
```

- `request()` (`lib/api.ts:47-78`) ajoute `x-actor: user` / `x-actor-name: Moi` aux écritures, transforme
  `{error:{code,message}}` en `ApiRequestError` et affiche un toast (`{silent:true}` pour le couper).
- Les clés `qk` sont préfixées : invalider `qk.orders.all` (`["orders"]`) rafraîchit toutes les listes et fiches de
  commandes.
- `useApiMutation` (`queries.ts:205-221`) toast le succès, toast chaque `warnings[]` de la réponse, invalide les
  clés données.

#### 6.2 État dans l'URL

`const [q, setQ] = useUrlState("q")` : les filtres vivent dans `?q=&type=`, survivent au rechargement, se partagent.
Changer un filtre remet la pagination à 1 (sauf `{keepPage:true}`). Plusieurs setters dans le même tick fusionnent
(`url-state.ts:15-40`).
Les grandes listes sont paginées par l'API ([Pagination](#pagination)) : `useServerList({ defaultSort })` lit `?page=`
et `?sort=-champ` et donne `params` (`limit`, `offset`, `sort`, `order`) à passer au hook `use…Page`, qui renvoie
`{items, total, counts, sums…}` ; `<DataTable server={{ list, total }}>` affiche la page et la barre de pagination.
Les listes de référence (clients, produits, fournisseurs pour les sélecteurs) sont chargées entières avec
`useClients()` / `useProducts()` / `useSuppliers()` (`limit=500`, `LIST_MAX` dans `lib/api.ts`).

#### 6.3 Horloge

N'utilisez jamais `new Date()` pour « aujourd'hui » : `businessToday()` / `businessNow()` (`lib/clock.ts`).

<a id="live"></a>
#### 6.4 Mises à jour en direct

`useActivityStream()` (`queries.ts:273-299`) ouvre `EventSource("/api/events/stream")`, se reconnecte avec backoff,
et pour chaque `ActivityEvent` : l'ajoute aux listes d'événements en cache, invalide les clés de `INVALIDATE[entity]`
(`queries.ts:232-243`), marque l'id pour le flash violet (`useRecentlyChanged`, `DataTable` le fait seul) et prévient
les abonnés `useOnActivity`. Les pages ne font jamais de polling.

<a id="surfaces-ia"></a>
#### 6.5 Les trois surfaces IA

| Surface | Code | Transport | État |
|---|---|---|---|
| Assistant (⌘J) | `features/assistant/AssistantPanel.tsx`, `chat-store.ts`, `ai-client.ts` | `fetch POST /ai/chat`, lecture SSE à la main (`ai-client.ts:59-75`) | store module : survit à la fermeture du panneau, pas au rechargement |
| Voix · Appel (`/voice`) | `pages/voice/index.tsx`, `features/assistant/useVoiceSession.ts`, `audio-player.ts` | `WebSocket /ai/voice`, MediaRecorder par tranches de 100 ms (STT en direct) | `sessionId` dans le hook ; historique côté serveur |
| Voix · Commande (⌥Espace, `/voice?mode=command`) | `features/voice-command/engine.ts`, `VoiceCommand.tsx`, `pages/voice/command.tsx` | voix : `WS /ai/voice/command?speak=1` (trames de 100 ms, STT en direct) ; clavier : `fetch POST /ai/command?speak=1` (JSON), SSE | singleton module partagé HUD / page |

- Audio mock : mime `audio/x-mock-wav` (`MOCK_TTS_MIME`) → le navigateur lit le texte avec `speechSynthesis` fr-FR.
- Les appels d'outils s'affichent avec `features/assistant/tools.tsx` (`TOOL_LABEL`, liens vers l'entité).
- Espace = push-to-talk sur `/voice` hors champ texte (`pages/voice/index.tsx:50-75`) ; ⌥Espace partout, même dans un
  champ (`VoiceCommand.tsx:23-40`).

<a id="ajouter-page"></a>
### Étendre : ajouter une page (6.6)

1. `apps/web/src/pages/overdue/index.tsx` :

   ```tsx
   import { Link } from "react-router-dom";
   import type { InvoiceSummary } from "@kit/shared";
   import { useInvoices } from "@/lib/queries";
   import { DataTable, Money, Page, PageBody, PageHeader, type Column } from "@/ui";

   const columns: Column<InvoiceSummary>[] = [
     { id: "number", header: "Facture", mono: true, cell: (i) => <Link to={`/invoices/${i.id}`}>{i.number}</Link> },
     { id: "client", header: "Client", sortValue: (i) => i.clientName, cell: (i) => i.clientName },
     { id: "days", header: "Retard (j)", numeric: true, sortValue: (i) => i.daysOverdue, cell: (i) => i.daysOverdue },
     { id: "balance", header: "Reste dû", numeric: true, sortValue: (i) => i.balance, cell: (i) => <Money value={i.balance} /> },
   ];

   export default function OverduePage() {
     const { data, isLoading } = useInvoices({ status: "overdue" });
     return (
       <Page>
         <PageHeader title="Retards" count={data?.length} />
         <PageBody flush>
           <DataTable columns={columns} rows={data ?? []} getRowId={(i) => i.id} loading={isLoading} />
         </PageBody>
       </Page>
     );
   }
   ```

2. `app/routes.tsx` : `import OverduePage from "@/pages/overdue";` et `{ path: "overdue", element: <OverduePage /> }`.
3. `app/nav.ts` : une entrée dans le groupe « Finance » (`{ to: "/overdue", label: "Retards", icon: … }`).
4. Nouvelle entité écrite par l'ERP ? Ajoutez sa ligne dans `INVALIDATE` (`queries.ts:232`) et son type d'entité dans
   `ActivityEvent["entity"]` (`packages/shared/src/domain.ts:316`).
5. `make check` (typecheck + garde-fous). Composants : uniquement `@/ui`, jamais `<select>` ni `<input type="date">`.

Pages de référence à copier : `pages/clients` (liste), `pages/client-detail` (fiche), `pages/activity` (flux).

### Pièges

- Un type changé côté Python ne casse pas la compilation web : il faut mettre à jour `packages/shared/src/*.ts` à la main.
- `AppShell` impose `min-w-[1024px]` : l'UI n'est pas faite pour mobile.
- Le chat garde son historique en mémoire du module : recharger la page le perd (le service IA ne le connaît pas).

---

<a id="donnees"></a>
## 7. Données

### Ce que c'est

Le pack de votre entreprise : `DATA_DIR/seed/*.json` (les tables de l'ERP) et `DATA_DIR/context/` (documents
métier). `DATA_DIR=./data` dans le zip d'équipe ; monté en lecture seule dans Docker (`/data`).

### Fichiers clés

`DATA_DIR/seed/*.json`, `DATA_DIR/context/*.md`, `DATA_DIR/context/clients/`, `DATA_DIR/context/suppliers/`,
`apps/backend/app/crud/__init__.py` (`PACK`), `apps/backend/app/core/datapack.py`, `apps/backend/app/services/context.py`.

### Comment ça marche

**Fichiers seed → tables** (`crud/__init__.py:31-50`). Ordres de grandeur du pack de référence :

| Fichier | Table | Contenu | ≈ lignes |
|---|---|---|---|
| `meta.json` | `meta` | `{company, today, currency, generatedAt}` | 1 objet |
| `clients.json` | `clients` | contacts, zone, jours de livraison, conditions, plafond, statut, préférences, notes, tags | 46 |
| `products.json` | `products` | catalogue, unité, prix, coût, alias, DLC | 66 |
| `suppliers.json` / `supplierPrices.json` | `suppliers` / `supplier_prices` | | 10 / 94 |
| `clientPrices.json` | `client_prices` (clé `clientId\|productId`) | prix négociés | 63 |
| `priceRules.json` | `price_rules` | règles de prix (groupes, volume) | 16 |
| `lots.json` / `stockMovements.json` | `lots` / `stock_movements` | stock par lot, mouvements | 3 270 / 15 833 |
| `orders.json` / `purchaseOrders.json` | `orders` / `purchase_orders` | 3 ans de ventes / achats | 2 192 / 696 |
| `invoices.json` / `payments.json` | `invoices` / `payments` | | 1 780 / 544 |
| `routes.json` / `routeRuns.json` | `routes` / `route_runs` | tournées | 6 / 80 |
| `clientEvents.json` / `supplierEvents.json` | `client_events` / `supplier_events` | historique relationnel | 2 015 / 500 |
| `tags.json` | `tags` (clé `scope\|id`) | groupes | 23 |
| `contextEntries.json` | `context_entries` | fiches de contexte | 641 |

Le journal d'activité (`events`) n'est pas dans le pack : il est vide après un reset. Fichier absent = table vide.

**Table de contexte** : une fiche = `{id, entityType, entityId?, kind, title, body (markdown), tags, source}`.

- `entityType` : `company` (pas d'`entityId`) | `client` (`cli_…`) | `supplier` (`sup_…`) | `product` (`prd_…`) |
  `category` (un id de `seed/categories.json`, propre à chaque entreprise ; `GET /api/categories`).
  Vérifié à l'écriture (`services/context.py:_check_target`).
- `kind` : `policy`, `procedure`, `preference`, `fact`, `relationship`, `pricing`, `logistics`, `risk`.
- `source` : `seed` ou l'acteur qui l'a écrite (`user`, `ai_chat`, `voice_agent`, `services/context.py:153`).
- Les anciens packs nomment `entityType` « `scope` » : converti au chargement (`datapack.py:32-36`).
- `GET /api/context/for?entityType=client&id=…` = fiches de l'entité + fiches liées (ce que charge `get_context`).

**Documents `DATA_DIR/context/`** :

- `*.md` du premier niveau (entreprise, journée type, glossaire produits, playbook clients, prix et crédit,
  livraisons) : **collés en entier dans le prompt système** à chaque tour (`prompts.py:89-96`). Modifiables à chaud.
- `clients/*.md`, `suppliers/*.md` : fiches persona pour **l'humain qui joue le client** au téléphone. Elles ne sont
  **pas** lues par l'agent ; ce que l'agent sait d'un client est dans la table de contexte.

**Reset** : `make reset` (= `POST /api/admin/reset`) recharge le seed et vide le journal ; toutes les écritures sont
perdues. `make clean` supprime aussi le volume de base Docker.

### Étendre

Ajouter du savoir pour l'agent : une fiche via l'UI **Contexte**, `POST /api/context`, l'outil `save_context`, ou un
`.md` de plus dans `DATA_DIR/context/` (attention à la taille du prompt). Modifier le seed puis `make reset` pour
repartir de vos propres données.

### Pièges

- Dans Docker, `DATA_DIR` est monté en lecture seule : modifier le seed se fait sur l'hôte, puis `make reset`.
- `make reset` efface aussi tout ce que l'agent a appris (`save_context`) et le journal d'activité.
- Le zip d'équipe utilise `DATA_DIR=./data` (déjà réglé dans votre `.env`).

---

<a id="tests"></a>
## 8. Tests et qualité

### Ce que c'est

Des tests Python hors ligne pour le service IA, un typecheck et des garde-fous pour le web.

### Fichiers clés

`apps/ai/tests/` (`test_clients.py`, `test_speech_providers.py`, `test_tools_and_mock.py`, `test_jev.py`),
`scripts/check-no-native-controls.sh`, `scripts/check-no-native-date.sh`, `apps/backend/tests/parity.py`.

### Comment ça marche

| Commande | Fait | Prérequis |
|---|---|---|
| `make test` | `cd apps/ai && uv run pytest -q` : adaptateurs contre des flux enregistrés, schémas d'outils, mock, Jev — aucun réseau | uv sur la machine |
| `make check` | `pnpm --filter @kit/web typecheck` + `scripts/check-no-native-controls.sh` (pas de `<select>` ni d'`<input type="date">` natifs) | Node 22 + pnpm |
| `make types` | génère `packages/shared/src/generated/{backend,ai}.ts` depuis les deux `/openapi.json` | services lancés, Node + pnpm |

`apps/backend/tests/parity.py` comparait l'ERP Python à une ancienne API TypeScript : il n'est pas utile pendant le
hackathon. Il n'y a pas de tests unitaires backend.

<a id="tester-sans-ui"></a>
### Étendre : tester un outil ou l'agent sans l'UI

```bash
make chat                                   # terminal : appels d'outils et résultats affichés, /reset, /exit
curl -s localhost:4100/tools | python3 -m json.tool | less          # schémas vus par le modèle
curl -N localhost:4100/chat -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"il reste du bar ?"}],"mode":"voice"}'
curl -N localhost:4100/command -H 'content-type: application/json' -d '{"text":"montre-moi le stock de turbot"}'
curl -s localhost:4100/stt -H 'content-type: audio/webm' -H 'x-mock-text: test' --data-binary @/dev/null
```

Un outil seul, en Python (depuis `apps/ai`, ERP lancé) :

```python
# uv run python -c "import asyncio; from app.tools import TOOLS, ToolContext, ErpClient; ..."
import asyncio
from app.tools import TOOLS, ErpClient, ToolContext

ctx = ToolContext(erp=ErpClient("ai_chat", "test"), actor="ai_chat")
print(asyncio.run(TOOLS["get_product_stock"].run({"productId": "prd_0001"}, ctx)))
```

Un test sans ERP : sur le modèle de `test_tool_validates_arguments` (`tests/test_tools_and_mock.py:35`), qui appelle
`tool.run({...}, ctx=None)` sur un outil qui n'utilise pas `ctx`. WebSocket scripté : envoyez `{"type":"start"}` puis
`{"type":"text","text":"…"}` (pas de micro nécessaire).

**Fournisseurs mock** (aucune clé) : `MockLLM` comprend quelques intentions françaises (« c'est la Poissonnerie
Lemoine », « il reste du bar ? », « 4 kg de bar », « confirme la commande »…) et appelle les **vrais** outils, un par
étape (`clients/mock_llm.py`) ; ce n'est pas un modèle d'agent. `MockSTT` renvoie l'en-tête `x-mock-text` s'il est
fourni (`/stt`, `/command`), sinon `MOCK_STT_TEXT`. `MockTTS` renvoie un WAV silencieux de mime `audio/x-mock-wav`.

---

<a id="pieges"></a>
## 9. Pièges connus et limites (vérifiés dans le code)

| # | Piège | Où | Conséquence / contournement |
|---|---|---|---|
| 1 | **Historique vocal en mémoire** (`conversations`) | `services/voice_session.py:68` | perdu à chaque redémarrage du service IA, y compris le rechargement auto d'uvicorn quand vous sauvegardez un fichier de `apps/ai/app` |
| 2 | **Les alertes ne bloquent rien** : client bloqué, plafond de crédit, stock insuffisant, zone non desservie, prix sous le coût = `warnings` | `services/orders.py:85-139`, `:274-276` | `confirm_order` réussit quand même ; c'est au prompt ou à un outil de refuser |
| 3 | **Indice STT vocal optionnel** : `audio_start` accepte `hint`, mais la page Voix n'en envoie pas | `services/voice_session.py`, `features/assistant/useVoiceSession.ts` | sans `hint` : pas de vocabulaire (noms de clients, produits) et le mock STT entend `MOCK_STT_TEXT` ; envoyez `hint` dans `audio_start` pour l'activer |
| 4 | **STT après relâchement** : `transcribe_stream` n'est pas branché | `clients/base.py:81-88` | aucun texte partiel pendant que l'appelant parle |
| 5 | Seuls les `*.md` **du premier niveau** de `DATA_DIR/context/` vont dans le prompt | `agent/prompts.py:92-94` | les fiches `clients/` et `suppliers/` ne sont pas vues par l'agent |
| 6 | `meta` (entreprise, date) **en cache 60 s** côté IA ; `settings` lu une seule fois | `agent/prompts.py:70-86`, `config.py` | changer `.env` exige un redémarrage |
| 7 | **Types TS écrits à la main** ; `make types` écrit dans `generated/`, non exporté | `packages/shared/src/index.ts` | mettez à jour `domain.ts` / `api.ts` / `ai.ts` à chaque changement de schéma |
| 8 | **Barge-in sans rollback** | `services/voice_session.py:158-164` | une écriture ERP partie avant l'interruption reste faite |
| 9 | **Max 8 étapes** puis message d'abandon | `agent/loop.py:38`, `:93-97` | `AGENT_MAX_STEPS` ou outils composites |
| 10 | Commande ⌥Espace **sans mémoire** ; navigation par regex de verbes français + dernière entité vue | `services/command.py:40`, `:121` | « et ajoute 2 kilos » ne sait pas de quelle commande on parle |
| 11 | Le TTS attend une **fin de phrase suivie d'un espace** | `services/voice_session.py:235` | une longue première phrase retarde le premier son ; la dernière phrase part à `finish()` |
| 12 | Blocs `thinking` (Anthropic) et `thoughtSignature` (Gemini) gardés **en mémoire du process**, sans limite | `clients/anthropic.py:22`, `clients/gemini.py` | après redémarrage, un ancien historique de chat est renvoyé sans eux |
| 13 | Base ERP **mono-process**, services synchrones | `core/db.py` | pas de `--workers` ; un calcul lourd bloque l'API |
| 14 | Le mock LLM n'appelle **qu'un outil par étape** | `clients/mock_llm.py` | les mesures de latence en mock ne disent rien du parallélisme réel |
| 15 | L'historique de chat est **renvoyé en entier** à chaque message | `features/assistant/chat-store.ts:86` | il grossit sans limite ; « Nouvelle conversation » le vide |
