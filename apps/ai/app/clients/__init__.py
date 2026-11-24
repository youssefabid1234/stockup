"""
Provider clients: LLM, speech-to-text, text-to-speech. Raw HTTP (httpx), no vendor SDKs.

    base.py       the three interfaces (LLMClient, STTClient, TTSClient)
    factory.py    get_llm_client() / get_stt_client() / get_tts_client() from the env
    openai.py     LLM (also any OpenAI-compatible server), STT, TTS
    anthropic.py  LLM          gemini.py     LLM
    jev.py        Jev decision model (TypeSafe AI): choose / score / yes_no, next to the LLM
    deepgram.py   STT (+ live)  soniox.py  STT (+ live)  elevenlabs.py TTS  gradium.py  TTS + STT
    http.py / ws.py  shared HTTP / WebSocket helpers      audio.py  webm→ogg remux, PCM→mp3
    mock_llm.py   offline French fake that calls real tools     mock_speech.py  offline STT / TTS
"""

from .base import LLMClient, LLMEvent, LLMRequest, LLMText, LLMToolCall, LLMUsage, STTClient, STTUpdate, TTSClient, TTSResult
from .factory import ConfigError, get_jev_client, get_llm_client, get_stt_client, get_tts_client
from .jev import JevClient

__all__ = [name for name in dir() if not name.startswith("_")]
