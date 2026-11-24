"""Configuration from environment variables.

The repo-root `.env` (one file for backend, ai and web) is loaded first; real environment
variables win over it.

  DATA_DIR  where the data pack lives (relative paths are resolved from the repo root),
            default ./data — seed files are read from DATA_DIR/seed/*.json
  DB_PATH   SQLite file, default apps/backend/data/erp-en.db
  API_PORT  HTTP port, default 4000
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]  # apps/backend
REPO_ROOT = BACKEND_ROOT.parents[1]  # hackathon-kit

load_dotenv(REPO_ROOT / ".env", override=False)

DATA_DIR = (REPO_ROOT / (os.environ.get("DATA_DIR") or "./data")).resolve()
# team 12 (Youssef): SEED_DIR_NAME=seed_en reads the English data pack (data/seed_en, committed; made by
# scripts/translate_seed.py from the French data/seed). The English pack is the default.
SEED_DIR = DATA_DIR / (os.environ.get("SEED_DIR_NAME") or "seed_en").strip()
DB_PATH = Path(os.environ.get("DB_PATH") or BACKEND_ROOT / "data" / "erp-en.db").resolve()
API_PORT = int(os.environ.get("API_PORT") or 4000)
