# FAQ

Les questions qu'on nous pose le plus. Un mot inconnu ? [GLOSSAIRE.md](GLOSSAIRE.md). Toujours bloqués après
20 minutes ? Venez voir l'équipe Stockline.

1. [Installation](#installation)
2. [Comprendre le projet](#comprendre)
3. [Coder](#coder)
4. [Clés et coûts](#cles)
5. [Livrables et démo](#livrables)

<a id="installation"></a>
## Installation

**Je n'ai jamais fait de Python / de Docker, je fais comment ?**
Pas besoin de savoir installer Python : Docker fait tout. Suivez [SETUP.md](SETUP.md) ligne à ligne, copiez les
commandes telles quelles. Pour coder, le Python du kit est simple (des fonctions, des dictionnaires) : partez d'un
outil existant dans `apps/ai/app/tools/` et modifiez-le. Un agent de code (Claude Code, Cursor…) avec
[AGENTS.md](AGENTS.md) vous fera gagner beaucoup de temps.

**Le terminal me dit `command not found` ou `No such file or directory`.**
Vous n'êtes sans doute pas dans le bon dossier. `pwd` affiche où vous êtes ; `cd voice-erp-kit` pour y entrer
(le dossier qui contient le `Makefile`). Sur Windows, utilisez le terminal **Ubuntu**, pas PowerShell. Les autres
erreurs courantes : [SETUP.md, « En cas de problème »](SETUP.md#en-cas-de-problème).

**Je suis sur Windows et ⌥Espace ne marche pas.**
Normal : Alt+Espace est un raccourci du système Windows (il ouvre le menu de la fenêtre). Allez sur la page
**Voix**, onglet **Commande** : maintenez Espace (ou le gros bouton micro), parlez, relâchez. C'est la même
commande vocale.

**Comment repartir de zéro ?**
- Les données de l'ERP sont abîmées par vos tests : `make reset` (recharge les données de départ, les services
  doivent tourner).
- Tout est cassé : `make clean` (supprime les conteneurs **et** la base), puis `make up`.
- Votre code est cassé : `git status` pour voir ce qui a changé, `git checkout -- <fichier>` pour revenir au dernier
  commit d'un fichier.

**J'ai modifié `.env` et rien ne change.**
`make restart` (sans Docker : Ctrl-C puis `make dev`). `curl localhost:4100/health` montre les fournisseurs actifs.

<a id="comprendre"></a>
## Comprendre le projet

**Que fait le kit, en une phrase ?**
Un ERP de grossiste (port 4000), un service IA qui le pilote avec des outils (port 4100) et une interface web (port
5173) avec un chat, une page Voix et une commande vocale. Plan détaillé : [README.md](README.md) et [TECH.md](TECH.md).

**Quel document lire en premier ?**
[BRIEF.md](BRIEF.md) (le défi), puis [METIER.md](METIER.md) si vous ne connaissez pas le métier. Ensuite
[GUIDE-AGENTS.md](GUIDE-AGENTS.md) (agents LLM) ou [GUIDE-VOIX.md](GUIDE-VOIX.md) (vitesse, naturel) selon votre
angle d'attaque.

**Qu'est-ce que le mode `mock` ?**
De faux fournisseurs, gratuits et hors ligne. L'agent mock appelle vraiment l'ERP, mais il ne comprend rien ; le STT
mock entend toujours la même phrase. Parfait pour installer et coder l'interface, inutile pour juger l'agent.

**Que se passe-t-il pendant un tour vocal ?**
Votre voix part au STT pendant que vous parlez (le texte s'affiche en direct), le texte final part à l'agent, qui
appelle des outils de l'ERP, puis sa réponse est lue par le TTS phrase par phrase.
Détail : [GUIDE-VOIX.md §1](GUIDE-VOIX.md#anatomie).

<a id="coder"></a>
## Coder

**Où est-ce que je code ?**

| Modifiez | Pour |
|---|---|
| `apps/ai/app/agent/prompts.py` | ce que l'agent sait et comment il parle (règles, ton, mode vocal) |
| `apps/ai/app/tools/*.py` | ce que l'agent peut faire dans l'ERP (nouveaux outils, outils plus rapides) |
| `data/context/*.md` | le savoir de votre entreprise donné à l'agent |
| `apps/ai/app/agent/loop.py` | la boucle de l'agent (ordre des étapes, parallélisme, limites) |

| Laissez tel quel (sauf raison précise) | Pourquoi |
|---|---|
| `apps/ai/app/clients/` | les connexions aux fournisseurs : déjà réglées |
| `apps/ai/app/services/utterance.py` | la transcription en direct : fragile, déjà optimisée |
| `apps/ai/app/agent/sanitize.py` | nettoie l'historique pour que le fournisseur l'accepte |
| `apps/ai/app/schemas/`, `apps/ai/app/routers/` | le contrat avec l'interface : changez-le et le web casse |

**Comment savoir que mon changement a marché ?**
- `make chat` : parlez à l'agent dans le terminal, sans micro. Il affiche les outils appelés, le temps et les tokens.
- Page **Voix** (http://localhost:5173) : un vrai tour vocal, avec les mesures de latence.
- `make logs` : les erreurs Python s'y affichent (Ctrl-C pour sortir).
- `curl localhost:4100/tools` : la liste des outils que l'agent voit. Le vôtre doit y être.
Le code se recharge tout seul à l'enregistrement (l'historique de la conversation vocale est alors perdu).

**Comment ajouter un outil ?**
Une fonction `@tool` dans `apps/ai/app/tools/`, importée dans `tools/__init__.py`. Exemple pas à pas :
[TECH.md, « Les outils »](TECH.md#outils) (section 5.3 pour un outil simple, 5.4 pour un outil composite).

**J'ai besoin d'une action que l'ERP ne sait pas faire.**
Ajoutez d'abord l'endpoint dans le backend (`apps/backend/app/services/` + `routers/`), puis l'outil qui l'appelle.
Exemple de bout en bout : [TECH.md 2.6](TECH.md#ajouter-endpoint). Les règles métier restent dans le backend.

**`git commit` refuse / `git push` me demande un mot de passe.**
- Commit refusé (« Please tell me who you are ») : une fois pour toutes,
  `git config --global user.name "Prénom Nom"` et `git config --global user.email "vous@exemple.fr"`.
- Push : GitHub n'accepte plus le mot de passe du compte. Le plus simple : `gh auth login` (outil GitHub CLI), ou
  créez un *personal access token* dans GitHub (Settings → Developer settings) et collez-le à la place du mot de passe.

<a id="cles"></a>
## Clés et coûts

**Comment voir la consommation / le coût ?**
- Chaque réponse du chat (`POST /ai/chat`) se termine par un événement `done` qui contient `usage` : tokens
  d'entrée, de sortie, et de cache (`cache_read_input_tokens` lus, `cache_creation_input_tokens` écrits).
- `make chat` l'affiche après chaque réponse.
- La session vocale ne renvoie pas `usage` : loggez-le si vous en avez besoin.
- Les tableaux de bord des fournisseurs sont côté organisateurs : demandez-nous si vous voulez un chiffre global.

**Je n'ai plus de crédits / erreur 401 / 429.**
- **401** : clé refusée. Vérifiez-la dans `.env` (pas d'espace, pas de guillemets), puis `make restart`.
- **429** ou « quota » : trop de requêtes ou plafond atteint. Attendez une minute ; si ça persiste, venez nous voir.
- En attendant : repassez en `mock` pour coder, et gardez les vraies clés pour tester.

**Puis-je changer de modèle ?**
Oui, dans `.env` : `LLM_MODEL=claude-sonnet-5-5` (défaut, équilibré), `claude-haiku-5-5` (le plus rapide et le
moins cher) ou `claude-opus-5-5` (le plus fort, plus lent). Puis `make restart`. Vérifiez vos scénarios après :
plus rapide mais faux ne gagne pas.

**Puis-je utiliser un autre fournisseur ?**
Le code en supporte d'autres (OpenAI, Gemini, Deepgram, Gradium, tout endpoint compatible OpenAI), mais nous ne
fournissons de clés que pour **Anthropic** (LLM), **Soniox** (STT), **ElevenLabs** (TTS) et **Jev**. Avec votre
propre clé, c'est permis : dites-le dans `DECISIONS.md`.

<a id="livrables"></a>
## Livrables et démo

**Que dois-je rendre ?**
Le repo GitHub, `DECISIONS.md`, les slides (5 min), une vidéo (2 min) et la démo live :
[BRIEF.md §8](BRIEF.md#8-livrables-et-démo-finale).

**Comment montrer que notre agent est rapide ?**
Page **Voix** : colonnes **Total** et **Perçu** de chaque tour. Notez médiane et pire cas, avant/après chaque
changement, dans `DECISIONS.md`. Méthode : [GUIDE-VOIX.md §8](GUIDE-VOIX.md#plan).

**Le jury pourra-t-il lancer notre projet ?**
Oui s'il démarre avec `make setup` une fois le dossier `data/` remis en place. Testez-le sur une copie fraîche avant
de rendre. Ne mettez jamais `.env` dans le repo.

**Mon outil fait planter le démarrage (TypeError `@tool ...`).**
Lisez le message : il dit quoi corriger (`async def` manquant, premier paramètre pas `ctx`, paramètre sans type, docstring absente ou nom déjà pris).
