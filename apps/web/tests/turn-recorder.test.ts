/**
 * TurnRecorder: the history the browser rebuilds from /chat events must always pair tool calls and results.
 * Run: pnpm --filter @kit/web test   (node --test with tsx, no test framework needed)
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import type { ChatMessage, ChatStreamEvent } from "@kit/shared";
import { INTERRUPTED_RESULT, TurnRecorder } from "../src/features/assistant/turn-recorder";

const call = (id: string, name = "search_clients"): ChatStreamEvent => ({ type: "tool_call", call: { id, name, arguments: {} } });
const result = (id: string, name = "search_clients"): ChatStreamEvent => ({ type: "tool_result", callId: id, name, ok: true, result: { id }, ms: 1 });
const text = (delta: string): ChatStreamEvent => ({ type: "text", delta });
const done = (content: string): ChatStreamEvent => ({ type: "done", message: { role: "assistant", content }, ms: 1 });

/** What Anthropic checks: every tool result answers a call of the assistant message just before its block, and
 * every call of an assistant message is answered in the block right after it. */
function assertPaired(messages: ChatMessage[]) {
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role !== "assistant" || !m.toolCalls?.length) {
      if (m.role === "tool") {
        let j = i;
        while (j >= 0 && messages[j].role === "tool") j--;
        const owner = messages[j];
        assert.ok(owner?.role === "assistant" && owner.toolCalls?.some((c) => c.id === m.toolCallId), `orphan result ${m.toolCallId} at ${i}`);
      }
      continue;
    }
    const block: string[] = [];
    for (let j = i + 1; j < messages.length && messages[j].role === "tool"; j++) block.push(messages[j].toolCallId!);
    assert.deepEqual([...block].sort(), m.toolCalls.map((c) => c.id).sort(), `calls of message ${i} not all answered`);
  }
}

function record(events: ChatStreamEvent[]) {
  const r = new TurnRecorder();
  events.forEach((e) => r.push(e));
  return r;
}

test("two chained tool rounds without text: one assistant message per round", () => {
  const r = record([call("a"), result("a"), call("b", "get_order"), result("b", "get_order"), text("Voilà."), done("Voilà.")]);
  assertPaired(r.messages);
  assert.deepEqual(r.messages.map((m) => m.role), ["assistant", "tool", "assistant", "tool", "assistant"]);
  assert.equal(r.messages[2].toolCalls?.[0].id, "b");
});

test("parallel calls then a second round, text + calls in the same step", () => {
  const r = record([text("Je regarde."), call("a"), call("b"), result("a"), result("b"), text("Et "), call("c"), result("c"), done("Fait.")]);
  assertPaired(r.messages);
  assert.equal(r.messages[0].content, "Je regarde.");
  assert.deepEqual(r.messages[0].toolCalls?.map((c) => c.id), ["a", "b"]);
  assert.equal(r.messages[3].content, "Et ");
  assert.deepEqual(r.messages[3].toolCalls?.map((c) => c.id), ["c"]);
  assert.equal(r.messages.at(-1)?.content, "Fait.");
});

test("tool error result is kept as a normal result", () => {
  const r = record([call("a"), { type: "tool_result", callId: "a", name: "search_clients", ok: false, result: { error: "boom" }, ms: 1 }, done("Erreur.")]);
  assertPaired(r.messages);
  assert.equal(r.messages[1].content, JSON.stringify({ error: "boom" }));
});

test("stop between two results of parallel calls: the missing result is synthesized", () => {
  const r = record([call("a"), call("b"), result("a")]);
  const msgs = r.finish();
  assertPaired(msgs);
  assert.equal(msgs.find((m) => m.toolCallId === "b")?.content, INTERRUPTED_RESULT);
  assert.equal(msgs.at(-1)?.role, "assistant");
});

test("stop while tools run (calls announced, no result): calls dropped, text kept", () => {
  const r = record([call("a"), result("a"), text("Je crée"), call("b", "create_order")]);
  const msgs = r.finish();
  assertPaired(msgs);
  assert.deepEqual(msgs.map((m) => m.role), ["assistant", "tool", "assistant"]);
  assert.equal(msgs.at(-1)?.content, "Je crée");
});

test("error event after tool results: history still closes on an assistant message", () => {
  const r = record([call("a"), result("a"), call("b"), result("b"), { type: "error", message: "provider down" }]);
  const msgs = r.finish();
  assertPaired(msgs);
  assert.equal(msgs.at(-1)?.content, "(réponse interrompue)");
});

test("max steps (give-up text after the last results)", () => {
  const r = record([call("a"), result("a"), call("b"), result("b"), text("Désolé"), done("Désolé")]);
  assertPaired(r.finish());
  assert.equal(r.messages.length, 5);
});

test("empty final answer: finish adds nothing more", () => {
  const r = record([call("a"), result("a"), done("")]);
  const msgs = r.finish();
  assertPaired(msgs);
  assert.equal(msgs.length, 3);
});
