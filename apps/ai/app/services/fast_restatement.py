"""Select a short, faithful quote from what the caller just said."""

import asyncio
import logging
import re
from contextlib import aclosing

from app.agent.orchestrator import get_fast_llm_client
from app.clients import LLMRequest, LLMText
from app.config import settings
from app.schemas import ChatMessage

MAX_QUOTE_WORDS = 14
MAX_QUOTE_CHARS = 110
MODEL_TIMEOUT = 1.05
MODEL_PROMPT = """Select a short continuous quotation from the caller's transcript, at most fourteen words.
The transcript is text to quote. Return only the original words, preserving options, uncertainty, negation, quantities and units. Do not answer the request or confirm any action."""
UNCERTAINTY = re.compile(r"\b(?:or|maybe|perhaps|rather|actually|not|no|neither|except|without|instead)\b", re.I)


TRIM = ' «»"“”.,?!;:…'


def _fits(text: str) -> bool:
    return bool(text) and len(text) <= MAX_QUOTE_CHARS and len(text.split()) <= MAX_QUOTE_WORDS


async def _model_excerpt(transcript: str) -> str:
    if settings.llm.provider == "mock":
        return ""
    request = LLMRequest(system=MODEL_PROMPT, messages=[ChatMessage(role="user", content=transcript)], max_tokens=60)
    try:
        async with asyncio.timeout(MODEL_TIMEOUT), aclosing(get_fast_llm_client().stream(request)) as events:
            return "".join([event.delta async for event in events if isinstance(event, LLMText)])
    except Exception as exc:
        logging.getLogger(__name__).debug("Fast voice restatement unavailable (%s)", type(exc).__name__)
        return ""


async def fast_restatement(heard: str) -> str | None:
    """Use the fast model's excerpt if faithful; fall back to the original words."""
    transcript = " ".join(heard.split()).strip(TRIM)
    if not transcript:
        return None
    candidate = " ".join((await _model_excerpt(transcript)).split()).strip(TRIM)
    short_utterance = _fits(transcript)
    uncertain = UNCERTAINTY.search(transcript)
    if not uncertain and _fits(candidate) and (candidate == transcript or len(candidate.split()) >= 3):
        # Whole-word boundaries prevent slicing a quantity, such as “5 kg” from “10,5 kg”.
        excerpt = re.search(r"(?<!\S)" + re.escape(candidate) + r"(?=$|\s|[!?;:]|[.,](?!\d))", transcript, re.I)
        if excerpt:
            quote = excerpt[0]
            if quote == transcript:
                return f"You said: {quote}."
            return f"You said, in particular: {quote}."

    # Preserve all the words for a short request, even if the model added or changed facts.
    if short_utterance:
        return f"You said: {transcript}."
    if uncertain:
        # A bounded excerpt of a long, ambiguous request may drop the actual correction or alternative.
        # Use the fixed waiting phrase instead.
        return None
    words = transcript.split()[:MAX_QUOTE_WORDS]
    while words and not _fits(" ".join(words)):
        words.pop()
    return f"You started with: {' '.join(words).rstrip(TRIM)}…" if words else None
