# Le Pétrin de Balma (C0007, `cli_0007`)

> Customer profile for phone role-play. The full history is in `seed_en/clientEvents.json` (filter on `clientId: "cli_0007"`).

| | |
|---|---|
| Type | Retail trade (Artisan bakeries) — 12 avenue de Toulouse, 31130 Balma |
| Area | Balma, Labège & Sud Toulouse — delivered Wed, Sat |
| Status | **blocked** — regular customer |
| Sales representative | Julien Fabre |
| Customer since | 07/09/2020 (6 years) |
| Payment | 30 days — Bad Payer, Risk Account |
| Outstanding balance | 9 465,37 € incl. VAT (ceiling 5 500 €) — **6 overdue invoices: 7 244,72 €** |
| Temperament | disorganized, chatty — quality ★★☆, price ★★☆, risk of losing the customer low |

## Who they are

Balma Bakery resumed in 2020, in difficulty since the opening of a cooking terminal opposite. Two LCR rejected in October 2026, account blocked the 02/11.

## People

- **Romain Gaillard** — Baker-manager · 06 28 91 47 33
  - Speaking style: Sympathic but fleeing as soon as we talk about money, always overwhelmed.
  - Typical phrases: "The LCR is ironed, I swear." · "Just deliver me the flour of the week."

## What they buy and how

Order twice a week, usually the day before between 13h and 18h, especially by telephone and WhatsApp. Regular products: T55 traditional French wheat flour (25 kg bag), 82% laminating butter (2 kg sheet), Baker's chocolate sticks 44% (1.6 kg carton, 300 sticks), Printed kraft baguette bags (carton of 1000), Fine sea salt (25 kg bag), Dehydrated rye sourdough (1 kg bag), Porcelain king cake charms (pack of 100), T150 organic wholemeal flour (25 kg bag).

Over the last 90 days (13 orders delivered):

| Product | 90-day volume | Lines | Last price |
|---|---|---|---|
| T55 traditional French wheat flour (25 kg bag) (`prd_0001`) | 151,00 piece | 7 | 19,11 € |
| 82% laminating butter (2 kg sheet) (`prd_0026`) | 171,07 kg | 6 | 9,16 € |
| Baker's chocolate sticks 44% (1.6 kg carton, 300 sticks) (`prd_0042`) | 68,00 box | 9 | 13,88 € |
| Printed kraft baguette bags (carton of 1000) (`prd_0065`) | 42,00 box | 11 | 22,00 € |
| T55 baker's wheat flour (25 kg bag) (`prd_0002`) | 47,00 piece | 5 | 17,20 € |
| T130 rye flour (25 kg bag) (`prd_0006`) | 23,00 piece | 7 | 24,56 € |
| Pasteurised liquid whole egg (1 L carton) (`prd_0035`) | 98,00 liter | 6 | 4,31 € |
| Blanched ground almonds (5 kg bag) (`prd_0046`) | 32,18 kg | 4 | 11,83 € |

CRM record : _Commanded twice a week: tradition, yeast, standard laminating butter._

## What frustrates them

- Talk about money on the phone.
- The Sandrine Recoverys

## A brief history

- **24/04/2026** · Have quality : T130 rye flour (25 kg bag)
- **30/04/2026** · Payment · Recovery : FAC-2026-000601
- **02/05/2026** · claim · Outturn: T150 organic wholemeal flour (25 kg bag) not delivered
- **16/05/2026** · claim · Outturn: T150 organic wholemeal flour (25 kg bag) not delivered
- **15/07/2026** · Payment · Recovery : FAC-2026-001192
- **21/07/2026** · note · Summer closure 2026
- **09/09/2026** · Payment · Recovery : FAC-2026-001645
- **03/10/2026** · claim · Outturn: T150 organic wholemeal flour (25 kg bag) not delivered
- **31/10/2026** · payment · Second LCR rejected
- **02/11/2026** · Payment · Locked account for unpaid payments
- **05/11/2026** · Schedule · Proposed Schedule
- **07/11/2026** · Payment · Recovery : FAC-2026-002079

Full history: 72 events (19 claim, 19 payment, 7 call, 6 quality, 6 visit, 4 price, 3 note, 2 delivery, 2 special request, 2 have, 1 opening, 1 schedule).

## Open cases

- **31/10/2026 — Second LCR rejected**
  LCR of 2 380 € rejected for insufficient provision, after September.
- **02/11/2026 — Locked account for outstanding payments** (`inv_007756`)
  6 outstanding due invoices for 7 244,72 € incl. VAT. Deliveries suspended until at least 50 % due and a validated schedule.
- **05/11/2026 — Proposed timeline**
  Romain proposes to pay in 3 times and requests the resumption of deliveries. Waiting for validation by management.
- **07/11/2026 — Recovery: FAC-2026-002079 fallen** (`inv_007894`)
  Invoice FAC-2026-002079 (1 399,04 € incl. VAT) fell on the 28/10/2026. Re-launched by email and then phone. Romain: "It's gone this week."

## How to talk to them

- No delivery without Sandrine or Bernard agreement.
- Take the message and transmit.

## Price & group

Groups: **Boulangeries** (`boulangeries`), **To be monitored** (`a-surveiller`).
No negotiated prices.

Price rules that may apply:
- `prl_0001` Bakeries: -4 % on flours from 10 bags
- `prl_0006` Epiphany 2027: almond powder -6 % from 20 kg
- `prl_0007` Epiphany 2027: crowns and beans -5 %

Latest notes CRM:

- 25/06/2026, Julien (commercial): Don't want any substitution without being warned: if a product is missing, call Romain before the truck leaves.
- 15/10/2026, Julien (commercial): Closed on Wednesday: never delivered on that day.
- 02/11/2026, Sandrine (Accounting): BLOCKED account for unpaid invoices. 6 outstanding invoices, the oldest FAC-2026-001941 of the 07/09/2026. Outstanding 9 465,37 € incl. VAT for a ceiling of 5 500,00 €. Resumption of deliveries only after a settlement of at least 50 % of the due date and a schedule validated by management.
- 21/11/2026, Julien (commercial): Romain called back to resume deliveries and promised a transfer. Do not deliver anything without the agreement of accounting.
