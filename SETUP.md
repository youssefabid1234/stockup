# Step by step installation

An unknown word? [GLOSSAIRE.md](GLOSSAIRE.md) · A question ? [FAQ.md](FAQ.md)

This guide takes you from zero to a first voice call that changes the ERP. Count **20 to 30 minutes** the first
10 to 15 minutes of waiting (downloads) Do the 1 ** step before ** the hackathon if you can.

You have received a `team-XX.zip` file. It contains a `voice-erp-kit/` folder:

| What? | Where | Note |
|---|---|---|
| The kit (ERP, service AI, interface) | `voice-erp-kit/` | the code you will change |
| Data from **your** company | `voice-erp-kit/data/` | customers, products, 3 years of history, documents |
| Configuration and your API keys | `voice-erp-kit/.env` | **private**: don't share it, don't commit it. Zip received the previous day: no keys yet, see [Real keys or simulated models](#clés-réelles-ou-modèles-simulés) |
| Your team record | `voice-erp-kit/TEAM.md` | the name of your company |

There is nothing else to download or clone: everything is in the zip.

---

## Step 1 — Install Docker (的 10 min, to be done before)

Docker runs all three services (ERP, AI, interface) without installing anything else.

### Mac

1. Install Apple development tools (`make`, `git`): in a terminal, `xcode-select --install`, then
   "Install." If he answers "already installed," it's okay.
2. Download [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Apple or Intel chip: the site
   Chooses for you). About 600 Mo.
3. Open the `.dmg`, drag Docker to Applications, launch it. Accept permissions (Mac password).
4. Wait until the whale at the top of the screen stops flashing.
5. In a terminal: `docker run hello-world`. You must see "Hello from Docker!".

### Windows

On Windows, everything is done ** in WSL** (a Linux built-in Windows): `make` and the scripts in the kit do not work
in PowerShell or in the command prompt. You need the admin rights to install WSL.

1. In PowerShell ** admin**: `wsl --install`, then restart. Upon restarting, Ubuntu opens and you
   requires a username and password (for Linux, choose them).
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). During installation, keep
   "Use WSL 2". Start it, then Settings → Resources → WSL integration → activate **Ubuntu**.
3. Open terminal **Ubuntu** (Start menu), then: `sudo apt update && sudo apt install -y make unzip curl git`.
4. Check in Ubuntu: `docker run hello-world`.

From here, on Windows, ** all commands are typed in the Ubuntu** terminal, and the project lives in the
Linux (`~/voice-erp-kit`), not in `C:\`: it's much faster and automatic reloading of the code works.
To open the project in VS Code: `code .` from Ubuntu (extension "WSL").

### Linux

Install [Docker Engine](https://docs.docker.com/engine/install/) and the plugin composes, add to the group
`docker` (`sudo usermod -aG docker $USER`, then reconnect), install `make`, `unzip`, `curl` and `git`.

### Adjusting for all

Docker Desktop → Settings → Resources: give at least **4 GB of RAM**.

> Not the admin rights? On Mac or Linux, go to [Without Docker](#sans-docker). On Windows, WSL requires
> these rights: come and see Team Stockline.

---

## Step 2 — Start the project (5 to 10 min the first time)

```bash
# Mac / Linux : depuis le dossier où est le zip.
# Windows : dans Ubuntu, copiez d'abord le zip dans Linux :
#   cp /mnt/c/Users/<vous>/Downloads/team-XX.zip ~ && cd ~
unzip team-XX.zip
cd voice-erp-kit
make setup
```

`make setup` checks Docker and ports, builds images and starts services. It stops when all
You'll see:

```
  ✓ api, ai and web are up

Ready → http://localhost:5173
```

The first time, it downloads 1 to 2 Go and then builds the images: this is the long step. You can restart it
Without risk if it stops. Next times, `make up` starts in seconds.

**Check that everything works:**

| Open | You need to see |
|---|---|
| http://localhost:5173 (wait ~10 s after "Ready") | the ERP, with the name of **your** company at the top left |
| http://localhost:4000/docs | the API doc of ERP |
| http://localhost:4100/health | `"ok": true` and active suppliers (`llm`, `stt`, `tts`); `mock` = simulated model |

---

## Step 3 — First call (的 5 min)

1. In the ERP, open **Voix** (left menu, section AI).
2. Allow the microphone when requested by the browser (Recommended Chrome).
3. **Maintenez Espace**, parlez comme un client ("Hello, this is the restaurant..., what do you have this morning?"),
   Relax. While you speak, your words appear live (in italic grey as long as they are temporary);
   the final text goes to the agent. You can also type the sentence instead of speaking.
4. Look: the transcription, the tools called by the agent, the answer said out loud, and to the right the ERP
   which is updated (in purple: what the agent has done).
5. Test also **的 Space** (Alt + Space) anywhere in the ERP: a voice command in one sentence
   ("creates a command for ...").

### Real keys or simulated models

Everything is set in `.env` (one file for all three services):

- **Zip received the day J**: your keys are already in `.env`, the selected suppliers are active.
- **Zip received the previous **: `.env` uses simulated models (`mock`), without a key. On D-Day, you will be given your
  `.env` file: Replace the folder with the new one (keep the name `.env`), then `make restart`.

With simulated models, everything works offline and the agent calls the real ERP, but:

- the false LLM includes only a few simple sentences;
- the false transcription hears **always ** the same sentence ("Hello, do you have left of the bar?"), whatever you
  Say: type your text to test something else;
- It is the browser that reads the answer aloud.

It is useful to develop without consuming credit. To return to it at any time: `LLM_PROVIDER=mock`,
`STT_PROVIDER=mock`, `TTS_PROVIDER=mock`, then `make restart`.

### Change pattern or voice

Your `.env` list at the bottom, in comment, all the keys of your team. To change supplier, change
the `*_PROVIDER` and copy the corresponding key to the `*_API_KEY` just below, then `make restart`. Example:

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=              # vide = le modèle par défaut du fournisseur
LLM_API_KEY=<la valeur de la ligne # ANTHROPIC_KEY=…>
```

| Role | Suppliers | Variables |
|---|---|---|
| LLM (brain) | `openai`, `anthropic`, `gemini`, `openai-compatible`, `mock` | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |
| Transcript (STT) | `soniox`, `deepgram`, `gradium`, `openai`, `mock` | `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY` |
| Voice Synthesis (TTS) | `elevenlabs`, `gradium`, `openai`, `mock` | `TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`, `TTS_API_KEY` |
| Jev (decision model, optional) | TypeSafe AI | `JEV_API_KEY` |

Jev is not a LLM: it quickly answers closed questions (choice, score, yes/no) and is used ** next to **
LLM. The basic agent does not use it: it is up to you to plug it (see
[apps/ai/README.md](apps/ai/README.md#jev-decision-model)]. Default templates and voices, and details of each
variable: [README, Configuration](README.md#configuration-one-env).

---

## Step 4 — Your team repo (的 3 min)

```bash
git init -b main && git add . && git commit -m "start"
```

Create a **private** repo on GitHub, push the code (`git remote add origin … && git push -u origin main`), then
Add the jury accounts as employees. This is your deliverable.

`.env` (your keys) and `data/seed/` (the data, too heavy for GitHub) are ignored by git, on purpose.

---

## Step 5 — Coder

- Files to read first: `apps/ai/app/agent/loop.py` (the agent loop) and `apps/ai/app/tools/`
  (what the agent can do in the ERP). The project plan is just below.
- The code recharges itself when you save. After a change of `.env`: `make restart`.
- Do you use a code agent (Claude Code, Cursor...)? Give it [AGENTS.md](AGENTS.md).
- Read: [BRIEF.md](BRIEF.md) (the challenge), [METIER.md](METIER.md) (the occupation), [ERP.md](ERP.md) (the ERP).

### How the project is organised

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

The path of a call: the interface sends the sound to the service AI → transcription (STT) → the agent (LLM) calls
→ tools each tool is a HTTP call to ERP → the answer is read aloud (TTS) and the ERP updates to
the screen. Business rules only live in the ERP. Diagram: [README, Architecture](README.md#architecture); details
and examples to extend the kit: [TECH.md](TECH.md).

| You want to... | Look. |
|---|---|
| the agent respond faster | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/`, `agent/loop.py` |
| that he knows more about the client | `agent/prompts.py`, `tools/context.py`, `data/context/` |
| give him a new action in the ERP | one route in `apps/backend/app/routers/` + one tool in `apps/ai/app/tools/` ([README, Add a tool](README.md#add-a-tool)) |
| changing the interface | `apps/web/src/pages/`, components of `apps/web/src/ui/` ([DESIGN.md](DESIGN.md)) |

### Useful commands

| Command | Effect |
|---|---|
| `make up` / `make down` | start/stop (data are kept) |
| `make restart` | apply a change from `.env` |
| `make logs` | see the logs of the 3 services (Ctrl-C to exit) |
| `make reset` | reset ERP data to zero (remove your changes) |
| `make rebuild` | after adding a Python or npm addiction |
| `make chat` | Talk to the agent in the terminal |
| `make clean` | delete all, including database (`make setup` to leave) |
| `make help` | all commands |

`make test`, `make types` and `make check` turn on your machine, without Docker: they ask for the tools of
[Without Docker](#sans-docker) (uv for `test`, Node 22 and pnpm for `types` and `check`).

---

## Without Docker

For a machine without admin rights (Mac or Linux), or if Docker does not want to start. You must:

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.12 on its own. `make local`
  Set him up if he misses.
- **Node 22 or more.** Without admin rights, go through [nvm](https://github.com/nvm-sh/nvm):
  `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash`, reopen the terminal, then
  `nvm install 22`.
- `pnpm`: `make local` active via corepack (provided with Node).

```bash
cd voice-erp-kit
make local        # installe tout (≈ 5 min) et démarre les 3 services (Ctrl-C pour arrêter)
make dev          # les fois suivantes
```

Everything else is the same: http://localhost:5173, `make reset`, `make chat`. Only Docker commands
(`make up`, `make restart`, `make logs`...) do not serve: after a change of `.env`, stop (Ctrl-C) and
restart `make dev`. If you change `API_PORT`, put the same port in `ERP_API_URL`.

---

## Without Internet (key USB)

If Wi-Fi is not enough for `make setup`, the Stockline team has a USB key with Docker images already built.
Copy to your **le** machine that fits it:

| Your machine | File |
|---|---|
| Mac Apple Silicon (M1, M2, M3, M4...) | `voice-erp-kit-images-arm64.tar.gz` |
| Everything else (Mac Intel, Windows/WSL, Linux) | `voice-erp-kit-images-amd64.tar.gz` |

Then, in the project file (after `unzip team-XX.zip` and `cd voice-erp-kit`):

```bash
make offline IMAGES=/chemin/vers/voice-erp-kit-images-arm64.tar.gz   # ou -amd64.tar.gz ; le .tar non compressé marche aussi
```

Nothing is downloaded or built: the services start directly (wait for ~20 s before opening
http://localhost:5173). Then, `make up` / `make down` as usual.

---

## In case of a problem

| Symptoms | Solution |
|---|---|
| `Docker is installed but not running` | Launch Docker Desktop and wait for the whale to be stable |
| `port 5173 is already used` (or 4000, 4100) | another program uses this port: stop it, or change `WEB_PORT` / `API_PORT` / `AI_PORT` in `.env` |
| `make: command not found` (Windows) | you are in PowerShell: open the terminal **Ubuntu** (step 1) |
| `make: command not found` or "Development Tools" window (Mac) | `xcode-select --install` (Step 1) |
| `Permission denied` on `./scripts/…` | the zip has been extracted by Windows: `chmod +x scripts/*.sh`, or re-extray it with `unzip` in Ubuntu |
| `no data at ./data` | the `data/` folder must be next to the `Makefile`, and `.env` must contain `DATA_DIR=./data` |
| Page remains blank just after « Ready » | Wait for 10–20 s and then recharge |
| The first `make setup` is very long or fails to download | This is the download (1–2 GB); on the Wi-Fi of the place, ask the USB key of images to the Stockline team, then `make offline IMAGES=<chemin du fichier>` (section "Without Internet") |
| The ERP displays strange data after your tests | `make reset` |
| The microphone doesn't work | Allow it in the browser (icon to the left of the address), use Chrome |
| The agent still understands "you still have the bar?" | the transcription is in `mock`: see [Real keys or simulated models](#clés-réelles-ou-modèles-simulés) |
| `HTTP 401` / `HTTP 429` / `quota` in the answers | key refused or ceiling reached: check the key in `.env`, then `make restart`; if the ceiling is reached, come see us |
| A change to `.env` is not taken into account | `make restart` (without Docker: Ctrl-C then `make dev`) |
| `corepack enable` fails (`EACCES`) in Docker-free mode | install Node with nvm (see [Without Docker](#sans-docker)), or `npm install -g pnpm@10` |
| Another thing. | `make logs` shows the error; otherwise come see team Stockline (blocked more than 20 min = come) |
