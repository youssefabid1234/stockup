"""
Deepgram STT.
  transcribe()         pre-recorded: POST /v1/listen with the raw audio body (WebM/Opus, mp4, wav… detected from the bytes).
  transcribe_stream()  live: wss://api.deepgram.com/v1/listen, binary audio frames, {"type": "CloseStream"} to finish;
                       containerised audio (WebM/Opus from MediaRecorder) needs no `encoding` / `sample_rate`.
Model nova-3 + language=fr (monolingual French); keyterm prompting boosts client / product names.
"""

import json
from collections.abc import AsyncIterator, Callable
from urllib.parse import urlencode

import httpx

from .base import STTClient, STTUpdate
from .http import check_ok, http_client, provider_error
from .ws import open_ws, sending


class DeepgramSTT(STTClient):
    name = "deepgram"
    streams = True

    def __init__(
        self, api_key: str, model: str = "nova-3", language: str = "fr", http: httpx.AsyncClient | None = None, connect: Callable = open_ws
    ):
        self.api_key, self.model, self.language, self.http, self.connect = api_key, model, language, http, connect

    def build_params(self, hint: str | None) -> list[tuple[str, str]]:
        params = [("model", self.model), ("language", self.language), ("smart_format", "true")]
        # Keyterm prompting (nova-3 / flux): boost names the model would otherwise mishear. Max 500 tokens in all.
        terms = [t.strip() for t in (hint or "").split(",") if t.strip()]
        params += [("keyterm", t) for t in terms[:50]]
        return params

    async def transcribe(self, audio: bytes, mime: str, hint: str | None = None) -> str:
        res = await (self.http or http_client()).post(
            "https://api.deepgram.com/v1/listen",
            params=self.build_params(hint),
            headers={"authorization": f"Token {self.api_key}", "content-type": mime},
            content=audio,
        )
        await check_ok(res, "deepgram stt")
        alternatives = ((res.json().get("results") or {}).get("channels") or [{}])[0].get("alternatives") or [{}]
        return (alternatives[0].get("transcript") or "").strip()

    def live_url(self, hint: str | None) -> str:
        return "wss://api.deepgram.com/v1/listen?" + urlencode([*self.build_params(hint), ("interim_results", "true")])

    async def transcribe_stream(self, audio: AsyncIterator[bytes], mime: str, hint: str | None = None) -> AsyncIterator[STTUpdate]:
        async with self.connect(self.live_url(hint), {"Authorization": f"Token {self.api_key}"}, "deepgram stt") as ws:
            async with sending(ws, audio, end=json.dumps({"type": "CloseStream"})):
                final = ""  # is_final segments, in order; an interim result replaces the current segment
                async for raw in ws:
                    msg = json.loads(raw)
                    kind = msg.get("type")
                    if kind == "Error":
                        raise provider_error("deepgram stt", msg.get("variant") or "error", msg.get("description") or raw)
                    if kind != "Results":
                        continue  # Metadata (sent last, before close), SpeechStarted, UtteranceEnd
                    text = ((msg.get("channel") or {}).get("alternatives") or [{}])[0].get("transcript") or ""
                    if msg.get("is_final"):
                        final = f"{final} {text}".strip()
                        yield STTUpdate(final, stable=final)
                    else:
                        yield STTUpdate(f"{final} {text}".strip(), stable=final)
            yield STTUpdate(final, final=True, stable=final)  # the server closes the socket once everything is transcribed
