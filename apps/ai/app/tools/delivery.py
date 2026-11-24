"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES (registered only when it is on) · see agent/rules_order.py

check_delivery_date: "pour jeudi", "demain", "au plus vite" → is it a delivery day of this client, still in time to
order for it, and if not, the next possible day. Deterministic (no model), one small ERP read, never wrong about the
calendar. The ERP's delivery days are the truth (see the decision in rules_order.py).
"""

from datetime import date, datetime, timedelta

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool


def pack_now(meta: dict) -> tuple[date, float]:
    """The pack's "now": business date (meta.today) and Paris hour from meta.generatedAt (06h30 for our pack)."""
    today = date.fromisoformat(meta["today"][:10])
    hour = 6.5
    if gen := meta.get("generatedAt"):
        try:
            utc = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            try:
                from zoneinfo import ZoneInfo

                local = utc.astimezone(ZoneInfo("Europe/Paris"))
            except Exception:  # no tz database in the container: Paris is UTC+1 in winter
                local = utc + timedelta(hours=1)
            if local.date() == today:
                hour = local.hour + local.minute / 60
        except ValueError:
            pass
    return today, hour


@tool
async def check_delivery_date(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0001"),
    asked: str | None = Field(None, description="Le jour tel que dit : « jeudi », « demain », « le 27 », « au plus vite » (vide = au plus vite)"),
) -> dict:
    """
    Vérifie un jour de livraison pour un client : jour de tournée du client, heure limite (17h la veille ; Lauragais-Tarn :
    la veille avant 12h). Renvoie ok + la date (YYYY-MM-DD, à passer à create_draft_order) et « say » (à dire), ou la raison
    et le prochain jour possible. À appeler dès qu'un jour de livraison est demandé. Check a delivery day for a client.
    """
    # imported here, not at the top: app.agent imports the tools package (a top-level import would be circular)
    from app.agent.rules_order import delivery_answer

    meta = await ctx.erp.get("/api/meta")
    client = await ctx.erp.get(f"/api/clients/{enc(client_id)}")
    today, hour = pack_now(meta)
    return {
        "client": client.get("name"),
        **delivery_answer(today, client.get("deliveryDays") or [], asked, hour, client.get("zone")),
    }
