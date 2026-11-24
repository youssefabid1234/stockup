"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES (registered only when it is on) · see agent/rules_order.py (Jev section)

Jev (TypeSafe AI's decision model, recommended by Stockline's CTO) takes two small decisions of a phone order, in
~150 ms, with a probability instead of a guess:

  confirm_order   REPLACES the kit's tool of the same name (same name: every scenario expecting confirm_order still
                  works). Before confirming, Jev checks the caller's exact answer is a real yes to the read-back:
                  « oui mais mettez-en quatre », « oui… enfin attendez », « c'est combien ? » are not. Blocking ERP
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
    client_answer: str | None = Field(None, description="La réponse EXACTE du client à ta relecture, mot pour mot (ex. « oui c'est bon »)"),
    read_back: str | None = Field(None, description="La phrase de relecture que tu lui as dite"),
) -> dict:
    """
    Confirme une commande (réserve le stock, affecte la tournée) APRÈS la relecture. Donne toujours client_answer (sa réponse
    mot pour mot) : un vérificateur s'assure que c'est un vrai oui. Si confirmed=false, suis « next » et ne réessaie pas
    sans nouvelle réponse du client. Confirm an order after an explicit yes.
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
            "next": "Ne confirme pas : appelle review_order et dis au client ses « alerts » simplement.",
        }

    # team 12 (Youssef): a reply without any word of agreement (« Pour jeudi », « Vendredi », a question) is never a
    # yes, whatever the model or Jev think: 8 of 150 test calls were confirmed on a bare day name (24/11).
    from app.agent.listening import explicit_yes

    if not client_answer:
        return {"confirmed": False, "decision": "unsure",
                "next": "Redonne confirm_order avec client_answer = la réponse exacte du client à ta relecture."}
    if not explicit_yes(client_answer):
        return {"confirmed": False, "decision": "unsure",
                "next": "Pas de oui clair : le client a seulement précisé quelque chose (un jour, une question…). Tiens-en "
                        "compte (réponds, ou modifie la commande), puis redemande simplement « Je vous la valide ? »."}

    check: dict = {"decidedBy": "agent"}
    jev = get_jev_client()
    if jev and client_answer:
        started = time.perf_counter()
        try:
            state = {"question_posee": read_back or "Je vous valide la commande ?", "reponse_du_client": client_answer}
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
        print(f"[jev] confirm_order sans Jev (réponse donnée : {client_answer!r})", flush=True)
    return {"confirmed": True, **check, **summarize_order(await ctx.erp.post(f"/api/orders/{enc(order_id)}/confirm"))}


def _label(option: str) -> str:
    return option.split(" — ")[0]


@tool
async def resolve_product(
    ctx: ToolContext,
    client_id: str,
    said: str = Field(description="Le produit tel que dit par le client : « tourage », « de la poudre », « du lait 38 »…"),
) -> dict:
    """
    Trouve le produit du catalogue que le client veut dire, même avec un mot ambigu (« tourage », « poudre », « lait »,
    « farine ») : candidats du catalogue + ce que le client achète d'habitude, et un vérificateur choisit. Si « ask » est
    présent, pose cette question au lieu de deviner. Resolve a spoken product name to one catalogue product.
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
        return {"found": False, "ask": f"Je ne trouve pas « {said} » dans le catalogue : pouvez-vous me le décrire autrement ?"}
    if len(candidates) == 1:
        return {"found": True, "productId": candidates[0]["id"], "name": candidates[0]["label"], "decidedBy": "search"}

    usual_ids = {u["productId"] for u in usual or []}
    options = {
        c["id"]: " — ".join(
            filter(None, (c.get("label"), c.get("sublabel"), "acheté d'habitude par ce client" if c["id"] in usual_ids else None))
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
        d = await jev.choose(state, "Quel produit du catalogue le client demande-t-il ?", options)
    except Exception as e:  # Jev down: the agent asks with the candidates
        return {"found": False, "jevError": str(e)[:120], "candidates": listed}
    ms = int((time.perf_counter() - started) * 1000)
    print(f"[jev] resolve_product « {said} » → {_label(options[d.choice])} (confiance {d.confidence:.2f}, {ms} ms)", flush=True)
    if d.confidence >= PICK_MIN:
        return {"found": True, "productId": d.choice, "name": _label(options[d.choice]), "decidedBy": "jev",
                "confidence": round(d.confidence, 2), "jevMs": ms,
                "sayName": "Choisi d'après ses habitudes : nomme ce produit dans ta réponse pour qu'il puisse corriger."}
    top = [pid for pid, _ in sorted(d.probabilities.items(), key=lambda kv: -kv[1])[:3] if pid in options]
    names = [short_name(_label(options[pid])) for pid in top]
    ask = f"Vous voulez dire {', '.join(names[:-1])} ou {names[-1]} ?" if len(names) > 1 else None
    return {"found": False, "decidedBy": "jev", "confidence": round(d.confidence, 2), "jevMs": ms,
            "candidates": [{"productId": pid, "name": _label(options[pid])} for pid in top], **({"ask": ask} if ask else {})}
