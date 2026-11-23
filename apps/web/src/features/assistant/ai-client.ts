/** AI service client (proxied at /ai → :4100): health query, chat SSE stream, history rebuild from events. */
import { useQuery } from "@tanstack/react-query";
import type { ChatRequest, ChatStreamEvent } from "@kit/shared";
import { AI_BASE } from "@/lib/api";

export interface AiHealth {
  ok: boolean;
  llm: { provider: string; model?: string };
  stt: { provider: string };
  tts: { provider: string };
}

export class AiUnavailableError extends Error {}

export async function fetchAiHealth(signal?: AbortSignal): Promise<AiHealth> {
  let res: Response;
  try {
    res = await fetch(`${AI_BASE}/health`, { signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new AiUnavailableError("Service IA injoignable");
  }
  if (!res.ok) throw new AiUnavailableError(`Service IA injoignable (${res.status})`);
  return (await res.json()) as AiHealth;
}

/** GET /ai/health, polled slowly so the panel recovers on its own once the service starts. */
export const useAiHealth = () =>
  useQuery({
    queryKey: ["ai", "health"],
    queryFn: ({ signal }) => fetchAiHealth(signal),
    retry: false,
    refetchInterval: (q) => (q.state.status === "error" ? 5_000 : 60_000),
    staleTime: 30_000,
  });

/** POST /ai/chat and call onEvent for each SSE `data:` line. Resolves when the stream ends. */
export async function streamChat(req: ChatRequest, onEvent: (e: ChatStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${AI_BASE}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new AiUnavailableError("Service IA injoignable (localhost:4100)");
  }
  if (!res.ok || !res.body) {
    let msg = `Service IA : erreur ${res.status}`;
    try {
      const j = await res.json();
      if (j?.error?.message) msg = j.error.message;
    } catch { /* not JSON */ }
    throw res.status >= 500 ? new AiUnavailableError(msg) : new Error(msg);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let i: number;
    while ((i = buf.search(/\r?\n\r?\n/)) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i).replace(/^\r?\n\r?\n/, "");
      const data = block.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).replace(/^ /, "")).join("\n");
      if (!data) continue;
      try {
        onEvent(JSON.parse(data) as ChatStreamEvent);
      } catch { /* ignore malformed line */ }
    }
  }
}

export { TurnRecorder } from "./turn-recorder";
