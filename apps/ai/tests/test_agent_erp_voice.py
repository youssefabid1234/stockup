"""ErpClient headers and verbs, tool results the model can't read, and the STT hint on WS /voice."""

import json
from datetime import datetime
from urllib.parse import unquote

import httpx

from app.agent.loop import execute_tool
from app.clients.mock_speech import MockSTT, MockTTS
from app.schemas import ToolCall
from app.services import voice_session
from app.tools import TOOLS
from app.tools.erp import ErpClient
from app.tools.registry import ToolContext, tool


def recording_erp(actor_name: str | None = None) -> tuple[ErpClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ErpClient("voice_agent", actor_name, base_url="http://erp", http=http), seen


async def test_accented_actor_name_is_percent_encoded():
    erp, seen = recording_erp("Hélène Ström")
    assert await erp.get("/api/meta") == {"ok": True}
    header = seen[0].headers["x-actor-name"]
    assert header.isascii()
    assert unquote(header) == "Hélène Ström"  # what the ERP shows (apps/backend/app/dependencies.py)
    assert seen[0].headers["x-actor"] == "voice_agent"


async def test_patch_and_delete():
    erp, seen = recording_erp()
    await erp.patch("/api/orders/ord_1", {"notes": "x"})
    await erp.delete("/api/orders/ord_1/lines/l1", {"force": True, "skip": None})
    assert [r.method for r in seen] == ["PATCH", "DELETE"]
    assert json.loads(seen[0].content) == {"notes": "x"}
    assert seen[1].url.params == httpx.QueryParams({"force": "True"})
    assert "x-actor-name" not in seen[0].headers


async def test_non_json_tool_result_becomes_an_error():
    @tool(name="demo_datetime")
    async def demo_datetime(ctx: ToolContext) -> dict:
        """Returns something json.dumps can't write."""
        return {"at": datetime(2026, 11, 24)}

    try:
        erp, _ = recording_erp()
        ev = await execute_tool(ToolCall(id="c1", name="demo_datetime", arguments={}), [demo_datetime], ToolContext(erp=erp, actor="ai_chat"))
        assert ev.ok is False
        assert "non sérialisable" in ev.result["error"]
    finally:
        TOOLS.pop("demo_datetime")


class FakeWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def send_bytes(self, data: bytes) -> None:
        pass


async def test_voice_audio_start_hint_reaches_stt(monkeypatch):
    class FakeLLM:
        provider, model = "mock", "mock"

    async def no_agent(messages, **kwargs):
        return
        yield

    monkeypatch.setattr(voice_session, "get_stt_client", lambda: MockSTT("texte fixe"))
    monkeypatch.setattr(voice_session, "get_tts_client", lambda: MockTTS())
    monkeypatch.setattr(voice_session, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(voice_session, "run_agent", no_agent)

    conn = voice_session.VoiceConnection(FakeWS())  # type: ignore[arg-type]
    await conn.handle_text(json.dumps({"type": "audio_start", "mime": "audio/webm", "hint": "il vous reste des cèpes ?"}))
    conn.recording.feed(b"\x00")  # type: ignore[union-attr]
    await conn.handle_text(json.dumps({"type": "audio_end"}))
    await conn.turn
    transcripts = [m["text"] for m in conn.ws.sent if m["type"] == "transcript" and m["final"]]
    assert transcripts == ["il vous reste des cèpes ?"]

    # without a hint, the mock STT falls back to its fixed text (the web app sends none)
    await conn.handle_text(json.dumps({"type": "audio_start", "mime": "audio/webm"}))
    await conn.handle_text(json.dumps({"type": "audio_end"}))
    await conn.turn
    assert [m["text"] for m in conn.ws.sent if m["type"] == "transcript"][-1] == "texte fixe"
