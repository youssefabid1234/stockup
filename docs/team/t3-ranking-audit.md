# T3 · Classification of replacements: audit before / after (Daycem, 24/11)

For DECISIONS.md. Without paying call: `rank_alternatives` on the real data of the ERP (71 products,
`GET /api/products/{id}/alternatives`stock of 24/11 after `make reset`).

## The problem
The ERP returns products of the same class in stock, **classified by nearest price**.
The company only names a substitute for 9 products. For the other 62, the first choice was often absurd
for the same use (about 29), e.g.: pre-cooked baguette → raspberry purée, semolina sugar → vanilla extract,
liquid cream → liquid whole egg, black chocolate 64% → white chocolate, strawberry → lemon.

## What changes (general rule, no product name in code: `agent/rules_sales.py`)
1. **Classification**: in stock → document substitute → same category → ** distinctive words shared with the name of the
   Missing product** (`name_match` : without packaging in parentheses, no numbers or units; the first word counts
   double; a word shared by most candidates does not separate) → same unit → promo → order of the ERP.
2. ** "No substitutes of the same use"** (`has_same_use_substitute`) : no substitutes for the documents in stock and none
   candidate who shares a word of the name (here the last word counts) → `product_insight` does not propose anything and the agent
   asks the customer what he wants (rule added to SALES_RULES).

## Result
- 9 document substitutes: **always first** (test).
- **27 first choices change** (e.g. liquid cream → fresh cream ; black 64% → black 70% ; sour sugar → sugar
  beaded ; egg white → whole egg ; T55 baker → T55 tradition ; grape bread → mini-veennoiseries).
- **23 products without substitute for the same use** → the agent asks (fresh fruits, salt, vanilla, flower water)
  orange, napping, praline, cocoa, packaging...).
- Known limits: pre-cooked baguette and raspberry puree → laminated paste, laminated paste → croissant remain
  proposed (nothing better in stock in the category, and a common word is enough for "same use"; some questionable "ask" (slipper margarine, walnut kernels,
  The customer always keeps the last word: no replacement is added without its "yes".

## Connection (Youssef file, applied with its agreement; exclusions added then)
`apps/ai/app/tools/insight.py` must pass `for_product_name` and `for_unit` à `rank_alternatives` (other than point 1 is
no effect) and call `has_same_use_substitute` before the second price wave (point 2). Patch ready (311 green tests with
the patch applied):

```diff
--- a/apps/ai/app/tools/insight.py
+++ b/apps/ai/app/tools/insight.py
@@ -98,7 +98,7 @@

 async def gets_insight(erp, client_id: str, product_id: str, qty: float | None = None) -> dict[str, Any]:
     ""Everything about one product for one client, in one call. Shape: docs/team/interfaces.md §2.""
- from app.agent.rules_sales import rank_alternatives, substitution_policy
+ from app.agent.rules_sales import has_same_use_substitute, rank_alternatives, substitution_policy

     async def safe(coro):
         try:
@@ -153,6 +153,15 @@
         returned

     candidates = [a for a in alternatives or [] if a.get("id") and a.get("id") != product_id]
+ if not has_same_use_substitute(product_id, product.get("name") or "", candidates):
+ # Daycem's T3: noting in stock has the same use (docs name none, no name in common): don't push lemons for
+ # strawberries; no second wave of prices either
+ out["alternatives"] = []
+ out["note"] = (
+ "No product in stock has the same use. Announces the rupture and asks the customer what he wants, "
+ "without offering a product."
+        )
+ return out
     PRICES = await asyncio.gather(
         *(_resolve(erp, client_id, a["id"], qty if a.get("unit") == product.get("unit") else None) for a in candidates)
     )
@@ -170,6 +179,9 @@
         if promo := promo_of(p, rules):
             row["promo"] = promo
         rows.append(row)
- ranked = rank_alternatives(rows, card.get("preferences") or "", for_product_id=product_id, for_category=product.get("category"))
+ ranked = rank_alternatives(
+ rows, card.get("preferences") or "", for_product_id=product_id, for_category=product.get("category"),
+ for_product_name=product.get("name"), for_unit=product.get("unit"),
+    )
     out["alternatives"] = [{k: v for k, v in r.items() if k != "category"} for r in raised[:MAX_ALTERNATIVES]]
     returned
```

## Product Detail by Product
"1st before" = order of the ERP + documents; "1st after" = new classification (- = no replacement of the same use).

| Product | Name | Doc | 1st front | 1st after | Effect |
|---|---|---|---|---|---|
| prd_0001 | Wheat flour T55 French tradition | yes | Wheat flour T55 baker | Wheat flour T55 baker |  |
| prd_0002 | Wheat flour T55 baker |  | Wheat flour T65 year | Wheat flour T55 French tradition | changed |
| prd_0003 | Groat flour T45 pastry |  | Rye flour T130 | Rye flour T130 |  |
| prd_0004 | Wheat flour T65 year |  | Wheat flour T55 French tradition | Wheat flour T55 French tradition |  |
| prd_0005 | Flour bise T80 |  | Wheat flour T55 French tradition | Wheat flour T55 French tradition |  |
| prd_0006 | Rye flour T130 |  | Groat flour T45 pastry | Groat flour T45 pastry |  |
| prd_0007 | Organic T65 wheat flour | yes | Wheat flour T65 year | Wheat flour T65 year |  |
| prd_0008 | Complete flour T150 organic |  | Multicereal seed mixture | Multicereal seed mixture |  |
| prd_0009 | Organic small spelt flour |  | Multicereal seed mixture | Multicereal seed mixture |  |
| prd_0010 | Multicereal seed mixture |  | Rye flour T130 | — | no replacements of the same use → ask |
| prd_0011 | Fresh baker's yeast | yes | Instant dry yeast | Instant dry yeast |  |
| prd_0012 | Instant dry yeast |  | Fresh baker's yeast | Fresh baker's yeast |  |
| prd_0013 | Dehydrated rye leaven |  | Instant dry yeast | — | no replacements of the same use → ask |
| prd_0014 | Breading enhancer |  | Dehydrated rye leaven | — | no replacements of the same use → ask |
| prd_0015 | Soft sugar |  | Liquid vanilla extract | Beaded sugar | changed |
| prd_0016 | Ice sugar |  | Beaded sugar | Beaded sugar |  |
| prd_0017 | Beaded sugar |  | White pastry fondant | Ice sugar | changed |
| prd_0018 | End-of-sea salt |  | Orange blossom water | — | no replacements of the same use → ask |
| prd_0019 | Hot neutral coating |  | Liquid vanilla extract | — | no replacements of the same use → ask |
| prd_0020 | White pastry fondant |  | Beaded sugar | Preparation for cold pastry cream | changed |
| prd_0021 | Preparation for cold pastry cream |  | Soft sugar | White pastry fondant | changed |
| prd_0022 | Bourbon vanilla pods from Madagascar | yes | Liquid vanilla extract | Liquid vanilla extract |  |
| prd_0023 | Liquid vanilla extract |  | Soft sugar | — | no replacements of the same use → ask |
| prd_0024 | Orange blossom water |  | End-of-sea salt | — | no replacements of the same use → ask |
| prd_0025 | Touring butter AOP Charentes-Poitou 84 % | yes | Touring butter 82 % | Touring butter 82 % |  |
| prd_0026 | Touring butter 82 % |  | Sweet butter PDO Charentes-Poitou | Sweet butter PDO Charentes-Poitou |  |
| prd_0027 | Sweet butter PDO Charentes-Poitou | yes | Pastry butter 82 % | Pastry butter 82 % |  |
| prd_0028 | Pastry butter 82 % |  | Touring butter 82 % | Touring butter 82 % |  |
| prd_0029 | Half-salt butter |  | Sweet butter PDO Charentes-Poitou | Sweet butter PDO Charentes-Poitou |  |
| prd_0030 | Sheeting margarine |  | Pastry butter 82 % | — | no replacements of the same use → ask |
| prd_0031 | Liquid cream UHT 35 % |  | Whole egg liquid pasteurized | Thick fresh cream 30% | changed |
| prd_0032 | Thick fresh cream 30% |  | Whole egg liquid pasteurized | Liquid cream UHT 35 % | changed |
| prd_0033 | Whole milk UHT |  | Pasteurized liquid egg white | Liquid cream UHT 35 % | changed |
| prd_0034 | Outdoor eggs size M | yes | Whole egg liquid pasteurized | Whole egg liquid pasteurized |  |
| prd_0035 | Whole egg liquid pasteurized |  | Liquid cream UHT 35 % | Pasteurized liquid egg white | changed |
| prd_0036 | Pasteurized liquid egg yolk |  | Outdoor eggs size M | Whole egg liquid pasteurized | changed |
| prd_0037 | Pasteurized liquid egg white |  | Liquid cream UHT 35 % | Whole egg liquid pasteurized | changed |
| prd_0038 | Cover chocolate black 64% |  | White cover chocolate 33% | Black chocolate cover 70% | changed |
| prd_0039 | Black chocolate cover 70% | yes | Cover chocolate black 64% | Cover chocolate black 64% |  |
| prd_0040 | Milk cover chocolate 38% |  | Cover chocolate black 64% | Cover chocolate black 64% |  |
| prd_0041 | White cover chocolate 33% |  | Cover chocolate black 64% | Cover chocolate black 64% |  |
| prd_0042 | Chocolate baker's sticks 44% |  | Milk cover chocolate 38% | Milk cover chocolate 38% |  |
| prd_0043 | Cocoa powder 22-24 % |  | Chocolate baker's sticks 44% | — | no replacements of the same use → ask |
| prd_0044 | Black chocolate chips cooked |  | Cocoa powder 22-24 % | Cover chocolate black 64% | changed |
| prd_0045 | Noise Praline 50 % |  | White cover chocolate 33% | — | no replacements of the same use → ask |
| prd_0046 | White almond powder |  | Slashed almonds | Roasted hazelnut powder | changed |
| prd_0047 | Slashed almonds | yes | White almond powder | White almond powder |  |
| prd_0048 | Roasted hazelnut powder |  | Walnut kernels | White almond powder | changed |
| prd_0049 | Green pistachios punctuated |  | Roasted hazelnut powder | — | no replacements of the same use → ask |
| prd_0050 | Dried sultanine grapes |  | Candied fruit in cubes | — | no replacements of the same use → ask |
| prd_0051 | Walnut kernels |  | Slashed almonds | — | no replacements of the same use → ask |
| prd_0052 | Candied fruit in cubes |  | White almond powder | — | no replacements of the same use → ask |
| prd_0053 | Frozen pure raw butter crescent 70 g |  | Chocolate pure raw frozen butter 75 g | Chocolate pure raw frozen butter 75 g |  |
| prd_0054 | Chocolate pure raw frozen butter 75 g |  | Frozen pure raw butter crescent 70 g | Frozen pure raw butter crescent 70 g |  |
| prd_0055 | Frozen raw grape bread 110 g |  | Pasta, pure butter in plates | Assortment of raw mini-veennoiseries | changed |
| prd_0056 | Assortment of raw mini-veennoiseries |  | Frozen raw grape bread 110 g | Frozen raw grape bread 110 g |  |
| prd_0057 | Pasta, pure butter in plates |  | Frozen raw grape bread 110 g | Frozen pure raw butter crescent 70 g | changed |
| prd_0058 | Frozen pre-cooked fly 280 g |  | Frozen raspberry puree | Pasta, pure butter in plates | changed |
| prd_0059 | Frozen raspberry puree |  | Frozen pre-cooked fly 280 g | Pasta, pure butter in plates | changed |
| prd_0060 | Strawberry Gariguette |  | Yellow Lemon | — | no replacements of the same use → ask |
| prd_0061 | Raspberry |  | Yellow Lemon | — | no replacements of the same use → ask |
| prd_0062 | Yellow Lemon |  | Apple Golden pastry | — | no replacements of the same use → ask |
| prd_0063 | Apple Golden pastry |  | Yellow Lemon | — | no replacements of the same use → ask |
| prd_0064 | Pear Williams |  | Yellow Lemon | — | no replacements of the same use → ask |
| prd_0065 | Printed kraft bag |  | Pastry paper bags | — | no replacements of the same use → ask |
| prd_0066 | Pastry paper bags |  | White pastry boxes 20 cm | Silicone baking paper 40 × 60 | changed |
| prd_0067 | White pastry boxes 20 cm |  | Pastry paper bags | — | no replacements of the same use → ask |
| prd_0068 | Crowns of golden cardboard kings |  | White pastry boxes 20 cm | Round gold soles 28 cm | changed |
| prd_0069 | King's beans in porcelain |  | Pastry paper bags | — | no replacements of the same use → ask |
| prd_0070 | Round gold soles 28 cm |  | White pastry boxes 20 cm | — | no replacements of the same use → ask |
| prd_0071 | Silicone baking paper 40 × 60 |  | Printed kraft bag | Pastry paper bags | changed |

Diagnosis S45: `place_order` written before the customer's agreement (Amine K.)

Replay of 24/11 (after `make reset`, all lit): S44, S04, S05, S40 pass; **S45 fails on `tools_none`** because
that in the first turn the agent calls `place_order` together with `product_insight` (ORDER_RULES rule: "as soon as
The answer itself is right ("... almond powder").
White ... I'll put it in your place ?").

Verified without model (direct tool call, ERP reset before and after): `place_order` **creates the draft itself
when stock is missing**, with only one alert:

| Client | Request | `written` | Reading | Alert |
|---|---|---|---|---|
| cli_0021 | 3 AOP turning cartons, Wednesday | True | 30 kilos of AOP Touring Butter...; Wednesday, November 25 | in rupture |
| cli_0053 | 10 kg hazelnut powder, Friday | True | 10 kilos of roasted hazelnut powder; Friday, 27 November | only 2.57 kilos left |

Same call to the first round of S05 (which passes: its controls do not prohibit it). Proposal to Amine K.: if a
line exceeds stock available, do not write anything and return `next` = "insufficient quantity of product: proposed
first with product_insight".

## Exclusions written in the sheets ("never from...", "...only")

`card_rules` reads preferences and notes, sentence by sentence; `rank_alternatives` remove what the prohibited card
and `has_same_use_substitute` does not count these products (if nothing remains → "no equivalent", the agent asks).
General rule: a prohibition removes a product whose name contains all its words; an obligation does not apply
that if the missing product contains its first word (its family), and only keeps the products that contain the
a phrase whose words are not in any product name
("Never deliver that day," "...does not read the recovery emails") has no effect.

List verified by Daycem (24/11), 29 out of 104 sheets:

| Phrase | Sheets | Effect |
|---|---|---|
| "Don't want to freeze" | 10 | no frozen product (pre-cooked baguette, chocolate, croissant, grape bread, raspberry purée) |
| "Never thick" | 7 | Never the thick fresh cream |
| "35 % Cream Only" | 7 (the same) | if the liquid cream 35% is missing: nothing → the agent asks |
| "Traditional flour of Lauragais only" | 8 | if the T55 tradition lacks: nothing (not even the document substitute) → the agent asks |
| « Covers exclusively Cacaos Garonne » | 1 | if coverage is missing: only another coverage |
| "AOP tour only" | 1 | if the AOP tour is missing: nothing (this customer already refuses the replacements) |
| "Liquid products only" | 3 | ignored (see limits) |
| "Never delivered that day" (notes) | 18 | no effect |

### Known limits (not coded)
1. **Ovoproducts** (3 plugs: central kitchen, EHPAD, high school): "ovoproduct" does not appear in any product name,
   So the rule is ignored; if a liquid egg is missing, the shell eggs can still be offered (the agent
   read the form, but there is no guarantee of it). **Piste**: synonyms from the company glossary
   (`DATA_DIR/context`, as `doc_substitutes`) : egg products = whole egg / yellow / white liquid egg.
2. **Mark of blankets** (1 sheet: "Cacoos Garonne covers exclusively, Ecuadorian origin and Peru"):
   the mark is not in the names, only the "cover" family is verified. **Site**: check the supplier
   of product (`mainSupplierId` in the ERP) against the name of the supplier cited in the form.

### Direct Test of `product_insight` (24/11, no model, after `make reset`)
Same demand, 1,500 L of UHT 35% liquid cream (there are 1,320 L left, 180 missing), for two customers who
accept replacements:

| Client | Form | Alternatives returned | Note |
|---|---|---|---|
| Le Petit Four de Saint-Cyprien (cli_0053) | "Only 35% cream, never thick" | none | "No product in stock has the same use. Announces the break and asks the customer what he wants, without offering a product." |
| Le Pétrin de Colomiers (cli_0021) | no exclusion | Thick fresh cream 30%, whole egg liquid, liquid egg white, whole milk, liquid egg yolk | — |

Thick cream, the first choice for a customer without exclusion, is never offered to the customer who excluded it.
(Cas built: in the EPR of 24/11, no really broken product touches an exclusion plug; the
scenario S46 uses the nearest real case.)

## Bilingual: English data (`SEED_DIR_NAME=seed_en`, 24/11)

The same functions read English and French **without setting** (a plug is in either language).
Audit without model: French LES (port 4000) against a temporary English LES (port 4001, base-by-base), same code.

| Audit | French | English before | English after |
|---|---|---|---|
| Replacement decision, AOP turning (104 plugs) | Refuses 37 · accepts 52 · ask 6 · unknown 9 | unknown 104 | Refuses 37 · accepts 51 · ask 7 · unknown 9 |
| First choice of classification (71 products) | — | 61 / 71 Like French | **71 / 71** |
| "No substitutes of the same use" | 23 | 25 | 23 (the same) |
| Sheets where an exclusion is read | 39 | 0 | 41 |

**French has not moved**: code of `main` against bilingual code, of the 104 sheets × 71 products (preferences and
Notes): 7,384 / 7,384 identical decisions, 7,384 / 7,384 identical classifications (order and exclusions).

How:
- `substitution_policy` : actual English turns ("Accepts equivalent substitutions if informed", "Equivalent
  substitutions accepted if we are toold, "Refusals substitutes", "Substitutions refused", "Never any
  substitution on the butter", "Does not want any substitution without being gold").
- `card_rules` "never X", "does not want X", "no X", "X only", "only X", "exclusively X"; words
  English generics ignored (goods, products, from, the...).
- Product names: in English the product is **the last word** ("UHT liquid cream"), in French the first;
  `name_match` compares English names **via their French original** (`data/seed_en/GLOSSARY.md`), hence the same
  A non-glossary English name uses the last word.
- `doc_substitutes` : read by ID, walk in both languages (tested with an English line).

Remaining deviations (no refusal read as an agreement, or the other way around):
1. **"request" instead of "accept"** on 39 couple sheet × produced on 7,384 (including cli_0007 for touring)
   AOP: "standard laminating butter" shares two words with "AOP ... laminating butter", one in French
   "standard tour"). On the conservative side: the agent asks before appointing a replacement.
   11 French decisions: abandoned.
2. **Exclusions** (32 couples, 11 sheets):
   - "Liquid egg products only" (3 sheets) ** is read in English** (the word "egg" is in the names): if an egg
     Liquid lacks, more eggs in shell or cream. In French, "ovoproducts" remains ignored (limit 1).
   - "35 % cream only" (7 sheets) does not apply when the cream is thick fresh or the cream preparation
     pastryman lacks: their English names keep "cream", not "cream". The French rule went further
     (only cream products), no useful effect in practice.
   - Sarrailh ("exclusively AOP butter for laminating") : the English rule also affects sweet butter AOP.
     effect in practice: this customer refuses replacements, `product_insight` Don't propose anything.
3. **English prompt.** At the time of the ranking audit the English rules were awaiting integration. They now run when `TEAM_SALES_RULES=1`.
