"""
Provider adapters, tested offline: httpx.MockTransport plays the provider (recorded-style SSE / JSON),
and we check both the request we build and the events we parse.
"""

import json

import httpx

from app.clients import LLMRequest, LLMText, LLMToolCall, LLMUsage
from app.clients.anthropic import AnthropicLLM
from app.clients.deepgram import DeepgramSTT
from app.clients.elevenlabs import ElevenLabsTTS
from app.clients.gemini import GeminiLLM
from app.clients.openai import OpenAILLM, OpenAISTT, OpenAITTS
from app.schemas import ChatMessage, ToolCall, ToolInfo

TOOLS = [ToolInfo(name="search", description="Recherche", parameters={"type": "object", "properties": {"query": {"type": "string"}}})]


def sse(*events, done=False, chunk=7) -> httpx.Response:
    """An SSE body, cut into small chunks so the parser has to re-assemble lines."""
    body = "".join(f"data: {json.dumps(e)}\r\n\r\n" for e in events) + ("data: [DONE]\n\n" if done else "")
    raw = body.encode()

    async def stream():
        for i in range(0, len(raw), chunk):
            yield raw[i : i + chunk]

    return httpx.Response(200, content=stream(), headers={"content-type": "text/event-stream"})


def recorder(response_for):
    """MockTransport that records requests and answers with response_for(request)."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response_for(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


async def collect(llm, req):
    return [ev async for ev in llm.stream(req)]


# ── OpenAI ──


async def test_openai_stream_text_tools_usage():
    events = [
        {"choices": [{"delta": {"content": "Je "}}]},
        {"choices": [{"delta": {"content": "regarde."}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_a", "function": {"name": "sea", "arguments": '{"qu'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "rch", "arguments": 'ery":"bar"}'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "call_b", "function": {"name": "search", "arguments": "{}"}}]}}]},
        {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 5}},
    ]
    http, seen = recorder(lambda _: sse(*events, done=True))
    llm = OpenAILLM("gpt-x", "sk-test", "https://example.test/v1/", http=http)
    history = [
        ChatMessage(role="user", content="bar ?"),
        ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id="c1", name="search", arguments={"query": "bar"})]),
        ChatMessage(role="tool", tool_call_id="c1", name="search", content="[]"),
    ]
    out = await collect(llm, LLMRequest(system="SYS", messages=history, tools=TOOLS, max_tokens=50))

    assert out == [
        LLMText("Je "),
        LLMText("regarde."),
        LLMUsage(12, 5),
        LLMToolCall(ToolCall(id="call_a", name="search", arguments={"query": "bar"})),
        LLMToolCall(ToolCall(id="call_b", name="search", arguments={})),
    ]
    req = seen[0]
    assert str(req.url) == "https://example.test/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body == {
        "model": "gpt-x",
        "stream": True,
        "messages": [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "bar ?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "search", "arguments": '{"query":"bar"}'}}],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "[]"},
        ],
        "tools": [{"type": "function", "function": {"name": "search", "description": "Recherche", "parameters": TOOLS[0].parameters}}],
        "max_tokens": 50,
        "stream_options": {"include_usage": True},
    }


async def test_openai_compatible_no_key_no_usage_option():
    http, seen = recorder(lambda _: sse({"choices": [{"delta": {"content": "ok"}}]}, done=True))
    llm = OpenAILLM("llama", "", "http://localhost:11434/v1", provider="openai-compatible", include_usage=False, http=http)
    out = await collect(llm, LLMRequest(system="S", messages=[ChatMessage(role="user", content="hi")]))
    assert out == [LLMText("ok")]
    body = json.loads(seen[0].content)
    assert "authorization" not in seen[0].headers and "stream_options" not in body and "tools" not in body


async def test_openai_http_error_is_raised_with_body():
    http, _ = recorder(lambda _: httpx.Response(401, text='{"error":"bad key"}'))
    llm = OpenAILLM("gpt-x", "sk-bad", http=http)
    try:
        await collect(llm, LLMRequest(system="S", messages=[]))
    except Exception as e:
        assert "api.openai.com HTTP 401" in str(e) and "bad key" in str(e)
    else:
        raise AssertionError("expected an error")


# ── Anthropic ──


async def test_anthropic_stream_thinking_tools_and_replay():
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 30}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Chercher "}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "le bar."}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "SIG"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Je regarde."}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "toolu_1", "name": "search", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '{"query":'}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": ' "bar"}'}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 40}},
        {"type": "message_stop"},
    ]
    http, seen = recorder(lambda _: sse(*events))
    llm = AnthropicLLM("claude-test", "key", "https://anthropic.test", effort="low", http=http)
    out = await collect(llm, LLMRequest(system="SYS", messages=[ChatMessage(role="user", content="bar ?")], tools=TOOLS))
    assert out == [LLMText("Je regarde."), LLMUsage(30, 40), LLMToolCall(ToolCall(id="toolu_1", name="search", arguments={"query": "bar"}))]

    first = json.loads(seen[0].content)
    assert str(seen[0].url) == "https://anthropic.test/v1/messages"
    assert seen[0].headers["x-api-key"] == "key" and seen[0].headers["anthropic-version"] == "2023-06-01"
    assert first == {
        "model": "claude-test",
        "max_tokens": 4096,
        "stream": True,
        "system": [{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "bar ?", "cache_control": {"type": "ephemeral"}}]}],
        "output_config": {"effort": "low"},
        "tools": [{"name": "search", "description": "Recherche", "input_schema": TOOLS[0].parameters, "cache_control": {"type": "ephemeral"}}],
    }

    # Next request: the thinking block goes back with the tool-calling turn; tool results merge into one user message.
    history = [
        ChatMessage(role="user", content="bar ?"),
        ChatMessage(role="assistant", content="Je regarde.", tool_calls=[ToolCall(id="toolu_1", name="search", arguments={"query": "bar"})]),
        ChatMessage(role="tool", tool_call_id="toolu_1", name="search", content="[1]"),
        ChatMessage(role="tool", tool_call_id="toolu_2", name="search", content="[2]"),
    ]
    await collect(llm, LLMRequest(system="SYS", messages=history))
    assert json.loads(seen[1].content)["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "bar ?"}]},
        {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Chercher le bar.", "signature": "SIG"},
                {"type": "text", "text": "Je regarde."},
                {"type": "tool_use", "id": "toolu_1", "name": "search", "input": {"query": "bar"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "[1]"},
                {"type": "tool_result", "tool_use_id": "toolu_2", "content": "[2]", "cache_control": {"type": "ephemeral"}},
            ],
        },
    ]


def count_breakpoints(value) -> int:
    if isinstance(value, dict):
        return ("cache_control" in value) + sum(count_breakpoints(v) for v in value.values())
    if isinstance(value, list):
        return sum(count_breakpoints(v) for v in value)
    return 0


def test_anthropic_cache_breakpoints_and_stable_prefix():
    tools = [*TOOLS, ToolInfo(name="get_price", description="Prix", parameters={"type": "object", "properties": {}})]
    llm = AnthropicLLM("m", "k")
    step1 = [ChatMessage(role="user", content="bar ?")]
    step2 = [
        *step1,
        ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id="toolu_9", name="search", arguments={"query": "bar"})]),
        ChatMessage(role="tool", tool_call_id="toolu_9", name="search", content="[1]"),
    ]
    b1 = llm.build_body(LLMRequest(system="SYS", messages=step1, tools=tools))
    b2 = llm.build_body(LLMRequest(system="SYS", messages=step2, tools=tools))
    for body in (b1, b2):
        assert count_breakpoints(body) == 3  # ≤ 4 allowed by the API
        assert body["tools"][-1]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in body["tools"][0]
        assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert body["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    # Same tools + system bytes on both steps (the cached prefix), and step 2 extends step 1's messages.
    assert json.dumps(b1["tools"]) == json.dumps(b2["tools"]) and json.dumps(b1["system"]) == json.dumps(b2["system"])
    assert b2["messages"][0]["content"][0]["text"] == "bar ?" and "cache_control" not in b2["messages"][0]["content"][0]
    # No tools, no system: no stray breakpoint, no empty system field.
    bare = llm.build_body(LLMRequest(system="", messages=step1))
    assert "system" not in bare and "tools" not in bare and count_breakpoints(bare) == 1


async def test_anthropic_usage_with_cache_tokens():
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 12, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 26800, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Il en reste 12 kilos."}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 9, "cache_read_input_tokens": None}},
        {"type": "message_stop"},
    ]
    http, _ = recorder(lambda _: sse(*events))
    out = await collect(AnthropicLLM("m", "k", http=http), LLMRequest(system="S", messages=[ChatMessage(role="user", content="bar ?")]))
    assert out[-1] == LLMUsage(12, 9, cache_creation_input_tokens=0, cache_read_input_tokens=26800)


async def test_anthropic_stream_error_event():
    http, _ = recorder(lambda _: sse({"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}))
    try:
        await collect(AnthropicLLM("m", "k", http=http), LLMRequest(system="S", messages=[]))
    except Exception as e:
        assert str(e) == "anthropic: Overloaded"
    else:
        raise AssertionError("expected an error")


# ── Gemini ──


async def test_gemini_stream_and_signature_replay():
    events = [
        {"candidates": [{"content": {"role": "model", "parts": [{"text": "réflexion", "thought": True}, {"text": "Je "}]}}]},
        {"candidates": [{"content": {"role": "model", "parts": [{"text": "regarde."}]}}]},
        {
            "candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": "search", "args": {"query": "bar"}}, "thoughtSignature": "TS1"}]}}],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 8},
        },
    ]
    http, seen = recorder(lambda _: sse(*events))
    llm = GeminiLLM("gemini-test", "gkey", "https://gemini.test/v1beta", http=http)
    out = await collect(llm, LLMRequest(system="SYS", messages=[ChatMessage(role="user", content="bar ?")], tools=TOOLS, max_tokens=100))
    assert out[:2] == [LLMText("Je "), LLMText("regarde.")]
    call = out[2].call
    assert call.id.startswith("gem_") and call.name == "search" and call.arguments == {"query": "bar"}
    assert out[3] == LLMUsage(20, 8)

    assert str(seen[0].url) == "https://gemini.test/v1beta/models/gemini-test:streamGenerateContent?alt=sse"
    assert seen[0].headers["x-goog-api-key"] == "gkey"
    assert json.loads(seen[0].content) == {
        "systemInstruction": {"parts": [{"text": "SYS"}]},
        "contents": [{"role": "user", "parts": [{"text": "bar ?"}]}],
        "tools": [{"functionDeclarations": [{"name": "search", "description": "Recherche", "parameters": TOOLS[0].parameters}]}],
        "generationConfig": {"maxOutputTokens": 100},
    }

    history = [
        ChatMessage(role="user", content="bar ?"),
        ChatMessage(role="assistant", content="Je regarde.", tool_calls=[call]),
        ChatMessage(role="tool", tool_call_id=call.id, name="search", content='[{"id":"prd_1"}]'),
    ]
    await collect(llm, LLMRequest(system="SYS", messages=history))
    assert json.loads(seen[1].content)["contents"] == [
        {"role": "user", "parts": [{"text": "bar ?"}]},
        {"role": "model", "parts": [{"text": "Je regarde."}, {"functionCall": {"name": "search", "args": {"query": "bar"}}, "thoughtSignature": "TS1"}]},
        {"role": "user", "parts": [{"functionResponse": {"name": "search", "response": {"result": [{"id": "prd_1"}]}}}]},
    ]


# ── Speech ──


async def test_deepgram_params_and_transcript():
    reply = {"results": {"channels": [{"alternatives": [{"transcript": " il vous reste du bar ? "}]}]}}
    http, seen = recorder(lambda _: httpx.Response(200, json=reply))
    text = await DeepgramSTT("dg", http=http).transcribe(b"AUDIO", "audio/webm", hint="Lemoine, bar de ligne ,")
    assert text == "il vous reste du bar ?"
    req = seen[0]
    assert req.url.path == "/v1/listen"
    assert req.url.params.multi_items() == [
        ("model", "nova-3"), ("language", "fr"), ("smart_format", "true"), ("keyterm", "Lemoine"), ("keyterm", "bar de ligne"),
    ]  # fmt: skip
    assert req.headers["authorization"] == "Token dg" and req.headers["content-type"] == "audio/webm"
    assert req.content == b"AUDIO"


async def test_openai_stt_multipart():
    http, seen = recorder(lambda _: httpx.Response(200, json={"text": "Bonjour "}))
    assert await OpenAISTT("sk", http=http).transcribe(b"AUDIO", "audio/webm;codecs=opus", hint="Lemoine") == "Bonjour"
    req = seen[0]
    body = req.content.decode("latin-1")
    assert req.url.path == "/v1/audio/transcriptions" and req.headers["authorization"] == "Bearer sk"
    assert 'filename="audio.webm"' in body and "gpt-4o-mini-transcribe" in body and 'name="prompt"' in body and "Lemoine" in body


async def test_openai_tts_streams_mp3():
    http, seen = recorder(lambda _: httpx.Response(200, content=b"ID3mp3bytes"))
    result = await OpenAITTS("sk", http=http).synthesize("Bonjour", voice="nova")
    assert result.mime == "audio/mpeg" and b"".join([c async for c in result.chunks]) == b"ID3mp3bytes"
    assert json.loads(seen[0].content) == {"model": "gpt-4o-mini-tts", "voice": "nova", "input": "Bonjour", "response_format": "mp3"}


async def test_elevenlabs_request_and_error():
    http, seen = recorder(lambda _: httpx.Response(200, content=b"mp3"))
    result = await ElevenLabsTTS("xi", http=http).synthesize("Bonjour")
    assert b"".join([c async for c in result.chunks]) == b"mp3"
    req = seen[0]
    assert req.url.path == "/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb/stream" and req.url.params["output_format"] == "mp3_44100_128"
    assert req.headers["xi-api-key"] == "xi"
    assert json.loads(req.content) == {"text": "Bonjour", "model_id": "eleven_flash_v2_5", "language_code": "fr"}

    http, _ = recorder(lambda _: httpx.Response(429, text="quota"))
    try:
        await ElevenLabsTTS("xi", http=http).synthesize("x")
    except Exception as e:
        assert str(e) == "elevenlabs tts HTTP 429: quota — limite de débit ou quota atteint : réessayez dans un instant"
    else:
        raise AssertionError("expected an error")
