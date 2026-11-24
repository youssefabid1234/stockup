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
from dataclasses import dataclass, field, replace

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
    recent_orders: list[str] = field(default_factory=list)  # team 12: latest orders, newest first, ready to say
    sales_rep: str | None = None  # team 12 (Daycem, T5): the client's sales rep from the ERP card (salesRep)
    company_name: str | None = None  # team 12: a NEW client's business name typed in the form (None = to ask)
    prospect_note: str = ""  # team 12: a prospect calling back: its card and the requests already noted

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
    client, ctx_for, orders = await asyncio.gather(
        erp.get(f"/api/clients/{client_id}"),
        erp.get("/api/context/for", {"entityType": "client", "id": client_id}),
        _safe(erp.get("/api/orders", {"clientId": client_id, "limit": 3})),  # « c'est quoi ma dernière commande ? »
    )
    days = client.get("deliveryDays") or []
    cc = CallContext(
        client_id=client["id"],
        name=client.get("name", ""),
        status=client.get("status", "active"),
        delivery_days=client.get("deliveryDays") or [],
        preferences=client.get("preferences") or "",
        contacts=client.get("contacts") or [],
        sales_rep=client.get("salesRep") or None,
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
    # Stock of the usual items and the lines of the latest orders, in parallel.
    rows = orders.get("items", orders) if isinstance(orders, dict) else orders
    rows = [o for o in rows if isinstance(o, dict) and o.get("id")][:3] if isinstance(rows, list) else []
    details = await asyncio.gather(*(_safe(erp.get(f"/api/orders/{o['id']}")) for o in rows))
    cc.recent_orders = [describe_order(o, d) for o, d in zip(rows, details, strict=True)]
    stocks = await asyncio.gather(
        *(erp.get(f"/api/products/{u.product_id}") for u in cc.usual if u.product_id), return_exceptions=True
    )
    for u, p in zip([u for u in cc.usual if u.product_id], stocks, strict=True):
        if isinstance(p, dict):
            u.available = p.get("available")
    cc.loaded_ms = int((time.perf_counter() - t0) * 1000)
    return cc


async def _safe(coro):
    """An optional read: never let it break the sheet (None on any error)."""
    try:
        return await coro
    except Exception:
        return None


STATUS_FR = {"draft": "brouillon", "confirmed": "confirmée", "delivered": "livrée", "invoiced": "facturée", "cancelled": "annulée"}


def describe_order(summary: dict, detail: dict | None) -> str:
    """« jeu. 26/11 · confirmée · 151 € : 10 sac de tradi, 5 kg de demi-sel » (lines when the detail loaded)."""
    from datetime import date

    day = summary.get("deliveryDate") or ""
    try:
        d = date.fromisoformat(day[:10])
        when = f"{DAYS_FR[['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][d.weekday()]]} {d:%d/%m}"
    except (ValueError, KeyError):
        when = day
    head = f"{when} · {STATUS_FR.get(summary.get('status'), summary.get('status') or '?')}"
    if summary.get("totalHt") is not None:
        head += f" · {summary['totalHt']:.0f} €"
    lines = []
    for li in (detail or {}).get("lines") or []:
        name = li.get("productName") or li.get("name") or li.get("productId") or "?"
        qty = li.get("qty", li.get("quantity"))
        lines.append(f"{qty:g} {li.get('unit') or ''} {name}".replace("  ", " ") if isinstance(qty, (int, float)) else name)
    return head + (" : " + ", ".join(lines[:8]) + (" …" if len(lines) > 8 else "") if lines else f" ({summary.get('lineCount', '?')} lignes)")


_LEAD = re.compile(r"\bJ\s*-\s*(\d+)\b")


def order_lead_days(preferences: str) -> int | None:
    """« Bon de commande à J-3 » → 3 (the client must order N days before delivery)."""
    m = _LEAD.search(preferences or "")
    return int(m.group(1)) if m else None


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
    # A phone found in the ERP wins over the form's « nouveau client » box (ticked by mistake, or a colleague of a
    # known bakery): no duplicate prospect, the agent gets the real sheet.
    if not client_id and phone:
        if hit := await find_client_by_phone(erp, phone):
            client_id, contact_name = hit[0], contact_name or hit[1]
    if client_id:
        shared = _cached(client_id) or await _load_and_cache(erp, client_id)
        if shared.status == "prospect":  # registered at a first call, account not opened yet: still a new client
            return await _prospect_sheet(erp, shared, contact_name, phone)
        # A copy per call: the cached sheet is shared (Guy then Nadine calling for the same bakery must not mix).
        return replace(shared, caller_contact=contact_name, caller_phone=phone)
    if is_new or company_name or phone or contact_name:
        # Not found in the ERP → a new client. Placeholder (to discuss with the team): the agent takes the details and
        # the request but confirms nothing; the wholesaler approves the new account first.
        return CallContext(
            client_id="",
            name=company_name or contact_name or "Nouveau client",
            status="new",
            caller_contact=contact_name,
            caller_phone=phone,
            company_name=company_name,
        )
    return None


# Order tools a new client (or a prospect) never gets: the team opens the account first (voice_session removes them).
NO_ORDER_FOR_NEW = frozenset({
    "create_draft_order", "add_order_line", "confirm_order", "place_order", "review_order", "update_order_line",
    "remove_order_line", "change_delivery_date", "cancel_draft_order",
})  # fmt: skip


async def _prospect_sheet(erp: ErpClient, shared: CallContext, contact_name: str | None, phone: str | None) -> CallContext:
    """A prospect (card made by register_new_client at a first call) calls back: the new-client flow, on its card."""
    from app.tools.erp import enc

    try:
        detail, events = await asyncio.gather(
            erp.get(f"/api/clients/{enc(shared.client_id)}"), erp.get(f"/api/clients/{enc(shared.client_id)}/events")
        )
        events = events.get("items", events) if isinstance(events, dict) else events
    except Exception:
        detail, events = {}, []
    asked = [(e.get("description") or "").split(" · contact")[0].split(" · tél.")[0] for e in events or [] if e.get("type") == "onboarding"]
    where = ", ".join(x for x in (detail.get("address"), detail.get("city")) if x)
    note = (f"Déjà enregistré comme prospect lors d'un premier appel (fiche {shared.client_id})" + (f" : {where}" if where else "")
            + (f". Déjà noté : {' | '.join(a for a in asked[:5] if a)}" if asked else "") + ". Le compte n'est pas encore ouvert.")
    return CallContext(
        client_id=shared.client_id, name=shared.name, status="new", caller_contact=contact_name, caller_phone=phone,
        company_name=shared.name, prospect_note=note,
    )  # fmt: skip


NEW_CLIENT_RULES = (
    "Premier appel : accueille-le chaleureusement. Ce qui est écrit ci-dessus est connu : ne le redemande jamais. Demande "
    "ce qui manque, une seule question à la fois : le nom de l'établissement s'il n'est pas connu, son activité si elle "
    "n'est pas claire (boulangerie, pâtisserie, restaurant…), la ville de livraison, puis ce qu'il voudrait (produits, "
    "quantités, jour souhaité) ; l'adresse précise si elle vient naturellement.\n"
    "- Dès que tu connais l'établissement et sa demande, appelle register_new_client (avec la ville si tu l'as, et le nom "
    "et le téléphone ci-dessus) : sa fiche et sa demande sont alors enregistrées pour l'équipe. Ne dis « c'est noté » ou "
    "« c'est enregistré » qu'après cet appel. Rappelle-le avec seulement le nouveau point s'il ajoute un produit, donne "
    "la ville ou l'adresse ensuite (même fiche, jamais de doublon). S'il raccroche avant, appelle-le quand même avec ce "
    "que tu sais.\n"
    "- Un nouveau produit sans précision (« du beurre, deux kilos ») : enregistre-le TOUT DE SUITE avec "
    "register_new_client (« beurre, 2 kg, type à préciser »), puis pose ta question de précision une seule fois. "
    "S'il répond, rappelle l'outil avec la précision ; s'il répond « merci » ou parle d'autre chose, ne repose jamais "
    "la question : c'est noté « à préciser », l'équipe verra avec lui.\n"
    "- Ne crée et ne confirme AUCUNE commande (pas de create_draft_order, place_order ni confirm_order) : l'équipe ouvre son "
    "compte et le rappelle très vite pour valider sa première commande et le jour de livraison. Ne promets aucune date.\n"
    "- Tu peux dire si un produit est disponible et donner son prix catalogue, présenté comme indicatif (le tarif est fixé "
    "à l'ouverture du compte). Conditions de paiement, franco, livraison : seulement ce que disent les documents de "
    "l'entreprise et register_new_client (secteur et jours de tournée, ou hors zone).\n"
    "- Si register_new_client répond qu'il existe déjà, ce n'est pas un nouveau client : traite-le comme un client connu "
    "avec l'id donné."
)


DAYS_FR = {"mon": "lundi", "tue": "mardi", "wed": "mercredi", "thu": "jeudi", "fri": "vendredi", "sat": "samedi", "sun": "dimanche"}  # fmt: skip


def render_for_prompt(cc: CallContext | None) -> str:
    """The sheet as the model reads it (French, compact). '' when nothing is loaded."""
    if cc is None:
        return ""
    on_phone = f"- Au téléphone : {cc.caller_contact}" + (f" ({cc.caller_phone})" if cc.caller_phone else "") if cc.caller_contact or cc.caller_phone else ""
    if cc.is_new:
        known = (f"- Établissement (donné avant l'appel, ne le redemande pas) : {cc.company_name}" if cc.company_name
                 else "- Établissement : pas encore connu, à demander")
        prospect = f"- {cc.prospect_note}" if cc.prospect_note else ""
        return "\n".join(p for p in ["# NOUVEAU CLIENT au téléphone (pas encore dans l'ERP)", known, on_phone, prospect, NEW_CLIENT_RULES] if p)
    lines = [
        f"# Client au téléphone : {cc.name} ({cc.client_id})",
        "Il est déjà identifié (numéro reconnu) et sa fiche est chargée ci-dessous (à jour) : ne le recherche pas (pas de"
        " search, get_client ni get_context pour ce client), sers-toi de cette fiche et de son id. Utilise toujours les"
        " outils pour le stock d'un autre produit, les prix et la commande.",
        on_phone,
        f"- Commercial(e) : {cc.sales_rep}" if cc.sales_rep else "",
        f"- Statut : {cc.status}" + (" — COMPTE BLOQUÉ : ne rien promettre, prendre le message" if cc.blocked else ""),
        f"- Jours de livraison (ERP, ils font foi même si une note dit le contraire) : "
        f"{', '.join(DAYS_FR.get(d, d) for d in cc.delivery_days) or 'inconnus'}",
    ]
    prefs = " ".join(s for s in re.split(r"(?<=\.)\s+", cc.preferences) if not contradicts_delivery_days(s, cc.delivery_days))
    if prefs:
        lines.append(f"- Préférences : {prefs}")
    if (lead := order_lead_days(cc.preferences)) is not None:
        lines.append(f"- Délai de commande : J-{lead} (il commande {lead} jours avant la livraison). Pour une livraison plus "
                     "proche, dis-le-lui d'abord et propose la première date qui respecte ce délai (ou demande si c'est urgent).")
    if cc.outstanding is not None:
        lines.append(f"- Encours : {cc.outstanding:.0f} € (plafond {cc.credit_limit or 0:.0f} €), problèmes ouverts : {cc.open_issues}")
    if cc.usual:
        usual = "; ".join(
            f"{u.product_name} ({u.product_id}) ~{u.avg_qty:g} {u.unit}" + (f", stock {u.available:g}" if u.available is not None else "")
            for u in cc.usual
            if u.avg_qty is not None
        )
        lines.append(f"- Commande habituelle : {usual}")
    if cc.recent_orders:
        lines.append("- Dernières commandes (la plus récente d'abord) : " + " | ".join(cc.recent_orders))
    for n in cc.notes:
        lines.append(f"- Note : {n}")
    for e in cc.context_entries:
        lines.append(f"## {e['title']} ({e['kind']})\n{e['body']}")
    return "\n".join(line for line in lines if line)
