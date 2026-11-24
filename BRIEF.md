# Voice Hackathon — Participants Briefing

24 hours to build a vocal agent that does a real job in a food wholesaler's ERP.
This brief explains the context, what you are given, what you are expected to do, and how you can do it.
The installation is in [SETUP.md](SETUP.md), the technical details of the kit in [README](README.md).
An unknown word? [GLOSSAIRE.md](GLOSSAIRE.md) · A question ? [FAQ.md](FAQ.md)

---

## 1. The context

Stockline builds the software of food wholesalers: tidal, fruit and vegetables, meat, creamery,
These companies buy at night from their suppliers and deliver in the morning hundreds of
restaurants, fish shops, canteens, hotels and caterers.

In this profession, almost everything goes through the voice:

- **Customers** call to order ("as usual", at 2 in the morning), ask if the wild turbot
  has arrived, complaining about a delivery, discussing a price.
- **Suppliers** are called to compare prices, negotiate, book a lot.
- **The ** carriers to book the fastest tour at the best price.
- **Prospects** to sell and present the arrivals of the day.
- **Collectors**: "How many bars do we have left?", "this customer pays how many dayss?", "What is it?
  which is going on with Ostrea?"

Each call ends in the ERP: an order, a price, a claim, a payment, a tour. Today,
a good voice agent listens, understands the trade, acts in the ERP during the call and
answer as the best salesman in the box would.

## 2. The trade

A food wholesaler buys wholesale every night, stores some days in the cold and delivers in the morning of
hundreds of professionals, with a weak margin and products that perish quickly. Customers, take of
order, catalogue, prices, purchases, stocks and lots, preparation, tours, billing and outstanding, claims,
seasons: each game has its own vocabulary and traps.

**Read the full reference: [METIER.md](METIER.md).** This is the best source of ideas to choose your
problem, and what your agent needs to understand to be credible.

## 3. The challenge

**Build the most useful vocal agent on this ERP.**

There is no imposed subject. Your first step is to **choose a real problem** in this trade, and
**justify** why it's this one: who calls who, when, what it costs today, what
the agent changes. Leave the above context and your company's data.

Your agent will be judged on three lines:

| Axis | What that means. | How we see it |
|---|---|---|
| **Smart** | He knows the company, the customer, the products, the history. He is not mistaken, offers alternatives, manages ambiguity, acts just in the ERP. | He knows that this chef refuses substitutions, proposes the right replacement, finds "the wolf" in the catalog, creates the right order. |
| **Fast** | The answer comes quickly, without annoying white. | End of speech time → first sound, number of round trips model/tools, cost per call. |
| **Natural** | We forget it's a machine. | Short phrases, fair tone, managed interruptions, spoken numbers, command rereading, background noise. |

The jury will test your agent **in direct**, on scenarios you won't know in advance.

## 4. What we give you

| What? | Detail |
|---|---|
| **The kit (repo code)** | A complete and simple ERP: customers, suppliers, products, stocks and lots, pre-orders, orders, invoices, payments, outstanding, tours, negotiated prices, historical customers/suppliers, context table. Backend Python (FastaPI), service AI Python, frontend React. |
| **The ERP** guide | [ERP.md](ERP.md): each page, life cycles, business rules (price, stock, credit), data model, agent tools and API. |
| **A basic agent** | A single agent loop, ~16 tools that read and write in the ERP, LLM / STT / TTS customers interchangeable (OpenAI, Anthropic, Gemini, Deepgram, Soniox, ElevenLabs, Gradium, or any OpenAI compatible endpoint), a chat, a push-to-talk voice mode and a voice control mode. |
| **Call simulation** | No phone number: one page **Voix** with two audio tracks. Keep Space to speak as a client, release, the agent responds. The ERP updates live before your eyes. |
| **Data (in your zip, `./data`)** | A team fictitious company (24 in total), with ~100 customers, its suppliers, its catalog and 3 years of history: orders with varied rhythms, seasons, claims, late payment, detailed personas, company documents. |
| **Keys** (already in your `.env`) | LLM (Anthropic), transcription (Soniox), voice (ElevenLabs), Jev (fast decision model).With ceilings: monitor your consumption. |
| **Help** | The Stockline team on site all night to unlock you. |

Everything also spins ** without keys**: fake models (mock) answer deterministically and call the real ERP.
Useful to develop and test without burning your credits.

## 5. Start

Each team receives a **zip**: kit, company data (`./data`) and configuration (`.env`,
**Follow [SETUP.md](SETUP.md)**: Install Docker (to be done before hackathon), `make setup`, first
Call, team repo. Count 20 to 30 minutes the first time.

Next:

1. Open **http://localhost:5173** and browse the ERP: customers, orders, stocks, Context. These are the data
   from **your** company.
2. Page **Voix**: Keep Space and speak like a client. Look at the transcription, the tools called,
   the response times, and the ERP that is updating.
3. Read `apps/ai/app/agent/loop.py` (the loop) and `apps/ai/app/tools/` (the tools). This is where you will pass
   Most of your time. Project plan: [SETUP.md, How the project is organised](SETUP.md#how-the-project-is-organised).

## 6. How to do it

A cut that works well on 24 h :

1. **Choose problem (H0 → H2).** Read customer cards (`data/context/clients/`) and related documents
   the enterprise (`data/context/`). Who calls ?
   What to do? What is missing today? Choose **un** case and write it in
   `DECISIONS.md` with your justification.
2. **Write your test scenarios (H2 → H3).** 5 to 10 realistic calls, including difficult cases: customer
   ambiguous, broken product, customer blocked for unpaid, change of mind during call, noise. These are
   your non-regression tests for the whole night.
3. **Take the course from end to end (H3 → H8).** True Keys, true microphone, a complete call that
   ends with the right action in the ERP. Mocking but complete.
4. **Measuring, then improving (H8 → H20).** Note the latency, cost and errors of each scenario.
   Attack the worst of the three axes first. Test each change.
5. **Prepare demo (H20 → H24).** Freeze code, save video, prepare slides, repeat demo
   Live.

Note each important choice in `DECISIONS.md` along the water (what, why, what you tried and
The jury will read it.

## 7. Technical tracks

These are not subjects, just directions that make the difference. New on Agents LLM? Read
[GUIDE-AGENTS.md](GUIDE-AGENTS.md): loop, tools, context, quick cache, model choice, Jev, measurement, traps.
For the voice (end of speech latency → first sound, kit measurements, techniques to go faster and ring
natural, and where to plug them): [GUIDE-VOIX.md](GUIDE-VOIX.md).

**To go fast**

- Streaming templates everywhere: STT with partial transcriptions, LLM en streaming, TTS sentence par phrase.
- Speech-to-speech (native audio models) to remove steps.
- Parallelize: launch the independent tools together, preload the customer's card from the beginning of the call,
  anticipate the next tool call.
- A small quick model for single spins (Jev for decisions), a big one only when needed.
- Deterministic code for what doesn't need a model: quantities, units, dates.

**To be smart**

- Context management: to put in the prompt only what the turn needs.
- Context **table**: Each fact is related to a customer, supplier, product or category.
  Build on it: semantic search, graph between entities, memory of what the agent learns on appeal.
- Retrival on history: open claims, buying habits, negotiated prices.
- Orchestration: a principal agent who pilot specialized agents, composite tools (search + stock)
  + customer price in one call), a dialog state for the purchase of orders.

**To be natural**

- Short speaking tours, interruptions (barge-in), small waiting phrases while the tools turn.
- Reread the order before validating, say the numbers and units in the mouth ("12 kilos", "18 euros
  fifty").
- Test with background noise (market, kitchen, truck) and accents.
- The right tone for each contact person: the customer records tell us how each person speaks.

## 8. Finishables and final demo

To be returned before the end of the 24 h:

- [ ] **The GitHub** repo of your team, which runs with `make setup` once the `data/` folder of your zip
  reset (`data/seed/` is not in git).
- [ ] **`DECISIONS.md`**: the problem chosen and why, your technical choices, what worked and what didn't
  your measures (latency, cost, success rate of scenarios).
- [ ] **The slides**: 5 minutes maximum.
- [ ] **A demo video**: 2 minutes maximum, a real call from end to end.
- [ ] **The live** demo: The jury calls your agent live on its own scenarios.

**Main prize**: the best agent on smart, fast and natural, plus the relevance of the chosen problem.

**Special prices** :

| Price | For |
|---|---|
| Fastest | the lowest late speech latency → first sound, measured in demo |
| The cheapest | the lowest cost per successful call |
| The most natural | The one you think of as a human |
| The smartest | the one who best manages the difficult cases of the jury |

## 9. Rules and aid

- You can change everything in the kit: ERP, tools, prompts, frontend, data. Keep it started with
  `make setup` so the jury can throw it.
- All data is fictitious. Never put a API key in the repo: they go to `.env`, which is
  Ignored by git.
- The keys have a ceiling. Develop with the mocks, test with the real keys.
- Blocked more than 20 - Come and see the team. Stockline. That's why we're here..
- Installation and common problems: [SETUP.md](SETUP.md). Architecture, configuration, add tool or tool
  Model supplier: [README](README.md).
