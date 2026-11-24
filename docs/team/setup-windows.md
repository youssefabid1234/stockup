# Lancer le kit sur Windows sans Docker (testé le 23/11)

Le kit officiel passe par WSL + Docker (SETUP.md). Sans droits admin ni redémarrage, ceci marche :

```powershell
winget install --id astral-sh.uv -e        # Python du kit (uv)
npm install -g pnpm@10                       # site web (Node 22+ requis)
gh repo clone MohamedAmineLS/Stockline-Hackathon-AI
```

Puis copier **depuis le zip de l'équipe** (jamais dans git) : le dossier `data/seed/` dans `data/`, et `.env` à la racine.

Installer les dépendances (Git Bash ; `UV` = chemin complet de uv.exe si `uv` n'est pas reconnu, par ex.
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_…\uv.exe`) :

```bash
cd apps/backend && uv sync && cd ../ai && uv sync --group dev && cd ../..
npm_config_manage_package_manager_versions=false pnpm install
```

Lancer les 3 programmes, chacun dans son terminal :

```powershell
# 1. ERP (port 4000), dans apps/backend
uv run uvicorn app.main:app --reload --reload-dir app --port 4000
# 2. Agent IA (port 4100), dans apps/ai
uv run uvicorn app.main:app --reload --reload-dir app --port 4100
# 3. Site (port 5173), à la racine
$env:npm_config_manage_package_manager_versions = 'false'; pnpm --filter @kit/web dev
```

Vérifier : http://localhost:4100/health (fournisseurs actifs), http://localhost:5173/voice (page Voix, dans Chrome).
Après un changement de `.env` : Ctrl-C dans le terminal de l'agent IA, puis relancer la commande 2.
Remettre les données à zéro : `curl -X POST http://localhost:4000/api/admin/reset`.
