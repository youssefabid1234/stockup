"""
OWNER: Amine Khalil (T6 de Youssef, idée 5 « SAV avec contexte stock ») · switch TEAM_ORDER_RULES (registered only when on)

A complaint in the middle of an order call, handled like Lucie does (data/context/04-playbook-clients.md, « Réclamations ») :

    « La livraison de ce matin, il manquait deux sacs de tradi. »
      report_delivery_issue → finds the REAL delivery concerned (the latest one with that product; if the caller says
                              « ce matin » and there was none, it says so: nothing is invented), the price paid, the
                              amount, records the complaint WITH the order, the product and the amount, and returns the
                              solutions the house allows: a free redelivery with the next delivery (if the stock
                              follows) or a credit note; above 150 € HT the management decides → nothing is promised.
      settle_delivery_issue → the solution the caller chose: a 0 € line on the next delivery (never a new paid order
                              for goods already paid), or the credit note written on the complaint for the ADV.
"""

import asyncio  # no `from __future__ import annotations`: the tool registry needs the real types
import re
from datetime import date
from typing import Literal

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool

DIRECTION_ABOVE = 150.0  # € HT: « un avoir au-delà de 150 € HT doit être validé par la direction »
DONE = ("prepared", "delivered", "invoiced")  # left the warehouse
TODAY_WORDS = re.compile(r"\b(?:ce matin|aujourd'?hui|tout à l'heure|tout a l'heure)\b", re.I)
EVENT_TYPE = {"manquant": "delivery_issue", "erreur": "delivery_issue", "abime": "quality_issue", "qualite": "quality_issue"}
PROBLEM_SAY = {"manquant": "manquant", "erreur": "erreur de livraison", "abime": "arrivé abîmé", "qualite": "problème de qualité"}


async def concerned_order(ctx: ToolContext, client_id: str, product_id: str, today: date, order_id: str | None) -> dict | None:
    """The delivery the complaint is about: the given order, else the latest one gone out with this product."""
    if order_id:
        return await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    rows = await ctx.erp.get("/api/orders", {"clientId": client_id, "limit": 30})
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    gone = sorted((o for o in rows if o.get("status") in DONE and o.get("deliveryDate", "") <= today.isoformat()),
                  key=lambda o: o["deliveryDate"], reverse=True)[:5]
    details = await asyncio.gather(*(ctx.erp.get(f"/api/orders/{enc(o['id'])}") for o in gone))
    return next((d for d in details if any(li.get("productId") == product_id for li in d.get("lines", []))), None)


@tool
async def report_delivery_issue(
    ctx: ToolContext,
    client_id: str,
    said: str = Field(description="Le produit tel que dit : « tradi », « levure »"),
    problem: Literal["manquant", "abime", "erreur", "qualite"] = Field(description="manquant = pas livré ; abime ; erreur = mauvais produit ; qualite"),
    qty: float | None = Field(None, description="La quantité concernée telle que dite (vide = toute la ligne)"),
    said_unit: str | None = Field(None, description="L'unité dite : « sacs », « kilos », « cartons »"),
    said_when: str | None = Field(None, description="Quand, tel que dit : « ce matin », « samedi »"),
    client_words: str | None = Field(None, description="Ce que dit le client, fidèlement"),
    order_id: str | None = Field(None, description="Seulement si le client a confirmé une autre livraison que celle proposée (ord_…)"),
) -> dict:
    """
    Réclamation sur une livraison (manquant, abîmé, erreur, qualité) en UN appel : retrouve la vraie livraison concernée,
    le prix payé et le montant, enregistre la réclamation avec la commande, et renvoie les solutions permises (relivraison
    gratuite à la prochaine livraison si le stock suit, ou avoir ; au-delà de 150 € HT, la direction décide). Si « next »
    est présent, rien n'est enregistré : pose sa question. Ne crée jamais de commande payante pour un manquant.
    """
    from app.agent.rules_order import delivery_answer, fr_money, french_day, say_quantity, short_name, to_selling_qty

    from .delivery import pack_now
    from .order_jev import resolve_product
    from .order_review import products_by_id

    meta, client, catalogue = await asyncio.gather(
        ctx.erp.get("/api/meta"), ctx.erp.get(f"/api/clients/{enc(client_id)}"), products_by_id(ctx)
    )
    today, hour = pack_now(meta)
    found = await resolve_product.fn(ctx, client_id, said)
    if not found.get("found"):
        return {"logged": False, "next": found.get("ask") or f"Quel produit pour « {said} » ?"}
    pid = found["productId"]
    p = catalogue[pid]
    name = short_name(p["name"])

    order = await concerned_order(ctx, client_id, pid, today, order_id)
    if not order:
        return {"logged": False, "next": f"Aucune livraison récente avec {name} pour ce client : demande la date de la livraison "
                                         "ou le numéro du bon, sans rien promettre."}
    delivered = date.fromisoformat(order["deliveryDate"])
    if not order_id and said_when and TODAY_WORDS.search(said_when) and delivered != today:
        return {"logged": False, "deliveryFound": {"orderId": order["id"], "date": french_day(delivered)},
                "next": f"Il n'y a pas eu de livraison {name} ce matin : la dernière est celle du {french_day(delivered)}. "
                        "Demande si c'est bien celle-là ; si oui, rappelle report_delivery_issue avec cet order_id."}

    line = next(li for li in order["lines"] if li.get("productId") == pid)
    missing = line["qty"] if qty is None else to_selling_qty(qty, said_unit, p["unit"], p.get("caliber") or "", p["name"])
    missing = min(missing, line["qty"])
    price = line.get("unitPrice") or 0
    amount = round(missing * price, 2)
    qty_say = say_quantity(missing, p["unit"], p.get("caliber"))

    event = await ctx.erp.post(f"/api/clients/{enc(client_id)}/events", {
        "type": EVENT_TYPE[problem],
        "title": f"Réclamation : {qty_say} de {name} {PROBLEM_SAY[problem]} (livraison du {french_day(delivered)})",
        "description": client_words or None,
        "severity": "high" if amount > DIRECTION_ABOVE else "medium",
        "orderId": order["id"], "productIds": [pid], "amount": amount,
    })
    out = {"logged": True, "eventId": event.get("id"), "orderId": order["id"], "deliverySay": french_day(delivered),
           "productId": pid, "qty": missing, "qtySay": qty_say, "amountHt": amount, "amountSay": fr_money(amount)}
    if amount > DIRECTION_ABOVE:
        return {**out, "options": [], "next": "Réclamation enregistrée. Au-delà de 150 € HT, la direction décide : ne promets ni "
                                              "avoir ni relivraison ; dis que le responsable rappelle dans la journée."}
    options = ["avoir"]
    nxt = delivery_answer(today, client.get("deliveryDays") or [], None, hour, client.get("zone"))
    product = await ctx.erp.get(f"/api/products/{enc(pid)}")
    if nxt.get("ok") and (product.get("available") or 0) >= missing:
        options.insert(0, "relivraison")
        out["redeliverySay"] = nxt["say"]
    return {**out, "options": options,
            "next": "Réclamation enregistrée avec la livraison concernée. Excuse-toi en une phrase, puis propose les options : "
                    + ("relivraison gratuite le " + nxt["say"] + " avec la prochaine livraison, ou " if "relivraison" in options else "")
                    + f"un avoir de {fr_money(amount)} hors taxes sur la prochaine facture. Puis settle_delivery_issue avec son choix."}


@tool
async def settle_delivery_issue(
    ctx: ToolContext,
    client_id: str,
    solution: Literal["relivraison", "avoir"],
    event_id: str = Field(description="eventId renvoyé par report_delivery_issue"),
    product_id: str = Field(description="productId renvoyé par report_delivery_issue"),
    qty: float = Field(description="qty renvoyée par report_delivery_issue"),
    amount_ht: float = Field(description="amountHt renvoyé par report_delivery_issue"),
    order_id: str | None = Field(None, description="La commande en cours de cet appel, s'il y en a une (la relivraison y est ajoutée)"),
) -> dict:
    """
    Applique la solution choisie par le client pour une réclamation : relivraison gratuite (ligne à 0 € sur la prochaine
    livraison, dans la commande en cours s'il y en a une) ou avoir (noté sur la réclamation pour l'ADV). Jamais au-delà
    de 150 € HT (la direction décide).
    """
    from app.agent.rules_order import delivery_answer, fr_money

    from .delivery import pack_now
    from .order_review import review_for

    if amount_ht > DIRECTION_ABOVE:
        return {"done": False, "next": "Au-delà de 150 € HT : la direction décide ; dis que le responsable rappelle."}
    if solution == "avoir":
        await ctx.erp.patch(f"/api/client-events/{enc(event_id)}", {
            "resolution": f"Avoir de {amount_ht:.2f} € HT à établir sur la prochaine facture (accepté par le client au téléphone)",
            "tags": ["avoir"],
        })
        return {"done": True, "say": f"un avoir de {fr_money(amount_ht)} hors taxes sur votre prochaine facture"}

    note = f"Relivraison gratuite (réclamation {event_id})"
    free = {"productId": product_id, "qty": qty, "unitPrice": 0, "note": note}
    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}") if order_id else None
    if order and order.get("status") in ("draft", "confirmed"):
        await ctx.erp.post(f"/api/orders/{enc(order_id)}/lines", free)
    else:
        meta, client = await asyncio.gather(ctx.erp.get("/api/meta"), ctx.erp.get(f"/api/clients/{enc(client_id)}"))
        today, hour = pack_now(meta)
        nxt = delivery_answer(today, client.get("deliveryDays") or [], None, hour, client.get("zone"))
        created = await ctx.erp.post("/api/orders", {"clientId": client_id, "deliveryDate": nxt.get("date"),
                                                     "source": "voice_agent", "lines": [free]})
        order_id = created["id"]
    await ctx.erp.patch(f"/api/client-events/{enc(event_id)}", {"resolution": f"Relivraison gratuite ajoutée à la commande {order_id}"})
    review = await review_for(ctx, order_id)
    return {"done": True, "orderId": order_id, "freeLine": True, **review}
