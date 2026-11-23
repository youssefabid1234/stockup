# ERP.md — le guide de l'ERP du kit

Ce fichier explique l'ERP du kit : ce qu'il couvre, comment il marche, comment s'en servir (écran et API).
Tout ce qui est écrit ici est vérifié dans le code. En cas de doute, le code fait foi :
`apps/backend/app/services/` (règles métier), `apps/backend/app/schemas/domain.py` (modèle de données).

Les autres docs, à ne pas confondre :

| Doc | Pour quoi |
|---|---|
| [BRIEF.md](BRIEF.md) | le défi, les livrables, le jury |
| [METIER.md](METIER.md) | le métier de grossiste alimentaire et son vocabulaire |
| [SETUP.md](SETUP.md) | installation pas à pas |
| [README.md](README.md) | architecture, configuration, commandes |
| [AGENTS.md](AGENTS.md) | règles pour les agents de code |
| [apps/ai/README.md](apps/ai/README.md) | boucle agent, outils, fournisseurs LLM/STT/TTS, protocole WebSocket voix |

---

## 1. Ce que couvre l'ERP

Un grossiste (marée, fruits et légumes, crèmerie, épicerie) vend à des restaurants, poissonneries, cantines…
et achète à des fournisseurs. L'ERP suit tout le flux, de la commande au paiement.

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

Trois briques :

| Brique | Où | Port |
|---|---|---|
| API ERP (FastAPI + SQLite) | `apps/backend` | 4000 (`/docs`, `/openapi.json`) |
| Service IA (agent, chat, voix) | `apps/ai` | 4100 |
| Web (React) | `apps/web` | 5173 (proxy `/api` → 4000, `/ai` → 4100) |

Raccourcis globaux du web : `⌘K` recherche et « Aller à », `⌘J` assistant IA, `⌥ Espace` (maintenu) commande vocale,
`⌘B` ou `⌘\` barre latérale.

---

## 2. Les pages (ordre du menu)

Chaque page lit l'API ERP. Les filtres sont dans l'URL (on peut partager un lien filtré).

### Accueil — `/`
- **Montre** : CA du jour, CA du mois, commandes du jour, pré-commandes à traiter, à livrer aujourd'hui, impayés en
  retard ; CA des 30 derniers jours ; top 10 clients sur 30 j ; stock bas ; DLC proches ; activité en direct.
- **Actions** : « Nouvelle commande » ; chaque ligne mène à son objet.
- **API** : `GET /api/dashboard`, `GET /api/events/stream`.

### Commandes — `/orders`
- **Montre** : les commandes de vente (n°, client, date de livraison, lignes, total, statut), totaux en pied.
- **Filtres** : onglets de statut (Toutes, Pré-commandes, Confirmées, Préparées, Livrées, Facturées, Annulées) avec
  compteurs ; recherche n° / client ; date de livraison (Hier, Aujourd'hui, Demain, ou une date) ; canal ;
  `?clientId=` filtre par client.
- **Actions** : « Nouvelle commande » → choix du client → brouillon vide → page de la commande.
- **API** : `GET /api/orders`, `POST /api/orders`.

### Commande — `/orders/:id`
- **Montre** : bandeau (client, date, total HT, total TTC, création), alertes, lignes éditables, note ; colonne de
  droite : client, panier habituel, facture, tournée.
- **Lignes** : quantité, prix, note modifiables en ligne ; stock disponible par ligne ; icône ⓘ sur le prix =
  d'où vient ce prix (Négocié / Règle « … » / Catalogue) ; bouton « Alternatives » = produits de remplacement.
  Après préparation, la colonne « préparé » reçoit les poids réels.
- **Actions** : Confirmer → Préparer → Livrer → Facturer ; Annuler (deux clics) ; « Voir la facture ».
- **API** : `GET /api/orders/{id}`, `PATCH /api/orders/{id}`, `POST|PATCH|DELETE /api/orders/{id}/lines…`,
  `POST /api/orders/{id}/confirm|prepare|deliver|invoice|cancel`, `GET /api/products/{id}/alternatives`,
  `GET /api/prices/resolve`, `GET /api/clients/{id}/usual`.

### Clients — `/clients`
- **Montre** : nom, type, groupes, zone, commercial, encours, en retard, dernière commande, statut.
- **Filtres** : recherche (nom, code, ville, contact), type, zone, groupe.
- **Actions** : « Nouveau client » (panneau latéral ; créé en statut `prospect`).
- **API** : `GET /api/clients`, `POST /api/clients`.

### Client — `/clients/:id`
- **Onglets** : Vue d'ensemble · Historique · Contexte.
- **Vue d'ensemble** : KPI (encours, en retard, plafond de crédit, CA 30 j, dernière commande), commandes récentes,
  factures ouvertes, panier habituel, prix négociés, informations, contacts, notes CRM, historique récent, groupes.
- **Actions** : Bloquer / Débloquer, ajouter une note, nouvel événement, nouvelle fiche de contexte.
- **API** : `GET /api/clients/{id}`, `PATCH /api/clients/{id}`, `POST /api/clients/{id}/notes`,
  `GET|POST /api/clients/{id}/events`, `GET /api/context/for?entityType=client&id=…`.

### Prix — `/prices`
Quatre onglets :
- **Matrice** : produits × groupes de clients (ou jusqu'à 8 clients choisis). Chaque case = prix résolu ; un clic
  ouvre le détail et permet de créer une règle ou un prix négocié. `GET /api/prices/grid`.
- **Règles** : liste des règles de prix, création / édition dans un panneau avec aperçu, suppression.
  `GET|POST|PATCH|DELETE /api/price-rules`.
- **Prix négociés** : tous les prix client × produit, édition en ligne, ajout, suppression.
  `PUT|DELETE /api/clients/{id}/prices/{productId}`.
- **Simulateur** : client + produit + quantité (+ date) → prix retenu, tous les candidats et pourquoi chacun a été
  appliqué ou non. `GET /api/prices/resolve`.

### Historique — `/history`
- **Montre** : tous les événements clients et fournisseurs de l'entreprise, plus récents d'abord.
- **Filtres** : onglets Clients / Fournisseurs ; famille (Réclamations & qualité, Retours & avoirs, Paiements,
  Commercial, Relation, Notes) ; statut ; du / au ; recherche plein texte.
- **Actions** : « Marquer résolu » en ligne ; lien vers le client / fournisseur.
- **API** : `GET /api/client-events`, `GET /api/supplier-events`, `PATCH /api/client-events/{id}`,
  `PATCH /api/supplier-events/{id}`.

### Produits — `/products` et `/products/:id`
- **Liste** : onglets par catégorie ; recherche nom / SKU / appellation (alias) ; groupe. Prix, coût, marge, stock,
  prochaine DLC. `GET /api/products?q=…&category=…&tag=…` (le filtre texte s'appelle `q`, pas `search`).
- **Fiche** : KPI, lots en FEFO, prix des fournisseurs comparés, mouvements récents, ventes 30 j, contexte ;
  « Ajuster le stock » (panneau). `GET /api/products/{id}`, `POST /api/stock/adjust`, `PATCH /api/products/{id}`.

### Stocks — `/stock`
- **Montre** : chaque produit : physique, réservé, disponible, entrant, prochaine DLC, état.
- **Onglets** : Tout · Rupture (disponible ≤ 0) · Stock bas (règle du tableau de bord, voir §3.3) · DLC proche
  (prochaine DLC dans 2 jours ou moins).
- **Actions** : clic sur une ligne → panneau avec les lots et l'ajustement.
- **API** : `GET /api/stock`, `GET /api/stock/movements`, `POST /api/stock/adjust`.

### Achats — `/purchase-orders` et `/purchase-orders/:id`
- **Liste** : onglets Toutes, Brouillons, Envoyées, Partielles, Reçues, Annulées ; recherche ; date attendue ;
  fournisseur (`?supplierId=`). « Nouvelle commande d'achat » → choix du fournisseur → brouillon vide.
- **Fiche** : lignes éditables (en brouillon), écart avec le prix habituel du fournisseur, alertes, date attendue,
  note, lots reçus ; actions Envoyer, Réceptionner (mode réception ligne par ligne, réception partielle possible),
  Annuler.
- **API** : `GET|POST /api/purchase-orders`, `GET|PATCH /api/purchase-orders/{id}`, lignes,
  `POST /api/purchase-orders/{id}/send|receive|cancel`, `GET /api/suppliers/{id}/usual`.

### Fournisseurs — `/suppliers` et `/suppliers/:id`
- **Liste** : nom, ville, catégories, délai, conditions, minimum de commande. Filtres : recherche, catégorie, groupe.
- **Fiche** (onglets Vue d'ensemble · Historique · Contexte) : infos, contacts, tarif fournisseur, commandes
  d'achat ; « Commander » crée un brouillon d'achat pour ce fournisseur.
- **API** : `GET /api/suppliers`, `GET|PATCH /api/suppliers/{id}`, `GET|POST /api/suppliers/{id}/events`.

### Encours — `/receivables`
- **Montre** : balance âgée par client au jour métier ; KPI (encours, échu, DSO, clients en retard) ; barre empilée
  par tranche (clic = filtre).
- **Filtres** : recherche, groupe, commercial, zone, « En retard uniquement ».
- **Panneau client** (clic sur une ligne) : factures ouvertes, paiements, litiges ouverts, dernières relances ;
  actions Enregistrer un paiement, Enregistrer la relance (crée un événement `late_payment`), Bloquer / Débloquer,
  Fiche client.
- **API** : `GET /api/receivables`, `POST /api/payments`, `POST /api/clients/{id}/events`, `PATCH /api/clients/{id}`.

### Factures — `/invoices` et `/invoices/:id`
- **Liste** : onglets À payer, En retard, Payées, Toutes ; recherche n° / client ; totaux.
- **Fiche** : la facture en document (lignes avec TVA, totaux), statut, échéance, commandes liées, paiements
  affectés, « Enregistrer un paiement ».
- **API** : `GET /api/invoices`, `GET /api/invoices/{id}`, `POST /api/payments`.

### Paiements — `/payments`
- **Montre** : les paiements reçus. Filtres : recherche (client, référence, facture), mode de paiement.
- **Actions** : enregistrer un paiement, avec affectation manuelle ou automatique (plus anciennes factures d'abord).
- **API** : `GET /api/payments`, `POST /api/payments`.

### Tournées — `/routes`
- **Onglets** : Tournées du jour · Définitions.
- **Tournées du jour** : date (Aujourd'hui, Demain, Autre) ; une carte par tournée avec arrêts, ETA, poids ;
  flèches Monter / Descendre pour réordonner ; « Planifier ».
- **API** : `GET /api/routes`, `GET /api/route-runs?date=`, `POST /api/route-runs/plan`,
  `PATCH /api/route-runs/{id}/stops`.

### Assistant — `⌘J` (pas une page)
Panneau de chat à droite. Voir §6.

### Voix — `/voice`
Deux modes (en-tête, `?mode=command`) : Appel et Commande. Voir §6.

### Contexte — `/context`
- **Montre** : toutes les fiches de contexte. Onglets : Toutes, Entreprise, Clients, Fournisseurs, Produits, Rayons.
- **Filtres** : recherche, genre (`kind`), source, entité.
- **Actions** : clic = panneau d'édition (sauvegarde auto) ; « Nouvelle fiche ». Fiches écrites par l'IA en violet.
- **API** : `GET|POST /api/context`, `GET|PATCH|DELETE /api/context/{id}`.

### Activité — `/activity`
- **Montre** : le journal de toutes les écritures, en direct. Onglets Tout · IA & voix · Équipe ; filtre par objet.
- **API** : `GET /api/events`, `GET /api/events/stream`.

### Groupes — `/groups`
- **Montre** : trois colonnes (clients, produits, fournisseurs) ; nombre de membres par groupe.
- **Actions** : créer un groupe ; clic = éditer, ajouter / retirer des membres.
- **API** : `GET|POST /api/tags`, `PATCH|DELETE /api/tags/{scope}/{id}`, `PATCH /api/clients|products|suppliers/{id}`
  avec `{tags}`.

---

## 3. Cycles de vie et règles métier

Les erreurs ont toujours la forme `{"error": {"code", "message"}}`. Une transition interdite renvoie
`409 invalid_transition`. Les alertes (`warnings`) ne bloquent jamais : elles sont recalculées à chaque lecture.

### 3.1 Commandes de vente

```
draft ──confirm──▶ confirmed ──prepare──▶ prepared ──deliver──▶ delivered ──invoice──▶ invoiced
  │                    │   └────────────deliver────────────────▲
  └──────cancel────────┴──────────cancel──────────┘ (depuis draft, confirmed, prepared)
```

| Action | Depuis | Effet |
|---|---|---|
| `POST /api/orders` | — | Crée en `draft`. Prix de chaque ligne résolu (§3.4). `deliveryDate` par défaut = prochain jour de livraison du client strictement après aujourd'hui (demain s'il n'en a pas). `source` par défaut = `voice_agent` si l'acteur est `voice_agent`, sinon `manual`. |
| `PATCH /api/orders/{id}` | `draft`, `confirmed` | Date de livraison, note. Une commande confirmée qui change de date change de tournée. |
| Ajouter / retirer une ligne | `draft`, `confirmed` | Retirer la dernière ligne d'une commande confirmée : `409 empty_order` (annulez plutôt). |
| Modifier une ligne | `draft`, `confirmed` ; en `prepared` seulement `preparedQty` et `note` | Changer `productId` recalcule le prix. |
| `confirm` | `draft` | Exige ≥ 1 ligne (`409 empty_order`). Réserve le stock (calculé, voir §3.3). Pose la commande sur la tournée de la zone du client à la date de livraison. |
| `prepare` | `confirmed` | Saisit les poids réels (`preparedQty`) ; une ligne non listée = préparée comme commandée. Le total suit les poids réels. |
| `deliver` | `confirmed`, `prepared` | Sort le stock des lots en FEFO (mouvements `sale`). Si le stock physique manque, la livraison passe quand même et le journal le signale. L'arrêt de tournée passe `delivered`. |
| `invoice` | `delivered` | Crée une facture (`issued`) et passe la commande en `invoiced`. |
| `cancel` | `draft`, `confirmed`, `prepared` | La réservation disparaît ; l'arrêt quitte sa tournée. |

Une ligne : `productId`, `qty`, `unitPrice` (€ HT), `preparedQty`, `note` (« bien frais »), `substituteFor` (produit
remplacé). La quantité qui compte (stock, total, facture) = `preparedQty` si connue, sinon `qty`.

**Alertes de commande** (seulement en `draft`, `confirmed`, `prepared`) :

| Code | Déclencheur |
|---|---|
| `client_blocked` | le client a le statut `blocked` |
| `credit_limit` | `creditLimit` > 0 et encours TTC + TTC de cette commande > `creditLimit` |
| `no_route` | aucune tournée de la zone du client ne roule ce jour de semaine |
| `insufficient_stock` | disponible (sans compter la réservation de cette commande) < quantité demandée du produit |
| `expiring_soon` | le premier lot FEFO du produit expire au plus tard le lendemain de la livraison |
| `price_below_cost` | prix de la ligne < coût de référence du produit |

### 3.2 Commandes d'achat et réceptions

```
draft ──send──▶ sent ──receive──▶ partially_received ──receive──▶ received
draft | sent | partially_received ──cancel──▶ cancelled   (les lots déjà reçus restent en stock)
```

- Création en `draft` ; lignes facultatives. Prix par défaut = tarif du fournisseur (`SupplierPrice`), sinon coût
  de référence du produit. `expectedDate` par défaut = aujourd'hui + `leadTimeDays` du fournisseur.
- Lignes modifiables en `draft` seulement ; `expectedDate` et `note` en `draft` ou `sent`.
- `send` exige ≥ 1 ligne (`409 empty_order`).
- `receive` (depuis `sent` ou `partially_received`) : `receivedQty` = quantité reçue **maintenant**, ajoutée au déjà
  reçu. Sans corps : tout le reste à recevoir. Chaque ligne reçue crée **un lot** : `receivedAt` = aujourd'hui,
  `expiresAt` = aujourd'hui + `shelfLifeDays` du produit, plus un mouvement `receipt`. Statut `received` si toutes les
  lignes sont complètes, sinon `partially_received`. Rien reçu : `400 nothing_received`.

**Alertes d'achat** (seulement en `draft`, `sent`) :

| Code | Déclencheur |
|---|---|
| `below_min_order` | total HT < `minOrderAmount` du fournisseur |
| `not_in_supplier_catalog` | le produit n'a pas de prix chez ce fournisseur |
| `price_above_usual` | prix de la ligne > 110 % du prix habituel du fournisseur |

### 3.3 Stock

Le stock est fait de **lots** (`Lot`). Un lot = une entrée d'un produit, avec une DLC (`expiresAt`).

| Grandeur | Calcul |
|---|---|
| `onHand` (physique) | Σ `qtyRemaining` des lots |
| `reserved` (réservé) | Σ quantités des lignes des commandes `confirmed` et `prepared` |
| `available` (disponible) | `onHand` − `reserved` |
| `incoming` (entrant) | Σ (`qty` − `receivedQty`) des achats `sent` et `partially_received` |
| `nextExpiry` | DLC du premier lot encore en stock |

- La réservation n'est pas stockée : elle découle du statut des commandes. Annuler ou livrer la libère.
- **FEFO** (premier expiré, premier sorti) : on sort d'abord le lot qui expire le plus tôt (puis le plus ancien reçu).
- **Ajustement** (`POST /api/stock/adjust`, `reason` = `adjustment` ou `waste`) : `qty` > 0 crée un nouveau lot
  (DLC = aujourd'hui + durée de vie) ; `qty` < 0 sort en FEFO. `waste` (perte) sort toujours, quel que soit le
  signe envoyé.
- Mouvements (`StockMovement.reason`) : `receipt`, `sale`, `adjustment`, `waste`, `return`.
- **Stock bas** (tableau de bord) : disponible ≤ 0, ou disponible < 2 jours de ventes moyennes (moyenne sur 14 jours).
- **DLC proches** (tableau de bord) : lots en stock qui expirent dans 2 jours ou moins (déjà expirés compris).
- **Alternatives** (`GET /api/products/{id}/alternatives`) : même catégorie, actif, disponible > 0, prix le plus
  proche d'abord, 10 maximum.

### 3.4 Prix : qui gagne

Ordre de résolution (`apps/backend/app/services/pricing.py`) :

1. **Prix négocié** (`ClientPrice`, client × produit) : gagne toujours.
2. **Règle de prix** (`PriceRule`) : la plus spécifique applicable gagne. Spécificité, de la plus forte à la plus
   faible :
   client + produit > client + groupe/catégorie > client + tous produits > groupe de clients + produit >
   groupe de clients + groupe/catégorie > groupe de clients + tous produits > tous clients + produit >
   tous clients + groupe/catégorie > tous clients + tous produits.
   À égalité : `priority` la plus haute, puis la plus récente.
   Une règle s'applique si `active`, si la date est dans `validFrom`…`validTo`, et si quantité ≥ `minQty`.
3. **Prix catalogue** (`Product.price`).

Méthodes d'une règle : `fixed` (prix fixe), `discount_pct` (% de remise sur le prix catalogue, entre 0 et 100),
`markup_pct` (% de marge sur le coût).

**Voir pourquoi un prix a été choisi** : `GET /api/prices/resolve?clientId=…&productId=…&qty=…[&date=…]` renvoie
`price`, `source` (`client_price` | `rule` | `list`), `ruleId`, `marginPct`, `explanation` (phrase en français) et
`candidates` : chaque prix possible, `applied`, et `reason` quand il n'a pas été retenu (« règle inactive »,
« à partir de 10 unités », « le prix négocié du client prime »…). Dans le web : l'icône ⓘ sur une ligne de commande,
ou Prix → Simulateur.

Le prix d'une ligne est figé à sa création. Changer une règle ne modifie pas les commandes existantes.

### 3.5 Crédit, clients bloqués, risque d'encours

- `Client.status` : `active`, `blocked`, `prospect`. On bloque à la main (`PATCH /api/clients/{id}` avec
  `{"status": "blocked"}`, bouton Bloquer). Un client bloqué **peut** encore commander : l'ERP ajoute l'alerte
  `client_blocked`. C'est à l'agent de décider quoi dire.
- `creditLimit` : encours TTC autorisé. `0` = pas de contrôle.
- **Encours** (`outstanding`) = Σ (`totalTtc` − `amountPaid`) des factures ouvertes. **Échu** (`overdue`) = la part
  dont l'échéance est passée.
- **Tranches** de la balance âgée (jours après échéance) : `current` (pas échu), `d1_30`, `d31_60`, `d61_90`, `d90plus`.
- **Risque** (`GET /api/receivables`, champ `risk`) :

| Niveau | Si au moins une condition |
|---|---|
| `high` (Élevé) | client `blocked` ; encours > `creditLimit` (si > 0) ; plus de 60 jours de retard ; délai moyen de paiement > 60 j **et** quelque chose d'échu |
| `watch` (À surveiller) | encours > 80 % du plafond ; plus de 30 jours de retard ; un événement `late_payment` **ouvert** ; délai moyen de paiement > 45 j |
| `ok` | sinon |

- `avgDaysToPay` : factures payées dont le dernier paiement date de moins de 90 jours (date du dernier paiement −
  date d'émission).
- **DSO** = encours / CA TTC facturé sur 90 jours × 90.
- Seuls les clients avec au moins une facture ouverte apparaissent dans `/api/receivables`.

### 3.6 Factures, paiements, affectation

- Une facture naît d'une commande livrée (`POST /api/orders/{id}/invoice`). Lignes = quantités préparées, TVA par
  produit (`vatRate`, 0,055 pour l'alimentaire). `issuedAt` = aujourd'hui ; `dueDate` = aujourd'hui +
  `paymentTermsDays` du client (0 = comptant).
- Statuts stockés : `issued`, `partially_paid`, `paid` (et `draft`, `cancelled`). `overdue` n'est **jamais stocké** :
  il est calculé à la lecture (facture ouverte dont `dueDate` < aujourd'hui).
- `GET /api/invoices?status=open` : pseudo-statut = toutes les factures avec un solde.
- **Paiement** (`POST /api/payments`) : montant TTC, `method` (`transfer`, `card`, `cheque`, `cash`,
  `direct_debit`).
  - Sans `allocations` : affecté aux factures ouvertes **les plus anciennes d'abord** ; l'excédent reste non affecté.
  - Avec `allocations` : chaque facture doit être à ce client (`400 wrong_client`), chaque montant ≤ solde de la
    facture, la somme ≤ montant du paiement (`400 over_allocated`).
  - Le statut de la facture suit : `paid` si solde ≤ 0, sinon `partially_paid`.

### 3.7 Tournées

- Une **tournée** (`Route`) dessert une `zone` certains jours (`days`), avec une heure de départ et une capacité.
- Un **passage** (`RouteRun`, `run_…`) = une tournée à une date. Statut `planned` → `in_progress` (un arrêt livré) →
  `done` (plus d'arrêt en attente).
- Confirmer une commande la pose sur le passage de la zone du client à sa date (créé au besoin). S'il n'y a pas de
  tournée ce jour-là, l'ERP prend quand même une tournée de la zone (et la commande porte l'alerte `no_route`).
- `POST /api/route-runs/plan {date}` : pose toutes les commandes `confirmed` / `prepared` de la date, ajoute les
  nouvelles triées par ville puis nom, retire les arrêts annulés ou déplacés.
- `PATCH /api/route-runs/{id}/stops {orderIds}` : ces commandes d'abord, dans cet ordre ; les autres suivent.
- ETA d'un arrêt = heure de départ + 12 min × rang. Poids : une `box` ≈ 5 kg, toute autre unité ≈ 1 kg.

### 3.8 Historique client et fournisseur

Le long terme de la relation : réclamations, retours, litiges, appels, visites, négociations…

- **Types client** (`ClientEventType`) : `onboarding`, `call`, `visit`, `complaint`, `quality_issue`, `delivery_issue`,
  `return`, `credit_note`, `dispute`, `late_payment`, `payment_plan`, `price_negotiation`, `special_request`,
  `menu_change`, `contact_change`, `compliment`, `churn_risk`, `won_back`, `note`.
- **Types fournisseur** (`SupplierEventType`) : `onboarding`, `call`, `visit`, `quality_issue`, `delivery_issue`,
  `shortage`, `return`, `credit_note`, `dispute`, `price_change`, `price_negotiation`, `invoice_issue`, `payment`,
  `contract`, `certification`, `contact_change`, `compliment`, `note`.
- **Statut** (`open` | `resolved`) : les types « problème » sont créés `open` automatiquement.
  Client : `complaint`, `quality_issue`, `delivery_issue`, `return`, `dispute`, `late_payment`, `churn_risk`.
  Fournisseur : `quality_issue`, `delivery_issue`, `shortage`, `return`, `dispute`, `invoice_issue`.
  Les autres n'ont pas de statut. Passer à `resolved` remplit `resolvedAt` ; repasser à `open` l'efface.
- **Gravité** (`severity`) : `low`, `medium`, `high`.
- **Canal** (`channel`) : `phone`, `email`, `whatsapp`, `visit`, `voice_agent`, `sms`, `other`. Par défaut
  `voice_agent` quand l'acteur est l'agent vocal. Auteur par défaut : le nom de l'acteur, sinon « Équipe »,
  « Assistant IA », « Agent vocal ».
- Liens facultatifs : `orderId`, `invoiceId` (doivent être à ce client), `productIds`, `amount` (€), `tags`.
- `at` : par défaut maintenant ; une date seule = 09:00.
- Stats de la fiche client (`eventStats`) : total, ouverts, réclamations sur 12 mois (`complaint`, `quality_issue`,
  `delivery_issue`), retours sur 12 mois.

### 3.9 Groupes (tags)

- Un groupe (`TagDef`) a un `id` (slug, unique par `scope`), un `scope` (`client`, `supplier`, `product`), un `label`,
  une couleur et une description.
- Les entités portent les ids de groupes dans leur champ `tags`. Un tag non défini est refusé (`400 unknown_tag`).
- Les règles de prix ciblent un groupe de clients et / ou un groupe de produits.
- Supprimer un groupe le retire de toutes les entités ; les règles qui le visent ne s'appliquent plus.

### 3.10 La table de contexte

Ce que les agents doivent savoir, en fiches courtes et modifiables.

- Une fiche (`ContextEntry`, `ctx_…`) est rattachée par `entityType` + `entityId` :
  - `company` : pas d'`entityId` ;
  - `client`, `supplier`, `product` : un id existant (`cli_…`, `sup_…`, `prd_…`) ;
  - `category` : l'id d'une catégorie produit de votre entreprise (liste propre à chaque entreprise :
    `GET /api/categories` → `[{id, label}]`).
- **Genres** (`kind`) : `policy` (règle), `procedure` (comment faire / dire), `preference` (ce qu'ils aiment),
  `fact` (contexte), `relationship` (les personnes), `pricing` (accords), `logistics` (livraison, stockage),
  `risk` (irritants, crédit, risque de départ).
- **Source** (`source`) : `seed` (pack de données), `user` (web), `ai_chat`, `voice_agent`. Fixée par l'en-tête
  `x-actor` à l'écriture.
- Recherche : `GET /api/context?q=…` plein texte insensible aux accents, classé par pertinence (titre > tags et entité > corps).
  Filtres `entityType`, `entityId`, `kind`, `source`, `tag` ; `limit` (défaut 100).
- **`GET /api/context/for?entityType=client&id=cli_0010`** : tout ce qu'il faut charger avant de parler d'une
  entité. `entries` = ses fiches ; `related` = fiches liées (produit → sa catégorie ; fournisseur → ses catégories ;
  toute entité → les fiches `company` ou `category` dont le texte cite son id).
- En plus de la table, l'agent lit à chaque tour les fichiers `DATA_DIR/context/*.md` (voir
  `apps/ai/app/agent/prompts.py`).

---

## 4. Modèle de données

Ids préfixés, montants en euros HT sauf `*Ttc`, dates `YYYY-MM-DD`, horodatages ISO complets. JSON en camelCase.
Source : `apps/backend/app/schemas/domain.py`.

| Entité | Id | Champs clés |
|---|---|---|
| `Client` | `cli_0010` (code `C0010`) | `name`, `type`, `contacts`, `zone`, `deliveryDays`, `paymentTermsDays`, `creditLimit`, `status`, `salesRep`, `preferences`, `notes`, `tags` |
| `Product` | `prd_0015` | `sku`, `name`, `aliases` (ce que les gens disent : « loup »), `category`, `unit` (`kg`, `piece`, `box`, `dozen`, `liter`), `price`, `cost`, `vatRate`, `shelfLifeDays`, `mainSupplierId`, `active`, `tags` |
| `Supplier` | `sup_0001` | `name`, `categories`, `leadTimeDays`, `paymentTermsDays`, `minOrderAmount`, `notes`, `tags` |
| `ClientPrice` | clé client × produit | `clientId`, `productId`, `price` |
| `SupplierPrice` | clé fournisseur × produit | `supplierId`, `productId`, `price`, `updatedAt` |
| `PriceRule` | `prl_0001` | `name`, `active`, `priority`, `clientScope`, `productScope`, `method`, `minQty`, `validFrom`, `validTo` |
| `Order` | `ord_002063`, n° `CMD-2026-016935` | `clientId`, `status`, `source`, `deliveryDate`, `routeRunId`, `totalHt`, `lines[]`, `invoiceId`, `createdBy` |
| `OrderLine` | `lin_…` | `productId`, `qty`, `unitPrice`, `preparedQty`, `note`, `substituteFor` |
| `PurchaseOrder` | `po_000697`, n° `ACH-2026-003650` | `supplierId`, `status`, `expectedDate`, `totalHt`, `lines[]` (`pol_…` : `qty`, `unitPrice`, `receivedQty`) |
| `Lot` | `lot_003273` | `productId`, `supplierId`, `purchaseOrderId`, `qtyReceived`, `qtyRemaining`, `receivedAt`, `expiresAt` |
| `StockMovement` | `mov_015840` | `productId`, `lotId`, `qty` (+ entrée, − sortie), `reason`, `refType`, `refId`, `note` |
| `Invoice` | `inv_001630`, n° `FAC-2026-011440` | `clientId`, `orderIds`, `status`, `issuedAt`, `dueDate`, `lines`, `totalHt`, `totalVat`, `totalTtc`, `amountPaid` |
| `Payment` | `pay_000545` | `clientId`, `amount` (TTC), `method`, `receivedAt`, `reference`, `allocations[]` (`invoiceId`, `amount`) |
| `Route` | `rte_0001` | `name`, `zone`, `driver`, `vehicle`, `capacityKg`, `days`, `departureTime` |
| `RouteRun` | `run_000075` | `routeId`, `date`, `status`, `stops[]` (`orderId`, `clientId`, `seq`, `eta`, `status`) |
| `ClientEvent` | `cev_002017` | `clientId`, `at`, `type`, `title`, `description`, `channel`, `author`, `severity`, `status`, `resolution`, `orderId`, `invoiceId`, `productIds`, `amount` |
| `SupplierEvent` | `sev_000500` | idem, avec `supplierId` et `purchaseOrderId` |
| `TagDef` | slug (`gastro`, `premium`) | `scope`, `label`, `color`, `description` |
| `ContextEntry` | `ctx_0001` | `entityType`, `entityId`, `kind`, `title`, `body` (markdown court), `tags`, `source` |
| `ActivityEvent` | `evt_0000029` | `at`, `actor`, `actorName`, `type`, `entity`, `entityId`, `summary` |

Numéros de documents : `CMD-<année>-<6 chiffres>` (vente), `ACH-…` (achat), `FAC-…` (facture). Les ids des
nouvelles lignes (`lin_…`, `pol_…`) sont aléatoires ; tous les autres ids continuent la séquence.

---

## 5. L'horloge métier et le flux d'activité

### L'horloge : `meta.today`
- Les données sont ancrées sur une date fixe : `GET /api/meta` → `{company, today, currency, generatedAt, trade, region}`
  (`trade` et `region` : le métier et la zone, affichés dans la barre latérale).
- « Aujourd'hui », « demain », « en retard », « échu », « 30 derniers jours » se calculent **toujours** sur
  `meta.today`, jamais sur la vraie date.
- Les nouveaux enregistrements ont la date `meta.today` et l'heure réelle de l'horloge murale.
- L'agent reçoit cette date dans son prompt système (« Aujourd'hui : mardi 24 novembre 2026 »).

### Le flux d'activité
- Chaque écriture ajoute un `ActivityEvent` (`type` comme `order.confirmed`, `payment.recorded`,
  `client_event.created`, `context.created`…) avec une phrase `summary` en français.
- **Qui écrit** : en-tête `x-actor` = `user` | `ai_chat` | `voice_agent` (valeur inconnue ou absente = `user`), plus
  `x-actor-name` facultatif (nom affiché, encodé URI). Le web envoie `user` / « Moi ». Les outils de l'agent envoient
  `ai_chat` (chat) ou `voice_agent` (voix, commande vocale).
- **En direct** : `GET /api/events/stream` (Server-Sent Events) envoie `ready` une fois, puis un événement `activity`
  par écriture validée, et `ping` toutes les 15 s. `GET /api/events?limit=50` = l'historique, plus récent d'abord.
- **Violet** : dans le web, tout ce qui vient de `ai_chat` ou `voice_agent` est teinté violet (Activité, Accueil,
  colonne de droite de la page Voix, fiches de contexte écrites par l'IA, appels d'outils dans l'assistant).
- `make reset` vide le journal.

---

## 6. Le côté IA de l'ERP

### Les trois surfaces

| Surface | Comment | Ce qu'elle fait | Route IA |
|---|---|---|---|
| **Assistant** | `⌘J`, panneau de droite sur toutes les pages | Chat texte avec l'agent (mode `chat`, markdown léger). Les appels d'outils s'affichent en lignes violettes avec lien vers l'objet. | `POST /ai/chat` (SSE) |
| **Voix · Appel** | page `/voice` | Simulation d'appel téléphonique : maintenez Espace (ou le gros bouton) pour parler en tant que client, relâchez ; l'agent répond en texte et en audio (mode `voice` : 1–2 phrases, pas d'ids, nombres arrondis). Chronologie à deux pistes, latences par tour, écritures de l'agent en direct à droite. | `WS /ai/voice` |
| **Voix · Commande** | page `/voice?mode=command`, ou `⌥ Espace` maintenu sur n'importe quelle page (HUD), ou bouton « Voix » de l'en-tête | Un commercial pilote l'ERP à la voix, une phrase à la fois, sans historique (mode `command` : agit tout de suite, répond en une phrase). Si la phrase demande de *voir* (« montre », « ouvre », « affiche »…), le web navigue vers la page de l'objet. Un clic court sur le bouton ouvre le HUD pour taper la commande. | `POST /ai/command[?speak=1]` (SSE) |

Le prompt système (`apps/ai/app/agent/prompts.py`) = règles de base + règles du mode + entreprise et date du jour +
nom de l'interlocuteur + tous les fichiers `DATA_DIR/context/*.md`. Protocoles détaillés : [apps/ai/README.md](apps/ai/README.md).

### Les outils de l'agent

16 outils, dans `apps/ai/app/tools/`. Ils appellent l'API ERP avec `x-actor` ; ils ne contiennent pas de règle métier.
Liste à jour : `GET http://localhost:4100/tools`.

| Outil | Ce qu'il fait | Route ERP |
|---|---|---|
| `search` | Retrouve client, produit, fournisseur ou commande depuis ce qui est dit (flou, sans accents, alias, mots parasites ignorés) | `GET /api/search` |
| `get_client` | Fiche client : statut, conditions, encours, préférences, notes, panier habituel, problèmes ouverts, 5 derniers événements | `GET /api/clients/{id}` |
| `get_product_stock` | Disponible, entrant, prochaine DLC, prix catalogue | `GET /api/products/{id}` |
| `find_alternatives` | 5 produits de remplacement en stock | `GET /api/products/{id}/alternatives` |
| `get_price` | Prix pour un client et une quantité, avec l'explication ; signale un meilleur prix par volume | `GET /api/prices/resolve` |
| `search_context` | Cherche dans les fiches de contexte (règles, procédures, habitudes…) | `GET /api/context` |
| `get_context` | Tout le contexte d'un client, fournisseur, produit ou rayon | `GET /api/context/for` |
| `save_context` | Mémorise un fait durable (préférence, contact, contrainte) | `POST /api/context` |
| `get_client_history` | Historique d'un client, filtrable par types | `GET /api/clients/{id}/events` |
| `log_client_event` | Enregistre une réclamation, un appel, une demande… | `POST /api/clients/{id}/events` |
| `get_supplier_history` | Historique d'un fournisseur | `GET /api/suppliers/{id}/events` |
| `log_supplier_event` | Enregistre un événement fournisseur | `POST /api/suppliers/{id}/events` |
| `create_draft_order` | Crée une pré-commande (`draft`) avec ou sans lignes | `POST /api/orders` |
| `add_order_line` | Ajoute une ligne à une commande | `POST /api/orders/{id}/lines` |
| `confirm_order` | Confirme (après accord explicite sur le récapitulatif) ; renvoie les alertes | `POST /api/orders/{id}/confirm` |
| `get_order` | Détail d'une commande : lignes, statut, total, alertes | `GET /api/orders/{id}` |

Ce que l'agent **ne peut pas** faire aujourd'hui (pas d'outil) : modifier ou retirer une ligne, annuler, préparer,
livrer, facturer, enregistrer un paiement, gérer les achats, les prix, le stock, les tournées. Les routes existent
dans l'API : un outil de plus suffit (voir [apps/ai/README.md, « Add a tool »](apps/ai/README.md#add-a-tool-about-10-lines)).

---

## 7. Pas à pas

Dans les exemples d'API, `B=http://localhost:4000/api`. Ajoutez `-H 'x-actor: voice_agent'` pour voir l'écriture en
violet dans le web.

### 7.1 Prendre une commande de bout en bout
**Web**
1. Commandes → « Nouvelle commande » → tapez le client → Entrée. Un brouillon s'ouvre.
2. Ajoutez les lignes (recherche produit, alias compris) ou piochez dans le panier habituel à droite.
3. Lisez les alertes, puis Confirmer. Le stock est réservé, la commande est sur une tournée.
4. Préparer (saisissez les poids réels si besoin) → Livrer → Facturer.
5. Sur la facture : « Enregistrer un paiement ».

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

### 7.2 Gérer une rupture avec un produit de remplacement
1. Vérifiez les notes et le contexte du client d'abord (certains refusent toute substitution) :
   `GET $B/context/for?entityType=client&id=cli_…`.
2. Sur la commande, une ligne en rupture porte `insufficient_stock`. Bouton « Alternatives » de la ligne →
   « Remplacer ». Par l'API : `GET $B/products/prd_…/alternatives`, puis
   `PATCH $B/orders/ord_…/lines/lin_… {"productId":"prd_NEW","substituteFor":"prd_OLD"}`. Le prix est recalculé
   pour le nouveau produit.
3. Possible en `draft` ou `confirmed`.

### 7.3 Recevoir une commande d'achat en partie
1. Achats → la commande (`sent` ou `partially_received`) → Réceptionner → saisissez la quantité reçue par ligne →
   valider.
2. API : `POST $B/purchase-orders/po_…/receive {"lines":[{"lineId":"pol_…","receivedQty":6}]}`.
3. Résultat : un lot par ligne reçue (DLC = aujourd'hui + durée de vie), statut `partially_received` tant qu'il
   reste à recevoir. Une seconde réception ajoute au déjà reçu. Le reste à recevoir compte dans `incoming`.

### 7.4 Enregistrer une réclamation
1. Fiche client → Historique → « Nouvel événement » → type Réclamation, titre, description, gravité, commande ou
   produits liés.
2. API : `POST $B/clients/cli_…/events {"type":"complaint","title":"Raie pas fraîche","severity":"medium","orderId":"ord_…"}`.
   Elle est créée `open`.
3. Pour clore : « Marquer résolu » (Historique) ou `PATCH $B/client-events/cev_… {"status":"resolved","resolution":"Avoir de 20 €"}`.

### 7.5 Comprendre pourquoi un client est bloqué (ou à risque)
1. `GET $B/clients/cli_…` : `status`, `creditLimit`, `outstanding`, `overdue`, `notes`, `recentEvents`, `openIssues`.
2. Encours → filtrez sur le client → panneau : tranches, factures ouvertes, dernières relances, litiges, risque.
   API : `GET $B/receivables?q=<nom>` (champs `risk`, `maxDaysOverdue`, `creditUsedPct`, `avgDaysToPay`,
   `openDisputes`, `lastReminderAt`).
3. Historique du client, filtre Paiements : `GET $B/clients/cli_…/events?type=late_payment,payment_plan,dispute`.
4. Le statut `blocked` est posé à la main : l'événement `client.updated` (« Client … bloqué ») dans le journal dit
   quand et par qui.

### 7.6 Fixer un prix négocié
1. Prix → Prix négociés → « Nouveau prix négocié » ; ou Matrice → clic sur une case client → « Fixer ce prix ».
2. API : `PUT $B/clients/cli_…/prices/prd_… {"price":17.5}` (remplace s'il existe). Supprimer :
   `DELETE $B/clients/cli_…/prices/prd_…`.
3. Vérifiez : `GET $B/prices/resolve?clientId=cli_…&productId=prd_…` → `source: "client_price"`. Les commandes
   déjà créées gardent leur ancien prix.

### 7.7 Voir ce que l'agent sait d'un client
1. Fiche client → onglet Contexte (fiches propres + fiches liées).
2. API : `GET $B/context/for?entityType=client&id=cli_…` (ce que charge l'outil `get_context`), plus
   `GET $B/clients/cli_…` (ce que renvoie `get_client`).
3. Ce qu'il a appris pendant les conversations : `GET $B/context?source=ai_chat,voice_agent`.
4. Le contexte entreprise toujours présent dans le prompt : `DATA_DIR/context/*.md`.

### 7.8 Remettre les données à zéro
`make reset` (= `POST /api/admin/reset`). Vide la base, recharge le pack de données de `DATA_DIR`, vide le journal.
Toutes vos écritures sont perdues.

### 7.9 Vos données
Les données de votre entreprise sont dans `./data` (`DATA_DIR=./data` dans `.env`). Si vous les cassez,
`make reset` les recharge. Vérifiez : `GET $B/meta` → `company` et `today`.

---

## 8. Aide-mémoire de l'API

Toutes les routes sont sous `/api`. Toutes les écritures acceptent `x-actor` et `x-actor-name`. Schémas complets et
essai en direct : http://localhost:4000/docs.

**Listes (toutes les routes GET qui renvoient une liste).** Pagination, filtres et tri côté serveur :
`limit` (défaut **100**, max **500**), `offset`, `sort` (champ triable de la route, voir `/docs`), `order=asc|desc`.
Réponse : un **tableau** JSON — la page demandée, donc **tronqué à `limit`** — ou, avec `envelope=1`,
`{items, total, limit, offset, counts?, sums?, …}` où `total` dit combien de lignes correspondent aux filtres et les
extras (`counts` par statut, `sums`…) portent sur tout l'ensemble filtré. Un agent n'a presque jamais besoin de tout :
filtrez (`clientId`, `status`, `date`, `q`…) et gardez `limit` petit. Détails : [TECH.md · Pagination](TECH.md#pagination).

```bash
curl -s 'localhost:4000/api/orders?clientId=cli_0012&limit=5'                       # les 5 dernières commandes (tableau)
curl -s 'localhost:4000/api/invoices?status=overdue&sort=balance&order=desc&limit=10' # les 10 plus gros retards
curl -s 'localhost:4000/api/orders?status=delivered&envelope=1&limit=1' | jq .total   # combien de commandes livrées
```

**Système**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/health` | `{ok, today}` |
| GET | `/meta` | entreprise, date métier |
| GET | `/dashboard` | KPI de l'accueil |
| GET | `/search?q=&types=&limit=` | recherche floue ; `types` = `client,product,supplier,order` (+ `context` sur demande) |
| GET | `/events?actor=&entity=` | journal d'activité (`actor=ai` : assistant + agent vocal ; défaut `limit` 50) |
| GET | `/events/stream` | journal en direct (SSE) |
| POST | `/admin/reset` | recharge le pack de données |

**Clients**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/clients?q=&type=&zone=&status=&tag=` | liste avec KPI ; `sort` = `name`, `outstanding`, `overdue`, `last`… |
| GET | `/clients/{id}` | fiche complète (prix négociés, 20 dernières commandes, factures ouvertes, paiements, habituel, historique récent) |
| GET | `/clients/{id}/usual` | panier habituel (60 derniers jours) |
| POST | `/clients` | créer |
| PATCH | `/clients/{id}` | modifier (statut, plafond, tags…) |
| POST | `/clients/{id}/notes` | ajouter une note `{text, author}` |
| GET / POST | `/clients/{id}/events?type=&status=&q=` | historique du client (`sort=open` : dossiers ouverts d'abord) / ajouter un événement |
| GET | `/client-events?type=&status=&clientId=&q=&from=&to=` | historique tous clients, récent d'abord |
| PATCH | `/client-events/{id}` | modifier, résoudre |
| PUT / DELETE | `/clients/{id}/prices/{productId}` | prix négocié |

**Catalogue, fournisseurs, stock**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/products?q=&category=&tag=&active=` | catalogue avec stock ; `sort` = `name`, `price`, `margin`, `available`… |
| GET | `/products/{id}` | fiche : stock, lots, prix fournisseurs, mouvements, ventes 30 j |
| GET | `/products/{id}/alternatives` | produits de remplacement |
| PATCH | `/products/{id}` | prix, coût, tags… |
| GET | `/suppliers?q=&category=&tag=` · `/suppliers/{id}` | fournisseurs (la fiche embarque les 60 dernières commandes d'achat) |
| PATCH | `/suppliers/{id}` | modifier |
| GET | `/suppliers/{id}/usual` | achats habituels (60 jours) |
| GET / POST | `/suppliers/{id}/events` | historique fournisseur |
| GET / PATCH | `/supplier-events` · `/supplier-events/{id}` | historique tous fournisseurs / modifier |
| GET | `/stock?q=&tab=` | niveaux de stock (`tab` = `out`, `low`, `expiring`) |
| GET | `/stock/movements?productId=` | mouvements, récent d'abord |
| POST | `/stock/adjust` | ajustement ou perte `{productId, qty, reason, note}` |

**Ventes**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/orders?status=&clientId=&date=&q=&source=` | liste, livraison la plus récente d'abord (`status` = liste séparée par des virgules) ; `sort` = `date`, `number`, `total`, `client`… |
| GET | `/orders/{id}` | détail avec alertes |
| POST | `/orders` | créer un brouillon `{clientId, deliveryDate?, lines?, note?, source?}` |
| PATCH | `/orders/{id}` | date de livraison, note |
| POST / PATCH / DELETE | `/orders/{id}/lines[/{lineId}]` | lignes |
| POST | `/orders/{id}/confirm` · `/prepare` · `/deliver` · `/invoice` · `/cancel` | cycle de vie |

**Achats**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/purchase-orders?status=&supplierId=&date=&q=` | liste, récente d'abord |
| GET | `/purchase-orders/{id}` | détail avec lots reçus et alertes |
| POST | `/purchase-orders` | créer un brouillon `{supplierId, lines?, expectedDate?, note?}` |
| PATCH | `/purchase-orders/{id}` | date attendue, note |
| POST / PATCH / DELETE | `/purchase-orders/{id}/lines[/{lineId}]` | lignes (brouillon) |
| POST | `/purchase-orders/{id}/send` · `/receive` · `/cancel` | cycle de vie |

**Facturation**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/invoices?status=&clientId=&q=` | liste sans les lignes (`status=open` et `overdue` acceptés) ; `sort` = `issued`, `due`, `balance`… |
| GET | `/invoices/{id}` | détail avec paiements |
| GET | `/payments?clientId=&method=&q=` | liste, récent d'abord (`q` : client, référence ou n° de facture) |
| POST | `/payments` | enregistrer `{clientId, amount, method, receivedAt?, reference?, allocations?}` |
| GET | `/receivables?q=&tag=&rep=&zone=&onlyOverdue=` | balance âgée, risque, DSO |

**Prix et groupes**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/prices/resolve?clientId=&productId=&qty=&date=` | prix retenu et pourquoi |
| GET | `/prices/grid?clientId=` ou `?clientTag=` (+ `productTag`, `category`, `q`) | grille de prix |
| GET / POST | `/price-rules` | règles (`active`, `clientId`, `productId` en filtres) / créer |
| PATCH / DELETE | `/price-rules/{id}` | modifier / supprimer |
| GET / POST | `/tags?scope=` · `/tags` | groupes avec compteurs / créer |
| PATCH / DELETE | `/tags/{scope}/{id}` | modifier / supprimer |

**Logistique**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/routes` | définitions des tournées |
| GET | `/route-runs?date=&routeId=` | passages avec arrêts, ETA, poids |
| POST | `/route-runs/plan` | planifier une date `{date}` |
| PATCH | `/route-runs/{id}/stops` | réordonner `{orderIds}` |

**Contexte**
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/context?entityType=&entityId=&kind=&source=&tag=&q=` | chercher / lister (par pertinence avec `q`) |
| GET | `/context/for?entityType=&id=` | tout le contexte d'une entité |
| GET / PATCH / DELETE | `/context/{id}` | une fiche |
| POST | `/context` | créer `{entityType, entityId?, kind, title, body, tags?}` |
