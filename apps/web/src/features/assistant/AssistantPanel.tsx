/**
 * Assistant — AI chat in the 400px right column (⌘J). Fills its parent (h-full, flex col).
 * POST /ai/chat → SSE of ChatStreamEvent (packages/shared/src/ai.ts). Tool calls render as compact violet rows that link
 * to the ERP entity; ERP writes also arrive in the activity stream on their own.
 */
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, CircleAlert, PlugZap, RotateCcw, Sparkles, Square, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button, IconButton, Kbd, Spinner } from "@/ui";
import { shell } from "@/app/shell-state";
import { useAiHealth } from "./ai-client";
import { chat, useChat, type ChatItem } from "./chat-store";
import { Markdown } from "@/ui/markdown";
import { ToolRow } from "./tools";

const SUGGESTIONS: { label: string; send: boolean }[] = [
  { label: "Qu'est-ce que commande d'habitude Le Bistrot du Port ?", send: true },
  { label: "Stock de bar de ligne ?", send: true },
  { label: "Crée une pré-commande pour ", send: false },
];

export function AssistantPanel() {
  const { items, busy, unavailable } = useChat();
  const health = useAiHealth();
  const down = health.isError || unavailable;
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  useEffect(() => { inputRef.current?.focus(); }, []);

  // Follow the stream unless the user scrolled up.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [items]);

  // Auto-grow the textarea (1 → 6 lines).
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input]);

  const submit = (text = input) => {
    if (!text.trim() || busy) return;
    stick.current = true;
    setInput("");
    void chat.send(text);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
    if (e.key === "Escape" && busy) { e.preventDefault(); chat.stop(); }
  };

  const pickSuggestion = (s: (typeof SUGGESTIONS)[number]) => {
    if (s.send) return submit(s.label);
    setInput(s.label);
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (el) { el.focus(); el.setSelectionRange(s.label.length, s.label.length); }
    });
  };

  const llm = health.data?.llm;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border pl-4 pr-2">
        <Sparkles size={14} strokeWidth={1.75} className="text-violet" />
        <div className="text-[13.5px] font-semibold">Assistant</div>
        <div className="min-w-0 flex-1 truncate pl-1 font-mono text-[10.5px] text-muted-foreground" title={llm ? `${llm.provider} · ${llm.model ?? ""}` : undefined}>
          {down ? <span className="text-destructive">hors ligne</span> : llm ? `${llm.provider}${llm.model ? ` · ${llm.model}` : ""}` : ""}
        </div>
        {items.length ? <IconButton icon={RotateCcw} label="Nouvelle conversation" size="sm" onClick={() => { chat.reset(); inputRef.current?.focus(); }} /> : null}
        <Kbd>⌘J</Kbd>
        <IconButton icon={X} label="Fermer" size="sm" onClick={shell.closeAssistant} />
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto"
        onScroll={(e) => {
          const el = e.currentTarget;
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {items.length === 0 ? (
          <div className="flex flex-col gap-4 px-4 pb-4 pt-8">
            <div className="flex flex-col gap-1.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-[4px] bg-violet/10 text-violet"><Sparkles size={16} strokeWidth={1.75} /></div>
              <div className="mt-1 text-[14px] font-semibold">Que voulez-vous savoir ?</div>
              <p className="text-[12.5px] text-muted-foreground">
                L'assistant lit l'ERP (clients, stock, commandes) et peut préparer des pré-commandes. Chaque action apparaît ici et dans l'activité.
              </p>
            </div>
            <div className="flex flex-col items-start gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  disabled={busy}
                  onClick={() => pickSuggestion(s)}
                  className="max-w-full truncate rounded-[3px] border border-border bg-card px-2 py-1 text-left text-[12px] text-secondary-foreground transition-colors hover:border-violet/40 hover:bg-violet/[.05] hover:text-foreground disabled:opacity-50"
                >
                  {s.send ? s.label : `${s.label}…`}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4 px-4 py-4">
            {items.map((it) => <Message key={it.id} it={it} />)}
          </div>
        )}
      </div>

      {down ? (
        <div className="flex shrink-0 items-start gap-2 border-t border-border bg-destructive/[.05] px-4 py-2.5 text-[12px]">
          <PlugZap size={14} strokeWidth={1.75} className="mt-px shrink-0 text-destructive" />
          <div className="min-w-0 flex-1">
            <div className="font-medium">Service IA injoignable</div>
            <div className="text-muted-foreground">
              Lancez <code className="font-mono text-[11px]">pnpm --filter @kit/ai dev</code> (port 4100).
            </div>
          </div>
          <Button size="sm" loading={health.isFetching} onClick={() => health.refetch()}>Réessayer</Button>
        </div>
      ) : null}

      <div className="shrink-0 border-t border-border p-3">
        <div className="flex items-end gap-2 rounded-[4px] border border-input bg-background px-2.5 py-1.5 focus-within:border-violet/50 focus-within:ring-2 focus-within:ring-violet/15">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Demandez à l'assistant…"
            className="max-h-[120px] min-h-[22px] flex-1 resize-none bg-transparent py-0.5 text-[13px] leading-[18px] outline-none placeholder:text-muted-foreground"
          />
          {busy ? (
            <IconButton icon={Square} label="Arrêter (Échap)" size="sm" variant="default" onClick={chat.stop} />
          ) : (
            <IconButton
              icon={ArrowUp}
              label="Envoyer (Entrée)"
              size="sm"
              variant="default"
              disabled={!input.trim()}
              onClick={() => submit()}
              className={cn(input.trim() && "border-violet bg-violet text-primary-foreground hover:bg-violet/90 hover:text-primary-foreground")}
            />
          )}
        </div>
        <div className="mt-1.5 flex items-center justify-between px-0.5 text-[10.5px] text-muted-foreground">
          <span>Entrée pour envoyer · Maj+Entrée pour un saut de ligne</span>
        </div>
      </div>
    </div>
  );
}

function Message({ it }: { it: ChatItem }) {
  if (it.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[4px] bg-muted px-2.5 py-1.5 text-[13px]">{it.text}</div>
      </div>
    );
  }
  const empty = it.parts.length === 0;
  return (
    <div className="flex flex-col gap-1.5 text-[13px] leading-[19px]">
      {it.parts.map((p, i) =>
        p.kind === "text" ? (
          <div key={i} className={cn(i === it.parts.length - 1 && it.status === "streaming" && "after:ml-0.5 after:inline-block after:h-3 after:w-[2px] after:animate-pulse after:bg-violet after:align-middle after:content-['']")}>
            <Markdown text={p.text} />
          </div>
        ) : (
          <ToolRow key={p.tool.id || i} t={p.tool} />
        ),
      )}
      {empty && it.status === "streaming" ? (
        <div className="flex items-center gap-2 text-[12px] text-muted-foreground"><Spinner size={12} className="text-violet" />Réflexion…</div>
      ) : null}
      {it.status === "error" ? (
        <div className="flex items-start gap-1.5 text-[12px] text-destructive">
          <CircleAlert size={13} strokeWidth={1.75} className="mt-[3px] shrink-0" />
          <span>{it.error ?? "Erreur"}</span>
        </div>
      ) : null}
      {it.status === "stopped" ? <div className="text-[11.5px] text-muted-foreground">Réponse interrompue.</div> : null}
      {it.status === "done" && it.ms != null ? (
        <div className="num font-mono text-[10.5px] text-muted-foreground">{(it.ms / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} s</div>
      ) : null}
    </div>
  );
}
