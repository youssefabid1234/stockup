/**
 * Chat conversation, kept in module memory so it survives closing/reopening the panel (⌘J) and page changes.
 * The stream keeps running while the panel is closed.
 */
import { useSyncExternalStore } from "react";
import type { ChatMessage, ChatStreamEvent } from "@kit/shared";
import { AiUnavailableError, streamChat, TurnRecorder } from "./ai-client";
import type { ToolRun } from "./tools";

export type Part = { kind: "text"; text: string } | { kind: "tool"; tool: ToolRun };

export type ChatItem =
  | { id: string; role: "user"; text: string; at: number }
  | { id: string; role: "assistant"; parts: Part[]; status: "streaming" | "done" | "error" | "stopped"; error?: string; ms?: number; at: number };

interface ChatState {
  items: ChatItem[];
  busy: boolean;
  unavailable: boolean; // last request could not reach the AI service
}

let state: ChatState = { items: [], busy: false, unavailable: false };
let history: ChatMessage[] = [];
let controller: AbortController | undefined;
const listeners = new Set<() => void>();
let seq = 0;
let generation = 0; // bumped by reset(): a stream from an older conversation must not touch the new one
const uid = () => `m${++seq}`;

function set(patch: Partial<ChatState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
}

function updateAssistant(id: string, fn: (a: Extract<ChatItem, { role: "assistant" }>) => Extract<ChatItem, { role: "assistant" }>) {
  set({ items: state.items.map((it) => (it.id === id && it.role === "assistant" ? fn(it) : it)) });
}

function applyEvent(id: string, e: ChatStreamEvent) {
  updateAssistant(id, (a) => {
    const parts = [...a.parts];
    const last = parts[parts.length - 1];
    switch (e.type) {
      case "text":
        if (last?.kind === "text") parts[parts.length - 1] = { kind: "text", text: last.text + e.delta };
        else parts.push({ kind: "text", text: e.delta });
        return { ...a, parts };
      case "tool_call":
        parts.push({ kind: "tool", tool: { id: e.call.id, name: e.call.name, args: e.call.arguments } });
        return { ...a, parts };
      case "tool_result":
        return {
          ...a,
          parts: parts.map((p) => (p.kind === "tool" && p.tool.id === e.callId ? { kind: "tool", tool: { ...p.tool, ok: e.ok, ms: e.ms, result: e.result } } : p)),
        };
      case "done":
        // Some providers answer without streaming deltas: fall back to the final message.
        if (!parts.some((p) => p.kind === "text") && e.message.content) parts.push({ kind: "text", text: e.message.content });
        return { ...a, parts, status: "done", ms: e.ms };
      case "error":
        return { ...a, status: "error", error: e.message };
    }
  });
}

export const chat = {
  async send(text: string) {
    const content = text.trim();
    if (!content || state.busy) return;
    const assistantId = uid();
    set({
      busy: true,
      unavailable: false,
      items: [
        ...state.items,
        { id: uid(), role: "user", text: content, at: Date.now() },
        { id: assistantId, role: "assistant", parts: [], status: "streaming", at: Date.now() },
      ],
    });
    const userMsg: ChatMessage = { role: "user", content };
    const recorder = new TurnRecorder();
    controller = new AbortController();
    const ctrl = controller;
    const gen = generation;
    try {
      await streamChat({ messages: [...history, userMsg], mode: "chat" }, (e) => {
        recorder.push(e);
        applyEvent(assistantId, e);
      }, ctrl.signal);
      updateAssistant(assistantId, (a) => (a.status === "streaming" ? { ...a, status: "done" } : a));
    } catch (e) {
      const err = e as Error;
      if (err.name === "AbortError") updateAssistant(assistantId, (a) => ({ ...a, status: "stopped" }));
      else {
        updateAssistant(assistantId, (a) => ({ ...a, status: "error", error: err.message }));
        if (err instanceof AiUnavailableError) set({ unavailable: true });
      }
    } finally {
      if (gen !== generation) return; // eslint-disable-line no-unsafe-finally
      // A conversation the service never saw stays out of the history (so a retry is clean).
      if (recorder.messages.length || state.items.find((i) => i.id === assistantId && i.role === "assistant" && i.parts.length)) {
        history = [...history, userMsg, ...recorder.finish()];
      }
      if (controller === ctrl) controller = undefined;
      set({ busy: false });
    }
  },
  stop() {
    controller?.abort();
  },
  reset() {
    generation++;
    controller?.abort();
    history = [];
    set({ items: [], busy: false, unavailable: false });
  },
};

export function useChat(): ChatState {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => state);
}
