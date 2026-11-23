"""
Soniox / Gradium / Deepgram live adapters + the audio helpers, tested offline on hand-written samples that follow
the providers' documented formats. WebSocket APIs are played by FakeWS; HTTP ones by httpx.MockTransport.
"""

import asyncio
import base64
import json
import math
import struct
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.clients.audio import AudioFormatError, Mp3Encoder, ogg_crc, opus_samples, webm_opus_packets, webm_to_ogg
from app.clients.base import STTClient, STTUpdate
from app.clients.deepgram import DeepgramSTT
from app.clients.factory import ConfigError, make_stt_client, make_tts_client
from app.clients.gradium import GradiumSTT, GradiumTTS
from app.clients.http import ProviderError
from app.clients.soniox import FINALIZE, SonioxSTT
from app.clients.ws import once
from app.config import STTSettings, TTSSettings

# ── fakes ──


def recorder(response_for):
    """MockTransport that records requests and answers with response_for(request)."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response_for(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


class FakeWS:
    """Plays a WebSocket server: records what we send, answers with `replies` once the end-of-audio message arrived."""

    def __init__(self, replies: list[dict], end):
        self.replies, self.end, self.sent = [json.dumps(r) for r in replies], end, []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        while self.end not in self.sent:  # the server answers once the audio is complete (like a short utterance)
            await asyncio.sleep(0)
        for r in self.replies:
            yield r


def fake_connect(ws: FakeWS, seen: dict):
    @asynccontextmanager
    async def connect(url, headers, who):
        seen.update(url=url, headers=headers, who=who)
        try:
            yield ws
        finally:
            ws.closed = True

    return connect


def ebml(eid: int, payload: bytes, unknown: bool = False) -> bytes:
    """One EBML element: id + 8-byte size (or "unknown", like MediaRecorder's live Segment / Cluster) + payload."""
    size = b"\x01\xff\xff\xff\xff\xff\xff\xff" if unknown else b"\x01" + len(payload).to_bytes(7, "big")
    return eid.to_bytes((eid.bit_length() + 7) // 8, "big") + size + payload


OPUS_HEAD = b"OpusHead" + bytes([1, 1]) + struct.pack("<HIhB", 312, 48000, 0, 0)
PKT_20MS = b"\xfc" + b"a" * 20  # TOC config 31 (CELT 20 ms), code 0 → 1 frame = 960 samples
PKT_3X20MS = b"\xfb\x03" + b"b" * 30  # code 3, 3 frames → 2880 samples


def webm_sample(codec: bytes = b"A_OPUS") -> bytes:
    """A MediaRecorder-shaped WebM: EBML header, live Segment, Tracks (Opus), live Cluster with two SimpleBlocks."""
    header = ebml(0x1A45DFA3, ebml(0x4282, b"webm"))
    track = ebml(0xAE, ebml(0xD7, b"\x01") + ebml(0x86, codec) + ebml(0x63A2, OPUS_HEAD))
    blocks = b"".join(ebml(0xA3, b"\x81" + b"\x00\x00" + b"\x80" + p) for p in (PKT_20MS, PKT_3X20MS))
    cluster = ebml(0x1F43B675, ebml(0xE7, b"\x00") + blocks, unknown=True)
    return header + ebml(0x18538067, ebml(0x1654AE6B, track) + cluster, unknown=True)


def ogg_pages(data: bytes) -> list[tuple[int, int, bytes]]:
    """(flags, granule, packet) per page, checking capture pattern and CRC."""
    pages, pos = [], 0
    while pos < len(data):
        assert data[pos : pos + 4] == b"OggS"
        flags, granule, nseg = data[pos + 5], struct.unpack_from("<q", data, pos + 6)[0], data[pos + 26]
        lacing = data[pos + 27 : pos + 27 + nseg]
        end = pos + 27 + nseg + sum(lacing)
        page = data[pos:end]
        assert struct.unpack_from("<I", page, 22)[0] == ogg_crc(page[:22] + b"\0\0\0\0" + page[26:])
        pages.append((flags, granule, page[27 + nseg :]))
        pos = end
    return pages


# ── audio helpers ──


def test_webm_to_ogg_copies_opus_packets():
    head, packets = webm_opus_packets(webm_sample())
    assert head == OPUS_HEAD and packets == [PKT_20MS, PKT_3X20MS]
    assert opus_samples(PKT_20MS) == 960 and opus_samples(PKT_3X20MS) == 2880

    pages = ogg_pages(webm_to_ogg(webm_sample()))
    assert [p[0] for p in pages] == [0x02, 0, 0, 0x04]  # BOS, tags, audio, EOS
    assert pages[0][2] == OPUS_HEAD and pages[1][2].startswith(b"OpusTags")
    assert [p[1] for p in pages[2:]] == [960, 960 + 2880]
    assert [p[2] for p in pages[2:]] == [PKT_20MS, PKT_3X20MS]


def test_webm_to_ogg_rejects_other_codecs():
    with pytest.raises(AudioFormatError):
        webm_to_ogg(webm_sample(codec=b"A_VORBIS"))
    with pytest.raises(AudioFormatError):
        webm_to_ogg(b"\x00\x00not webm")


def test_mp3_encoder_handles_odd_chunks():
    pcm = b"".join(struct.pack("<h", int(8000 * math.sin(i / 48000 * 2 * math.pi * 440))) for i in range(9600))
    enc = Mp3Encoder(48000)
    out = enc.encode(pcm[:1001]) + enc.encode(pcm[1001:]) + enc.flush()  # 1001: cut in the middle of a sample
    assert out[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2")  # an MPEG audio frame sync, no ID3 tag
    assert len(out) > 500


# ── Soniox ──


async def test_soniox_start_request_tokens_and_end_frame():
    ws = FakeWS(
        [
            {"tokens": [{"text": "Il", "is_final": True}, {"text": " vous", "is_final": False}], "final_audio_proc_ms": 300},
            {"tokens": [{"text": " vous reste", "is_final": True}, {"text": " du", "is_final": False}]},
            {"tokens": [{"text": " du bar ?", "is_final": True}, {"text": "<fin>", "is_final": True}]},
        ],
        end=FINALIZE,
    )
    seen: dict = {}
    stt = SonioxSTT("sx", connect=fake_connect(ws, seen))
    text = await stt.transcribe(b"WEBM" * 10, "audio/webm;codecs=opus", hint="Lemoine, bar de ligne ,")
    assert text == "Il vous reste du bar ?"
    assert seen["url"] == "wss://stt-rt.soniox.com/transcribe-websocket" and seen["headers"] == {"Authorization": "Bearer sx"}
    assert json.loads(ws.sent[0]) == {
        "model": "stt-rt-v6", "audio_format": "auto", "language_hints": ["fr"], "enable_endpoint_detection": True,
        "context": {"terms": ["Lemoine", "bar de ligne"]},
    }  # fmt: skip
    assert ws.sent[1:] == [b"WEBM" * 10, FINALIZE] and ws.closed  # audio as binary frames, then finalize


async def test_soniox_stream_partials_then_final():
    ws = FakeWS(
        [
            {"tokens": [{"text": "Bon", "is_final": False}]},
            {"tokens": [{"text": "Bonjour", "is_final": True}, {"text": "<end>", "is_final": True}, {"text": " il", "is_final": False}]},
            {"tokens": [{"text": " il", "is_final": True}, {"text": "<fin>", "is_final": True}]},
        ],
        end=FINALIZE,
    )
    stt = SonioxSTT("sx", connect=fake_connect(ws, {}))
    updates = [u async for u in stt.transcribe_stream(once(b"a", b"b"), "audio/webm")]
    assert updates == [
        STTUpdate("Bon"),
        STTUpdate("Bonjour il", stable="Bonjour"),  # <end> is a pause marker, not text
        STTUpdate("Bonjour il", final=True, stable="Bonjour il"),
    ]
    assert ws.sent[1:] == [b"a", b"b", FINALIZE]


async def test_soniox_error_response():
    ws = FakeWS([{"tokens": [], "error_code": 401, "error_type": "unauthenticated", "error_message": "Invalid API key."}], end=FINALIZE)
    with pytest.raises(ProviderError) as e:
        await SonioxSTT("bad", connect=fake_connect(ws, {})).transcribe(b"x", "audio/webm")
    assert "soniox stt HTTP 401" in str(e.value) and "clé API refusée" in str(e.value)


# ── Deepgram live ──


def dg_result(text: str, is_final: bool) -> dict:
    return {"type": "Results", "is_final": is_final, "speech_final": is_final, "channel": {"alternatives": [{"transcript": text}]}}


async def test_deepgram_live_url_and_updates():
    ws = FakeWS(
        [dg_result("il vous", False), dg_result("il vous reste", True), dg_result("du bar", False), dg_result("du bar ?", True),
         {"type": "Metadata", "request_id": "r", "duration": 1.2}],
        end=json.dumps({"type": "CloseStream"}),
    )  # fmt: skip
    seen: dict = {}
    stt = DeepgramSTT("dg", connect=fake_connect(ws, seen))
    updates = [u async for u in stt.transcribe_stream(once(b"chunk"), "audio/webm;codecs=opus", hint="Lemoine")]
    assert [u.text for u in updates] == [
        "il vous",
        "il vous reste",
        "il vous reste du bar",
        "il vous reste du bar ?",
        "il vous reste du bar ?",
    ]
    assert updates[-1].final and not any(u.final for u in updates[:-1])
    url = urlparse(seen["url"])
    assert (url.scheme, url.netloc, url.path) == ("wss", "api.deepgram.com", "/v1/listen")
    assert parse_qs(url.query) == {
        "model": ["nova-3"], "language": ["fr"], "smart_format": ["true"], "keyterm": ["Lemoine"], "interim_results": ["true"],
    }  # fmt: skip
    assert seen["headers"] == {"Authorization": "Token dg"} and ws.sent == [b"chunk", '{"type": "CloseStream"}']


async def test_default_transcribe_stream_uses_transcribe():
    reply = {"results": {"channels": [{"alternatives": [{"transcript": "Bonjour"}]}]}}
    http, seen = recorder(lambda _: httpx.Response(200, json=reply))
    # the base-class fallback (buffer, then transcribe()), exercised through Deepgram's REST call
    updates = [u async for u in STTClient.transcribe_stream(DeepgramSTT("dg", http=http), once(b"a", b"b"), "audio/webm")]
    assert updates == [STTUpdate("Bonjour", final=True, stable="Bonjour")] and seen[0].content == b"ab"


# ── Gradium ──


def ndjson(*msgs, chunk=11) -> httpx.Response:
    raw = "".join(json.dumps(m) + "\n" for m in msgs).encode()

    async def stream():
        for i in range(0, len(raw), chunk):
            yield raw[i : i + chunk]

    return httpx.Response(200, content=stream(), headers={"content-type": "application/x-ndjson"})


async def test_gradium_tts_request_and_mp3_stream():
    pcm = b"".join(struct.pack("<h", int(6000 * math.sin(i / 48000 * 2 * math.pi * 220))) for i in range(3840 * 3))
    frames = [pcm[i : i + 7680] for i in range(0, len(pcm), 7680)]  # 80 ms chunks, as documented
    http, seen = recorder(
        lambda _: ndjson(
            *[{"type": "audio", "audio": base64.b64encode(f).decode()} for f in frames], {"type": "text", "text": "Bonjour", "start_s": 0.1}
        )
    )
    result = await GradiumTTS("gk", http=http).synthesize("Bonjour.")
    out = b"".join([c async for c in result.chunks])
    assert result.mime == "audio/mpeg" and out[:2] in (b"\xff\xfb", b"\xff\xfa")
    req = seen[0]
    assert str(req.url) == "https://api.gradium.ai/api/speech/tts" and req.headers["x-api-key"] == "gk"
    assert json.loads(req.content) == {
        "text": "Bonjour.", "voice_id": "F7Iib4MAyHIRed0x", "model_name": "default", "output_format": "pcm", "only_audio": False,
    }  # fmt: skip


async def test_gradium_tts_errors():
    http, _ = recorder(lambda _: httpx.Response(500, text="error from server 1008: API key is revoked or expired"))
    with pytest.raises(ProviderError) as e:
        await GradiumTTS("bad", http=http).synthesize("x")
    assert "gradium tts HTTP 500" in str(e.value) and "clé API refusée" in str(e.value)

    http, _ = recorder(lambda _: ndjson({"type": "error", "message": "Session is too long, please upgrade your plan.", "code": 1008}))
    result = await GradiumTTS("gk", http=http).synthesize("x")
    with pytest.raises(ProviderError, match="Session is too long"):
        [c async for c in result.chunks]


async def test_gradium_stt_converts_webm_and_parses_ndjson():
    reply = "\n".join(
        json.dumps(m)
        for m in [
            {"type": "text", "text": "Il vous reste", "start_s": 0.2},
            {"type": "text", "text": " du bar ?", "start_s": 1.0},
            {"type": "end_text", "stop_s": 1.6},
        ]
    )
    http, seen = recorder(lambda _: httpx.Response(200, text=reply, headers={"content-type": "application/x-ndjson"}))
    text = await GradiumSTT("gk", http=http).transcribe(webm_sample(), "audio/webm;codecs=opus", hint="Lemoine, bar de ligne")
    assert text == "Il vous reste du bar ?"
    req = seen[0]
    assert req.url.path == "/api/speech/asr" and req.headers["x-api-key"] == "gk" and req.headers["content-type"] == "audio/ogg"
    assert req.url.params["model"] == "default"
    assert json.loads(req.url.params["json_config"]) == {
        "language": "fr",
        "keywords": {"words": ["Lemoine", "bar", "de", "ligne"], "boost": 3},
    }
    assert req.content == webm_to_ogg(webm_sample())


async def test_gradium_stt_formats():
    assert GradiumSTT.prepare(b"OggS..", "audio/ogg;codecs=opus") == (b"OggS..", "audio/ogg")
    assert GradiumSTT.prepare(b"RIFF..", "audio/wav") == (b"RIFF..", "audio/wav")
    with pytest.raises(ProviderError, match="format audio non supporté"):
        GradiumSTT.prepare(b"....", "audio/mp4")  # Safari
    with pytest.raises(ProviderError, match="format audio non supporté"):
        GradiumSTT.prepare(b"garbage", "audio/webm")

    http, _ = recorder(lambda _: httpx.Response(200, text='{"type": "error", "message": "boom"}\n'))
    with pytest.raises(ProviderError, match="boom"):
        await GradiumSTT("gk", http=http).transcribe(b"RIFF", "audio/wav")


# ── factory ──


def test_factory_builds_the_four_speech_providers_with_french_defaults():
    stt = lambda p, **kw: make_stt_client(
        STTSettings(provider=p, api_key=kw.get("key", "k"), model=kw.get("model", ""), language="fr", mock_text="")
    )
    tts = lambda p, **kw: make_tts_client(TTSSettings(provider=p, api_key="k", model="", voice=kw.get("voice", ""), language="fr"))

    assert (type(stt("deepgram")).__name__, stt("deepgram").model) == ("DeepgramSTT", "nova-3")
    assert (type(stt("soniox")).__name__, stt("soniox").model) == ("SonioxSTT", "stt-rt-v6")
    assert (type(stt("gradium")).__name__, stt("gradium").model) == ("GradiumSTT", "default")
    assert stt("soniox", model="stt-rt-v5").model == "stt-rt-v5"
    assert (type(tts("elevenlabs")).__name__, tts("elevenlabs").model) == ("ElevenLabsTTS", "eleven_flash_v2_5")
    assert (type(tts("gradium")).__name__, tts("gradium").voice) == ("GradiumTTS", "F7Iib4MAyHIRed0x")
    assert tts("gradium", voice="0fvH6XAKvA748v2v").voice == "0fvH6XAKvA748v2v"
    with pytest.raises(ConfigError, match="STT_API_KEY"):
        stt("soniox", key="")
    with pytest.raises(ConfigError, match="soniox"):
        stt("nope")
