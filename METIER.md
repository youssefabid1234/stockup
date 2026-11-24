# Food wholesaler trade — reference

This document explains in detail how a food wholesaler works and how each concept is
in the kit's ERP. Read it to choose your problem and to make your agent speak and act like a
The general briefing is in [BRIEF.md](BRIEF.md).

## How to read this document

- **For humans**: read "The trade in one page", "The chain", "The actors" and "Where the voice changes"
  The rest is used as a reference for the 24 hours.
- **For code agents** (Claude Code, Cursor...): each domain ends with a ** blockIn the ERP** which
  gives the exact names between backticks: entities and fields (`Order.status`), routes (`/api/context/for`), tools
  the agent (`get_price`), interface pages (**Commands**). The lines **Rule** are business rules
  When a rule is only written in context and *not* applied by the backend, that is said.
- **The examples** come from the pack **Marée of Rungis** ("the pack" in the suite). Your team receives the pack of
  its own company in `./data`, with the same structure (`seed/` and `context/`).
  fictitious wholesaler in seafood installed in Rungis MIN: 66 products, 100 customers, approximately 1,2 M€ excl. VAT
  sales per month, average basket of about 920 € excl. VAT. Everything is fictitious. The "day date" of the pack is
  `meta.today` = Tuesday 24 November 2026, and the reference time is 4 h 30: the trucks have not left yet.
- The document covers the whole food wholesale trade (marée, fruit and vegetables, meat, creamery, grocery,
  There are 24 fictitious companies, one per team, and yours may belong to another.
  family: the principles are the same, only products, units and rhythms change.

---

## The trade in one page

A food wholesaler buys wholesale, stores little time, and sells in small quantities to
Professionals: restaurants, shops, canteens, hotels. It does not sell to private individuals.
"distributor" or "aggregator RHD" (out-of-home restoration).

What he really sells is not just product. It's:

- **the good product**, chosen from dozens of suppliers, with the right calibre, with the right quality;
- **at the right time**, delivered before service, often before 7 in the morning;
- ** in small quantity**, while the supplier sells by pallet or batch;
- ** to credit**, paid 30 days later;
- ** with advice**: "The turbot is priceless this week, take St. Peter's".

Three figures summarize the difficulty:

| Constraint | Order of magnitude | Consequences |
|---|---|---|
| Gross margin | 15 to 35 % of the selling price | There is little room for error. The final net margin is often only a few percent. |
| Life of the expense | 3 to 5 days for fish, some days to a few weeks for fruits and vegetables and meat | Anything that is not sold in time is discarded. |
| Customer order time | a few hours, often at night | You have to buy before you know what we're gonna sell. |

The wholesaler earns his living in a fragile balance: buy enough for never to say "I don't have any more", without
buy what will end up in the trash, and get paid by customers who pay late.

### Product families

Each wholesaler specializes in one or two families. The rules change a lot from one to the next.

| Family | Examples | Sales unit | Life | What Makes the Price | Main Alea |
|---|---|---|---|---|---|
| **** Seafood | bar, sole, oysters, lobster, mussels | kg, dozen, piece | 3 to 5 days; live shells | day auction, species, caliber, wild or farmed | weather: no fishing by storm |
| **Fruits and vegetables** | lemons, salads, potatoes, herbs | box, cage, kg, boot | 2 days (herbs, strawberries) to several weeks (potatoes) | season, origin, category (Extra, I, II), caliber | weather, frost, harvest; maturity |
| **Viande** | beef, veal, poultry, lamb | kg, piece, carcase or piece | a few days to a few weeks vacuum | breed, origin, category, piece, maturation | market prices, health crises |
| **Cremerie** | butter, cream, cheese, eggs | kg, liter, piece, tray | from some days (fresh cream) to months (refined cheeses) | AOP, refining, brand name | milk seasons, refining |
| **Spicery** | oil, preserved, salt, flour | cardboard, can, piece | of months (DDM) | trade mark, annual contract | little: long stock, stable prices |
| ** Beverages** | wine, beer, sodas, water | cardboard, drum, bottle | long | trade mark, contract, excise duty on alcohol | instructions (drinks, glass), season (summer) |
| **Frozen** | breaded fish, fries, frozen vegetables | carton, kg | for months at -18 °C | contract, volume | breakage of cold chain |

The Rungis Marée pack is a **marée** wholesaler with some fruits and vegetables, cream and grocery stores.
supplement: it's common, the chief wants everything in the same truck.

---

## The chain: from the boat to the plate

```
  AMONT (produire)            PREMIÈRE MISE EN MARCHÉ          GROS                    CLIENTS
  ───────────────             ───────────────────────          ────                    ───────
  pêcheurs ─────────▶ criée (vente aux enchères) ─▶ mareyeur ─┐
  ostréiculteurs, mytiliculteurs ─────────────────────────────┤
  maraîchers, arboriculteurs ─▶ coopérative / expéditeur ─────┤
  éleveurs ─▶ abattoir ─▶ atelier de découpe ─────────────────┼─▶ GROSSISTE ─▶ restaurants, brasseries,
  laiteries, fromagers, affineurs ────────────────────────────┤   (souvent       poissonniers, primeurs,
  industriels (épicerie, surgelés, boissons) ─────────────────┤    sur un MIN)   cantines, EHPAD, hôtels,
  importateurs (saumon de Norvège, agrumes, thon…) ───────────┘                  traiteurs, supermarchés
```

### The links, one by one

- **Fishers.** They land their fishing at the harbour. The small inshore fishery goes out for the day ; the biggest
  boats depart several days. In heavy weather, the boats remain at dock: nothing happens anymore.
- **Criée** (or tidal hall). The port market where fishing is auctioned, often on screen, very early
  in the morning. Buyers are registered professionals, especially marketers. The price changes every day.
  Examples in the pack: auctions by Boulogne-sur-Mer, Lorient, Le Guilvinec.
- **Mareyeur.** First buyer of fish. He buys at auction, sorting, lava, ice, sometimes raises nets,
  and ships during the day to wholesalers. It is he that the tidal wholesaler calls. Examples:
  Boulogne Marée Mareyage (`sup_0001`), Mareyage de Keroman (`sup_0002`), Bigouden Marée (`sup_0003`).
- **Producers live.** Oyster growers, mussel growers, marketers, cheese growers.
  sell themselves, often with longer minimums and deadlines. Example: Oysters Joubert (`sup_0004`),
  à J+2.
- **Cooperatives and shippers.** They bring together the production of many farmers, sort it, calibrate it
  and pack it. Frequent in fruits and vegetables and milk.
- **Abattoirs and cutting shops.** For meat: the animal becomes carcass, then quarters, then
  Ready-to-cut pieces or vacuum portions.
- **Importers.** They bring what France does not produce enough or not in season: salmon from Norway and
  from Scotland, Indian Ocean tuna, citrus fruits, exotic fruits. Often installed in wholesale markets.
  Example: Highland & Fjord Seafood (`sup_0006`), at Rungis, payment to 45 days.
- **Industrials.** Frozen, grocery, beverages. Year-round negotiated prices, long stocks, scheduled deliveries.
  Example: Oceane Frozen (`sup_0007`), delivery J+2, franco to 1 500 €.
- **MIN (domestic interest market).** Large public wholesale markets where wholesalers, producers are concentrated
  and buyers. **Rungis**, south of Paris, is the largest: it is organized in pavilions (marée, meat,
  fruit and vegetables, dairy products, etc.) and live at night. There are also regional MINs (Lyon,
  Marseille, Toulouse, Nantes, Lille, Bordeaux...). Being on a MIN means having dozens of suppliers to
  a few steps: one can get a box of lemons on foot from the neighbour (Primeurs Dufresne,
  `sup_0008`, two aisles further). Many wholesalers are not on a MIN and have their own
  warehouse in the area of activity.
- **The wholesaler.** It buys from all these links and sells to hundreds of professionals.
- **Customers.** Restaurants, mouth shops, communities, hotels, caterers, sometimes large
  distribution. Details below.

There are also **competitors** that the customer compares to the wholesaler: the other wholesalers in the same market,
large national catering distributors (huge catalogue, tight prices, less flexibility),
free wholesale services (the chef himself will shop), and producers who sell live.

### What the wholesaler brings

| Value | What it means in practice | Example |
|---|---|---|
| **Assortment** | A single contact for 60 with several thousand references, from dozens of suppliers | The chef gets bar, oysters, lemons and butter in the same truck. |
| **Fractioning** | He buys by lot or pallet, sells by kilo | The fisherman sells 50 kg of bar; the bistro wants 3. |
| **Selection and expertise** | He knows quality, calibres, seasons, reliable suppliers | "Don't take turbot this week, there was no landing." |
| **Availability at night** | It responds between 22 h and 6 h, when the chef leaves the service or the fisherman opens | Ostrea commands between 1 h and 3 h. |
| **Logistics and cold** | Refrigeration trucks, touring, slots early in the morning | Delivery before 7 h to dock number 2 of the central kitchen of Vitry. |
| **Credit** | The customer pays to 15, 30 or 45 days; the wholesaler finances the difference | The Comptoir de Marie has about 5 300 € outstanding for a ceiling of 6 500 €. |
| **Health safety** | Cold chain, batch traceability, early withdrawal in case of alert | He knows which customers received Lot X. |
| **Draping** | It finds a solution when the product lacks | Propose hake when the cod burns. |

**Rule.** The customer does not only compare prices. It compares reliability (delivered on time, the right product),
quality, flexibility (order late, small quantities) and credit.
the essentials.

---

## The actors

### Suppliers and how to buy

| Type | What he sells | Typical time | Price | What to Know |
|---|---|---|---|---|
| **Creekfisher** | fresh fish of the day | J+1 (night truck) | changes every day with the cry | depending on the weather; time of shutdown of the controls (often in the morning, before the auction) |
| ** Live producer** (Ostre growers, marketers, cheese growers) | its own production | J+1 à J+3 | fairly stable, not negotiable | small volumes, minimum order, high quality followed |
| **Cooperative, sender** | regrouped and calibrated production | J+1 à J+2 | campaign price, varies with season | large volumes, standard categories |
| **Importer** | Foreign products, counter-season | J+1 (stock on site) | related to world prices and exchange rates | often longer payment (45 days) |
| **Industrial** (frozen, grocery, beverages) | processed products | J+2 to J+5, days fixed | annual contract | free delivery, scheduled command |
| **Confrère wholesaler** | troubleshooting | immediate | more expensive | You buy it when you break up. |

**How a buyer buys, in practice.** The buyer (Franck Le Bihan in the pack) works at night and early
Every day:

1. It looks at what has been sold, what is already ordered by customers, what remains in stock and what is
   expires soon.
2. It consults the **mercuriales**: the price lists of the day that the suppliers send (by email,
   For the same product, it often has two or three possible suppliers.
3. He **Call** multiple suppliers, compares price and quality, and **Trade** : « If I take you 50 kilos,
   I do not want to exceed 22,80."The arguments are volume, fidelity, competitor price, and
   the combined purchase of several species.
4. It ** reserves** rare lots: "Keep me on Friday blue lobsters." A supplier serves its first
   loyal customers and good payers the days shortage.
5. It orders, respecting the **minimum of order** and the **franco** (amount from which the
   transport is offered).
6. He ** received** the following night: it controls quantity, temperature, quality and size.
   What is missing or not suitable becomes a supplier dispute.

What makes a supplier good or bad: the **reliability** (it delivers what it has promised), the **regularity of
quality**, **price flexibility**, **ponctuality** and relationship. Each supplier has its personality:
Loïc Tanguy (Bigouden Marée) never confirms until he has seen the boats; Gwenaël Le Corre (Keroman)
negotiates beyond 50 kg per species and cuts orders at 9 h.

**Rule.** Paying suppliers on time is a purchase argument: the days shortage, the supplier serves
First the customers who pay well.

### Transport

- **Camions own.** Most wholesalers have their refrigerated trucks and drivers.
  truck makes a **turned**: an area, some days, a departure schedule, a suite of stops.
- **Transporters and renters.** For peaks (fests, Saturdays loaded) or distant areas, a truck is rented
  with driver, or the boxs are entrusted to a refrigerated transporter. **reserve** : volume
  (m3), load (kg), temperature ("positive cold" 0/+4 °C or negative), departure time, dock, list of
  stoppages, price. Example in the pack: book a 12 m3 at a rental house for Saturday 28/11.
- **The customer who comes himself.** Some pass to the dock take their order (The Relay of Rungis).
- **Upstream transport.** Suppliers deliver the wholesaler by their night trucks, or by means of
  special carriers (fish from Brittany arrives in Rungis at night).

Transport constraints: **the cold chain** (never temperature break), **the slots** (a
restaurant does not receive during service, a canteen wants everything before 7 h), **capacity** (weight and volume
of the truck), ** the order of stops** (one does not cross Paris twice), and **the returns** (goods refused,
instructions, empty boxes).

### Clients

| Type | Examples of the package | How it commands | When | What matters most |
|---|---|---|---|---|
| **Gourmet restaurant** | La Table d'Aurélien, Maison Clément | The chef calls or sends a WhatsApp, produced by product, demanding on calibre and origin | in the evening after duty or at night | quality, accuracy, no substitution |
| **Bistrot, traditional restaurant** | Le Bistrot du Port, Le Comptoir de Marie | Phone, "as usual", asks the price | the day before or at night | price, regularity, advice |
| **Brasserie** | Brasserie Le Mazarin | Mail of manager + phone calls from the scale; large regular volumes, contract | the day before in the day | negotiated price by volume, reliability, service |
| **Poissonnier, early** (retail trade) | Poissonerie Lemoine, Marée Bleue | Phone at night, compares all days, buys what is beautiful and cheap | the night for the same morning | prices, freshness, presentation, opportunities |
| **Group restaurant** (canteen, central kitchen, EHPAD, business restaurant) | Vitry Central Kitchen, EHPAD Les Tilleuls | Close order by mail, 2 to 3 days before, according to fixed menus | at days fixed, long in advance | market compliance, fixed prices, health safety, punctuality |
| **Hotel** | Hotel Le Marceau | Economist who centralizes, internal voucher number, chef extras to validate | the day before in the day | procedure, invoice conforming, regularity |
| **Treater** | House Berthier | By event, large punctual volumes, several days before | according to event book | guaranteed volume at date, price at quote |
| **Large and medium area** (GMS) | Ici Créteil costs | Portal or EDI, before one hour limit | the day before 14 h | regulatory labelling, compliance, prices |
| **Export** | — (absent from the pack) | Group orders, long transport | Planned | documents, certificates, packaging |

**They compare.** A professional customer has almost always two or three wholesalers. He calls them the same
This evening, compares the price of the bar, the quality of last week, and distributes its orders. There are two profiles:

- **The faithful**: a main wholesaler, for trust, credit and relationship with his salesman.
  after a build-up of small mistakes, rarely for a few cents.
- **Opportunist**: it buys at the best price of the day. Fishmongers and primers are often: their
  margin depends on their purchase price.

Who prefers what (★★★ = decisive criterion):

| Type of customer | Price | Quality | Service (hour, flexibility) | Time limit for payment | Personal relationship |
|---|---|---|---|---|---|
| Gastronomics | ★ | ★★★ | ★★★ | ★ | ★★★ |
| Bistrot | ★★ | ★★ | ★★ | ★★ | ★★ |
| Brewery | ★★★ | ★★ | ★★★ | ★★ | ★★ |
| Fishmonger, future | ★★★ | ★★★ | ★★ | ★★ | ★ |
| Community | ★★★ (market-based) | ★★ (compliance) | ★★★ (Punctual) | ★ (pays slowly but surely) | ★ |
| Hotel | ★★ | ★★★ | ★★ | ★★ | ★ |
| Caterer | ★★ | ★★ | ★★★ (volume to date) | ★★ | ★★ |
| GMS | ★★★ | ★★ | ★★ (compliance, labelling) | ★★ | ★ |

**Communitys, a world apart.** A public canteen buys by **public market**: a call for tenders,
a specification, a **bordereau of price** fixed for one year or more, per batch ("sea products",
The wholesaler gains or loses the entire market. Then, no trading on the phone:
"the voucher is the voucher." Any unanticipated price difference or substitution is a problem.
payment goes through the public treasury, often slow, and the invoice is deposited on the public platform of
In public collective restoration, the law also imposes a share of products
quality and sustainable (including organic): this is a criterion for choice of suppliers. EHPAD and canteens have
strong requirements: netting without edges, no shells, adapted textures.

### Internal roles: who does what, who calls who

| Role | In the pack | What he does | His timetables |
|---|---|---|---|
| **manager, direction** | Bruno Ménard | Validates large disputes, account release, investment, markets | day |
| **Commercial** | Sophie, Karim, Julien, Nadia | Customer portfolio, purchase orders, prices and discounts, visits, prospecting | offset, often early |
| **Night standard, telemarketer** | Lucas Little | Take orders from 20 h to 6 h, do not negotiate | night |
| **Buyer** | Franck Le Bihan | Buys every night, follows the courses, negotiates, receives | night and morning |
| **Preparators** | (unappointed) | Take each order, weigh, pack, label | 2 h – 5 h |
| **Lender drivers** | Mickaël, Abdel, Sébastien, Thierry, Patrick, Romain | Deliver, sometimes cash, report returns and remarks | 5 h – 9 h |
| **Accounting, recovery** | Helen Garnier | Invoices, assets, receipts, recoveries, unpaid | day |
| **Quality** | (often manager in a PME) | Plan HACCP, temperatures, traceability, recalls | day |

Who calls who:

| Who | Call | For |
|---|---|---|
| Client | commercial or night standard | order, request a price, modify, claim, request the delivery time |
| Sales representative | customer | offer a arrival, revive a silent customer, announce a break, negotiate a contract |
| Buyer | suppliers | marketing, negotiation, batch reservation, quality claims |
| Supplier | buyer | announce a shortage, an increase, a supplement, claim a payment |
| Accounting | customer, supplier | restarting an unpaid, settling an invoice dispute |
| Driver | office, client | delay, customer absent, goods refused |
| Colleague | colleague | "How many Saint James remain?" "Can you call Marie back?" |
| manager | carrier, bank, big customers | Book a truck, negotiate a deal, unblock an account |

---

## Economy and tensions in the trade

**Little Margins.** The wholesaler's gross margin generally represents 15 to 35 % of the selling price (in the pack:
between 15 and 35 % for each product, from `Product.cost` to `Product.price`).
There's little left, every mistake is paid directly.

**The Working Capital Requirement.** The wholesaler pays its suppliers to 21, 30 or 45 days, and its customers on
pay to 30 or 45 days, sometimes 60 in practice. In between, it is he who advances the money. With 1,2 M€ of
sales per month, fifteen days difference represents about 600 k€ to be financed permanently. A customer who pays late
costs cash; a customer who does not pay costs the entire margin of dozens of other orders.

**Perishability.** Simple example: one buys 100 €, one sells 133 € (margin of 25 % on the sale price,
either 33 € (g) If 3 % of what we buy ends up in the trash, we lose 3 € on 33 : near 10 % of the
The gross margin disappears. For fresh fish, which keeps 3 or 4 days, each day counts.

**See the right product at the right time.** You must buy *before* to know. Customers order the previous day or the
Even night, but the buyer placed his orders the night before for the next one. Too little: break, customer
Disappointed, client leaving. Too much: unsold, forced promotion, loss. The job consists of planning from
history ("Tuesday, Blue Sea orders big"), calendar (fests, school holidays), weather,
orders already received and promises from customers.

**Price volatility.** The purchase prices of the fee move every day (in the pack: ±10 % around the cost of
The sale price must remain legible for the customer. A sharp rise is managed by the
"Take hake this week" rather than an increase announced on the phone.

**Variable quality.** Two batches of the same product are not valid: size, freshness, fat, colour,
Presentation. The gourmet chef refuses what a bistro will accept. The wholesaler must direct each lot
to the right customer.

**Color the stock.** A lot approaching its date must leave: it is called "to push".
offer customers who usually take it, make a price, offer it to customers open to promotions
(fishers, brewers), transform it (nets, portions), or downgrade it.

**The substitution.** When a product is missing, we propose an equivalent: other caliber, other origin, rearing in the
wild place, frozen instead of fee. It is a service if the client agrees, a mistake if it is not.
Not.

**The credit risk.** Each customer has a **credit ceiling** (maximum amount allowed).
delays, restart, sometimes **block** a customer: no more delivery until he has paid. Block too much
early makes a client lose; too late, money.

**Competition.** The customer compares every day. The relationship (the salesman who knows the leader's card, who
recalls at the right time, which remembers the complaint) is often what makes the difference.

---

## A day of 24

A wholesaler's timetable is tidal on a MIN, as in the pack. A wholesaler of fruits and vegetables or meat has a
near pace, a little later; a grocery or beverage wholesaler works mostly daytime.

| Time | What's happening | Who | In the pack |
|---|---|---|---|
| Watch, 4 h – 9 h | Screaming in ports; fishers buy ; mercurials sent | marketers, buyer | today's supplier price (`SupplierPrice.updatedAt`) |
| Watch, 9 h – 14 h | The buyer finished negotiating for the next night; commercials on the phone; hotels and communities send their orders | buyer, commercial | orders `createdBy` = commercial |
| Watch, 14 h – 18 h | Orders by mail from breweries, supermarket portal (before 14 h); invoicing, renewals | commercial, accounting | `Order.source` = `email`, `web` |
| Watch, 18 – midnight | Chiefs order after service (telephone, WhatsApp) | night standard | `createdBy: "lucas"`, `source: "whatsapp"` |
| 0 h – 2 h | Oyster bars, late restaurants; truck suppliers drive | night standard | `draft` commands to be validated |
| 2 h – 3 h | Reception of truck suppliers: control, one lot per line | recipient, buyer | `Lot`, movements `receipt` |
| 3 h | Night inventory: we throw away what has exceeded its date, we declassify | preparers | movements `waste`, `adjustment` |
| 2 h – 4 h 30 | Fishers and bistros order for the same morning; preparation: pickling, weighing, labelling | standard, preparators | `preparedQty`, status `prepared` |
| 3 h 40 – 4 h | The buyer sends the supplier orders for the next night (or J+2, J+3) | buyer | `PurchaseOrder.status` = `sent` |
| 4 h 30 | Time limit to be delivered the same morning | — | `meta.today` à 4 h 30 |
| 5 h – 6 h | Departure of tours | Drivers | Day `RouteRun` |
| 5 h 30 – 9 h | Delivery; calls "where is the truck?"; refusal and return to unloading | Drivers, office | status `delivered`, movements `sale` |
| 9 h – 12 h | Return of trucks, returns and crates; morning complaints; day auctions | Drivers, commercial | `ClientEvent` of type `complaint` |
| 12 h – 18 h | Invoices, receipts, re-launches, quotations, prospecting, preparation of purchases | accounting, commercial | `Invoice`, `Payment` |

On Sundays, nothing usually goes on. On Mondays, some tours do not ride (in the pack, Paris Sud and
Ups-de-Seine & Yvelines). On Christmas Eve and New Year's Eve, volumes explode and schedules stretch.

---

## The rules of the trade (hygiene, traceability, payment)

These rules are general and simplified, and they are sufficient for an agent not to say anything stupid.

- **Cold chain.** Fresh remains in the positive cold (around 0 to +4 °C; fish under ice, close to
  0 °C). Frozen remains at −18 °C or less. Frozen product does not recongregate. Temperatures are
  checked at reception, in the cold room and in trucks.
- **HACCP.** Every food business applies a hazard analysis hygiene plan (HACCP):
  Critical points, temperatures, cleaning, training. Establishments handling original products
  animal generally have a ** health approval** (the oval mark on the labels).
- **Traceability by lot.** Every professional must know from whom he has received a product and to which professional
  The wholesaler therefore follows each **lot**: supplier, date
  In the event of a health alert, he must be able to **Remove** the lot and
  notify the customers concerned quickly.
- **shelf life and DDM.** The **shelf life** (the consumption limit date, "to be consumed until") applies to products of high quality.
  Perishable: After, you no longer sell, you throw away. The **DDM** (date of minimum durability, "to consume of
  This is the case for stable products (groceries): after, the product may lose quality but
  is not dangerous.
- **Original label.** For fish sold to the consumer: commercial name and scientific name, fashion
  (fishing or high), fishing zone (FAO) or breeding country, and type of fishing gear.
  for that Ici Créteil expense refuses all box without FAO label and fishing gear.
  For beef and veal: origin is compulsory, including for beef and veal.
  restaurant.
- **Living shells.** Oysters, mussels, clams are sold live, with a sanitary label on
  each box.
- **VAT.** Food is at 5,5 % in France; alcoholic beverages at 20 %. In the pack, all
  the catalogue is in 5,5 % (`Product.vatRate` = 0.055).
- **Payment time.** The law limits payment times between companies. For **denres
  Perishable food**, the ceiling is short: about 30 days after delivery (specifyly, 30 days
  Other purchases are capped above. Any delay gives the right to
  penalties and a lump sum recovery compensation. Public purchasers have their own legal time limits,
  In the pack, some customers have 45 days: it is a choice of fiction, not to be missed.
  take as a legal model for the fee.
- **Prices and discounts.** Only authorized persons (commercial, management) grant a special prize.
  Standard night or vocal agent does not negotiate: it notes and transmits.

---

## The fields of trade, one by one

Each block follows the same plan: **What it is**, **Vocabular**, **How it works**, **The challenges**,
**In the ERP**.

### Customers

**What it is.** The portfolio: about 100 very different professionals (see "Customers"
Each has its own delivery days, terms of payment, habits, interlocutors and
His story with the wholesaler.

**Vocabular.**

- *Customer details*: address, area, delivery days, payment terms, ceiling, commercial.
- *Commercial*: the person who "holds" the customer. Some customers only want to talk to him.
- *The usual*, *the usual basket*: what the customer almost always orders.
- *Current* *credit ceiling*, *blocked customer*: see Billing.
- *Prospect*: potential customer, no order yet.
- *Client at risk*, *client who picks up*: he orders less, compares more, complains.

**How it works.** Each customer has a rhythm: every days, three times a week, according to the menus.
strong habits ("as usual", "last time salmon") and fixed requirements:
Sakana wants salmon from Scotland Red Label and never from Norway, the EHPAD The Tilleuls wants nets without
raisins & marée is closed on Monday and Tuesday. He often has several interlocutors: the chef chooses
the products, the manager validates the prices, the accountant pays. At the Hotel Le Marceau, everything goes through the economy with
House Clement only wants to be recalled by Karim, and never after 5 h 30.

**Challenges.**

- The client never gives his ID. He says "it's Marc du Bistrot", "it's Yann", or nothing at all.
  It must be recognized in name, number, voice, context.
- We must remember everything: last week's claim, the delay in payment, the name of the
  Second, the closing in August. The best commercial does so in memory; the night standard cannot.
- An ill-treated customer goes to the competitor from across the street, often without saying anything: he just orders less.

**In the ERP.**

- Entity `Client` : `code`, `name`, `type` (`restaurant` | `brasserie` | `fishmonger` | `canteen` |
  `supermarket` | `caterer` | `hotel`), `contacts[]` (`name`, `role`, `phone`, `email`), `address`, `city`,
  `zone`, `deliveryDays` (`mon`…`sun`), `paymentTermsDays`, `creditLimit`, `status` (`active` | `blocked` |
  `prospect`), `salesRep`, `preferences` (free summary), `notes[]` (`at`, `author`, `text`), `tags` (free summary),
  customers: `gastro`, `brasseries`, `collectivites`, `marche-public`, `a-surveiller`...).
- Regular basket: `GET /api/clients/{id}/usual`, calculated on orders of the last 60 days (products
  present in at least 25 % of the commands, with `avgQty`, `lastQty`, `frequency`).
- Full sheet : `GET /api/clients/{id}` (negotiated prices, recent orders, open invoices, payments,
  Traditional basket, historical). Commercial note: `POST /api/clients/{id}/notes`.
- Memory: context table (`ContextEntry`, `entityType: "client"`, `entityId: "cli_…"`), with plugs
  by client ("How to talk to them", "What's annoying them", open files). `GET /api/context/for?entityType=client&id=cli_0001`.
  Readable persona sheets in `./data/context/clients/`.
- Agent tools: `search` ("port bistro" → `cli_0007`), `get_client` (fiche, usual basket,
  notes, open problems, 5 latest events), `get_context`, `save_context` (memorize a lasting fact).
- Pages: **Clients**, customer detail (Context tab, block "What the agent knows"), **Contexte**, **Groups**.
- **Rule.** Before answering a customer: identify it (`search`), load its plug (`get_client`) and sound
  context (`get_context`). Check `status` : `blocked` or `prospect` change the whole conversation.

### Ordering and sales

**What it is.** The core of the activity: turning a call, an email, a WhatsApp or a voice message into one
order just, delivered to the right place on the right day. In the pack, over twelve months, 61 % orders arrive
by telephone, 24 % by email, 9 % by WhatsApp, 5 % by the web portal and 2 % are entered at the dock.

**Vocabular.**

- *Pre-order*, *bruillon*: command entered but not yet validated by the client.
- *Order line*: a product, a quantity, a price.
- *Quantity ordered* and *Quantity prepared* (the actual weight).
- *Time limit*, *cut-off* : after, the order leaves on the next day of delivery.
- *Routture* : more stock. *Partial delivery* : we deliver a part.
- *Substitution*: one product in place of another, with the consent of the customer.
- *Reread* *recap* : Reads the order to the customer before hanging up.
- *Good delivery (BL)*: the document accompanying the goods.
- * Troubleshooting*: an urgent order out of the usual rules.

**How it works.**

1. The customer calls, often at night, and dictates in bulk: "Put me 5 kilos of bar, 2 boxes of moulds and
   oysters as usual."
2. The seller identifies the products ("wolf" = bar), checks the stock, announces the prices if it is
   request, propose an alternative if a product is missing.
3. It keeps ** a single ** command open and complete as the call is made: the customer often adds a
   article at the end.
4. Il **relit**: "I'm recapitulating for tomorrow Wednesday: 6 kilos of sole 500-600, 3 kilos of nuts
   Saint-Jacques, 2 kilos of half-salt butter. Delivery by the Paris West tour, around 6 h. It's good for
   You?"
5. The customer says yes: the order is **confirmed**. It then passes in preparation, in delivery, then in
   Billing.

**Challenges.**

- The names are blurred ("of 3" = hollow oysters size 3, "nuts" = Santiago nuts, "of
  place" = place yellow or place black ?). The doubt must be lifted without annoying.
- Units vary: kilos, pieces, dozens, box, crates, "a bucket of cream" (5 liters), "one
  full of 4 dozen".
- The client changes his mind, interrupts, speaks with noise behind, at 3 in the morning.
- Everything happens at the same time between 22 h and 4 h 30. An error is a fishless chef for his service.
- The day of delivery is not obvious: before or after the deadline, day of tour or not, days of
  closing of the customer.

**In the ERP.**

- Entities `Order` (`number` "CMD-2026-000123", `clientId`, `status`, `source`, `deliveryDate`, `routeRunId`,
  `totalHt`, `note`, `createdBy`, `confirmedAt`, `deliveredAt`, `invoiceId`) and `OrderLine` (`productId`, `qty`,
  `unitPrice`, `preparedQty`, `note`, `substituteFor`).
- `Order.status` : `draft` → `confirmed` → `prepared` → `delivered` → `invoiced`, or `cancelled` since
  `draft`, `confirmed` or `prepared`. A prohibited transition returns an error 409 `invalid_transition`.
- `Order.source` : `phone` | `voice_agent` | `email` | `whatsapp` | `manual` | `web`.
- Roads: `POST /api/orders`, `POST /api/orders/{id}/lines`, `PATCH /api/orders/{id}/lines/{lineId}`,
  `DELETE /api/orders/{id}/lines/{lineId}`, `PATCH /api/orders/{id}` (date, note), `POST /api/orders/{id}/confirm`,
  `/prepare`, `/deliver`, `/invoice`, `/cancel`.
- Agent tools: `create_draft_order`, `add_order_line`, `confirm_order`, `get_order`. There is no
  tool to modify or delete a line, change the date or cancel: routes exist, tools
  are to be written.
- Alerts: Each current command returns `warnings[]` with a `code`: `client_blocked`, `credit_limit`,
  `no_route` (no tour that day for the area), `insufficient_stock`, `expiring_soon` (the lot released in
  `price_below_cost`. **These alerts do not block
  Never **: the backend still confirms. It's up to the agent to react.
- Default date: without `deliveryDate`, the ERP takes the customer's next delivery day *only after*
  `meta.today`. An order for the same morning must therefore give the date explicitly. Time limit (4 h 30
  in the pack) is **pas** applied by the backend: it is written in `context/06-livraisons-zones.md`.
- Pages: **Orders**, detail of an order (lines, alerts, tour, invoice), **Voix**, **Activity**.
- **Rule.** Confirmation (`confirm_order`) is only confirmed after an explicit "yes" from the client on the summary.
  Without clear confirmation, the command remains in `draft`.
- **Rule.** Only one current command per call: add lines, do not create a second one.
- **Rule.** A `prepared` command no longer changes except for the quantity prepared and the note (backend)
  A `confirmed` command is still changing.

### Products and catalogue

**What it is.** A few tens to a few thousand references, arranged by radius.
** clean to each company** (`seed/categories.json`, `GET /api/categories` → `[{id, label}]`): look at those
Of yours.

**Vocabular.**

- *Reference*, *article*, *SKU* (article code, e.g. `BAR-LIG-12`).
- Bar 1-2 kg, sole 500-600 g, lobsters 15/20 (15 to 20 pieces per kilo), oysters No 3
  (The smaller the number, the bigger the oyster).
- *Sauvage* or *line* (fished) against *breeding* : prices and image very different.
- *Origin*: Brittany, Scotland, Norway, zone FAO.
- *Label* : Red Label, AOP (Mont-Saint-Michel culhot mules, Butter d'Isigny), organic, MSC.
- *Sales unit*: kg, piece, dozen, box, liter. *Collection*: how many units per box.
- *Alias*: the names that customers use ("wolf" for bar, "cab" for cod).
- *Seasonal* *out of season*, *festery*.
- *Product to be pushed*: a product to be disposed of quickly.

**How it works.** Each product has a catalog price, a reference cost, a unit, a duration of
Conservation, origin, calibre, primary supplier and acceptable substitutes.
catalogue changes with the seasons: sardine and sea spider are inactive in November;
Santiago opens in October. A good seller also knows what is not written anywhere: what product is
this week, which is expensive, which must be sold out.

**Challenges.**

- The same product has ten names; two close products have nothing to do with a chef (line bar at 32,50 €/kg
  and rearing bar at 14,90 €/kg).
- The offer changes every day depending on the fishery or harvest.
- The agent must know the catalogue better than the customer, and know when to ask for a precision ("Yellow Place"
  or black place?") rather than guess.

**In the ERP.**

- Entity `Product`: `sku`, `name`, `aliases[]`, `category` (id of a class of
  the company, see `GET /api/categories`), `unit` (`kg`) `piece` (`box`) `dozen` (`liter`),
  `price` (price list € excl. VAT), `cost` (reference cost € excl. VAT), `vatRate`, `shelfLifeDays`, `origin`, `caliber`,
  `mainSupplierId`, `active`, `tags` (`premium`, `fetes`, `labels`, `best-sellers`, `saison`…).
- Roads: `GET /api/products?q=&category=&tag=`, `GET /api/products/{id}`, `GET /api/products/{id}/alternatives`.
- Flavoured search: `GET /api/search?q=` (accents, errors, aliases, ignored fill words); `search` tool.
- Tools: `get_product_stock`, `find_alternatives` (same radius, in stock, nearest price), `get_context`
  with `entityType: "product"` or `"category"`.
- Complete glossary with alias, prices and shelf life: `./data/context/03-glossaire-produits.md`.
- Pages: **Products**, product detail, **Groups**.
- **Rule.** `find_alternatives` knows only the radius and the price. The replacement "trade" (wild turbot →
  breeding turbot, Red Label → Norway) and the customer's refusals are in the context and the playbook:
  check before proposing.

### Price

**What it is.** The price of a product is not the same for everyone, nor from one day to the next.
customer has negotiated prices, a group of customers has discounts, a promotion lasts a week, a public market
sets everything for a year.

**Vocabular.**

- *Catalogue price* *list price* : basic price.
- *Negotiated price*, *Customer price*: a price for a customer and a product.
- *Remise* (in %), *price rule* (for a group of customers or a radius), *volume price* (from 50 kg).
- *Marge* : sale price less cost. *Coefficient* : sale price divided by cost.
- *Course of the day* : purchase price that varies with the auction.
- *Farm price* : guaranteed for a period. *Farm price* : fixed by a public market.
- *Cotation*, *devis* : a price proposed before the order.
- *Commercial gesture*: a reduction granted to repair a problem.

**How it works.** The price of a line is decided in this order:

1. A **price negotiated** for this customer and this product: it always wins.
2. Otherwise, the most precise **price rule** that applies (e.g. "Gastro: -5 % on crustaceans",
   "Volume: culhot moulds -4 % from 50 kg").
3. Otherwise, the **prix catalog**.

The price is fixed on the line at the time it is created. The purchase prices of the fee move every day, but
The sales prices remain stable: the price of the bar on the telephone is not changed because the auction went up, we
advises another species.

**Challenges.**

- A false price is lost margin or an angry customer on the bill.
- Defend the margin against a trading customer ("at the other side, it's 2 € less").
- Know who can grant a discount. In the pack: only the commercials; the night standard and the agent
  The Zinc of the Halles negotiates everything, but nothing is decided without Karim.
- Report a good deal: "From 50 kilos, the mould goes to 4,70".

**In the ERP.**

- `ClientPrice` (`clientId`, `productId`, `price`): `PUT` and `DELETE /api/clients/{id}/prices/{productId}`.
- `PriceRule` : `name`, `active`, `priority`, `clientScope` (`all` | `client` | `tag`), `productScope` (`all` |
  `product`, `tag`, `category`, `method` (`fixed` fixed price) `discount_pct` discount on list price
  `markup_pct` cost margin), `minQty`, `validFrom`, `validTo`. Routes `/api/price-rules`.
- Resolution: `GET /api/prices/resolve?clientId=&productId=&qty=` returns `price`, `listPrice`, `source`,
  `explanation` in French and all candidates. Grid: `GET /api/prices/grid?clientId=` or `?clientTag=`.
  The calculation lives in `apps/backend/app/services/pricing.py`, and nowhere else.
- Tool: `get_price` (also returns `betterPriceWithVolume` when a volume rule would give better).
- The control tools do not allow you to set a price: the ERP solves it.
- Special package agreements: `./data/context/05-prix-et-credit.md`.
- Page: **Price** (customer matrix × products, rules, negotiated prices, margin simulator).
- **Rule.** Always go through `get_price` (or `/api/prices/resolve`) to announce a prize. never
  calculate a discount in the prompt.
- **Rule.** The vocal agent does not grant any discounts: it notes the application (`log_client_event` of type
  `price_negotiation`) and forward it to the commercial.

### Procurement and suppliers

**What it is.** Buy every night what will be sold the following days, from the fishers, producers,
importers and industrialists (see "Suppliers" above).

**Vocabular.**

- *Order of purchase*, *Order of supplier*, *Order of order*.
- *Mercuriale*: the price list of a supplier's day.
- *Time period*: J+1, J+2, J+3 (days between order and delivery).
- *Order minimum*, *franco* (amount from which transport is offered).
- *Arrival*, *disembarkation* (what the boats bring back), *contribution*.
- *Receipt*, *partial receipt*, *additional* (the rest, delivered later).
- *Coverage*: how many sales days the stock allows to hold.
- *Reference*: Bring in a new supplier.

**How it works.** The buyer compares the prices of several suppliers, calls to negotiate or book a
lot, order pass, then receive. In the pack: the fee is ordered every night for the next night,
with about two days blankets; frozen on Monday, Wednesday or Thursday (J+2); cream and
on Monday or Thursday (J+3). The goods sometimes arrive in different quantity or quality: Oysters
Joubert delivered incomplete on specials no. 3, supplement announced on Thursday.

**Challenges.**

- Buy enough to serve everyone, without buying what will end up in the trash.
- Compare prices that change every day, between suppliers that do not have the same reliability.
- Respond when fishing doesn't come out: the storm in Brittany puts the wild turbot and the lobsters 15/20 at
  zero, and a purchase order remains in draft until the supplier has confirmed.
- Respect the minimums and cut-off hours of each supplier.

**In the ERP.**

- `Supplier` : `name`, `contacts[]`, `city`, `categories[]`, `leadTimeDays`, `paymentTermsDays`,
  `minOrderAmount`, `notes`, `tags` (`mareyeur`, `producteur`, `ostreiculteur`, `importateur`, `grossiste`).
- `SupplierPrice` (`supplierId`, `productId`, `price`, `updatedAt`): last known price for each
  supplier. The flagship products have 2 or 3 possible suppliers. No route updates this price.
- `PurchaseOrder` (`number` "ACH-2026-000045", `supplierId`, `status`, `expectedDate`, `totalHt`, `note`) and
  its lines (`productId`, `qty`, `unitPrice`, `receivedQty`).
- `PurchaseOrder.status`: `draft` → `sent` → `partially_received` → `received`, or `cancelled`.
  change only to `draft`.
- Roads: `/api/purchase-orders` (create, lines, `/send`, `/receive`, `/cancel`), `/api/suppliers`,
  `/api/suppliers/{id}/usual` (usually purchased from this supplier).
- Non-blocking alerts: `below_min_order`, `not_in_supplier_catalog`, `price_above_usual` (more than 10 %
  above the last known price).
- Agent tools: `get_supplier_history`, `log_supplier_event` (quality, delay, shortage, price increase),
  `get_context` with `entityType: "supplier"`. **No purchase tool**: create or send an order
  supplier asks to write the tool (roads exist).
- Supplier Personal Data Sheets: `./data/context/suppliers/`.
- Pages: **Achats**, purchase order detail, **Suppliers**, supplier detail, **History**.
- **Rule.** A supplier order compares to the last known price (`SupplierPrice`) and to the minimum of
  supplier before being sent.

### Stocks, lots and dates

**What it is.** What is actually in the cold room, lot by lot, with the deadline for each lot.

**Vocabular.**

- *Lot*: an arrival of a product, with its date of receipt, its deadline and its supplier.
- *shelf life*, *DDM*: see "The rules of the trade". In the pack, "shelf life" means the life in days after
  reception.
- *FEFO* (*first expired, first out*): the lot that expires earlier is first released.
- *Physical stock* (which is in a cold room), *reserved stock* (promise to confirmed orders), *stock
  available* (physically less reserved), *to be received* (commanded to supplier, not yet arrived).
- *Casse*, *loss*, *demark*, *destruction* : which is thrown.
- *Decommissioning*: a product that is no longer beautiful enough for its normal use, sold cheaper or processed.
- *Inventory*: the actual count, which corrects the theoretical stock.

**How it works.** Each reception creates a lot. When an order is confirmed, the quantity is reserved.
At the time of preparation and departure of the truck, the goods exit in FEFO. In the night inventory, which exceeded
A good salesman can say on the phone: "I still have 12 kilos left, shelf life
Thursday."

**Challenges.**

- The fresh fish is kept three or four days, the mackerel three. Each lot that ages must find
  Taker.
- The theoretical stock and the actual stock diverge (weighed, broken, input errors).
- A lot that expires soon is an opportunity: to offer it to customers who take it, at a sale price.
- A rupture announced too late does more damage than an early break: The Docks want to be
  48 hours ahead, Vitry 72 h front central kitchen, in writing.

**In the ERP.**

- `Lot` : `productId`, `supplierId`, `purchaseOrderId`, `qtyReceived`, `qtyRemaining`, `receivedAt`,
  `expiresAt`. Upon receipt of a purchase order, `expiresAt` = date of receipt + `Product.shelfLifeDays`.
- `StockLevel` (calculated, never stored): `onHand` = sum of `qtyRemaining`; `reserved` = quantities of
  `confirmed` or `prepared` commands (prepared quantity if known); `available` = `onHand` - `reserved`;
  `incoming` = outstanding purchase orders `sent` or `partially_received`; `nextExpiry`.
- The reservation is made ** by product**, not by lot. Lots are consumed (FEFO) only upon delivery
  (`POST /api/orders/{id}/deliver`).
- `StockMovement.reason` : `receipt` | `sale` | `adjustment` | `waste` | `return`.
- Roads: `GET /api/stock`, `GET /api/stock/movements?productId=`, `POST /api/stock/adjust` (`reason`
  `adjustment` or `waste`; `waste` always removes).
- Expired batches are not **pas** automatically destroyed: `waste` is required via `/api/stock/adjust`.
- Agent Tool: `get_product_stock` (available, physical, booked, receivable, next deadline, price
  There is no stock movement tool.
- Page: **Stocks** (lots, shelf life, movements).
- **Rule.** Advertise the **available** (`available`), never physics: the rest is already promised.
- **Rule.** If available is not enough, look at `incoming` and the expected date of purchase order
  before saying "break-up".

### Preparation and weighing

**What it is.** At night, preparers take each order, choose lots, weigh, pack under
Ice cream and label.

**Vocabular.**

- *Preparation*, *picking*: take the products in a cold room.
- *Real weight*, *variable weight*: what really weighs what is delivered.
- *Weighing range*: difference between ordered and delivered.
- *box*, *box*, *bac*, *label* (product, lot, date, origin).
- *Absorbing*: emptying, scalding, rising in nets, serving. The chef often asks for "drained", "headless",
  "in nets".

**How it works.** The customer orders 6 kilos; they deliver a fish of 5,8 or 6,3 kilos.
the actual weight. In the pack, the normal difference on the fish per kilo is −4 % to +6 %.
Preparation ("empty", "headless") are notes on the line. A prepared order is weighed and packaged:
changing it disorganizes everything.

**Challenges.**

- Keep reasonable deviations and explain them: Brasserie Montparnasse 1925 often contests weights and
  Pays her bills less the variances she estimates.
- Last minute orders arrive during preparation.
- Know what is still editable at the time of the appeal.

**In the ERP.**

- `OrderLine.preparedQty`: quantity actually prepared. If it exists, the total and invoice are calculated
  on it, if not on `qty`. `OrderLine.note` : « empty, "headless", "well fresh ».
- Route: `POST /api/orders/{id}/prepare` (with or without quantities per line; an unlisted line is prepared
  Transfer the command from `confirmed` to `prepared`.
- No preparation tool for the agent.
- Page: order details (ordered, prepared columns).
- **Rule.** Before promising a change, look at `Order.status`: `draft` or `confirmed` =
  editable; `prepared` = only the prepared quantity and note change; `delivered` or after = too late,
  It's either a claim or a return.
- **Rule.** When a customer requests a total price for a product by weight, specify that this is an estimate
  and that the invoice will follow the actual weight.

### Deliveries and tours

**What it is.** Refrigerating trucks that deliver each customer in a niche, according to area tours
In the pack: six tours from Rungis between 5 h and 6 h.

**Vocabular.**

- *Tour* *zone* *days tour* *start time*.
- *Stop* *order of stops* *estimated time* *crene*.
- *Lender driver*, *quai*, *service door*, *key* (delivery in the absence of the customer).
- *Back*, *refused with delivery*, * client absent*.
- *Offer*: rent a truck or entrust to a carrier.

**How it works.** Each customer belongs to an area, served by a tour some days.
Only the dayss where the tour runs ** and ** are available in its delivery dayss. A tour brings together
the orders confirmed of the day in a specific order. The driver leaves, delivers, reports returns and
sometimes the money (payment to the driver for Phở Saigon 13 or Le Festin Nomade).

**Challenges.**

- "What time are you delivering me?", "I won't be there until 7 h," "deliver through the service door":
  These questions are coming up all morning.
- A delay breaks the service of a restaurant or the production of a central kitchen.
- The capacity of the truck is limited: Saturdays and holidays require a second truck.
- The constraints specific to each customer: dock number 2 before 7 h, delivery from Wednesday to Saturday only,
  Blue lobster only on Friday and Saturday.

**In the ERP.**

- `Route` : `name`, `zone`, `driver`, `vehicle`, `capacityKg`, `days`, `departureTime`.
- `RouteRun` : a tour on a date (`routeId`, `date`, `status` : `planned` | `in_progress` | `done`) with
  its `stops[]` (`orderId`, `clientId`, `seq`, `eta`, `status`: `pending` and `delivered` and `failed`, `note`).
- Confirm an order connects it to the tour of the customer's area on its date (`Order.routeRunId`).
  draft order is not on any tour.
- `eta` = departure time + 12 minutes per stop (simple calculation). Weight for capacity: kg and litres such
  box (`box`) 5 kg, piece or a dozen 1 kg.
- Roads : `GET /api/routes`, `GET /api/route-runs?date=`, `POST /api/route-runs/plan`, `PATCH /api/route-runs/{id}/stops`
  (reordering)
- Absent: carriers, truck reservation, slots per customer, follow-up GPS. Delivery constraints
  are in context (`kind: "logistics"`) and in `context/06-livraisons-zones.md`.
- No tour tool for the agent: "Where is Mon truck?" asks to write the tool.
- Page: **** spins.
- **Rule.** For "what time am I delivered?": find the customer's day order, its `RouteRun`, the stop
  and his `eta`. Otherwise, give the fork of the tour.
- **Rule.** An alert `no_route` means that the tour of the area does not run that day: propose the
  Next day of delivery.

### Invoicing, payments and outstanding amounts

**What it is.** Invoice every delivery and get paid. It is often the hardest.

**Vocabular.**

- *Facture*, *relevé* (invoice that includes several deliveries), *avoir* (negative invoice after a return)
  or a dispute).
- *Deadline*, *payment period* ("30 days"), *cash payment*, *payment on delivery*.
- *Receipt*, *Receipt*, *lettering* (approximating a payment from the invoices it pays).
- *Current*: what the client must. *Spent*: what is late. *Age balance*: the outstanding amount per tranche of
  delay (to fail, 1-30 days, 31-60...).
- *Relaunch* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery* *Recovery*Recovery*Recovery*Recovery*Recovery*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover*Recover****Recover*Recover**
- *Credit base*, *client blocked*, *unblocking*.
- *DSO*: Average payment time for customers, in days.

**How it works.** In general, one invoice per delivery, with a maturity according to the customer's terms.
Some clients receive a weekly or monthly statement. Payments arrive by transfer (often a
If you pay a fee, you can pay a fee to the driver.
delay; the accounting officer restarts with the exact number, date and amount of each invoice.
or after too much delay, the customer is blocked: no more delivery until he has paid.

**Challenges.**

- A customer who does not pay more than a lost customer.
- Tactfully block: A blocked customer who calls 3 h to order must be well received, but none
  order must not leave.
- Not all slow payers are at risk: a community pays to 45-60 days but still pays; it does not
  Don't block it.
- Disputes block payments: a disputed invoice remains partially paid.

**In the ERP.**

- `Invoice` : `number` « FAC-2026-000210 », `clientId`, `orderIds[]`, `status`, `issuedAt`, `dueDate`,
  `lines[]`, `totalHt`, `totalVat`, `totalTtc`, `amountPaid`. `dueDate` = `issuedAt` + `Client.paymentTermsDays`.
- `Invoice.status` stored : `draft` | `issued` | `partially_paid` | `paid` | `cancelled`. **`overdue` is
  Never stored**: it is calculated on reading (open invoice including `dueDate` < `meta.today`).
- `Payment` : `clientId`, `amount` (€ incl. VAT), `method` (`transfer` | `card` | `cheque` | `cash` |
  `direct_debit`), `receivedAt`, `reference`, `allocations[]`. Without allowances, payment balances invoices
  open the oldest first.
- Outstanding: `GET /api/receivables` (old balance per customer: slices `current`, `d1_30`, `d31_60`, `d61_90`,
  `d90plus`, `avgDaysToPay`, `risk`, DSO). `risk` = `high` if current > ceiling, delay > 60 days, customer
  Blocked, or pays on average more than 60 days with fallen; `watch` if outstanding > 80 % of ceiling, delay >
  30 days, an open `late_payment`, or pays an average of more than 45 days.
- `Client.creditLimit` is in € incl. VAT; `Client.paymentTermsDays` = 0 means payment on delivery.
- Routes: `GET /api/invoices?clientId=&status=` (accepts `open` and `overdue`), `GET /api/invoices/{id}`,
  `POST /api/orders/{id}/invoice` (one invoice per order delivered), `GET/POST /api/payments`.
- Absent: holdings as documents (only `credit_note` events in history), records
  automatic grouping, late penalty.
- Agent Tools: `get_client` returns `outstanding`, `overdue`, `creditLimit`, `paymentTermsDays`. There is no
  no tool to list invoices or record a payment (example of README, `list_overdue_invoices`,
  shows how to write it).
- Pages: **Factures**, **Payments**, **Current**.
- **Rule.** The backend **does not prevent** from confirming an order for a `blocked` client or beyond its
  ceiling: it only returns alerts `client_blocked` and `credit_limit`. The business rule, in
  `context/05-prix-et-credit.md`: for a blocked account, no confirmed order, at most a draft with
  a note, and it is passed on to the salesman or to the accounts.
- **Rule.** If an order would exceed the ceiling: do not refuse dryly; save in draft
  with a note, warn politely, transmit. If the client has fallen, say it tactfully and propose a
  Regulation.
- **Rule.** In a restart, always quote number, date and exact amount. never recite memory:
  Read the bills again.

### Claims, returns and disputes

**What it is.** Everything that goes wrong after delivery: damaged product, missing, bad caliber, bad
prepared, delivered late, price or weight error. And, supplier side: poor quality lot, delivery
incomplete, unexpected increase.

**Vocabular.**

- *Claim*, *Litigation*, *Open* *Resolved*.
- *Back merchandise*, *refused delivery* (the chef sends back to the driver what is wrong).
- *Avoir* : amount refunded or deducted from the next invoice.
- *Commercial gesture*: a discount to repair the relationship.
- *Replacement*: Deliver the right product.
- *risk of losing the customer*: A client who threatens to go elsewhere.

**How it works.** The customer calls or the driver reports the problem.
quantity, lot, date of delivery, what the customer says. The file is open. The commercial decides on the
answer (avoir, replacement, gesture), the accounting issues the asset. The file is solved. Example of the package: The
Table d'Aurélien refused 1 kg of lobsters not bright enough the 18/11, deducted from the bill.
supplier, the buyer in turn claims: to have supplier, replacement, or price decrease on the
Next order.

**Challenges.**

- A customer who calls back for an already open claim wants us to remember, without having to do anything.
  to explain again.
- An agent who ignores the ongoing litigation and happily proposes a new order loses the customer.
- Do not promise on the phone what only the commercial can grant.
- Link a customer claim to its lot and supplier.

**In the ERP.**

- `ClientEvent` : `type` (`onboarding`, `call`, `visit`, `complaint`, `quality_issue`, `delivery_issue`,
  `return`, `credit_note`, `dispute`, `late_payment`, `payment_plan`, `price_negotiation`, `special_request`,
  `menu_change`, `contact_change`, `compliment`, `churn_risk`, `won_back`, `note`), `title`, `description`,
  `channel`, `author`, `severity` (`low` | `medium` | `high`), `status` (`open` | `resolved`), `resolution`,
  `orderId`, `invoiceId`, `productIds`, `amount`.
- `SupplierEvent`: same fields, `type` among `quality_issue`, `delivery_issue`, `shortage`, `return`,
  `credit_note`, `dispute`, `price_change`, `price_negotiation`, `invoice_issue`, `payment`, `contract`,
  `certification`, `contact_change`, `compliment`, `call`, `visit`, `onboarding`, `note`; link
  `purchaseOrderId`.
- Roads: `GET/POST /api/clients/{id}/events`, `PATCH /api/client-events/{id}` (window), side Idem
  suppliers.
- Tools: `get_client_history` and `get_supplier_history` (first opened folders), `log_client_event`
  and `log_supplier_event` (the problems are created `open`). `get_client` already returns `openIssues` and 5
  recent events.
- Absent: a merchandise return endpoint (the reason for movement `return` exists, not the road),
  assets as documents, the automatic link lot → customers delivered.
- Page: **History** (clients and suppliers), historical tabs of the sheets.
- **Rule.** Start any call from a client with its open folders (`openIssues`).
  Sell.
- **Rule.** During the call, record the claim faithfully (`log_client_event`), without promising to have
  A lasting fact (preference, constraint) goes in context (`save_context`), not in
  history.

### Seasons and hazards

**What it is.** The calendar, the weather and the news decide almost everything: what you can buy, what you can buy, what you can buy.
the customers want, at what price.

**Vocabular.**

- *Season*, *opening* (start of fishing of a species, such as the Saint James in October), *closure*.
- *Pic*, *creux*, *fests*, *bridge*.
- Seagull, zero landing, penury.
- *Prediction*, *anticipation*, *pre-order parties*.

**How it works.**

- **End of year**: oysters, lobsters, lobsters, scallops, smoked salmon.
  caterers pre-order weeks in advance (Maison Berthier has a draft for the 19/12), the
  breweries negotiate their volumes (The Mazarin awaits a proposal before the 1er December).
  reserve at suppliers and rent trucks.
- **Août**: Parisian restaurants close, volumes drop, some pay late (L'Ecume).
- **School holidays**: canteens stop (Issy's central kitchen is not delivered).
- **Career, Easter, Friday**: more fish. **Summer**: more drinks, fruit, light products.
- **Weather**: a storm blocks fishing several days (at this moment: no landing at Guilvinec since
  Friday); a heat wave changes demand and threatens the cold chain; a frost destroys a harvest.
- **The day of the week**: fish harvesters order more on weekends; Blue Tide orders big the
  Tuesday.

**Challenges.** Anticipate volumes, prevent customers from breaking up before they discover it, propose
the right seasonal products, adjust purchases, reserve capacity.

**In the ERP.**

- Three years of order history: the seasons are visible (`GET /api/orders?date=`, `/api/clients/{id}/usual`).
- `Product.active` (out of season = inactive), `Product.tags` (`saison`, `fetes`).
- `PriceRule.validFrom` / `validTo` for promotions dated ("Opening of St. James: -5 % in
  October").
- Situation of the day: `context/01-entreprise.md` ("Situation at 24/11") and supplier events
  `shortage` open.
- Absent: sales forecast, weather, holiday calendar. Everything is to be built if you need it.

---

## Quick map : trade → ERP

| Business concept | Entity, field | Main road | Agent Tool | Page |
|---|---|---|---|---|
| Recognize a customer, a product | — | `GET /api/search?q=` | `search` | ⌘K |
| Customer profile, the usual | `Client`, `Client.notes`, usual basket | `GET /api/clients/{id}`, `/usual` | `get_client` | **Clients** |
| What we know about a customer, supplier, product | `ContextEntry` (`entityType` + `entityId`, `kind`) | `GET /api/context/for` | `get_context`, `search_context`, `save_context` | **Context** |
| Ordering | `Order`, `OrderLine` | `POST /api/orders`, `/lines`, `/confirm` | `create_draft_order`, `add_order_line`, `confirm_order`, `get_order` | **Orders** |
| Edit, cancel an order | `Order.status` | `PATCH /api/orders/{id}`, `PATCH`/`DELETE …/lines/{lineId}`, `/cancel` | to be written | **Orders** |
| Stock, shelf life | `Lot`, `StockLevel`, `StockMovement` | `GET /api/stock`, `/api/products/{id}` | `get_product_stock` | **Stocks** |
| Replacement | `Product.category` | `GET /api/products/{id}/alternatives` | `find_alternatives` | **Products** |
| Price for one customer | `ClientPrice`, `PriceRule`, `Product.price` | `GET /api/prices/resolve` | `get_price` | **Price** |
| Procurement | `PurchaseOrder`, `SupplierPrice`, `Supplier` | `/api/purchase-orders` | to be written | **Achats**, **Suppliers** |
| Preparation, weighing | `OrderLine.preparedQty` | `POST /api/orders/{id}/prepare` | to be written | order detail |
| Turns, delivery time | `Route`, `RouteRun`, `RouteStop.eta` | `GET /api/route-runs?date=` | to be written | **Functions** |
| Invoices, delays | `Invoice` (`overdue` calculated) | `GET /api/invoices` | to write (`get_client` gives totals) | **Factures** |
| Payments | `Payment.allocations` | `GET/POST /api/payments` | to be written | **Payments** |
| Stock, risk | age balance, `risk` | `GET /api/receivables` | to be written | **Current** |
| Claims, history | `ClientEvent`, `SupplierEvent` | `/api/clients/{id}/events`, `/api/suppliers/{id}/events` | `get_client_history`, `log_client_event`, `get_supplier_history`, `log_supplier_event` | **History** |
| Customer groups, products, suppliers | `tags`, `TagDef` | `/api/tags` | — | **Groups** |
| What the agent did | `ActivityEvent` (`actor` : `user`, `ai_chat`, `voice_agent`, `system`) | `GET /api/events`, `/api/events/stream` | automatic (`x-actor`) | **Activity** |
| Date of the day | `Meta.today` | `GET /api/meta` | in the prompt | — |

**Business memory.** Two sources, not to be confused:

- `DATA_DIR/context/*.md` files (presentation, standard day, product glossary, customer playbook, prices and
  credit, deliveries and areas) are put **entiers** in the rapid system and read at each turn
  (`apps/ai/app/agent/prompts.py`). They can be modified live.
- The context table (`ContextEntry`) contains short sheets attached to an entity: `entityType`
  (`company` | `client` | `supplier` | `product` | `category`) + `entityId` (`cli_…`, `sup_…`, `prd_…`, or id
  of a category of `GET /api/categories`). `kind` : `policy` ( rule), `procedure`, `preference`, `fact`, `relationship`,
  `pricing`, `logistics`, `risk`. `source` : `seed`, `user`, `ai_chat`, `voice_agent`. `GET /api/context/for`
  returns the records of the entity ** and ** linked records (the radius of a product, the business rules that
  quote his id).

**What the kit does not model** (to be built if your problem needs it): carriers and booking
trucks, tasks and reminders ("recall the leader when the turbot arrives"), estimates, holdings as documents,
merchandise returns, tenders, sales forecasts, temperatures, supplier lot number, link
lot → customers delivered, time limit of order applied by the backend, actual blocking of orders of a customer
Locked.

---

## Where the voice changes the gift

The phone is the first channel in the trade. Here, actor by actor, the calls that really happen every
day. It is a description of the terrain, not a list of topics: it is up to you to choose the problem that you
Interesting.

### The customer who calls the wholesaler

- **The night order.** 3 h 40, Marie du Comptoir calls for a group this noon. She asks for the price of the back
  find it expensive, accept half cod, half hake on advice, add mussels and
  His course is approaching the ceiling: you must tell him without vexing her.
- **"As usual".** The customer does not detail. You need to know his usual basket, offer it to him,
  and note what changes this week.
- **The breakup.** The leader of The Table d'Aurélien wants wild turbot; there has not been one since the storm.
  It is necessary to say right away, to propose what is acceptable to him (Saint-Pierre, bar of
  line), and promise to remind him when the turbot arrives.
- **The order is too late.** The Little Mareyeur calls at 5 h 45 while his tour is gone at 5 h 30.
  We need to make this clear and propose the next day.
- **The modification.** The manager of Brasserie Montparnasse 1925 mounts its oysters from 33 to 45 dozen, adds
  of cakes, hesitant, change of mind. Possible or not depending on the condition of the order, and he has a weight dispute
  In progress.
- **"Where's the truck?"** 6 h 20, the mazarin sculpin has to mount its oyster bench. It takes time
  estimated from his stop, the name of the driver, the content of the order, and he takes advantage of it to add two box
  lemons.
- **The claim.** "The lobsters have arrived dead." Listen, note precisely, promise nothing,
  Reassuring, uplifting.
- **The customer blocked.** The Fisherie Daguerre wants to order while his account is suspended.
  courteous, explain, confirm nothing, transmit.
- **The prospect.** A new restaurant asks for the prices and the delivery days.
  questions (volumes, days, key products, current supplier), give prices list, propose a reminder of the
  commercial.
- **Extra.** The head of the hotel orders an extra which the economist must validate.
- **The simple question.** "Do you have Saint James? How long? Until when can I order for
  Tomorrow?"

### The wholesaler who calls his customers

- **Annunciate a breakup** before the customer discovers it on delivery, with an alternative and its price.
- **Propose an arrival or a lot to sell**: "I have very beautiful lobsters this morning", "I still have 15 kilos
  I will make them to you to ..." (the price is the commercial one who decides).
- **Relaunch an unpaid **: quote invoices, get a payment date, write it down.
- **Wake up a silent customer**: he ordered three times a week, nothing since ten days.
- **Prepare parties**: collect pre-orders from caterers and breweries.

### The wholesaler and suppliers

- **Compare and negotiate**: call two or three marketers, get a price, negotiate by volume.
- **Book a rare lot** or request a ** supplement** after incomplete delivery.
- **Reclaim**: off-calibre lot, incomplete delivery, delay.
- **Be called **: the supplier announces a storm, an increase, a delay; or claims a payment.

### The wholesaler and transport

- **Book an additional ** truck for a loaded Saturday: volume, temperature, hour, dock, price
 .
- **The driver calling**: absent customer, blocked access, refused goods, delay on tour.

### Internal

- **A colleague asks the stock**: "What is left for us in Santiago?"
  available, lots that will soon end and the arrival of tomorrow.
- **The commercial on Route** dictates a note after a visit, or asks for a customer's stock before entering.
- **The manager** asks about the status of unpaid payments, day breaks, night orders.
- **The preparer** reports a weighing deviation or a missing product during preparation.

These situations are all test scenarios: write yours from your company's customer and supplier records (`data/context/`).
---

## Why it's hard for an agent

Everything is played at the same time, at night, on the phone, with people in a hurry who talk fast, with noise, with
Each answer must be just one kilo and one cent. The agent must have the memory of the
best salesman (who is this customer, what he takes, what irritates him, what happened last week),
the strictness of an accountant (in outstanding amounts, ceiling, deadlines) and the prudence of a quality manager (no
substitution without agreement, no promise impossible), all at the speed of a normal conversation.

Which makes an agent sound like a pro:

- he recognizes the client and calls him by his first name;
- he speaks in units of the trade ("6 kilos of sole 500-600", "30 dozen of no. 3") ;
- he proposes the usual instead of asking ten questions;
- He announces a break with a reason and an alternative;
- it knows the actual day and time of delivery;
- it rereads the command before hanging up;
- He promises only what the company can hold.

---

## Glossary

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
