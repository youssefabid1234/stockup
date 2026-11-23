"""Short acknowledgements and keyboard clicks for ERP lookups (TEAM_FILLERS)."""

from __future__ import annotations

import math
import random
import re
import struct
from contextlib import aclosing
from dataclasses import dataclass, field
from functools import cache

from app import team_flags
from app.clients import TTSClient
from app.clients.audio import Mp3Encoder

PHRASES = {"thinking": ["Je regarde.", "Je vérifie."]}
LOOKUP = re.compile(
    r"\b(stock|disponib\w*|combien|prix|tarif|rupture|(?:vous avez|vous reste) (?:du|de|des|encore)|"
    r"(?:je voudrais|je commande) (?:\d+|un|une|du|des|de|dix)|ma commande|comme d'habitude)\b", re.I
)
SOCIAL_TURN = re.compile(
    r"(?:[\s.,!?’'\-]*(?:c'est tout|merci(?: beaucoup)?|au revoir|bonne journée|bonjour|salut|oui|non|d'accord))+[\s.,!?]*",
    re.I,
)
SEARCH_TOOLS = {"search", "get_product_stock", "get_price", "product_insight", "get_client"}
WAITING_LINE = re.compile(
    r"^\s*(?:(?:d['’]accord|un instant),?\s+)?"
    r"(?:je regarde(?: ça| ce qu['’]il nous reste)?|je vérifie(?: le stock)?)"
    r"(?:\s*[.!…,]+\s*|\s*$)",
    re.I,
)


@dataclass
class CachedAudio:
    mime: str
    data: bytes


@dataclass
class FillerBank:
    """Each voice connection owns its clips and uses its configured voice."""
    audio: dict[str, list[CachedAudio]] = field(default_factory=dict)

    async def warm_up(self, tts: TTSClient, voice: str | None = None) -> None:
        for situation, phrases in PHRASES.items():
            clips = self.audio.setdefault(situation, [])
            for phrase in phrases[len(clips):]:
                result = await tts.synthesize(phrase, voice)
                async with aclosing(result.chunks) as chunks:
                    data = b"".join([chunk async for chunk in chunks])
                if not data:
                    raise ValueError("Empty waiting audio from TTS")
                clips.append(CachedAudio(result.mime, data))

    def pick(self, situation: str) -> CachedAudio | None:
        options = self.audio.get(situation)
        return random.choice(options) if options else None


@cache
def keyboard_click() -> bytes:
    """One quiet keystroke with two short decaying impacts, generated in memory."""
    rate = 44100
    noise = random.Random(12)
    pcm = bytearray()
    for i in range(rate // 12):
        t = i / rate
        envelope = math.exp(-180 * t)
        if t >= 0.04:
            envelope += 0.5 * math.exp(-220 * (t - 0.04))
        sample = int(2600 * envelope * (0.6 * noise.uniform(-1, 1) + 0.4 * math.sin(2 * math.pi * 900 * t)))
        pcm.extend(struct.pack("<h", sample))
    encoder = Mp3Encoder(rate)
    return encoder.encode(bytes(pcm)) + encoder.flush()


async def on_turn_start(speaker, heard: str) -> None:
    if not team_flags.fillers():
        return
    words = heard.replace("’", "'")
    speaker.social_turn = bool(SOCIAL_TURN.fullmatch(words))
    if speaker.social_turn or team_flags.orchestrator() or not LOOKUP.search(words):
        return
    await play_waiting_line(speaker)


async def on_tool_call(speaker, tool_name: str) -> None:
    if not team_flags.fillers() or tool_name not in SEARCH_TOOLS:
        return
    if speaker.social_turn or speaker.tts.name == "mock" or speaker.has_text or speaker.clicked:
        return
    # A confirmed lookup can catch requests missed by the transcript heuristic.
    # Keep one sound at this point, so a short tool round trip adds no extra clip.
    if not speaker.acknowledged and not team_flags.orchestrator() and await play_waiting_line(speaker):
        return
    await speaker.play_audio("audio/mpeg", keyboard_click())
    speaker.clicked = True


async def play_waiting_line(speaker) -> bool:
    clip = speaker.bank.pick("thinking")
    if clip is None or clip.mime != "audio/mpeg":
        return False
    await speaker.play_audio(clip.mime, clip.data)
    speaker.acknowledged = True
    return True
