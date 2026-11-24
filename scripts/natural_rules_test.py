"""
Team 12 (Youssef) · one generated test per « natural voice » rule, through the REAL voice session (WS /voice, typed
caller lines, real agent + real TTS), judged independently (a separate Claude Sonnet call that only sees the rule, the
expected behaviour and the transcript). Rules enforced in code (waiting phrases, nudge, varied openings) are also
exercised in-process. Writes a table + the transcripts.

    cd apps/ai && .venv/bin/python ../../scripts/natural_rules_test.py [--only R04 R07]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/ai"))
spec = importlib.util.spec_from_file_location("run_scenarios", ROOT / "scripts/run_scenarios.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

# id, rule (as written in the prompt / code), expected behaviour, caller client, what the caller says (in order)
LIVE = [
    ("R01", "Parler comme si l'info était sous les yeux, jamais « je vais vérifier »",
     "Répond directement avec l'info (« J'ai… », « Il me reste… »), sans « je vais vérifier / regarder / chercher / un instant ».",
     "cli_0006", ["Vous avez de la levure fraîche en ce moment ?"]),
    ("R02", "L'essentiel d'abord, 1 à 2 phrases courtes, une seule question à la fin",
     "Au plus 2-3 phrases courtes ; au plus UNE question, placée à la fin.",
     "cli_0024", ["Bonjour, il me faudrait de la crème."]),
    ("R03", "Accuser réception en reprenant ses mots",
     "Reprend la quantité et le produit dits (« dix sacs de tradi… ») dans sa réponse.",
     "cli_0060", ["Mettez-moi dix sacs de tradi pour jeudi."]),
    ("R04", "Varier : jamais deux réponses de suite avec le même premier mot, jamais la même phrase répétée",
     "Les réponses successives commencent par des mots différents et ne répètent pas une phrase déjà dite.",
     "cli_0021", ["Il me faut 5 sacs de T65 pour mercredi.", "Et ajoutez 10 pains de levure.", "Et 2 sacs de seigle aussi.", "C'est combien en tout ?"]),
    ("R05", "Langue parlée, pas écrite (pas de « veuillez », « nous disposons », « afin de »)",
     "Phrases orales et simples ; aucune tournure administrative ou écrite.",
     "cli_0042", ["Est-ce que vous livrez le samedi chez nous ?"]),
    ("R06a", "S'adapter : client pressé → réponse très courte, sans formule",
     "Réponse très brève (une phrase, idéalement moins de 20 mots), pas de politesse superflue.",
     "cli_0019", ["Vite, je suis en plein rush : 5 sacs de T65 pour vendredi, c'est tout."]),
    ("R06b", "S'adapter : client perdu → une information à la fois, plus lentement",
     "Une seule information ou suggestion simple, puis une seule question pour l'aider ; pas de liste.",
     "cli_0083", ["Euh… je débute, je sais pas trop ce qu'il me faut pour faire des croissants…"]),
    ("R07", "Vouvoyer, sauf si le client tutoie le premier",
     "Le client tutoie : l'agent le tutoie aussi (tu / te / ton), sans vouvoiement.",
     "cli_0045", ["Salut, tu peux me mettre 3 sacs de seigle pour samedi ?"]),
    ("R08", "Jamais plus de 3 options citées d'un coup",
     "Cite au plus 3 options (ou les 2 plus probables) puis demande ; pas d'énumération longue.",
     "cli_0075", ["Quelles farines vous avez ?"]),
    ("R09", "Mot mal compris : redemander seulement ce qui manque, en reprenant le reste",
     "Redemande précisément le mot douteux (quelle farine) en reprenant le reste (dix sacs, jeudi), pas « je n'ai pas compris ».",
     "cli_0080", ["Il me faut dix sacs de farine(?) pour jeudi."]),
    ("R10", "Question « robot ? » : se présenter honnêtement comme assistante vocale, puis continuer",
     "Dit être l'assistante vocale du Fournil Occitan, sans prétendre être humaine, et relance la conversation.",
     "cli_0033", ["Attendez, vous êtes un robot ?"]),
    ("R11", "Fin d'appel courte et chaleureuse",
     "Une courte formule chaleureuse de fin d'appel, sans outil ni relance commerciale.",
     "cli_0072", ["C'est tout, merci, au revoir !"]),
    ("R12", "Questions fermées (« je l'ajoute dedans ? »), jamais « A ou B ? »",
     "Pose une question fermée à laquelle « oui » répond sans ambiguïté ; pas de « ou bien ».",
     "cli_0021", ["Mettez-moi 3 sacs de tradi pour mercredi."]),
    ("R13", "Plus de 4 produits à relire → résumer (nombre, 2-3 principaux, total) et proposer le détail",
     "Ne lit pas toute la liste : donne le nombre de produits, 2-3 principaux, le total, et propose le détail.",
     "cli_0026", ["Comme d'habitude pour samedi."]),
    ("R14", "Nombres et prix dits comme à l'oral (pas de symboles)",
     "Prix dit en mots ou « 19 euros 80 », jamais « 19,80 € » ni « € ».",
     "cli_0001", ["C'est combien le sac de tradi pour nous ?"]),
    ("R15", "Raisonnement interne jamais prononcé (« la fiche du client dit… »)",
     "Aucune phrase sur ses règles, sa fiche ou ses outils ; seulement la réponse au client.",
     "cli_0099", ["5 cartons de tourage AOP pour mercredi."]),
]

JUDGE = """Tu contrôles UNE règle de style d'un agent vocal (standardiste d'un grossiste en boulangerie, au téléphone, en français).
On te donne la règle, le comportement attendu et la transcription. Juge UNIQUEMENT cette règle (pas le reste).
Réponds UNIQUEMENT en JSON : {"verdict": "respectée" | "partielle" | "non respectée", "pourquoi": "une phrase courte"}."""


def transcript(turns) -> str:
    return "\n".join(f"CLIENT : {t['said']}\nAGENT ({(t.get('ms') or 0) / 1000:.1f} s) : {t['text'] or '[rien]'}" for t in turns)


async def judge(llm, rule, expected, turns) -> dict:
    from app.clients.base import LLMRequest, LLMText
    from app.schemas import ChatMessage

    req = LLMRequest(system=JUDGE, messages=[ChatMessage(role="user", content=f"Règle : {rule}\nAttendu : {expected}\n\nTranscription :\n{transcript(turns)}")], max_tokens=2000)
    try:
        text = "".join([e.delta async for e in llm.stream(req) if isinstance(e, LLMText)])
        return json.loads(text[text.find("{") : text.rfind("}") + 1])
    except Exception as e:
        return {"verdict": "?", "pourquoi": f"juge indisponible ({type(e).__name__})"}


async def run_live(case) -> dict:
    rid, rule, expected, client, lines = case
    ws = await runner.voice_session(None, client)
    turns = []
    try:
        for said in lines:
            got = await runner.turn_voice(ws, said)
            turns.append({"said": said, "text": got["text"], "ms": got.get("ms"), "tools": got["tools"]})
    finally:
        await ws.close()
    return {"id": rid, "rule": rule, "expected": expected, "turns": turns}


# ── rules enforced in code, exercised in-process (no model, no network) ──


async def code_rules() -> list[dict]:
    from app.services import fillers, voice_reply, voice_session

    out = []
    # C1: waiting phrases never repeat back-to-back, each used before any repeats
    bank = fillers.FillerBank()
    bank.audio["thinking"] = [fillers.CachedAudio("audio/mpeg", p.encode()) for p in fillers.PHRASES["thinking"]]
    picks = [bank.pick("thinking").data.decode() for _ in range(12)]
    ok = all(a != b for a, b in zip(picks, picks[1:])) and len(set(picks[:8])) == 8
    out.append({"id": "C1", "rule": "Phrases d'attente variées (code) : jamais deux fois de suite la même, toutes avant de répéter",
                "expected": "12 tours d'attente → aucune répétition consécutive, les 8 phrases utilisées avant la 1re répétition.",
                "said": " → ".join(picks), "verdict": "respectée" if ok else "non respectée",
                "why": "aucune répétition consécutive, 8 phrases différentes sur les 8 premiers tours" if ok else "répétition détectée"})

    # C2: one nudge after a silence, varied, nothing in the history, never while the agent works
    class Sock:
        def __init__(self):
            self.events = []

        async def send_text(self, m):
            self.events.append(json.loads(m))

        async def send_bytes(self, b):
            self.events.append(b)

    class TTS:
        name = "test"

        async def synthesize(self, text, voice=None):
            from app.clients.base import TTSResult

            async def chunks():
                yield text.encode()

            return TTSResult("audio/mpeg", chunks())

    voice_session.get_tts_client = lambda: TTS()
    conn = voice_session.VoiceConnection(Sock())
    conn.conversation = voice_session.Conversation(id="t")
    said = []
    for _ in range(3):
        await conn.nudge()
        said.append(next(e["text"] for e in reversed(conn.ws.events) if isinstance(e, dict) and e.get("type") == "nudge_said"))
    conn.turn = asyncio.get_running_loop().create_future()  # the agent is working
    before = len(conn.ws.events)
    await conn.nudge()
    silent_while_busy = len(conn.ws.events) == before
    ok = len(set(said)) == 3 and conn.conversation.history == [] and silent_while_busy
    out.append({"id": "C2", "rule": "Relance après un silence (code) : une phrase courte et variée, hors historique, jamais pendant que l'agent travaille",
                "expected": "3 relances → 3 phrases différentes ; historique vide ; aucune relance pendant une réponse en cours.",
                "said": " | ".join(said), "verdict": "respectée" if ok else "non respectée",
                "why": f"3 phrases différentes, historique vide, rien pendant une réponse en cours : {silent_while_busy}"})

    # C3: never the same opening word twice in a row
    a = "Parfait, j'ai noté dix sacs de tradi."
    b = voice_reply.vary_opening("Parfait, et je vous ajoute la levure.", a)
    c = voice_reply.vary_opening("Très bien, c'est noté.", a)
    ok = b == "Et je vous ajoute la levure." and c == "Très bien, c'est noté."
    out.append({"id": "C3", "rule": "Ouverture variée (code) : pas deux réponses de suite commençant par le même mot d'accusé",
                "expected": "« Parfait, … » après « Parfait, … » → le 2e « Parfait » est retiré ; un autre accusé est gardé.",
                "said": f"« {a} » puis « Parfait, et je vous ajoute la levure. » → « {b} » ; « Très bien, c'est noté. » → « {c} »",
                "verdict": "respectée" if ok else "non respectée", "why": "le doublon est retiré, le reste est gardé" if ok else "transformation inattendue"})
    return out


async def main(args) -> int:
    from app.clients.factory import make_llm_client
    from app.config import settings

    cases = [c for c in LIVE if not args.only or c[0] in args.only]
    sem = asyncio.Semaphore(4)

    async def one(c):
        async with sem:
            try:
                return await run_live(c)
            except Exception as e:
                return {"id": c[0], "rule": c[1], "expected": c[2], "turns": [{"said": c[4][0], "text": f"[erreur {type(e).__name__}: {e}]", "ms": None}]}

    t0 = time.monotonic()
    live = await asyncio.gather(*(one(c) for c in cases))
    llm = make_llm_client(replace(settings.llm, model="claude-sonnet-5-5"))
    verdicts = await asyncio.gather(*(judge(llm, r["rule"], r["expected"], r["turns"]) for r in live))
    code = [] if args.only else await code_rules()
    rows = ["| # | Règle | Comportement attendu | Ce que l'agent a dit (test généré) | Verdict du juge |", "|---|---|---|---|---|"]
    md = []
    for r, v in zip(live, verdicts):
        said = " ⏎ ".join(t["text"] for t in r["turns"])
        icon = {"respectée": "✅", "partielle": "🟡", "non respectée": "❌"}.get(v.get("verdict"), "❔")
        rows.append(f"| {r['id']} | {r['rule']} | {r['expected']} | « {said[:260]}{'…' if len(said) > 260 else ''} » | {icon} {v.get('verdict')} : {v.get('pourquoi', '')} |")
        md += [f"### {r['id']} · {r['rule']}", "```", transcript(r["turns"]), "```", ""]
    for c in code:
        icon = "✅" if c["verdict"] == "respectée" else "❌"
        rows.append(f"| {c['id']} | {c['rule']} | {c['expected']} | {c['said']} | {icon} {c['verdict']} : {c['why']} |")
    report = "\n".join(["# Règles « voix naturelle » : test de chaque règle", "",
                        f"{len(live)} tests en direct (session vocale réelle) + {len(code)} tests du code · {time.monotonic() - t0:.0f} s", "",
                        *rows, "", "## Transcriptions", "", *md])
    out = ROOT / f"scenarios/results/natural-rules-{time.strftime('%Y%m%d-%H%M%S')}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nreport: {out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    sys.exit(asyncio.run(main(ap.parse_args())))
