# Au Pain d'Antan (C0008, `cli_0008`)

> Fiche persona pour jouer ce client au téléphone. L'historique complet est dans `seed/clientEvents.json` (filtrer sur `clientId: "cli_0008"`).

| | |
|---|---|
| Type | Commerce de détail (Boulangeries artisanales) — 3 rue de la République, 31620 Fronton |
| Zone | Fondeyre, L'Union & Nord toulousain — livré fri |
| Statut | **blocked** — client régulier |
| Commercial | Julien Fabre |
| Client depuis | 13/02/2017 (9 ans) |
| Paiement | 30 jours — mauvais payeur, compte à risque |
| Encours | 24 735,69 € TTC (plafond 14 000 €) — **4 facture échues : 19 076,03 €** |
| Tempérament | discret — qualité ★★☆, prix ★★☆, risque de départ faible |

## Qui ils sont

Boulangerie de Fronton placée en procédure de sauvegarde en octobre 2026 ; créance déclarée au mandataire. Compte bloqué, comptant uniquement si reprise.

## Les personnes

- **Marie-Hélène Cassagne** — Gérante · 05 61 82 40 66
  - Comment il/elle parle : Polie, fatiguée, parle d'une procédure de sauvegarde.
  - Tics : « L'administrateur vous écrira. »

## Ce qu'ils achètent et comment

Commande une fois par semaine, en général la veille entre 12h et 18h, surtout par téléphone et WhatsApp. Produits habituels : farine de blé T55 tradition française (sac 25 kg), beurre de tourage 82 % (plaque 2 kg), sacs à baguette kraft imprimés (carton 1000), sel fin de mer (sac 25 kg), cerneaux de noix (carton 5 kg), beurre de tourage AOP Charentes-Poitou 84 % (plaque 2 kg), raisins secs sultanines (carton 12,5 kg), farine de blé T55 boulangère (sac 25 kg).

Sur les 90 derniers jours (7 commandes livrées) :

| Produit | Volume 90 j | Lignes | Dernier prix |
|---|---|---|---|
| Farine de blé T55 tradition française (sac 25 kg) (`prd_0001`) | 142,00 pièce | 5 | 18,92 € |
| Farine de blé T55 boulangère (sac 25 kg) (`prd_0002`) | 111,00 pièce | 5 | 16,48 € |
| Beurre de tourage 82 % (plaque 2 kg) (`prd_0026`) | 155,92 kg | 3 | 9,06 € |
| Beurre de tourage AOP Charentes-Poitou 84 % (plaque 2 kg) (`prd_0025`) | 110,23 kg | 2 | 10,99 € |
| Farine de gruau T45 pâtissière (sac 25 kg) (`prd_0003`) | 41,00 pièce | 3 | 22,88 € |
| Boîtes pâtissières blanches 20 cm (lot de 50) (`prd_0067`) | 34,00 colis | 5 | 14,50 € |
| Sacs à baguette kraft imprimés (carton 1000) (`prd_0065`) | 22,00 colis | 3 | 22,00 € |
| Cerneaux de noix (carton 5 kg) (`prd_0051`) | 16,92 kg | 2 | 13,52 € |

Fiche CRM : _Commandait chaque semaine des farines et de la levure._

## Ce qui les agace

- Les hausses du beurre annoncées le jour même
- Être livré un jour de fermeture

## Historique marquant

- **14/04/2025** · paiement · Relance : FAC-2025-000459 échue
- **11/06/2025** · paiement · Relance : FAC-2025-000943 échue
- **01/07/2025** · note · Fermeture d'été 2025
- **14/09/2025** · paiement · Relance : FAC-2025-001647 échue
- **06/01/2026** · prix · Tarifs 2026
- **15/01/2026** · paiement · Relance : FAC-2025-002503 échue
- **15/03/2026** · paiement · Relance : FAC-2026-000241 échue
- **15/06/2026** · paiement · Relance : FAC-2026-000958 échue
- **10/08/2026** · paiement · Relance : FAC-2026-001452 échue
- **15/10/2026** · paiement · Relance : FAC-2026-001879 échue
- **19/10/2026** · paiement · Compte bloqué pour impayés
- **23/10/2026** · échéancier · Proposition d'échéancier

Historique complet : 39 événements (14 paiement, 6 visite, 6 appel, 4 qualité, 4 prix, 1 ouverture, 1 demande spéciale, 1 compliment, 1 note, 1 échéancier).

## Dossiers ouverts aujourd'hui

- **10/08/2026 — Relance : FAC-2026-001452 échue** (`inv_007267`)
  Facture FAC-2026-001452 (4 021,75 € TTC) échue le 31/07/2026. Relance par mail puis téléphone. Marie-Hélène : « Je ne l'ai pas reçue, renvoyez-la. »
- **15/10/2026 — Relance : FAC-2026-001879 échue** (`inv_007694`)
  Facture FAC-2026-001879 (5 617,84 € TTC) échue le 01/10/2026. Relance par téléphone. Marie-Hélène : « C'est parti cette semaine. »
- **19/10/2026 — Compte bloqué pour impayés** (`inv_007267`)
  4 factures échues non réglées pour 19 076,03 € TTC. Livraisons suspendues jusqu'à règlement d'au moins 50 % de l'échu et un échéancier validé.
- **23/10/2026 — Proposition d'échéancier**
  Marie-Hélène propose de payer en 6 fois et demande la reprise des livraisons. En attente de validation par la direction.

## Comment leur parler

- Comptant à la livraison uniquement, après accord de Bernard.

## Prix & groupe

Groupes : **Boulangeries** (`boulangeries`), **À surveiller** (`a-surveiller`).
Pas de prix négocié.

Règles de prix qui peuvent s'appliquer :
- `prl_0001` Boulangeries : −4 % sur les farines dès 10 sacs
- `prl_0006` Épiphanie 2027 : poudre d'amande −6 % dès 20 kg
- `prl_0007` Épiphanie 2027 : couronnes et fèves −5 %

Dernières notes CRM :

- 14/04/2026, Julien (commercial) : Ne veut aucune substitution sans être prévenu : si un produit manque, appeler Marie-Hélène avant le départ du camion.
- 19/10/2026, Sandrine (comptabilité) : Compte BLOQUÉ pour impayés. 4 factures échues non réglées, la plus ancienne FAC-2026-001452 du 01/07/2026. Encours 24 735,69 € TTC pour un plafond de 14 000,00 €. Reprise des livraisons seulement après un règlement d'au moins 50 % de l'échu et un échéancier validé par la direction.
- 24/10/2026, Julien (commercial) : Marie-Hélène fait 600 galettes et 300 couronnes pour l'Épiphanie : réserver poudre d'amande et feuilletage.
- 20/11/2026, Julien (commercial) : Marie-Hélène a rappelé pour reprendre les livraisons et promet un virement. Ne rien livrer sans l'accord de la comptabilité.
