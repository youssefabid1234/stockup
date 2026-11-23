"""
OWNER: Mohamed Amine · switch TEAM_FILLERS · contract: docs/team/interfaces.md §1

« Jamais de blanc » : the caller must hear something within ~300 ms after releasing Space, even when the agent
needs 3 s of tools. Real life: Lucie says "Je regarde ça…" and you hear her keyboard.

Plan (from GUIDE-VOIX.md §4.7 fillers, §4.9 warm connections, §5 naturalness):
  - a small bank of short French phrases per situation, synthesized ONCE at start-up with the team voice
    (TTS_VOICE) and kept as audio bytes → played instantly, no TTS round-trip
  - a keyboard sound (short mp3 in app/assets/) played while tools run
  - never stack a filler on top of the agent's real answer; never a filler on a turn answered in < 700 ms
    (that would be slower, not faster): decide from the turn type (fast agent answer? tool call coming?)

Hook points already wired in services/voice_session.py (they do nothing while the switch is off):
  - on_turn_start(speaker, heard)  → right after the final transcript, before the agent runs
  - on_tool_call(speaker, name)    → each time the agent calls an ERP tool

TODO(Mohamed Amine):
  1. FillerBank.warm_up(tts) at start-up (voice session open) + Speaker.play_audio(mime, data) in voice_session.py
  2. on_turn_start: play a "thinking" filler unless the turn is trivial; measure perceivedMs on the Voix page
  3. on_tool_call: keyboard sound while stock / price / order tools run
  4. TTS warm connection (GUIDE-VOIX §4.9), sentence cut earlier (§4.8)
  5. STT vocabulary: services/vocabulary.py (jargon: tradi, tourage, chocolatine, gruau… + client contacts)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app import team_flags

if TYPE_CHECKING:  # avoid an import cycle: voice_session imports us
    from app.clients import TTSClient

# Short, natural, never a promise or a number. TODO(Mohamed Amine): tune with the team, record, listen.
PHRASES: dict[str, list[str]] = {
    "thinking": ["Je regarde ça.", "Un instant, je vérifie.", "D'accord, je regarde."],
    "stock": ["Je vérifie le stock.", "Je regarde ce qu'il nous reste."],
    "order": ["Je vous prépare ça.", "C'est noté, je le saisis."],
    "greeting": ["Bonjour, je vous écoute."],
}


@dataclass
class CachedAudio:
    mime: str
    data: bytes


@dataclass
class FillerBank:
    """Audio for every phrase of PHRASES, synthesized once. Empty until warm_up() ran."""

    audio: dict[str, list[CachedAudio]] = field(default_factory=dict)

    async def warm_up(self, tts: TTSClient, voice: str | None = None) -> None:
        """TODO(Mohamed Amine): synthesize every phrase with `tts.synthesize`, join the chunks, store them."""
        raise NotImplementedError

    def pick(self, situation: str) -> CachedAudio | None:
        options = self.audio.get(situation) or []
        return random.choice(options) if options else None


bank = FillerBank()


async def on_turn_start(speaker, heard: str) -> None:
    """Called by voice_session right after the final transcript. No-op while TEAM_FILLERS is off."""
    if not team_flags.fillers():
        return
    # TODO(Mohamed Amine): decide if this turn needs a filler, then e.g.
    #   audio = bank.pick("thinking"); if audio: await speaker.play_audio(audio.mime, audio.data)


async def on_tool_call(speaker, tool_name: str) -> None:
    """Called by voice_session each time the agent calls a tool. No-op while TEAM_FILLERS is off."""
    if not team_flags.fillers():
        return
    # TODO(Mohamed Amine): keyboard sound for ERP lookups (search, get_product_stock, get_price, product_insight…)
