"""
sanitize_history(): make a conversation safe to send to any provider, whatever the client rebuilt.

Every provider rejects a broken tool pairing with a 400 (Anthropic: "unexpected tool_use_id found in
tool_result blocks", "tool_use ids were found without tool_result blocks"; OpenAI: "messages with role
'tool' must be a response to a preceding message with 'tool_calls'"; Gemini: function response count
mismatch). One bad message in the browser's history would then fail every following turn.

Guarantees on the result:
  - every tool message directly follows (in the same block of tool messages) the assistant message
    whose tool_calls contain its id; orphans and duplicates are dropped;
  - every tool call of an assistant message has exactly one result; a missing one gets
    {"error": "interrompu"} (the turn was cut while the tool ran);
  - no empty / whitespace-only user message, no empty assistant message without tool calls;
  - no system message (the harness owns the system prompt);
  - it starts on a user message.
"""

import json

from app.schemas import ChatMessage

INTERRUPTED = json.dumps({"error": "interrompu"}, ensure_ascii=False, separators=(",", ":"))


def sanitize_history(messages: list[ChatMessage]) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    i, n = 0, len(messages)
    while i < n:
        m = messages[i]
        i += 1
        if m.role == "system":
            continue
        if m.role == "tool":  # not right after an assistant tool-call message (handled below): orphan
            continue
        if m.role == "user":
            if m.content.strip():
                out.append(m)
            continue
        # assistant
        calls = m.tool_calls or []
        if not calls:
            if m.content.strip():
                out.append(m if m.tool_calls is None else m.model_copy(update={"tool_calls": None}))
            continue
        # keep the first call of each id (a duplicated id is ambiguous for every provider)
        seen_ids: set[str] = set()
        unique = [c for c in calls if c.id and not (c.id in seen_ids or seen_ids.add(c.id))]
        if not unique:
            if m.content.strip():
                out.append(ChatMessage(role="assistant", content=m.content))
            continue
        # the tool messages that follow belong to this step
        results: dict[str, ChatMessage] = {}
        while i < n and messages[i].role == "tool":
            r = messages[i]
            i += 1
            if r.tool_call_id in seen_ids and r.tool_call_id not in results:
                results[r.tool_call_id] = r
        content = m.content if m.content.strip() else ""
        out.append(m.model_copy(update={"content": content, "tool_calls": unique}) if (content != m.content or unique != calls) else m)
        for c in unique:  # results in call order (Gemini pairs them by position, and needs the tool name)
            r = results.get(c.id)
            if r is None:
                r = ChatMessage(role="tool", tool_call_id=c.id, name=c.name, content=INTERRUPTED)
            elif not r.name:
                r = r.model_copy(update={"name": c.name})
            out.append(r)
    start = next((k for k, m in enumerate(out) if m.role == "user"), len(out))
    return out[start:]
