"""
Company vocabulary for speech-to-text: the names a generic model mishears — product names and the aliases people
actually say ("loup" for bar), client names — read from the ERP and sent to the STT as context terms
(Soniox `context.terms`, Deepgram `keyterm`). Cached a few minutes: a product added in the ERP is heard soon after.
"""

import asyncio
import time

from app.tools.erp import ErpClient

TTL_S = 300  # refresh every 5 min
RETRY_S = 30  # ERP down: try again sooner
MAX_TERMS = 500

_cache: tuple[float, list[str]] = (0.0, [])  # (expires at, terms)
_lock = asyncio.Lock()


async def company_terms(erp: ErpClient | None = None) -> list[str]:
    """Client names, then product names, then product aliases, deduplicated: the most misheard first, since the
    STT keeps only the first ones (soniox.py MAX_TERMS_CHARS). [] when the ERP does not answer (never raises)."""
    global _cache
    async with _lock:
        expires, terms = _cache
        if time.monotonic() < expires:
            return terms
        erp = erp or ErpClient("voice_agent")
        try:
            products, clients = await asyncio.wait_for(
                asyncio.gather(erp.get("/api/products", {"limit": 500}), erp.get("/api/clients", {"limit": 500})), 3
            )
            names = [c.get("name") for c in clients] + [p.get("name") for p in products]
            names += [a for p in products for a in p.get("aliases") or []]
            terms = dedupe(names)[:MAX_TERMS]
            _cache = (time.monotonic() + TTL_S, terms)
        except Exception as e:  # ERP unreachable, other shape…: transcribe without vocabulary
            print(f"[ai] STT vocabulary unavailable ({type(e).__name__}: {e}), retry in {RETRY_S}s", flush=True)
            _cache = (time.monotonic() + RETRY_S, terms)
        return _cache[1]


def dedupe(names: list) -> list[str]:
    seen, out = set(), []
    for n in names:
        n = " ".join(str(n or "").replace(",", " ").split())  # the hint is a comma-separated list
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


async def stt_hint(stt_name: str, hint: str | None) -> str | None:
    """The hint sent to the STT: the caller's own hint first, then the company vocabulary.
    The mock STT returns its hint as the transcript, so it gets the caller's hint untouched."""
    if stt_name == "mock":
        return hint
    terms = await company_terms()
    return ", ".join([*([hint] if hint else []), *terms]) or None


def reset_cache() -> None:
    global _cache
    _cache = (0.0, [])
