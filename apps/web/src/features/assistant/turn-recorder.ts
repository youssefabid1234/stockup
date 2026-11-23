/**
 * Rebuilds, from the /chat SSE events, the ChatMessage[] the server appended during one turn
 * (assistant with toolCalls → tool results → … → final assistant), so the next request carries the full history,
 * tool results included. Pure (type imports only): unit-tested with `node --test` (turn-recorder.test.ts).
 *
 * Every provider 400s on a broken pairing, so the invariants are: each tool result sits right after the assistant
 * message whose toolCalls hold its id, and each of those calls has exactly one result.
 */
import type { ChatMessage, ChatStreamEvent, ToolCall } from "@kit/shared";

/** Result given to a tool call the turn was cut before answering (same as the server's sanitize_history). */
export const INTERRUPTED_RESULT = JSON.stringify({ error: "interrompu" });

export class TurnRecorder {
  messages: ChatMessage[] = [];
  private text = "";
  private calls: ToolCall[] = [];
  private inResults = false;

  push(e: ChatStreamEvent) {
    if (e.type === "text") {
      if (this.inResults) this.inResults = false;
      this.text += e.delta;
    } else if (e.type === "tool_call") {
      // A tool call right after tool results opens a NEW model step (no text in between): its results must
      // go under a new assistant message, or the next request pairs them with the wrong tool_use (Anthropic 400).
      if (this.inResults) this.inResults = false;
      this.calls.push(e.call);
    } else if (e.type === "tool_result") {
      if (!this.inResults) {
        this.messages.push({ role: "assistant", content: this.text, toolCalls: this.calls });
        this.text = "";
        this.calls = [];
        this.inResults = true;
      }
      this.messages.push({ role: "tool", toolCallId: e.callId, name: e.name, content: JSON.stringify(e.result ?? null) });
    } else if (e.type === "done") {
      this.closeOpenCalls();
      this.messages.push(e.message);
      this.text = "";
      this.calls = [];
      this.inResults = false;
    }
  }

  /** Messages safe to keep when the turn ends early (stop, network cut, error event): no dangling tool calls. */
  finish(): ChatMessage[] {
    this.closeOpenCalls(); // cut between two results of parallel calls: the missing ones get a result
    const last = this.messages[this.messages.length - 1];
    if (!last || last.role !== "assistant" || last.toolCalls?.length) {
      // calls announced but never run (this.calls) are dropped: only their text survives
      this.messages.push({ role: "assistant", content: this.text.trim() || "(réponse interrompue)" });
    }
    this.text = "";
    this.calls = [];
    this.inResults = false;
    return this.messages;
  }

  /** The last assistant step's calls that got no tool_result get INTERRUPTED_RESULT (in call order). */
  private closeOpenCalls() {
    let i = this.messages.length - 1;
    while (i >= 0 && this.messages[i].role === "tool") i--;
    const step = this.messages[i];
    if (!step || step.role !== "assistant" || !step.toolCalls?.length) return;
    const answered = new Set(this.messages.slice(i + 1).map((m) => m.toolCallId));
    for (const c of step.toolCalls) {
      if (!answered.has(c.id)) this.messages.push({ role: "tool", toolCallId: c.id, name: c.name, content: INTERRUPTED_RESULT });
    }
  }
}
