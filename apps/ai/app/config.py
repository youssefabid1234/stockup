"""
Configuration, read once from the environment at import time.

The repo-root `.env` (see `.env.example`) is loaded if present; real environment variables win.
Every setting has a default, so with no `.env` at all the service runs on the mock providers.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# apps/ai/app/config.py → the repo root is three folders up.
REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(REPO_ROOT / ".env", override=False)  # never overrides variables already set


def env(name: str, default: str = "") -> str:
    """An environment variable, trimmed; empty counts as unset."""
    return os.environ.get(name, "").strip() or default


@dataclass(frozen=True)
class LLMSettings:
    provider: str  # openai | openai-compatible | anthropic | gemini | mock
    model: str  # empty → the provider's default model
    api_key: str
    base_url: str  # empty → the provider's public endpoint
    effort: str  # anthropic only: low | medium | high


@dataclass(frozen=True)
class STTSettings:
    provider: str  # openai | deepgram | soniox | gradium | mock
    api_key: str
    model: str  # empty → the provider's default model (see clients/factory.py)
    language: str  # ISO code of what the caller speaks
    mock_text: str  # what the mock STT "hears"


@dataclass(frozen=True)
class TTSSettings:
    provider: str  # openai | elevenlabs | gradium | mock
    api_key: str
    model: str  # empty → the provider's default model
    voice: str  # empty → the provider's default (French) voice
    language: str  # elevenlabs language_code; Gradium / OpenAI follow the voice and the text


@dataclass(frozen=True)
class JevSettings:
    api_key: str  # empty → no Jev client (get_jev_client() returns None)
    base_url: str
    model: str


@dataclass(frozen=True)
class Settings:
    port: int
    erp_api_url: str
    data_dir: Path  # data pack (separate repo); relative paths are resolved from the repo root
    max_steps: int  # max model ↔ tools round-trips per turn
    llm: LLMSettings
    stt: STTSettings
    tts: TTSSettings
    jev: JevSettings  # optional decision model, used next to the LLM (clients/jev.py)


settings = Settings(
    port=int(env("AI_PORT", "4100")),
    erp_api_url=env("ERP_API_URL", "http://localhost:4000").rstrip("/"),
    data_dir=(REPO_ROOT / env("DATA_DIR", "../hackathon-data")).resolve(),
    max_steps=int(env("AGENT_MAX_STEPS", "8")),
    llm=LLMSettings(
        provider=env("LLM_PROVIDER", "mock").lower(),
        model=env("LLM_MODEL"),
        api_key=env("LLM_API_KEY"),
        base_url=env("LLM_BASE_URL"),
        effort=env("LLM_EFFORT", "low"),
    ),
    stt=STTSettings(
        provider=env("STT_PROVIDER", "mock").lower(),
        api_key=env("STT_API_KEY"),
        model=env("STT_MODEL"),
        language=env("STT_LANGUAGE", "fr"),
        mock_text=env("MOCK_STT_TEXT", "Bonjour, il vous reste du bar ?"),
    ),
    tts=TTSSettings(
        provider=env("TTS_PROVIDER", "mock").lower(),
        api_key=env("TTS_API_KEY"),
        model=env("TTS_MODEL"),
        voice=env("TTS_VOICE"),
        language=env("TTS_LANGUAGE", "fr"),
    ),
    jev=JevSettings(
        api_key=env("JEV_API_KEY"),
        base_url=env("JEV_BASE_URL", "https://api.typesafe.ai").rstrip("/"),
        model=env("JEV_MODEL", "jev-latest"),
    ),
)
