"""
Team 12 · Replay our call scenarios against the running agent and check the results. OWNER: Youssef.

Real life: before opening the switchboard, Lucie's manager plays 8 typical calls and checks every answer.
Here: each scenarios/*.json is a call (several turns). For each turn we send the caller's words, collect what the
agent said, which ERP tools it used and how long it took, then check the scenario's expectations.

Run (services up, from the repo root, with the AI service's Python):
    apps/ai/.venv/Scripts/python scripts/run_scenarios.py                 # all, via POST /chat (no audio: free TTS)
    apps/ai/.venv/Scripts/python scripts/run_scenarios.py --only S03 S04  # some
    apps/ai/.venv/Scripts/python scripts/run_scenarios.py --owner daycem  # one owner's
    apps/ai/.venv/Scripts/python scripts/run_scenarios.py --voice         # through WS /voice: real voice timings (uses TTS credits)
    apps/ai/.venv/Scripts/python scripts/run_scenarios.py --reset         # reset the ERP data first (POST /api/admin/reset)
(mac/linux: apps/ai/.venv/bin/python)

Each turn uses the LLM (credits). Results: printed table + scenarios/results/<time>.json (git-ignored).

Expectations of a turn (all optional), see scenarios/README.md:
    tools_any  : at least one of these tools was called        tools_none : none of these was called
    says_any   : the answer contains one of these (no case)     says_none  : the answer contains none of these
    max_ms     : the turn took at most this (chat: whole turn; voice: end of speech → first audio byte)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
SCENARIOS = REPO / "scenarios"
AI = "http://localhost:4100"
ERP = "http://localhost:4000"


def load(only: list[str] | None, owner: str | None) -> list[dict]:
    out = []
    for f in sorted(SCENARIOS.glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        if only and s["id"] not in only:
            continue
        if owner and s.get("owner", "").lower() != owner.lower():
            continue
        out.append(s)
    return out


# ── one turn through POST /chat (mode voice, no audio) ──


async def turn_chat(client: httpx.AsyncClient, history: list[dict], said: str, actor: str | None, caller: str | None = None) -> dict:
    history.append({"role": "user", "content": said})
    body = {"messages": history, "mode": "voice", **({"actorName": actor} if actor else {}), **({"callerClientId": caller} if caller else {})}
    text, tools, ms, error, usage = "", [], None, None, None
    t0 = time.perf_counter()
    first_text_ms = None
    # Rebuild the full history like the web app does, so the next turn sees the ids returned by the tools (draft
    # order id…): per model step, one assistant message with its tool calls, then one "tool" message per result.
    step_text, step_calls = "", []
    async with client.stream("POST", f"{AI}/chat", json=body, timeout=120) as res:
        async for line in res.aiter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            match ev.get("type"):
                case "text":
                    if first_text_ms is None:
                        first_text_ms = int((time.perf_counter() - t0) * 1000)
                    text += ev.get("delta", "")
                    step_text += ev.get("delta", "")
                case "tool_call":
                    tools.append(ev["call"]["name"])
                    step_calls.append(ev["call"])
                case "tool_result":
                    if step_calls:  # first result of this step: close the assistant message that asked for the tools
                        history.append({"role": "assistant", "content": step_text, "toolCalls": step_calls})
                        step_text, step_calls = "", []
                    result = json.dumps(ev.get("result"), ensure_ascii=False, separators=(",", ":"))
                    history.append({"role": "tool", "toolCallId": ev["callId"], "name": ev["name"], "content": result})
                case "done":
                    ms, usage = ev.get("ms"), ev.get("usage")
                    final = (ev.get("message") or {}).get("content")
                    step_text = final if final is not None else step_text
                case "error":
                    error = ev.get("message")
    history.append({"role": "assistant", "content": step_text})
    return {"text": text.strip(), "tools": tools, "ms": ms, "firstTextMs": first_text_ms, "error": error, "usage": usage}


# ── one turn through WS /voice (typed text, real TTS) ──


async def voice_session(actor: str | None, caller: str | None):
    import websockets

    ws = await websockets.connect("ws://localhost:4100/voice", max_size=None)
    await ws.send(json.dumps({"type": "start", "sessionId": str(uuid.uuid4()), **({"actorName": actor} if actor else {})}))
    if caller:  # caller ID form: who calls, before the first word (the server answers caller_ready)
        await ws.send(json.dumps({"type": "caller", "clientId": caller}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            if isinstance(raw, str) and json.loads(raw).get("type") in ("caller_ready", "error"):
                break
    return ws


async def turn_voice(ws, said: str) -> dict:
    await ws.send(json.dumps({"type": "text", "text": said}))
    text, tools, error, timings = "", [], None, {}
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=120)
        if isinstance(raw, bytes):
            continue  # audio
        msg = json.loads(raw)
        match msg.get("type"):
            case "agent_text":
                text += msg.get("delta", "")
            case "agent_tool" if msg.get("args") is not None:
                tools.append(msg["name"])
            case "error":
                error = msg.get("message")
            case "agent_done":
                timings = msg.get("timings") or {}
                break
    return {"text": text.strip(), "tools": tools, "ms": timings.get("totalMs"), "timings": timings, "error": error}


def check(turn: dict, got: dict) -> list[str]:
    exp, problems = turn.get("expect") or {}, []
    said = got["text"].lower()
    if got.get("error"):
        problems.append(f"error: {got['error']}")
    if (anyof := exp.get("tools_any")) and not set(anyof) & set(got["tools"]):
        problems.append(f"no tool among {anyof}")
    if bad := set(exp.get("tools_none") or []) & set(got["tools"]):
        problems.append(f"forbidden tool {sorted(bad)}")
    if (anyof := exp.get("says_any")) and not any(w.lower() in said for w in anyof):
        problems.append(f"says none of {anyof}")
    if bad := [w for w in exp.get("says_none") or [] if w.lower() in said]:
        problems.append(f"says forbidden {bad}")
    if (limit := exp.get("max_ms")) and got.get("ms") and got["ms"] > limit:
        problems.append(f"{got['ms']} ms > {limit} ms")
    return problems


async def run(args) -> int:
    scenarios = load(args.only, args.owner)
    if not scenarios:
        print("no scenario matched")
        return 1
    async with httpx.AsyncClient() as client:
        if args.reset:
            (await client.post(f"{ERP}/api/admin/reset", timeout=120)).raise_for_status()
            print("ERP data reset")
        report, failed = [], 0
        for s in scenarios:
            print(f"\n=== {s['id']} · {s['title']}  (owner: {s.get('owner')})")
            history: list[dict] = []
            caller = None if args.no_caller else s.get("client")  # the scenario's client = the caller ID
            ws = await voice_session(s.get("actor"), caller) if args.voice else None
            try:
                for i, turn in enumerate(s["turns"], 1):
                    got = await (turn_voice(ws, turn["say"]) if ws else turn_chat(client, history, turn["say"], s.get("actor"), caller))
                    problems = check(turn, got)
                    failed += bool(problems)
                    status = "PASS" if not problems else "FAIL"
                    print(f"[{i}] client : {turn['say']}")
                    print(f"    agent  : {got['text']}")
                    print(f"    tools  : {', '.join(got['tools']) or '-'} · {got.get('ms')} ms"
                          + (f" · first text {got['firstTextMs']} ms" if got.get("firstTextMs") is not None else ""))
                    print(f"    {status}" + (f" — {'; '.join(problems)}" if problems else ""))
                    report.append({"scenario": s["id"], "turn": i, "say": turn["say"], **got, "problems": problems})
            finally:
                if ws:
                    await ws.close()
    try:  # the TEAM_* switches of the local .env (what the AI service loaded at its last restart)
        env = (REPO / ".env").read_text(encoding="utf-8").splitlines()
        on = [line.split("=")[0] for line in env if line.startswith("TEAM_") and line.split("=", 1)[1].split("#")[0].strip() in ("1", "true", "on", "yes")]
        print(f"\nswitches on (.env): {', '.join(on) or 'none'}")
    except OSError:
        pass
    out = SCENARIOS / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}{'-voice' if args.voice else ''}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    turns = len(report)
    times = sorted(r["ms"] for r in report if r.get("ms"))
    median = times[len(times) // 2] if times else None
    print(f"\n{turns - failed}/{turns} turns passed · median {median} ms · worst {times[-1] if times else None} ms · {out}")
    return 0 if failed == 0 else 2


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", nargs="*", help="scenario ids, e.g. S01 S04")
    p.add_argument("--owner", help="only this owner's scenarios")
    p.add_argument("--voice", action="store_true", help="through WS /voice (real timings, uses TTS credits)")
    p.add_argument("--reset", action="store_true", help="reset the ERP data first")
    p.add_argument("--no-caller", action="store_true", help="don't announce the scenario's client before the call (no caller ID)")
    sys.exit(asyncio.run(run(p.parse_args())))


if __name__ == "__main__":
    main()
