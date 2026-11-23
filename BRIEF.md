# Hackathon voix — Brief participants

24 heures pour construire un agent vocal qui fait un vrai travail dans l'ERP d'un grossiste alimentaire.
Ce brief explique le contexte, ce qu'on vous donne, ce qu'on attend et comment vous y prendre.
L'installation est dans [SETUP.md](SETUP.md), le détail technique du kit dans le [README](README.md).
Un mot inconnu ? [GLOSSAIRE.md](GLOSSAIRE.md) · Une question ? [FAQ.md](FAQ.md)

---

## 1. Le contexte

Stockline construit le logiciel des grossistes alimentaires : marée, fruits et légumes, viande, crèmerie,
épicerie fine, boissons. Ces entreprises achètent la nuit à leurs fournisseurs et livrent le matin des centaines
de restaurants, poissonniers, cantines, hôtels et traiteurs.

Dans ce métier, presque tout passe par la voix :

- **Les clients** appellent pour commander (« comme d'habitude », à 2 h du matin), demander si le turbot sauvage
  est arrivé, se plaindre d'une livraison, discuter un prix.
- **Les fournisseurs** sont appelés pour comparer les prix, négocier, réserver un lot.
- **Les transporteurs** pour réserver la tournée la plus rapide au meilleur prix.
- **Les prospects** pour vendre et présenter les arrivages du jour.
- **Les collègues** : « il nous reste combien de bar ? », « ce client paie à combien de jours ? », « qu'est-ce
  qui se passe avec Ostréa ? ».

Chaque appel finit dans l'ERP : une commande, un prix, une réclamation, un paiement, une tournée. Aujourd'hui,
quelqu'un le retape à la main. Un bon agent vocal écoute, comprend le métier, agit dans l'ERP pendant l'appel et
répond comme le ferait le meilleur commercial de la boîte.

## 2. Le métier

Un grossiste alimentaire achète en gros chaque nuit, stocke quelques jours au froid et livre le matin des
centaines de professionnels, avec une marge faible et des produits qui périssent vite. Clients, prise de
commande, catalogue, prix, achats, stocks et lots, préparation, tournées, facturation et encours, réclamations,
saisons : chaque partie a son vocabulaire et ses pièges.

**Lisez la référence complète : [METIER.md](METIER.md).** C'est la meilleure source d'idées pour choisir votre
problème, et ce que votre agent doit comprendre pour être crédible.

## 3. Le défi

**Construisez l'agent vocal le plus utile possible sur cet ERP.**

Il n'y a pas de sujet imposé. Votre première étape est de **choisir un vrai problème** dans ce métier, et de
**justifier** pourquoi c'est celui-là : qui appelle qui, à quel moment, ce que ça coûte aujourd'hui, ce que
l'agent change. Partez du contexte ci-dessus et des données de votre entreprise.

On jugera votre agent sur trois axes :

| Axe | Ce que ça veut dire | Comment on le voit |
|---|---|---|
| **Smart** | Il connaît l'entreprise, le client, les produits, l'historique. Il ne se trompe pas, propose des alternatives, gère l'ambiguïté, agit juste dans l'ERP. | Il sait que ce chef refuse les substitutions, propose le bon remplaçant, retrouve « le loup » dans le catalogue, crée la bonne commande. |
| **Fast** | La réponse arrive vite, sans blanc gênant. | Délai fin de parole → premier son, nombre d'allers-retours modèle/outils, coût par appel. |
| **Natural** | On oublie que c'est une machine. | Phrases courtes, ton juste, interruptions gérées, chiffres dits à l'oral, relecture de commande, bruit de fond. |

Le jury testera votre agent **en direct**, sur des scénarios que vous ne connaîtrez pas à l'avance.

## 4. Ce qu'on vous donne

| Quoi | Détail |
|---|---|
| **Le kit (repo code)** | Un ERP complet et simple : clients, fournisseurs, produits, stocks et lots, pré-commandes, commandes, factures, paiements, encours, tournées, prix négociés, historique clients/fournisseurs, table de contexte. Backend Python (FastAPI), service IA Python, frontend React. |
| **Le guide de l'ERP** | [ERP.md](ERP.md) : chaque page, les cycles de vie, les règles métier (prix, stock, crédit), le modèle de données, les outils de l'agent et l'API. |
| **Un agent de base** | Une boucle agent simple, ~16 outils qui lisent et écrivent dans l'ERP, des clients LLM / STT / TTS interchangeables (OpenAI, Anthropic, Gemini, Deepgram, Soniox, ElevenLabs, Gradium, ou tout endpoint compatible OpenAI), un chat, un mode vocal push-to-talk et un mode commande vocale. |
| **La simulation d'appel** | Pas de numéro de téléphone : une page **Voix** à deux pistes audio. Maintenez Espace pour parler en tant que client, relâchez, l'agent répond. L'ERP se met à jour en direct sous vos yeux. |
| **Les données (dans votre zip, `./data`)** | Une entreprise fictive par équipe (24 en tout), avec ~100 clients, ses fournisseurs, son catalogue et 3 ans d'historique : commandes à rythmes variés, saisons, réclamations, retards de paiement, personas détaillés, documents de l'entreprise. |
| **Des clés** (déjà dans votre `.env`) | LLM (Anthropic), transcription (Soniox), voix (ElevenLabs), Jev (modèle de décision rapide). Avec des plafonds : surveillez votre consommation. |
| **De l'aide** | L'équipe Stockline sur place toute la nuit pour vous débloquer. |

Tout tourne aussi **sans clé** : des faux modèles (mock) répondent de façon déterministe et appellent le vrai ERP.
Utile pour développer et tester sans brûler vos crédits.

## 5. Démarrer

Chaque équipe reçoit un **zip** : le kit, les données de son entreprise (`./data`) et sa configuration (`.env`,
privé). **Suivez [SETUP.md](SETUP.md)** : installer Docker (à faire avant le hackathon), `make setup`, premier
appel, repo d'équipe. Comptez 20 à 30 minutes la première fois.

Ensuite :

1. Ouvrez **http://localhost:5173** et parcourez l'ERP : clients, commandes, stocks, Contexte. Ce sont les données
   de **votre** entreprise.
2. Page **Voix** : maintenez Espace et parlez comme un client. Regardez la transcription, les outils appelés,
   les temps de réponse, et l'ERP qui se met à jour.
3. Lisez `apps/ai/app/agent/loop.py` (la boucle) et `apps/ai/app/tools/` (les outils). C'est là que vous passerez
   la plupart de votre temps. Le plan du projet : [SETUP.md, Comment le projet est organisé](SETUP.md#comment-le-projet-est-organisé).

## 6. Comment s'y prendre

Un découpage qui marche bien sur 24 h :

1. **Choisir le problème (H0 → H2).** Lisez les fiches clients (`data/context/clients/`) et les documents de
   l'entreprise (`data/context/`). Qui appelle ?
   Pour quoi faire ? Qu'est-ce qui rate aujourd'hui ? Choisissez **un** cas d'usage et écrivez-le dans
   `DECISIONS.md` avec votre justification.
2. **Écrire vos scénarios de test (H2 → H3).** 5 à 10 appels réalistes, dont des cas difficiles : client
   ambigu, produit en rupture, client bloqué pour impayés, changement d'avis en cours d'appel, bruit. Ce sont
   vos tests de non-régression pour toute la nuit.
3. **Faire marcher le parcours de bout en bout (H3 → H8).** Vraies clés, vrai micro, un appel complet qui
   finit avec la bonne action dans l'ERP. Moche mais complet.
4. **Mesurer, puis améliorer (H8 → H20).** Notez la latence, le coût et les erreurs de chaque scénario.
   Attaquez le pire des trois axes en premier. Retestez après chaque changement.
5. **Préparer la démo (H20 → H24).** Gelez le code, enregistrez la vidéo, préparez les slides, répétez la démo
   live.

Notez chaque choix important dans `DECISIONS.md` au fil de l'eau (quoi, pourquoi, ce que vous avez essayé et
abandonné). Le jury le lira.

## 7. Pistes techniques

Ce ne sont pas des sujets, juste des directions qui font la différence. Nouveaux sur les agents LLM ? Lisez
[GUIDE-AGENTS.md](GUIDE-AGENTS.md) : boucle, outils, contexte, cache de prompt, choix du modèle, Jev, mesure, pièges.
Pour la voix (latence fin de parole → premier son, mesures du kit, techniques pour aller plus vite et sonner
naturel, et où les brancher) : [GUIDE-VOIX.md](GUIDE-VOIX.md).

**Pour aller vite**

- Modèles en streaming partout : STT avec transcriptions partielles, LLM en streaming, TTS phrase par phrase.
- Speech-to-speech (modèles audio natifs) pour supprimer des étapes.
- Paralléliser : lancer les outils indépendants ensemble, précharger la fiche du client dès le début de l'appel,
  anticiper l'appel d'outil suivant.
- Un petit modèle rapide pour les tours simples (Jev pour les décisions), un gros seulement quand il le faut.
- Du code déterministe pour ce qui n'a pas besoin d'un modèle : quantités, unités, dates.

**Pour être smart**

- Gestion du contexte : mettre dans le prompt seulement ce dont le tour a besoin.
- La **table de contexte** : chaque fait est rattaché à un client, un fournisseur, un produit ou une catégorie.
  Construisez dessus : recherche sémantique, graphe entre entités, mémoire de ce que l'agent apprend en appel.
- Retrieval sur l'historique : réclamations ouvertes, habitudes d'achat, prix négociés.
- Orchestration : un agent principal qui pilote des agents spécialisés, des outils composites (recherche + stock
  + prix client en un seul appel), un état de dialogue pour la prise de commande.

**Pour être naturel**

- Tours de parole courts, interruptions (barge-in), petites phrases d'attente pendant que les outils tournent.
- Relire la commande avant de valider, dire les chiffres et unités à l'oral (« douze kilos », « dix-huit euros
  cinquante »).
- Tester avec du bruit de fond (marché, cuisine, camion) et des accents.
- Le bon ton pour chaque interlocuteur : les fiches clients disent comment chacun parle.

## 8. Livrables et démo finale

À rendre avant la fin des 24 h :

- [ ] **Le repo GitHub** de votre équipe, qui tourne avec `make setup` une fois le dossier `data/` de votre zip
  remis en place (`data/seed/` n'est pas dans git).
- [ ] **`DECISIONS.md`** : le problème choisi et pourquoi, vos choix techniques, ce qui a marché et ce qui n'a
  pas marché, vos mesures (latence, coût, taux de réussite des scénarios).
- [ ] **Les slides** : 5 minutes maximum.
- [ ] **Une vidéo** de démo : 2 minutes maximum, un vrai appel de bout en bout.
- [ ] **La démo live** : le jury appelle votre agent, en direct, sur ses propres scénarios.

**Prix principal** : le meilleur agent sur smart, fast et natural, plus la pertinence du problème choisi.

**Prix spéciaux** :

| Prix | Pour |
|---|---|
| Le plus rapide | la plus faible latence fin de parole → premier son, mesurée en démo |
| Le moins cher | le plus faible coût par appel réussi |
| Le plus naturel | celui qu'on prend pour un humain |
| Le plus smart | celui qui gère le mieux les cas difficiles du jury |

## 9. Règles et aide

- Vous pouvez tout modifier dans le kit : ERP, outils, prompts, frontend, données. Gardez-le démarrable avec
  `make setup` pour que le jury puisse le lancer.
- Toutes les données sont fictives. Ne mettez jamais de clé API dans le repo : elles vont dans `.env`, qui est
  ignoré par git.
- Les clés ont un plafond. Développez avec les mocks, testez avec les vraies clés.
- Bloqués plus de 20 minutes ? Venez voir l'équipe Stockline. On est là pour ça.
- Installation et problèmes courants : [SETUP.md](SETUP.md). Architecture, configuration, ajouter un outil ou un
  fournisseur de modèle : [README](README.md).
