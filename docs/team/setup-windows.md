# Launch the kit on Windows without Docker (tested the 23/11)

The official kit goes through WSL + Docker (SETUP.md). Without admin rights or restart, this works:

```powershell
winget install --id astral-sh.uv -e        # Python du kit (uv)
npm install -g pnpm@10                       # site web (Node 22+ requis)
gh repo clone MohamedAmineLS/Stockline-Hackathon-AI
```

Then copy ** from the zip of the ** team (never in git): the `data/seed/` folder in `data/`, and `.env` at the root.

Install dependencies (Git Bash; `UV` = full uv.exe path if `uv` is not recognized, e.g.
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_…\uv.exe`) :

```bash
cd apps/backend && uv sync && cd ../ai && uv sync --group dev && cd ../..
npm_config_manage_package_manager_versions=false pnpm install
```

Launch 3 programs, each in its terminal:

```powershell
# 1. ERP (port 4000), dans apps/backend
uv run uvicorn app.main:app --reload --reload-dir app --port 4000
# 2. Agent IA (port 4100), dans apps/ai
uv run uvicorn app.main:app --reload --reload-dir app --port 4100
# 3. Site (port 5173), à la racine
$env:npm_config_manage_package_manager_versions = 'false'; pnpm --filter @kit/web dev
```

Check: http://localhost:4100/health (active suppliers), http://localhost:5173/voice (Voice page, in Chrome).
After a change of `.env`: Ctrl-C in the AI agent terminal, then restart the 2 command.
Reset data to zero: `curl -X POST http://localhost:4000/api/admin/reset`.
