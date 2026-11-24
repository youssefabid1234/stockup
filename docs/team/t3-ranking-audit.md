# T3 · Classement des remplaçants : audit avant / après (Daycem, 24/11)

Pour DECISIONS.md. Sans appel payant : `rank_alternatives` sur les vraies données de l'ERP (71 produits,
`GET /api/products/{id}/alternatives`, stock du 24/11 après `make reset`).

## Le problème
L'ERP renvoie les produits de la même catégorie en stock, **classés par prix le plus proche**. Les documents de
l'entreprise ne nomment un substitut que pour 9 produits. Pour les 62 autres, le premier choix était souvent absurde
pour le même usage (environ 29), par exemple : baguette précuite → purée de framboise, sucre semoule → extrait de vanille,
crème liquide → œuf entier liquide, chocolat noir 64 % → chocolat blanc, fraise → citron.

## Ce qui change (règle générale, aucun nom de produit dans le code : `agent/rules_sales.py`)
1. **Classement** : en stock → substitut des documents → même catégorie → **mots distinctifs partagés avec le nom du
   produit manquant** (`name_match` : sans l'emballage entre parenthèses, ni nombres ni unités ; le premier mot compte
   double ; un mot partagé par la plupart des candidats ne départage pas) → même unité → promo → ordre de l'ERP.
2. **« Aucun remplaçant de même usage »** (`has_same_use_substitute`) : aucun substitut des documents en stock et aucun
   candidat qui partage un mot du nom (ici le mot de famille compte) → `product_insight` ne propose rien et l'agent
   demande au client ce qu'il souhaite (règle ajoutée à SALES_RULES).

## Résultat
- 9 substituts des documents : **toujours premiers** (test).
- **27 premiers choix changent** (ex. crème liquide → crème fraîche ; noir 64 % → noir 70 % ; sucre semoule → sucre
  perlé ; blanc d'œuf → œuf entier ; T55 boulangère → T55 tradition ; pain aux raisins → mini-viennoiseries).
- **23 produits sans remplaçant de même usage** → l'agent demande (fruits frais, sel, vanille, eau de fleur
  d'oranger, nappage, praliné, cacao, emballages…).
- Limites connues : baguette précuite et purée de framboise → pâte feuilletée, pâte feuilletée → croissant restent
  proposés (rien de mieux en stock dans la catégorie, et un mot commun suffit pour « même usage ») ; quelques « demander » discutables (margarine de feuilletage, cerneaux de noix,
  raisins secs). Le client garde toujours le dernier mot : aucun remplaçant n'est ajouté sans son « oui ».

## Branchement (fichier de Youssef, appliqué avec son accord ; exclusions ajoutées ensuite)
`apps/ai/app/tools/insight.py` doit passer `for_product_name` et `for_unit` à `rank_alternatives` (sinon le point 1 est
sans effet) et appeler `has_same_use_substitute` avant la 2e vague de prix (point 2). Patch prêt (311 tests verts avec
le patch appliqué) :

```diff
--- a/apps/ai/app/tools/insight.py
+++ b/apps/ai/app/tools/insight.py
@@ -98,7 +98,7 @@
 
 async def gather_insight(erp, client_id: str, product_id: str, qty: float | None = None) -> dict[str, Any]:
     """Everything about one product for one client, in one call. Shape: docs/team/interfaces.md §2."""
-    from app.agent.rules_sales import rank_alternatives, substitution_policy
+    from app.agent.rules_sales import has_same_use_substitute, rank_alternatives, substitution_policy
 
     async def safe(coro):
         try:
@@ -153,6 +153,15 @@
         return out
 
     candidates = [a for a in alternatives or [] if a.get("id") and a.get("id") != product_id]
+    if not has_same_use_substitute(product_id, product.get("name") or "", candidates):
+        # Daycem's T3: nothing in stock has the same use (docs name none, no name in common): don't push lemons for
+        # strawberries; no second wave of prices either
+        out["alternatives"] = []
+        out["note"] = (
+            "Aucun produit en stock n'a le même usage. Annonce la rupture et demande au client ce qu'il souhaite, "
+            "sans proposer de produit."
+        )
+        return out
     prices = await asyncio.gather(
         *(_resolve(erp, client_id, a["id"], qty if a.get("unit") == product.get("unit") else None) for a in candidates)
     )
@@ -170,6 +179,9 @@
         if promo := promo_of(p, rules):
             row["promo"] = promo
         rows.append(row)
-    ranked = rank_alternatives(rows, card.get("preferences") or "", for_product_id=product_id, for_category=product.get("category"))
+    ranked = rank_alternatives(
+        rows, card.get("preferences") or "", for_product_id=product_id, for_category=product.get("category"),
+        for_product_name=product.get("name"), for_unit=product.get("unit"),
+    )
     out["alternatives"] = [{k: v for k, v in r.items() if k != "category"} for r in ranked[:MAX_ALTERNATIVES]]
     return out
```

## Détail produit par produit
« 1er avant » = ordre de l'ERP + documents ; « 1er après » = nouveau classement (— = aucun remplaçant de même usage).

| Produit | Nom | Doc | 1er avant | 1er après | Effet |
|---|---|---|---|---|---|
| prd_0001 | Farine de blé T55 tradition française | oui | Farine de blé T55 boulangère | Farine de blé T55 boulangère |  |
| prd_0002 | Farine de blé T55 boulangère |  | Farine de blé T65 campagne | Farine de blé T55 tradition française | changé |
| prd_0003 | Farine de gruau T45 pâtissière |  | Farine de seigle T130 | Farine de seigle T130 |  |
| prd_0004 | Farine de blé T65 campagne |  | Farine de blé T55 tradition française | Farine de blé T55 tradition française |  |
| prd_0005 | Farine bise T80 |  | Farine de blé T55 tradition française | Farine de blé T55 tradition française |  |
| prd_0006 | Farine de seigle T130 |  | Farine de gruau T45 pâtissière | Farine de gruau T45 pâtissière |  |
| prd_0007 | Farine de blé T65 bio | oui | Farine de blé T65 campagne | Farine de blé T65 campagne |  |
| prd_0008 | Farine complète T150 bio |  | Mélange multicéréales graines | Mélange multicéréales graines |  |
| prd_0009 | Farine de petit épeautre bio |  | Mélange multicéréales graines | Mélange multicéréales graines |  |
| prd_0010 | Mélange multicéréales graines |  | Farine de seigle T130 | — | aucun remplaçant de même usage → demander |
| prd_0011 | Levure fraîche boulangère | oui | Levure sèche instantanée | Levure sèche instantanée |  |
| prd_0012 | Levure sèche instantanée |  | Levure fraîche boulangère | Levure fraîche boulangère |  |
| prd_0013 | Levain de seigle déshydraté |  | Levure sèche instantanée | — | aucun remplaçant de même usage → demander |
| prd_0014 | Améliorant de panification |  | Levain de seigle déshydraté | — | aucun remplaçant de même usage → demander |
| prd_0015 | Sucre semoule |  | Extrait de vanille liquide | Sucre en grains perlé | changé |
| prd_0016 | Sucre glace |  | Sucre en grains perlé | Sucre en grains perlé |  |
| prd_0017 | Sucre en grains perlé |  | Fondant pâtissier blanc | Sucre glace | changé |
| prd_0018 | Sel fin de mer |  | Eau de fleur d'oranger | — | aucun remplaçant de même usage → demander |
| prd_0019 | Nappage neutre à chaud |  | Extrait de vanille liquide | — | aucun remplaçant de même usage → demander |
| prd_0020 | Fondant pâtissier blanc |  | Sucre en grains perlé | Préparation pour crème pâtissière à froid | changé |
| prd_0021 | Préparation pour crème pâtissière à froid |  | Sucre semoule | Fondant pâtissier blanc | changé |
| prd_0022 | Gousses de vanille Bourbon de Madagascar | oui | Extrait de vanille liquide | Extrait de vanille liquide |  |
| prd_0023 | Extrait de vanille liquide |  | Sucre semoule | — | aucun remplaçant de même usage → demander |
| prd_0024 | Eau de fleur d'oranger |  | Sel fin de mer | — | aucun remplaçant de même usage → demander |
| prd_0025 | Beurre de tourage AOP Charentes-Poitou 84 % | oui | Beurre de tourage 82 % | Beurre de tourage 82 % |  |
| prd_0026 | Beurre de tourage 82 % |  | Beurre doux AOP Charentes-Poitou | Beurre doux AOP Charentes-Poitou |  |
| prd_0027 | Beurre doux AOP Charentes-Poitou | oui | Beurre pâtissier 82 % | Beurre pâtissier 82 % |  |
| prd_0028 | Beurre pâtissier 82 % |  | Beurre de tourage 82 % | Beurre de tourage 82 % |  |
| prd_0029 | Beurre demi-sel de baratte |  | Beurre doux AOP Charentes-Poitou | Beurre doux AOP Charentes-Poitou |  |
| prd_0030 | Margarine de feuilletage |  | Beurre pâtissier 82 % | — | aucun remplaçant de même usage → demander |
| prd_0031 | Crème liquide UHT 35 % |  | Œuf entier liquide pasteurisé | Crème fraîche épaisse 30 % | changé |
| prd_0032 | Crème fraîche épaisse 30 % |  | Œuf entier liquide pasteurisé | Crème liquide UHT 35 % | changé |
| prd_0033 | Lait entier UHT |  | Blanc d'œuf liquide pasteurisé | Crème liquide UHT 35 % | changé |
| prd_0034 | Œufs plein air calibre M | oui | Œuf entier liquide pasteurisé | Œuf entier liquide pasteurisé |  |
| prd_0035 | Œuf entier liquide pasteurisé |  | Crème liquide UHT 35 % | Blanc d'œuf liquide pasteurisé | changé |
| prd_0036 | Jaune d'œuf liquide pasteurisé |  | Œufs plein air calibre M | Œuf entier liquide pasteurisé | changé |
| prd_0037 | Blanc d'œuf liquide pasteurisé |  | Crème liquide UHT 35 % | Œuf entier liquide pasteurisé | changé |
| prd_0038 | Chocolat de couverture noir 64 % |  | Chocolat de couverture blanc 33 % | Chocolat de couverture noir 70 % | changé |
| prd_0039 | Chocolat de couverture noir 70 % | oui | Chocolat de couverture noir 64 % | Chocolat de couverture noir 64 % |  |
| prd_0040 | Chocolat de couverture lait 38 % |  | Chocolat de couverture noir 64 % | Chocolat de couverture noir 64 % |  |
| prd_0041 | Chocolat de couverture blanc 33 % |  | Chocolat de couverture noir 64 % | Chocolat de couverture noir 64 % |  |
| prd_0042 | Bâtons de chocolat boulanger 44 % |  | Chocolat de couverture lait 38 % | Chocolat de couverture lait 38 % |  |
| prd_0043 | Cacao en poudre 22-24 % |  | Bâtons de chocolat boulanger 44 % | — | aucun remplaçant de même usage → demander |
| prd_0044 | Pépites de chocolat noir cuisson |  | Cacao en poudre 22-24 % | Chocolat de couverture noir 64 % | changé |
| prd_0045 | Praliné noisette 50 % |  | Chocolat de couverture blanc 33 % | — | aucun remplaçant de même usage → demander |
| prd_0046 | Poudre d'amande blanche |  | Amandes effilées | Poudre de noisette torréfiée | changé |
| prd_0047 | Amandes effilées | oui | Poudre d'amande blanche | Poudre d'amande blanche |  |
| prd_0048 | Poudre de noisette torréfiée |  | Cerneaux de noix | Poudre d'amande blanche | changé |
| prd_0049 | Pistaches vertes émondées |  | Poudre de noisette torréfiée | — | aucun remplaçant de même usage → demander |
| prd_0050 | Raisins secs sultanines |  | Fruits confits en cubes | — | aucun remplaçant de même usage → demander |
| prd_0051 | Cerneaux de noix |  | Amandes effilées | — | aucun remplaçant de même usage → demander |
| prd_0052 | Fruits confits en cubes |  | Poudre d'amande blanche | — | aucun remplaçant de même usage → demander |
| prd_0053 | Croissant pur beurre cru surgelé 70 g |  | Chocolatine pur beurre crue surgelée 75 g | Chocolatine pur beurre crue surgelée 75 g |  |
| prd_0054 | Chocolatine pur beurre crue surgelée 75 g |  | Croissant pur beurre cru surgelé 70 g | Croissant pur beurre cru surgelé 70 g |  |
| prd_0055 | Pain aux raisins cru surgelé 110 g |  | Pâte feuilletée pur beurre en plaques | Assortiment mini-viennoiseries crues | changé |
| prd_0056 | Assortiment mini-viennoiseries crues |  | Pain aux raisins cru surgelé 110 g | Pain aux raisins cru surgelé 110 g |  |
| prd_0057 | Pâte feuilletée pur beurre en plaques |  | Pain aux raisins cru surgelé 110 g | Croissant pur beurre cru surgelé 70 g | changé |
| prd_0058 | Baguette précuite surgelée 280 g |  | Purée de framboise surgelée | Pâte feuilletée pur beurre en plaques | changé |
| prd_0059 | Purée de framboise surgelée |  | Baguette précuite surgelée 280 g | Pâte feuilletée pur beurre en plaques | changé |
| prd_0060 | Fraise Gariguette |  | Citron jaune | — | aucun remplaçant de même usage → demander |
| prd_0061 | Framboise |  | Citron jaune | — | aucun remplaçant de même usage → demander |
| prd_0062 | Citron jaune |  | Pomme Golden pâtissière | — | aucun remplaçant de même usage → demander |
| prd_0063 | Pomme Golden pâtissière |  | Citron jaune | — | aucun remplaçant de même usage → demander |
| prd_0064 | Poire Williams |  | Citron jaune | — | aucun remplaçant de même usage → demander |
| prd_0065 | Sacs à baguette kraft imprimés |  | Sachets viennoiserie papier | — | aucun remplaçant de même usage → demander |
| prd_0066 | Sachets viennoiserie papier |  | Boîtes pâtissières blanches 20 cm | Papier cuisson siliconé 40 × 60 | changé |
| prd_0067 | Boîtes pâtissières blanches 20 cm |  | Sachets viennoiserie papier | — | aucun remplaçant de même usage → demander |
| prd_0068 | Couronnes des rois carton dorées |  | Boîtes pâtissières blanches 20 cm | Semelles dorées rondes 28 cm | changé |
| prd_0069 | Fèves des rois en porcelaine |  | Sachets viennoiserie papier | — | aucun remplaçant de même usage → demander |
| prd_0070 | Semelles dorées rondes 28 cm |  | Boîtes pâtissières blanches 20 cm | — | aucun remplaçant de même usage → demander |
| prd_0071 | Papier cuisson siliconé 40 × 60 |  | Sacs à baguette kraft imprimés | Sachets viennoiserie papier | changé |

## Diagnostic S45 : `place_order` écrit avant l'accord du client (Amine K.)

Rejeu du 24/11 (après `make reset`, tout allumé) : S44, S04, S05, S40 passent ; **S45 échoue sur `tools_none`** parce
qu'au premier tour l'agent appelle `place_order` en même temps que `product_insight` (règle d'ORDER_RULES : « dès que des
produits et des quantités sont dits, appelle place_order »). La réponse elle-même est juste (« … poudre d'amande
blanche … je vous la mets à la place ? »).

Vérifié sans modèle (appel direct de l'outil, ERP remis à zéro avant et après) : `place_order` **crée le brouillon même
quand le stock manque**, avec seulement une alerte :

| Client | Demande | `written` | Relecture | Alerte |
|---|---|---|---|---|
| cli_0021 | 3 cartons de tourage AOP, mercredi | true | 30 kilos de Beurre de tourage AOP… ; mercredi 25 novembre | en rupture |
| cli_0053 | 10 kg de poudre de noisette, vendredi | true | 10 kilos de Poudre de noisette torréfiée ; vendredi 27 novembre | il n'en reste que 2,57 kilos |

Même appel au premier tour de S05 (qui passe : ses contrôles ne l'interdisent pas). Proposition à Amine K. : si une
ligne dépasse le stock disponible, ne rien écrire et renvoyer `next` = « produit en quantité insuffisante : propose
d'abord avec product_insight ».

## Exclusions écrites dans les fiches (« jamais de… », « … uniquement »)

`card_rules` lit les préférences et les notes, phrase par phrase ; `rank_alternatives` retire ce que la fiche interdit
et `has_same_use_substitute` ne compte pas ces produits (s'il ne reste rien → « rien d'équivalent », l'agent demande).
Règle générale : une interdiction retire un produit dont le nom contient tous ses mots ; une obligation ne s'applique
que si le produit manquant contient son premier mot (sa famille), et garde seulement les produits qui contiennent les
mots qu'elle partage avec lui (pourcentages compris). Une phrase dont les mots ne sont dans aucun nom de produit
(« jamais de livraison ce jour-là », « … ne lit pas les mails de relance ») n'a aucun effet.

Liste vérifiée par Daycem (24/11), 29 fiches sur 104 :

| Phrase | Fiches | Effet |
|---|---|---|
| « Ne veut pas de surgelé » | 10 | aucun produit surgelé (baguette précuite, chocolatine, croissant, pain aux raisins, purée de framboise) |
| « jamais d'épaisse » | 7 | jamais la crème fraîche épaisse |
| « Crème 35 % uniquement » | 7 (les mêmes) | si la crème liquide 35 % manque : rien → l'agent demande |
| « Farine de tradition du Lauragais uniquement » | 8 | si la T55 tradition manque : rien (même pas le substitut des documents) → l'agent demande |
| « Couvertures exclusivement Cacaos Garonne » | 1 | si une couverture manque : seulement une autre couverture |
| « tourage AOP exclusivement » | 1 | si le tourage AOP manque : rien (ce client refuse déjà les remplacements) |
| « Ovoproduits liquides uniquement » | 3 | ignorée (voir limites) |
| « jamais de livraison ce jour-là » (notes) | 18 | aucun effet |

### Limites connues (non codées)
1. **Ovoproduits** (3 fiches : cuisine centrale, EHPAD, lycée) : « ovoproduit » n'apparaît dans aucun nom de produit,
   donc la règle est ignorée ; si un œuf liquide manque, les œufs en coquille peuvent encore être proposés (l'agent
   lit la fiche, mais rien ne le garantit). **Piste** : des synonymes tirés du glossaire de l'entreprise
   (`DATA_DIR/context`, comme `doc_substitutes`) : « ovoproduits » = œuf entier / jaune / blanc d'œuf liquides.
2. **Marque des couvertures** (1 fiche : « Couvertures exclusivement Cacaos Garonne, origine Équateur et Pérou ») :
   la marque n'est pas dans les noms, seule la famille « couverture » est vérifiée. **Piste** : vérifier le fournisseur
   du produit (`mainSupplierId` dans l'ERP) contre le nom du fournisseur cité par la fiche.

### Test direct de `product_insight` (24/11, sans modèle, après `make reset`)
Même demande, 1 500 L de crème liquide UHT 35 % (il en reste 1 320 L, il en manque 180), pour deux clients qui
acceptent les remplacements :

| Client | Fiche | Alternatives renvoyées | Note |
|---|---|---|---|
| Le Petit Four de Saint-Cyprien (cli_0053) | « Crème 35 % uniquement, jamais d'épaisse » | aucune | « Aucun produit en stock n'a le même usage. Annonce la rupture et demande au client ce qu'il souhaite, sans proposer de produit. » |
| Le Pétrin de Colomiers (cli_0021) | aucune exclusion | crème fraîche épaisse 30 %, œuf entier liquide, blanc d'œuf liquide, lait entier, jaune d'œuf liquide | — |

La crème épaisse, premier choix pour un client sans exclusion, n'est jamais proposée au client qui l'a exclue.
(Cas construit : dans l'ERP du 24/11, aucun produit réellement en rupture ne touche une fiche à exclusion ; le
scénario S46 utilise le cas réel le plus proche.)

## Bilingue : données anglaises (`SEED_DIR_NAME=seed_en`, 24/11)

Les mêmes fonctions lisent le français et l'anglais **sans réglage** (une fiche est dans l'une ou l'autre langue).
Audit sans modèle : ERP français (port 4000) contre un ERP anglais temporaire (port 4001, base à part), même code.

| Audit | Français | Anglais avant | Anglais après |
|---|---|---|---|
| Décision de remplacement, tourage AOP (104 fiches) | refuse 37 · accepte 52 · demander 6 · inconnu 9 | inconnu 104 | refuse 37 · accepte 51 · demander 7 · inconnu 9 |
| Premiers choix du classement (71 produits) | — | 61 / 71 comme le français | **71 / 71** |
| « Aucun remplaçant de même usage » | 23 | 25 | 23 (les mêmes) |
| Fiches où une exclusion est lue | 39 | 0 | 41 |

**Le français n'a pas bougé** : code de `main` contre code bilingue, sur les 104 fiches × 71 produits (préférences et
notes) : 7 384 / 7 384 décisions identiques, 7 384 / 7 384 classements identiques (ordre et exclusions).

Comment :
- `substitution_policy` : tournures anglaises réelles (« Accepts equivalent substitutions if informed », « Equivalent
  substitutions accepted if we are told », « Refuses substitutions », « Substitutions refused », « Never any
  substitution on the butter », « Does not want any substitution without being told »).
- `card_rules` : « never X », « does not want X », « no X », « X only », « only X », « exclusively X » ; mots
  génériques anglais ignorés (goods, products, from, the…).
- Noms de produits : en anglais le produit est **le dernier mot** (« UHT liquid cream »), en français le premier ;
  `name_match` compare les noms anglais **via leur original français** (`data/seed_en/GLOSSARY.md`), d'où les mêmes
  premiers choix. Un nom anglais hors glossaire utilise le dernier mot.
- `doc_substitutes` : lu par identifiant, marche dans les deux langues (testé avec une ligne anglaise).

Écarts restants (aucun refus lu comme un accord, ni l'inverse) :
1. **« demander » au lieu de « accepte »** sur 39 couples fiche × produit sur 7 384 (dont cli_0007 pour le tourage
   AOP : « standard laminating butter » partage deux mots avec « AOP … laminating butter », un seul en français
   « tourage standard »). Côté prudent : l'agent demande avant de nommer un remplaçant. Une correction (ne pas compter
   le mot de famille) faisait bouger 11 décisions françaises : abandonnée.
2. **Exclusions** (32 couples, 11 fiches) :
   - « Liquid egg products only » (3 fiches) **est lue en anglais** (le mot « egg » est dans les noms) : si un œuf
     liquide manque, plus d'œufs en coquille ni de crème. En français, « ovoproduits » reste ignoré (limite 1).
   - « 35% cream only » (7 fiches) ne s'applique pas quand la crème fraîche épaisse ou la préparation pour crème
     pâtissière manque : leurs noms anglais gardent « crème », pas « cream ». La règle française allait plus loin
     (seulement des produits « crème »), sans effet utile en pratique.
   - Sarrailh (« exclusively AOP butter for laminating ») : la règle anglaise touche aussi le beurre doux AOP. Sans
     effet en pratique : ce client refuse les remplacements, `product_insight` ne propose rien.
3. **Le prompt reste en français** : `SALES_RULES_EN` est prête (mêmes règles, exemples sans nom réel, test « stay
   general » anglais) mais **pas branchée**, en attendant le réglage de langue commun à l'équipe.
