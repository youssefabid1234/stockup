"""
Anthropic Messages API adapter (POST /v1/messages, stream: true, tool_use blocks).

Differences with OpenAI:
  - the system prompt is a top-level field;
  - tool results go back as `tool_result` blocks inside a *user* message
    (consecutive tool messages are merged into one user message);
  - recent Claude models think: their `thinking` blocks must be sent back unchanged with the
    assistant turn that called tools, so we remember them by tool-call id.

Prompt caching: the prefix tools → system → messages is cached with 3 `cache_control` breakpoints
(last tool, system block, last block of the last message), so the next model call of the same turn
(after a tool) and the next turn re-read it at ~10% of the price. The prefix must stay byte-identical:
tools in a fixed order, no timestamp / id in the system prompt, thinking blocks replayed unchanged.
Hits show up as `cache_read_input_tokens` in the usage.
"""

from collections.abc import AsyncIterator

import httpx

from app.schemas import ChatMessage, ToolCall

from .base import LLMClient, LLMEvent, LLMRequest, LLMText, LLMToolCall, LLMUsage
from .http import ProviderError, http_client, parse_args, post_stream, sse_json

CACHE = {"type": "ephemeral"}  # 5-minute prompt cache breakpoint (max 4 per request; we use 3)

# thinking blocks of an assistant turn, keyed by the id of its first tool call
_thinking_by_call: dict[str, list[dict]] = {}


class AnthropicLLM(LLMClient):
    provider = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        effort: str | None = "low",  # "low" keeps voice latency down; raise for harder reasoning
        http: httpx.AsyncClient | None = None,
    ):
        self.model, self.api_key, self.base_url, self.effort, self.http = model, api_key, base_url.rstrip("/"), effort, http

    def build_body(self, req: LLMRequest) -> dict:
        messages = to_anthropic_messages(req.messages)
        mark_last_block(messages)
        body: dict = {
            "model": self.model,
            "max_tokens": req.max_tokens or 4096,
            "stream": True,
            "messages": messages,
        }
        if req.system:  # a list of blocks so it can carry a cache breakpoint
            body["system"] = [{"type": "text", "text": req.system, "cache_control": CACHE}]
        if self.effort:
            body["output_config"] = {"effort": self.effort}
        if req.tools:
            body["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in req.tools]
            body["tools"][-1]["cache_control"] = CACHE
        return body

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMEvent]:
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
        res = await post_stream(self.http or http_client(), f"{self.base_url}/v1/messages", json=self.build_body(req), headers=headers, limit=500)

        # Content blocks stream by index; tool_use inputs arrive as partial JSON strings.
        blocks: dict[int, dict] = {}
        tool_calls: list[dict] = []
        usage: dict = {}  # message_start gives the input side, message_delta the (cumulative) output side
        async for ev in sse_json(res):
            match ev.get("type"):
                case "message_start":
                    usage.update((ev.get("message") or {}).get("usage") or {})
                case "content_block_start":
                    blocks[ev["index"]] = {**ev["content_block"], "_json": ""}
                case "content_block_delta":
                    b, d = blocks.get(ev["index"]), ev["delta"]
                    if d["type"] == "text_delta":
                        yield LLMText(d["text"])
                    elif d["type"] == "input_json_delta" and b is not None:
                        b["_json"] += d["partial_json"]
                    elif d["type"] == "thinking_delta" and b is not None:
                        b["thinking"] = b.get("thinking", "") + d["thinking"]
                    elif d["type"] == "signature_delta" and b is not None:
                        b["signature"] = b.get("signature", "") + d["signature"]
                case "content_block_stop":
                    b = blocks.get(ev["index"])
                    if b and b.get("type") == "tool_use":
                        tool_calls.append({"id": b["id"], "name": b["name"], "args": b["_json"]})
                case "message_delta":
                    if ev.get("usage"):
                        usage.update({k: v for k, v in ev["usage"].items() if v is not None})
                        yield LLMUsage(
                            usage.get("input_tokens"),
                            usage.get("output_tokens"),
                            cache_creation_input_tokens=usage.get("cache_creation_input_tokens"),
                            cache_read_input_tokens=usage.get("cache_read_input_tokens"),
                        )
                case "error":
                    raise ProviderError(f"anthropic: {(ev.get('error') or {}).get('message', 'stream error')}")

        thinking = [
            {k: v for k, v in b.items() if k != "_json"}
            for b in blocks.values()
            if b.get("type") in ("thinking", "redacted_thinking")
        ]
        if tool_calls and thinking:
            _thinking_by_call[tool_calls[0]["id"]] = thinking
        for tc in tool_calls:
            yield LLMToolCall(ToolCall(id=tc["id"], name=tc["name"], arguments=parse_args(tc["args"])))


def to_anthropic_messages(messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.role == "tool":
            block = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        elif m.role == "assistant" and m.tool_calls:
            out.append({
                "role": "assistant",
                "content": [
                    *_thinking_by_call.get(m.tool_calls[0].id, []),
                    *([{"type": "text", "text": m.content}] if m.content.strip() else []),  # no blank text block (400)
                    *({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in m.tool_calls),
                ],
            })
        elif m.role in ("user", "assistant") and m.content.strip():
            # always a block list: the same message renders identically whether or not it carries the breakpoint
            out.append({"role": m.role, "content": [{"type": "text", "text": m.content}]})
    return out


def mark_last_block(messages: list[dict]) -> None:
    """Cache breakpoint on the last content block of the conversation: the next call (after a tool result,
    or next turn) re-reads everything up to here from the cache. Thinking blocks can't carry one: skipped."""
    if not messages:
        return
    blocks = messages[-1]["content"]
    if blocks and blocks[-1].get("type") not in ("thinking", "redacted_thinking"):
        blocks[-1] = {**blocks[-1], "cache_control": CACHE}
