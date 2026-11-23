# Prix et crédit

## Prix de vente

- Tarif beurre et chocolat révisé le 1er de chaque mois (cotation beurre, cours du cacao), envoyé aux clients le 25 du mois précédent.
- Farines : prix trimestriel indexé sur le blé meunier ; accords de prix annuels possibles pour les gros boulangers.
- Surgelés, emballages et épicerie : tarif annuel au 1er février.
- Franco 150 € HT, sinon 12 € de frais de livraison.
- Remises : commerciaux jusqu'à 5 %, au-delà Bernard. Le standard ne peut pas accorder de remise.

Ordre de résolution : prix négocié client > règle de prix (client, puis groupe) > prix liste.

## Groupes de clients

- **Boulangeries** (`boulangeries`) : Boulangeries artisanales : farines au sac, levure, tourage, emballages.
- **Pâtisseries** (`patisseries`) : Pâtissiers et chocolatiers : couvertures, crème, fruits secs ; pics à Pâques et Noël.
- **Restaurants** (`chr`) : Restaurants et bistrots : crème, œufs, beurre, quelques surgelés.
- **Snacking** (`snacking`) : Franchises et sandwicheries : viennoiserie crue au carton.
- **GMS** (`gms`) : Rayons pain et terminaux de cuisson des supermarchés.
- **Traiteurs** (`traiteurs`) : Traiteurs événementiels, volumes irréguliers.
- **Hôtellerie** (`hotellerie`) : Hôtels : petit-déjeuner, factures au mois.
- **Collectivités** (`collectivites`) : Cuisines centrales et établissements publics.
- **Marché public** (`marche-public`) : Prix au bordereau, paiement par mandat administratif.
- **Grands comptes** (`grands-comptes`) : Les plus gros chiffres d'affaires des 12 derniers mois, suivis par la direction.
- **À surveiller** (`a-surveiller`) : Retards de paiement, litiges ou compte bloqué : vérifier l'encours avant toute commande.
- **Clients perdus** (`perdus`) : Plus de commande depuis plusieurs mois (partis à la concurrence ou fermés) : à reconquérir.

## Règles de prix

- `prl_0001` Boulangeries : −4 % sur les farines dès 10 sacs, du 01/01/2024
- `prl_0002` Pâtisseries : −5 % sur le chocolat dès 20 kg, du 01/09/2024
- `prl_0003` GMS : −5 % sur la viennoiserie crue, du 01/02/2025 — Accord annuel des terminaux de cuisson.
- `prl_0004` Collectivités : −4 % sur la crèmerie, du 01/01/2025
- `prl_0005` Snacking : coût + 20 % sur les chocolatines, du 01/06/2025 — Prix plancher accordé aux franchises.
- `prl_0006` Épiphanie 2027 : poudre d'amande −6 % dès 20 kg, du 15/11/2026 au 31/01/2027 — Opération galettes : pré-commande avant le 15 décembre.
- `prl_0007` Épiphanie 2027 : couronnes et fèves −5 %, du 15/11/2026 au 15/12/2026 — Remise de pré-commande.
- `prl_0008` Pâques 2026 : couvertures −4 % en précommande (inactive), du 01/02/2026 au 28/02/2026

## Crédit et relances

- Boulangers en LCR à 30 jours fin de mois ; nouveaux clients au comptant pendant trois mois.
- Relance à J+5 par mail, J+15 par téléphone (Sandrine), J+30 mise en demeure.
- Blocage automatique à la deuxième LCR rejetée ou au-delà du plafond d'encours.
- Déblocage : règlement de l'échu ou échéancier signé par Bernard ; livraisons au comptant en attendant.

## Clients à surveiller (au 24/11)

- Le Pétrin de Balma (cli_0007) : mauvais payeur, compte à risque, 6 facture échues pour 7 244,72 € TTC — **bloqué**.
- Au Pain d'Antan (cli_0008) : mauvais payeur, compte à risque, 4 facture échues pour 19 076,03 € TTC — **bloqué**.
- Maison Pujol Traiteur (cli_0009) : paie à l'heure mais déduit ce qu'il conteste, 1 facture échue pour 294,30 € TTC.
- La Brasserie des Carmes (cli_0014) : paie en retard (3 à 6 semaines), mais finit par payer.
- Le Pétrin de Muret (cli_0019) : paie à l'heure mais déduit ce qu'il conteste, 1 facture échue pour 182,90 € TTC.
- Le Comptoir de Colomiers (cli_0025) : paie en retard (3 à 6 semaines), mais finit par payer, 1 facture échue pour 672,39 € TTC.
- Garcia Traiteur (cli_0035) : paie en retard (3 à 6 semaines), mais finit par payer, 5 facture échues pour 12 980,98 € TTC.
- Le Comptoir de Toulouse (Capitole) (cli_0037) : paie en retard (3 à 6 semaines), mais finit par payer.
- Maison Bourgeois Chocolatier (cli_0040) : paie en retard (3 à 6 semaines), mais finit par payer, 3 facture échues pour 4 507,13 € TTC.
- L'Épi de Balma (cli_0042) : paie en retard (3 à 6 semaines), mais finit par payer, 3 facture échues pour 6 113,24 € TTC.
- Le Buffet Toulousain (cli_0046) : mauvais payeur, compte à risque, 3 facture échues pour 4 883,56 € TTC — **bloqué**.
- Le Fournil de Labège (cli_0050) : paie en retard (3 à 6 semaines), mais finit par payer, 1 facture échue pour 4 474,22 € TTC.
- Restaurant inter-entreprises Rangueil (cli_0057) : mandat administratif : paiement lent mais sûr, 1 facture échue pour 18 878,58 € TTC.
- Traiteur Saint-Aubin (cli_0058) : paie en retard (3 à 6 semaines), mais finit par payer.
- Aux Délices de Florian (cli_0067) : paie en retard (3 à 6 semaines), mais finit par payer, 1 facture échue pour 6 884,34 € TTC.
