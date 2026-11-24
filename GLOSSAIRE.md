# Glossary

The words you will cross in the kit, in simple French: first the **termes professionnel** of food trading
(caliber, shelf life, franco, encours, tour...), then the ** technical terms**. The trade is explained in detail in
[METIER.md](METIER.md).

A practical question rather than a word? [FAQ.md](FAQ.md).

| Theme | Words |
|---|---|
| [1. Terminal and tools](#terminal) | terminal, folder, `cd`, `make`, Docker, image, container, port, localhost, `.env` |
| [2. Git and GitHub](#git) | git, repo, commit, push, GitHub |
| [3. Programmes and network](#reseau) | frontend, backend, service, API, endpoint, request HTTP, JSON, WebSocket, SSE, Python, async, FastAPI, React |
| [4. LLM and agents](#llm) | LLM, prompt, token, context, quick cache, agent, harness, loop, tool, Jev |
| [5. Voice and latency](#voix) | STT, TTS, streaming, latency, TTFT, first sound, barge-in, VAD |
| [6. Kit](#kit) | mock, ERP |
| [7. Trade terms](#metier) | caliber, shelf life, FEFO, course, franco, tour, avoir, mercuriale... |

<a id="terminal"></a>
## 1. Terminal and tools

| Word | Definition | In the kit |
|---|---|---|
| **Terminal** | Window where you type commands instead of clicking. On Windows: terminal **Ubuntu** (WSL), not PowerShell. | All `make …` commands of [SETUP.md](SETUP.md) |
| **Current file**, **`cd`** | The terminal is always "in" a folder. `cd voice-erp-kit` enters it, `cd ..` goes up from a scratch, `pwd` displays where you are. | `make` commands start from `voice-erp-kit/` (where the `Makefile` is) |
| **`make`** | Shortcut: `make up` launches a series of commands written in the `Makefile` file. | `make help` list all : `setup`, `up`, `down`, `logs`, `chat`, `reset`... |
| **Docker** | Software that runs programs in isolated boxes, with everything they need. Nothing else to install. | Docker Desktop, step 1 of [SETUP.md](SETUP.md) |
| **Image** | The "model" of a Docker box: the program and its dependencies, ready to launch. | Built by `make setup` / `make rebuild`, or loaded from USB key (`make offline`) |
| **Container** | A rotating image. The kit launches three: `backend` (ERP), `ai` (agent), `web` (interface). | `make ps` lists, `make logs` shows what they write |
| **Port** | "Door" number by which one speaks to a program on a machine. | 5173 = interface, 4000 = ERP, 4100 = service AI |
| **localhost** | "My own machine." `http://localhost:5173` = the program that listens to your computer's 5173 port. | Open http://localhost:5173 in Chrome |
| **Environmental variable** | A setting (name = value) read by a program on startup, out of code. | `LLM_PROVIDER=anthropic`, `AI_PORT=4100` |
| **`.env`** | The file that contains all these variables. Private: never in git. | Only one `.env` at the root for the three services; after modification: `make restart` |
| **Clé API** | Password that identifies you with a supplier (Anthropic, Soniox...) and allows it to invoice. | `LLM_API_KEY`, `STT_API_KEY`, `TTS_API_KEY`, `JEV_API_KEY` in `.env` |
| **Logs** | What programs write while they spin: queries, mistakes. First reflex when it breaks. | `make logs` (Ctrl-C to exit) |

<a id="git"></a>
## 2. Git and GitHub

| Word | Definition | In the kit |
|---|---|---|
| **git** | Tool that keeps the history of your code versions, file by file. | `git init`, step 4 of [SETUP.md](SETUP.md) |
| **Repo** (deposit) | A file followed by git, with all its history. | Your team repo = `voice-erp-kit/` folder |
| **Commit** | A recorded photo of your changes, with a message. | `git add . && git commit -m "filler avant les outils"` |
| **Push** | Send your commits to an online repo. | `git push` to your private GitHub repo |
| **GitHub** | Site that hosts online git rest and allows to share them. | The "repo GitHub" deliverable of [BRIEF.md §8](BRIEF.md#8-finishables-and-final-demo) |
| **`.gitignore`** | List of files that git does not follow. | `.env` and `data/seed/` are there, on purpose |

<a id="network"></a>
## 3. Programmes and network

| Word | Definition | In the kit |
|---|---|---|
| **Frontend** | The part you see: pages, buttons, in the browser. | `apps/web` (port 5173) |
| **Backend** | The server part, invisible: data, rules, calculations. | `apps/backend` = ERP (port 4000) |
| **Service** | A program that runs continuously and responds to requests. | Three services: ERP, AI, web |
| **API** | A list of applications that a program accepts from other programs. | API of ERP: http://localhost:4000/docs; AI service: http://localhost:4100/docs |
| **Endpoint** (road) | A specific address of the API, which does one thing. | `GET /api/products`, `POST /ai/chat`, `GET /tools` |
| **Request HTTP** | A message sent to a web address. `GET` = read, `POST` = create or act, `PATCH` = edit. | `curl localhost:4100/tools` sends one from the terminal |
| **JSON** | Text format for data exchange: `{"produit": "bar", "kilos": 5}`. | What ERP refers to and the tools of the agent |
| **WebSocket** | Connection that remains open between browser and server, in both directions. Ideal for sending audio continuously. | `WS /ai/voice` (Voices page), `WS /ai/voice/command` (Space) |
| **SSE** (*server-sent events*) | Answer HTTP that arrives piece by piece, from the server to the browser. | `POST /ai/chat`: the agent's text is displayed along the water |
| **Python** | The language of backend and service AI. Readable, many libraries. | `apps/backend`, `apps/ai` |
| **async** (asynchronous) | Code that can wait (a network response) without blocking everything: during this time, something else is moving forward. Keywords `async def` and `await`. | The entire AI service: several tools run in parallel (`asyncio.gather`) |
| **FastaPI** | Python library that turns functions into API endpoints. | `routers/` of the ERP and the AI service |
| **React** | JavaScript library to build the interface into components. | `apps/web/src` (TypeScript) |
| **TypeScript** | JavaScript with verified types. | The frontend; `make check` checks that it compiles |

<a id="llm"></a>
## 4. LLM and agents

To go further: [GUIDE-AGENTS.md](GUIDE-AGENTS.md).

| Word | Definition | In the kit |
|---|---|---|
| **LLM**, **model** | *Large language model*: a program that predicts the continuation of a text, and thus knows how to answer, reason, call tools. | Default Anthropic: `claude-sonnet-5-5` (`LLM_MODEL` in `.env`) |
| **Prompt** | Text sent to the template: instructions + conversation. | Built by `agent/prompts.py` |
| **Prompt system** | The fixed part of the prompt, which tells the model who it is and how to behave. | `build_system_prompt` : role, rules (`BASE_RULES`, `VOICE_RULES`...), company context |
| **Token** | A piece of word (about 3⁄4 words on average). The models read, write and bill in tokens. | The kit prompt makes 27 000 tokens by model call |
| **Context** | Everything the model sees at a moment: quick system, history, tool results. It is limited in size. | `data/context/*.md` (your company's knowledge) + call history |
| **Cache of prompt** | The supplier keeps in mind an identical start of prompt from one call to another: cheaper and faster. Only one byte changed at first breaks it. | `clients/anthropic.py` (`cache_control`); `cache_read_input_tokens` in `usage` |
| **Agent** | A LLM that acts: it reads the request, calls tools, reads the results, repeats and answers. | `agent/loop.py` (`run_agent`) |
| **Boulcle** | The cycle "model → tools → model..." until the final answer. | `AGENT_MAX_STEPS=8` laps maximum |
| **Tool** (*tool*) | A function that the model may require to call, with a name, description and parameters. | Functions `@tool` in `apps/ai/app/tools/*.py` (`search`, `get_price`, `create_draft_order`...) |
| **Harness** | The whole code around the model: loop, tools, quickness, error management. That's where you work. | `apps/ai/app/agent/` + `tools/` |
| **Jev** | TypeSafe AI decision model: Not a cat, it quickly answers closed questions (choice, yes/no, score) with a probability. Used ** next to ** of LLM. | `get_jev_client()`, examples `agent/jev_examples.py`; key `JEV_API_KEY` |

<a id="voice"></a>
## 5. Voice and latency

To go further: [GUIDE-VOIX.md](GUIDE-VOIX.md).

| Word | Definition | In the kit |
|---|---|---|
| **STT** (*speak-to-text*) | Transcription: the voice becomes text. | default Soniox with your keys (`STT_PROVIDER`); `services/utterance.py` |
| **TTS** (*text-to-speech*) | Voice synthesis: the text becomes voice. | ElevenLabs (`TTS_PROVIDER`); `Speaker` in `services/voice_session.py` |
| **Streaming** (flow) | Process data as it is processed, rather than waiting for the end. | Audio starts in STT while you speak; the text of LLM starts in TTS sentence by sentence |
| **Partial transcription** | The provisional text that STT returns during the floor, corrected thereafter. | Displayed in italic grey on the Voice page |
| **Push-to-talk** | One keeps a touch while one speaks; the release marks the end of the word. | Space on the Voice, Space page everywhere |
| **VAD** (*voice activity detection*) | Automatically detect when someone talks and when they're done. | Not in the kit: track 4.2 from [GUIDE-VOIX.md](GUIDE-VOIX.md#vad) |
| **Latency** | Waiting time. Here: from the end of your sentence to the first sound of the agent. | Columns **Total** and **Preview** of the Voice Page |
| **TTFT** (*time to first token*) | Time between sending to the model and its first piece of response. | `llmFirstTokenMs` in the measurements of each tower |
| **First sound** | The time when the appellant hears the agent. This is the "fastest" price metric. | `totalMs` (server) and `perceivedMs` (navigator) |
| **Barge-in** | The caller cut off the agent: you have to stop the audio and listen. | `interrupt()` in `voice_session.py` |

<a id="kit"></a>
## 6. The kit

| Word | Definition | In the kit |
|---|---|---|
| **Mock** | A fake supplier, free and offline, who imitates the real one. To develop without a key. | `*_PROVIDER=mock`; the STT mock still hears "Hello, do you still have the bar?" (`MOCK_STT_TEXT`) |
| **ERP** | Company management software: customers, products, stock, orders, invoices. | `apps/backend` + interface pages; see [ERP.md](ERP.md) |
| **Seed** | The starting data loaded into the ERP. | `data/seed/`; `make reset` recharges them |
| **`x-actor`** | Header that says who did a writing in the ERP (`user`, `ai_chat`, `voice_agent`). | In purple in the interface: what the agent did |

<a id="metier"></a>
## 7. Trade terms

The vocabulary of food trading, and where it appears in the ERP (entities, fields, roads).

| Term | Definition | In the ERP |
|---|---|---|
| Chartered | Rent a truck or assign a delivery to a carrier | absent |
| Alias | Common name of a product ("wolf" for bar) | `Product.aliases` |
| AOP, Red Label | Official signs of quality or origin | `Product.tags` (`labels`) |
| Arrival, disembarkation | Merchandise that happens, what the ships bring back | `PurchaseOrder`, `Lot` |
| Having | Negative bill after return or litigation | event `credit_note` |
| Aged balance | Amounts allocated by length of delay | `GET /api/receivables` |
| BL (Delivery note) | Document accompanying the delivery | — |
| Price list | Prices fixed by a public contract | `ClientPrice`, `PriceRule` (`marche-public`) |
| Riche | Oyster basket (e.g. 4 dozen) | unit `dozen` |
| Draft, pre-order | Order not validated by the client | `Order.status = "draft"` |
| Caliber | Product size (1-2 kg, 15/20, No 3) | `Product.caliber` |
| Cold chain | Continuous maintenance of temperature | — |
| box, case | Packing unit | Unit `box` (≈ 5 kg) |
| Purchase order | Order placed to a supplier | `PurchaseOrder` |
| Commercial staff | Responsible seller of a customer | `Client.salesRep` |
| Supplement | Remains of incomplete delivery, delivered later | `partially_received` |
| Coverage | Number of sales days that stock allows to hold | — |
| Scream | Hall where fishing is auctioned | — |
| Cut-off, time limit | Time after which the order starts on the next day | context only |
| DDM | Date of minimum durability, "preferably before" | — |
| Downgrading | Product sold cheaper or processed because less beautiful | — |
| Marking, loss, breakage | What's thrown out | movement `waste` |
| shelf life | Consumption deadline, "until" | `Lot.expiresAt`, `Product.shelfLifeDays` |
| Available | Physical stock minus reserved stock | `StockLevel.available` |
| DSO | Average payment time for customers | `GET /api/receivables` |
| Due date | Date on which invoice must be paid | `Invoice.dueDate` |
| Overdue, late | Invoice not paid after maturity | calculated status `overdue` |
| Outstanding balance | Total due by customer, € incl. VAT | `outstanding` |
| Extra | One-time command out of habits | — |
| FEFO | First expired, first out | `fefo_lots` in `services/stock.py` |
| Franco | Amount from which the transport is offered | `Supplier.notes` |
| Commercial gesture | Rebate granted to repair a problem | event + `resolution` |
| HACCP | Method of analysis of food hygiene hazards | — |
| The usual | What the customer almost always orders | `GET /api/clients/{id}/usual` |
| Lot | An arrival of a product, with its deadline | `Lot` |
| Mareyeur | First buyer of the fish at the auction, who prepares and ships it | `Supplier.tags` (`mareyeur`) |
| Public procurement | Contract to purchase a community after tendering | tag client `marche-public` |
| Mercurial | Price list of a supplier's day | `SupplierPrice` |
| MIN | Market of national interest (Rungis, Lyon, Marseille...) | — |
| Minimum order | Minimum amount to order from a supplier | `Supplier.minOrderAmount` |
| Credit ceiling | Maximum permitted outstanding | `Client.creditLimit` |
| Clearance plan | Schedule to pay off a debt | event `payment_plan` |
| Real weight | What it weighs what is delivered | `OrderLine.preparedQty` |
| List price, catalogue | Basic price | `Product.price` |
| Negotiated price | Price of a product for a customer | `ClientPrice` |
| Prospect | Potential customer | `Client.status = "prospect"` |
| Recovery | Reminder of unpaid invoice | event `late_payment` |
| Reserved | Stock promised to confirmed orders | `StockLevel.reserved` |
| RHD | Out-of-home catering | — |
| Out | More stock available | alert `insufficient_stock` |
| Substitution | Product delivered instead of another, with agreement | `OrderLine.substituteFor` |
| Turned | Circuit of a truck on an area, some days | `Route`, `RouteRun` |
| Area | Customer delivery sector | `Client.zone` = `Route.zone` |
