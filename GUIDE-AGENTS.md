# GUIDE-AGENTS.md — build a good agent with the kit

A guide to learning, not a code reference. Each section explains ** the idea**, shows ** where she lives in the
kit**, then gives concrete **advices**. For the details of the code (lines, signatures, extracts), follow the links
to [TECH.md](TECH.md): this guide does not copy it.

Prerequisites: the kit runs ([SETUP.md](SETUP.md)) and you have read the challenge ([BRIEF.md](BRIEF.md)).
below start from `apps/ai/app/`.

## Contents

1. [What is an agent?](#1-what-is-an-agent)
2. [The harness](#2-the-harness)
3. [The loop of Agent ](#3-agents-loop)
4. [Tools](#4-tools)
5. [The context and memory](#5-context-and-memory)
6. [Models](#6-models)
7. [Jev, decision model](#7-jev-the-decision-model)
8. [Measure and improve ](#8-measuring-and-improving)
9. [Frequent traps](#9-common-traps)
10. [To go further](#10-to-go-further)

## I want... → section

| I want... | Section |
|---|---|
| understand what an agent is, quickly | [1](#1-what-is-an-agent) |
| know which file does what in the AI service | [2](#2-the-harness) |
| understand why a spin takes 3 model calls | [3](#3-agents-loop) |
| write a new tool that works at the first stroke | [4](#4-tools) |
| the agent knows the client better | [5](#5-context-and-memory) |
| reduce cost and latency | [3](#3-agents-loop), [5.5](#55-quick-cache), [6](#6-models), [7](#7-jev-the-decision-model) |
| change model | [6](#6-models) |
| decide "yes/no" or "what product" without LLM | [7](#7-jev-the-decision-model) |
| prove that Mon agent is improving | [8](#8-measuring-and-improving) |
| Avoiding conventional mistakes | [9](#9-common-traps) |

---

## 1. What is an agent?

### The idea

A **LLM** is a function: text enters, text exits. It does not know anything about your ERP, does not read the database, does not
creates no order. It predicts the most plausible sequel, which means that it **invents** willingly a price or a price
stock if we let him do it.

A **Agent** is a LLM placed in a loop, with **tools** (functions it can ask to call):

```
   percevoir            décider                agir                 observer
 (message client) ──► (le modèle choisit ──► (le code exécute ──► (le résultat revient
                       un outil ou répond)     l'outil sur l'ERP)    dans la conversation)
        ▲                                                                   │
        └───────────────────────── on recommence ◄──────────────────────────┘
                     jusqu'à ce que le modèle réponde sans outil
```

The model never does the action itself: it ** requests** `get_price(clientId, productId)`, your code executes it and
makes it the result. This is what makes it reliable (the numbers come from the ERP) and controllable (you decide which
tools exist and what they return).

### Agent or simple code?

| Take an agent when... | Take some code when... |
|---|---|
| the entrance is blurred ("the wolf as usual, but less") | the entry is structured (a form, an id) |
| the path depends on the response (rupture → alternative → customer agreement) | the path is always the same |
| we have to talk, reformulate, negotiate. | you have to calculate (price, VAT, dates, units) |
| we accept a few hundred ms and a cost per turn | each millisecond or centime counts |

The good design is almost always **mixte**: the model includes and converses, the code calculates and the ERP applies the
rules. In the kit, no business rules are in the agent: price, stock and credit are calculated by the backend
(`apps/backend/app/services/`).

### In the kit

- The loop: `agent/loop.py` (`run_agent`).
- Tools: `tools/` (16 tools, `@tool` decorator).
- The mock (`clients/mock_llm.py`) mimics a keyless agent: useful to develop, useless to judge intelligence.

### Advice

- Before encode, write the ideal call in dialog (client/agent) and note ** which tool** is used for each replica.
  Replica without tools possible are your next tools.
- All that is deterministic (convert "a half cash", calculate "next Friday") : in code, not in the
  prompt.

---

## 2. The Harness

### The idea

The model is only a piece. The **harness** (harness) is all around: the construction of the rapid,
tools registry, loop, history, streaming, error management and boundaries.
with the same model get very different agents according to their harness. That's where you'll gain the most.

### In the kit

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

| Harness piece | File | Detail |
|---|---|---|
| assembly of the prompt | `agent/prompts.py` | [TECH 4.3](TECH.md#prompts) |
| register of tools | `tools/registry.py`, `tools/__init__.py` | [TECH 5.1](TECH.md#decorateur) |
| loop, errors, step limit | `agent/loop.py` | [TECH 4.4](TECH.md#boucle) |
| historical background | depends on mode (navigator, voice session, none) | [TECH 4.4](TECH.md#boucle) |
| streaming text and voice | `clients/*.py`, `services/voice_session.py` | [TECH 4.5](TECH.md#latence), [4.6](TECH.md#session-voix) |
| choice of supplier | `clients/factory.py`, `config.py` | [TECH 4.1](TECH.md#config-ia) |

### Advice

- The harness is yours: everything changes. The most profitable levers are often the prompt, the tools and what you want.
  is put in context, not the model.
- Change one piece at a time and measure (section [8](#8-measuring-and-improving)].

---

## 3. Agent's loop

### The idea

A **tour** (as the client → says the agent answers) contains one or more ** steps**. Each step is a
a complete call to the model, which reads everything: rapid system, tools, history and results of tools already obtained.
Each step in addition adds **latency** (a network return + generation) and **cost** (all the
context is rebilled as input).

### In the kit, step by step (`agent/loop.py`)

1. `run_agent` builds the quick system once per turn (`build_system_prompt`) and a `LLMRequest` that points
   on list `messages`.
2. **Step**: `llm.stream(request)` issues text (`LLMText`, streamed immediately to UI or TTS), calls
   tools (`LLMToolCall`, `tool_use` blocks at Anthropic) and consumption (`LLMUsage`).
3. **No tool call** → is the final answer: event `done`, end of round.
4. **Calls** → message `assistant` (with its `tool_calls`) is added, then ** all the requested tools
   turn in parallel** (`asyncio.gather`). Each result becomes a `tool` message (JSON compact) and we return
   in 2.
5. ** Tool Errors**: `execute_tool` never lifts. Unknown tool, invalid arguments, ERP → refusal model
   receives `{"error": "…"}` and can explain or try again.
6. **Limit**: beyond `AGENT_MAX_STEPS` (default 8), message `GIVE_UP`.
7. **Cancellation**: When the client shuts down (barge-in) or disconnects, the asyncio task is cancelled and the
   loop stops without issuing anything. A ERP write already left remains made.

Line detail: [TECH 4.4](TECH.md#boucle).

### What a step costs (measured)

Real test with team keys (November 2026), Claude Sonnet 5.5, before prompt cache:

| Tower | Steps | Tokens |
|---|---|---|
| simple stock issue | 2 Model Calls | ≈ 54 000 (≈ 27 000 by call) |
| command socket | several calls | ≈ 117 000 |

Almost everything comes from the prompt system (rules + company documents) returned to **each** step. Sonnet 5.5 a
chosen the right tools, prices and dates each time: quality was not the problem, the volume was.
Quick cache, now active for Anthropic, charges this prefix at reduced rate (section [5.5](#55-quick-cache)]);
it does not reduce the number of steps.

### Advice

- Count the steps of your scenarios (`tool_call` events in the stream). One step less often is better
  than a faster model.
- Ask the model (in the prompt) to call ** at the same time** independent tools: the loop runs them
  already in parallel.
- A composite tool (section [4](#4-tools)) replaces two or three steps.
- Don't go up `AGENT_MAX_STEPS` to hide a loop: if a turn exceeds 4–5 steps, it's a tool or a tool
  Missing prompt rule.

---

## 4. Tools

### The idea

For the model, a tool is only three things: a **nom**, a **description** and a **schema JSON** of the
settings. It never sees your code. It decides to call the tool only according to the description, and fills in
the arguments according to the diagram. Then it reads the result, in whole, at each next step.

Consequence: A tool is conceived as a API for a colleague in a hurry who reads only the doc.

### In the kit

- `@tool` (`tools/registry.py`) converts a `async` function into a tool: name of the → function name, docstring →
  description, annotated parameters → schema (camelCase for model), `Field(description=…)` → description of
  parameter, `Literal[…]` → enum. The arguments received are validated by Pydantic. Detail: [TECH 5.1](TECH.md#decorateur).
- The 16 tools are in `tools/catalog.py`, `context.py`, `history.py`, `orders.py` ([TECH 5.2](TECH.md#outils)).
- `curl -s localhost:4100/tools` shows exactly what the model receives.

### Write a good tool

| Rule | Why? | Example in the kit |
|---|---|---|
| The description says **quand** use it, and quotes the neighbouring tools | the model chooses from the description | `save_context`: "Not for a claim (use log_client_event)" |
| Parameters described with an id example | fewer ill-formed arguments | `client_id: str = Field(description="ex. cli_0012")` |
| `Literal` as soon as the values are closed | the model cannot invent a value | `search(types=…)`, `get_context(entity_type=…)` |
| Output **small**: only useful fields | each byte is reread at each step, and in voice it remains in the history | `pick(...)`, `[:5]`, `summarize_order`, `compact` |
| Send back the **ids** that the next step needs | the model does not invent an id if it has one in front of the eyes | `search` returns `id`; `summarize_order` returns `lineId` |
| A **composite** tool for frequent chaining | a local HTTP call costs ms, a model stage of hundreds | `quote_product` in [TECH 5.4](TECH.md#outil-composite) |
| ** scripturessafe to play again** and in two steps | the model tries again after an error; a confirmation does not cancel | `create_draft_order` and then `confirm_order` |
| Lift an exception with a French message | the model reads `{"error": …}` and can explain it to the customer | `ErpError` (`tools/erp.py`) |
| No business rules in the tool | one truth: the backend | prices come from `/api/prices/resolve` |

**Ids rather than names**: the model finds the entity with `search` (fuzzy search), then works with the id.
create no tool that takes a client name "as said" and guesses: the blurred search returns several
and it is to the model (or Jev, section [7](#7-jev-the-decision-model)]) to ask "what?".

### Anti-patterns

- A generic `query_erp(path)` tool: the model invents roads and reads huge raw ERP objects.
- Send the complete ERP object "in case": thousands of tokens read at each step.
- Two tools with almost identical descriptions: the model hesitates or alternates.
- A tool that confirms an order without accepted summary (see [9](#9-common-traps)].
- Send `{"ok": false}` without a message: the model doesn't know what to say.

### Mini example: from bad to good version

Bad: vague description, raw object, nothing says when to use it.

```python
@tool
async def client_info(ctx: ToolContext, name: str) -> dict:
    """Infos client."""
    hits = await ctx.erp.get("/api/search", {"q": name, "types": "client"})
    return await ctx.erp.get(f"/api/clients/{hits[0]['id']}")   # devine le 1er, renvoie tout
```

Okay: take an id, say when to use it, send it back little.

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

Then import it into `tools/__init__.py` and check with `curl -s localhost:4100/tools`. Step by step:
[TECH 5.3](TECH.md#ajouter-outil).

### Advice

- Test a tool alone before giving it to the model: `await TOOLS["nom"].run({...}, ctx)` ([TECH 8](TECH.md#tester-sans-ui)).
- If the template does not call your tool, rewrite the description before touching the prompt.
- An irreversible confirmation = a separate tool + an explicit prompt rule (`BASE_RULES` already does it for
  `confirm_order`).

---

## 5. Context and memory

### 5.1 The idea: the context window

The model has no memory between two calls. All he "knows" at one step is in the query: prompt
system + tool definitions + history + tool results. This query is measured in **tokens** () 3 to 4
characters in French) and it has a maximum size, the ** context window**. Long before the limit, a context
too big costs expensive, slows down the first token and dilutes attention: the model misses the rule more easily
major drowned in the middle.

### 5.2 The kit's quick system

`build_system_prompt(mode, actor_name)` (`agent/prompts.py`) assembles at each tower:

| Part | Content |
|---|---|
| `ROLE` | "Assistant AI of the ERP of {company}", the activity |
| `BASE_RULES` | tools for any data, `search` first, `get_price` for a price, context before responding, draft then explicit confirmation, alerts |
| `MODE_RULES[mode]` | `CHAT_RULES` (light markdown), `VOICE_RULES` (1–2 sentences, numbers in all letters, summary), `COMMAND_RULES` (act immediately, one sentence) |
| date | `meta.today` of the ERP, in French (the data have their own simulated date) |
| Interlocutor | `actor_name` |
| context | **tous** the `DATA_DIR/context/*.md` of the first level, read at each turn |

Detail: [TECH 4.3](TECH.md#prompts).

### 5.3 History, by Mode

| Mode | Who keeps the history |
|---|---|
| `chat` | the browser, returned in full to each message |
| `voice` | AI service, in memory, cut to ~40 messages (`trim` in `services/voice_session.py`) |
| `command` | person: one message per request |

`run_agent` ** adds ** messages to the list you pass: who keeps the list keeps the memory.
tools remain there too, hence the interest of small outputs.

### 5.4 Recover instead of loading everything

Two strategies to provide knowledge to the model:

- ** Put it all in the prompt** (stuffing): this is what the kit does with `DATA_DIR/context/*.md`. Simple, always
  available, but paid at each stage of each round.
- **Go look for what is needed** (retrival): the ** contexttable** of the ERP, via three tools of
  `tools/context.py` :
  - `get_context(entity_type, id)`: everything you know about a customer, supplier, product or radius;
  - `search_context(query, …)`: full text search in the sheets (rules, procedures);
  - `save_context(…)`: Memorize a lasting fact learned during the call (long-term memory shared with the team).

The `data/context/clients/` and `suppliers/` plugs are not **pas** in the prompt (only the first level is):
the agent sees them via the table, if he thinks of calling `get_context`.

### 5.5 Quick cache

**The idea.** From one step to another, the start of the query (tools + quick system + start of history) is
same. The supplier's prompt cache keeps this **prefix** already processed: at the following call, tokens cached
are read much faster and billed at a fraction of the normal price (about 10 % at Anthropic; writing
initial costs a little more than a normal token; see the supplier price page). The Anthropic cache used here
lasts 5 minutes.

**In the kit.** The `clients/anthropic.py` adapter sets three cache points (`cache_control`): on the last one
tool, on the prompt system and on the last block of the conversation (`mark_last_block`). The next step of the same
turn (after a tool) and the next turn therefore reread the whole prefix from the cache. Other suppliers manage
hide them in their own way (or not): look at their documentation.

**Why does it matter here?** ≈ 27 000 tokens per call, the essentials of which are the same prefix; a turn of
117 000 relit command. Without cache, you pay this full price prefix at each step. With cache, the 2e step
of a tower and the subsequent towers of the same call reread it almost for free, and the first token arrives earlier.

**What breaks the cache.** The cache only works on an identical ** prefix for byte**. Any change
invalidate the following:

- modify a `.md` from `DATA_DIR/context/`, a `prompts.py` rule, a tool description;
- add, remove or reorder tools (in Anthropic, the order of the prefix is: tools, then system, then
  messages);
- put in the prompt system something that changes every turn (one hour, one meter, the customer's card)
  current **before ** stable rules);
- change mode or contact (`actor_name` is in the prompt).

So put the stable first and the variable at the end (in the messages, or in the last part of the prompt).

**See hits.** Look at `usage` in event `done` (fields `cache_read_input_tokens` and
`cache_creation_input_tokens` in Python, `cacheReadInputTokens` / `cacheCreationInputTokens` in JSON
`/ai/chat`) ; `make chat` displays them ("cache read ... / written ..."). Tokens read in cache must be raised as soon as the
2e step of a turn; if they stay at 0, something changes in your prefix. Be careful: with the cache,
`input_tokens` only counts the hidden part **non** (total = `input_tokens` + written + read).

### Advice

- Measure the size of your prompt before enriching it: each added Ko is paid at each step.
- Preload what is sure to be useful (the client's card identified at the beginning of the call) ** at the end** of the prompt, and
  Leave the rest in retrieval.
- For a long voice call, a summary of old tricks is better than 40 raw messages.
- Use `save_context` for what must survive the call ("deliver through the service door"; not for a
  claim (`log_client_event`).

---

## 6. Models

### The idea

Three sliders: ** intelligence**, **latency**, ** cost**. For a vocal agent, latency in the first word counts as much
recent models "think" before responding (internal raisonment): we no longer settle
the temperature, we regulate ** the reflection effort**.

### In the kit

| Model Anthropic | Profile (`.env.example`) |
|---|---|
| `claude-sonnet-5-5` | default, balanced (`DEFAULT_MODELS` in `clients/factory.py`) |
| `claude-haiku-5-5` | fastest, cheapest |
| `claude-opus-5-5` | smartest, slowest |

Price: the kit does not give, see the price page of the supplier. Cost of a tour
+ output tokens × output price (+ reduced price for cached tokens).

- **Change of model**: in `.env`, `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-haiku-5-5`, then `make restart`
  (Docker) or restart `make dev`. `GET /ai/health` displays the active model. Other suppliers (OpenAI, Gemini, all
  OpenAI compatible endpoint): [TECH 4.1](TECH.md#config-ia).
- **Effort**: `LLM_EFFORT` (default `low`, `medium`, `high`), sent by `clients/anthropic.py` in
  `output_config.effort`. `low` keeps the voice fast; mount it for a tough ride.
- **Streaming**: all clients stream; text goes to the TTS sentence by sentence.
- **Reflection**: Anthropic adapter returns `thinking` blocks with the tower that calls for tools (required by
  recent models).

### Route between models

A single LLM customer is built (`get_llm_client()`, cached). To route, build a second one with
`make_llm_client(LLMSettings(...))` and choose by turn:

- small model (Haiku) for simple tricks: "there is still bar?", "thank you, goodbye";
- Large model (Sonnet / Opus) for trading, claims, multi-line orders;
- the **routeur** may be a rule, or a decision Jev (section [7](#7-jev-the-decision-model)].

**Repli**: If the provider returns an error (quota, failure), `run_agent` issues an event `error`.
catch this in the caller and restart the turn on another client.

### Advice

- Compare models on **vos** scenarios (section [8](#8-measuring-and-improving)), not on a print.
- Before changing a model, reduce the context and number of steps: it's often more gain.
- The mock (`LLM_PROVIDER=mock`) calls only one tool per step: its latency does not say anything about the real model.

---

## 7. Jev, the decision model

### The idea

Jev (TypeSafe AI, model `jev-latest`) is **not a LLM**: it does not write any text. You give it a **stat**
(one sentence or JSON) and **typed issues**; for each, it refers a ** decision with
probabilities**. Probability is his asset: when he hesitates, you know, and the agent can ask the client at
I guess so.

| Type | Sending | You receive |
|---|---|---|
| choice (`choose`) | options `{id: description}` | `choice`, `confidence`, `probabilities` |
| score (`score`) | orderly levels | `score` (e.g. 1,7), `confidence` |
| yes/no (`yes_no`) | a statement to be verified | probability of "yes", 0..1 |
| several at a time (`ask`) | a dictum of questions | all answers in one call |

### When to use it instead of a LLM call

- **What product the customer meant by ** among the results of `search` ("the line bar", not "the bar
  breeding stock").
- **Confirmation yes/no** after a summary ("yes go-y" = yes; "uh... rather the fat" = uncertain).
- **Intent Routage**: order, stock question, claim, price → what fast, what tools, what model.
- **Scorer**: emergency, discontent, risk.

Keep the LLM for ** speaker** and for open decisions.

### Measured latency

Real test (November 2026) : `choose` - 750 ms (752 ms, first call, cold), `yes_no` - 170 ms (168 ms).
fast as a LLM step with 27 000 context tokens, but not free: measure it in your path, and launch it
**in parallel** of other things when possible.

### In the kit

- Customer : `clients/jev.py` (`JevClient` : `ask`, `choose`, `score`, `yes_no`; question makers
  `choice_question`, `score_question`, `yes_no_question`).
- Access: `get_jev_client()` returns a `JevClient`, or `None` if `JEV_API_KEY` is empty.
- Examples to copy: `agent/jev_examples.py`
  - `pick_product(jev, utterance, candidates)` → the product id, or `None` if confidence is < 0,6;
  - `is_yes(jev, question, answer)` → `True` / `False` / `None` (≥ 0,8 yes, ≤ 0,2 no, if not uncertain).
- **Nothing in the default agent calls Jev**: it's up to you to plug it in. Format and uses:
  [TECH 4.7](TECH.md#jev), [apps/ai/README.md, Jev](apps/ai/README.md#jev-decision-model).

### Combine Jev and LLM: "Jev decides, LLM speaks"

Two simple ways:

1. **In a ** tool: a composite tool calls `search`, then `pick_product`; if Jev is safe, it returns the
   product, if not `{"ambiguous": true, "candidates": [...]}` and the LLM asks "what?".
2. **Before loop**: in `services/voice_session.py`, when the agent's last question was a
   summary, `is_yes` on the customer response; if `True`, you can confirm directly. If `None`, leave
   the LLM reformulate.

### Advice

- Describe the options (`{"prd_1": "Bar de ligne 1-2 kg, Bretagne"}`) instead of giving naked ids.
- Set a confidence threshold and manage the "uncertain" case: this is where Jev makes the agent safer.
- Always keep the path without Jev running (`if jev:`): the key may be missing.

---

## 8. Measuring and improving

### The idea

Without measure, we "improve" at random. An agent is measured on three axes, the same as the jury: **resist**
(the right action in ERP), **latency**, **cost**.

### What the kit already measures

| Measurement | Where to read it |
|---|---|
| tokens for the entrance, exit and cache of the tower | `usage` of Event `done` (`POST /ai/chat`, `make chat`) |
| total duration of the round | `ms` of event `done` |
| duration of each tool | `ms` of each `tool_result` |
| Detailed vocal latency | `timings` of `agent_done` (voice) and `done` (`/command`): `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`, `totalMs` |
| what the agent wrote | the ERP activity log (purple), `x-actor` |

The AI service has no logging: if you want a measurement history, write each `done` event
in a JSONL file from the caller.

### Build a scenario set

1. Leave documents from **your** company (`data/context/*.md`, `clients/` cards): each rule, preference
   or litigation is a potential scenario ("this leader refuses substitutions", "this client is blocked for unpaid").
2. Write 5 to 10 scenarios: what the customer says, and the ** result expected in the ERP** (command draft with
   such lines, no confirmation, a registered claim...) Include difficult cases: ambiguous client,
   rupture, change of mind, client blocked.
3. Replay them in text (`make chat`, `curl /ai/chat`): it's faster and more reproducible than the voice.
   for latency and naturalness.
4. Note for each: pass yes/no, number of steps, tokens, `ms`. `make reset` resets the ERP to zero between two
   Pass.

### Iterer

- **A change at once**, then replay ** the scenario that fails**; the whole game once at the end.
- Attack the worst of the three axes first.
- Record each trial (guarded or abandoned) in `DECISIONS.md` with its measurements: the jury reads it.
- Offline automatic tests: `apps/ai/tests/` ([TECH 8](TECH.md#tests)).

---

## 9. Common traps

| Trap | Symptoms | Parade |
|---|---|---|
| **Id hallucinated** | `{"error": "… introuvable"}`, or worse: the wrong entity | always `search` first; tools that return useful ids; never id in an example of prompt that looks like a real one |
| **Tool loop** | same tool called 3 times, then `GIVE_UP` | clear error message in the tool; rule "if the tool fails twice, tell the client"; composite tool |
| **Huge tool outputs** | tokens that explode, slow responses | `pick`, cut lists, shortened texts |
| **Prompt which inflates** | every turn slower and more expensive, rules ignored | context in retrival, cache of prompt intact ([5.5](#55-quick-cache)), regular review of the `.md` |
| **Order confirmed without rereading** | `confirm_order` Called Before Customer Agreement | oral summary + explicit agreement (`VOICE_RULES`), or `is_yes` from Jev |
| **Alerts ignored** | order confirmed for a blocked customer | ERP returns `warnings` but ** blocks nothing**: the prompt or a tool must refuse ([TECH 9](TECH.md#pieges)) |
| **Customer preferences ignored** | proposed substitution to a client who refuses them | `get_context` on the client at the beginning of the call (or preloaded) |
| **Beautiful date** | "Tomorrow" calculated on the real date | use `meta.today` (already in the prompt) |
| **Ids and markdown read aloud** | "c, l, i, underscore..." | `VOICE_RULES`; check the text of `agent_done` |
| **Writing done despite interruption** | the customer has cut, the line is still added | no rollback at the barge-in : reread the command at the end of the call |
| **Lost vocal history** | the agent forgets everything after a file backup | the voice history is in memory; the auto reload of uvicorn the vacuum |
| **Mock** measurements | excellent latency in dev, bad demo | measuring with the real keys |

Complete list of limits verified in code: [TECH 9](TECH.md#pieges).

---

## 10. To go further

- **Orchestrator and Specialized Agents**: A Principal Agent Delegating to an "Order" Agent, an Agent
  "claim", each with fewer tools and a shorter prompt.
- **Dialogue state**: for ordering, a small structured state (client, lines, date, confirmed?) held
  by the code, which the model reads and updates, rather than reconstructing everything from history.
- **Planning**: Have the template write a short plan before acting on a complex request, and then execute it.
- **Automatic Evaluations**: Replay scenarios with each change, and note the nature of a response
  by a "judge" model with a fixed grid.
- ** Faster voice** : STT streaming (`transcribe_stream`, already implemented for Soniox and Deepgram), sentences
  during tools ([TECH 4.5](TECH.md#latence)).
- **Memory**: Summarize a client's calls in the context table with `save_context`.
