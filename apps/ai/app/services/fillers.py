"""Short acknowledgements and keyboard clicks for ERP lookups (TEAM_FILLERS)."""

from __future__ import annotations

import asyncio
import logging
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
from app.config import settings

from .fast_restatement import fast_restatement

PHRASES = {"thinking": ["Je regarde.", "Je vérifie."], "follow_up": ["Un instant, je vérifie."]}
FAST_INTRO = "Je vais voir."
FAST_INTRO_DELAY = 0.75
FAST_RESTATEMENT_DELAY = 1.05
FAST_AUDIO_TIMEOUT = 2.4
FIRST_KEYBOARD_DELAY = 1.4
FOLLOW_UP_DELAY = 1.8
KEYBOARD_INTERVAL = 2.2
LOOKUP = re.compile(
    r"\b(stock|disponib\w*|combien|prix|tarif|rupture|(?:vous avez|vous reste) (?:du|de|des|encore)|"
    r"je (?:veux|voudrais|commande|prends|souhaite)|(?:ajoutez|rajoutez|mettez)(?:-moi)?|"
    r"ma commande|comme d'habitude)\b", re.I
)
SOCIAL_TURN = re.compile(
    r"(?:[\s.,!?’'\-]*(?:c'est tout|merci(?: beaucoup)?|au revoir|bonne journée|bonjour|salut|oui|non|d'accord))+[\s.,!?]*",
    re.I,
)
SEARCH_TOOLS = {
    "search", "get_product_stock", "get_price", "product_insight", "get_client",
    "find_alternatives", "get_order", "check_delivery_date", "create_draft_order", "add_order_line",
}
QUANTITY = re.compile(
    r"\b((?:\d+(?:[,.]\d+)?|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|vingt)"
    r"\s*(?:kg|g|kilos?|grammes?|cartons?|sacs?|paquets?|litres?|bouteilles?))"
    r"\s+((?:de |d['’])[a-zà-ÿ][a-zà-ÿ0-9'’\-]*(?: +[a-zà-ÿ][a-zà-ÿ0-9'’\-]*){0,4})"
    r"(?=$|[.,!?;:]|\s)", re.I
)
ITEM_END = re.compile(r"\s+(?:pour|et|mais|sans|avec|puis|merci|s['’]il|livrés?|livrée?s?)\b", re.I)
AMBIGUOUS = re.compile(
    r"\b(?:ou|finalement|plutôt|à la place|au lieu|pas|ni|sans|annulez|retirez|enlevez|je me suis tromp[ée])\b",
    re.I,
)
WAITING_LINE = re.compile(
    r"^\s*(?:(?:d['’]accord|un instant|une seconde),?\s+)?"
    r"(?:je (?:vais )?regard(?:e|er)(?: ça| ce qu['’]il nous reste)?|je vérifie(?: le stock)?)"
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
        phrases_by_situation = PHRASES
        if team_flags.fillers_mode() == 2:
            phrases_by_situation = {"fast_intro": [FAST_INTRO], "follow_up": PHRASES["follow_up"]}
        for situation, phrases in phrases_by_situation.items():
            clips = self.audio.setdefault(situation, [])
            for phrase in phrases[len(clips):]:
                clips.append(await synthesize_clip(tts, phrase, voice))

    def pick(self, situation: str) -> CachedAudio | None:
        options = self.audio.get(situation)
        return random.choice(options) if options else None


async def synthesize_clip(tts: TTSClient, phrase: str, voice: str | None) -> CachedAudio:
    result = await tts.synthesize(phrase, voice)
    async with aclosing(result.chunks) as chunks:
        data = b"".join([chunk async for chunk in chunks])
    if not data:
        raise ValueError("Empty waiting audio from TTS")
    return CachedAudio(result.mime, data)


@cache
def keyboard_click() -> bytes:
    """A short burst of three keystrokes with slightly different pitches and intensity."""
    rate = 44100
    noise = random.Random(12)
    pcm = bytearray()
    keys = ((0.0, 920, 4100), (0.09, 780, 3500), (0.205, 1040, 4400))
    for i in range(int(rate * 0.27)):
        sample = 0.0
        for start, pitch, volume in keys:
            t = i / rate - start
            if 0 <= t < 0.065:
                envelope = math.exp(-150 * t)
                if t >= 0.038:
                    envelope += 0.35 * math.exp(-220 * (t - 0.038))
                sample += volume * envelope * (0.65 * noise.uniform(-1, 1) + 0.35 * math.sin(2 * math.pi * pitch * t))
        pcm.extend(struct.pack("<h", int(sample)))
    encoder = Mp3Encoder(rate)
    return encoder.encode(bytes(pcm)) + encoder.flush()


def quantity_restatement(heard: str) -> str | None:
    matches = list(QUANTITY.finditer(heard))
    if len(matches) != 1 or AMBIGUOUS.search(heard):
        return None
    match = matches[0]
    if re.search(r"\bet\b", heard[match.end(1):], re.I):
        return None
    amount, item = match.groups()
    item = ITEM_END.split(item, maxsplit=1)[0]
    if re.fullmatch(r"de|d['’]", item, re.I):
        return None
    amount = re.sub(r"(?<=\d)(?=[a-z])", " ", amount, flags=re.I)
    return f"Pour {amount.lower()} {item.lower()}."


async def keep_waiting(speaker) -> None:
    """Play sparse audio while a lookup is still in progress. The speaker cancels us when the answer is ready."""
    if speaker.quick_transcript is not None:
        await keep_waiting_with_restatement(speaker)
        return
    await asyncio.sleep(FIRST_KEYBOARD_DELAY)
    await speaker.play_audio("audio/mpeg", keyboard_click())
    await asyncio.sleep(FOLLOW_UP_DELAY)
    clip = speaker.bank.pick("follow_up")
    if speaker.restatement:
        try:
            async with asyncio.timeout(1.4):
                clip = await synthesize_clip(speaker.tts, speaker.restatement, settings.tts.voice or None)
        except Exception as exc:
            logging.getLogger(__name__).debug("Voice restatement unavailable (%s)", type(exc).__name__)
    if clip and clip.mime == "audio/mpeg":
        await speaker.play_audio(clip.mime, clip.data)
    for _ in range(2):
        await asyncio.sleep(KEYBOARD_INTERVAL)
        await speaker.play_audio("audio/mpeg", keyboard_click())


async def keep_waiting_with_restatement(speaker) -> None:
    if not speaker.acknowledged:
        await asyncio.sleep(FAST_INTRO_DELAY)
        if not await play_waiting_line(speaker):
            await speaker.play_audio("audio/mpeg", keyboard_click())
            return

    async with asyncio.TaskGroup() as pending:
        preparation = pending.create_task(prepare_fast_clip(speaker))
        if team_flags.fillers_mode() == 3:
            await asyncio.sleep(FIRST_KEYBOARD_DELAY)
            await speaker.play_audio("audio/mpeg", keyboard_click())
        await asyncio.sleep(FAST_RESTATEMENT_DELAY)

    clip = preparation.result()
    if clip and clip.mime == "audio/mpeg":
        await speaker.play_audio(clip.mime, clip.data)
    for _ in range(2):
        await asyncio.sleep(KEYBOARD_INTERVAL)
        await speaker.play_audio("audio/mpeg", keyboard_click())


async def prepare_fast_clip(speaker) -> CachedAudio | None:
    try:
        async with asyncio.timeout(FAST_AUDIO_TIMEOUT):
            phrase = await fast_restatement(speaker.quick_transcript) or speaker.restatement
            if phrase:
                result = await synthesize_clip(speaker.tts, phrase, settings.tts.voice or None)
                if result.mime == "audio/mpeg":
                    return result
    except Exception as exc:
        logging.getLogger(__name__).debug("Fast waiting audio unavailable (%s)", type(exc).__name__)
    return speaker.bank.pick("follow_up")


async def on_turn_start(speaker, heard: str) -> None:
    if not team_flags.fillers():
        return
    words = heard.replace("’", "'")
    speaker.social_turn = bool(SOCIAL_TURN.fullmatch(words))
    if speaker.social_turn or speaker.tts.name == "mock":
        return
    if team_flags.fillers_mode() != 2:
        speaker.restatement = quantity_restatement(words)
    if team_flags.fast_fillers():
        speaker.quick_transcript = words
        if LOOKUP.search(words) or speaker.restatement:
            await play_waiting_line(speaker)
        speaker.start_waiting()
        return
    if (LOOKUP.search(words) or speaker.restatement) and await play_waiting_line(speaker):
        speaker.start_waiting()


async def on_tool_call(speaker, tool_name: str) -> None:
    if not team_flags.fillers() or tool_name not in SEARCH_TOOLS:
        return
    if speaker.social_turn or speaker.tts.name == "mock" or not speaker.first_phrase:
        return
    if speaker.buffer.strip() and not WAITING_LINE.fullmatch(speaker.buffer):
        return
    if speaker.waiting_task is None:
        if not speaker.acknowledged and not await play_waiting_line(speaker):
            await speaker.play_audio("audio/mpeg", keyboard_click())
        speaker.start_waiting()


async def play_waiting_line(speaker) -> bool:
    clip = speaker.bank.pick("fast_intro" if team_flags.fillers_mode() == 2 else "thinking")
    if clip is None or clip.mime != "audio/mpeg":
        return False
    await speaker.play_audio(clip.mime, clip.data)
    speaker.acknowledged = True
    return True
