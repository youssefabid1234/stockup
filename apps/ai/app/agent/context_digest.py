"""
OWNER: Amine Khalil (T3/T4 repris de Youssef) · switch TEAM_SLIM_PROMPT · « un prompt plus léger, donc plus rapide »

Every model call re-reads the system prompt. Measured (mar. 24/11): ~35 k tokens per call, of which the company context
(the 6 DATA_DIR/context/*.md files) is 55 % — mostly the product catalogue tables (aliases, prices, shelf life), which
the tools already give on demand (search, resolve_product, product_insight, quote_line) and the caller's sheet already
covers (status, habits, credit). This module keeps, from the SAME files, only the sections the agent needs on every turn:
house rules, today's situation, who validates what, cut-off times, ambiguous words, usual substitutions, seasons, how to
take an order, prices / credit rules, routes. Extracted by heading at each turn (edit the .md files live, like the kit).
A file this module does not know is kept whole (safe default).
"""

from __future__ import annotations

import re

from app.config import settings

# file (matched on a word of its name) → the « ## » sections to keep (matched on the start of the heading, accents kept)
KEEP: dict[str, tuple[str, ...]] = {
    "entreprise": ("Équipe", "Règles de la maison", "Situation au"),
    "journee": ("Heures limites", "Facturation"),
    "glossaire": ("Alias ambigus", "Substitutions habituelles", "Saisonnalité"),
    "playbook": ("Prendre une commande", "Substitutions", "Clients bloqués", "Réclamations"),
    "prix": ("Prix de vente", "Règles de prix", "Crédit et relances"),
    "livraisons": ("Tournées",),
}
_SECTION = re.compile(r"^## ", re.M)


def _keep_for(name: str) -> tuple[str, ...] | None:
    low = name.lower()
    return next((headings for key, headings in KEEP.items() if key in low), None)


def digest(text: str, headings: tuple[str, ...]) -> str:
    """The file's title + intro paragraph, then only the « ## » sections whose heading starts with one of `headings`."""
    parts = _SECTION.split(text)
    head, sections = parts[0].strip(), parts[1:]
    kept = [f"## {s.strip()}" for s in sections if s.split("\n", 1)[0].strip().startswith(headings)]
    return "\n\n".join([head, *kept]) if kept else text.strip()


def read_context_digest() -> str:
    """Like prompts.read_context_files(), with only the essential sections of the known files."""
    folder = settings.data_dir / "context"
    try:
        files = sorted(p for p in folder.iterdir() if p.name.endswith(".md"))
    except OSError:
        return ""
    out = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        headings = _keep_for(p.name)
        out.append(f"<!-- {p.name} (extrait) -->\n{digest(text, headings)}" if headings else f"<!-- {p.name} -->\n{text.strip()}")
    return "\n\n".join(out)
