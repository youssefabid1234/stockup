"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES (registered only when it is on) · see agent/rules_order.py (Jev section)

Jev (TypeSafe AI's decision model, recommended by Stockline's CTO) takes two small decisions of a phone order, in
~150 ms, with a probability instead of a guess:

  confirm_order   REPLACES the kit's tool of the same name (same name: every scenario expecting confirm_order still
                  works). Before confirming, Jev checks the caller's exact answer is a real yes to the read-back:
                  "Yes but put four," "yes... well wait," "how much?" are not. Blocking ERP
                  warnings (client blocked, credit limit, no route, missing stock) also stop it. No Jev key / Jev
                  down / no answer given → the model's judgement is kept (the kit's behaviour).
  resolve_product « tourage », « poudre », « du lait »… → the catalogue candidates, and Jev picks one using what the
                  client usually buys; below 0.6 confidence the agent asks instead of guessing.
"""

import asyncio
import time

from pydantic import Field

from .erp import enc
from .orders import summarize_order
from .registry import TOOLS, ToolContext, tool

TOOLS.pop("confirm_order", None)  # replaced below (this module is imported only when TEAM_ORDER_RULES is on)


@tool
async def confirm_order(
    ctx: ToolContext,
    order_id: str,
    client_answer: str | None = Field(None, description="The answer EXACTE from the client to your review, word for word (e.g. \"yes it's good\")"),
    read_back: str | None = Field(None, description="The rereading phrase you told her"),
) -> dict:
    """
    Confirm an order (reserves stock, affects tour) AFTER the rereading. Always give client_answer (its answer
    a verifier ensures that it is a true yes. If confirmed=false, follow "next" and do not try again
    without further response from the customer. Confirm an order after an explicit yes.
    """
    from app.agent.rules_order import JEV_YES_QUESTIONS, NEXT_STEP, WARNINGS_FOR_CALLER, classify_answer
    from app.clients import get_jev_client

    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    blocking = [w for w in order.get("warnings") or [] if WARNINGS_FOR_CALLER.get(w.get("code"), (None, False))[1]]
    if blocking:
        return {
            "confirmed": False,
            "decision": "blocked",
            "blockedBy": [w["code"] for w in blocking],
            "next": "Don't confirm: review_order and tell the client his \"alerts\" simply.",
        }

    check: dict = {"decidedBy": "agent"}
    jev = get_jev_client()
    if jev and client_answer:
        started = time.perf_counter()
        try:
            state = {"question_posee": read_back or "Do you want me to validate the order?", "reponse_du_client": client_answer}
            r = await jev.ask(state, JEV_YES_QUESTIONS)
            accord, change = r["answers"]["accord"]["noul"], r["answers"]["change"]["noul"]
            decision = classify_answer(accord, change)
            check = {
                "decidedBy": "jev",
                "decision": decision,
                "accord": round(accord, 2),
                "change": round(change, 2),
                "jevMs": int((time.perf_counter() - started) * 1000),
            }
            print(f"[jev] confirm_order « {client_answer} » → {decision} (accord {accord:.2f}, change {change:.2f}, "
                  f"{check['jevMs']} ms)", flush=True)
            if decision != "yes":
                return {"confirmed": False, **check, "next": NEXT_STEP[decision]}
        except Exception as e:  # Jev down / slow: keep the model's judgement (the kit's behaviour)
            check = {"decidedBy": "agent", "jevError": str(e)[:120]}
    if check["decidedBy"] == "agent":
        print(f"[jev] confirm_order without Jev (response given: {client_answer!r})", flush=True)
    return {"confirmed": True, **check, **summarize_order(await ctx.erp.post(f"/api/orders/{enc(order_id)}/confirm"))}


def _label(option: str) -> str:
    return option.split(" — ")[0]


@tool
async def resolve_product(
    ctx: ToolContext,
    client_id: str,
    said: str = Field(description="The product as the customer says: \"turning\", \"powder\", \"milk 38\"..."),
) -> dict:
    """
    Find the product of the catalogue that the customer means, even with an ambiguous word ("turning", "powder", "milk",
    "meal"): candidates from the catalogue + what the customer usually buys, and an auditor chooses. If "ask" is
    Now, ask this question instead of guessing. Resolve a Spoken product name to one catalog product.
    """
    from app.agent.rules_order import PICK_MIN, alias_match, short_name
    from app.clients import get_jev_client

    from .order_review import products_by_id

    # 1. An exact catalogue alias (« pain de levure », « tradi », « T45 ») settles it, no model needed
    catalogue = await products_by_id(ctx)
    if (pid := alias_match(said, catalogue)) is not None:
        return {"found": True, "productId": pid, "name": catalogue[pid]["name"], "decidedBy": "alias"}

    hits, usual = await asyncio.gather(
        ctx.erp.get("/api/search", {"q": said, "types": "product"}),
        ctx.erp.get(f"/api/clients/{enc(client_id)}/usual"),
    )
    candidates = [h for h in hits if h.get("type") == "product"][:6]
    if not candidates:
        return {"found": False, "ask": f"I do not find \" {said} » in the catalogue: can you describe it differently?"}
    if len(candidates) == 1:
        return {"found": True, "productId": candidates[0]["id"], "name": candidates[0]["label"], "decidedBy": "search"}

    usual_ids = {u["productId"] for u in usual or []}
    options = {
        c["id"]: " — ".join(
            filter(None, (c.get("label"), c.get("sublabel"), "usually purchased by this customer" if c["id"] in usual_ids else None))
        )
        for c in candidates
    }
    listed = [{"productId": k, "name": _label(v)} for k, v in options.items()]
    jev = get_jev_client()
    if not jev:
        return {"found": False, "candidates": listed}
    started = time.perf_counter()
    try:
        state = {
            "ce_que_dit_le_client": said,
            "ce_que_le_client_achete_d_habitude": [short_name(u["productName"]) for u in (usual or [])[:10]],
        }
        d = await jev.choose(state, "What product does the customer ask for in the catalogue?", options)
    except Exception as e:  # Jev down: the agent asks with the candidates
        return {"found": False, "jevError": str(e)[:120], "candidates": listed}
    ms = int((time.perf_counter() - started) * 1000)
    print(f"[jev] resolve_product « {said} » → {_label(options[d.choice])} (trust {d.confidence:.2f}, {ms} ms)", flush=True)
    if d.confidence >= PICK_MIN:
        return {"found": True, "productId": d.choice, "name": _label(options[d.choice]), "decidedBy": "jev",
                "confidence": round(d.confidence, 2), "jevMs": ms,
                "sayName": "Choose according to his habits: name this product in your answer so that he can correct."}
    top = [pid for pid, _ in sorted(d.probabilities.items(), key=lambda kv: -kv[1])[:3] if pid in options]
    names = [short_name(_label(options[pid])) for pid in top]
    ask = f"You mean {', '.join(names[:-1])} ou {names[-1]} ?" if len(names) > 1 else None
    return {"found": False, "decidedBy": "jev", "confidence": round(d.confidence, 2), "jevMs": ms,
            "candidates": [{"productId": pid, "name": _label(options[pid])} for pid in top], **({"ask": ask} if ask else {})}
