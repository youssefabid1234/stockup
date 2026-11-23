"""
System prompt = role + rules + mode rules + company & today's date + company context files.

  - Company context: every Markdown file in DATA_DIR/context/, re-read on each turn (edit them live).
  - "Today" comes from the ERP (GET /api/meta): the data pack has its own simulated date.
"""

import re
import time
from datetime import UTC, date, datetime

import httpx

from app.config import settings
from app.schemas import ChatMode

# The role line is filled per company: {company} from GET /api/meta, {trade} from meta.trade if the ERP has it,
# else the first sentence of DATA_DIR/context/*entreprise*.md (see company_trade). Each team runs a different trade.
ROLE = """Tu es l'assistant IA de l'ERP de {company}. {trade}.
Tu aides les commerciaux et réponds aux clients : stock, prix, fiches clients, prises de commande."""

BASE_RULES = """Règles :
- Utilise les outils pour toute donnée (stock, prix, client, commande). N'invente jamais un chiffre, un id ou un nom.
- Commence par "search" pour retrouver un client ou un produit à partir de ce qui est dit (surnoms, fautes : la recherche est floue).
- S'il y a plusieurs candidats plausibles, demande lequel.
- Pour annoncer un prix à un client, utilise get_price (prix négocié, règles de groupe et de volume) plutôt que le prix catalogue.
- Avant de répondre sur un client, un fournisseur ou un produit, charge ses fiches de contexte (get_context) ; pour une règle ou une procédure, search_context. Si tu apprends un fait durable (préférence, contact, contrainte), mémorise-le avec save_context.
- Respecte les préférences et notes du client (ex. pas de substitution) avant de proposer un remplacement.
- Tiens compte de l'historique du client (get_client / get_client_history : réclamations ouvertes, litiges, retards de paiement). Si un client se plaint, enregistre-le avec log_client_event.
- Une commande se crée en brouillon (create_draft_order). Ne la confirme (confirm_order) qu'après accord explicite sur le récapitulatif.
- Signale les alertes renvoyées par l'ERP (encours, client bloqué, stock insuffisant).
- Réponds en français, de façon concise."""

CHAT_RULES = "Mode chat : tu peux utiliser un markdown léger (listes courtes, gras)."

VOICE_RULES = """Mode VOCAL (au téléphone) — ta réponse est lue à voix haute :
- 1 à 2 phrases courtes, ton naturel et chaleureux, comme un bon commercial au téléphone.
- Jamais de markdown, de listes, d'emojis, d'ids techniques ni d'URL.
- Arrondis les nombres et dis les unités en toutes lettres (« 12 kilos », « 18 euros 50 le kilo »).
- Tout texte que tu écris est prononcé dans l'ordre, y compris entre deux appels d'outils. Donc : au plus une très courte phrase d'attente AVANT le premier outil (« Je regarde. »), puis plus rien entre les appels d'outils (pas de « Je crée le brouillon. », pas de commentaire d'étape). La vraie réponse (salutation comprise) vient une seule fois, à la fin, après le dernier outil.
- Une seule question à la fois. Récapitule la commande avant de la confirmer."""

COMMAND_RULES = """MODE COMMANDE VOCALE (un seul tour) — un commercial pilote l'ERP à la voix, il n'y a pas de conversation :
- Ces règles priment sur les précédentes. Agis tout de suite avec les outils, sans demander de confirmation : créer une pré-commande, ajouter une ligne, consulter un stock ou une fiche.
- Ne pose une question que si c'est vraiment ambigu (deux clients aussi plausibles) ou si l'action est destructive / irréversible et pas explicitement demandée ; dans ce cas, n'agis pas et pose UNE question courte.
- Une demande explicite (« confirme la commande … », « marque … comme payée ») vaut accord : exécute-la.
- Si aucun outil ne permet l'action demandée, dis-le en une phrase, sans inventer.
- Réponse : UNE phrase courte, sans markdown, qui dit ce qui a été fait et cite les numéros (commande, facture), quantités et dates.
- Pas de « Autre chose ? », pas de salutation."""

MODE_RULES = {"chat": CHAT_RULES, "voice": VOICE_RULES, "command": COMMAND_RULES}


async def build_system_prompt(mode: ChatMode, actor_name: str | None = None) -> str:
    meta = await get_meta()
    today = meta.get("today") or datetime.now(UTC).date().isoformat()
    company = meta.get("company") or "un grossiste alimentaire"
    trade = meta.get("trade") or company_trade()
    parts = [
        ROLE.format(company=company, trade=f"Activité : {trade}" if trade else "C'est un grossiste alimentaire"),
        BASE_RULES,
        MODE_RULES[mode],
        f"Entreprise : {meta.get('company') or '(ERP injoignable)'}. Aujourd'hui : {french_date(today)} ({today}).",
        f"Interlocuteur : {actor_name}." if actor_name else "",
        f"# Contexte entreprise\n\n{context}" if (context := read_context_files()) else "",
    ]
    return "\n\n".join(p for p in parts if p)


_meta_cache: tuple[float, dict] | None = None


async def get_meta() -> dict:
    """{company, today, …} from the ERP, cached for a minute. {} if the ERP is down (tools will report it)."""
    global _meta_cache
    if _meta_cache and time.monotonic() - _meta_cache[0] < 60:
        return _meta_cache[1]
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            res = await client.get(f"{settings.erp_api_url}/api/meta")
        if not res.is_success:
            return {}
        _meta_cache = (time.monotonic(), res.json())
        return _meta_cache[1]
    except (httpx.HTTPError, ValueError):
        return {}


def read_context_files() -> str:
    """All DATA_DIR/context/*.md files, in name order, each preceded by its file name."""
    folder = settings.data_dir / "context"
    try:
        files = sorted(p for p in folder.iterdir() if p.name.endswith(".md"))
        return "\n\n".join(f"<!-- {p.name} -->\n{p.read_text(encoding='utf-8').strip()}" for p in files)
    except OSError:
        return ""


def company_trade() -> str:
    """What the company does, in one sentence: the first paragraph line of DATA_DIR/context/*entreprise*.md
    (e.g. "Grossiste familial en produits asiatiques installé à Ivry-sur-Seine…"). "" if there is none."""
    folder = settings.data_dir / "context"
    try:
        files = sorted(p for p in folder.iterdir() if p.name.endswith(".md") and "entreprise" in p.name.lower())
        text = files[0].read_text(encoding="utf-8") if files else ""
    except OSError:
        return ""
    para = next((line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(("#", "|", "-", ">"))), "")
    sentence = re.split(r"(?<=[.!?])\s", para, maxsplit=1)[0].replace("**", "").strip()
    return sentence.rstrip(".")[:200]


WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]  # fmt: skip


def french_date(iso: str) -> str:
    """"2026-11-24" → "mardi 24 novembre 2026"."""
    d = date.fromisoformat(iso[:10])
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"
