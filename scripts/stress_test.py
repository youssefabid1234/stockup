"""
Team 12 (Youssef) · run the 150 test calls of scripts/stress_cases.py against the real agent (POST /chat, voice mode,
caller ID = the case's client), judge each call, write a report (failures with their transcript, durations).

    cd apps/ai && .venv/bin/python ../../scripts/stress_test.py [--only T001 T002] [--workers 5]

Judging: hard rules (error, empty answer, confirm_order without an explicit yes, > 15 s) + an LLM judge (Claude
Sonnet 5.5, team key) that compares the call with the case's expected behaviour. The ERP is reset first (the demo
promo comes back by itself) so every run starts from the same data.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/ai"))
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("run_scenarios", ROOT / "scripts/run_scenarios.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from stress_cases import C as CASES  # noqa: E402

SLOW_MS = 15000
JUDGE = """Tu évalues un agent vocal de prise de commande d'un grossiste en fournitures de boulangerie (Le Fournil Occitan, Toulouse). Date de l'ERP : mardi 24/11/2026.
On te donne : la famille du test, le comportement attendu, et la transcription (ce que dit le client, ce que répond l'agent, les outils ERP appelés).
Réponds UNIQUEMENT par un objet JSON : {"verdict": "ok" | "ko", "gravite": "grave" | "moyen" | "mineur", "raison": "une phrase"}.
- "ko" seulement si l'agent contredit le comportement attendu sur un point qui compte : mauvaise quantité/produit/date, commande confirmée sans oui, promesse ou prix inventé, remplaçant imposé à un client qui refuse, compte bloqué servi, données d'un autre client divulguées, réponse incompréhensible ou hors sujet, ou rien de répondu.
- Une petite maladresse de ton ou une question de plus n'est PAS un ko (au plus "mineur" avec verdict ok).
- "grave" = erreur qui part dans l'ERP ou trompe le client ; "moyen" = mauvaise compréhension corrigeable ; "mineur" = détail."""


def transcript(case, turns) -> str:
    lines = []
    for t in turns:
        lines.append(f"CLIENT : {t['said']}")
        tools = ", ".join(t["tools"]) or "aucun"
        lines.append(f"AGENT ({(t['ms'] or 0) / 1000:.1f} s · outils : {tools}) : {t['text'] or '[rien]'}" + (f"  [ERREUR {t['error']}]" if t["error"] else ""))
    return "\n".join(lines)


async def judge(llm, case, turns) -> dict:
    from app.clients.base import LLMRequest, LLMText
    from app.schemas import ChatMessage

    user = f"Famille : {case['family']}\nAttendu : {case['expect']}\n\nTranscription :\n{transcript(case, turns)}"
    req = LLMRequest(system=JUDGE, messages=[ChatMessage(role="user", content=user)], max_tokens=4000)
    try:
        text = "".join([e.delta async for e in llm.stream(req) if isinstance(e, LLMText)])
        return json.loads(text[text.find("{") : text.rfind("}") + 1])
    except Exception as e:
        return {"verdict": "?", "gravite": "?", "raison": f"juge indisponible ({type(e).__name__})"}


def hard_checks(case, turns) -> list[str]:
    out = []
    for i, t in enumerate(turns, 1):
        if t["error"]:
            out.append(f"réplique {i} : erreur « {t['error'][:80]} »")
        elif not t["text"]:
            out.append(f"réplique {i} : aucune réponse")
        if t["ms"] and t["ms"] > SLOW_MS:
            out.append(f"réplique {i} : lente ({t['ms'] / 1000:.1f} s)")
    if not case["yes"] and any("confirm_order" in t["tools"] for t in turns):
        out.append("commande CONFIRMÉE alors que le client n'a jamais dit oui")
    return out


async def run_case(http, case) -> dict:
    history, turns = [], []
    for said in case["turns"]:
        try:
            got = await runner.turn_chat(http, history, said, None, caller=case["client"])
        except Exception as e:
            got = {"text": "", "tools": [], "ms": None, "error": f"{type(e).__name__}: {e}", "usage": None}
        turns.append({"said": said, **{k: got.get(k) for k in ("text", "tools", "ms", "error", "usage")}})
        if got.get("error") and not got.get("text"):
            break
    return {**case, "calls": turns}


async def main(args) -> int:
    from app.clients.factory import make_llm_client
    from app.config import settings

    cases = [c for c in CASES if not args.only or c["id"] in args.only]
    async with httpx.AsyncClient() as http:
        (await http.post(f"{runner.ERP}/api/admin/reset", timeout=120)).raise_for_status()
        print(f"ERP reset · {len(cases)} calls · {args.workers} at a time", flush=True)
        sem, done, t0 = asyncio.Semaphore(args.workers), 0, time.monotonic()

        async def one(c):
            nonlocal done
            async with sem:
                r = await run_case(http, c)
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(cases)} · {time.monotonic() - t0:.0f}s", flush=True)
            return r

        results = await asyncio.gather(*(one(c) for c in cases))
    print(f"calls done in {time.monotonic() - t0:.0f}s · judging…", flush=True)
    llm = make_llm_client(replace(settings.llm, model=args.judge_model))
    jsem = asyncio.Semaphore(8)

    async def j(r):
        async with jsem:
            r["judge"] = await judge(llm, r, r["calls"])
        r["hard"] = hard_checks(r, r["calls"])
        r["ok"] = r["judge"].get("verdict") == "ok" and not [h for h in r["hard"] if "lente" not in h]
        return r

    results = await asyncio.gather(*(j(r) for r in results))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_json = ROOT / f"scenarios/results/stress-{stamp}.json"
    out_json.parent.mkdir(exist_ok=True)
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    report = write_report(results)
    out_md = ROOT / f"scenarios/results/stress-{stamp}.md"
    out_md.write_text(report, encoding="utf-8")
    print(f"report: {out_md}")
    print(report.split("\n## ")[0][:3000])
    return 0


def write_report(results) -> str:
    all_ms = [t["ms"] for r in results for t in r["calls"] if t["ms"]]
    first_ms = [r["calls"][0]["ms"] for r in results if r["calls"] and r["calls"][0]["ms"]]
    ko = [r for r in results if not r["ok"]]
    # tokens → rough cost (Claude Sonnet 5.5 rates: in 2 $, cache write ~2.5 $, cache read 0.10 $, out 10 $ per million)
    u = {"in": 0, "out": 0, "cw": 0, "cr": 0}
    for r in results:
        for t in r["calls"]:
            x = t.get("usage") or {}
            u["in"] += x.get("inputTokens") or 0
            u["out"] += x.get("outputTokens") or 0
            u["cw"] += x.get("cacheCreationInputTokens") or 0
            u["cr"] += x.get("cacheReadInputTokens") or 0
    cost = (u["in"] * 2 + u["cw"] * 2.5 + u["cr"] * 0.1 + u["out"] * 10) / 1e6
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(len(xs) * p))] / 1000 if xs else 0  # noqa: E731
    lines = [
        "# 150 appels de test : résultats",
        "",
        f"- **Réussis : {len(results) - len(ko)}/{len(results)}** · échecs : {len(ko)} "
        f"(graves {sum(r['judge'].get('gravite') == 'grave' for r in ko)}, moyens {sum(r['judge'].get('gravite') == 'moyen' for r in ko)})",
        f"- Répliques : {len(all_ms)} · durée (fin de la phrase du client → réponse complète, /chat) : médiane **{statistics.median(all_ms) / 1000:.1f} s**, "
        f"90 % sous {q(all_ms, 0.9):.1f} s, pire {max(all_ms) / 1000:.1f} s",
        f"- 1re réplique de chaque appel : médiane **{statistics.median(first_ms) / 1000:.1f} s**, pire {max(first_ms) / 1000:.1f} s",
        f"- Coût estimé (clé de l'équipe) : ~{cost:.0f} $ (tokens : entrée {u['in']:,}, cache écrit {u['cw']:,}, cache lu {u['cr']:,}, sortie {u['out']:,})",
        "",
        "| Famille | Réussis | Médiane réplique | Pire |",
        "|---|---|---|---|",
    ]
    fams = {}
    for r in results:
        fams.setdefault(r["family"], []).append(r)
    for f, rs in fams.items():
        ms = [t["ms"] for r in rs for t in r["calls"] if t["ms"]]
        lines.append(f"| {f} | {sum(r['ok'] for r in rs)}/{len(rs)} | {statistics.median(ms) / 1000:.1f} s | {max(ms) / 1000:.1f} s |" if ms else f"| {f} | 0/{len(rs)} | – | – |")
    lines += ["", "## Échecs (transcription complète)", ""]
    order = {"grave": 0, "moyen": 1, "mineur": 2, "?": 3}
    for r in sorted(ko, key=lambda r: order.get(r["judge"].get("gravite"), 4)):
        lines += [
            f"### {r['id']} · {r['family']} · {r['client'] or 'inconnu'} · **{r['judge'].get('gravite', '?')}**",
            f"- Attendu : {r['expect']}",
            f"- Pourquoi c'est raté : {r['judge'].get('raison', '')}" + (f" · règles : {'; '.join(r['hard'])}" if r["hard"] else ""),
            "",
            "```",
            transcript(r, r["calls"]),
            "```",
            "",
        ]
    slow = [r for r in results if r["ok"] and any("lente" in h for h in r["hard"])]
    if slow:
        lines += ["## Réussis mais lents (> 15 s sur une réplique)", ""] + [f"- {r['id']} {r['family']} : {'; '.join(r['hard'])}" for r in slow]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--judge-model", default="claude-sonnet-5-5")
    sys.exit(asyncio.run(main(ap.parse_args())))
