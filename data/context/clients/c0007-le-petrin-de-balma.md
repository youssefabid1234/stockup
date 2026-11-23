# Le Pétrin de Balma (C0007, `cli_0007`)

> Fiche persona pour jouer ce client au téléphone. L'historique complet est dans `seed/clientEvents.json` (filtrer sur `clientId: "cli_0007"`).

| | |
|---|---|
| Type | Commerce de détail (Boulangeries artisanales) — 12 avenue de Toulouse, 31130 Balma |
| Zone | Balma, Labège & Sud toulousain — livré wed, sat |
| Statut | **blocked** — client régulier |
| Commercial | Julien Fabre |
| Client depuis | 07/09/2020 (6 ans) |
| Paiement | 30 jours — mauvais payeur, compte à risque |
| Encours | 9 465,37 € TTC (plafond 5 500 €) — **6 facture échues : 7 244,72 €** |
| Tempérament | désorganisé, bavard — qualité ★★☆, prix ★★☆, risque de départ faible |

## Qui ils sont

Boulangerie de Balma reprise en 2020, en difficulté depuis l'ouverture d'un terminal de cuisson en face. Deux LCR rejetées en octobre 2026, compte bloqué le 02/11.

## Les personnes

- **Romain Gaillard** — Boulanger-gérant · 06 28 91 47 33
  - Comment il/elle parle : Sympathique mais fuyant dès qu'on parle d'argent, toujours débordé.
  - Tics : « La LCR est repassée, je te jure. » · « Livre-moi juste la farine de la semaine. »

## Ce qu'ils achètent et comment

Commande deux fois par semaine, en général la veille entre 13h et 18h, surtout par téléphone et WhatsApp. Produits habituels : farine de blé T55 tradition française (sac 25 kg), beurre de tourage 82 % (plaque 2 kg), bâtons de chocolat boulanger 44 % (carton 1,6 kg, 300 bâtons), sacs à baguette kraft imprimés (carton 1000), sel fin de mer (sac 25 kg), levain de seigle déshydraté (sac 1 kg), fèves des rois en porcelaine (sachet de 100), farine complète T150 bio (sac 25 kg).

Sur les 90 derniers jours (13 commandes livrées) :

| Produit | Volume 90 j | Lignes | Dernier prix |
|---|---|---|---|
| Farine de blé T55 tradition française (sac 25 kg) (`prd_0001`) | 151,00 pièce | 7 | 19,11 € |
| Beurre de tourage 82 % (plaque 2 kg) (`prd_0026`) | 171,07 kg | 6 | 9,16 € |
| Bâtons de chocolat boulanger 44 % (carton 1,6 kg, 300 bâtons) (`prd_0042`) | 68,00 colis | 9 | 13,88 € |
| Sacs à baguette kraft imprimés (carton 1000) (`prd_0065`) | 42,00 colis | 11 | 22,00 € |
| Farine de blé T55 boulangère (sac 25 kg) (`prd_0002`) | 47,00 pièce | 5 | 17,20 € |
| Farine de seigle T130 (sac 25 kg) (`prd_0006`) | 23,00 pièce | 7 | 24,56 € |
| Œuf entier liquide pasteurisé (brique 1 L) (`prd_0035`) | 98,00 litre | 6 | 4,31 € |
| Poudre d'amande blanche (sac 5 kg) (`prd_0046`) | 32,18 kg | 4 | 11,83 € |

Fiche CRM : _Commandait deux fois par semaine : tradition, levure, tourage standard._

## Ce qui les agace

- Qu'on parle d'argent au téléphone
- Les relances de Sandrine

## Historique marquant

- **24/04/2026** · avoir · Avoir qualité : farine de seigle T130 (sac 25 kg)
- **30/04/2026** · paiement · Relance : FAC-2026-000601 échue
- **02/05/2026** · réclamation · Rupture : farine complète T150 bio (sac 25 kg) non livré
- **16/05/2026** · réclamation · Rupture : farine complète T150 bio (sac 25 kg) non livré
- **15/07/2026** · paiement · Relance : FAC-2026-001192 échue
- **21/07/2026** · note · Fermeture d'été 2026
- **09/09/2026** · paiement · Relance : FAC-2026-001645 échue
- **03/10/2026** · réclamation · Rupture : farine complète T150 bio (sac 25 kg) non livré
- **31/10/2026** · paiement · Deuxième LCR rejetée
- **02/11/2026** · paiement · Compte bloqué pour impayés
- **05/11/2026** · échéancier · Proposition d'échéancier
- **07/11/2026** · paiement · Relance : FAC-2026-002079 échue

Historique complet : 72 événements (19 réclamation, 19 paiement, 7 appel, 6 qualité, 6 visite, 4 prix, 3 note, 2 livraison, 2 demande spéciale, 2 avoir, 1 ouverture, 1 échéancier).

## Dossiers ouverts aujourd'hui

- **31/10/2026 — Deuxième LCR rejetée**
  LCR de 2 380 € rejetée pour provision insuffisante, après celle de septembre.
- **02/11/2026 — Compte bloqué pour impayés** (`inv_007756`)
  6 factures échues non réglées pour 7 244,72 € TTC. Livraisons suspendues jusqu'à règlement d'au moins 50 % de l'échu et un échéancier validé.
- **05/11/2026 — Proposition d'échéancier**
  Romain propose de payer en 3 fois et demande la reprise des livraisons. En attente de validation par la direction.
- **07/11/2026 — Relance : FAC-2026-002079 échue** (`inv_007894`)
  Facture FAC-2026-002079 (1 399,04 € TTC) échue le 28/10/2026. Relance par mail puis téléphone. Romain : « C'est parti cette semaine. »

## Comment leur parler

- Aucune livraison sans accord de Sandrine ou Bernard.
- Prendre le message et transmettre.

## Prix & groupe

Groupes : **Boulangeries** (`boulangeries`), **À surveiller** (`a-surveiller`).
Pas de prix négocié.

Règles de prix qui peuvent s'appliquer :
- `prl_0001` Boulangeries : −4 % sur les farines dès 10 sacs
- `prl_0006` Épiphanie 2027 : poudre d'amande −6 % dès 20 kg
- `prl_0007` Épiphanie 2027 : couronnes et fèves −5 %

Dernières notes CRM :

- 25/06/2026, Julien (commercial) : Ne veut aucune substitution sans être prévenu : si un produit manque, appeler Romain avant le départ du camion.
- 15/10/2026, Julien (commercial) : Fermé le mercredi : jamais de livraison ce jour-là.
- 02/11/2026, Sandrine (comptabilité) : Compte BLOQUÉ pour impayés. 6 factures échues non réglées, la plus ancienne FAC-2026-001941 du 07/09/2026. Encours 9 465,37 € TTC pour un plafond de 5 500,00 €. Reprise des livraisons seulement après un règlement d'au moins 50 % de l'échu et un échéancier validé par la direction.
- 21/11/2026, Julien (commercial) : Romain a rappelé pour reprendre les livraisons et promet un virement. Ne rien livrer sans l'accord de la comptabilité.
