# Installation pas à pas

Un mot inconnu ? [GLOSSAIRE.md](GLOSSAIRE.md) · Une question ? [FAQ.md](FAQ.md)

Ce guide vous amène de zéro à un premier appel vocal qui modifie l'ERP. Comptez **20 à 30 minutes** la première
fois, dont 10 à 15 minutes d'attente (téléchargements). Faites l'étape 1 **avant** le hackathon si vous pouvez.

Vous avez reçu un fichier `team-XX.zip`. Il contient un dossier `voice-erp-kit/` :

| Quoi | Où | Note |
|---|---|---|
| Le kit (ERP, service IA, interface) | `voice-erp-kit/` | le code que vous allez modifier |
| Les données de **votre** entreprise | `voice-erp-kit/data/` | clients, produits, 3 ans d'historique, documents |
| La configuration et vos clés API | `voice-erp-kit/.env` | **privé** : ne le partagez pas, ne le committez pas. Zip reçu la veille : pas encore de clés, voir [Clés réelles ou modèles simulés](#clés-réelles-ou-modèles-simulés) |
| Votre fiche équipe | `voice-erp-kit/TEAM.md` | le nom de votre entreprise |

Il n'y a rien d'autre à télécharger ni à cloner : tout est dans le zip.

---

## Étape 1 — Installer Docker (≈ 10 min, à faire avant)

Docker fait tourner les trois services (ERP, IA, interface) sans rien installer d'autre.

### Mac

1. Installez les outils de développement Apple (`make`, `git`) : dans un terminal, `xcode-select --install`, puis
   « Installer ». S'il répond « already installed », c'est bon.
2. Téléchargez [Docker Desktop](https://www.docker.com/products/docker-desktop/) (puce Apple ou Intel : le site
   choisit pour vous). Environ 600 Mo.
3. Ouvrez le `.dmg`, glissez Docker dans Applications, lancez-le. Acceptez les autorisations (mot de passe Mac).
4. Attendez que la baleine en haut de l'écran arrête de clignoter.
5. Dans un terminal : `docker run hello-world`. Vous devez voir « Hello from Docker! ».

### Windows

Sur Windows, tout se fait **dans WSL** (un Linux intégré à Windows) : `make` et les scripts du kit ne marchent ni
dans PowerShell ni dans l'invite de commandes. Il faut les droits administrateur pour installer WSL.

1. Dans PowerShell **administrateur** : `wsl --install`, puis redémarrez. Au redémarrage, Ubuntu s'ouvre et vous
   demande un nom d'utilisateur et un mot de passe (pour Linux, choisissez-les).
2. Installez [Docker Desktop](https://www.docker.com/products/docker-desktop/). Pendant l'installation, gardez
   « Use WSL 2 ». Lancez-le, puis Settings → Resources → WSL integration → activez **Ubuntu**.
3. Ouvrez le terminal **Ubuntu** (menu Démarrer), puis : `sudo apt update && sudo apt install -y make unzip curl git`.
4. Vérifiez dans Ubuntu : `docker run hello-world`.

À partir d'ici, sur Windows, **toutes les commandes se tapent dans le terminal Ubuntu**, et le projet vit dans le
Linux (`~/voice-erp-kit`), pas dans `C:\` : c'est beaucoup plus rapide et le rechargement automatique du code marche.
Pour ouvrir le projet dans VS Code : `code .` depuis Ubuntu (extension « WSL »).

### Linux

Installez [Docker Engine](https://docs.docker.com/engine/install/) et le plugin compose, ajoutez-vous au groupe
`docker` (`sudo usermod -aG docker $USER`, puis reconnectez-vous), installez `make`, `unzip`, `curl` et `git`.

### Réglage pour tous

Docker Desktop → Settings → Resources : donnez au moins **4 Go de RAM**.

> Pas les droits administrateur ? Sur Mac ou Linux, passez à [Sans Docker](#sans-docker). Sur Windows, WSL exige
> ces droits : venez voir l'équipe Stockline.

---

## Étape 2 — Lancer le projet (5 à 10 min la première fois)

```bash
# Mac / Linux : depuis le dossier où est le zip.
# Windows : dans Ubuntu, copiez d'abord le zip dans Linux :
#   cp /mnt/c/Users/<vous>/Downloads/team-XX.zip ~ && cd ~
unzip team-XX.zip
cd voice-erp-kit
make setup
```

`make setup` vérifie Docker et les ports, construit les images puis démarre les services. Il s'arrête quand tout
répond. Vous verrez :

```
  ✓ api, ai and web are up

Ready → http://localhost:5173
```

La première fois, il télécharge 1 à 2 Go puis construit les images : c'est l'étape longue. Vous pouvez le relancer
sans risque s'il s'arrête. Les fois suivantes, `make up` démarre en quelques secondes.

**Vérifiez que tout marche :**

| Ouvrez | Vous devez voir |
|---|---|
| http://localhost:5173 (attendez ~10 s après « Ready ») | l'ERP, avec le nom de **votre** entreprise en haut à gauche |
| http://localhost:4000/docs | la doc de l'API de l'ERP |
| http://localhost:4100/health | `"ok": true` et les fournisseurs actifs (`llm`, `stt`, `tts`) ; `mock` = modèle simulé |

---

## Étape 3 — Premier appel (≈ 5 min)

1. Dans l'ERP, ouvrez **Voix** (menu de gauche, section IA).
2. Autorisez le micro quand le navigateur le demande (Chrome conseillé).
3. **Maintenez Espace**, parlez comme un client (« Bonjour, c'est le restaurant…, vous avez quoi ce matin ? »),
   relâchez. Pendant que vous parlez, vos mots s'affichent en direct (en gris italique tant qu'ils sont provisoires) ;
   au relâchement, le texte final part à l'agent. Vous pouvez aussi taper la phrase au lieu de parler.
4. Regardez : la transcription, les outils appelés par l'agent, la réponse dite à voix haute, et à droite l'ERP
   qui se met à jour (en violet : ce que l'agent a fait).
5. Testez aussi **⌥ Espace** (Alt + Espace) n'importe où dans l'ERP : une commande vocale en une phrase
   (« crée une commande pour … »).

### Clés réelles ou modèles simulés

Tout est réglé dans `.env` (un seul fichier pour les trois services) :

- **Zip reçu le jour J** : vos clés sont déjà dans `.env`, les fournisseurs choisis sont actifs.
- **Zip reçu la veille** : `.env` utilise les modèles simulés (`mock`), sans clé. Le jour J, on vous donne votre
  fichier `.env` : remplacez celui du dossier par le nouveau (gardez le nom `.env`), puis `make restart`.

Avec les modèles simulés, tout marche hors ligne et l'agent appelle le vrai ERP, mais :

- le faux LLM ne comprend que quelques phrases simples ;
- la fausse transcription entend **toujours** la même phrase (« Bonjour, il vous reste du bar ? »), quoi que vous
  disiez : tapez votre texte pour tester autre chose ;
- c'est le navigateur qui lit la réponse à voix haute.

C'est utile pour développer sans consommer de crédits. Pour y revenir à tout moment : `LLM_PROVIDER=mock`,
`STT_PROVIDER=mock`, `TTS_PROVIDER=mock`, puis `make restart`.

### Changer de modèle ou de voix

Votre `.env` liste en bas, en commentaire, toutes les clés de votre équipe. Pour changer de fournisseur, modifiez
le `*_PROVIDER` et copiez la clé correspondante dans le `*_API_KEY` juste en dessous, puis `make restart`. Exemple :

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=              # vide = le modèle par défaut du fournisseur
LLM_API_KEY=<la valeur de la ligne # ANTHROPIC_KEY=…>
```

| Rôle | Fournisseurs | Variables |
|---|---|---|
| LLM (le cerveau) | `openai`, `anthropic`, `gemini`, `openai-compatible`, `mock` | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |
| Transcription (STT) | `soniox`, `deepgram`, `gradium`, `openai`, `mock` | `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY` |
| Synthèse vocale (TTS) | `elevenlabs`, `gradium`, `openai`, `mock` | `TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`, `TTS_API_KEY` |
| Jev (modèle de décision, optionnel) | TypeSafe AI | `JEV_API_KEY` |

Jev n'est pas un LLM : il répond vite à des questions fermées (choix, score, oui/non) et s'utilise **à côté** du
LLM. L'agent de base ne s'en sert pas : c'est à vous de le brancher (voir
[apps/ai/README.md](apps/ai/README.md#jev-decision-model)). Modèles et voix par défaut, et le détail de chaque
variable : [README, Configuration](README.md#configuration-one-env).

---

## Étape 4 — Votre repo d'équipe (≈ 3 min)

```bash
git init -b main && git add . && git commit -m "start"
```

Créez un repo **privé** sur GitHub, poussez-y le code (`git remote add origin … && git push -u origin main`), puis
ajoutez les comptes du jury en collaborateurs. C'est votre livrable.

`.env` (vos clés) et `data/seed/` (les données, trop lourdes pour GitHub) sont ignorés par git, exprès.

---

## Étape 5 — Coder

- Les fichiers à lire en premier : `apps/ai/app/agent/loop.py` (la boucle de l'agent) et `apps/ai/app/tools/`
  (ce que l'agent peut faire dans l'ERP). Le plan du projet est juste en dessous.
- Le code se recharge tout seul quand vous enregistrez. Après un changement de `.env` : `make restart`.
- Vous utilisez un agent de code (Claude Code, Cursor…) ? Donnez-lui [AGENTS.md](AGENTS.md).
- À lire : [BRIEF.md](BRIEF.md) (le défi), [METIER.md](METIER.md) (le métier), [ERP.md](ERP.md) (l'ERP).

### Comment le projet est organisé

```
voice-erp-kit/
├── apps/
│   ├── backend/app/     l'ERP (Python, FastAPI, SQLite), port 4000
│   │   ├── routers/       les routes de l'API (/api/clients, /api/orders…)
│   │   ├── services/      les règles métier : prix, stock, crédit, factures
│   │   └── schemas/       la forme des données (Pydantic) = le contrat de l'API
│   ├── ai/app/          le service IA (Python, FastAPI), port 4100
│   │   ├── agent/         loop.py (la boucle de l'agent), prompts.py (ce que le modèle lit)
│   │   ├── tools/         les outils de l'agent (@tool) : chercher un produit, créer une commande…
│   │   ├── clients/       un fichier par fournisseur LLM / STT / TTS (+ Jev)
│   │   └── services/      voice_session.py (l'appel vocal), command.py (⌥ Espace)
│   └── web/src/         l'interface (React), port 5173 : pages/ et composants ui/
├── data/                votre entreprise : seed/ (données de l'ERP), context/ (documents lus par l'agent)
├── packages/shared/     les types TypeScript partagés par l'interface
├── docker/, docker-compose.yml, Makefile, scripts/   le lancement (vous n'avez pas à y toucher)
└── .env                 la configuration et vos clés
```

Le chemin d'un appel : l'interface envoie le son au service IA → transcription (STT) → l'agent (LLM) appelle des
outils → chaque outil est un appel HTTP à l'ERP → la réponse est lue à voix haute (TTS) et l'ERP se met à jour à
l'écran. Les règles métier ne vivent que dans l'ERP. Schéma : [README, Architecture](README.md#architecture) ; détails
et exemples pour étendre le kit : [TECH.md](TECH.md).

| Vous voulez… | Regardez |
|---|---|
| que l'agent réponde plus vite | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/`, `agent/loop.py` |
| qu'il en sache plus sur le client | `agent/prompts.py`, `tools/context.py`, `data/context/` |
| lui donner une nouvelle action dans l'ERP | une route dans `apps/backend/app/routers/` + un outil dans `apps/ai/app/tools/` ([README, Add a tool](README.md#add-a-tool)) |
| changer l'interface | `apps/web/src/pages/`, composants de `apps/web/src/ui/` ([DESIGN.md](DESIGN.md)) |

### Les commandes utiles

| Commande | Effet |
|---|---|
| `make up` / `make down` | démarrer / arrêter (les données sont gardées) |
| `make restart` | appliquer un changement de `.env` |
| `make logs` | voir les logs des 3 services (Ctrl-C pour sortir) |
| `make reset` | remettre les données de l'ERP à zéro (efface vos modifications) |
| `make rebuild` | après avoir ajouté une dépendance Python ou npm |
| `make chat` | parler à l'agent dans le terminal |
| `make clean` | tout supprimer, base de données comprise (`make setup` pour repartir) |
| `make help` | toutes les commandes |

`make test`, `make types` et `make check` tournent sur votre machine, hors Docker : ils demandent les outils de
[Sans Docker](#sans-docker) (uv pour `test`, Node 22 et pnpm pour `types` et `check`).

---

## Sans Docker

Pour une machine sans droits administrateur (Mac ou Linux), ou si Docker ne veut pas démarrer. Il faut :

- [uv](https://docs.astral.sh/uv/getting-started/installation/), qui installe Python 3.12 tout seul. `make local`
  l'installe s'il manque.
- **Node 22 ou plus.** Sans droits administrateur, passez par [nvm](https://github.com/nvm-sh/nvm) :
  `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash`, rouvrez le terminal, puis
  `nvm install 22`.
- `pnpm` : `make local` l'active via corepack (fourni avec Node).

```bash
cd voice-erp-kit
make local        # installe tout (≈ 5 min) et démarre les 3 services (Ctrl-C pour arrêter)
make dev          # les fois suivantes
```

Tout le reste est identique : http://localhost:5173, `make reset`, `make chat`. Seules les commandes Docker
(`make up`, `make restart`, `make logs`…) ne servent pas : après un changement de `.env`, arrêtez (Ctrl-C) et
relancez `make dev`. Si vous changez `API_PORT`, mettez le même port dans `ERP_API_URL`.

---

## Sans Internet (clé USB)

Si le Wi-Fi ne suffit pas pour `make setup`, l'équipe Stockline a une clé USB avec les images Docker déjà construites.
Copiez sur votre machine **le** fichier qui lui correspond :

| Votre machine | Fichier |
|---|---|
| Mac Apple Silicon (M1, M2, M3, M4…) | `voice-erp-kit-images-arm64.tar.gz` |
| Tout le reste (Mac Intel, Windows/WSL, Linux) | `voice-erp-kit-images-amd64.tar.gz` |

Puis, dans le dossier du projet (après `unzip team-XX.zip` et `cd voice-erp-kit`) :

```bash
make offline IMAGES=/chemin/vers/voice-erp-kit-images-arm64.tar.gz   # ou -amd64.tar.gz ; le .tar non compressé marche aussi
```

Rien n'est téléchargé ni construit : les services démarrent directement (attendez ~20 s avant d'ouvrir
http://localhost:5173). Ensuite, `make up` / `make down` comme d'habitude.

---

## En cas de problème

| Symptôme | Solution |
|---|---|
| `Docker is installed but not running` | lancez Docker Desktop et attendez que la baleine soit stable |
| `port 5173 is already used` (ou 4000, 4100) | un autre programme utilise ce port : arrêtez-le, ou changez `WEB_PORT` / `API_PORT` / `AI_PORT` dans `.env` |
| `make: command not found` (Windows) | vous êtes dans PowerShell : ouvrez le terminal **Ubuntu** (étape 1) |
| `make: command not found` ou fenêtre « outils de développement » (Mac) | `xcode-select --install` (étape 1) |
| `Permission denied` sur `./scripts/…` | le zip a été extrait par Windows : `chmod +x scripts/*.sh`, ou ré-extrayez-le avec `unzip` dans Ubuntu |
| `no data at ./data` | le dossier `data/` doit être à côté du `Makefile`, et `.env` doit contenir `DATA_DIR=./data` |
| La page reste blanche juste après « Ready » | attendez 10–20 s puis rechargez |
| Le premier `make setup` est très long ou échoue au téléchargement | c'est le téléchargement (1–2 Go) ; sur le Wi-Fi du lieu, demandez la clé USB d'images à l'équipe Stockline, puis `make offline IMAGES=<chemin du fichier>` (section « Sans Internet ») |
| L'ERP affiche des données bizarres après vos tests | `make reset` |
| Le micro ne marche pas | autorisez-le dans le navigateur (icône à gauche de l'adresse), utilisez Chrome |
| L'agent comprend toujours « il vous reste du bar ? » | la transcription est en `mock` : voir [Clés réelles ou modèles simulés](#clés-réelles-ou-modèles-simulés) |
| `HTTP 401` / `HTTP 429` / `quota` dans les réponses | clé refusée ou plafond atteint : vérifiez la clé dans `.env`, puis `make restart` ; si le plafond est atteint, venez nous voir |
| Une modification de `.env` n'est pas prise en compte | `make restart` (sans Docker : Ctrl-C puis `make dev`) |
| `corepack enable` échoue (`EACCES`) en mode sans Docker | installez Node avec nvm (voir [Sans Docker](#sans-docker)), ou `npm install -g pnpm@10` |
| Autre chose | `make logs` montre l'erreur ; sinon venez voir l'équipe Stockline (bloqués plus de 20 min = venez) |
