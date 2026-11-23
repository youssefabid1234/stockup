"""
Google Gemini adapter (POST models/{model}:streamGenerateContent?alt=sse, functionDeclarations).

Differences: roles are "user" / "model"; tool results are `functionResponse` parts that need the
function *name*; newer models attach a `thoughtSignature` to function calls that must be sent back.
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.schemas import ChatMessage, ToolCall

from .base import LLMClient, LLMEvent, LLMRequest, LLMText, LLMToolCall, LLMUsage
from .http import http_client, new_call_id, post_stream, sse_json

_signature_by_call: dict[str, str] = {}


class GeminiLLM(LLMClient):
    provider = "gemini"

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        http: httpx.AsyncClient | None = None,
    ):
        self.model, self.api_key, self.base_url, self.http = model, api_key, base_url.rstrip("/"), http

    def build_body(self, req: LLMRequest) -> dict:
        body: dict = {"systemInstruction": {"parts": [{"text": req.system}]}, "contents": to_gemini_contents(req.messages)}
        if req.tools:
            body["tools"] = [
                {"functionDeclarations": [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in req.tools]}
            ]
        if req.max_tokens:
            body["generationConfig"] = {"maxOutputTokens": req.max_tokens}
        return body

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMEvent]:
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse"
        res = await post_stream(self.http or http_client(), url, json=self.build_body(req), headers={"x-goog-api-key": self.api_key}, limit=500)

        usage = None
        async for chunk in sse_json(res):
            candidate = (chunk.get("candidates") or [{}])[0] or {}
            for part in (candidate.get("content") or {}).get("parts") or []:
                if part.get("text") and not part.get("thought"):
                    yield LLMText(part["text"])
                if fc := part.get("functionCall"):
                    call_id = fc.get("id") or new_call_id("gem")
                    if part.get("thoughtSignature"):
                        _signature_by_call[call_id] = part["thoughtSignature"]
                    yield LLMToolCall(ToolCall(id=call_id, name=fc["name"], arguments=fc.get("args") or {}))
            if chunk.get("usageMetadata"):
                usage = chunk["usageMetadata"]
        if usage:
            yield LLMUsage(usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))


def to_gemini_contents(messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = []

    def push(role: str, part: dict) -> None:  # consecutive parts of the same role share one content
        if out and out[-1]["role"] == role:
            out[-1]["parts"].append(part)
        else:
            out.append({"role": role, "parts": [part]})

    for m in messages:
        if m.role == "tool":
            try:
                response = json.loads(m.content)
            except json.JSONDecodeError:
                response = m.content
            if not isinstance(response, dict):
                response = {"result": response}
            push("user", {"functionResponse": {"name": m.name or "tool", "response": response}})
        elif m.role == "assistant":
            if m.content:
                push("model", {"text": m.content})
            for c in m.tool_calls or []:
                part: dict = {"functionCall": {"name": c.name, "args": c.arguments}}
                if sig := _signature_by_call.get(c.id):
                    part["thoughtSignature"] = sig
                push("model", part)
        elif m.role == "user" and m.content:
            push("user", {"text": m.content})
    return out
