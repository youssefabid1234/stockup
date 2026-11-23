"""
OWNER: Youssef · switch TEAM_PRELOAD · contract: docs/team/interfaces.md §2

The caller's sheet, loaded ONCE per call (in parallel) as soon as we know who calls, then put in the system prompt
of every following turn. Real life: Lucie opens Nadine's sheet the second she recognises her voice, instead of
searching it again at each question.

Why: today the model calls get_client / get_context / get_product_stock one after the other at every turn
(≈ 1 s each). Preloading removes those round-trips (fast) and gives the rule bricks the facts they need (smart):
preferences, "never substitute", delivery days, blocked account, usual basket and its stock, open issues.

Used by:
  - agent/prompts.py → render_for_prompt(cc) is appended to the system prompt (dynamic part, after the static
    rules so the static prefix stays in Anthropic's prompt cache)
  - agent/rules_order.py (Amine K.) and agent/rules_sales.py (Daycem) read its fields
  - services/voice_session.py keeps it on the Conversation
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field

from app.tools.erp import ErpClient


@dataclass
class UsualItem:
    product_id: str
    product_name: str
    unit: str
    avg_qty: float | None = None
    last_qty: float | None = None
    available: float | None = None  # current stock (None = not loaded)


@dataclass
class CallContext:
    """Everything the agent should know about the caller before answering. Field names are the contract."""

    client_id: str
    name: str
    status: str = "active"  # active | blocked | prospect | lost
    delivery_days: list[str] = field(default_factory=list)  # ["tue", "thu", "sat"]
    preferences: str = ""  # free text from the ERP (e.g. "Jamais de substitution sur le beurre")
    contacts: list[dict] = field(default_factory=list)  # [{name, role, phone}]
    usual: list[UsualItem] = field(default_factory=list)  # usual basket, with stock when loaded
    outstanding: float | None = None
    credit_limit: float | None = None
    open_issues: int = 0
    notes: list[str] = field(default_factory=list)  # latest CRM notes, "date author : text"
    context_entries: list[dict] = field(default_factory=list)  # [{kind, title, body}] from /api/context/for
    active_promos: list[dict] = field(default_factory=list)  # [{name, productIds?, categoryId?, discountPct?}] TODO
    loaded_ms: int | None = None
    caller_contact: str | None = None  # who is on the phone (caller ID form), e.g. "Nadine Sarrailh"
    caller_phone: str | None = None

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    @property
    def is_new(self) -> bool:
        """A caller who is not in the ERP yet (status "new")."""
        return self.status == "new"


async def load_call_context(erp: ErpClient, client_id: str) -> CallContext:
    """
    The caller's sheet: client + context entries in parallel, then the stock of the usual items in parallel.
    Notes contradicting the ERP's delivery days ("Fermé le mercredi" for a client delivered on Wednesdays) are
    dropped: the ERP and the order history are the truth (team decision, 23/11).
    TODO(Youssef, later): active promos for this client (price rules), once Daycem's demo promo exists.
    """
    t0 = time.perf_counter()
    client, ctx_for = await asyncio.gather(
        erp.get(f"/api/clients/{client_id}"),
        erp.get("/api/context/for", {"entityType": "client", "id": client_id}),
    )
    days = client.get("deliveryDays") or []
    cc = CallContext(
        client_id=client["id"],
        name=client.get("name", ""),
        status=client.get("status", "active"),
        delivery_days=client.get("deliveryDays") or [],
        preferences=client.get("preferences") or "",
        contacts=client.get("contacts") or [],
        usual=[
            UsualItem(
                product_id=u.get("productId", ""),
                product_name=u.get("productName", ""),
                unit=u.get("unit", ""),
                avg_qty=u.get("avgQty"),
                last_qty=u.get("lastQty"),
            )
            for u in (client.get("usual") or [])[:10]
        ],
        outstanding=client.get("outstanding"),
        credit_limit=client.get("creditLimit"),
        open_issues=client.get("openIssues") or 0,
        notes=[
            f"{n['at'][:10]} {n['author']} : {n['text']}"
            for n in (client.get("notes") or [])[-5:]
            if not contradicts_delivery_days(n.get("text") or "", days)
        ],
        context_entries=[
            {"kind": e.get("kind"), "title": e.get("title"), "body": drop_contradictions(e.get("body") or "", days)[:600]}
            for e in (ctx_for.get("entries") or [])[:12]
        ],
    )
    # Stock of the usual items, in parallel (for "comme d'hab": the agent knows at once what is available).
    stocks = await asyncio.gather(
        *(erp.get(f"/api/products/{u.product_id}") for u in cc.usual if u.product_id), return_exceptions=True
    )
    for u, p in zip([u for u in cc.usual if u.product_id], stocks, strict=True):
        if isinstance(p, dict):
            u.available = p.get("available")
    cc.loaded_ms = int((time.perf_counter() - t0) * 1000)
    return cc


# ── "Fermé le mercredi" vs the ERP's delivery days ──

_DAY_CODES = {"lundi": "mon", "mardi": "tue", "mercredi": "wed", "jeudi": "thu", "vendredi": "fri", "samedi": "sat", "dimanche": "sun"}  # fmt: skip
_CLOSED = re.compile(r"ferm[ée]e?s?\s+(?:le\s+|les\s+)?(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)", re.IGNORECASE)


def contradicts_delivery_days(text: str, delivery_days: list[str]) -> bool:
    """True if `text` says the client is closed on a day the ERP delivers them (the ERP + history win)."""
    return any(_DAY_CODES[m.lower()] in delivery_days for m in _CLOSED.findall(text))


def drop_contradictions(body: str, delivery_days: list[str]) -> str:
    """Remove the lines of a context entry that contradict the ERP's delivery days."""
    return "\n".join(line for line in body.splitlines() if not contradicts_delivery_days(line, delivery_days))


# ── Finding the caller in the conversation, and keeping their sheet ready ──

CACHE_TTL_S = 300  # a sheet is reused for 5 min (a call), then reloaded
_cache: dict[str, tuple[float, CallContext]] = {}
_pending: dict[str, asyncio.Task] = {}


def identify_client(messages: list) -> str | None:
    """
    The client the conversation is about: the last client the agent looked up (get_client), or the only client a
    search returned. None while nobody is identified. Works on the kit's ChatMessage objects.
    """
    found = None
    calls: dict[str, tuple[str, dict]] = {}
    for m in messages:
        for c in getattr(m, "tool_calls", None) or []:
            calls[c.id] = (c.name, c.arguments or {})
        if getattr(m, "role", None) != "tool":
            continue
        name = getattr(m, "name", None)
        try:
            result = json.loads(m.content or "null")
        except ValueError:
            continue
        if name == "get_client" and isinstance(result, dict) and str(result.get("id", "")).startswith("cli_"):
            found = result["id"]
        elif name == "search" and isinstance(result, list):
            clients = [r for r in result if isinstance(r, dict) and r.get("type") == "client"]
            if len(clients) == 1:
                found = clients[0].get("id")
    return found


def prefetch(erp: ErpClient, client_id: str) -> None:
    """Start loading a client's sheet in the background (no wait). Safe to call many times."""
    if _cached(client_id) or (client_id in _pending and not _pending[client_id].done()):
        return
    _pending[client_id] = asyncio.create_task(_load_and_cache(erp, client_id))


async def context_for(messages: list, erp: ErpClient) -> CallContext | None:
    """The sheet of the client this conversation is about (from cache, the background load, or loaded now)."""
    client_id = identify_client(messages)
    if not client_id:
        return None
    if cc := _cached(client_id):
        return cc
    task = _pending.get(client_id)
    try:
        return await (task if task and not task.done() else _load_and_cache(erp, client_id))
    except Exception as e:  # the sheet is a bonus: never fail the turn because of it
        print(f"[preload] sheet of {client_id} unavailable: {type(e).__name__}: {e}", flush=True)
        return None


def _cached(client_id: str) -> CallContext | None:
    hit = _cache.get(client_id)
    return hit[1] if hit and hit[0] > time.monotonic() else None


async def _load_and_cache(erp: ErpClient, client_id: str) -> CallContext:
    cc = await load_call_context(erp, client_id)
    _cache[client_id] = (time.monotonic() + CACHE_TTL_S, cc)
    print(f"[preload] sheet of {cc.name} loaded in {cc.loaded_ms} ms", flush=True)
    return cc


def clear_cache() -> None:
    _cache.clear()
    _pending.clear()


# ── Caller ID: who is calling, known BEFORE the call (form on the Voix page = the number on the screen) ──


def _digits(phone: str | None) -> str:
    d = re.sub(r"\D", "", phone or "")
    return "0" + d[2:] if d.startswith("33") and len(d) == 11 else d  # +33 6… → 06…


async def find_client_by_phone(erp: ErpClient, phone: str) -> tuple[str, str] | None:
    """(client_id, contact name) whose contact has this phone number, or None."""
    wanted = _digits(phone)
    if len(wanted) < 9:
        return None
    clients = await erp.get("/api/clients", {"limit": 500})
    clients = clients.get("items", clients) if isinstance(clients, dict) else clients
    for c in clients:
        for contact in c.get("contacts") or []:
            if _digits(contact.get("phone")) == wanted:
                return c["id"], contact.get("name") or ""
    return None


async def caller_context(
    erp: ErpClient,
    *,
    client_id: str | None = None,
    phone: str | None = None,
    contact_name: str | None = None,
    company_name: str | None = None,
    is_new: bool = False,
) -> CallContext | None:
    """
    The sheet of the caller announced before the call: an ERP client (by id, else by phone) loaded now (cache),
    or a NEW client (not in the ERP: status "new"). None if nothing was given.
    """
    if not is_new and not client_id and phone:
        if hit := await find_client_by_phone(erp, phone):
            client_id, contact_name = hit[0], contact_name or hit[1]
    if not is_new and client_id:
        cc = _cached(client_id) or await _load_and_cache(erp, client_id)
        cc.caller_contact = contact_name or cc.caller_contact
        cc.caller_phone = phone or cc.caller_phone
        return cc
    if is_new or company_name or phone or contact_name:
        # Not found in the ERP → a new client. Placeholder (to discuss with the team): the agent takes the details and
        # the request but confirms nothing; the wholesaler approves the new account first.
        return CallContext(
            client_id="",
            name=company_name or contact_name or "Nouveau client",
            status="new",
            caller_contact=contact_name,
            caller_phone=phone,
        )
    return None


NEW_CLIENT_RULES = (
    "NOUVEAU CLIENT, pas encore dans l'ERP. Accueille-le chaleureusement, demande ou confirme le nom de l'établissement, "
    "l'adresse de livraison et ce qu'il veut commander. Ne crée et ne confirme AUCUNE commande : explique que l'équipe "
    "ouvre son compte et le rappelle très vite pour valider sa première commande. Tu peux lui dire si un produit est "
    "disponible et son prix catalogue."
)


DAYS_FR = {"mon": "lundi", "tue": "mardi", "wed": "mercredi", "thu": "jeudi", "fri": "vendredi", "sat": "samedi", "sun": "dimanche"}  # fmt: skip


def render_for_prompt(cc: CallContext | None) -> str:
    """The sheet as the model reads it (French, compact). '' when nothing is loaded."""
    if cc is None:
        return ""
    on_phone = f"- Au téléphone : {cc.caller_contact}" + (f" ({cc.caller_phone})" if cc.caller_phone else "") if cc.caller_contact or cc.caller_phone else ""
    if cc.is_new:
        return "\n".join(p for p in [f"# Appelant identifié avant l'appel : {cc.name}", on_phone, NEW_CLIENT_RULES] if p)
    lines = [
        f"# Client au téléphone : {cc.name} ({cc.client_id})",
        "Il est déjà identifié (numéro reconnu) et sa fiche est chargée ci-dessous (à jour) : ne le recherche pas (pas de"
        " search, get_client ni get_context pour ce client), sers-toi de cette fiche et de son id. Utilise toujours les"
        " outils pour le stock d'un autre produit, les prix et la commande.",
        on_phone,
        f"- Statut : {cc.status}" + (" — COMPTE BLOQUÉ : ne rien promettre, prendre le message" if cc.blocked else ""),
        f"- Jours de livraison (ERP, ils font foi même si une note dit le contraire) : "
        f"{', '.join(DAYS_FR.get(d, d) for d in cc.delivery_days) or 'inconnus'}",
    ]
    prefs = " ".join(s for s in re.split(r"(?<=\.)\s+", cc.preferences) if not contradicts_delivery_days(s, cc.delivery_days))
    if prefs:
        lines.append(f"- Préférences : {prefs}")
    if cc.outstanding is not None:
        lines.append(f"- Encours : {cc.outstanding:.0f} € (plafond {cc.credit_limit or 0:.0f} €), problèmes ouverts : {cc.open_issues}")
    if cc.usual:
        usual = "; ".join(
            f"{u.product_name} ({u.product_id}) ~{u.avg_qty:g} {u.unit}" + (f", stock {u.available:g}" if u.available is not None else "")
            for u in cc.usual
            if u.avg_qty is not None
        )
        lines.append(f"- Commande habituelle : {usual}")
    for n in cc.notes:
        lines.append(f"- Note : {n}")
    for e in cc.context_entries:
        lines.append(f"## {e['title']} ({e['kind']})\n{e['body']}")
    return "\n".join(line for line in lines if line)
