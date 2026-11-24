"""
Examples: Jev (the decision model, clients/jev.py) next to the LLM. NOT wired into the default agent: copy what you need.

Jev answers a typed question in a few hundred ms (168–752 ms measured) with probabilities, so it can take the small decisions of a voice
turn without a full LLM round-trip, and tell you when it is unsure (low confidence → ask the caller back).

    from app.clients import get_jev_client
    from app.agent.jev_examples import pick_product, is_yes

    jev = get_jev_client()                      # None when JEV_API_KEY is not set: keep the LLM path then
    if jev:
        hits = await ctx.erp.get("/api/search", {"q": "du bar", "types": "product"})
        product_id = await pick_product(jev, "Il me faut 5 kilos de bar de ligne", hits)
        # → "prd_0042", or None: too close to call, let the LLM ask "lequel ?"

Inside a @tool, `ctx.erp` is there already; elsewhere use `ErpClient("voice_agent")` (app.tools).
"""

from app.clients.jev import JevClient


async def pick_product(jev: JevClient, utterance: str, candidates: list[dict], min_confidence: float = 0.6) -> str | None:
    """Which of the search results did the caller mean? Returns its id, or None when Jev is not sure enough.

    `candidates` are /api/search results ({"id", "label", "sublabel", …}); the label + sublabel describe each option."""
    options = {c["id"]: " — ".join(filter(None, (c.get("label"), c.get("sublabel")))) or None for c in candidates}
    if len(options) <= 1:
        return next(iter(options), None)
    decision = await jev.choose(
        {"ce_que_dit_le_client": utterance},
        "Quel produit du catalogue le client demande-t-il ?",
        options,
    )
    return decision.choice if decision.confidence >= min_confidence else None


async def is_yes(jev: JevClient, question_asked: str, answer: str) -> bool | None:
    """Did the caller confirm? True / False, or None when unclear ("euh… plutôt le gros"): ask again."""
    p = await jev.yes_no(
        {"question_posee": question_asked, "reponse_du_client": answer},
        "Le client confirme ou accepte ce qu'on lui propose.",
    )
    return True if p >= 0.8 else False if p <= 0.2 else None
