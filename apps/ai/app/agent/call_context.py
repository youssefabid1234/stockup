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

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"


async def load_call_context(erp: ErpClient, client_id: str) -> CallContext:
    """
    v0 (working): client sheet + its context entries, fetched in parallel.
    TODO(Youssef):
      - stock of the usual items in parallel (fill UsualItem.available)
      - active price rules / promos for this client (GET /api/price-rules?active=true&clientId=…)
      - keep it small: the model re-reads it at every step (trim bodies, top N entries)
      - measure loaded_ms and keep it < 300 ms
    """
    t0 = time.perf_counter()
    client, ctx_for = await asyncio.gather(
        erp.get(f"/api/clients/{client_id}"),
        erp.get("/api/context/for", {"entityType": "client", "id": client_id}),
    )
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
        notes=[f"{n['at'][:10]} {n['author']} : {n['text']}" for n in (client.get("notes") or [])[-5:]],
        context_entries=[
            {"kind": e.get("kind"), "title": e.get("title"), "body": (e.get("body") or "")[:600]}
            for e in (ctx_for.get("entries") or [])[:12]
        ],
    )
    cc.loaded_ms = int((time.perf_counter() - t0) * 1000)
    return cc


DAYS_FR = {"mon": "lundi", "tue": "mardi", "wed": "mercredi", "thu": "jeudi", "fri": "vendredi", "sat": "samedi", "sun": "dimanche"}  # fmt: skip


def render_for_prompt(cc: CallContext | None) -> str:
    """The sheet as the model reads it (French, compact). '' when nothing is loaded."""
    if cc is None:
        return ""
    lines = [
        f"# Client au téléphone : {cc.name} ({cc.client_id})",
        f"- Statut : {cc.status}" + (" — COMPTE BLOQUÉ : ne rien promettre, prendre le message" if cc.blocked else ""),
        f"- Jours de livraison : {', '.join(DAYS_FR.get(d, d) for d in cc.delivery_days) or 'inconnus'}",
    ]
    if cc.preferences:
        lines.append(f"- Préférences : {cc.preferences}")
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
    return "\n".join(lines)
