"""
Team 12 · Daycem (T3) · Can Jev tell whether a client accepts a substitute? Small measured test, kept for DECISIONS.md.

One Jev call per client card (10 cards = 10 calls), no LLM, no ERP write. The expected answer of each card was set by
hand BEFORE the run, from what the card really says. Decision rule: p(yes) >= 0.8 -> "oui", <= 0.2 -> "non", else
"demander" (ask the caller).

    v1: state = CRM line + « Ce qui les agace » + latest CRM notes; generic question about butter
    v2: v1 + the « Qui ils sont » paragraph; precise question about the requested product (beurre de tourage AOP)

Run inside the ai container (needs JEV_API_KEY):
    docker compose cp scripts/jev_substitution_test.py ai:/tmp/jev_substitution_test.py
    docker compose exec ai sh -c 'cd /app/apps/ai && PYTHONPATH=. python /tmp/jev_substitution_test.py --version 2'
Results of both runs: docs/team/jev-substitution-test.md.
"""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

from app.clients import get_jev_client

CARDS = Path("/data/context/clients")

QUESTIONS = {
    1: "Ce client accepte-t-il qu'on lui livre un autre beurre (un remplacement) quand le beurre qu'il commande manque ?",
    2: "Ce client accepte-t-il un autre produit à la place du beurre de tourage AOP, quand celui-ci manque ?",
}
YES = "La fiche dit qu'il accepte les remplacements pour ce produit, au moins s'il est prévenu."
NO = "La fiche dit qu'il refuse les remplacements (en général ou sur ce produit)."

# (card prefix, expected answer), set by hand before the runs.
CASES = [
    ("c0001", "non"),       # « Jamais de substitution sur le beurre »
    ("c0021", "oui"),       # « Accepte les substitutions équivalentes si on prévient »
    ("c0097", "non"),       # « Refuse les substitutions : appeler avant toute modification »
    ("c0102", "demander"),  # accepte en général mais tient à son tourage AOP : pas évident pour un beurre
    ("c0100", "oui"),       # accepte si on prévient (beurre demi-sel)
    ("c0039", "non"),       # refuse (beurre demi-sel)
    ("c0002", "demander"),  # refuse les substitutions d'origine sur la couverture ; rien sur le beurre
    ("c0012", "demander"),  # refuse les substitutions de couverture ; rien sur le beurre
    ("c0007", "oui"),       # « aucune substitution sans être prévenu » : au téléphone il est prévenu
    ("c0010", "demander"),  # prospect, rien sur les remplacements
]


def _section(text: str, title: str) -> str:
    m = re.search(rf"## {title}\n(.*?)(?=\n## |\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def _bullets(block: str) -> list[str]:
    return [line[2:].strip() for line in block.splitlines() if line.startswith("- ")]


def card_state(prefix: str, version: int) -> dict:
    text = next(CARDS.glob(f"{prefix}-*.md")).read_text(encoding="utf-8")
    crm = re.search(r"Fiche CRM : _(.*?)_\s*$", text, re.M)
    notes = re.search(r"Dernières notes CRM :\n(.*?)(?=\n## |\Z)", text, re.S)
    state = {
        "fiche_crm": crm.group(1) if crm else "",
        "ce_qui_les_agace": _bullets(_section(text, "Ce qui les agace")),
        "notes": _bullets(notes.group(1)) if notes else [],
    }
    if version >= 2:
        who = _section(text, "Qui ils sont")
        state["qui_ils_sont"] = next((p for p in who.split("\n\n") if not p.startswith("**")), "").strip()
    return state


async def main(version: int) -> None:
    jev = get_jev_client()
    if jev is None:
        sys.exit("JEV_API_KEY vide : pas de client Jev")
    rows = []
    for prefix, truth in CASES:
        t0 = time.perf_counter()
        p = await jev.yes_no(card_state(prefix, version), QUESTIONS[version], YES, NO)
        ms = int((time.perf_counter() - t0) * 1000)
        got = "oui" if p >= 0.8 else "non" if p <= 0.2 else "demander"
        rows.append((truth, got, ms))
        print(f"{prefix}  vérité={truth:9} jev={got:9} p(oui)={p:.2f}  {ms} ms  {'OK' if got == truth else 'FAUX'}", flush=True)
    good = sum(t == g for t, g, _ in rows)
    times = [ms for *_, ms in rows]
    print(f"\nv{version} : {good}/{len(rows)} bonnes réponses · temps moyen {sum(times) // len(times)} ms"
          f" · min {min(times)} · max {max(times)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, choices=[1, 2], default=2)
    asyncio.run(main(parser.parse_args().version))
