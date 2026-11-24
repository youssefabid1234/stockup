"""
Factories: settings (LLM_*, STT_*, TTS_*, JEV_* env vars) → one client of each kind, built once.

To add a provider: write a class implementing LLMClient / STTClient / TTSClient (see base.py)
in a new file, then add a `case` below.
"""

from functools import cache

from app.config import JevSettings, LLMSettings, STTSettings, TTSSettings, settings

from .anthropic import AnthropicLLM
from .base import LLMClient, STTClient, TTSClient
from .deepgram import DeepgramSTT
from .elevenlabs import ElevenLabsTTS
from .gemini import GeminiLLM
from .gradium import GradiumSTT, GradiumTTS
from .jev import JevClient
from .mock_llm import MockLLM
from .mock_speech import MockSTT, MockTTS
from .openai import OpenAILLM, OpenAISTT, OpenAITTS
from .soniox import SonioxSTT

DEFAULT_MODELS = {"openai": "gpt-4.1-mini", "anthropic": "claude-sonnet-5-5", "gemini": "gemini-2.5-flash"}
# Speech defaults, all fine for French. STT_MODEL / TTS_MODEL / TTS_VOICE override them.
DEFAULT_STT_MODELS = {"openai": "gpt-4o-mini-transcribe", "deepgram": "nova-3", "soniox": "stt-rt-v6", "gradium": "default"}
DEFAULT_TTS = {  # provider → (model, voice)
    "openai": ("gpt-4o-mini-tts", "alloy"),
    "elevenlabs": ("eleven_flash_v2_5", "JBFqnCBsd6RMkjVDRZzb"),  # premade multilingual voice
    "gradium": ("default", "F7Iib4MAyHIRed0x"),  # Armand, flagship fr-FR voice
}


class ConfigError(Exception):
    """A provider is selected but a required setting is missing."""


def need(name: str, value: str) -> str:
    if not value:
        raise ConfigError(f"{name} is required for this provider")
    return value


def make_llm_client(cfg: LLMSettings) -> LLMClient:
    model = cfg.model or DEFAULT_MODELS.get(cfg.provider, "")
    match cfg.provider:
        case "mock":
            return MockLLM()
        case "openai":
            return OpenAILLM(model, need("LLM_API_KEY", cfg.api_key), cfg.base_url or "https://api.openai.com/v1")
        case "openai-compatible":  # Groq, Mistral, OpenRouter, Ollama, vLLM… (API key optional for local servers)
            return OpenAILLM(
                need("LLM_MODEL", model),
                cfg.api_key,
                need("LLM_BASE_URL (e.g. http://localhost:11434/v1)", cfg.base_url),
                provider="openai-compatible",
                include_usage=False,
            )
        case "anthropic":
            return AnthropicLLM(model, need("LLM_API_KEY", cfg.api_key), cfg.base_url or "https://api.anthropic.com", cfg.effort)
        case "gemini":
            return GeminiLLM(model, need("LLM_API_KEY", cfg.api_key), cfg.base_url or "https://generativelanguage.googleapis.com/v1beta")
    raise ConfigError(f'Unknown LLM_PROVIDER "{cfg.provider}" (openai | openai-compatible | anthropic | gemini | mock)')


def make_stt_client(cfg: STTSettings) -> STTClient:
    model, lang = cfg.model or DEFAULT_STT_MODELS.get(cfg.provider, ""), cfg.language
    match cfg.provider:
        case "mock":
            return MockSTT(cfg.mock_text)
        case "openai":
            return OpenAISTT(need("STT_API_KEY", cfg.api_key), model, lang)
        case "deepgram":
            return DeepgramSTT(need("STT_API_KEY", cfg.api_key), model, lang)
        case "soniox":
            return SonioxSTT(need("STT_API_KEY", cfg.api_key), model, lang)
        case "gradium":
            return GradiumSTT(need("STT_API_KEY", cfg.api_key), model, lang)
    raise ConfigError(f'Unknown STT_PROVIDER "{cfg.provider}" (deepgram | soniox | gradium | openai | mock)')


def make_tts_client(cfg: TTSSettings) -> TTSClient:
    model, voice = DEFAULT_TTS.get(cfg.provider, ("", ""))
    model, voice = cfg.model or model, cfg.voice or voice
    match cfg.provider:
        case "mock":
            return MockTTS()
        case "openai":
            return OpenAITTS(need("TTS_API_KEY", cfg.api_key), model, voice)
        case "elevenlabs":
            return ElevenLabsTTS(need("TTS_API_KEY", cfg.api_key), model, voice, cfg.language)
        case "gradium":
            return GradiumTTS(need("TTS_API_KEY", cfg.api_key), model, voice)
    raise ConfigError(f'Unknown TTS_PROVIDER "{cfg.provider}" (elevenlabs | gradium | openai | mock)')


def make_jev_client(cfg: JevSettings) -> JevClient | None:
    """Jev is optional: no JEV_API_KEY → None (agent code checks `if jev:`)."""
    return JevClient(cfg.api_key, cfg.model, cfg.base_url) if cfg.api_key else None


# The clients the service uses, built once from the environment.
@cache
def get_llm_client() -> LLMClient:
    return make_llm_client(settings.llm)


@cache
def get_stt_client() -> STTClient:
    return make_stt_client(settings.stt)


@cache
def get_tts_client() -> TTSClient:
    return make_tts_client(settings.tts)


@cache
def get_jev_client() -> JevClient | None:
    """The Jev decision model (clients/jev.py), or None when JEV_API_KEY is not set."""
    return make_jev_client(settings.jev)
