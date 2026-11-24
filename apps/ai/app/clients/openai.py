"""
OpenAI adapters, raw HTTP:
  - LLM: Chat Completions (POST {base_url}/chat/completions, stream: true). Also every "OpenAI-compatible"
    server: Mistral, Groq, OpenRouter, Ollama, vLLM, LM Studio… (set LLM_BASE_URL).
  - STT: POST /audio/transcriptions (gpt-4o-mini-transcribe, whisper-1…)
  - TTS: POST /audio/speech (gpt-4o-mini-tts, tts-1…), streamed mp3.
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.schemas import ChatMessage, ToolCall

from .base import LLMClient, LLMEvent, LLMRequest, LLMText, LLMToolCall, LLMUsage, STTClient, TTSClient, TTSResult
from .http import body_chunks, check_ok, http_client, parse_args, post_stream, sse_json

OPENAI_URL = "https://api.openai.com/v1"


class OpenAILLM(LLMClient):
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = OPENAI_URL,
        provider: str = "openai",
        include_usage: bool = True,  # stream_options.include_usage: some compatible servers reject unknown fields
        http: httpx.AsyncClient | None = None,
    ):
        self.provider, self.model = provider, model
        self.api_key, self.base_url, self.include_usage = api_key, base_url.rstrip("/"), include_usage
        self.http = http

    def build_body(self, req: LLMRequest) -> dict:
        body: dict = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": req.system}, *map(to_openai_message, req.messages)],
        }
        if req.tools:
            body["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in req.tools
            ]
        if req.max_tokens:
            body["max_tokens"] = req.max_tokens
        if self.include_usage:
            body["stream_options"] = {"include_usage": True}
        return body

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMEvent]:
        headers = {"authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        res = await post_stream(
            self.http or http_client(), f"{self.base_url}/chat/completions", json=self.build_body(req), headers=headers, limit=500
        )

        # Tool calls stream in pieces, keyed by index: accumulate them, emit them at the end.
        pending: dict[int, dict] = {}
        async for chunk in sse_json(res):
            delta = ((chunk.get("choices") or [{}])[0] or {}).get("delta") or {}
            if delta.get("content"):
                yield LLMText(delta["content"])
            for tc in delta.get("tool_calls") or []:
                cur = pending.setdefault(tc.get("index") or 0, {"id": "", "name": "", "args": ""})
                fn = tc.get("function") or {}
                if tc.get("id"):
                    cur["id"] = tc["id"]
                cur["name"] += fn.get("name") or ""
                cur["args"] += fn.get("arguments") or ""
            if chunk.get("usage"):
                yield LLMUsage(chunk["usage"].get("prompt_tokens"), chunk["usage"].get("completion_tokens"))

        for i, tc in sorted(pending.items()):
            yield LLMToolCall(ToolCall(id=tc["id"] or f"call_{i}", name=tc["name"], arguments=parse_args(tc["args"])))


def to_openai_message(m: ChatMessage) -> dict:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content or None,
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": compact_json(c.arguments)}}
                for c in m.tool_calls
            ],
        }
    return {"role": m.role, "content": m.content}


def compact_json(value) -> str:
    """JSON like JavaScript's JSON.stringify: no spaces, accents kept."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class OpenAISTT(STTClient):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-transcribe", language: str = "fr", http: httpx.AsyncClient | None = None):
        self.api_key, self.model, self.language, self.http = api_key, model, language, http

    async def transcribe(self, audio: bytes, mime: str, hint: str | None = None) -> str:
        data = {"model": self.model, "language": self.language}
        if hint:
            data["prompt"] = hint  # vocabulary hint: product / client names
        res = await (self.http or http_client()).post(
            f"{OPENAI_URL}/audio/transcriptions",
            headers={"authorization": f"Bearer {self.api_key}"},
            files={"file": (f"audio.{extension_for(mime)}", audio, mime)},
            data=data,
        )
        await check_ok(res, "openai stt")
        return (res.json().get("text") or "").strip()


class OpenAITTS(TTSClient):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-tts", voice: str = "alloy", http: httpx.AsyncClient | None = None):
        self.api_key, self.model, self.voice, self.http = api_key, model, voice, http

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        res = await post_stream(
            self.http or http_client(),
            f"{OPENAI_URL}/audio/speech",
            who="openai tts",
            headers={"authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "voice": voice or self.voice, "input": text, "response_format": "mp3"},
        )
        return TTSResult("audio/mpeg", body_chunks(res))


def extension_for(mime: str) -> str:
    """File extension the transcription APIs expect for a recording mime type."""
    if "webm" in mime:
        return "webm"
    if "ogg" in mime:
        return "ogg"
    if "mp4" in mime or "m4a" in mime:
        return "m4a"
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    return "wav"
