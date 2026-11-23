"""
Live transcription: Soniox streaming against a fake Soniox server (a real local WebSocket server that speaks the
documented protocol), the Utterance fallbacks, the partial transcripts on WS /voice and WS /voice/command, and
the company vocabulary.
"""

import asyncio
import json
from contextlib import suppress

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from app.clients.base import STTClient, STTUpdate
from app.clients.http import ProviderError
from app.clients.mock_speech import MockSTT, MockTTS
from app.clients.soniox import SonioxSTT
from app.clients.ws import open_ws
from app.routers import voice as voice_router
from app.services import command, utterance, vocabulary, voice_session
from app.services.utterance import Utterance
from app.tools.erp import ErpClient

WORDS = ["Il", " vous", " reste", " du", " bar", " ?"]

# ── fake Soniox server ──


class FakeSoniox:
    """Speaks Soniox's real-time protocol on ws://127.0.0.1:<port>.

    Every audio frame makes one more word heard: earlier words final (sent once), the newest one provisional
    (resent whole). {"type": "finalize"} → the remaining provisional word final, then <fin>.
    `mode`: "ok" | "error" (error message after the first frame) | "hangup" (closes after the first frame)
          | "silent" (never answers a finalize)."""

    def __init__(self, mode: str = "ok"):
        self.mode, self.start, self.frames, self.closed = mode, None, [], asyncio.Event()
        self.url = ""

    async def handler(self, ws):
        self.start = json.loads(await ws.recv())
        final_sent = 0  # words already sent as final
        with suppress(ConnectionClosed):
            try:
                async for msg in ws:
                    if isinstance(msg, bytes):
                        self.frames.append(msg)
                        if self.mode == "error":
                            await ws.send(json.dumps({"error_code": 400, "error_type": "bad_audio", "error_message": "Unknown format."}))
                            await ws.close()
                            return
                        if self.mode == "hangup":
                            await ws.close(1011, "internal error")
                            return
                        heard = min(len(self.frames), len(WORDS))
                        finals = [{"text": w, "is_final": True} for w in WORDS[final_sent : heard - 1]]
                        final_sent = max(final_sent, heard - 1)
                        await ws.send(json.dumps({"tokens": [*finals, {"text": WORDS[heard - 1], "is_final": False}]}))
                    elif json.loads(msg).get("type") == "finalize" and self.mode != "silent":
                        rest = [{"text": w, "is_final": True} for w in WORDS[final_sent : min(len(self.frames), len(WORDS))]]
                        await ws.send(json.dumps({"tokens": [*rest, {"text": "<fin>", "is_final": True}]}))
            finally:
                self.closed.set()

    def stt(self) -> SonioxSTT:
        return SonioxSTT("sx", connect=lambda _url, headers, who: open_ws(self.url, headers, who))


@pytest.fixture
async def soniox():
    servers = []

    async def make(mode: str = "ok") -> FakeSoniox:
        fake = FakeSoniox(mode)
        server = await serve(fake.handler, "127.0.0.1", 0)
        servers.append(server)
        fake.url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        return fake

    yield make
    for s in servers:
        s.close()
        await s.wait_closed()


async def live(queue: asyncio.Queue):
    """Audio as the browser sends it: frames until None."""
    while (frame := await queue.get()) is not None:
        yield frame


# ── Soniox streaming ──


async def test_soniox_partials_arrive_while_streaming_then_finalize(soniox):
    fake = await soniox()
    queue: asyncio.Queue = asyncio.Queue()
    updates = []
    stream = fake.stt().transcribe_stream(live(queue), "audio/webm", hint="Lemoine, bar de ligne")
    for i in range(3):  # three frames, each answered BEFORE the end of the audio
        await queue.put(b"webm%d" % i)
        updates.append(await anext(stream))
    assert [u.text for u in updates] == ["Il", "Il vous", "Il vous reste"]
    assert [u.stable for u in updates] == ["", "Il", "Il vous"] and not any(u.final for u in updates)

    await queue.put(None)  # key released → finalize → <fin>
    last = await anext(stream)
    assert last == STTUpdate("Il vous reste", final=True, stable="Il vous reste")
    await stream.aclose()
    await asyncio.wait_for(fake.closed.wait(), 2)  # socket closed once the final words are in
    assert fake.start == {
        "model": "stt-rt-v6", "audio_format": "auto", "language_hints": ["fr"], "enable_endpoint_detection": True,
        "context": {"terms": ["Lemoine", "bar de ligne"]},
    }  # fmt: skip
    assert fake.frames == [b"webm0", b"webm1", b"webm2"]


async def test_soniox_whole_recording_uses_the_same_path(soniox):
    fake = await soniox()
    assert await fake.stt().transcribe(b"x" * 10, "audio/webm") == "Il"  # one chunk = one word in the fake


async def test_soniox_error_message_is_a_provider_error(soniox):
    fake = await soniox("error")
    with pytest.raises(ProviderError, match="soniox stt HTTP 400"):
        await fake.stt().transcribe(b"x", "audio/webm")


async def test_soniox_hangup_is_a_provider_error(soniox):
    fake = await soniox("hangup")
    with pytest.raises(ProviderError, match="soniox stt"):
        await fake.stt().transcribe(b"x", "audio/webm")


async def test_cancel_closes_the_provider_stream(soniox):
    fake = await soniox()
    queue: asyncio.Queue = asyncio.Queue()

    async def consume():
        async for _ in fake.stt().transcribe_stream(live(queue), "audio/webm"):
            pass

    task = asyncio.create_task(consume())
    await queue.put(b"a")
    await asyncio.sleep(0.1)
    task.cancel()  # barge-in
    with suppress(asyncio.CancelledError):
        await task
    await asyncio.wait_for(fake.closed.wait(), 2)


async def test_a_failing_audio_source_surfaces_as_itself(soniox):
    fake = await soniox()

    async def dropped():
        yield b"a"
        raise OSError("browser gone")

    with pytest.raises(OSError, match="browser gone"):
        async with asyncio.timeout(2):
            async for _ in fake.stt().transcribe_stream(dropped(), "audio/webm"):
                pass


# ── Utterance ──


async def no_partial(_u):
    pass


async def test_utterance_streams_and_finalizes(soniox):
    fake = await soniox()
    partials = []

    async def on_partial(u):
        partials.append(u.text)

    u = Utterance(fake.stt(), "audio/webm", None, on_partial)
    for f in (b"a", b"b"):
        u.feed(f)
    await asyncio.sleep(0.2)
    assert partials == ["Il", "Il vous"]  # shown while the key is still down
    assert await u.text() == "Il vous"


class Recorder(STTClient):
    """Streams nothing useful (fails or hangs) and records the whole-recording fallback."""

    name, streams = "rec", True

    def __init__(self, live_mode: str):
        self.live_mode, self.batch = live_mode, []

    async def transcribe(self, audio, mime, hint=None):
        self.batch.append(audio)
        return "texte complet"

    async def transcribe_stream(self, audio, mime, hint=None):
        async for _ in audio:
            if self.live_mode == "fail":
                raise ProviderError("network down")
        await asyncio.sleep(60)  # "hang": no final words
        yield STTUpdate("jamais")


@pytest.fixture(autouse=True)
def no_erp_vocabulary(monkeypatch):
    async def none():
        return []

    monkeypatch.setattr(vocabulary, "company_terms", none)


async def test_utterance_falls_back_to_the_whole_recording_when_live_breaks():
    stt = Recorder("fail")
    u = Utterance(stt, "audio/webm", None, no_partial)
    u.feed(b"ab")
    u.feed(b"cd")
    assert await u.text() == "texte complet" and stt.batch == [b"abcd"]


async def test_utterance_falls_back_when_the_final_words_never_come(monkeypatch):
    monkeypatch.setattr(utterance, "FINAL_TIMEOUT_S", 0.1)
    stt = Recorder("hang")
    u = Utterance(stt, "audio/webm", None, no_partial)
    u.feed(b"ab")
    assert await u.text() == "texte complet" and u.live.cancelled()


async def test_utterance_without_streaming_transcribes_at_the_end():
    class Batch(Recorder):
        streams = False

    stt = Batch("fail")
    u = Utterance(stt, "audio/webm", None, no_partial)
    u.feed(b"ab")
    assert u.live is None and await u.text() == "texte complet"


# ── WS /voice and WS /voice/command with the mock STT (partials offline) ──


class FakeLLM:
    provider, model = "mock", "mock"


async def say_ok(messages, **kwargs):
    from app.schemas import ChatMessage, DoneEvent, TextEvent

    yield TextEvent(delta="C'est noté.")
    yield DoneEvent(message=ChatMessage(role="assistant", content="C'est noté."), ms=1)


@pytest.fixture
def app(monkeypatch):
    for mod in (voice_session, command):
        monkeypatch.setattr(mod, "get_stt_client", lambda: MockSTT("un deux trois quatre", chunks_per_word=1))
        monkeypatch.setattr(mod, "get_tts_client", lambda: MockTTS())
        monkeypatch.setattr(mod, "get_llm_client", lambda: FakeLLM())
        monkeypatch.setattr(mod, "run_agent", say_ok)
    app = FastAPI()
    app.include_router(voice_router.router)
    return TestClient(app)


def receive_until(ws, kind):
    out = []
    while True:
        frame = ws.receive()
        if frame.get("text") is None:
            continue  # agent audio
        m = json.loads(frame["text"])
        out.append(m)
        if m["type"] in (kind, "error"):
            return out


def test_voice_ws_sends_partials_then_the_final_transcript(app):
    with app.websocket_connect("/voice") as ws:
        ws.send_json({"type": "start"})
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "audio_start", "mime": "audio/webm"})
        partials = []
        for i in range(2):
            ws.send_bytes(b"frame%d" % i)
            partials.append(ws.receive_json())  # arrives before audio_end
        assert partials == [
            {"type": "transcript", "track": "caller", "text": "un", "final": False, "stable": ""},
            {"type": "transcript", "track": "caller", "text": "un deux", "final": False, "stable": "un"},
        ]
        ws.send_json({"type": "audio_end"})
        msgs = receive_until(ws, "agent_done")
        assert msgs[0] == {"type": "transcript", "track": "caller", "text": "un deux trois quatre", "final": True}
        assert msgs[-1]["timings"]["sttMs"] < 500


def test_command_ws_streams_partials_then_the_command_events(app):
    with app.websocket_connect("/voice/command") as ws:
        ws.send_json({"type": "audio_start", "mime": "audio/webm"})
        ws.send_bytes(b"frame")
        assert ws.receive_json() == {"type": "transcript", "text": "un", "ms": 0, "final": False, "stable": ""}
        ws.send_json({"type": "audio_end"})
        msgs = receive_until(ws, "done")
        assert [m["type"] for m in msgs] == ["transcript", "text", "done"]
        assert msgs[0]["text"] == "un deux trois quatre" and msgs[0]["final"] is True


# ── vocabulary ──


async def test_company_terms_from_the_erp(monkeypatch):
    monkeypatch.undo()  # the real company_terms
    vocabulary.reset_cache()
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.url.path, req.url.params.get("limit")))
        if req.url.path == "/api/products":
            return httpx.Response(200, json=[{"name": "Bar de ligne 1-2 kg", "aliases": ["loup", "Bar"]}, {"name": "Turbot, sauvage"}])
        return httpx.Response(200, json=[{"name": "Lemoine"}, {"name": "LOUP"}])

    erp = ErpClient("voice_agent", base_url="http://erp", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await vocabulary.company_terms(erp) == ["Lemoine", "LOUP", "Bar de ligne 1-2 kg", "Turbot sauvage", "Bar"]
    assert sorted(seen) == [("/api/clients", "500"), ("/api/products", "500")]
    vocabulary.reset_cache()


async def test_stt_hint_merges_the_callers_hint_but_not_for_the_mock(monkeypatch):
    async def terms():
        return ["Lemoine", "loup"]

    monkeypatch.setattr(vocabulary, "company_terms", terms)
    assert await vocabulary.stt_hint("soniox", "cèpes") == "cèpes, Lemoine, loup"
    assert await vocabulary.stt_hint("mock", "il vous reste des cèpes ?") == "il vous reste des cèpes ?"
