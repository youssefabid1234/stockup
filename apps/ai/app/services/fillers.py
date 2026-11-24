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

# team 12 (Youssef, natural voice): many short variants, picked without repetition within a call (FillerBank.pick).
# The voice-agent guides all say a filler repeated on every turn is the first thing that sounds robotic.
PHRASES = {
    "thinking": ["Je regarde.", "Voyons ça.", "Une seconde.", "Alors, voyons…", "Je jette un œil.", "Deux secondes.",
                 "Ok, je regarde.", "Je vérifie."],
    "follow_up": ["Un instant, je vérifie.", "Je suis dessus.", "Encore une petite seconde.", "Ça arrive.", "J'y suis presque."],
}
# Mode 4 · « zéro silence » (TEAM_FILLERS=4): the agent opens the call, says one of these at once after each request,
# then types on the keyboard without a gap until the first word of the real answer.
# Default acknowledgement (no clear intent). No « Parfait » / « Ça marche »: they sound like a yes before the answer.
ACK_PHRASES = ["Je regarde ça.", "Une seconde, je vérifie.", "Je vois ça tout de suite.", "Voyons ça."]
# team 12 (Youssef): the first words match what the caller asked (tested 24/11: « Parfait, je vais voir ça » before
# refusing a discount sounded like a yes, and the same phrase came back on every turn). Neutral: never a promise.
ACK_BY_INTENT = {
    "discount": ["J'entends bien.", "Je comprends.", "Je vois."],
    "complaint": ["Ah, je suis désolée.", "Oh, désolée pour ça.", "Je suis navrée, je regarde."],
    "readback": ["Je vous relis ça.", "Je reprends votre commande.", "Alors, votre commande…"],
    "total": ["Je fais le compte.", "Je calcule ça.", "Je regarde le total."],
    "usual": ["Je reprends votre habituel.", "Votre habituel, je regarde.", "Je regarde ce que vous prenez d'habitude."],
    "change": ["Pas de souci, je change ça.", "Je corrige.", "D'accord, je modifie."],
    "price": ["Je regarde votre prix.", "Je vous dis ça.", "Voyons votre tarif."],
    "stock": ["Je regarde le stock.", "Voyons ce qu'il me reste.", "Je regarde ce que j'ai."],
    "order": ["Je note ça.", "Je vous prépare ça.", "Je regarde ça pour vous."],
    "delivery": ["Je regarde vos livraisons.", "Voyons les jours de livraison.", "Je regarde le calendrier."],
}
# Checked in this order (the first match wins): « non, mettez-en 12 » is a change, « 10 % sur l'ensemble » a discount.
INTENT_PATTERNS = [
    ("discount", r"\b(remise|r[ée]duc\w*|geste|ristourne|moins cher|concurren\w*|rabais|faire un prix)\b|\d+\s?%|pour cent"),
    ("complaint", r"\b(manqu\w*|ab[îi]m\w*|cass[ée]\w*|pas re[çc]u|erreur|r[ée]clam\w*|m[ée]content|en retard|pas livr\w*|probl[eè]me)\b"),
    ("readback", r"\b(reli\w*|r[ée]cap\w*|r[ée]p[ée]t\w*|confirme[zr]?-moi|rappelez-moi|relecture|qu'est-ce que j'ai command\w*)\b"),
    ("total", r"\b(en tout|au total|le total|ça fait combien|combien ça fait)\b"),
    ("usual", r"\b(comme d'hab\w*|habituel\w*|la m[êe]me chose|comme la derni[èe]re)"),
    ("change", r"(^|\W)non\s*,|\b(plut[ôo]t|finalement|enl[eè]v\w*|retir\w*|annul\w*|corrig\w*|à la place|au lieu|chang\w*|en fait)\b"),
    ("price", r"\b(combien|prix|tarif\w*|co[ûu]te)\b"),
    ("stock", r"\b(vous avez|vous reste|il vous reste|dispo\w*|en stock|rupture|vous en avez)\b"),
    ("order", r"\b(il me faut|il me faudrait|je voudrais|je veux|mettez|ajoutez|rajoutez|je prends|command\w*)\b|\b\d+\s*(sacs?|cartons?|kilos?|kg|litres?|plateaux?|paquets?|pains?|seaux?)\b"),
    ("delivery", r"\b(livr\w*|quel jour|quand|demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|horaire\w*)\b"),
]
INTENT_RX = [(name, re.compile(rx, re.I)) for name, rx in INTENT_PATTERNS]
JEV_INTENTS = {  # when no keyword matches: Jev chooses (fast, ~150-250 ms)
    "discount": "il demande une remise, un geste ou compare avec un concurrent",
    "complaint": "il se plaint d'un problème (livraison, qualité, erreur)",
    "readback": "il veut qu'on lui relise ou rappelle sa commande",
    "price": "il demande un prix",
    "stock": "il demande si un produit est disponible",
    "order": "il commande ou ajoute un produit",
    "change": "il corrige ou change quelque chose",
    "other": "autre chose (question générale, bavardage)",
}
JEV_TIMEOUT = 0.3
# team 12 (Youssef): said once after a silence in hands-free mode (voice_session.nudge), never twice the same
NUDGES = ["Vous êtes toujours là ?", "Allô, vous m'entendez ?", "Je vous écoute, prenez votre temps.", "Oui, je suis là, je vous écoute."]
OPENING_LINES = {
    None: "Bonjour, que puis-je faire pour vous ?",
    "madame": "Bonjour Madame, que puis-je faire pour vous ?",
    "monsieur": "Bonjour Monsieur, que puis-je faire pour vous ?",
}
TYPING_LEAD = 0.15  # send the next typing clip this long before the queued audio runs out (no stall, no backlog)
TYPING_MAX = 30.0  # never type for longer than this (a turn that hangs)
SOCIAL_TYPING_DELAY = 0.3  # « oui », « merci » : no phrase, typing only if the answer takes a moment
TTS_KBPS = 128  # ElevenLabs mp3_44100_128: duration of a clip ≈ bytes × 8 / 128 000
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
    text: str = ""  # team 12: the phrase, for the log (« [ack] price → Je regarde votre prix. »)


@dataclass
class FillerBank:
    """Each voice connection owns its clips and uses its configured voice."""
    audio: dict[str, list[CachedAudio]] = field(default_factory=dict)

    async def warm_up(self, tts: TTSClient, voice: str | None = None) -> None:
        phrases_by_situation = PHRASES
        if team_flags.no_silence():
            phrases_by_situation = {"ack": ACK_PHRASES, **{f"ack:{k}": v for k, v in ACK_BY_INTENT.items()}}
        elif team_flags.fillers_mode() == 2:
            phrases_by_situation = {"fast_intro": [FAST_INTRO], "follow_up": PHRASES["follow_up"]}
        for situation, phrases in phrases_by_situation.items():
            clips = self.audio.setdefault(situation, [])
            for phrase in phrases[len(clips):]:
                clips.append(await synthesize_clip(tts, phrase, voice))

    def pick(self, situation: str) -> CachedAudio | None:
        """A clip for this situation, never the same one twice in a row and each one used before any repeats
        (a shuffled round per situation): the caller does not hear « Je regarde » on every turn."""
        options = self.audio.get(situation)
        if not options:
            return None
        i = next_index(self.rounds.setdefault(situation, []), len(options), self.last.get(situation))
        self.last[situation] = i
        return options[i]

    rounds: dict[str, list[int]] = field(default_factory=dict)
    last: dict[str, int] = field(default_factory=dict)


def next_index(round_: list[int], n: int, last: int | None) -> int:
    """Next index of a shuffled round over n items; a new round never starts with the previous pick."""
    if not round_:
        round_.extend(random.sample(range(n), n))
        if n > 1 and round_[-1] == last:  # popped from the end: avoid an immediate repeat across rounds
            round_[0], round_[-1] = round_[-1], round_[0]
    return round_.pop()


class PhraseRotation:
    """Text variant of FillerBank.pick (phrases synthesized on demand, e.g. the silence nudge)."""

    def __init__(self, phrases: list[str]):
        self.phrases, self.round, self.last = phrases, [], None

    def next(self) -> str:
        i = next_index(self.round, len(self.phrases), self.last)
        self.last = i
        return self.phrases[i]


async def synthesize_clip(tts: TTSClient, phrase: str, voice: str | None) -> CachedAudio:
    result = await tts.synthesize(phrase, voice)
    async with aclosing(result.chunks) as chunks:
        data = b"".join([chunk async for chunk in chunks])
    if not data:
        raise ValueError("Empty waiting audio from TTS")
    return CachedAudio(result.mime, data, phrase)


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


TYPING_RATE = 44100
TYPING_SECONDS = 0.45  # short clips: when the answer arrives, at most one is still queued ahead of it


@cache
def typing_clip(variant: int) -> tuple[bytes, float]:
    """0.45 s of someone typing (2 to 4 keystrokes at an irregular rhythm, real silence in between), MP3.
    Several variants so the loop does not sound like a loop. Returns (mp3, seconds)."""
    rnd = random.Random(100 + variant)
    noise = random.Random(7 + variant)
    keys, t = [], rnd.uniform(0.0, 0.08)
    while t < TYPING_SECONDS - 0.07:
        keys.append((t, rnd.uniform(700, 1150), rnd.uniform(2400, 4200)))
        t += rnd.uniform(0.11, 0.24)
    pcm = bytearray()
    for i in range(int(TYPING_RATE * TYPING_SECONDS)):
        sample = 0.0
        for start, pitch, volume in keys:
            dt = i / TYPING_RATE - start
            if 0 <= dt < 0.065:
                envelope = math.exp(-150 * dt) + (0.35 * math.exp(-220 * (dt - 0.038)) if dt >= 0.038 else 0)
                sample += volume * envelope * (0.65 * noise.uniform(-1, 1) + 0.35 * math.sin(2 * math.pi * pitch * dt))
        pcm.extend(struct.pack("<h", max(-32768, min(32767, int(sample)))))
    encoder = Mp3Encoder(TYPING_RATE)
    return encoder.encode(bytes(pcm)) + encoder.flush(), TYPING_SECONDS


LOOKUP_MORE = re.compile(
    r"\b(?:faudrait|faut|besoin|livr\w*|commande\w*|habitude|reste|dispo\w*|quand|combien|prix|tarif|"
    r"finalement|plutôt|plutot|enlev\w*|retir\w*|annul\w*|rajout\w*|ajout\w*|change\w*|modifi\w*|"
    r"\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|quinze|vingt|trente|quarante|cinquante|cent)\b",
    re.I,
)


def needs_lookup(words: str) -> bool:
    """Will the agent have to search the ERP (worth « D'accord, je regarde ça »)? Not for a plain confirmation."""
    from app.agent.router import is_simple_turn

    if is_simple_turn(words):
        return False
    return bool(LOOKUP.search(words) or QUANTITY.search(words) or LOOKUP_MORE.search(words))


def mp3_seconds(data: bytes, kbps: int = TTS_KBPS) -> float:
    """Playing time of a constant-bitrate MP3 chunk (enough to pace the audio we queue)."""
    return len(data) * 8 / (kbps * 1000)


async def keep_typing(speaker, delay: float = 0.0) -> None:
    """Mode 4: type without a gap until the speaker cancels us (first sentence of the answer, or barge-in).
    Each clip is sent just before the audio already queued runs out: the caller never hears a stall, and at most one
    short clip is still queued when the answer arrives."""
    if delay:
        await asyncio.sleep(delay)
    loop = asyncio.get_running_loop()
    stop_at = loop.time() + TYPING_MAX
    variant = 0
    while loop.time() < stop_at:
        if (wait := speaker.audio_until - loop.time() - TYPING_LEAD) > 0:
            await asyncio.sleep(wait)
        data, seconds = typing_clip(variant % 6)
        variant += 1
        await speaker.play_audio("audio/mpeg", data, seconds=seconds)


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
    if team_flags.no_silence():
        if speaker.tts.name == "mock" or speaker.waiting_task is not None:  # already typing (early_acknowledgement)
            return
        # The acknowledgement only when the agent really has to look something up (an order, a quantity, a price, a
        # change). « C'est bon, validez », « oui », « merci » get no phrase (it slowed the talk down for nothing): only
        # typing, and only if the answer lags.
        # team 12 (Youssef): the phrase follows the request (keywords, else Jev); a discount or a complaint gets one too
        from app.agent.router import is_simple_turn

        simple = speaker.social_turn or is_simple_turn(words)  # « c'est bon, validez », « merci »: no phrase
        speaker.intent = None if simple else await choose_intent(words)
        if needs_lookup(words) or speaker.intent:
            await play_waiting_line(speaker)
        speaker.waiting_task = asyncio.create_task(keep_typing(speaker, 0.0 if speaker.acknowledged else SOCIAL_TYPING_DELAY))
        return
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


async def early_acknowledgement(speaker, utterance) -> None:
    """
    Mode 4, at the microphone: the final transcript comes 1.2-1.5 s after the caller's last word (Soniox, measured
    24/11), and the acknowledgement used to wait for it: 1.3-1.9 s of silence. Now, from the end of speech, the words
    heard so far are checked every 50 ms; as soon as they show a lookup (« vous avez encore du tourage… »), the
    acknowledgement plays and the typing starts. Stops as soon as the final transcript is there (on_turn_start decides).
    """
    if not (team_flags.fillers() and team_flags.no_silence()) or speaker.tts.name == "mock":
        return
    while not speaker.transcript_ready:
        words = (getattr(utterance, "partial", "") or "").replace("’", "'")
        if words and needs_lookup(words):
            speaker.intent = intent_of(words)  # keywords only here: this path is about speed
            await play_waiting_line(speaker)
            speaker.waiting_task = asyncio.create_task(keep_typing(speaker, 0.0))
            return
        await asyncio.sleep(0.05)


async def on_tool_call(speaker, tool_name: str) -> None:
    if not team_flags.fillers() or tool_name not in SEARCH_TOOLS:
        return
    if team_flags.no_silence():  # already typing since the start of the turn
        return
    if speaker.social_turn or speaker.tts.name == "mock" or not speaker.first_phrase:
        return
    if speaker.buffer.strip() and not WAITING_LINE.fullmatch(speaker.buffer):
        return
    if speaker.waiting_task is None:
        if not speaker.acknowledged and not await play_waiting_line(speaker):
            await speaker.play_audio("audio/mpeg", keyboard_click())
        speaker.start_waiting()


def intent_of(words: str) -> str | None:
    """What kind of request is it (keywords, instant)? None when nothing matches."""
    text = (words or "").replace("’", "'")
    return next((name for name, rx in INTENT_RX if rx.search(text)), None)


async def choose_intent(words: str, use_jev: bool = True) -> str | None:
    """Keywords first; if none match, Jev picks among the intents (capped at JEV_TIMEOUT, never blocks the turn)."""
    found = intent_of(words)
    if found or not use_jev or not words.strip():
        return found
    try:
        from app.clients import get_jev_client

        jev = get_jev_client()
        if jev is None:
            return None
        async with asyncio.timeout(JEV_TIMEOUT):
            c = await jev.choose(words, "Que demande le client au téléphone ?", JEV_INTENTS)
        return c.choice if c.choice in ACK_BY_INTENT and c.confidence >= 0.5 else None
    except Exception:
        return None


async def play_waiting_line(speaker) -> bool:
    situation = "ack" if team_flags.no_silence() else "fast_intro" if team_flags.fillers_mode() == 2 else "thinking"
    intent = getattr(speaker, "intent", None)
    audio = getattr(speaker.bank, "audio", None) or {}
    if situation == "ack" and intent and audio.get(f"ack:{intent}"):
        situation = f"ack:{intent}"
    clip = speaker.bank.pick(situation)
    if getattr(clip, "text", ""):
        print(f"[ack] {intent or 'défaut'} → {clip.text}", flush=True)
    if clip is None or clip.mime != "audio/mpeg":
        return False
    await speaker.play_audio(clip.mime, clip.data)
    speaker.acknowledged = True
    return True
