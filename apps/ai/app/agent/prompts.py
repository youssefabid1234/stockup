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
ROLE = """You are the ERP assistant for {company}. {trade}.
Help sales staff and callers check stock, prices and customer records and place orders."""

BASE_RULES = """Always reply in clear, concise English. Write new ERP notes and descriptions in English. Preserve proper names, references, quantities, prices and quoted identifiers.
- Use tools for all business facts. Never invent names, IDs or numbers. Start with search to identify an unfamiliar customer or product. Ask if several matches are plausible.
- Use get_price for the actual customer price, including negotiated and volume rates.
- Read relevant records with get_context or search_context. Save lasting preferences or constraints with save_context. Check customer history and record complaints with log_client_event.
- Respect substitution preferences. Create a draft and read it back. Only call confirm_order after explicit agreement to that summary.
- Explain ERP warnings about credit, blocked accounts and insufficient stock."""

CHAT_RULES = "Chat mode: use short lists or bold text when useful."

VOICE_RULES = """Phone mode. Write only words meant for the caller.
- Use tools silently. Keep reasoning and internal steps private. The audio service handles waiting.
- Greet once at the start when appropriate. After that, lead with the answer or the one question you need.
- Speak warm, conversational English. Use one or two short sentences and one question at a time.
- Speak quantities, units, prices and dates accurately. Avoid Markdown, URLs and technical identifiers.
- Say what is available or still needs checking. Read the order back and wait for explicit consent.
Examples: “Hello, how can I help?” “Yes, we have T55 flour. How many bags would you like?”"""

COMMAND_RULES = """Single-turn voice command from a member of staff. These mode rules take priority.
Act on an explicit request using tools. Create a draft, add a line or look up a record immediately. Ask one short question if the target is ambiguous or a destructive action lacks explicit authorisation.
An explicit request to confirm an order or record payment authorises that action. If no tool supports it, say so.
Report the result in one short English sentence, including relevant document numbers, quantities and dates. Skip greetings and follow-up offers."""


MODE_RULES = {"chat": CHAT_RULES, "voice": VOICE_RULES, "command": COMMAND_RULES}


async def build_system_prompt(mode: ChatMode, actor_name: str | None = None, call_context=None) -> str:
    # Team 12 sections (each '' while its TEAM_* switch is off). Static rules come BEFORE the company context so the
    # long static prefix stays cacheable; the caller's sheet (dynamic) comes LAST. See docs/team/interfaces.md.
    from .call_context import render_for_prompt
    from .rules_order import order_rules_section
    from app.tools.insight import product_insight_section

    from .listening import listening_section
    from .rules_sales import sales_rules_section

    meta = await get_meta()
    today = meta.get("today") or datetime.now(UTC).date().isoformat()
    company = meta.get("company") or "a food wholesaler"
    trade = meta.get("trade") or company_trade()
    team_rules = mode != "command"  # the one-shot command mode keeps the kit's rules
    parts = [
        ROLE.format(company=company, trade=f"Business: {trade}" if trade else "Food wholesaler"),
        BASE_RULES,
        MODE_RULES[mode],
        order_rules_section() if team_rules else "",  # Amine K.
        sales_rules_section() if team_rules else "",  # Daycem
        listening_section(mode),  # Youssef (pieces, other voices, doubtful words: voice mode only)
        product_insight_section() if team_rules else "",  # Youssef (one tool: stock + price + substitutes)
        f"Company: {meta.get('company') or '(ERP unavailable)'}. Today: {english_date(today)} ({today}).",
        f"Caller: {actor_name}." if actor_name else "",
        f"# Background\n\n{context}" if (context := company_context()) else "",
        render_for_prompt(call_context),  # Youssef (preloaded caller sheet)
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


def company_context() -> str:
    """Team 12 (Amine K.): the essential sections only when TEAM_SLIM_PROMPT is on (agent/context_digest.py), else all."""
    from app import team_flags

    if team_flags.slim_prompt():
        from .context_digest import read_context_digest

        return read_context_digest()
    return read_context_files()


def read_context_files() -> str:
    """All DATA_DIR/context/*.md files, in name order, each preceded by its file name."""
    folder = settings.data_dir / "context"
    try:
        files = sorted(p for p in folder.iterdir() if p.name.endswith(".md"))
        return "\n\n".join(f"<!-- {p.name} -->\n{p.read_text(encoding='utf-8').strip()}" for p in files)
    except OSError:
        return ""


def company_trade() -> str:
    """What the company does, in one sentence: the first paragraph line of DATA_DIR/context/*company*.md
    (e.g. "Family grower in Asian products installed in Ivry-sur-Seine..."). "if there is none."""
    folder = settings.data_dir / "context"
    try:
        files = sorted(p for p in folder.iterdir() if p.name.endswith(".md") and "entreprise" in p.name.lower())
        text = files[0].read_text(encoding="utf-8") if files else ""
    except OSError:
        return ""
    para = next((line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(("#", "|", "-", ">"))), "")
    sentence = re.split(r"(?<=[.!?])\s", para, maxsplit=1)[0].replace("**", "").strip()
    return sentence.rstrip(".")[:200]


def english_date(iso: str) -> str:
    day = date.fromisoformat(iso[:10])
    return f"{day:%A} {day.day} {day:%B %Y}"
