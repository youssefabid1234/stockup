# GUIDE-AGENTS.md — construire un bon agent avec le kit

Un guide pour apprendre, pas une référence de code. Chaque section explique **l'idée**, montre **où elle vit dans le
kit**, puis donne des **conseils** concrets. Pour le détail du code (lignes, signatures, extraits), suivez les liens
vers [TECH.md](TECH.md) : ce guide ne le recopie pas.

Pré-requis : le kit tourne ([SETUP.md](SETUP.md)) et vous avez lu le défi ([BRIEF.md](BRIEF.md)). Les chemins de code
ci-dessous partent de `apps/ai/app/`.

## Sommaire

1. [Qu'est-ce qu'un agent ?](#1-quest-ce-quun-agent-)
2. [Le harness](#2-le-harness)
3. [La boucle de l'agent](#3-la-boucle-de-lagent)
4. [Les outils](#4-les-outils)
5. [Le contexte et la mémoire](#5-le-contexte-et-la-mémoire)
6. [Les modèles](#6-les-modèles)
7. [Jev, le modèle de décision](#7-jev-le-modèle-de-décision)
8. [Mesurer et améliorer](#8-mesurer-et-améliorer)
9. [Pièges fréquents](#9-pièges-fréquents)
10. [Pour aller plus loin](#10-pour-aller-plus-loin)

## Je veux… → section

| Je veux… | Section |
|---|---|
| comprendre ce qu'est un agent, vite | [1](#1-quest-ce-quun-agent-) |
| savoir quel fichier fait quoi dans le service IA | [2](#2-le-harness) |
| comprendre pourquoi un tour prend 3 appels au modèle | [3](#3-la-boucle-de-lagent) |
| écrire un nouvel outil qui marche du premier coup | [4](#4-les-outils) |
| que l'agent connaisse mieux le client | [5](#5-le-contexte-et-la-mémoire) |
| réduire le coût et la latence | [3](#3-la-boucle-de-lagent), [5.5](#55-le-cache-de-prompt), [6](#6-les-modèles), [7](#7-jev-le-modèle-de-décision) |
| changer de modèle | [6](#6-les-modèles) |
| décider « oui / non » ou « quel produit » sans LLM | [7](#7-jev-le-modèle-de-décision) |
| prouver que mon agent s'améliore | [8](#8-mesurer-et-améliorer) |
| éviter les erreurs classiques | [9](#9-pièges-fréquents) |

---

## 1. Qu'est-ce qu'un agent ?

### L'idée

Un **LLM** est une fonction : du texte entre, du texte sort. Il ne sait rien de votre ERP, ne lit pas la base, ne
crée pas de commande. Il prédit la suite la plus plausible, ce qui veut dire qu'il **invente** volontiers un prix ou un
stock si on le laisse faire.

Un **agent**, c'est un LLM placé dans une boucle, avec des **outils** (des fonctions qu'il peut demander d'appeler) :

```
   percevoir            décider                agir                 observer
 (message client) ──► (le modèle choisit ──► (le code exécute ──► (le résultat revient
                       un outil ou répond)     l'outil sur l'ERP)    dans la conversation)
        ▲                                                                   │
        └───────────────────────── on recommence ◄──────────────────────────┘
                     jusqu'à ce que le modèle réponde sans outil
```

Le modèle ne fait jamais l'action lui-même : il **demande** `get_price(clientId, productId)`, votre code l'exécute et
lui rend le résultat. C'est ce qui le rend fiable (les chiffres viennent de l'ERP) et contrôlable (vous décidez quels
outils existent et ce qu'ils renvoient).

### Agent ou code simple ?

| Prenez un agent quand… | Prenez du code quand… |
|---|---|
| l'entrée est floue (« le loup comme d'hab', mais moins ») | l'entrée est structurée (un formulaire, un id) |
| le chemin dépend de la réponse (rupture → alternative → accord du client) | le chemin est toujours le même |
| il faut parler, reformuler, négocier | il faut calculer (prix, TVA, dates, unités) |
| on accepte quelques centaines de ms et un coût par tour | chaque milliseconde ou centime compte |

Le bon design est presque toujours **mixte** : le modèle comprend et converse, le code calcule et l'ERP applique les
règles. Dans le kit, aucune règle métier n'est dans l'agent : prix, stock et crédit sont calculés par le backend
(`apps/backend/app/services/`).

### Dans le kit

- La boucle : `agent/loop.py` (`run_agent`).
- Les outils : `tools/` (16 outils, décorateur `@tool`).
- Le mock (`clients/mock_llm.py`) imite un agent sans clé : utile pour développer, inutile pour juger l'intelligence.

### Conseils

- Avant de coder, écrivez l'appel idéal en dialogue (client / agent) et notez **quel outil** sert à chaque réplique.
  Les répliques sans outil possible sont vos prochains outils.
- Tout ce qui est déterministe (convertir « une demi-caisse », calculer « vendredi prochain ») : en code, pas dans le
  prompt.

---

## 2. Le harness

### L'idée

Le modèle n'est qu'une pièce. Le **harness** (harnais), c'est tout ce qu'il y a autour : la construction du prompt,
le registre des outils, la boucle, l'historique, le streaming, la gestion des erreurs et les limites. Deux équipes
avec le même modèle obtiennent des agents très différents selon leur harness. C'est là que vous gagnerez le plus.

### Dans le kit

```
         page Voix (WS /ai/voice)    assistant ⌘J (POST /ai/chat)    ⌥Espace (POST /ai/command)
                    │                          │                              │
        services/voice_session.py        routers/chat.py              services/command.py
        STT → agent → TTS par phrase     historique = navigateur      un seul tour, sans mémoire
        historique en mémoire (~40 msg)            │                              │
                    └──────────────┬───────────────┴──────────────────────────────┘
                                   ▼
                    agent/loop.py   run_agent(messages, llm, tools, mode)
                    ┌──────────────────────────────────────────────────────────┐
                    │ agent/prompts.py  build_system_prompt(mode)              │
                    │   rôle + BASE_RULES + règles du mode + date ERP          │
                    │   + tous les DATA_DIR/context/*.md                       │
                    │                                                          │
                    │ boucle ≤ AGENT_MAX_STEPS :                               │
                    │   llm.stream(LLMRequest) ──► texte (streamé) / appels    │
                    │   appels ──► execute_tool en parallèle ──► messages tool │
                    └───────────┬───────────────────────────────┬──────────────┘
                                ▼                               ▼
               clients/factory.py → get_llm_client()     tools/registry.py  TOOLS, @tool
               clients/anthropic.py · openai.py ·        tools/catalog.py · context.py ·
               gemini.py · mock_llm.py (httpx brut)      history.py · orders.py
                                                                 │ ctx.erp (tools/erp.py, x-actor)
                                                                 ▼
                                                         ERP API :4000 (règles métier)
```

| Pièce du harness | Fichier | Détail |
|---|---|---|
| assemblage du prompt | `agent/prompts.py` | [TECH 4.3](TECH.md#prompts) |
| registre des outils | `tools/registry.py`, `tools/__init__.py` | [TECH 5.1](TECH.md#decorateur) |
| boucle, erreurs, limite d'étapes | `agent/loop.py` | [TECH 4.4](TECH.md#boucle) |
| historique | dépend du mode (navigateur, session vocale, aucun) | [TECH 4.4](TECH.md#boucle) |
| streaming texte et voix | `clients/*.py`, `services/voice_session.py` | [TECH 4.5](TECH.md#latence), [4.6](TECH.md#session-voix) |
| choix du fournisseur | `clients/factory.py`, `config.py` | [TECH 4.1](TECH.md#config-ia) |

### Conseils

- Le harness est à vous : tout se modifie. Les leviers les plus rentables sont souvent le prompt, les outils et ce qui
  est mis dans le contexte, pas le modèle.
- Changez une pièce à la fois et mesurez (section [8](#8-mesurer-et-améliorer)).

---

## 3. La boucle de l'agent

### L'idée

Un **tour** (ce que dit le client → ce que répond l'agent) contient une ou plusieurs **étapes**. Chaque étape est un
appel complet au modèle, qui relit tout : prompt système, outils, historique et résultats d'outils déjà obtenus.
Chaque étape en plus ajoute donc de la **latence** (un aller-retour réseau + génération) et du **coût** (tout le
contexte est refacturé en entrée).

### Dans le kit, pas à pas (`agent/loop.py`)

1. `run_agent` construit le prompt système une fois par tour (`build_system_prompt`) et une `LLMRequest` qui pointe
   sur la liste `messages`.
2. **Étape** : `llm.stream(request)` émet du texte (`LLMText`, streamé tout de suite vers l'UI ou le TTS), des appels
   d'outils (`LLMToolCall`, des blocs `tool_use` chez Anthropic) et la consommation (`LLMUsage`).
3. **Pas d'appel d'outil** → c'est la réponse finale : événement `done`, fin du tour.
4. **Des appels** → le message `assistant` (avec ses `tool_calls`) est ajouté, puis **tous les outils demandés
   tournent en parallèle** (`asyncio.gather`). Chaque résultat devient un message `tool` (JSON compact) et on revient
   en 2.
5. **Erreurs d'outil** : `execute_tool` ne lève jamais. Outil inconnu, arguments invalides, refus de l'ERP → le modèle
   reçoit `{"error": "…"}` et peut expliquer ou réessayer.
6. **Limite** : au-delà de `AGENT_MAX_STEPS` (8 par défaut), message `GIVE_UP`.
7. **Annulation** : quand le client coupe la parole (barge-in) ou se déconnecte, la tâche asyncio est annulée et la
   boucle s'arrête sans rien émettre. Une écriture ERP déjà partie reste faite.

Détail ligne à ligne : [TECH 4.4](TECH.md#boucle).

### Ce que coûte une étape (mesuré)

Test réel avec les clés d'équipe (novembre 2026), Claude Sonnet 5.5, avant cache de prompt :

| Tour | Étapes | Tokens d'entrée |
|---|---|---|
| question de stock simple | 2 appels au modèle | ≈ 54 000 (≈ 27 000 par appel) |
| prise de commande | plusieurs appels | ≈ 117 000 |

Presque tout vient du prompt système (règles + documents de l'entreprise) renvoyé à **chaque** étape. Sonnet 5.5 a
choisi les bons outils, prix et dates à chaque fois : la qualité n'était pas le problème, le volume l'était. Le
cache de prompt, désormais actif pour Anthropic, fait payer ce préfixe à tarif réduit (section [5.5](#55-le-cache-de-prompt)) ;
il ne réduit pas le nombre d'étapes.

### Conseils

- Comptez les étapes de vos scénarios (événements `tool_call` dans le flux). Une étape de moins vaut souvent mieux
  qu'un modèle plus rapide.
- Demandez au modèle (dans le prompt) d'appeler **en même temps** les outils indépendants : la boucle les exécute
  déjà en parallèle.
- Un outil composite (section [4](#4-les-outils)) remplace deux ou trois étapes.
- Ne montez pas `AGENT_MAX_STEPS` pour masquer une boucle : si un tour dépasse 4–5 étapes, c'est un outil ou une
  règle de prompt qui manque.

---

## 4. Les outils

### L'idée

Pour le modèle, un outil n'est que trois choses : un **nom**, une **description** et un **schéma JSON** des
paramètres. Il ne voit jamais votre code. Il décide d'appeler l'outil uniquement d'après la description, et remplit
les arguments d'après le schéma. Puis il lit le résultat, en entier, à chaque étape suivante.

Conséquence : un outil se conçoit comme une API pour un collègue pressé qui lit seulement la doc.

### Dans le kit

- `@tool` (`tools/registry.py`) transforme une fonction `async` en outil : nom de la fonction → nom, docstring →
  description, paramètres annotés → schéma (camelCase pour le modèle), `Field(description=…)` → description du
  paramètre, `Literal[…]` → enum. Les arguments reçus sont validés par Pydantic. Détail : [TECH 5.1](TECH.md#decorateur).
- Les 16 outils sont dans `tools/catalog.py`, `context.py`, `history.py`, `orders.py` ([TECH 5.2](TECH.md#outils)).
- `curl -s localhost:4100/tools` montre exactement ce que le modèle reçoit.

### Écrire un bon outil

| Règle | Pourquoi | Exemple dans le kit |
|---|---|---|
| La description dit **quand** l'utiliser, et cite les outils voisins | le modèle choisit sur la description | `save_context` : « Pas pour une réclamation (utilise log_client_event) » |
| Paramètres décrits avec un exemple d'id | moins d'arguments mal formés | `client_id: str = Field(description="ex. cli_0012")` |
| `Literal` dès que les valeurs sont fermées | le modèle ne peut pas inventer une valeur | `search(types=…)`, `get_context(entity_type=…)` |
| Sortie **petite** : seulement les champs utiles | chaque octet est relu à chaque étape, et en voix il reste dans l'historique | `pick(...)`, `[:5]`, `summarize_order`, `compact` |
| Renvoyer les **ids** dont l'étape suivante a besoin | le modèle n'invente pas d'id s'il en a un sous les yeux | `search` renvoie `id` ; `summarize_order` renvoie `lineId` |
| Un outil **composite** pour un enchaînement fréquent | un appel HTTP local coûte des ms, une étape modèle des centaines | `quote_product` dans [TECH 5.4](TECH.md#outil-composite) |
| Écritures **sûres à rejouer** et en deux temps | le modèle réessaie après une erreur ; une confirmation ne s'annule pas | `create_draft_order` puis `confirm_order` |
| Lever une exception avec un message français | le modèle lit `{"error": …}` et peut l'expliquer au client | `ErpError` (`tools/erp.py`) |
| Pas de règle métier dans l'outil | une seule vérité : le backend | les prix viennent de `/api/prices/resolve` |

**Ids plutôt que noms** : le modèle trouve l'entité avec `search` (recherche floue), puis travaille avec l'id. Ne
créez pas d'outil qui prend un nom de client « tel que dit » et devine : la recherche floue renvoie plusieurs
candidats, et c'est au modèle (ou à Jev, section [7](#7-jev-le-modèle-de-décision)) de demander « lequel ? ».

### Anti-patterns

- Un outil `query_erp(path)` générique : le modèle invente des routes et lit des objets ERP bruts énormes.
- Renvoyer l'objet ERP complet « au cas où » : des milliers de tokens relus à chaque étape.
- Deux outils aux descriptions presque identiques : le modèle hésite ou alterne.
- Un outil qui confirme une commande sans récapitulatif accepté (voir [9](#9-pièges-fréquents)).
- Renvoyer `{"ok": false}` sans message : le modèle ne sait pas quoi dire.

### Mini-exemple : de la mauvaise à la bonne version

Mauvais : description vague, objet brut, rien ne dit quand l'utiliser.

```python
@tool
async def client_info(ctx: ToolContext, name: str) -> dict:
    """Infos client."""
    hits = await ctx.erp.get("/api/search", {"q": name, "types": "client"})
    return await ctx.erp.get(f"/api/clients/{hits[0]['id']}")   # devine le 1er, renvoie tout
```

Bon : prend un id, dit quand l'utiliser, renvoie peu.

```python
@tool
async def get_client_credit(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Situation de paiement d'un client : encours, retard, plafond, statut. À utiliser avant d'accepter une grosse
    commande ou quand le client demande pourquoi il est bloqué. Pour la fiche complète : get_client. Client credit status.
    """
    c = await ctx.erp.get(f"/api/clients/{enc(client_id)}")
    return pick(c, "status", "outstanding", "overdue", "creditLimit", "paymentTermsDays")
```

Puis l'importer dans `tools/__init__.py` et vérifier avec `curl -s localhost:4100/tools`. Pas à pas complet :
[TECH 5.3](TECH.md#ajouter-outil).

### Conseils

- Testez un outil seul avant de le donner au modèle : `await TOOLS["nom"].run({...}, ctx)` ([TECH 8](TECH.md#tester-sans-ui)).
- Si le modèle n'appelle pas votre outil, réécrivez la description avant de toucher au prompt.
- Une confirmation irréversible = un outil séparé + une règle de prompt explicite (`BASE_RULES` le fait déjà pour
  `confirm_order`).

---

## 5. Le contexte et la mémoire

### 5.1 L'idée : la fenêtre de contexte

Le modèle n'a pas de mémoire entre deux appels. Tout ce qu'il « sait » à une étape est dans la requête : prompt
système + définitions d'outils + historique + résultats d'outils. Cette requête se mesure en **tokens** (≈ 3 à 4
caractères en français) et elle a une taille maximale, la **fenêtre de contexte**. Bien avant la limite, un contexte
trop gros coûte cher, ralentit le premier token et dilue l'attention : le modèle rate plus facilement la règle
importante noyée au milieu.

### 5.2 Le prompt système du kit

`build_system_prompt(mode, actor_name)` (`agent/prompts.py`) assemble, à chaque tour :

| Partie | Contenu |
|---|---|
| `ROLE` | « assistant IA de l'ERP de {entreprise} », l'activité |
| `BASE_RULES` | outils pour toute donnée, `search` d'abord, `get_price` pour un prix, contexte avant de répondre, brouillon puis confirmation explicite, alertes |
| `MODE_RULES[mode]` | `CHAT_RULES` (markdown léger), `VOICE_RULES` (1–2 phrases, nombres en toutes lettres, récapituler), `COMMAND_RULES` (agir tout de suite, une phrase) |
| date | `meta.today` de l'ERP, en français (les données ont leur propre date simulée) |
| interlocuteur | `actor_name` |
| contexte entreprise | **tous** les `DATA_DIR/context/*.md` du premier niveau, relus à chaque tour |

Détail : [TECH 4.3](TECH.md#prompts).

### 5.3 L'historique, selon le mode

| Mode | Qui garde l'historique |
|---|---|
| `chat` | le navigateur, renvoyé en entier à chaque message |
| `voice` | le service IA, en mémoire, coupé à ~40 messages (`trim` dans `services/voice_session.py`) |
| `command` | personne : un seul message par requête |

`run_agent` **ajoute** ses messages à la liste qu'on lui passe : qui garde la liste garde la mémoire. Les résultats
d'outils y restent aussi, d'où l'intérêt de sorties petites.

### 5.4 Récupérer plutôt que tout charger

Deux stratégies pour donner du savoir au modèle :

- **Tout mettre dans le prompt** (stuffing) : c'est ce que fait le kit avec `DATA_DIR/context/*.md`. Simple, toujours
  disponible, mais payé à chaque étape de chaque tour.
- **Aller chercher ce qu'il faut** (retrieval) : la **table de contexte** de l'ERP, via trois outils de
  `tools/context.py` :
  - `get_context(entity_type, id)` : tout ce qu'on sait d'un client, fournisseur, produit ou rayon ;
  - `search_context(query, …)` : recherche plein texte dans les fiches (règles, procédures) ;
  - `save_context(…)` : mémoriser un fait durable appris pendant l'appel (mémoire long terme partagée avec l'équipe).

Les fiches `data/context/clients/` et `suppliers/` ne sont **pas** dans le prompt (seul le premier niveau l'est) :
l'agent les voit via la table, s'il pense à appeler `get_context`.

### 5.5 Le cache de prompt

**L'idée.** D'une étape à l'autre, le début de la requête (outils + prompt système + début de l'historique) est
identique. Le cache de prompt du fournisseur garde ce **préfixe** déjà traité : à l'appel suivant, les tokens en cache
sont relus beaucoup plus vite et facturés à une fraction du prix normal (environ 10 % chez Anthropic ; l'écriture
initiale coûte un peu plus qu'un token normal ; voir la page de prix du fournisseur). Le cache Anthropic utilisé ici
dure 5 minutes.

**Dans le kit.** L'adaptateur `clients/anthropic.py` pose trois points de cache (`cache_control`) : sur le dernier
outil, sur le prompt système et sur le dernier bloc de la conversation (`mark_last_block`). L'étape suivante du même
tour (après un outil) et le tour suivant relisent donc tout le préfixe depuis le cache. Les autres fournisseurs gèrent
leur cache à leur façon (ou pas) : regardez leur documentation.

**Pourquoi ça compte ici.** ≈ 27 000 tokens d'entrée par appel, dont l'essentiel est le même préfixe ; un tour de
commande en relit ≈ 117 000. Sans cache, vous payez ce préfixe plein tarif à chaque étape. Avec cache, la 2ᵉ étape
d'un tour et les tours suivants d'un même appel le relisent presque gratuitement, et le premier token arrive plus tôt.

**Ce qui casse le cache.** Le cache ne marche que sur un préfixe **identique octet pour octet**. Tout changement
invalide ce qui suit :

- modifier un `.md` de `DATA_DIR/context/`, une règle de `prompts.py`, une description d'outil ;
- ajouter, retirer ou réordonner des outils (chez Anthropic, l'ordre du préfixe est : outils, puis système, puis
  messages) ;
- mettre dans le prompt système quelque chose qui change à chaque tour (une heure, un compteur, la fiche du client
  courant **avant** les règles stables) ;
- changer de mode ou d'interlocuteur (`actor_name` est dans le prompt).

Mettez donc le stable en premier et le variable à la fin (dans les messages, ou en dernière partie du prompt).

**Voir les hits.** Regardez `usage` dans l'événement `done` (champs `cache_read_input_tokens` et
`cache_creation_input_tokens` en Python, `cacheReadInputTokens` / `cacheCreationInputTokens` dans le JSON de
`/ai/chat`) ; `make chat` les affiche (« cache lu … / écrit … »). Les tokens lus en cache doivent être élevés dès la
2ᵉ étape d'un tour ; s'ils restent à 0, quelque chose change dans votre préfixe. Attention : avec le cache,
`input_tokens` ne compte plus que la partie **non** cachée (total = `input_tokens` + écrits + lus).

### Conseils

- Mesurez la taille de votre prompt avant de l'enrichir : chaque Ko ajouté est payé à chaque étape.
- Préchargez ce qui est sûr d'être utile (la fiche du client identifié en début d'appel) **à la fin** du prompt, et
  laissez le reste en retrieval.
- Pour un long appel vocal, un résumé des tours anciens vaut mieux que 40 messages bruts.
- Utilisez `save_context` pour ce qui doit survivre à l'appel (« livrer par la porte de service ») ; pas pour une
  réclamation (`log_client_event`).

---

## 6. Les modèles

### L'idée

Trois curseurs : **intelligence**, **latence**, **coût**. Pour un agent vocal, la latence au premier mot compte autant
que l'intelligence. Les modèles récents « réfléchissent » avant de répondre (raisonnement interne) : on ne règle plus
la température, on règle **l'effort** de réflexion.

### Dans le kit

| Modèle Anthropic | Profil (`.env.example`) |
|---|---|
| `claude-sonnet-5-5` | défaut, équilibré (`DEFAULT_MODELS` dans `clients/factory.py`) |
| `claude-haiku-5-5` | le plus rapide, le moins cher |
| `claude-opus-5-5` | le plus intelligent, le plus lent |

Prix : le kit n'en donne pas, voir la page de prix du fournisseur. Coût d'un tour ≈ tokens d'entrée × prix d'entrée
+ tokens de sortie × prix de sortie (+ tarif réduit pour les tokens lus en cache).

- **Changer de modèle** : dans `.env`, `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-haiku-5-5`, puis `make restart`
  (Docker) ou relancer `make dev`. `GET /ai/health` affiche le modèle actif. Autres fournisseurs (OpenAI, Gemini, tout
  endpoint compatible OpenAI) : [TECH 4.1](TECH.md#config-ia).
- **Effort** : `LLM_EFFORT` (`low` par défaut, `medium`, `high`), envoyé par `clients/anthropic.py` en
  `output_config.effort`. `low` garde la voix rapide ; montez-le pour un tour difficile.
- **Streaming** : tous les clients streament ; le texte part vers le TTS phrase par phrase.
- **Réflexion** : l'adaptateur Anthropic renvoie les blocs `thinking` avec le tour qui appelle des outils (exigé par
  les modèles récents).

### Router entre modèles

Un seul client LLM est construit (`get_llm_client()`, mis en cache). Pour router, construisez-en un second avec
`make_llm_client(LLMSettings(...))` et choisissez par tour :

- petit modèle (Haiku) pour les tours simples : « il reste du bar ? », « merci, au revoir » ;
- gros modèle (Sonnet / Opus) pour la négociation, les réclamations, les commandes à plusieurs lignes ;
- le **routeur** peut être une règle, ou une décision Jev (section [7](#7-jev-le-modèle-de-décision)).

**Repli** : si le fournisseur renvoie une erreur (quota, panne), `run_agent` émet un événement `error`. Vous pouvez
rattraper ça dans l'appelant et relancer le tour sur un autre client.

### Conseils

- Comparez les modèles sur **vos** scénarios (section [8](#8-mesurer-et-améliorer)), pas sur une impression.
- Avant de changer de modèle, réduisez le contexte et le nombre d'étapes : c'est souvent plus de gain.
- Le mock (`LLM_PROVIDER=mock`) n'appelle qu'un outil par étape : ses latences ne disent rien du vrai modèle.

---

## 7. Jev, le modèle de décision

### L'idée

Jev (TypeSafe AI, modèle `jev-latest`) n'est **pas un LLM** : il n'écrit pas de texte. Vous lui donnez un **état**
(une phrase ou du JSON) et des **questions typées** ; il renvoie, pour chacune, une décision **avec des
probabilités**. La probabilité est son atout : quand il hésite, vous le savez, et l'agent peut demander au client au
lieu de deviner.

| Type | Vous envoyez | Vous recevez |
|---|---|---|
| choix (`choose`) | des options `{id: description}` | `choice`, `confidence`, `probabilities` |
| score (`score`) | des niveaux ordonnés | `score` (ex. 1,7), `confidence` |
| oui / non (`yes_no`) | une affirmation à vérifier | probabilité de « oui », 0..1 |
| plusieurs à la fois (`ask`) | un dict de questions | toutes les réponses en un appel |

### Quand l'utiliser à la place d'un appel LLM

- **Quel produit le client voulait dire** parmi les résultats de `search` (« le bar de ligne », pas « le bar
  d'élevage »).
- **Confirmation oui / non** après un récapitulatif (« ouais vas-y » = oui ; « euh… plutôt le gros » = incertain).
- **Routage d'intention** : commande, question de stock, réclamation, prix → quel prompt, quels outils, quel modèle.
- **Scorer** : urgence, mécontentement, risque.

Gardez le LLM pour **parler** et pour les décisions ouvertes.

### Latence mesurée

Test réel (novembre 2026) : `choose` ≈ 750 ms (752 ms, premier appel, à froid), `yes_no` ≈ 170 ms (168 ms). Plus
rapide qu'une étape LLM avec 27 000 tokens de contexte, mais pas gratuit : mesurez-le dans votre parcours, et lancez-le
**en parallèle** d'autre chose quand c'est possible.

### Dans le kit

- Client : `clients/jev.py` (`JevClient` : `ask`, `choose`, `score`, `yes_no` ; constructeurs de questions
  `choice_question`, `score_question`, `yes_no_question`).
- Accès : `get_jev_client()` renvoie un `JevClient`, ou `None` si `JEV_API_KEY` est vide.
- Exemples à copier : `agent/jev_examples.py`
  - `pick_product(jev, utterance, candidates)` → l'id du produit, ou `None` si la confiance est < 0,6 ;
  - `is_yes(jev, question, answer)` → `True` / `False` / `None` (≥ 0,8 oui, ≤ 0,2 non, sinon incertain).
- **Rien dans l'agent par défaut n'appelle Jev** : à vous de le brancher. Format et usages :
  [TECH 4.7](TECH.md#jev), [apps/ai/README.md, Jev](apps/ai/README.md#jev-decision-model).

### Combiner Jev et le LLM : « Jev décide, le LLM parle »

Deux façons simples :

1. **Dans un outil** : un outil composite appelle `search`, puis `pick_product` ; si Jev est sûr, il renvoie le
   produit, sinon `{"ambiguous": true, "candidates": [...]}` et le LLM demande « lequel ? ».
2. **Avant la boucle** : dans `services/voice_session.py`, quand la dernière question de l'agent était un
   récapitulatif, `is_yes` sur la réponse du client ; si `True`, vous pouvez confirmer directement. Si `None`, laissez
   le LLM reformuler.

### Conseils

- Décrivez les options (`{"prd_1": "Bar de ligne 1-2 kg, Bretagne"}`) plutôt que de donner des ids nus.
- Fixez un seuil de confiance et gérez le cas « incertain » : c'est là que Jev rend l'agent plus sûr.
- Gardez toujours le chemin sans Jev qui marche (`if jev:`) : la clé peut manquer.

---

## 8. Mesurer et améliorer

### L'idée

Sans mesure, on « améliore » au hasard. Un agent se mesure sur trois axes, les mêmes que le jury : **réussite**
(la bonne action dans l'ERP), **latence**, **coût**.

### Ce que le kit mesure déjà

| Mesure | Où la lire |
|---|---|
| tokens d'entrée, de sortie et de cache du tour | `usage` de l'événement `done` (`POST /ai/chat`, `make chat`) |
| durée totale du tour | `ms` de l'événement `done` |
| durée de chaque outil | `ms` de chaque `tool_result` |
| latence vocale détaillée | `timings` de `agent_done` (voix) et de `done` (`/command`) : `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`, `totalMs` |
| ce que l'agent a écrit | le journal d'activité de l'ERP (en violet), `x-actor` |

Le service IA n'a pas de journalisation : si vous voulez un historique de mesures, écrivez chaque événement `done`
dans un fichier JSONL depuis l'appelant.

### Construire un jeu de scénarios

1. Partez des documents de **votre** entreprise (`data/context/*.md`, fiches `clients/`) : chaque règle, préférence
   ou litige est un scénario potentiel (« ce chef refuse les substitutions », « ce client est bloqué pour impayés »).
2. Écrivez 5 à 10 scénarios : ce que dit le client, et le **résultat attendu dans l'ERP** (commande brouillon avec
   telles lignes, aucune confirmation, une réclamation enregistrée…). Incluez des cas difficiles : client ambigu,
   rupture, changement d'avis, client bloqué.
3. Rejouez-les en texte (`make chat`, `curl /ai/chat`) : c'est plus rapide et reproductible que la voix. Gardez la voix
   pour la latence et le naturel.
4. Notez pour chacun : réussi oui/non, nombre d'étapes, tokens, `ms`. `make reset` remet l'ERP à zéro entre deux
   passes.

### Itérer

- **Un changement à la fois**, puis rejouez **le scénario qui échoue** ; tout le jeu une fois à la fin.
- Attaquez le pire des trois axes en premier.
- Consignez chaque essai (gardé ou abandonné) dans `DECISIONS.md` avec ses mesures : le jury le lit.
- Tests automatiques hors ligne : `apps/ai/tests/` ([TECH 8](TECH.md#tests)).

---

## 9. Pièges fréquents

| Piège | Symptôme | Parade |
|---|---|---|
| **Id halluciné** | `{"error": "… introuvable"}`, ou pire : la mauvaise entité | toujours `search` d'abord ; outils qui renvoient les ids utiles ; jamais d'id dans un exemple de prompt qui ressemble à un vrai |
| **Boucle d'outils** | même outil appelé 3 fois, puis `GIVE_UP` | message d'erreur clair dans l'outil ; règle « si l'outil échoue deux fois, dis-le au client » ; outil composite |
| **Sorties d'outil énormes** | tokens qui explosent, réponses lentes | `pick`, listes coupées, textes raccourcis |
| **Prompt qui gonfle** | chaque tour plus lent et plus cher, règles ignorées | contexte en retrieval, cache de prompt intact ([5.5](#55-le-cache-de-prompt)), revue régulière des `.md` |
| **Commande confirmée sans relecture** | `confirm_order` appelé avant l'accord du client | récapitulatif oral + accord explicite (`VOICE_RULES`), ou `is_yes` de Jev |
| **Alertes ignorées** | commande confirmée pour un client bloqué | l'ERP renvoie des `warnings` mais **ne bloque rien** : le prompt ou un outil doit refuser ([TECH 9](TECH.md#pieges)) |
| **Préférences client ignorées** | substitution proposée à un client qui les refuse | `get_context` sur le client en début d'appel (ou préchargé) |
| **Mauvaise date** | « demain » calculé sur la vraie date | utiliser `meta.today` (déjà dans le prompt) |
| **Ids et markdown lus à voix haute** | « c, l, i, underscore… » | `VOICE_RULES` ; vérifier le texte de `agent_done` |
| **Écriture faite malgré l'interruption** | le client a coupé, la ligne est quand même ajoutée | pas de rollback au barge-in : relire la commande en fin d'appel |
| **Historique vocal perdu** | l'agent oublie tout après une sauvegarde de fichier | l'historique vocal est en mémoire ; le rechargement auto d'uvicorn le vide |
| **Mesures en mock** | latences excellentes en dev, mauvaises en démo | mesurer avec les vraies clés |

Liste complète des limites vérifiées dans le code : [TECH 9](TECH.md#pieges).

---

## 10. Pour aller plus loin

- **Orchestrateur et agents spécialisés** : un agent principal qui délègue à un agent « commande », un agent
  « réclamation », chacun avec moins d'outils et un prompt plus court.
- **État de dialogue** : pour la prise de commande, un petit état structuré (client, lignes, date, confirmé ?) tenu
  par le code, que le modèle lit et met à jour, plutôt que de tout reconstruire depuis l'historique.
- **Planification** : faire écrire au modèle un plan court avant d'agir sur une demande complexe, puis l'exécuter.
- **Évaluations automatiques** : rejouer les scénarios à chaque changement, et faire noter le naturel d'une réponse
  par un modèle « juge » avec une grille fixe.
- **Voix plus rapide** : STT en streaming (`transcribe_stream`, déjà implémenté pour Soniox et Deepgram), phrases
  d'attente pendant les outils ([TECH 4.5](TECH.md#latence)).
- **Mémoire** : résumer les appels passés d'un client dans la table de contexte avec `save_context`.
