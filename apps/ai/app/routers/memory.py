"""
Team 12 (Youssef) · what Lucie keeps from a call, outside the live conversation code (the page calls these):

  POST /calls/notebook  after each reply: her notebook changes (notes added, crossed out, corrected, questions to ask,
                        what is important, links), so whoever supervises the agent sees what she retains, at a glance;
  POST /calls/summary   after hanging up: a short summary written in the client's ERP history (a CRM note); the next
                        call's sheet shows it (with the orders, which the ERP already keeps), so she remembers.

Both use the fast model (TEAM_FAST_MODEL), never block a reply, and invent nothing (only what was said).
"""

from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent import call_context
from app.clients.base import LLMRequest, LLMText
from app.schemas import ChatMessage
from app.tools.erp import ErpClient, enc

router = APIRouter(prefix="/calls", tags=["calls"])
TIMEOUT_S = 8


class Said(BaseModel):
    who: str  # "client" | "lucie"
    text: str


class Note(BaseModel):
    id: str
    text: str
    kind: str = "info"
    status: str = "active"  # active | struck


class NotebookIn(BaseModel):
    clientName: str | None = None
    turns: list[Said]
    notes: list[Note] = []


class SummaryIn(BaseModel):
    clientId: str
    clientName: str | None = None
    turns: list[Said]


NOTEBOOK_RULES = """Tu tiens le carnet de notes de Lucie, standardiste d'un grossiste en boulangerie, pendant un appel.
On te donne le carnet actuel (notes avec leur id) et la fin de la conversation. Mets le carnet à jour comme une vraie
standardiste qui griffonne : seulement ce qui est utile à retenir (commande, quantité, jour, préférence, réclamation,
info client, chose à vérifier).
Réponds UNIQUEMENT en JSON : {"ops": [...]} avec au plus 4 opérations parmi :
  {"op": "add", "text": "≤ 8 mots, style note manuscrite", "kind": "commande|préférence|info|question|à faire|réclamation", "important": true|false}
  {"op": "strike", "id": "n3", "reason": "≤ 6 mots : pourquoi c'est barré (changé, annulé, faux)"}
  {"op": "edit", "id": "n3", "text": "nouvelle version (l'ancienne reste barrée)"}
  {"op": "link", "from": "n1", "to": "n4", "label": "≤ 3 mots"}
Règles : n'invente rien, ne recopie pas les prix ; ne répète pas une note existante ; si le client change d'avis, barre ou corrige l'ancienne
note ; une question encore sans réponse = kind "question" ; "important" seulement pour 1 ou 2 choses capitales
(commande confirmée, réclamation, compte bloqué). Rien à changer → {"ops": []}."""

SUMMARY_RULES = """Tu résumes un appel téléphonique entre Lucie (assistante vocale d'un grossiste en boulangerie) et un
client, pour l'historique du client. 1 à 3 lignes courtes, en français, sans rien inventer : ce qui a été commandé ou
demandé (produits, quantités, jour), les préférences ou habitudes apprises, ce qui reste à faire. Commence par
« Appel : ». Si rien d'utile, réponds seulement « RIEN »."""


def transcript(turns: list[Said]) -> str:
    return "\n".join(f"{'CLIENT' if t.who == 'client' else 'LUCIE'} : {t.text}" for t in turns if t.text.strip())


async def ask(system: str, content: str, max_tokens: int = 500) -> str:
    from app.agent.orchestrator import get_fast_llm_client

    req = LLMRequest(system=system, messages=[ChatMessage(role="user", content=content)], max_tokens=max_tokens)
    async with asyncio.timeout(TIMEOUT_S):
        return "".join([e.delta async for e in get_fast_llm_client().stream(req) if isinstance(e, LLMText)])


def parse_ops(text: str, notes: list[Note]) -> list[dict]:
    """The model's JSON → safe operations (known ids only, short texts, at most 4)."""
    try:
        ops = json.loads(text[text.find("{") : text.rfind("}") + 1]).get("ops") or []
    except (ValueError, AttributeError):  # cut short: keep the operations that are complete
        ops = []
        for chunk in re.findall(r"\{[^{}]*\}", text):
            try:
                ops.append(json.loads(chunk))
            except ValueError:
                pass
    ids, out = {n.id for n in notes}, []
    for op in ops[:4]:
        if not isinstance(op, dict):
            continue
        kind = op.get("op")
        if kind == "add" and str(op.get("text", "")).strip():
            out.append({"op": "add", "text": str(op["text"]).strip()[:80], "kind": str(op.get("kind") or "info"),
                        "important": bool(op.get("important"))})  # fmt: skip
        elif kind in ("strike", "edit") and op.get("id") in ids:
            out.append({k: str(v)[:80] for k, v in op.items() if k in ("op", "id", "reason", "text")})
        elif kind == "link" and op.get("from") in ids and op.get("to") in ids:
            out.append({"op": "link", "from": op["from"], "to": op["to"], "label": str(op.get("label") or "")[:30]})
    return out


@router.post("/notebook")
async def notebook(body: NotebookIn):
    if not body.turns:
        return {"ops": []}
    notes = "\n".join(f"{n.id} [{n.kind}{', barrée' if n.status == 'struck' else ''}] {n.text}" for n in body.notes) or "(vide)"
    content = f"Client : {body.clientName or 'inconnu'}\nCarnet actuel :\n{notes}\n\nFin de la conversation :\n{transcript(body.turns[-8:])}"
    try:
        return {"ops": parse_ops(await ask(NOTEBOOK_RULES, content, 900), body.notes)}
    except Exception as e:
        print(f"[carnet] indisponible ({type(e).__name__})", flush=True)
        return {"ops": []}


@router.post("/summary")
async def summary(body: SummaryIn):
    said = transcript(body.turns)
    if len([t for t in body.turns if t.text.strip()]) < 2 or not body.clientId:
        return {"saved": False}
    try:
        text = re.sub(r"\s+", " ", await ask(SUMMARY_RULES, said[-6000:], 300)).strip()
    except Exception as e:
        print(f"[résumé] indisponible ({type(e).__name__})", flush=True)
        return {"saved": False}
    if not text or text.upper().startswith("RIEN"):
        return {"saved": False}
    await ErpClient("voice_agent", "Lucie").post(f"/api/clients/{enc(body.clientId)}/notes",
                                                 {"text": text[:600], "author": "Lucie (assistante vocale)"})  # fmt: skip
    call_context.clear_cache()  # the next call reloads the sheet, with this note and the call's orders
    print(f"[résumé] {body.clientName or body.clientId} : {text}", flush=True)
    return {"saved": True, "text": text}
