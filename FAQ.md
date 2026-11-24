# FAQ

Any unknown word? [GLOSSAIRE.md](GLOSSAIRE.md). Still blocked after
20 minutes? Come and see Team Stockline.

1. [Installation](#installation)
2. [Understanding project ](#comprendre)
3. [Coder](#coder)
4. [Clears and costs](#cles)
5. [Living and demo](#livrables)

<a id="installation"></a>
## Installation

**I've never done Python/Docker, how do I do it?**
No need to know how to install Python: Docker does everything. Follow [SETUP.md](SETUP.md) line, copy the
commands as is. To encode, the Python of the kit is simple (functions, dictionaries): start from a
existing tool in `apps/ai/app/tools/` and modify it. A code agent (Claude Code, Cursor...) with
[AGENTS.md](AGENTS.md) will save you a lot of time.

**The terminal tells me `command not found` or `No such file or directory`.**
You may not be in the right folder. `pwd` displays where you are; `cd voice-erp-kit` to enter it
(the folder that contains the `Makefile`). On Windows, use the terminal **Ubuntu**, not PowerShell. Other
common errors: [SETUP.md, "In case of problem"](SETUP.md#en-cas-de-problème).

**I'm on Windows and .**
Normal: Alt+Space is a shortcut to the Windows system (it opens the window menu). Go to the page
**Voix**, tab **Order**: Hold Space (or the big microphone button), speak, release. It's the same
Voice control.

**How to start from scratch?**
- The data of the ERP is damaged by your tests: `make reset` (reloads the starting data, services
  must turn).
- Everything is broken: `make clean` (removes the ** and ** containers the base), then `make up`.
- Your code is broken: `git status` to see what changed, `git checkout -- <fichier>` to return to the last
  commit a file.

**I have changed `.env` and nothing changes.**
`make restart` (without Docker: Ctrl-C then `make dev`). `curl localhost:4100/health` shows active suppliers.

<a id="understand"></a>
## Understanding the project

**What does the kit do, in one sentence?**
A wholesaler ERP (port 4000), a AI service that drives it with tools (port 4100) and a web interface (port
5173) with a chat, a Voice page and voice control. Detailed map: [README.md](README.md) and [TECH.md](TECH.md).

**What document read first?**
[BRIEF.md](BRIEF.md) (the challenge), then [METIER.md](METIER.md) if you don't know the job.
[GUIDE-AGENTS.md](GUIDE-AGENTS.md) (agents LLM) or [GUIDE-VOIX.md](GUIDE-VOIX.md) (speed, natural) according to your
angle of attack.

**What is `mock` mode?**
Fake suppliers, free and offline. The Mock agent really calls the ERP, but it doesn't understand anything; the STT
mock always hears the same sentence. Perfect for installing and encode the interface, useless for judging the agent.

**What happens during a vocal tour?**
Your voice goes to the STT while you speak (the text is displayed live), the final text goes to the agent, who
calls tools of the ERP, then its answer is read by the TTS sentence by sentence.
Detail: [GUIDE-VOIX.md §1](GUIDE-VOIX.md#anatomie).

<a id="coder"></a>
## Code

**Where do I code?**

| Edit | For |
|---|---|
| `apps/ai/app/agent/prompts.py` | what the agent knows and how he speaks (rules, tone, vocal mode) |
| `apps/ai/app/tools/*.py` | what the agent can do in the ERP (new tools, faster tools) |
| `data/context/*.md` | the knowledge of your business given to the agent |
| `apps/ai/app/agent/loop.py` | the loop of the agent (order of steps, parallelism, limits) |

| Leave it as it is (unless there is a specific reason) | Why? |
|---|---|
| `apps/ai/app/clients/` | connections to suppliers: already settled |
| `apps/ai/app/services/utterance.py` | live transcription: fragile, already optimized |
| `apps/ai/app/agent/sanitize.py` | clean the history so that the supplier accepts it |
| `apps/ai/app/schemas/`, `apps/ai/app/routers/` | the contract with the interface: change it and the web breaks |

**How do I know that Mon has changed?**
- `make chat`: Talk to the agent in the terminal, without a microphone. It displays the tools called, time and tokens.
- Page **Voix** (http://localhost:5173): a real vocal tower, with latency measurements.
- `make logs`: Python errors are displayed (Ctrl-C to exit).
- `curl localhost:4100/tools`: the list of tools the agent sees. Yours must be there.
The code recharges itself on recording (the history of the voice conversation is lost).

**How to add a tool?**
A `@tool` function in `apps/ai/app/tools/`, imported into `tools/__init__.py`. Step by step example:
[TECH.md, "Tools"](TECH.md#outils) (section 5.3 for a simple tool, 5.4 for a composite tool).

**I need an action that the ERP can't do.**
First add the endpoint in the backend (`apps/backend/app/services/` + `routers/`), then the tool that calls it.
End-to-end example: [TECH.md 2.6](TECH.md#ajouter-endpoint). Business rules remain in the backend.

**`git commit` refuses / `git push` asks me a password.**
- Commit refused (Please tell me who you are): once and for all,
  `git config --global user.name "Prénom Nom"` and `git config --global user.email "vous@exemple.fr"`.
- Push: GitHub no longer accepts the account password. The simplest: `gh auth login` (GitHub CLI tool), or
  Create a *personal access token* in GitHub (Settings → Developer settings) and paste it instead of the password.

<a id="cles"></a>
## Keys and costs

**How to see consumption / cost?**
- Each response of the cat (`POST /ai/chat`) ends with an event `done` that contains `usage`: tokens
  entry, output, and cache (`cache_read_input_tokens` read, `cache_creation_input_tokens` written).
- `make chat` displays it after each answer.
- The voice session does not return `usage`: log it if you need it.
- The suppliers' dashboards are on the organizers' side: ask us if you want a global number.

**I no longer have any credits / error 401 / 429.**
- **401**: Refused key. Check it in `.env` (no space, no quotes), then `make restart`.
- **429** or "quota": too many requests or ceiling reached. Wait a minute; if it persists, come see us.
- In the meantime: go back to `mock` to code, and keep the real keys to test.

**Can I change my model?**
Yes, in `.env`: `LLM_MODEL=claude-sonnet-5-5` (default, balanced), `claude-haiku-5-5` (fastest and fastest)
or `claude-opus-5-5` (the strongest, slower). Then `make restart`. Check your scenarios after:
faster but fake doesn't win.

**Can I use another supplier?**
The code supports others (OpenAI, Gemini, Deepgram, Gradium, any OpenAI compatible endpoint), but we do
supply key only for **Anthropic** (LLM), **Soniox** (STT), **ElevenLabs** (TTS) and **Jev**. With your
Your own key is allowed: say it in `DECISIONS.md`.

<a id="deliverables"></a>
## Deliverables and demo

**What should I do?**
Repo GitHub, `DECISIONS.md`, slides (5 min), video (2 min) and live demo:
[BRIEF.md §8](BRIEF.md#8-livrables-et-démo-finale).

**How to show that our agent is fast?**
Page **Voix**: columns **Total** and **Perçu** of each round. Note median and worst case, before/after each round
change in `DECISIONS.md`. Method: [GUIDE-VOIX.md §8](GUIDE-VOIX.md#plan).

**Can the jury launch our project?**
Yes if it starts with `make setup` once the `data/` folder is in place. Test it on a fresh copy before
Never put `.env` in the repo.

**Mon tool crashes the boot (TypeError `@tool ...`).**
Read the message: it says what to fix (`async def` missing, first parameter not `ctx`, parameter without type, docstring absent or name already taken).
