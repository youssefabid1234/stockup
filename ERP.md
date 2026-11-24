# ERP.md — the guide to the ERP kit

This file explains the ERP of the kit: what it covers, how it works, how to use it (screen and API).
Everything written here is checked in the code. In case of doubt, the code is authentic:
`apps/backend/app/services/` (business rules), `apps/backend/app/schemas/domain.py` (data model).

The other docs, not to be confused:

| Doc | For what? |
|---|---|
| [BRIEF.md](BRIEF.md) | challenge, deliverables, jury |
| [METIER.md](METIER.md) | the trade of food wholesaler and his vocabulary |
| [SETUP.md](SETUP.md) | step by step installation |
| [README.md](README.md) | architecture, configuration, commands |
| [AGENTS.md](AGENTS.md) | rules for code agents |
| [apps/ai/README.md](apps/ai/README.md) | agent loop, tools, suppliers LLM/STT/TTS, WebSocket voice protocol |

---

## 1. What the ERP covers

A wholesaler (marée, fruit and vegetables, cream shop, grocery store) sells to restaurants, fish shops, canteens...
and buys from suppliers. The ERP tracks the entire flow, from order to payment.

```
VENTES
 client ──▶ commande (draft) ──confirm──▶ réservation de stock + arrêt sur une tournée
                                   │
                                   ▼
                       préparation (prepared, poids réels)
                                   │
                                   ▼
                  livraison (delivered) : sortie des lots en FEFO
                                   │
                                   ▼
            facture (FAC-…) ──▶ paiement ──▶ affectation aux factures ──▶ encours / balance âgée

ACHATS
 fournisseur ──▶ commande d'achat (draft) ──send──▶ sent ──receive──▶ réception ──▶ lots (DLC = date de réception + durée de vie)

AUTOUR
 prix (négociés, règles, catalogue) · historique client / fournisseur · groupes (tags) · table de contexte
 journal d'activité en direct (qui a fait quoi : équipe, assistant IA, agent vocal)
```

Three bricks:

| carton | Where | Port |
|---|---|---|
| API ERP (FastaPI + SQLite) | `apps/backend` | 4000 (`/docs`, `/openapi.json`) |
| Service AI (agent, cat, voice) | `apps/ai` | 4100 |
| Web (React) | `apps/web` | 5173 (proxy `/api` → 4000, `/ai` → 4100) |

Global web shortcuts: `⌘K` search and "Go to", `⌘J` assistant AI, `⌥ Espace` (maintenance) voice command,
`⌘B` or `⌘\` sidebar.

---

## 2. Pages (menu order)

Each page reads the API ERP. The filters are in the URL (you can share a filtered link).

### Home — `/`
- **Montre** : CA of the day, CA of the month, orders of the day, pre-orders to process, to deliver today, unpaid in
  delay; CA of the last 30 days; top 10 customers on 30 j; low stock; shelf life close; live activity.
- **Actions**: "New command"; each line leads to its object.
- **API** : `GET /api/dashboard`, `GET /api/events/stream`.

### Orders — `/orders`
- **Montre**: sales orders (n°, customer, delivery date, lines, total, status), total standing.
- **Filters**: status tabs (All, Pre-orders, Confirmed, Prepared, Delivered, Invoiced, Cancelled) with
  counters; search no. / customer; delivery date (Hier, Today, Tomorrow, or a date); channel;
  `?clientId=` filter per customer.
- **Actions**: "New order" → customer choice → empty draft → order page.
- **API** : `GET /api/orders`, `POST /api/orders`.

### Order — `/orders/:id`
- **Montre**: banner (client, date, total excl. VAT, total incl. VAT, creation), alerts, editable lines, note; column of
  Right: customer, usual basket, bill, tour.
- **Lines**: quantity, price, changeable note online; stock available by line; price icon i =
  where this price comes from (Negotiated / Rule "..." / Catalogue); "Alternatives" button = replacement products.
  After preparation, the column "prepared" receives the actual weights.
- **Actions**: Confirm → Prepare → Deliver → Invoice; Cancel (two clicks); "View invoice".
- **API** : `GET /api/orders/{id}`, `PATCH /api/orders/{id}`, `POST|PATCH|DELETE /api/orders/{id}/lines…`,
  `POST /api/orders/{id}/confirm|prepare|deliver|invoice|cancel`, `GET /api/products/{id}/alternatives`,
  `GET /api/prices/resolve`, `GET /api/clients/{id}/usual`.

### Customers — `/clients`
- **Montre** : name, type, groups, zone, commercial, outstanding, late, last order, status.
- **Filtres** : search (name, code, city, contact), type, zone, group.
- **Actions**: "New customer" (side panel; created in `prospect` status).
- **API** : `GET /api/clients`, `POST /api/clients`.

### Customer — `/clients/:id`
- **Onglets**: Overview · Background · Background.
- **Overview** : KPI (current, overdue, credit ceiling, CA 30 j, last order), recent orders,
  Open bills, usual basket, negotiated prices, information, contacts, notes CRM, recent history, groups.
- **Actions** : Block / Unlock, add a note, new event, new context sheet.
- **API** : `GET /api/clients/{id}`, `PATCH /api/clients/{id}`, `POST /api/clients/{id}/notes`,
  `GET|POST /api/clients/{id}/events`, `GET /api/context/for?entityType=client&id=…`.

### Price — `/prices`
Four tabs:
- **Matrice**: products × customer groups (or up to 8 customers selected). Each box = price solved; one click
  opens the details and creates a negotiated rule or price. `GET /api/prices/grid`.
- **Rules**: Price rules list, creation / editing in a panel with preview, deletion.
  `GET|POST|PATCH|DELETE /api/price-rules`.
- **Prices negotiated**: all customer prices × product, online edition, addition, deletion.
  `PUT|DELETE /api/clients/{id}/prices/{productId}`.
- **Simulator** : customer + product + quantity (+ date) → price selected, all the candidates and why each one was
  applied or not. `GET /api/prices/resolve`.

### History — `/history`
- **Montre**: all the company's customer and supplier events, most recent first.
- **Filters**: Clients/Suppliers tabs; Family (Claims & Quality, Returns & Assets, Payments,
  Commercial, Relationship, Notes) ; status ; from / to ; search full text.
- **Actions**: "mark Solved" online; link to customer / supplier.
- **API** : `GET /api/client-events`, `GET /api/supplier-events`, `PATCH /api/client-events/{id}`,
  `PATCH /api/supplier-events/{id}`.

### Products — `/products` and `/products/:id`
- **List**: tabs by category; search name / SKU / name (alias); group. Price, cost, margin, stock,
  shelf life. `GET /api/products?q=…&category=…&tag=…` (the text filter is called `q`, not `search`).
- **Fiche**: KPI, batches in FEFO, comparative supplier prices, recent movements, sales 30 j, context;
  "Adjust stock" (sign). `GET /api/products/{id}`, `POST /api/stock/adjust`, `PATCH /api/products/{id}`.

### Stocks — `/stock`
- **Montre**: each product: physical, reserved, available, incoming, next shelf life, condition.
- **Onglets**: All · Out (available ≤ 0) · Low stock (dashboard rule, see §3.3) · Near shelf life
  (Next shelf life in 2 days or less).
- **Actions**: Click on a line → panel with batches and fit.
- **API** : `GET /api/stock`, `GET /api/stock/movements`, `POST /api/stock/adjust`.

### Purchases — `/purchase-orders` and `/purchase-orders/:id`
- **List**: All tabs, Drafts, Sent, Partial, Received, Cancelled; Search; Date expected;
  supplier (`?supplierId=`). "New Purchase Order" → choice of supplier → blank draft.
- **Fiche**: editable lines (in draft), deviation from the supplier's usual price, alerts, expected date,
  note, lots received; actions Send, Receive (line-by-line reception mode, partial receipt possible),
  Cancel.
- **API**: `GET|POST /api/purchase-orders`, `GET|PATCH /api/purchase-orders/{id}`, lines,
  `POST /api/purchase-orders/{id}/send|receive|cancel`, `GET /api/suppliers/{id}/usual`.

### Suppliers — `/suppliers` and `/suppliers/:id`
- **List**: name, city, categories, delay, conditions, minimum order. Filters: search, category, group.
- **Fiche** ( tabs Overview · Background · Background) : information, contacts, supplier price, orders
  "Order" creates a purchase draft for this supplier.
- **API** : `GET /api/suppliers`, `GET|PATCH /api/suppliers/{id}`, `GET|POST /api/suppliers/{id}/events`.

### Outstanding — `/receivables`
- **Montre**: aged balance per customer on business day; KPI (current, due, DSO, customers late); stacked bar
  per slice (click = filter).
- **Filtres**: search, group, commercial, area, "Dead only".
- **Customer panel** (click on a line): open invoices, payments, open disputes, latest re-launches;
  Actions Save a payment, Save Recovery (create an event `late_payment`), Block / Unlock,
  Customer profile.
- **API** : `GET /api/receivables`, `POST /api/payments`, `POST /api/clients/{id}/events`, `PATCH /api/clients/{id}`.

### Invoices — `/invoices` and `/invoices/:id`
- **List**: tabs To be paid, Late, Paid, All ; search no. / customer ; total.
- **Fiche**: the invoice in document (lines with VAT, total), status, maturity, related orders, payments
  affected, "Save a payment".
- **API** : `GET /api/invoices`, `GET /api/invoices/{id}`, `POST /api/payments`.

### Payments — `/payments`
- **Montre**: payments received. Filters: search (client, reference, invoice), method of payment.
- **Actions**: Record a payment, with manual or automatic assignment (older invoices first).
- **API** : `GET /api/payments`, `POST /api/payments`.

### Turns — `/routes`
- **Onglets** : Day shots · Definitions.
- **Tours of the day**: date (Today, Tomorrow, Other); one map per tour with stops, ETA, weight;
  Up / Down arrows to reorder; "Plan".
- **API** : `GET /api/routes`, `GET /api/route-runs?date=`, `POST /api/route-runs/plan`,
  `PATCH /api/route-runs/{id}/stops`.

### Assistant — `⌘J` (not one page)
Cat panel on the right. See §6.

### Votes — `/voice`
Two modes (header, `?mode=command`): Call and Command. See §6.

### Background — `/context`
- **Montre**: all context sheets. Tabs: All, Company, Customers, Suppliers, Products, Rayons.
- **Filtres**: search, gender (`kind`), source, entity.
- **Actions**: click = editing panel (autoguard) ; "New file". Sheets written by the AI in purple.
- **API** : `GET|POST /api/context`, `GET|PATCH|DELETE /api/context/{id}`.

### Activity — `/activity`
- **Montre**: the journal of all scripts, live. Tabs All · AI & voice · Team ; filter by object.
- **API** : `GET /api/events`, `GET /api/events/stream`.

### Groups — `/groups`
- **Montre**: three columns (customers, products, suppliers); number of members per group.
- **Actions** : create a group ; click = edit, add / remove members.
- **API** : `GET|POST /api/tags`, `PATCH|DELETE /api/tags/{scope}/{id}`, `PATCH /api/clients|products|suppliers/{id}`
  with `{tags}`.

---

## 3. Life cycles and business rules

Errors always have the form `{"error": {"code", "message"}}`. A prohibited transition returns
`409 invalid_transition`. Alerts (`warnings`) never block: they are recalculated at each reading.

### 3.1 Sales Orders

```
draft ──confirm──▶ confirmed ──prepare──▶ prepared ──deliver──▶ delivered ──invoice──▶ invoiced
  │                    │   └────────────deliver────────────────▲
  └──────cancel────────┴──────────cancel──────────┘ (depuis draft, confirmed, prepared)
```

| Action | Since | Effect |
|---|---|---|
| `POST /api/orders` | — | Creates in `draft`. Price of each line solved (§3.4). Default `deliveryDate` = next day of delivery of the customer strictly after today (tomorrow if it does not have one). Default `source` = `voice_agent` if the actor is `voice_agent`, otherwise `manual`. |
| `PATCH /api/orders/{id}` | `draft`, `confirmed` | Delivery date, note. A confirmed order that changes date change tour. |
| Add/Remove Line | `draft`, `confirmed` | Remove the last line from a confirmed command: `409 empty_order` (cancel instead). |
| Edit a line | `draft`, `confirmed`; in `prepared` only `preparedQty` and `note` | Change `productId` recalculates the price. |
| `confirm` | `draft` | Requires ≥ 1 line (`409 empty_order`). Reserves the stock (calculated, see §3.3). Place the order on the tour of the customer area on the delivery date. |
| `prepare` | `confirmed` | Entered the actual weights (`preparedQty`); an unlisted line = prepared as ordered. The total follows the actual weights. |
| `deliver` | `confirmed`, `prepared` | Removes the stock of the lots in FEFO (movements `sale`). If the physical stock is missing, the delivery passes and the newspaper reports it. The stopover passes `delivered`. |
| `invoice` | `delivered` | Create an invoice (`issued`) and place the order in `invoiced`. |
| `cancel` | `draft`, `confirmed`, `prepared` | The reservation disappears; the stop leaves its tour. |

One line: `productId`, `qty`, `unitPrice` (€ excl. VAT), `preparedQty`, `note` ("fresh property"), `substituteFor` (product
The quantity that counts (stock, total, invoice) = `preparedQty` if known, otherwise `qty`.

**Order Alerts** (only in `draft`, `confirmed`, `prepared`):

| Code | Trigger |
|---|---|
| `client_blocked` | the customer has the status `blocked` |
| `credit_limit` | `creditLimit` > 0 and current incl. VAT + incl. VAT of this order > `creditLimit` |
| `no_route` | no tour of the customer area runs this weekday |
| `insufficient_stock` | available (excluding reservation of this order) < requested quantity of product |
| `expiring_soon` | the first lot FEFO of the product expires no later than the day after delivery |
| `price_below_cost` | price of line < reference cost of product |

### 3.2 Purchase orders and receptions

```
draft ──send──▶ sent ──receive──▶ partially_received ──receive──▶ received
draft | sent | partially_received ──cancel──▶ cancelled   (les lots déjà reçus restent en stock)
```

- Creation in `draft`; optional lines. Default price = supplier price (`SupplierPrice`), otherwise cost
  default `expectedDate` = today + `leadTimeDays` from the supplier.
- Editable lines in `draft` only; `expectedDate` and `note` in `draft` or `sent`.
- `send` requires ≥ 1 line (`409 empty_order`).
- `receive` (since `sent` or `partially_received`): `receivedQty` = received quantity **now**, already added
  received. Without bodies: everything else to receive. Each received line creates **a lot**: `receivedAt` = today,
  `expiresAt` = today + `shelfLifeDays` of the product, plus a `receipt` movement. Status `received` if all
  lines are complete, otherwise `partially_received`. Not received: `400 nothing_received`.

**Buy Alerts** (only in `draft`, `sent`):

| Code | Trigger |
|---|---|
| `below_min_order` | total supplier excl. VAT < `minOrderAmount` |
| `not_in_supplier_catalog` | the product has no price at that supplier |
| `price_above_usual` | price of the line > 110 % of the supplier's usual price |

### 3.3 Stock

The stock is made of **lots** (`Lot`). A lot = a product entry, with a shelf life (`expiresAt`).

| Size | Calculation |
|---|---|
| `onHand` (physical) | `qtyRemaining` of lots |
| `reserved` (reserved) | Quantity of `confirmed` and `prepared` command lines |
| `available` (available) | `onHand` − `reserved` |
| `incoming` (entry) | (`qty` - `receivedQty`) for purchases `sent` and `partially_received` |
| `nextExpiry` | shelf life of the first batch still in stock |

- The reservation is not stored: it results from the status of the orders. Cancel or deliver it free.
- **FEFO** (first expired, first released): the lot that expires the earlier (then the oldest received) is first released.
- **Adjustment** (`POST /api/stock/adjust`, `reason` = `adjustment` or `waste`): `qty` > 0 creates a new batch
  (shelf life = today + life) ; `qty` < 0 comes out in FEFO. `waste` (loss) always comes out, whatever the
  Sign sent.
- Movements (`StockMovement.reason`): `receipt`, `sale`, `adjustment`, `waste`, `return`.
- **Stock low** (dashboard): available ≤ 0, or available < 2 days average sales (average on 14 days).
- **shelf life near** (Dashboard): lots in stock that expire in 2 days or less (already expired included).
- **Alternatives** (`GET /api/products/{id}/alternatives`): same category, active, available > 0, most price
  close first, maximum 10.

### 3.4 Prize: who wins

Order of Resolution (`apps/backend/app/services/pricing.py`):

1. **Price negotiated** (`ClientPrice`, customer × product): always wins.
2. **Price rule** (`PriceRule`): the most specific applicable wins. Specificity, from the strongest to the most
   Low:
   customer + product > customer + group/category > customer + all products > customer group + product >
   Customer group + group/category > customer group + all products > all customers + product >
   all customers + group/category > all customers + all products.
   Equal: `priority` the highest, then the most recent.
   A rule applies if `active`, the date is in `validFrom`...`validTo`, and the quantity is ≥ `minQty`.
3. **Catalogue price** (`Product.price`).

Methods of a rule: `fixed` (fixed price), `discount_pct` (% discount on the catalogue price, between 0 and 100),
`markup_pct` (% cost margin).

**See why a price has been chosen** : `GET /api/prices/resolve?clientId=…&productId=…&qty=…[&date=…]` returns
`price`, `source` (`client_price`) `rule` (`list`), `ruleId`, `marginPct`, `explanation` (phrase in French) and
`candidates`: Each price possible, `applied`, and `reason` when not retained ("inactive rule",
"from 10 units", "the negotiated price of the prime customer". In the web: the i icon on a command line,
or Price → Simulator.

The price of a line is fixed at its creation. Changing a rule does not change existing commands.

### 3.5 Credit, customers blocked, risk of outstanding

- `Client.status`: `active`, `blocked`, `prospect`. We block by hand (`PATCH /api/clients/{id}` with
  `{"status": "blocked"}`, Block button). A client blocked ** can still order**: the ERP adds the alert
  `client_blocked`, it's up to the agent to decide what to say.
- `creditLimit`: incl. VAT stock allowed. `0` = no control.
- **Outstanding balance** (`outstanding`) = Σ (`totalTtc` − `amountPaid`) Open invoices. **Spent** (`overdue`) = share
  whose deadline has passed.
- **Tranches** of the older balance (days after maturity): `current` (not due), `d1_30`, `d31_60`, `d61_90`, `d90plus`.
- **Risque** (`GET /api/receivables`, field `risk`):

| Level | If at least one condition |
|---|---|
| `high` (High) | customer `blocked`; outstanding > `creditLimit` (if > 0); more than 60 days late; average payment time > 60 j ** and ** something expired |
| `watch` (To be monitored) | outstanding > ceiling 80 %; more than 30 days late; one event `late_payment` **opened**; average payment time > 45 j |
| `ok` | if not |

- `avgDaysToPay`: Invoices paid whose last payment is less than 90 days (date of last payment -
  date of issue).
- **DSO** = outstanding / CA incl. VAT billed on 90 days × 90.
- Only customers with at least one open invoice appear in `/api/receivables`.

### 3.6 Invoices, payments, assignment

- An invoice arises from an order delivered (`POST /api/orders/{id}/invoice`). Lines = prepared quantities, VAT per
  product (`vatRate`, 0,055 Food). `issuedAt` = Today ; `dueDate` = Today +
  Customer's `paymentTermsDays` (0 = cash).
- Storage status: `issued`, `partially_paid`, `paid` (and `draft`, `cancelled`). `overdue` is not **Never stored**:
  it is calculated at reading (open bill including `dueDate` < today).
- `GET /api/invoices?status=open`: pseudo-status = all invoices with a balance.
- **Payment** (`POST /api/payments`): amount incl. VAT, `method` (`transfer`, `card`, `cheque`, `cash`,
  `direct_debit`).
  - Without `allocations`: allocated to ** open invoices the oldest first**; the surplus remains unallocated.
  - With `allocations`: each invoice must be to this customer (`400 wrong_client`), each amount ≤ balance of the
    invoice, the sum ≤ the amount of the payment (`400 over_allocated`).
  - The invoice status is as follows: `paid` if balance ≤ 0, otherwise `partially_paid`.

### 3.7 Turns

- A ** turned** (`Route`) serves a `zone` some days (`days`), with one departure time and capacity.
- A **passage** (`RouteRun`, `run_…`) = one tour on a date. Status `planned` → `in_progress` (one stop delivered) →
  `done` (more standstill).
- Confirm an order the installation on the client's area crossing on its date (created if necessary).
  toured that day, the ERP still takes a tour of the area (and the command carries the alert `no_route`).
- `POST /api/route-runs/plan {date}`: Installs all the `confirmed` / `prepared` commands of the date, adds the
  news sorted by city then name, removes cancelled or displaced stops.
- `PATCH /api/route-runs/{id}/stops {orderIds}`: These commands first, in this order; the others follow.
- ETA one stop = departure time + 12 Min × row. Weight: one `box` ≈ 5 kg, any other unit ≈ 1 kg.

### 3.8 Customer and supplier history

The long term of the relationship: claims, returns, disputes, appeals, visits, negotiations...

- **Customer types** (`ClientEventType`): `onboarding`, `call`, `visit`, `complaint`, `quality_issue`, `delivery_issue`,
  `return`, `credit_note`, `dispute`, `late_payment`, `payment_plan`, `price_negotiation`, `special_request`,
  `menu_change`, `contact_change`, `compliment`, `churn_risk`, `won_back`, `note`.
- **Supplier types** (`SupplierEventType`): `onboarding`, `call`, `visit`, `quality_issue`, `delivery_issue`,
  `shortage`, `return`, `credit_note`, `dispute`, `price_change`, `price_negotiation`, `invoice_issue`, `payment`,
  `contract`, `certification`, `contact_change`, `compliment`, `note`.
- **Status** (`open` | `resolved`) : problem types are created `open` automatically.
  Customer: `complaint`, `quality_issue`, `delivery_issue`, `return`, `dispute`, `late_payment`, `churn_risk`.
  Supplier: `quality_issue`, `delivery_issue`, `shortage`, `return`, `dispute`, `invoice_issue`.
  The others have no status. Switching to `resolved` fills `resolvedAt`; go back to `open` the eraser.
- **Gravity** (`severity`): `low`, `medium`, `high`.
- **Canal** (`channel`) : `phone`, `email`, `whatsapp`, `visit`, `voice_agent`, `sms`, `other`. By default
  `voice_agent` when the actor is the vocal agent. Default author: the name of the actor, otherwise "Team",
  "Assistant AI", "Vocal Agent".
- Optional links: `orderId`, `invoiceId` (must be this customer), `productIds`, `amount` (€), `tags`.
- `at`: default now; one date only = 09:00.
- Customer data sheet (`eventStats`): total, open, claims over 12 months (`complaint`, `quality_issue`,
  `delivery_issue`), back on 12 months.

### 3.9 Groups (tags)

- A group (`TagDef`) has a `id` (slug, unique by `scope`), a `scope` (`client`, `supplier`, `product`), a `label`,
  a colour and description.
- Entities carry group ids in their `tags` field. An undefined tag is refused (`400 unknown_tag`).
- Price rules target a group of customers and/or a group of products.
- Remove a group from all entities; the rules that apply to it no longer apply.

### 3.10 The context table

What agents need to know, in short and editable sheets.

- A plug (`ContextEntry`, `ctx_…`) is attached by `entityType` + `entityId`:
  - `company`: no `entityId`;
  - `client`, `supplier`, `product`: an existing id (`cli_…`, `sup_…`, `prd_…`);
  - `category`: the id of a product category of your business (business-specific list:
    `GET /api/categories` → `[{id, label}]`).
- **Genres** (`kind`): `policy` (rule), `procedure` (how to do/say), `preference` (what they like),
  `fact` (context), `relationship` (persons), `pricing` (agreements), `logistics` (delivery, storage),
  `risk` (irritants, credit, risk of losing the customer).
- **Source** (`source`): `seed` (data package), `user` (web), `ai_chat`, `voice_agent`. Fixed by the header
  `x-actor` writing.
- Search: `GET /api/context?q=…` full text insensitive to accents, classified by relevance (Title > tags and entity > body).
  Filters `entityType`, `entityId`, `kind`, `source`, `tag`; `limit` (default 100).
- **`GET /api/context/for?entityType=client&id=cli_0010`**: everything you need to load before talking about a
  entity. `entries` = its records; `related` = related records (product → its category; supplier → its categories;
  any → entity the `company` or `category` forms whose text quotes its id).
- In addition to the table, the agent reads each turn `DATA_DIR/context/*.md` files (see
  `apps/ai/app/agent/prompts.py`).

---

## 4. Data model

Prefixed Ids, amounts in euros excl. VAT except `*Ttc`, dates `YYYY-MM-DD`, full ISO timers. JSON in camelCase.
Source: `apps/backend/app/schemas/domain.py`.

| Entity | Id | Key fields |
|---|---|---|
| `Client` | `cli_0010` (code `C0010`) | `name`, `type`, `contacts`, `zone`, `deliveryDays`, `paymentTermsDays`, `creditLimit`, `status`, `salesRep`, `preferences`, `notes`, `tags` |
| `Product` | `prd_0015` | `sku`, `name`, `aliases` (what people say: "wolf"), `category`, `unit` (`kg`, `piece`, `box`, `dozen`, `liter`), `price`, `cost`, `vatRate`, `shelfLifeDays`, `mainSupplierId`, `active`, `tags` |
| `Supplier` | `sup_0001` | `name`, `categories`, `leadTimeDays`, `paymentTermsDays`, `minOrderAmount`, `notes`, `tags` |
| `ClientPrice` | customer key × product | `clientId`, `productId`, `price` |
| `SupplierPrice` | key supplier × product | `supplierId`, `productId`, `price`, `updatedAt` |
| `PriceRule` | `prl_0001` | `name`, `active`, `priority`, `clientScope`, `productScope`, `method`, `minQty`, `validFrom`, `validTo` |
| `Order` | `ord_002063`, n° `CMD-2026-016935` | `clientId`, `status`, `source`, `deliveryDate`, `routeRunId`, `totalHt`, `lines[]`, `invoiceId`, `createdBy` |
| `OrderLine` | `lin_…` | `productId`, `qty`, `unitPrice`, `preparedQty`, `note`, `substituteFor` |
| `PurchaseOrder` | `po_000697`, n° `ACH-2026-003650` | `supplierId`, `status`, `expectedDate`, `totalHt`, `lines[]` (`pol_…` : `qty`, `unitPrice`, `receivedQty`) |
| `Lot` | `lot_003273` | `productId`, `supplierId`, `purchaseOrderId`, `qtyReceived`, `qtyRemaining`, `receivedAt`, `expiresAt` |
| `StockMovement` | `mov_015840` | `productId`, `lotId`, `qty` (+ input, - output), `reason`, `refType`, `refId`, `note` |
| `Invoice` | `inv_001630`, n° `FAC-2026-011440` | `clientId`, `orderIds`, `status`, `issuedAt`, `dueDate`, `lines`, `totalHt`, `totalVat`, `totalTtc`, `amountPaid` |
| `Payment` | `pay_000545` | `clientId`, `amount` (incl. VAT), `method`, `receivedAt`, `reference`, `allocations[]` (`invoiceId`, `amount`) |
| `Route` | `rte_0001` | `name`, `zone`, `driver`, `vehicle`, `capacityKg`, `days`, `departureTime` |
| `RouteRun` | `run_000075` | `routeId`, `date`, `status`, `stops[]` (`orderId`, `clientId`, `seq`, `eta`, `status`) |
| `ClientEvent` | `cev_002017` | `clientId`, `at`, `type`, `title`, `description`, `channel`, `author`, `severity`, `status`, `resolution`, `orderId`, `invoiceId`, `productIds`, `amount` |
| `SupplierEvent` | `sev_000500` | Idem, with `supplierId` and `purchaseOrderId` |
| `TagDef` | slug (`gastro`, `premium`) | `scope`, `label`, `color`, `description` |
| `ContextEntry` | `ctx_0001` | `entityType`, `entityId`, `kind`, `title`, `body` (markdown court), `tags`, `source` |
| `ActivityEvent` | `evt_0000029` | `at`, `actor`, `actorName`, `type`, `entity`, `entityId`, `summary` |

Document numbers: `CMD-<année>-<6 chiffres>` (sale), `ACH-…` (purchase), `FAC-…` (invoice).
new lines (`lin_…`, `pol_…`) are random; all other ids continue the sequence.

---

## 5. Business Clock and Business Flow

### The clock : `meta.today`
- The data is anchored to a fixed date: `GET /api/meta` → `{company, today, currency, generatedAt, trade, region}`
  (`trade` and `region`: the trade and area, displayed in the sidebar).
- "Today", "Tomorrow", "Delayed", "Due", "30 Last days" are calculated **Always** on
  `meta.today`, never on the real date.
- The new recordings have the date `meta.today` and the actual time of the wall clock.
- The agent receives this date in its prompt system ("Today: Tuesday 24 November 2026").

### The flow of activity
- Each write adds a `ActivityEvent` (`type` like `order.confirmed`, `payment.recorded`,
  `client_event.created`, `context.created`... with a `summary` sentence in French.
- ** Who writes** : header `x-actor` = `user` | `ai_chat` | `voice_agent` ( value unknown or absent = `user`), plus
  `x-actor-name` optional (name displayed, encoded URI). The web sends `user` / "Me". Agent tools send
  `ai_chat` (chat) or `voice_agent` (voice, voice command).
- **Direct**: `GET /api/events/stream` (Server-Sent Events) sends `ready` once, then an event `activity`
  by validated writing, and `ping` all 15 s. `GET /api/events?limit=50` = history, most recent first.
- **Violet**: in the web, everything from `ai_chat` or `voice_agent` is stained purple (Activity, Home,
  right column of the Voice page, context sheets written by the AI, tool calls in the wizard).
- `make reset` clears the paper.

---

## 6. The AI side of the ERP

### The three surfaces

| Surface | How | What she does | Road AI |
|---|---|---|---|
| **Assistant** | `⌘J`, right panel on all pages | Text chat with the agent (mode `chat`, light markdown). Tool calls are displayed in purple lines with link to the object. | `POST /ai/chat` (SSE) |
| **Voice · Call** | page `/voice` | Phone call simulation: hold Space (or the big button) to speak as a client, release; the agent responds in text and audio (mode `voice`: 1–2 sentences, no ids, rounded numbers). Two-track chronology, latency per turn, live agent writings to the right. | `WS /ai/voice` |
| **Voice · Command** | page `/voice?mode=command`, or `⌥ Espace` held on any page (HUD), or "Voice" button on the header | A commercial driver controls the ERP at the same time, one sentence at a time, without history (mode `command`: acts immediately, answers in one sentence). If the sentence asks for "see" ("watch", "open", "show" ...), the web navigates to the object page. A short click on the button opens the HUD to type the command. | `POST /ai/command[?speak=1]` (SSE) |

The prompt system (`apps/ai/app/agent/prompts.py`) = basic rules + mode rules + company and date +
contact name + all `DATA_DIR/context/*.md` files. Detailed protocols: [apps/ai/README.md](apps/ai/README.md).

### The Agent's Tools

16 tools, in `apps/ai/app/tools/`. They call the API ERP with `x-actor`; they do not contain any business rules.
Updated list: `GET http://localhost:4100/tools`.

| Tool | What he does | Road ERP |
|---|---|---|
| `search` | Find customer, product, supplier or order from what is said (float, without accents, alias, unknown parasitic words) | `GET /api/search` |
| `get_client` | Customer profile: status, conditions, stock, preferences, notes, usual basket, open issues, latest 5 events | `GET /api/clients/{id}` |
| `get_product_stock` | Available, incoming, next shelf life, catalogue price | `GET /api/products/{id}` |
| `find_alternatives` | 5 replacement products in stock | `GET /api/products/{id}/alternatives` |
| `get_price` | Price for one customer and one quantity, with explanation; reports a better price per volume | `GET /api/prices/resolve` |
| `search_context` | Search in context sheets (rules, procedures, habits...) | `GET /api/context` |
| `get_context` | The whole context of a customer, supplier, product or radius | `GET /api/context/for` |
| `save_context` | Memorizes a lasting fact (preference, contact, constraint) | `POST /api/context` |
| `get_client_history` | Customer history, filterable by type | `GET /api/clients/{id}/events` |
| `log_client_event` | Record a complaint, a call, a request... | `POST /api/clients/{id}/events` |
| `get_supplier_history` | Supplier History | `GET /api/suppliers/{id}/events` |
| `log_supplier_event` | Record a supplier event | `POST /api/suppliers/{id}/events` |
| `create_draft_order` | Create a pre-order (`draft`) with or without lines | `POST /api/orders` |
| `add_order_line` | Add a line to a command | `POST /api/orders/{id}/lines` |
| `confirm_order` | Confirms (after explicit agreement on the summary); returns alerts | `POST /api/orders/{id}/confirm` |
| `get_order` | Detail of an order: lines, status, total, alerts | `GET /api/orders/{id}` |

What Agent ** can't do today ** (no tool): modify or remove a line, cancel, prepare,
Deliver, bill, record a payment, manage purchases, prices, stock, tours. Roads exist
in the API: one more tool is enough (see [apps/ai/README.md, "Add a tool"](apps/ai/README.md#add-a-tool-about-10-lines)).

---

## 7. Step by step

In the examples of API, `B=http://localhost:4000/api`. Add `-H 'x-actor: voice_agent'` to see the writing in
purple in the web.

### 7.1 Take an order from end to end
**Web**
1. Orders → "New order" → type the client → Enter. A draft opens.
2. Add the lines (product search, including aliases) or pick up in the usual shopping cart on the right.
3. Read the alerts, then Confirm. Stock is booked, order is on a tour.
4. Prepare (enter actual weights if needed) → Deliver → Invoice.
5. On the invoice: "Save a payment".

**API**
```bash
curl -s -X POST $B/orders -H 'content-type: application/json' \
  -d '{"clientId":"cli_0010","lines":[{"productId":"prd_0015","qty":4,"note":"bien frais"}]}'   # → draft, ord_…
curl -s -X POST $B/orders/ord_…/confirm
curl -s -X POST $B/orders/ord_…/prepare -H 'content-type: application/json' \
  -d '{"lines":[{"lineId":"lin_…","preparedQty":4.3}]}'
curl -s -X POST $B/orders/ord_…/deliver
curl -s -X POST $B/orders/ord_…/invoice                                                       # → inv_…, FAC-…
curl -s -X POST $B/payments -H 'content-type: application/json' \
  -d '{"clientId":"cli_0010","amount":86.19,"method":"transfer"}'
```

### 7.2 Manage a rupture with a replacement product
1. Check the client's notes and context first (some refuse any substitution):
   `GET $B/context/for?entityType=client&id=cli_…`.
2. On order, a broken line carries `insufficient_stock`. "Alternatives" button of line →
   "Replace". By API: `GET $B/products/prd_…/alternatives`, then
   `PATCH $B/orders/ord_…/lines/lin_… {"productId":"prd_NEW","substituteFor":"prd_OLD"}`. Price recalculated
   for the new product.
3. Possible in `draft` or `confirmed`.

### 7.3 Receive a purchase order in part
1. Purchases → Order (`sent` or `partially_received`) → Receive → Enter the quantity received by line →
   validate.
2. API : `POST $B/purchase-orders/po_…/receive {"lines":[{"lineId":"pol_…","receivedQty":6}]}`.
3. Result: one lot per received line (shelf life = today + service life), status `partially_received` as long as it
   A second reception adds to the already received. The remainder to be received account in `incoming`.

### 7.4 Record a Claim
1. Customer details → History → "New event" → type Claim, title, description, gravity, order or
   related products.
2. API : `POST $B/clients/cli_…/events {"type":"complaint","title":"Raie pas fraîche","severity":"medium","orderId":"ord_…"}`.
   It is created `open`.
3. To close: "mark Solved" (Historical) or `PATCH $B/client-events/cev_… {"status":"resolved","resolution":"Avoir de 20 €"}`.

### 7.5 Understand why a client is blocked (or at risk)
1. `GET $B/clients/cli_…` : `status`, `creditLimit`, `outstanding`, `overdue`, `notes`, `recentEvents`, `openIssues`.
2. Current → filter on customer → panel: slices, open invoices, latest re-launchs, disputes, risk.
   API: `GET $B/receivables?q=<nom>` (fields `risk`, `maxDaysOverdue`, `creditUsedPct`, `avgDaysToPay`,
   `openDisputes`, `lastReminderAt`).
3. Customer History, Filter Payments: `GET $B/clients/cli_…/events?type=late_payment,payment_plan,dispute`.
4. The `blocked` status is placed by hand: the event `client.updated` ("Customer ... blocked") in the newspaper says
   When and by whom.

### 7.6 Set a negotiated price
1. Price → Prices negotiated → "New negotiated price"; or Matrix → click on a customer box → "Setting this price".
2. API: `PUT $B/clients/cli_…/prices/prd_… {"price":17.5}` (replaces if it exists). Delete:
   `DELETE $B/clients/cli_…/prices/prd_…`.
3. Check: `GET $B/prices/resolve?clientId=cli_…&productId=prd_…` → `source: "client_price"`. Orders
   already created keep their old prize.

### 7.7 See what the agent knows about a client
1. Customer Sheet → Context tab (clean sheets + linked sheets).
2. API : `GET $B/context/for?entityType=client&id=cli_…` (what the `get_context` tool loads), more
   `GET $B/clients/cli_…` (which `get_client` returns).
3. What he learned during the conversations: `GET $B/context?source=ai_chat,voice_agent`.
4. The context always present in the prompt: `DATA_DIR/context/*.md`.

### 7.8 Reset data to zero
`make reset` (= `POST /api/admin/reset`). Empty the database, reload the `DATA_DIR` data package, empty the log.
All your writings are lost.

### 7.9 Data
Your company's data is in `./data` (`DATA_DIR=./data` in `.env`). If you break them,
`make reset` recharges them. Check: `GET $B/meta` → `company` and `today`.

---

## 8. Aide-memoire of the API

All routes are under `/api`. All entries accept `x-actor` and `x-actor-name`. Complete diagrams and
live test: http://localhost:4000/docs.

**List (all GET routes that return a list).** Pagination, filters and server side sorting:
`limit` (default **100**, max **500**), `offset`, `sort` (triable road field, see `/docs`), `order=asc|desc`.
Answer: a **table** JSON — the page requested, so **truncated to `limit`** — or, with `envelope=1`,
`{items, total, limit, offset, counts?, sums?, …}` where `total` says how many lines match the filters and the
extras (`counts` by status, `sums`...) cover the entire filtered assembly. An agent almost never needs everything:
filter (`clientId`, `status`, `date`, `q`...) and keep `limit` small. Details: [TECH.md · Pagination](TECH.md#pagination).

```bash
curl -s 'localhost:4000/api/orders?clientId=cli_0012&limit=5'                       # les 5 dernières commandes (tableau)
curl -s 'localhost:4000/api/invoices?status=overdue&sort=balance&order=desc&limit=10' # les 10 plus gros retards
curl -s 'localhost:4000/api/orders?status=delivered&envelope=1&limit=1' | jq .total   # combien de commandes livrées
```

**System**
| Method | Path | Role |
|---|---|---|
| GET | `/health` | `{ok, today}` |
| GET | `/meta` | business, business date |
| GET | `/dashboard` | Host KPI |
| GET | `/search?q=&types=&limit=` | blurred search; `types` = `client,product,supplier,order` (+ `context` on request) |
| GET | `/events?actor=&entity=` | activity log (`actor=ai`: assistant + vocal agent; default `limit` 50) |
| GET | `/events/stream` | Live journal (SSE) |
| POST | `/admin/reset` | recharge the data pack |

**Clients**
| Method | Path | Role |
|---|---|---|
| GET | `/clients?q=&type=&zone=&status=&tag=` | list with KPI; `sort` = `name`, `outstanding`, `overdue`, `last`... |
| GET | `/clients/{id}` | complete sheet (negotiated prices, 20 latest orders, open invoices, payments, usual, recent history) |
| GET | `/clients/{id}/usual` | usual shopping cart (60 last days) |
| POST | `/clients` | create |
| PATCH | `/clients/{id}` | edit (status, ceiling, tags...) |
| POST | `/clients/{id}/notes` | add a note `{text, author}` |
| GET / POST | `/clients/{id}/events?type=&status=&q=` | client history (`sort=open`: folders opened first) / add event |
| GET | `/client-events?type=&status=&clientId=&q=&from=&to=` | historical all customers, recent first |
| PATCH | `/client-events/{id}` | modify, resolve |
| PUT / DELETE | `/clients/{id}/prices/{productId}` | negotiated price |

**Catalogue, suppliers, stock**
| Method | Path | Role |
|---|---|---|
| GET | `/products?q=&category=&tag=&active=` | catalogue with stock; `sort` = `name`, `price`, `margin`, `available`... |
| GET | `/products/{id}` | sheet : stock, lots, supplier prices, movements, sales 30 j |
| GET | `/products/{id}/alternatives` | alternative products |
| PATCH | `/products/{id}` | price, cost, tags... |
| GET | `/suppliers?q=&category=&tag=` · `/suppliers/{id}` | suppliers (the card takes in the latest 60 purchase orders) |
| PATCH | `/suppliers/{id}` | modify |
| GET | `/suppliers/{id}/usual` | regular purchases (60 days) |
| GET / POST | `/suppliers/{id}/events` | history supplier |
| GET / PATCH | `/supplier-events` · `/supplier-events/{id}` | history all suppliers / modify |
| GET | `/stock?q=&tab=` | Stock levels (`tab` = `out`, `low`, `expiring`) |
| GET | `/stock/movements?productId=` | movements, recent first |
| POST | `/stock/adjust` | adjustment or loss `{productId, qty, reason, note}` |

**Sales**
| Method | Path | Role |
|---|---|---|
| GET | `/orders?status=&clientId=&date=&q=&source=` | list, most recent delivery first (`status` = comma separated list); `sort` = `date`, `number`, `total`, `client`... |
| GET | `/orders/{id}` | detail with alerts |
| POST | `/orders` | create a draft `{clientId, deliveryDate?, lines?, note?, source?}` |
| PATCH | `/orders/{id}` | delivery date, note |
| POST / PATCH / DELETE | `/orders/{id}/lines[/{lineId}]` | lines |
| POST | `/orders/{id}/confirm` · `/prepare` · `/deliver` · `/invoice` · `/cancel` | life cycle |

**Achats**
| Method | Path | Role |
|---|---|---|
| GET | `/purchase-orders?status=&supplierId=&date=&q=` | list, recent first |
| GET | `/purchase-orders/{id}` | details with batches received and alerts |
| POST | `/purchase-orders` | create a draft `{supplierId, lines?, expectedDate?, note?}` |
| PATCH | `/purchase-orders/{id}` | due date, note |
| POST / PATCH / DELETE | `/purchase-orders/{id}/lines[/{lineId}]` | lines (brown) |
| POST | `/purchase-orders/{id}/send` · `/receive` · `/cancel` | life cycle |

**Facturation**
| Method | Path | Role |
|---|---|---|
| GET | `/invoices?status=&clientId=&q=` | list without accepted lines (`status=open` and `overdue`); `sort` = `issued`, `due`, `balance`... |
| GET | `/invoices/{id}` | details with payments |
| GET | `/payments?clientId=&method=&q=` | list, recent first (`q`: customer, reference or invoice number) |
| POST | `/payments` | register `{clientId, amount, method, receivedAt?, reference?, allocations?}` |
| GET | `/receivables?q=&tag=&rep=&zone=&onlyOverdue=` | age balance, risk, DSO |

**Prices and groups**
| Method | Path | Role |
|---|---|---|
| GET | `/prices/resolve?clientId=&productId=&qty=&date=` | price and why |
| GET | `/prices/grid?clientId=` or `?clientTag=` (+ `productTag`, `category`, `q`) | Price grid |
| GET / POST | `/price-rules` | rules (`active`, `clientId`, `productId` in filters) / create |
| PATCH / DELETE | `/price-rules/{id}` | edit / delete |
| GET / POST | `/tags?scope=` · `/tags` | groups with meters / create |
| PATCH / DELETE | `/tags/{scope}/{id}` | edit / delete |

**Logistics**
| Method | Path | Role |
|---|---|---|
| GET | `/routes` | definitions of tours |
| GET | `/route-runs?date=&routeId=` | passages with stops, ETA, weight |
| POST | `/route-runs/plan` | plan a date `{date}` |
| PATCH | `/route-runs/{id}/stops` | reorder `{orderIds}` |

**Context**
| Method | Path | Role |
|---|---|---|
| GET | `/context?entityType=&entityId=&kind=&source=&tag=&q=` | search / list (by relevance with `q`) |
| GET | `/context/for?entityType=&id=` | the whole context of an entity |
| GET / PATCH / DELETE | `/context/{id}` | one sheet |
| POST | `/context` | create `{entityType, entityId?, kind, title, body, tags?}` |
