# Plan d’implémentation des suggestions et appels sortants

**Branche** `mohamed-amine/suggestions-proactives` · **Périmètre** Le Fournil Occitan

L’agent propose une offre qui a du sens pour ce client au bon moment. Le même moteur alimente la prise de commande, un appel sortant et, si personne ne décroche, un message de suivi. La première version tourne entièrement dans la simulation Voix du hackathon. Le jury choisit de décrocher ou de laisser sonner et peut vérifier les actions dans l’ERP.

## 1. Ce que le jury pourra essayer

- **Appel entrant.** Le boulanger passe sa commande normalement. Une fois sa demande traitée et avant la relecture finale, il entend par exemple « Au fait, votre beurre de tourage 82 % est en promo jusqu’au 30 novembre. Je vous donne le prix au carton ? » Le mot « votre » suppose un achat antérieur de cette référence. Un prix par carton suppose un conditionnement vérifié.
- **Appel sortant.** Un membre de l’équipe prépare une campagne de démo sur une promo vérifiée. L’agent choisit le client éligible à partir de ses achats et déclenche la sonnerie. Le jury décroche et entend « Bonjour, c’est l’assistant vocal du Fournil Occitan. Je vous appelle pour la promo sur le beurre de tourage que vous prenez pour vos viennoiseries. Vous avez trente secondes ? » Le lien avec les viennoiseries doit venir de la fiche du client ou d’un usage vérifié du produit. L’offre et son prix viennent après l’accord pour continuer. L’agent peut ensuite saisir un brouillon, le relire et le faire confirmer dans l’ERP.
- **Appel manqué.** Le jury laisse sonner sur une deuxième tentative, prévue pour un autre client éligible. Après le délai, la page affiche le SMS simulé et le résultat de la tentative. Le message peut dire « Bonjour, ici Le Fournil Occitan. Le beurre de tourage 82 % est en promotion jusqu’au 30 novembre. Vous pouvez nous rappeler si vous souhaitez en profiter. » L’agent revérifie l’offre avant de produire le message. Ces scripts sont des exemples de ton. Les dates, les prix et les clients de la démo seront confirmés avec le pack de données.

## 2. Briques existantes à réutiliser

| Besoin | Point d’appui dans le dépôt | Travail prévu |
|---|---|---|
| Habitudes d’achat | [Service clients](../../apps/backend/app/services/clients.py), `usual_basket` et détail client | Récupérer les achats habituels des 60 derniers jours, leur fréquence et la dernière date d’achat. Pour repérer un complément, examiner un nombre borné de commandes effectivement livrées ou facturées. |
| Fiche de l’appel | [Contexte client](../../apps/ai/app/agent/call_context.py) | Utiliser le préchargement et ajouter une vue structurée des données utiles. Le champ `active_promos` est encore marqué TODO. Les commandes récentes de cette fiche sont actuellement formatées pour l’oral. |
| Prix et promotions | [API de tarification](../../apps/backend/app/routers/pricing.py), [détection de promo](../../apps/ai/app/tools/insight.py) | Réutiliser la résolution ERP avec le client, la quantité et la date de prix applicables. Réutiliser `promo_of` pour reconnaître la règle datée réellement appliquée. |
| Ton et substitutions | [Règles « bon vendeur »](../../apps/ai/app/agent/rules_sales.py) | Garder la priorité aux préférences et aux restrictions existantes. Une suggestion indépendante et un remplacement restent deux décisions distinctes. |
| Dates, unités et écriture | [Livraison](../../apps/ai/app/tools/delivery.py), [relecture et chiffrage](../../apps/ai/app/tools/order_review.py), [outils de commande](../../apps/ai/app/tools/orders.py) | Réutiliser le calcul de la prochaine tournée, la conversion et la validation du panier. Vérifier les mêmes données à l’acceptation et avant confirmation. |
| Voix et journal | [Session vocale](../../apps/ai/app/services/voice_session.py), [page Voix](../../apps/web/src/pages/voice/index.tsx), [événements clients](../../apps/backend/app/services/client_events.py) | Réutiliser le premier message vocal, la synthèse, l’interruption, les événements ERP et le canal `sms` prévu au schéma. L’envoi et sa déduplication demandent leur propre état. |

## 3. Construire un moteur de sélection commun

Ajouter un service de lecture côté IA, par exemple `agent/recommendations.py`. Il propose au plus une offre pour un client, un canal et, si connue, une commande en cours. Il renvoie un objet structuré ou aucune offre. L’objet contient un identifiant stable d’offre, référence et libellé produit, motif vérifiable, source de ce motif, prix HT, unité, quantité de référence, règle tarifaire et échéance si applicable. Garder les justifications détaillées pour l’équipe dans l’interface. L’oral reçoit seulement les faits utiles au client.

1. **Trouver des candidats.** Commencer par les références déjà achetées qui font l’objet d’une vraie promotion et les compléments achetés avec le panier. Pour les nouveautés, ajouter une date de mise au catalogue explicite, nullable pour les anciens produits, ou utiliser une sélection de lancement datée et validée par l’équipe. Le schéma `Product` actuel n’a pas de date de mise au catalogue. Ni une première réception ni l’absence d’achat par ce client ne suffisent à qualifier un produit de nouveau.
2. **Filtrer avant de classer.** Écarter les produits inactifs, indisponibles pour au moins un conditionnement, déjà dans la commande en cours ou incompatibles avec les préférences. Suspendre la suggestion en cas de compte bloqué, de réclamation ouverte prioritaire, de refus récent de l’offre ou de contexte insuffisant. En sortant, vérifier en plus que le contact est autorisé sur le canal, que sa plage horaire est ouverte et qu’il respecte le délai entre deux sollicitations. Conserver le parcours d’une demande volontaire du client.
3. **Classer d’abord la pertinence.** Priorité initiale à une promo applicable sur un achat habituel, puis à une nouveauté dont l’usage correspond à des achats attestés, puis à un complément observé dans les paniers. Fréquence et récence départagent les produits d’une même catégorie. Une alternative refusée ne doit jamais revenir déguisée en suggestion. Calibrer la fréquence avec le pack avant d’affirmer « vous en prenez régulièrement ». Deux achats vérifiés constituent un seuil de présélection à tester. Préférer le fait précis « vous en avez commandé la semaine dernière » quand il est établi.
4. **Vérifier juste avant de parler.** Utiliser la date métier de l’ERP pour les règles de prix et les tournées, en tenant compte de l’échéance réelle de la promo. Une remise de groupe permanente et un prix négocié qui l’emporte sur la promo se présentent comme le tarif du client. Si le seuil de volume est nécessaire, le dire ou écarter l’offre. Revalider au moment de l’ajout avec la quantité réellement demandée. À défaut de preuve fraîche sur le prix, le stock ou le créneau, poursuivre l’appel sans cette offre et supprimer le suivi sortant devenu caduc.

Limiter la première version à un petit ensemble de candidats issu de l’historique et préparer ces lectures en arrière-plan, en parallèle du chargement de la fiche et du panier. Si elles sont encore en cours au moment de répondre, le tour principal passe immédiatement. Le modèle reformule une offre autorisée en une phrase. La sélection, le prix et l’autorisation d’en parler viennent du code.

## 4. Placer la suggestion dans la conversation

Laisser la conversation déterminer **où** placer l’unique suggestion spontanée. Stocker dans la session le candidat, l’offre en attente de réponse et l’état de la proposition. Pour une reprise après reconnexion, restaurer cet état avec la conversation en cours. Les refus d’une offre et les résultats sortants se conservent côté ERP pour les appels suivants.

| Moment | Comportement attendu |
|---|---|
| Accueil entrant ou demande encore en cours | Identifier le client, écouter et traiter son besoin. |
| Demande résolue ou juste avant la relecture | Si une offre a un lien clair avec le panier, l’insérer en une phrase. Si une question métier attend déjà une réponse, reporter la suggestion. |
| Réclamation, confusion sur les unités, urgence, rupture en cours de résolution ou « c’est tout, merci » | Écarter la suggestion pour ce tour. Une clôture explicite termine l’appel. |
| « Non merci » ou interruption | Reprendre le sujet du client. Garder le refus de cette offre pour la campagne. Après interruption, tracer ce qui a effectivement été joué et écarter toute acceptation ambiguë. |
| « Oui, ajoutez-en deux cartons » | Rattacher le oui à la proposition en attente, vérifier produit et quantité, revalider prix, stock et date, modifier le brouillon existant puis relire le nouveau panier. |
| « Oui », « dites-moi le prix » ou « oui mais… » | Distinguer l’autorisation d’en parler, l’ajout de la ligne et la confirmation de l’ensemble. Demander une précision si le référent ou la quantité manque. |

Autoriser une suggestion spontanée au maximum par appel entrant. Le client peut ensuite poser des questions sur l’offre, ou demander explicitement d’autres suggestions. L’agent prononce uniquement le prix et le bénéfice vérifiés. Les coûts d’achat, litiges et scores de ciblage restent dans les données internes. Compter la suggestion à partir de la lecture audio commencée et associer une acceptation à une offre effectivement exposée et non interrompue de façon ambiguë.

## 5. Orchestrer l’appel sortant et le SMS

### Simulation pour le jury

- Ajouter un petit panneau **Appels sortants** sur la page Voix. Il montre l’offre réelle, les clients éligibles et la raison de sélection, par exemple « achète déjà cette référence ». Un bouton lance la campagne de démonstration. Le service choisit et planifie les tentatives. Le navigateur affiche la tentative et transmet l’action **Décrocher**. En l’absence de réponse du jury, la décision d’expiration vient du serveur. Un délai de démo court et configurable rend la scène facile à répéter.
- À la prise d’appel, vérifier à nouveau l’offre et reprendre la session Voix avec le client et l’offre de la tentative côté serveur. Jouer l’ouverture avec la synthèse existante dès le décrochage. Le client entend l’identité du Fournil et peut refuser, poser une question ou commander. Sur un refus ou une réponse, aucun SMS de suivi automatique.
- Sur **non-réponse**, vérifier la disponibilité, le prix si le texte le mentionne, l’échéance et l’autorisation SMS. Générer un message court à partir de champs validés et d’un modèle de texte. L’afficher dans une boîte de sortie de démo sous le libellé **SMS simulé**. Le journal ERP marque le canal, l’offre et le résultat. Si le SMS a été annulé, afficher la raison côté équipe.
- Ajouter deux interrupteurs éteints par défaut, par exemple `TEAM_RECOMMENDATIONS` et `TEAM_OUTBOUND_DEMO`. Le second active les routes et le panneau de simulation. Tous les accès à un fournisseur réel relèvent d’une configuration séparée.

### État et non-duplication

Prévoir une route de prévisualisation de la campagne, une route de lancement, une lecture de l’état de la tentative et une action de décrochage. Attacher la session vocale à l’identifiant de la tentative après le décrochage validé. Le client et l’offre viennent de cette tentative côté serveur. La page peut lire l’état à intervalle court pour la démo.

Stocker côté ERP les tentatives et la boîte de sortie dans SQLite. Garder les événements CRM pour la lisibilité de l’historique. Une clé unique par offre, campagne et contact évite les répétitions au rechargement. Pour un lot de démo, limiter le nombre de tentatives et les traiter l’une après l’autre.

```text
planifiée → sonne → décrochée → terminée (intéressé, refus, panier confirmé…)
                  ↘ sans réponse → SMS à préparer → simulé / annulé / échec
                  ↘ échec technique / annulation
```

Décrochage et expiration concourent pour la même transition en base. Utiliser une mise à jour conditionnelle, une échéance persistée et une insertion de SMS unique par tentative dans la même transaction de décision. Traiter les tâches dues avec un service côté serveur, qui peut reprendre les tentatives à échéance après redémarrage. Un événement tardif ou dupliqué ne doit ni ouvrir une seconde session ni renvoyer un message. Enregistrer le résultat fournisseur. Pour un envoi réel, transmettre la même référence d’idempotence si le fournisseur la prend en charge. Après un résultat incertain, rapprocher l’état fournisseur avant toute nouvelle tentative. Garder une distinction visible entre SMS simulé, accepté pour envoi et livré.

### Extension vers un vrai numéro

Introduire un adaptateur de téléphonie et de SMS seulement après validation de la simulation. La téléphonie doit relayer l’audio entre l’appel et la session vocale avec interruption, gérer le format audio du fournisseur, et signaler les fins d’appel. Vérifier la signature des notifications, dédupliquer les événements fournisseur et confirmer le statut final avant d’autoriser le SMS. Séparer les états occupé, échec, refus et messagerie de la non-réponse selon les états effectivement fournis. Si un humain répond à l’approche de l’expiration, le serveur attend un état final cohérent avant l’envoi.

Limiter les premiers vrais essais à des contacts de test autorisés et à une seule tentative à la fois. Pour déployer chez le Fournil, prévoir les préférences par canal, les horaires autorisés, l’opposition aux sollicitations, les quotas et une commande d’arrêt de campagne. L’historique d’achat aide à sélectionner une offre. Il ne constitue pas une autorisation de contacter quelqu’un.

## 6. Ordre de réalisation et points de passage

| Lot | Travail | Fini quand |
|---|---|---|
| **A · Sélection** | Moteur et règles de prix, avec des données de test représentatives du pack. Commencer par la promo réellement applicable sur un produit déjà acheté. | Même produit, deux tarifs négociés différents. L’offre n’est présentée comme une promo qu’au client auquel la règle est réellement appliquée. |
| **B · Appel entrant** | État de la suggestion, bon moment, refus, acceptation et raccord avec la commande. | Le client peut poser une question, couper l’agent ou refuser. Le parcours sans suggestion marche aussi vite qu’avant à la variation de mesure près. |
| **C · Appel sortant simulé** | Campagne bornée, stockage des tentatives, sonnerie, reprise de session, SMS simulé et journal ERP. | Décrocher lance le dialogue. Laisser sonner donne un seul SMS, y compris après rechargement. |
| **D · Nouveautés et compléments** | Donnée de lancement datée, rapprochement par usage, historique de co-achat. | Une vraie nouveauté compatible ressort. Un produit ancien ou sans lien faussement qualifié de nouveau est écarté. |
| **E · Intégration réelle** | Adaptateur téléphonie, audio bidirectionnel et livraison des SMS, validation sur contacts de test. | Retour fournisseur confirmé et corrélé à chaque tentative. Préférences et garde-fous testés avant toute ouverture à des clients. |

Pour une démo courte, réaliser A avec un seul type d’offre, puis B et C. Réutiliser la promo de démo de l’équipe uniquement si l’historique, le tarif, le stock et le contact du client choisi passent les vérifications. Documenter tout ajout de données fictives.

### Coordination dans l’équipe

Mohamed Amine porte la voix et les scénarios. Daycem valide le ton, les préférences, la logique de sélection commerciale et les cas de rupture. Youssef valide les points d’intégration au préchargement, au super-outil produit et au rejeu. Amine Khalil valide l’ajout au panier et l’accord avant confirmation. Les extensions du protocole WebSocket, des données ERP et de l’interface Voix restent à convenir avec les propriétaires avant modification du code.

## 7. Tests de réception

- **Prix et pertinence.** Vérifier un bon client, un prix négocié prioritaire, une promo expirée, un seuil de volume, une nouveauté non pertinente, un produit déjà au panier et du stock épuisé pendant l’appel. Vérifier aussi un client qui refuse précisément la référence proposée comme alternative.
- **Conversation.** Rejouer commande normale, refus d’offre, réclamation, « merci », interruption au milieu de la phrase et « oui, mais deux cartons ». Contrôler le brouillon, les quantités, le tarif et la confirmation effective dans l’ERP. Rejouer les scénarios habituels avec les deux interrupteurs désactivés puis avec le parcours entrant actif.
- **Sortant.** Tester décroché, refus, non-réponse, échec technique, absence d’autorisation SMS, offre expirée pendant la sonnerie, double notification et décrochage proche de l’expiration. Redémarrer le service avec une tentative en cours. Vérifier la trace ERP et l’unicité du message.
- **Mesures.** Utiliser `scripts/run_scenarios.py --voice` et un vrai passage au micro pour comparer la latence perçue et le premier son utile avec la version de départ. Suivre séparément offres prononcées, acceptées, commandes confirmées avec la ligne et SMS simulés. Faire écouter des appels avec et sans suggestion à un membre de l’équipe pour vérifier le ton et le moment choisi.

**Démo de 90 secondes.** Faire entendre une suggestion bien placée dans une commande entrante. Montrer le bon qui ne bouge qu’après la demande d’ajout. Lancer ensuite la campagne et inviter le jury à laisser sonner. Afficher le SMS simulé et sa trace dans l’ERP. Préparer une variante où le jury décroche et prend la conversation à son compte.
