# Le métier de grossiste alimentaire — référence

Ce document explique en détail comment fonctionne un grossiste alimentaire et comment chaque notion se retrouve
dans l'ERP du kit. Lisez-le pour choisir votre problème et pour que votre agent parle et agisse comme un
professionnel. Le brief général est dans [BRIEF.md](BRIEF.md).

## Comment lire ce document

- **Pour les humains** : lisez « Le métier en une page », « La chaîne », « Les acteurs » et « Où la voix change
  la donne ». Le reste sert de référence pendant les 24 heures.
- **Pour les agents de code** (Claude Code, Cursor…) : chaque domaine se termine par un bloc **Dans l'ERP** qui
  donne les noms exacts entre backticks : entités et champs (`Order.status`), routes (`/api/context/for`), outils
  de l'agent (`get_price`), pages de l'interface (**Commandes**). Les lignes **Règle** sont des règles métier
  explicites. Quand une règle est seulement écrite dans le contexte et *pas* appliquée par le backend, c'est dit.
- **Les exemples** viennent du pack **Marée de Rungis** (« le pack » dans la suite). Votre équipe reçoit le pack de
  sa propre entreprise dans `./data`, avec la même structure (`seed/` et `context/`). Marée de Rungis est un
  grossiste fictif en produits de la mer installé au MIN de Rungis : 66 produits, 100 clients, environ 1,2 M€ HT
  de ventes par mois, panier moyen d'environ 920 € HT. Tout est fictif. La « date du jour » du pack est
  `meta.today` = mardi 24 novembre 2026, et l'heure de référence est 4 h 30 : les camions ne sont pas encore partis.
- Le document couvre tout le commerce de gros alimentaire (marée, fruits et légumes, viande, crèmerie, épicerie,
  boissons, surgelés). Il y a 24 entreprises fictives, une par équipe, et la vôtre peut appartenir à une autre
  famille : les principes sont les mêmes, seuls les produits, les unités et les rythmes changent.

---

## Le métier en une page

Un grossiste alimentaire achète en gros, stocke peu de temps, et revend par petites quantités à des
professionnels : restaurants, commerces, cantines, hôtels. Il ne vend pas aux particuliers. On dit aussi
« distributeur » ou « grossiste RHD » (restauration hors domicile).

Ce qu'il vend vraiment, ce n'est pas seulement du produit. C'est :

- **le bon produit**, choisi parmi des dizaines de fournisseurs, au bon calibre, à la bonne qualité ;
- **au bon moment**, livré avant le service, souvent avant 7 h du matin ;
- **en petite quantité**, alors que le fournisseur vend par palette ou par lot ;
- **à crédit**, payé 30 jours plus tard ;
- **avec du conseil** : « le turbot est hors de prix cette semaine, prenez du Saint-Pierre ».

Trois chiffres résument la difficulté :

| Contrainte | Ordre de grandeur | Conséquence |
|---|---|---|
| Marge brute | 15 à 35 % du prix de vente | Peu de place pour l'erreur. La marge nette finale ne fait souvent que quelques pour cent. |
| Durée de vie du frais | 3 à 5 jours pour le poisson, quelques jours à quelques semaines pour les fruits et légumes et la viande | Tout ce qui n'est pas vendu à temps est jeté. |
| Délai de commande client | quelques heures, souvent la nuit | Il faut acheter avant de savoir ce qu'on vendra. |

Le grossiste gagne sa vie dans un équilibre fragile : acheter assez pour ne jamais dire « je n'en ai plus », sans
acheter ce qui finira à la poubelle, et se faire payer par des clients qui paient tard.

### Les familles de produits

Chaque grossiste est spécialisé dans une ou deux familles. Les règles changent beaucoup de l'une à l'autre.

| Famille | Exemples | Unité de vente | Durée de vie | Ce qui fait le prix | Aléa principal |
|---|---|---|---|---|---|
| **Marée** (produits de la mer) | bar, sole, huîtres, langoustines, moules | kg, douzaine, pièce | 3 à 5 jours ; coquillages vivants | criée du jour, espèce, calibre, sauvage ou élevage | météo : pas de pêche par tempête |
| **Fruits et légumes** | citrons, salades, pommes de terre, herbes | colis, cagette, kg, botte | de 2 jours (herbes, fraises) à plusieurs semaines (pommes de terre) | saison, origine, catégorie (Extra, I, II), calibre | météo, gel, récolte ; maturité |
| **Viande** | bœuf, veau, volaille, agneau | kg, pièce, carcasse ou morceau | quelques jours à quelques semaines sous vide | race, origine, catégorie, morceau, maturation | cours des marchés, crises sanitaires |
| **Crèmerie** | beurre, crème, fromages, œufs | kg, litre, pièce, plateau | de quelques jours (crème fraîche) à des mois (fromages affinés) | AOP, affinage, marque | saisons de lait, affinage |
| **Épicerie** | huile, conserves, sel, farine | carton, bidon, pièce | des mois (DDM) | marque, contrat annuel | peu : stock long, prix stables |
| **Boissons** | vin, bière, sodas, eaux | carton, fût, bouteille | longue | marque, contrat, accises sur l'alcool | consignes (fûts, verre), saison (été) |
| **Surgelés** | poisson pané, frites, légumes surgelés | carton, kg | des mois à −18 °C | contrat, volume | rupture de la chaîne du froid |

Le pack Marée de Rungis est un grossiste **marée** avec un peu de fruits et légumes, de crèmerie et d'épicerie en
complément : c'est courant, le chef veut tout recevoir dans le même camion.

---

## La chaîne : du bateau à l'assiette

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

### Les maillons, un par un

- **Pêcheurs.** Ils débarquent leur pêche au port. La petite pêche côtière sort pour la journée ; les plus gros
  bateaux partent plusieurs jours. Par gros temps, les bateaux restent à quai : plus rien n'arrive.
- **Criée** (ou halle à marée). Le marché du port où la pêche est vendue aux enchères, souvent sur écran, très tôt
  le matin. Les acheteurs sont des professionnels enregistrés, surtout des mareyeurs. Le prix y change chaque jour.
  Exemples dans le pack : criées de Boulogne-sur-Mer, Lorient, Le Guilvinec.
- **Mareyeur.** Premier acheteur du poisson. Il achète à la criée, trie, lave, glace, lève parfois les filets,
  et expédie dans la journée vers les grossistes. C'est lui que le grossiste marée appelle. Exemples :
  Boulogne Marée Mareyage (`sup_0001`), Mareyage de Keroman (`sup_0002`), Bigouden Marée (`sup_0003`).
- **Producteurs en direct.** Ostréiculteurs (huîtres), mytiliculteurs (moules), maraîchers, fromagers. Ils
  vendent eux-mêmes, souvent avec des minimums et des délais plus longs. Exemple : Huîtres Joubert (`sup_0004`),
  à J+2.
- **Coopératives et expéditeurs.** Ils regroupent la production de nombreux agriculteurs, la trient, la calibrent
  et l'emballent. Fréquents en fruits et légumes et en lait.
- **Abattoirs et ateliers de découpe.** Pour la viande : l'animal devient carcasse, puis quartiers, puis
  morceaux prêts à découper ou portions sous vide.
- **Importateurs.** Ils font venir ce que la France ne produit pas assez ou pas en saison : saumon de Norvège et
  d'Écosse, thon de l'océan Indien, agrumes, fruits exotiques. Souvent installés sur les marchés de gros.
  Exemple : Highland & Fjord Seafood (`sup_0006`), à Rungis, paiement à 45 jours.
- **Industriels.** Surgelés, épicerie, boissons. Prix négociés à l'année, stocks longs, livraisons planifiées.
  Exemple : Océane Surgelés (`sup_0007`), livraison J+2, franco à 1 500 €.
- **MIN (marché d'intérêt national).** Grands marchés de gros publics où se concentrent grossistes, producteurs
  et acheteurs. **Rungis**, au sud de Paris, est le plus grand : il est organisé en pavillons (marée, viande,
  fruits et légumes, produits laitiers, etc.) et vit la nuit. Il existe aussi des MIN régionaux (Lyon,
  Marseille, Toulouse, Nantes, Lille, Bordeaux…). Être sur un MIN, c'est avoir des dizaines de fournisseurs à
  quelques pas : on peut aller chercher un colis de citrons à pied chez le voisin (Primeurs Dufresne,
  `sup_0008`, deux allées plus loin). Beaucoup de grossistes ne sont pas sur un MIN et ont leur propre
  entrepôt en zone d'activité.
- **Le grossiste.** Il achète à tous ces maillons et revend à des centaines de professionnels.
- **Les clients.** Restaurants, commerces de bouche, collectivités, hôtels, traiteurs, parfois la grande
  distribution. Détails plus bas.

Il existe aussi des **concurrents** que le client compare au grossiste : les autres grossistes du même marché, les
grands distributeurs nationaux de la restauration (catalogue énorme, prix serrés, moins de souplesse), les
libres-services de gros (le chef va lui-même faire ses courses), et les producteurs qui vendent en direct.

### Ce que le grossiste apporte

| Valeur | Ce que ça veut dire concrètement | Exemple |
|---|---|---|
| **Assortiment** | Un seul interlocuteur pour 60 à plusieurs milliers de références, issues de dizaines de fournisseurs | Le chef reçoit bar, huîtres, citrons et beurre dans le même camion. |
| **Fractionnement** | Il achète par lot ou par palette, revend au kilo | Le mareyeur vend 50 kg de bar ; le bistrot en veut 3. |
| **Sélection et expertise** | Il connaît la qualité, les calibres, les saisons, les fournisseurs fiables | « Ne prenez pas de turbot cette semaine, il n'y a pas eu de débarque. » |
| **Disponibilité la nuit** | Il répond entre 22 h et 6 h, quand le chef sort du service ou le poissonnier ouvre | Ostréa commande entre 1 h et 3 h. |
| **Logistique et froid** | Camions frigorifiques, tournées, créneaux tôt le matin | Livraison avant 7 h au quai n° 2 de la cuisine centrale de Vitry. |
| **Crédit** | Le client paie à 15, 30 ou 45 jours ; le grossiste finance l'écart | Le Comptoir de Marie a environ 5 300 € d'encours pour un plafond de 6 500 €. |
| **Sécurité sanitaire** | Chaîne du froid, traçabilité par lot, retrait rapide en cas d'alerte | Il sait quels clients ont reçu le lot n° X. |
| **Dépannage** | Il trouve une solution quand le produit manque | Proposer du merlu quand le cabillaud a flambé. |

**Règle.** Le client ne compare pas seulement des prix. Il compare la fiabilité (livré à l'heure, le bon produit),
la qualité, la souplesse (commander tard, petites quantités) et le crédit. Un agent qui ne parle que de prix rate
l'essentiel.

---

## Les acteurs

### Les fournisseurs et la façon d'acheter

| Type | Ce qu'il vend | Délai typique | Prix | Ce qu'il faut savoir |
|---|---|---|---|---|
| **Mareyeur de criée** | poisson frais du jour | J+1 (camion de nuit) | change chaque jour avec la criée | dépend de la météo ; heure de coupure des commandes (souvent le matin, avant la criée) |
| **Producteur en direct** (ostréiculteur, maraîcher, fromager) | sa propre production | J+1 à J+3 | assez stable, peu négociable | petits volumes, minimum de commande, qualité très suivie |
| **Coopérative, expéditeur** | production regroupée et calibrée | J+1 à J+2 | prix de campagne, varie avec la saison | gros volumes, catégories normées |
| **Importateur** | produits étrangers, contre-saison | J+1 (stock sur place) | lié aux cours mondiaux et au change | souvent paiement plus long (45 jours) |
| **Industriel** (surgelés, épicerie, boissons) | produits transformés | J+2 à J+5, jours fixes | contrat annuel | franco de port, commande planifiée |
| **Confrère grossiste** | dépannage | immédiat | plus cher | on lui achète quand on est en rupture |

**Comment un acheteur achète, en pratique.** L'acheteur (Franck Le Bihan dans le pack) travaille la nuit et tôt
le matin. Chaque jour :

1. Il regarde ce qui a été vendu, ce qui est déjà commandé par les clients, ce qui reste en stock et ce qui
   expire bientôt.
2. Il consulte les **mercuriales** : les listes de prix du jour que les fournisseurs envoient (par mail,
   message, téléphone). Pour un même produit, il a souvent deux ou trois fournisseurs possibles.
3. Il **appelle** plusieurs fournisseurs, compare prix et qualité, et **négocie** : « Si je te prends 50 kilos,
   je ne veux pas dépasser 22,80. » Les arguments sont le volume, la fidélité, le prix du concurrent, et
   l'achat groupé de plusieurs espèces.
4. Il **réserve** des lots rares : « Garde-moi les homards bleus de vendredi. » Un fournisseur sert d'abord ses
   clients fidèles et bons payeurs les jours de pénurie.
5. Il passe commande, en respectant le **minimum de commande** et le **franco** (montant à partir duquel le
   transport est offert).
6. Il **réceptionne** la nuit suivante : il contrôle la quantité, la température, la qualité et le calibre.
   Ce qui manque ou ne convient pas devient un litige fournisseur.

Ce qui rend un fournisseur bon ou mauvais : la **fiabilité** (il livre ce qu'il a promis), la **régularité de
qualité**, la **souplesse de prix**, la **ponctualité** et la relation. Chaque fournisseur a sa personnalité :
Loïc Tanguy (Bigouden Marée) ne confirme jamais avant d'avoir vu les bateaux ; Gwenaël Le Corre (Keroman)
négocie au-delà de 50 kg par espèce et coupe les commandes à 9 h.

**Règle.** Payer ses fournisseurs à l'heure est un argument d'achat : les jours de pénurie, le fournisseur sert
d'abord les clients qui paient bien.

### Le transport

- **Camions en propre.** La plupart des grossistes ont leurs camions frigorifiques et leurs chauffeurs. Chaque
  camion fait une **tournée** : une zone, certains jours, un horaire de départ, une suite d'arrêts.
- **Transporteurs et loueurs.** Pour les pics (fêtes, samedis chargés) ou les zones lointaines, on loue un camion
  avec chauffeur, ou on confie les colis à un transporteur frigorifique. Il faut alors **réserver** : volume
  (m³), charge (kg), température (« froid positif » 0/+4 °C ou négatif), heure de départ, quai, liste des
  arrêts, prix. Exemple dans le pack : réserver un 12 m³ chez un loueur pour le samedi 28/11.
- **Le client qui vient lui-même.** Certains passent au quai prendre leur commande (Le Relais de Rungis).
- **Le transport amont.** Les fournisseurs livrent le grossiste par leurs camions de nuit, ou par des
  transporteurs spécialisés (le poisson de Bretagne arrive à Rungis la nuit).

Les contraintes du transport : **la chaîne du froid** (jamais de rupture de température), **les créneaux** (un
restaurant ne reçoit pas pendant le service, une cantine veut tout avant 7 h), **la capacité** (poids et volume
du camion), **l'ordre des arrêts** (on ne traverse pas Paris deux fois), et **les retours** (marchandise refusée,
consignes, caisses vides).

### Les clients

| Type | Exemples du pack | Comment il commande | Quand | Ce qui compte le plus |
|---|---|---|---|---|
| **Restaurant gastronomique** | La Table d'Aurélien, Maison Clément | Le chef appelle ou envoie un WhatsApp, produit par produit, exigeant sur le calibre et l'origine | le soir après le service ou la nuit | qualité, exactitude, aucune substitution |
| **Bistrot, restaurant traditionnel** | Le Bistrot du Port, Le Comptoir de Marie | Téléphone, « comme d'habitude », demande le prix | la veille ou la nuit | prix, régularité, conseil |
| **Brasserie** | Brasserie Le Mazarin | Mail du gérant + appels de l'écailler ; gros volumes réguliers, contrat | la veille en journée | prix négocié au volume, fiabilité, service |
| **Poissonnier, primeur** (commerce de détail) | Poissonnerie Lemoine, Marée Bleue | Téléphone la nuit, compare tous les jours, achète ce qui est beau et pas cher | la nuit pour le matin même | prix, fraîcheur, présentation, opportunités |
| **Restauration collective** (cantine, cuisine centrale, EHPAD, restaurant d'entreprise) | Cuisine centrale de Vitry, EHPAD Les Tilleuls | Commande ferme par mail, 2 à 3 jours avant, selon des menus fixés | à jours fixes, longtemps à l'avance | conformité au marché, prix fixes, sécurité sanitaire, ponctualité |
| **Hôtel** | Hôtel Le Marceau | Économat qui centralise, numéro de bon interne, extras du chef à valider | la veille en journée | procédure, facture conforme, régularité |
| **Traiteur** | Maison Berthier | Par événement, gros volumes ponctuels, plusieurs jours avant | selon le carnet d'événements | volume garanti à date, prix au devis |
| **Grande et moyenne surface** (GMS) | Frais d'Ici Créteil | Portail ou EDI, avant une heure limite | la veille avant 14 h | étiquetage réglementaire, conformité, prix |
| **Export** | — (absent du pack) | Commandes groupées, transport long | planifié | documents, certificats, emballage |

**Ils comparent.** Un client professionnel a presque toujours deux ou trois grossistes. Il les appelle le même
soir, compare le prix du bar, la qualité de la semaine dernière, et répartit ses commandes. Il y a deux profils :

- **Le fidèle** : un grossiste principal, pour la confiance, le crédit et la relation avec son commercial. Il part
  après une accumulation de petites erreurs, rarement pour quelques centimes.
- **L'opportuniste** : il achète au meilleur prix du jour. Les poissonniers et les primeurs le sont souvent : leur
  marge dépend de leur prix d'achat.

Qui privilégie quoi (★★★ = critère décisif) :

| Type de client | Prix | Qualité | Service (heure, souplesse) | Délai de paiement | Relation personnelle |
|---|---|---|---|---|---|
| Gastronomique | ★ | ★★★ | ★★★ | ★ | ★★★ |
| Bistrot | ★★ | ★★ | ★★ | ★★ | ★★ |
| Brasserie | ★★★ | ★★ | ★★★ | ★★ | ★★ |
| Poissonnier, primeur | ★★★ | ★★★ | ★★ | ★★ | ★ |
| Collectivité | ★★★ (fixé par le marché) | ★★ (conformité) | ★★★ (ponctualité) | ★ (paie lentement mais sûrement) | ★ |
| Hôtel | ★★ | ★★★ | ★★ | ★★ | ★ |
| Traiteur | ★★ | ★★ | ★★★ (volume à date) | ★★ | ★★ |
| GMS | ★★★ | ★★ | ★★ (conformité, étiquetage) | ★★ | ★ |

**Les collectivités, un monde à part.** Une cantine publique achète par **marché public** : un appel d'offres,
un cahier des charges, un **bordereau de prix** fixé pour un an ou plus, par lots (« produits de la mer »,
« fruits et légumes »). Le grossiste gagne ou perd le marché entier. Ensuite, pas de négociation au téléphone :
« le bordereau, c'est le bordereau ». Tout écart de prix ou substitution non prévue est un problème. Le
paiement passe par la trésorerie publique, souvent lent, et la facture se dépose sur la plateforme publique de
facturation (Chorus Pro). En restauration collective publique, la loi impose aussi une part de produits
durables et de qualité (dont du bio) : c'est un critère de choix des fournisseurs. Les EHPAD et cantines ont des
exigences fortes : filets sans arêtes, pas de coquillages, textures adaptées.

### Les rôles internes : qui fait quoi, qui appelle qui

| Rôle | Dans le pack | Ce qu'il fait | Ses horaires |
|---|---|---|---|
| **Gérant, direction** | Bruno Ménard | Valide les gros litiges, les déblocages de compte, les investissements, les marchés | journée |
| **Commerciaux** | Sophie, Karim, Julien, Nadia | Portefeuille de clients, prise de commande, prix et remises, visites, prospection | décalés, souvent tôt |
| **Standard de nuit, télévendeur** | Lucas Petit | Prend les commandes de 20 h à 6 h, ne négocie pas | nuit |
| **Acheteur** | Franck Le Bihan | Achète chaque nuit, suit les cours, négocie, réceptionne | nuit et matin |
| **Préparateurs** | (non nommés) | Prennent chaque commande, pèsent, emballent, étiquettent | 2 h – 5 h |
| **Chauffeurs-livreurs** | Mickaël, Abdel, Sébastien, Thierry, Patrick, Romain | Livrent, encaissent parfois, rapportent les retours et les remarques | 5 h – 9 h |
| **Comptabilité, recouvrement** | Hélène Garnier | Factures, avoirs, encaissements, relances, impayés | journée |
| **Qualité** | (souvent le gérant dans une PME) | Plan HACCP, températures, traçabilité, rappels | journée |

Qui appelle qui :

| Qui | Appelle | Pour |
|---|---|---|
| Client | commercial ou standard de nuit | commander, demander un prix, modifier, réclamer, demander l'heure de livraison |
| Commercial | client | proposer un arrivage, relancer un client silencieux, annoncer une rupture, négocier un contrat |
| Acheteur | fournisseurs | mercuriales, négociation, réservation de lots, réclamations qualité |
| Fournisseur | acheteur | annoncer une pénurie, une hausse, un complément, réclamer un paiement |
| Comptabilité | client, fournisseur | relancer un impayé, régler un litige de facture |
| Chauffeur | bureau, client | retard, client absent, marchandise refusée |
| Collègue | collègue | « il nous reste combien de Saint-Jacques ? », « tu peux rappeler Marie ? » |
| Gérant | transporteur, banque, gros clients | réserver un camion, négocier un marché, débloquer un compte |

---

## Économie et tensions du métier

**Marges faibles.** La marge brute du grossiste représente en général 15 à 35 % du prix de vente (dans le pack :
entre 15 et 35 % pour chaque produit, de `Product.cost` à `Product.price`). Une fois payés les camions, les chauffeurs, le froid, les loyers et
les impayés, il reste peu. Chaque erreur se paie directement.

**Le besoin en fonds de roulement.** Le grossiste paie ses fournisseurs à 21, 30 ou 45 jours, et ses clients le
paient à 30 ou 45 jours, parfois 60 en pratique. Entre les deux, c'est lui qui avance l'argent. Avec 1,2 M€ de
ventes par mois, quinze jours d'écart représentent environ 600 k€ à financer en permanence. Un client qui paie en retard
coûte de la trésorerie ; un client qui ne paie pas coûte toute la marge de dizaines d'autres commandes.

**La périssabilité.** Exemple simple : on achète 100 €, on revend 133 € (marge de 25 % sur le prix de vente,
soit 33 € de marge brute). Si 3 % de ce qu'on achète finit à la poubelle, on perd 3 € sur 33 : près de 10 % de
la marge brute disparaît. Pour le poisson frais, qui se garde 3 ou 4 jours, chaque jour compte.

**Avoir le bon produit au bon moment.** Il faut acheter *avant* de savoir. Les clients commandent la veille ou la
nuit même, mais l'acheteur passe ses commandes la nuit précédente pour la suivante. Trop peu : rupture, client
déçu, client qui part. Trop : invendus, promotion forcée, perte. Le métier consiste à prévoir à partir de
l'historique (« le mardi, Marée Bleue commande gros »), du calendrier (fêtes, vacances scolaires), de la météo,
des commandes déjà reçues et des promesses des clients.

**La volatilité des prix.** Les prix d'achat du frais bougent chaque jour (dans le pack : ±10 % autour du coût de
référence). Le prix de vente, lui, doit rester lisible pour le client. Une hausse brutale se gère par le
conseil (« prenez du merlu cette semaine ») plutôt que par une hausse annoncée au téléphone.

**La qualité variable.** Deux lots du même produit ne se valent pas : taille, fraîcheur, gras, couleur,
présentation. Le chef gastronomique refuse ce qu'un bistrot acceptera. Le grossiste doit orienter chaque lot
vers le bon client.

**Écouler le stock.** Un lot qui approche de sa date doit partir : on l'appelle « à pousser ». Les leviers : le
proposer aux clients qui en prennent d'habitude, faire un prix, le proposer aux clients ouverts aux promotions
(poissonniers, brasseries), le transformer (filets, portions), ou le déclasser.

**La substitution.** Quand un produit manque, on propose un équivalent : autre calibre, autre origine, élevage au
lieu de sauvage, surgelé au lieu de frais. C'est un service si le client est d'accord, une faute s'il ne l'est
pas.

**Le risque de crédit.** Chaque client a un **plafond de crédit** (encours maximal autorisé). Il faut surveiller
les retards, relancer, parfois **bloquer** un client : plus de livraison tant qu'il n'a pas payé. Bloquer trop
tôt fait perdre un client ; trop tard, de l'argent.

**La concurrence.** Le client compare chaque jour. La relation (le commercial qui connaît la carte du chef, qui
rappelle au bon moment, qui se souvient de la réclamation) est souvent ce qui fait la différence.

---

## Une journée de 24 heures

Horaires d'un grossiste marée sur un MIN, comme dans le pack. Un grossiste en fruits et légumes ou en viande a un
rythme proche, un peu plus tardif ; un grossiste en épicerie ou en boissons travaille surtout de jour.

| Heure | Ce qui se passe | Qui | Dans le pack |
|---|---|---|---|
| Veille, 4 h – 9 h | Criées dans les ports ; les mareyeurs achètent ; mercuriales envoyées | mareyeurs, acheteur | prix fournisseurs du jour (`SupplierPrice.updatedAt`) |
| Veille, 9 h – 14 h | L'acheteur finit de négocier pour la nuit suivante ; commerciaux au téléphone ; hôtels et collectivités envoient leurs commandes | acheteur, commerciaux | commandes `createdBy` = commercial |
| Veille, 14 h – 18 h | Commandes par mail des brasseries, du portail des supermarchés (avant 14 h) ; facturation, relances | commerciaux, compta | `Order.source` = `email`, `web` |
| Veille, 18 h – minuit | Les chefs commandent après le service (téléphone, WhatsApp) | standard de nuit | `createdBy: "lucas"`, `source: "whatsapp"` |
| 0 h – 2 h | Bars à huîtres, restaurants tardifs ; les camions fournisseurs roulent | standard de nuit | commandes `draft` à valider |
| 2 h – 3 h | Réception des camions fournisseurs : contrôle, un lot par ligne | réceptionnaire, acheteur | `Lot`, mouvements `receipt` |
| 3 h | Inventaire de nuit : on jette ce qui a dépassé sa date, on déclasse | préparateurs | mouvements `waste`, `adjustment` |
| 2 h – 4 h 30 | Poissonniers et bistrots commandent pour le matin même ; préparation : picking, pesée, étiquetage | standard, préparateurs | `preparedQty`, statut `prepared` |
| 3 h 40 – 4 h | L'acheteur envoie les commandes fournisseurs pour la nuit suivante (ou J+2, J+3) | acheteur | `PurchaseOrder.status` = `sent` |
| 4 h 30 | Heure limite pour être livré le matin même | — | `meta.today` à 4 h 30 |
| 5 h – 6 h | Départ des tournées | chauffeurs | `RouteRun` du jour |
| 5 h 30 – 9 h | Livraisons ; appels « il est où le camion ? » ; refus et retours au déchargement | chauffeurs, bureau | statut `delivered`, mouvements `sale` |
| 9 h – 12 h | Retour des camions, des retours et des caisses ; réclamations du matin ; criées du jour | chauffeurs, commerciaux | `ClientEvent` de type `complaint` |
| 12 h – 18 h | Facturation, encaissements, relances, cotations, prospection, préparation des achats | compta, commerciaux | `Invoice`, `Payment` |

Le dimanche, rien ne roule en général. Le lundi, certaines tournées ne roulent pas (dans le pack, Paris Sud et
Hauts-de-Seine & Yvelines). La veille de Noël et du Nouvel An, les volumes explosent et les horaires s'étirent.

---

## Les règles du métier (hygiène, traçabilité, paiement)

Ces règles sont générales et simplifiées. Elles suffisent pour qu'un agent ne dise pas de bêtise.

- **Chaîne du froid.** Le frais reste au froid positif (autour de 0 à +4 °C ; le poisson sous glace, proche de
  0 °C). Le surgelé reste à −18 °C ou moins. Un produit décongelé ne se recongèle pas. Les températures sont
  contrôlées à la réception, en chambre froide et dans les camions.
- **HACCP.** Toute entreprise alimentaire applique un plan d'hygiène fondé sur l'analyse des dangers (HACCP) :
  points critiques, températures, nettoyage, formation. Les établissements qui manipulent des produits d'origine
  animale ont en général un **agrément sanitaire** (la marque ovale sur les étiquettes).
- **Traçabilité par lot.** Chaque professionnel doit savoir de qui il a reçu un produit et à quel professionnel
  il l'a livré (« un pas en amont, un pas en aval »). Le grossiste suit donc chaque **lot** : fournisseur, date
  de réception, date limite, clients livrés. En cas d'alerte sanitaire, il doit pouvoir **retirer** le lot et
  prévenir les clients concernés vite.
- **DLC et DDM.** La **DLC** (date limite de consommation, « à consommer jusqu'au ») concerne les produits très
  périssables : après, on ne vend plus, on jette. La **DDM** (date de durabilité minimale, « à consommer de
  préférence avant ») concerne les produits stables (épicerie) : après, le produit peut perdre en qualité mais
  n'est pas dangereux.
- **Étiquetage de l'origine.** Pour le poisson vendu au consommateur : nom commercial et nom scientifique, mode
  de production (pêché ou élevé), zone de pêche (zone FAO) ou pays d'élevage, et type d'engin de pêche. C'est
  pour ça que Frais d'Ici Créteil refuse tout colis sans étiquette FAO et engin de pêche. Pour les fruits et
  légumes : pays d'origine et catégorie. Pour la viande bovine : l'origine est obligatoire, y compris au
  restaurant.
- **Coquillages vivants.** Huîtres, moules, palourdes sont vendues vivantes, avec une étiquette sanitaire sur
  chaque colis.
- **TVA.** Les denrées alimentaires sont à 5,5 % en France ; les boissons alcoolisées à 20 %. Dans le pack, tout
  le catalogue est à 5,5 % (`Product.vatRate` = 0.055).
- **Délais de paiement.** La loi plafonne les délais de paiement entre entreprises. Pour les **denrées
  alimentaires périssables**, le plafond est court : environ 30 jours après la livraison (précisément, 30 jours
  après la fin de la décade de livraison). Les autres achats sont plafonnés plus haut. Tout retard donne droit à
  des pénalités et à une indemnité forfaitaire de recouvrement. Les acheteurs publics ont leur propre délai légal,
  souvent dépassé en pratique. Dans le pack, certains clients ont 45 jours : c'est un choix de fiction, à ne pas
  prendre comme modèle légal pour le frais.
- **Prix et remises.** Seules les personnes habilitées (commerciaux, direction) accordent un prix spécial. Un
  standard de nuit ou un agent vocal ne négocie pas : il note et transmet.

---

## Les domaines du métier, un par un

Chaque bloc suit le même plan : **Ce que c'est**, **Vocabulaire**, **Comment ça marche**, **Les défis**,
**Dans l'ERP**.

### Clients

**Ce que c'est.** Le portefeuille : une centaine de professionnels très différents (voir « Les clients »
plus haut). Chacun a ses jours de livraison, ses conditions de paiement, ses habitudes, ses interlocuteurs et
son histoire avec le grossiste.

**Vocabulaire.**

- *Fiche client* : adresse, zone, jours de livraison, conditions de paiement, plafond, commercial.
- *Commercial attitré* : la personne qui « tient » le client. Certains clients ne veulent parler qu'à elle.
- *L'habituel*, *le panier habituel* : ce que le client commande presque toujours.
- *Encours*, *plafond de crédit*, *client bloqué* : voir Facturation.
- *Prospect* : client potentiel, pas encore de commande.
- *Client à risque*, *client qui décroche* : il commande moins, compare plus, se plaint.

**Comment ça marche.** Chaque client a un rythme : tous les jours, trois fois par semaine, au gré des menus. Il a
des habitudes fortes (« comme d'habitude », « le saumon de la dernière fois ») et des exigences fixes :
Sakana veut du saumon d'Écosse Label Rouge et jamais de Norvège, l'EHPAD Les Tilleuls veut des filets sans
arêtes, Racines & Marée est fermé le lundi et le mardi. Il a souvent plusieurs interlocuteurs : le chef choisit
les produits, le gérant valide les prix, la comptable paie. À l'Hôtel Le Marceau, tout passe par l'économat avec
un numéro de bon interne. Maison Clément ne veut être rappelée que par Karim, et jamais après 5 h 30.

**Les défis.**

- Le client ne donne jamais son identifiant. Il dit « c'est Marc du Bistrot », « c'est Yann », ou rien du tout.
  Il faut le reconnaître au nom, au numéro, à la voix, au contexte.
- Il faut se souvenir de tout : la réclamation de la semaine dernière, le retard de paiement, le prénom du
  second, la fermeture en août. Le meilleur commercial le fait de mémoire ; le standard de nuit ne le peut pas.
- Un client mal traité part chez le concurrent d'en face, souvent sans rien dire : il commande juste moins.

**Dans l'ERP.**

- Entité `Client` : `code`, `name`, `type` (`restaurant` | `brasserie` | `fishmonger` | `canteen` |
  `supermarket` | `caterer` | `hotel`), `contacts[]` (`name`, `role`, `phone`, `email`), `address`, `city`,
  `zone`, `deliveryDays` (`mon`…`sun`), `paymentTermsDays`, `creditLimit`, `status` (`active` | `blocked` |
  `prospect`), `salesRep`, `preferences` (résumé libre), `notes[]` (`at`, `author`, `text`), `tags` (groupes de
  clients : `gastro`, `brasseries`, `collectivites`, `marche-public`, `a-surveiller`…).
- Panier habituel : `GET /api/clients/{id}/usual`, calculé sur les commandes des 60 derniers jours (produits
  présents dans au moins 25 % des commandes, avec `avgQty`, `lastQty`, `frequency`).
- Fiche complète : `GET /api/clients/{id}` (prix négociés, commandes récentes, factures ouvertes, paiements,
  panier habituel, historique). Note de commercial : `POST /api/clients/{id}/notes`.
- Mémoire : table de contexte (`ContextEntry`, `entityType: "client"`, `entityId: "cli_…"`), avec des fiches
  par client (« Comment leur parler », « Ce qui les agace », dossiers ouverts). `GET /api/context/for?entityType=client&id=cli_0001`.
  Fiches persona lisibles dans `./data/context/clients/`.
- Outils de l'agent : `search` (« bistrot du port » → `cli_0007`), `get_client` (fiche, panier habituel,
  notes, problèmes ouverts, 5 derniers événements), `get_context`, `save_context` (mémoriser un fait durable).
- Pages : **Clients**, détail client (onglet Contexte, bloc « Ce que l'agent sait »), **Contexte**, **Groupes**.
- **Règle.** Avant de répondre à un client : l'identifier (`search`), charger sa fiche (`get_client`) et son
  contexte (`get_context`). Vérifier `status` : `blocked` ou `prospect` changent toute la conversation.

### Prise de commande et ventes

**Ce que c'est.** Le cœur de l'activité : transformer un appel, un mail, un WhatsApp ou un message vocal en une
commande juste, livrée au bon endroit le bon jour. Dans le pack, sur douze mois, 61 % des commandes arrivent
par téléphone, 24 % par mail, 9 % par WhatsApp, 5 % par le portail web et 2 % sont saisies au quai.

**Vocabulaire.**

- *Pré-commande*, *brouillon* : commande saisie mais pas encore validée par le client.
- *Ligne de commande* : un produit, une quantité, un prix.
- *Quantité commandée* et *quantité préparée* (le poids réel).
- *Heure limite*, *cut-off* : après, la commande part au prochain jour de livraison.
- *Rupture* : plus de stock. *Livraison partielle* : on livre une partie.
- *Substitution* : un produit à la place d'un autre, avec l'accord du client.
- *Relecture*, *récap* : relire la commande au client avant de raccrocher.
- *Bon de livraison (BL)* : le document qui accompagne la marchandise.
- *Dépannage* : une commande urgente hors des règles habituelles.

**Comment ça marche.**

1. Le client appelle, souvent la nuit, et dicte en vrac : « Mets-moi 5 kilos de bar, 2 caisses de moules et
   des huîtres comme d'habitude. »
2. Le vendeur identifie les produits (« le loup » = bar), vérifie le stock, annonce les prix si on les lui
   demande, propose une alternative si un produit manque.
3. Il garde **une seule** commande ouverte et la complète au fil de l'appel : le client ajoute souvent un
   article à la fin.
4. Il **relit** : « Je récapitule pour demain mercredi : 6 kilos de sole 500-600, 3 kilos de noix de
   Saint-Jacques, 2 kilos de beurre demi-sel. Livraison par la tournée Paris Ouest, vers 6 h. C'est bon pour
   vous ? »
5. Le client dit oui : la commande est **confirmée**. Elle passe ensuite en préparation, en livraison, puis en
   facturation.

**Les défis.**

- Les noms sont flous (« des n° 3 » = huîtres creuses calibre 3, « des noix » = noix de Saint-Jacques, « du
  lieu » = lieu jaune ou lieu noir ?). Il faut lever le doute sans agacer.
- Les unités varient : kilos, pièces, douzaines, colis, caisses, « un seau de crème » (5 litres), « une
  bourriche de 4 douzaines ».
- Le client change d'avis, interrompt, parle avec du bruit derrière, à 3 h du matin.
- Tout arrive en même temps entre 22 h et 4 h 30. Une erreur, c'est un chef sans poisson pour son service.
- Le jour de livraison n'est pas évident : avant ou après l'heure limite, jour de tournée ou pas, jours de
  fermeture du client.

**Dans l'ERP.**

- Entités `Order` (`number` « CMD-2026-000123 », `clientId`, `status`, `source`, `deliveryDate`, `routeRunId`,
  `totalHt`, `note`, `createdBy`, `confirmedAt`, `deliveredAt`, `invoiceId`) et `OrderLine` (`productId`, `qty`,
  `unitPrice`, `preparedQty`, `note`, `substituteFor`).
- `Order.status` : `draft` → `confirmed` → `prepared` → `delivered` → `invoiced`, ou `cancelled` depuis
  `draft`, `confirmed` ou `prepared`. Une transition interdite renvoie une erreur 409 `invalid_transition`.
- `Order.source` : `phone` | `voice_agent` | `email` | `whatsapp` | `manual` | `web`.
- Routes : `POST /api/orders`, `POST /api/orders/{id}/lines`, `PATCH /api/orders/{id}/lines/{lineId}`,
  `DELETE /api/orders/{id}/lines/{lineId}`, `PATCH /api/orders/{id}` (date, note), `POST /api/orders/{id}/confirm`,
  `/prepare`, `/deliver`, `/invoice`, `/cancel`.
- Outils de l'agent : `create_draft_order`, `add_order_line`, `confirm_order`, `get_order`. Il n'y a pas
  d'outil pour modifier ou supprimer une ligne, changer la date ou annuler : les routes existent, les outils
  sont à écrire.
- Alertes : chaque commande en cours renvoie `warnings[]` avec un `code` : `client_blocked`, `credit_limit`,
  `no_route` (aucune tournée ce jour-là pour la zone), `insufficient_stock`, `expiring_soon` (le lot sorti en
  premier expire au plus tard le lendemain de la livraison), `price_below_cost`. **Ces alertes ne bloquent
  jamais** : le backend confirme quand même. C'est à l'agent de réagir.
- Date par défaut : sans `deliveryDate`, l'ERP prend le prochain jour de livraison du client *strictement après*
  `meta.today`. Une commande pour le matin même doit donc donner la date explicitement. L'heure limite (4 h 30
  dans le pack) n'est **pas** appliquée par le backend : elle est écrite dans `context/06-livraisons-zones.md`.
- Pages : **Commandes**, détail d'une commande (lignes, alertes, tournée, facture), **Voix**, **Activité**.
- **Règle.** On ne confirme (`confirm_order`) qu'après un « oui » explicite du client sur le récapitulatif.
  Sans confirmation claire, la commande reste en `draft`.
- **Règle.** Une seule commande en cours par appel : on ajoute des lignes, on n'en crée pas une deuxième.
- **Règle.** Une commande `prepared` ne se modifie plus, sauf la quantité préparée et la note (le backend
  l'impose). Une commande `confirmed` se modifie encore.

### Produits et catalogue

**Ce que c'est.** De quelques dizaines à quelques milliers de références, rangées par rayon. Les rayons sont
**propres à chaque entreprise** (`seed/categories.json`, `GET /api/categories` → `[{id, label}]`) : regardez ceux
de la vôtre.

**Vocabulaire.**

- *Référence*, *article*, *SKU* (code article, ex. `BAR-LIG-12`).
- *Calibre* : la taille. Bar 1-2 kg, sole 500-600 g, langoustines 15/20 (15 à 20 pièces au kilo), huîtres n° 3
  (plus le numéro est petit, plus l'huître est grosse).
- *Sauvage* ou *de ligne* (pêché) contre *élevage* : prix et image très différents.
- *Origine* : Bretagne, Écosse, Norvège, zone FAO.
- *Label* : Label Rouge, AOP (moules de bouchot du Mont-Saint-Michel, beurre d'Isigny), bio, MSC.
- *Unité de vente* : kg, pièce, douzaine, colis, litre. *Colisage* : combien d'unités par colis.
- *Alias* : les noms que les clients utilisent (« loup » pour bar, « cab » pour cabillaud).
- *Saisonnier*, *hors saison*, *produit de fêtes*.
- *Produit à pousser* : un produit à écouler vite.

**Comment ça marche.** Chaque produit a un prix catalogue, un coût de référence, une unité, une durée de
conservation, une origine, un calibre, un fournisseur principal et des produits de remplacement acceptables. Le
catalogue change avec les saisons : la sardine et l'araignée de mer sont inactives en novembre ; la
Saint-Jacques ouvre en octobre. Un bon vendeur connaît aussi ce qui n'est écrit nulle part : quel produit est
beau cette semaine, lequel est cher, lequel il faut écouler.

**Les défis.**

- Le même produit a dix noms ; deux produits proches n'ont rien à voir pour un chef (bar de ligne à 32,50 €/kg
  et bar d'élevage à 14,90 €/kg).
- L'offre change chaque jour selon la pêche ou la récolte.
- L'agent doit connaître le catalogue mieux que le client, et savoir quand demander une précision (« Lieu jaune
  ou lieu noir ? ») plutôt que de deviner.

**Dans l'ERP.**

- Entité `Product` : `sku`, `name`, `aliases[]`, `category` (id d'une catégorie de
  l'entreprise, voir `GET /api/categories`), `unit` (`kg` | `piece` | `box` | `dozen` | `liter`),
  `price` (prix liste € HT), `cost` (coût de référence € HT), `vatRate`, `shelfLifeDays`, `origin`, `caliber`,
  `mainSupplierId`, `active`, `tags` (`premium`, `fetes`, `labels`, `best-sellers`, `saison`…).
- Routes : `GET /api/products?q=&category=&tag=`, `GET /api/products/{id}`, `GET /api/products/{id}/alternatives`.
- Recherche floue : `GET /api/search?q=` (accents, fautes, alias, mots de remplissage ignorés) ; outil `search`.
- Outils : `get_product_stock`, `find_alternatives` (même rayon, en stock, prix le plus proche), `get_context`
  avec `entityType: "product"` ou `"category"`.
- Glossaire complet avec alias, prix et DLC : `./data/context/03-glossaire-produits.md`.
- Pages : **Produits**, détail produit, **Groupes**.
- **Règle.** `find_alternatives` ne connaît que le rayon et le prix. Le remplacement « métier » (turbot sauvage →
  turbot d'élevage, Label Rouge → Norvège) et les refus du client sont dans le contexte et le playbook : les
  vérifier avant de proposer.

### Prix

**Ce que c'est.** Le prix d'un produit n'est pas le même pour tout le monde, ni d'un jour à l'autre. Un gros
client a des prix négociés, un groupe de clients a des remises, une promotion dure une semaine, un marché public
fixe tout pour un an.

**Vocabulaire.**

- *Prix catalogue*, *prix liste* : le prix de base.
- *Prix négocié*, *prix client* : un prix pour un client et un produit.
- *Remise* (en %), *règle de prix* (pour un groupe de clients ou un rayon), *prix de volume* (« dès 50 kg »).
- *Marge* : prix de vente moins coût. *Coefficient* : prix de vente divisé par coût.
- *Cours du jour* : prix d'achat qui varie avec la criée.
- *Prix ferme* : garanti pour une période. *Prix au bordereau* : fixé par un marché public.
- *Cotation*, *devis* : un prix proposé avant la commande.
- *Geste commercial* : une baisse accordée pour réparer un problème.

**Comment ça marche.** Le prix d'une ligne se décide dans cet ordre :

1. Un **prix négocié** pour ce client et ce produit : il gagne toujours.
2. Sinon, la **règle de prix** la plus précise qui s'applique (par exemple « Gastro : −5 % sur les crustacés »,
   « Volume : moules de bouchot −4 % dès 50 kg »).
3. Sinon, le **prix catalogue**.

Le prix est figé sur la ligne au moment où elle est créée. Les prix d'achat du frais bougent chaque jour, mais
les prix de vente restent stables : on ne change pas le prix du bar au téléphone parce que la criée a monté, on
conseille une autre espèce.

**Les défis.**

- Annoncer le bon prix du premier coup. Un prix faux, c'est de la marge perdue ou un client fâché à la facture.
- Défendre la marge face à un client qui négocie (« chez l'autre, c'est 2 € de moins »).
- Savoir qui peut accorder une remise. Dans le pack : seuls les commerciaux ; le standard de nuit et l'agent
  vocal n'en accordent aucune. Le Zinc des Halles négocie tout, mais rien ne se décide sans Karim.
- Signaler une bonne affaire : « à partir de 50 kilos, la moule passe à 4,70 ».

**Dans l'ERP.**

- `ClientPrice` (`clientId`, `productId`, `price`) : `PUT` et `DELETE /api/clients/{id}/prices/{productId}`.
- `PriceRule` : `name`, `active`, `priority`, `clientScope` (`all` | `client` | `tag`), `productScope` (`all` |
  `product` | `tag` | `category`), `method` (`fixed` prix fixe | `discount_pct` remise sur le prix liste |
  `markup_pct` marge sur le coût), `minQty`, `validFrom`, `validTo`. Routes `/api/price-rules`.
- Résolution : `GET /api/prices/resolve?clientId=&productId=&qty=` renvoie `price`, `listPrice`, `source`,
  `explanation` en français et tous les candidats. Grille : `GET /api/prices/grid?clientId=` ou `?clientTag=`.
  Le calcul vit dans `apps/backend/app/services/pricing.py`, et nulle part ailleurs.
- Outil : `get_price` (renvoie aussi `betterPriceWithVolume` quand une règle de volume donnerait mieux).
- Les outils de commande ne permettent pas de fixer un prix : l'ERP le résout. C'est voulu.
- Accords particuliers du pack : `./data/context/05-prix-et-credit.md`.
- Page : **Prix** (matrice clients × produits, règles, prix négociés, simulateur de marge).
- **Règle.** Toujours passer par `get_price` (ou `/api/prices/resolve`) pour annoncer un prix. Ne jamais
  calculer une remise dans le prompt.
- **Règle.** L'agent vocal n'accorde aucune remise : il note la demande (`log_client_event` de type
  `price_negotiation`) et la transmet au commercial.

### Achats et fournisseurs

**Ce que c'est.** Acheter chaque nuit ce qui sera vendu les jours suivants, auprès des mareyeurs, producteurs,
importateurs et industriels (voir « Les fournisseurs » plus haut).

**Vocabulaire.**

- *Commande d'achat*, *commande fournisseur*, *bon de commande*.
- *Mercuriale* : la liste de prix du jour d'un fournisseur.
- *Délai* : J+1, J+2, J+3 (jours entre la commande et la livraison).
- *Minimum de commande*, *franco* (montant à partir duquel le transport est offert).
- *Arrivage*, *débarque* (ce que les bateaux ramènent), *apport*.
- *Réception*, *réception partielle*, *complément* (le reste, livré plus tard).
- *Couverture* : combien de jours de ventes le stock permet de tenir.
- *Référencement* : faire entrer un nouveau fournisseur.

**Comment ça marche.** L'acheteur compare les prix de plusieurs fournisseurs, appelle pour négocier ou réserver un
lot, passe commande, puis réceptionne. Dans le pack : le frais est commandé chaque nuit pour la nuit suivante,
avec environ deux jours de couverture ; les surgelés le lundi, le mercredi ou le jeudi (J+2) ; la crèmerie et
l'épicerie le lundi ou le jeudi (J+3). La marchandise arrive parfois en quantité ou qualité différente : Huîtres
Joubert a livré incomplet sur les spéciales n° 3, complément annoncé jeudi.

**Les défis.**

- Acheter assez pour servir tout le monde, sans acheter ce qui finira à la poubelle.
- Comparer des prix qui changent chaque jour, entre fournisseurs qui n'ont pas la même fiabilité.
- Réagir quand la pêche ne sort pas : la tempête en Bretagne met le turbot sauvage et les langoustines 15/20 à
  zéro, et une commande d'achat reste en brouillon tant que le fournisseur n'a pas confirmé.
- Respecter les minimums et les heures de coupure de chaque fournisseur.

**Dans l'ERP.**

- `Supplier` : `name`, `contacts[]`, `city`, `categories[]`, `leadTimeDays`, `paymentTermsDays`,
  `minOrderAmount`, `notes`, `tags` (`mareyeur`, `producteur`, `ostreiculteur`, `importateur`, `grossiste`).
- `SupplierPrice` (`supplierId`, `productId`, `price`, `updatedAt`) : dernier prix connu chez chaque
  fournisseur. Les produits phares ont 2 ou 3 fournisseurs possibles. Aucune route ne met à jour ce prix.
- `PurchaseOrder` (`number` « ACH-2026-000045 », `supplierId`, `status`, `expectedDate`, `totalHt`, `note`) et
  ses lignes (`productId`, `qty`, `unitPrice`, `receivedQty`).
- `PurchaseOrder.status` : `draft` → `sent` → `partially_received` → `received`, ou `cancelled`. Les lignes ne
  se modifient qu'en `draft`.
- Routes : `/api/purchase-orders` (créer, lignes, `/send`, `/receive`, `/cancel`), `/api/suppliers`,
  `/api/suppliers/{id}/usual` (ce qu'on achète d'habitude à ce fournisseur).
- Alertes non bloquantes : `below_min_order`, `not_in_supplier_catalog`, `price_above_usual` (plus de 10 %
  au-dessus du dernier prix connu).
- Outils de l'agent : `get_supplier_history`, `log_supplier_event` (qualité, retard, pénurie, hausse de prix),
  `get_context` avec `entityType: "supplier"`. **Aucun outil d'achat** : créer ou envoyer une commande
  fournisseur demande d'écrire l'outil (les routes existent).
- Fiches persona des fournisseurs : `./data/context/suppliers/`.
- Pages : **Achats**, détail d'une commande d'achat, **Fournisseurs**, détail fournisseur, **Historique**.
- **Règle.** Une commande fournisseur se compare au dernier prix connu (`SupplierPrice`) et au minimum du
  fournisseur avant d'être envoyée.

### Stocks, lots et dates

**Ce que c'est.** Ce qu'il y a réellement en chambre froide, lot par lot, avec la date limite de chaque lot.

**Vocabulaire.**

- *Lot* : une arrivée d'un produit, avec sa date de réception, sa date limite et son fournisseur.
- *DLC*, *DDM* : voir « Les règles du métier ». Dans le pack, « DLC » désigne la durée de vie en jours après
  réception.
- *FEFO* (*first expired, first out*) : on sort d'abord le lot qui expire le plus tôt.
- *Stock physique* (ce qui est en chambre froide), *stock réservé* (promis à des commandes confirmées), *stock
  disponible* (physique moins réservé), *à recevoir* (commandé au fournisseur, pas encore arrivé).
- *Casse*, *perte*, *démarque*, *destruction* : ce qui est jeté.
- *Déclassement* : un produit qui n'est plus assez beau pour son usage normal, vendu moins cher ou transformé.
- *Inventaire* : le comptage réel, qui corrige le stock théorique.

**Comment ça marche.** Chaque réception crée un lot. Quand une commande est confirmée, la quantité est réservée.
À la préparation et au départ du camion, la marchandise sort en FEFO. À l'inventaire de nuit, ce qui a dépassé
sa date est détruit et compté en perte. Un bon vendeur sait dire au téléphone : « Il m'en reste 12 kilos, DLC
jeudi. »

**Les défis.**

- Le poisson frais se garde trois ou quatre jours, le maquereau trois. Chaque lot qui vieillit doit trouver
  preneur.
- Le stock théorique et le stock réel divergent (pesées, casse, erreurs de saisie).
- Un lot qui expire bientôt est une occasion : le proposer aux clients qui en prennent, à un prix d'écoulement.
- Une rupture annoncée trop tard fait plus de dégâts qu'une rupture annoncée tôt : Les Docks veulent être
  prévenus 48 h avant, la cuisine centrale de Vitry 72 h avant, par écrit.

**Dans l'ERP.**

- `Lot` : `productId`, `supplierId`, `purchaseOrderId`, `qtyReceived`, `qtyRemaining`, `receivedAt`,
  `expiresAt`. À la réception d'une commande d'achat, `expiresAt` = date de réception + `Product.shelfLifeDays`.
- `StockLevel` (calculé, jamais stocké) : `onHand` = somme des `qtyRemaining` ; `reserved` = quantités des
  commandes `confirmed` ou `prepared` (quantité préparée si connue) ; `available` = `onHand` − `reserved` ;
  `incoming` = reste à recevoir des commandes d'achat `sent` ou `partially_received` ; `nextExpiry`.
- La réservation se fait **par produit**, pas par lot. Les lots ne sont consommés (FEFO) qu'à la livraison
  (`POST /api/orders/{id}/deliver`).
- `StockMovement.reason` : `receipt` | `sale` | `adjustment` | `waste` | `return`.
- Routes : `GET /api/stock`, `GET /api/stock/movements?productId=`, `POST /api/stock/adjust` (`reason`
  `adjustment` ou `waste` ; `waste` retire toujours).
- Les lots périmés ne sont **pas** détruits automatiquement : il faut un `waste` via `/api/stock/adjust`.
- Outil de l'agent : `get_product_stock` (disponible, physique, réservé, à recevoir, prochaine date limite, prix
  liste). Il n'y a pas d'outil de mouvement de stock.
- Page : **Stocks** (lots, DLC, mouvements).
- **Règle.** Annoncer le **disponible** (`available`), jamais le physique : le reste est déjà promis.
- **Règle.** Si le disponible ne suffit pas, regarder `incoming` et la date attendue de la commande d'achat
  avant de dire « rupture ».

### Préparation et pesée

**Ce que c'est.** La nuit, les préparateurs prennent chaque commande, choisissent les lots, pèsent, emballent sous
glace et étiquettent.

**Vocabulaire.**

- *Préparation*, *picking* : prendre les produits en chambre froide.
- *Poids réel*, *poids variable* : ce que pèse vraiment ce qui est livré.
- *Écart de pesée* : différence entre commandé et livré.
- *Colis*, *caisse*, *bac*, *étiquette* (produit, lot, date, origine).
- *Habillage* : vider, écailler, lever en filets, portionner. Le chef demande souvent « vidé », « sans tête »,
  « en filets ».

**Comment ça marche.** Le client commande 6 kilos ; on lui livre un poisson de 5,8 ou 6,3 kilos. La facture suit
le poids réel. Dans le pack, l'écart normal sur le poisson au kilo est de −4 % à +6 %. Les demandes de
préparation (« vidé », « sans tête ») sont des notes sur la ligne. Une commande préparée est pesée et emballée :
la modifier désorganise tout.

**Les défis.**

- Garder des écarts raisonnables et les expliquer : Brasserie Montparnasse 1925 conteste souvent les poids et
  paie ses factures moins les écarts qu'elle estime.
- Les commandes de dernière minute arrivent pendant la préparation.
- Savoir ce qui est encore modifiable au moment de l'appel.

**Dans l'ERP.**

- `OrderLine.preparedQty` : quantité réellement préparée. Si elle existe, le total et la facture se calculent
  dessus, sinon sur `qty`. `OrderLine.note` : « vidé », « sans tête », « bien frais ».
- Route : `POST /api/orders/{id}/prepare` (avec ou sans quantités par ligne ; une ligne non listée est préparée
  exactement comme commandée). Passe la commande de `confirmed` à `prepared`.
- Pas d'outil de préparation pour l'agent.
- Page : détail d'une commande (colonnes commandé, préparé).
- **Règle.** Avant de promettre une modification, regarder `Order.status` : `draft` ou `confirmed` =
  modifiable ; `prepared` = seule la quantité préparée et la note changent ; `delivered` ou après = trop tard,
  c'est une réclamation ou un retour.
- **Règle.** Quand un client demande un prix total pour un produit au poids, préciser que c'est une estimation
  et que la facture suivra le poids réel.

### Livraisons et tournées

**Ce que c'est.** Des camions frigorifiques qui livrent chaque client dans un créneau, selon des tournées par zone
(voir « Le transport »). Dans le pack : six tournées partent de Rungis entre 5 h et 6 h.

**Vocabulaire.**

- *Tournée*, *zone*, *jours de tournée*, *heure de départ*.
- *Arrêt*, *ordre des arrêts*, *heure estimée*, *créneau*.
- *Chauffeur-livreur*, *quai*, *porte de service*, *clé* (livraison en l'absence du client).
- *Retour*, *refus à la livraison*, *client absent*.
- *Affrètement* : louer un camion ou confier à un transporteur.

**Comment ça marche.** Chaque client appartient à une zone, servie par une tournée certains jours. Un client
n'est livrable que les jours où sa tournée roule **et** qui sont dans ses jours de livraison. Une tournée regroupe
les commandes confirmées du jour dans un ordre précis. Le chauffeur part, livre, rapporte les retours et
parfois l'argent (paiement au chauffeur pour Phở Saigon 13 ou Le Festin Nomade).

**Les défis.**

- « Vous me livrez à quelle heure ? », « je ne serai pas là avant 7 h », « livrez par la porte de service » :
  ces questions arrivent toute la matinée.
- Un retard casse le service d'un restaurant ou la production d'une cuisine centrale.
- La capacité du camion est limitée : les samedis et les fêtes, il faut un deuxième camion.
- Les contraintes propres à chaque client : quai n° 2 avant 7 h, livraison du mercredi au samedi seulement,
  homard bleu seulement le vendredi et le samedi.

**Dans l'ERP.**

- `Route` : `name`, `zone`, `driver`, `vehicle`, `capacityKg`, `days`, `departureTime`.
- `RouteRun` : une tournée à une date (`routeId`, `date`, `status` : `planned` | `in_progress` | `done`) avec
  ses `stops[]` (`orderId`, `clientId`, `seq`, `eta`, `status` : `pending` | `delivered` | `failed`, `note`).
- Confirmer une commande la rattache à la tournée de la zone du client à sa date (`Order.routeRunId`). Une
  commande en brouillon n'est sur aucune tournée.
- `eta` = heure de départ + 12 minutes par arrêt (calcul simple). Poids pour la capacité : kg et litres tels
  quels, un colis (`box`) ≈ 5 kg, une pièce ou une douzaine ≈ 1 kg.
- Routes : `GET /api/routes`, `GET /api/route-runs?date=`, `POST /api/route-runs/plan`, `PATCH /api/route-runs/{id}/stops`
  (réordonner).
- Absent : transporteurs, réservation de camion, créneaux par client, suivi GPS. Les contraintes de livraison
  sont dans le contexte (`kind: "logistics"`) et dans `context/06-livraisons-zones.md`.
- Pas d'outil de tournée pour l'agent : « où est mon camion ? » demande d'écrire l'outil.
- Page : **Tournées**.
- **Règle.** Pour « à quelle heure je suis livré ? » : trouver la commande du jour du client, sa `RouteRun`, l'arrêt
  et son `eta`. À défaut, donner la fourchette de la tournée.
- **Règle.** Une alerte `no_route` signifie que la tournée de la zone ne roule pas ce jour-là : proposer le
  prochain jour de livraison.

### Facturation, paiements et encours

**Ce que c'est.** Facturer chaque livraison et se faire payer. C'est souvent le plus dur.

**Vocabulaire.**

- *Facture*, *relevé* (facture qui regroupe plusieurs livraisons), *avoir* (facture négative après un retour
  ou un litige).
- *Échéance*, *délai de paiement* (« 30 jours »), *paiement comptant*, *paiement à la livraison*.
- *Encaissement*, *règlement*, *lettrage* (rapprocher un paiement des factures qu'il paie).
- *Encours* : ce que le client doit. *Échu* : ce qui est en retard. *Balance âgée* : l'encours par tranche de
  retard (à échoir, 1-30 jours, 31-60…).
- *Relance*, *mise en demeure*, *recouvrement*, *plan d'apurement* (étaler une dette).
- *Plafond de crédit*, *client bloqué*, *déblocage*.
- *DSO* : délai moyen de paiement des clients, en jours.

**Comment ça marche.** En général, une facture par livraison, avec une échéance selon les conditions du client.
Certains clients reçoivent un relevé hebdomadaire ou mensuel. Les paiements arrivent par virement (souvent un
virement pour plusieurs factures), chèque, carte, espèces au chauffeur ou prélèvement. Certains paient en
retard ; la comptable relance avec le numéro, la date et le montant exacts de chaque facture. Au-delà du
plafond ou après trop de retard, le client est bloqué : plus de livraison tant qu'il n'a pas payé.

**Les défis.**

- Un client qui ne paie pas coûte plus cher qu'un client perdu.
- Bloquer avec tact : un client bloqué qui appelle à 3 h pour commander doit être bien reçu, mais aucune
  commande ne doit partir.
- Les payeurs lents ne sont pas tous à risque : une collectivité paie à 45-60 jours mais paie toujours ; il ne
  faut pas la bloquer.
- Les litiges bloquent les paiements : une facture contestée reste partiellement payée.

**Dans l'ERP.**

- `Invoice` : `number` « FAC-2026-000210 », `clientId`, `orderIds[]`, `status`, `issuedAt`, `dueDate`,
  `lines[]`, `totalHt`, `totalVat`, `totalTtc`, `amountPaid`. `dueDate` = `issuedAt` + `Client.paymentTermsDays`.
- `Invoice.status` stocké : `draft` | `issued` | `partially_paid` | `paid` | `cancelled`. **`overdue` n'est
  jamais stocké** : il est calculé à la lecture (facture ouverte dont `dueDate` < `meta.today`).
- `Payment` : `clientId`, `amount` (€ TTC), `method` (`transfer` | `card` | `cheque` | `cash` |
  `direct_debit`), `receivedAt`, `reference`, `allocations[]`. Sans allocations, le paiement solde les factures
  ouvertes les plus anciennes d'abord.
- Encours : `GET /api/receivables` (balance âgée par client : tranches `current`, `d1_30`, `d31_60`, `d61_90`,
  `d90plus`, `avgDaysToPay`, `risk`, DSO). `risk` = `high` si encours > plafond, retard > 60 jours, client
  bloqué, ou paie en moyenne à plus de 60 jours avec de l'échu ; `watch` si encours > 80 % du plafond, retard >
  30 jours, un `late_payment` ouvert, ou paie en moyenne à plus de 45 jours.
- `Client.creditLimit` est en € TTC ; `Client.paymentTermsDays` = 0 veut dire paiement à la livraison.
- Routes : `GET /api/invoices?clientId=&status=` (accepte `open` et `overdue`), `GET /api/invoices/{id}`,
  `POST /api/orders/{id}/invoice` (une facture par commande livrée), `GET/POST /api/payments`.
- Absent : avoirs en tant que documents (seulement des événements `credit_note` dans l'historique), relevés
  groupés automatiques, pénalités de retard.
- Outils de l'agent : `get_client` renvoie `outstanding`, `overdue`, `creditLimit`, `paymentTermsDays`. Il n'y a
  pas d'outil pour lister les factures ou enregistrer un paiement (l'exemple du README, `list_overdue_invoices`,
  montre comment l'écrire).
- Pages : **Factures**, **Paiements**, **Encours**.
- **Règle.** Le backend **n'empêche pas** de confirmer une commande pour un client `blocked` ou au-delà de son
  plafond : il renvoie seulement les alertes `client_blocked` et `credit_limit`. La règle métier, dans
  `context/05-prix-et-credit.md` : pour un compte bloqué, aucune commande confirmée, au plus un brouillon avec
  une note, et on transmet au commercial ou à la comptabilité.
- **Règle.** Si une commande ferait dépasser le plafond : ne pas refuser sèchement ; enregistrer en brouillon
  avec une note, prévenir poliment, transmettre. Si le client a de l'échu, le dire avec tact et proposer un
  règlement.
- **Règle.** Dans une relance, toujours citer numéro, date et montant exacts. Ne jamais réciter de mémoire :
  relire les factures.

### Réclamations, retours et litiges

**Ce que c'est.** Tout ce qui se passe mal après la livraison : produit abîmé, manquant, mauvais calibre, mal
préparé, livré en retard, erreur de prix ou de poids. Et, côté fournisseur : lot de mauvaise qualité, livraison
incomplète, hausse imprévue.

**Vocabulaire.**

- *Réclamation*, *litige*, *dossier ouvert*, *dossier résolu*.
- *Retour marchandise*, *refus à la livraison* (le chef renvoie au chauffeur ce qui ne va pas).
- *Avoir* : montant remboursé ou déduit de la prochaine facture.
- *Geste commercial* : une remise pour réparer la relation.
- *Remplacement* : relivrer le bon produit.
- *Risque de départ* : un client qui menace d'aller voir ailleurs.

**Comment ça marche.** Le client appelle ou le chauffeur rapporte le problème. On note précisément : produit,
quantité, lot, date de livraison, ce que dit le client. Le dossier est ouvert. Le commercial décide de la
réponse (avoir, remplacement, geste), la comptabilité émet l'avoir. Le dossier est résolu. Exemple du pack : La
Table d'Aurélien a refusé 1 kg de langoustines pas assez vives le 18/11, déduit de la facture. Côté
fournisseur, l'acheteur réclame à son tour : avoir fournisseur, remplacement, ou baisse de prix sur la
prochaine commande.

**Les défis.**

- Un client qui rappelle pour une réclamation déjà ouverte veut qu'on s'en souvienne, sans avoir à tout
  réexpliquer.
- Un agent qui ignore le litige en cours et propose joyeusement une nouvelle commande perd le client.
- Ne pas promettre au téléphone ce que seul le commercial peut accorder.
- Relier une réclamation client à son lot et à son fournisseur.

**Dans l'ERP.**

- `ClientEvent` : `type` (`onboarding`, `call`, `visit`, `complaint`, `quality_issue`, `delivery_issue`,
  `return`, `credit_note`, `dispute`, `late_payment`, `payment_plan`, `price_negotiation`, `special_request`,
  `menu_change`, `contact_change`, `compliment`, `churn_risk`, `won_back`, `note`), `title`, `description`,
  `channel`, `author`, `severity` (`low` | `medium` | `high`), `status` (`open` | `resolved`), `resolution`,
  `orderId`, `invoiceId`, `productIds`, `amount`.
- `SupplierEvent` : mêmes champs, `type` parmi `quality_issue`, `delivery_issue`, `shortage`, `return`,
  `credit_note`, `dispute`, `price_change`, `price_negotiation`, `invoice_issue`, `payment`, `contract`,
  `certification`, `contact_change`, `compliment`, `call`, `visit`, `onboarding`, `note` ; lien
  `purchaseOrderId`.
- Routes : `GET/POST /api/clients/{id}/events`, `PATCH /api/client-events/{id}` (résoudre), idem côté
  fournisseurs.
- Outils : `get_client_history` et `get_supplier_history` (dossiers ouverts en premier), `log_client_event`
  et `log_supplier_event` (les problèmes sont créés `open`). `get_client` renvoie déjà `openIssues` et les 5
  derniers événements.
- Absent : un endpoint de retour de marchandise (la raison de mouvement `return` existe, pas la route), les
  avoirs en tant que documents, le lien automatique lot → clients livrés.
- Page : **Historique** (clients et fournisseurs), onglets historique des fiches.
- **Règle.** Commencer tout appel d'un client par ses dossiers ouverts (`openIssues`). En parler avant de
  vendre.
- **Règle.** Pendant l'appel, enregistrer la réclamation fidèlement (`log_client_event`), sans promettre d'avoir
  ni de geste. Un fait durable (préférence, contrainte) va dans le contexte (`save_context`), pas dans
  l'historique.

### Saisons et aléas

**Ce que c'est.** Le calendrier, la météo et l'actualité décident de presque tout : ce qu'on peut acheter, ce que
les clients veulent, à quel prix.

**Vocabulaire.**

- *Saison*, *ouverture* (début de la pêche d'une espèce, comme la Saint-Jacques en octobre), *fermeture*.
- *Pic*, *creux*, *fêtes*, *pont*.
- *Coup de mer*, *débarque nulle*, *pénurie*.
- *Prévision*, *anticipation*, *pré-commande de fêtes*.

**Comment ça marche.**

- **Fin d'année** : huîtres, homards, langoustines, Saint-Jacques, saumon fumé. Les volumes se multiplient, les
  traiteurs pré-commandent des semaines à l'avance (Maison Berthier a un brouillon pour le 19/12), les
  brasseries négocient leurs volumes (Le Mazarin attend une proposition avant le 1er décembre). Il faut
  réserver chez les fournisseurs et louer des camions.
- **Août** : les restaurants parisiens ferment, les volumes chutent, certains paient en retard (L'Écume).
- **Vacances scolaires** : les cantines s'arrêtent (la cuisine centrale d'Issy n'est pas livrée).
- **Carême, Pâques, le vendredi** : plus de poisson. **Été** : plus de boissons, de fruits, de produits légers.
- **Météo** : une tempête bloque la pêche plusieurs jours (en ce moment : pas de débarque au Guilvinec depuis
  vendredi) ; une canicule change la demande et menace la chaîne du froid ; un gel détruit une récolte.
- **Le jour de la semaine** : les poissonniers commandent plus en fin de semaine ; Marée Bleue commande gros le
  mardi.

**Les défis.** Anticiper les volumes, prévenir les clients d'une rupture avant qu'ils ne la découvrent, proposer
les bons produits de saison, ajuster les achats, réserver la capacité.

**Dans l'ERP.**

- Trois ans d'historique de commandes : les saisons s'y voient (`GET /api/orders?date=`, `/api/clients/{id}/usual`).
- `Product.active` (hors saison = inactif), `Product.tags` (`saison`, `fetes`).
- `PriceRule.validFrom` / `validTo` pour les promotions datées (« Ouverture de la Saint-Jacques : −5 % en
  octobre »).
- Situation du jour : `context/01-entreprise.md` (« Situation au 24/11 ») et les événements fournisseurs
  `shortage` ouverts.
- Absent : prévision des ventes, météo, calendrier des fêtes. Tout est à construire si vous en avez besoin.

---

## Carte rapide : métier → ERP

| Notion métier | Entité, champ | Route principale | Outil de l'agent | Page |
|---|---|---|---|---|
| Reconnaître un client, un produit | — | `GET /api/search?q=` | `search` | ⌘K |
| Fiche client, l'habituel | `Client`, `Client.notes`, panier habituel | `GET /api/clients/{id}`, `/usual` | `get_client` | **Clients** |
| Ce qu'on sait d'un client, fournisseur, produit | `ContextEntry` (`entityType` + `entityId`, `kind`) | `GET /api/context/for` | `get_context`, `search_context`, `save_context` | **Contexte** |
| Prise de commande | `Order`, `OrderLine` | `POST /api/orders`, `/lines`, `/confirm` | `create_draft_order`, `add_order_line`, `confirm_order`, `get_order` | **Commandes** |
| Modifier, annuler une commande | `Order.status` | `PATCH /api/orders/{id}`, `PATCH`/`DELETE …/lines/{lineId}`, `/cancel` | à écrire | **Commandes** |
| Stock, DLC | `Lot`, `StockLevel`, `StockMovement` | `GET /api/stock`, `/api/products/{id}` | `get_product_stock` | **Stocks** |
| Remplacement | `Product.category` | `GET /api/products/{id}/alternatives` | `find_alternatives` | **Produits** |
| Prix pour un client | `ClientPrice`, `PriceRule`, `Product.price` | `GET /api/prices/resolve` | `get_price` | **Prix** |
| Achats | `PurchaseOrder`, `SupplierPrice`, `Supplier` | `/api/purchase-orders` | à écrire | **Achats**, **Fournisseurs** |
| Préparation, pesée | `OrderLine.preparedQty` | `POST /api/orders/{id}/prepare` | à écrire | détail commande |
| Tournées, heure de livraison | `Route`, `RouteRun`, `RouteStop.eta` | `GET /api/route-runs?date=` | à écrire | **Tournées** |
| Factures, retards | `Invoice` (`overdue` calculé) | `GET /api/invoices` | à écrire (`get_client` donne les totaux) | **Factures** |
| Paiements | `Payment.allocations` | `GET/POST /api/payments` | à écrire | **Paiements** |
| Encours, risque | balance âgée, `risk` | `GET /api/receivables` | à écrire | **Encours** |
| Réclamations, historique | `ClientEvent`, `SupplierEvent` | `/api/clients/{id}/events`, `/api/suppliers/{id}/events` | `get_client_history`, `log_client_event`, `get_supplier_history`, `log_supplier_event` | **Historique** |
| Groupes de clients, produits, fournisseurs | `tags`, `TagDef` | `/api/tags` | — | **Groupes** |
| Ce que l'agent a fait | `ActivityEvent` (`actor` : `user`, `ai_chat`, `voice_agent`, `system`) | `GET /api/events`, `/api/events/stream` | automatique (`x-actor`) | **Activité** |
| La date du jour | `Meta.today` | `GET /api/meta` | dans le prompt | — |

**La mémoire de l'entreprise.** Deux sources, à ne pas confondre :

- Les fichiers `DATA_DIR/context/*.md` (présentation, journée type, glossaire produits, playbook client, prix et
  crédit, livraisons et zones) sont mis **entiers** dans le prompt système et relus à chaque tour
  (`apps/ai/app/agent/prompts.py`). On peut les modifier en direct.
- La table de contexte (`ContextEntry`) contient des fiches courtes attachées à une entité : `entityType`
  (`company` | `client` | `supplier` | `product` | `category`) + `entityId` (`cli_…`, `sup_…`, `prd_…`, ou l'id
  d'une catégorie de `GET /api/categories`). `kind` : `policy` (règle), `procedure`, `preference`, `fact`, `relationship`,
  `pricing`, `logistics`, `risk`. `source` : `seed`, `user`, `ai_chat`, `voice_agent`. `GET /api/context/for`
  renvoie les fiches de l'entité **et** les fiches liées (le rayon d'un produit, les règles d'entreprise qui
  citent son id).

**Ce que le kit ne modélise pas** (à construire si votre problème en a besoin) : transporteurs et réservation de
camions, tâches et rappels (« rappeler le chef quand le turbot arrive »), devis, avoirs en tant que documents,
retours de marchandise, appels d'offres, prévisions de ventes, températures, numéro de lot du fournisseur, lien
lot → clients livrés, heure limite de commande appliquée par le backend, blocage réel des commandes d'un client
bloqué.

---

## Où la voix change la donne

Le téléphone est le premier canal du métier. Voici, acteur par acteur, les appels qui se passent vraiment chaque
jour. C'est une description du terrain, pas une liste de sujets : à vous de choisir le problème qui vous
intéresse.

### Le client qui appelle le grossiste

- **La commande de nuit.** 3 h 40, Marie du Comptoir appelle pour un groupe ce midi. Elle demande le prix du dos
  de cabillaud, le trouve cher, accepte moitié cabillaud, moitié merlu sur conseil, ajoute des moules et du
  maquereau vidé. Son encours approche du plafond : il faut le lui dire sans la vexer.
- **« Comme d'habitude ».** Le client ne détaille pas. Il faut connaître son panier habituel, le lui proposer,
  et noter ce qui change cette semaine.
- **La rupture.** Le chef de La Table d'Aurélien veut du turbot sauvage ; il n'y en a pas depuis la tempête. Il
  refuse l'élevage. Il faut le dire tout de suite, proposer ce qui est acceptable pour lui (Saint-Pierre, bar de
  ligne), et promettre de le rappeler quand le turbot arrive.
- **La commande trop tardive.** Le Petit Mareyeur appelle à 5 h 45 alors que sa tournée est partie à 5 h 30. Il
  faut le dire clairement et proposer le prochain jour.
- **La modification.** Le gérant de Brasserie Montparnasse 1925 monte ses huîtres de 33 à 45 douzaines, ajoute
  des tourteaux, hésite, change d'avis. Possible ou pas selon l'état de la commande, et il a un litige de poids
  en cours.
- **« Il est où le camion ? »** 6 h 20, l'écailler du Mazarin doit monter son banc d'huîtres. Il faut l'heure
  estimée de son arrêt, le nom du chauffeur, le contenu de la commande, et il en profite pour ajouter deux colis
  de citrons.
- **La réclamation.** « Les langoustines sont arrivées mortes. » Écouter, noter précisément, ne rien promettre,
  rassurer, faire remonter.
- **Le client bloqué.** La Poissonnerie Daguerre veut commander alors que son compte est suspendu. Rester
  courtois, expliquer, ne rien confirmer, transmettre.
- **Le prospect.** Un nouveau restaurant demande les prix et les jours de livraison. Accueillir, poser les bonnes
  questions (volumes, jours, produits clés, fournisseur actuel), donner les prix liste, proposer un rappel du
  commercial.
- **L'extra.** Le chef de l'hôtel commande un extra que l'économat doit valider.
- **La question simple.** « Vous avez des Saint-Jacques ? À combien ? Jusqu'à quand je peux commander pour
  demain ? »

### Le grossiste qui appelle ses clients

- **Annoncer une rupture** avant que le client ne la découvre à la livraison, avec une alternative et son prix.
- **Proposer un arrivage ou un lot à écouler** : « J'ai de très beaux homards ce matin », « Il me reste 15 kilos
  de lieu jaune, je vous les fais à… » (le prix, c'est le commercial qui le décide).
- **Relancer un impayé** : citer les factures, obtenir une date de paiement, la noter.
- **Réveiller un client silencieux** : il commandait trois fois par semaine, plus rien depuis dix jours.
- **Préparer les fêtes** : recueillir les pré-commandes des traiteurs et des brasseries.

### Le grossiste et ses fournisseurs

- **Comparer et négocier** : appeler deux ou trois mareyeurs, obtenir un prix, négocier au volume.
- **Réserver un lot rare** ou demander un **complément** après une livraison incomplète.
- **Réclamer** : lot hors calibre, livraison incomplète, retard.
- **Être appelé** : le fournisseur annonce une tempête, une hausse, un retard ; ou réclame un paiement.

### Le grossiste et le transport

- **Réserver un camion** supplémentaire pour un samedi chargé : volume, température, heure, quai, prix
 .
- **Le chauffeur qui appelle** : client absent, accès bloqué, marchandise refusée, retard sur la tournée.

### En interne

- **Un collègue demande le stock** : « Il nous reste quoi en Saint-Jacques ? » La bonne réponse donne le
  disponible, les lots qui finissent bientôt et l'arrivage de demain.
- **Le commercial sur la route** dicte une note après une visite, ou demande l'encours d'un client avant d'entrer.
- **Le gérant** demande où en sont les impayés, les ruptures du jour, les commandes de la nuit.
- **Le préparateur** signale un écart de pesée ou un produit manquant pendant la préparation.

Ces situations sont autant de scénarios de test : écrivez les vôtres à partir des fiches clients et fournisseurs de votre entreprise (`data/context/`).
---

## Pourquoi c'est dur pour un agent

Tout se joue en même temps, la nuit, au téléphone, avec des gens pressés qui parlent vite, avec du bruit, avec
leurs propres mots. Chaque réponse doit être juste au kilo et au centime près. L'agent doit avoir la mémoire du
meilleur commercial (qui est ce client, ce qu'il prend, ce qui l'agace, ce qui s'est passé la semaine dernière),
la rigueur d'un comptable (encours, plafond, échéances) et la prudence d'un responsable qualité (pas de
substitution sans accord, pas de promesse impossible), le tout à la vitesse d'une conversation normale.

Ce qui fait sonner un agent comme un pro :

- il reconnaît le client et l'appelle par son prénom ;
- il parle en unités du métier (« six kilos de sole 500-600 », « trente douzaines de n° 3 ») ;
- il propose l'habituel au lieu de poser dix questions ;
- il annonce une rupture avec une raison et une alternative ;
- il connaît le jour et l'heure de livraison réels ;
- il relit la commande avant de raccrocher ;
- il ne promet que ce que l'entreprise peut tenir.

---

## Glossaire

| Terme | Définition | Dans l'ERP |
|---|---|---|
| Affrètement | Louer un camion ou confier une livraison à un transporteur | absent |
| Alias | Nom courant d'un produit (« loup » pour bar) | `Product.aliases` |
| AOP, Label Rouge | Signes officiels de qualité ou d'origine | `Product.tags` (`labels`) |
| Arrivage, débarque | Marchandise qui arrive, ce que les bateaux ramènent | `PurchaseOrder`, `Lot` |
| Avoir | Facture négative après un retour ou un litige | événement `credit_note` |
| Balance âgée | Encours réparti par ancienneté du retard | `GET /api/receivables` |
| BL (bon de livraison) | Document qui accompagne la livraison | — |
| Bordereau de prix | Prix fixés par un marché public | `ClientPrice`, `PriceRule` (`marche-public`) |
| Bourriche | Panier d'huîtres (ex. 4 douzaines) | unité `dozen` |
| Brouillon, pré-commande | Commande non validée par le client | `Order.status = "draft"` |
| Calibre | Taille d'un produit (1-2 kg, 15/20, n° 3) | `Product.caliber` |
| Chaîne du froid | Maintien continu de la température | — |
| Colis, caisse | Unité d'emballage | unité `box` (≈ 5 kg) |
| Commande d'achat | Commande passée à un fournisseur | `PurchaseOrder` |
| Commercial attitré | Vendeur responsable d'un client | `Client.salesRep` |
| Complément | Reste d'une livraison incomplète, livré plus tard | `partially_received` |
| Couverture | Nombre de jours de ventes que le stock permet de tenir | — |
| Criée | Halle où la pêche est vendue aux enchères | — |
| Cut-off, heure limite | Heure après laquelle la commande part au jour suivant | contexte seulement |
| DDM | Date de durabilité minimale, « de préférence avant » | — |
| Déclassement | Produit vendu moins cher ou transformé car moins beau | — |
| Démarque, perte, casse | Ce qui est jeté | mouvement `waste` |
| DLC | Date limite de consommation, « jusqu'au » | `Lot.expiresAt`, `Product.shelfLifeDays` |
| Disponible | Stock physique moins stock réservé | `StockLevel.available` |
| DSO | Délai moyen de paiement des clients | `GET /api/receivables` |
| Échéance | Date à laquelle la facture doit être payée | `Invoice.dueDate` |
| Échu, en retard | Facture non payée après échéance | statut calculé `overdue` |
| Encours | Total dû par un client, € TTC | `outstanding` |
| Extra | Commande ponctuelle hors habitudes | — |
| FEFO | Premier expiré, premier sorti | `fefo_lots` dans `services/stock.py` |
| Franco | Montant à partir duquel le transport est offert | `Supplier.notes` |
| Geste commercial | Remise accordée pour réparer un problème | événement + `resolution` |
| HACCP | Méthode d'analyse des dangers en hygiène alimentaire | — |
| L'habituel | Ce que le client commande presque toujours | `GET /api/clients/{id}/usual` |
| Lot | Une arrivée d'un produit, avec sa date limite | `Lot` |
| Mareyeur | Premier acheteur du poisson à la criée, qui le prépare et l'expédie | `Supplier.tags` (`mareyeur`) |
| Marché public | Contrat d'achat d'une collectivité après appel d'offres | tag client `marche-public` |
| Mercuriale | Liste de prix du jour d'un fournisseur | `SupplierPrice` |
| MIN | Marché d'intérêt national (Rungis, Lyon, Marseille…) | — |
| Minimum de commande | Montant minimal pour commander à un fournisseur | `Supplier.minOrderAmount` |
| Plafond de crédit | Encours maximal autorisé | `Client.creditLimit` |
| Plan d'apurement | Échéancier pour rembourser une dette | événement `payment_plan` |
| Poids réel | Ce que pèse ce qui est livré | `OrderLine.preparedQty` |
| Prix liste, catalogue | Prix de base | `Product.price` |
| Prix négocié | Prix d'un produit pour un client | `ClientPrice` |
| Prospect | Client potentiel | `Client.status = "prospect"` |
| Relance | Rappel d'une facture impayée | événement `late_payment` |
| Réservé | Stock promis à des commandes confirmées | `StockLevel.reserved` |
| RHD | Restauration hors domicile | — |
| Rupture | Plus de stock disponible | alerte `insufficient_stock` |
| Substitution | Produit livré à la place d'un autre, avec accord | `OrderLine.substituteFor` |
| Tournée | Circuit d'un camion sur une zone, certains jours | `Route`, `RouteRun` |
| Zone | Secteur de livraison d'un client | `Client.zone` = `Route.zone` |
