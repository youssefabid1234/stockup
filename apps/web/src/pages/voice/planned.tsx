// Team 12 (Youssef) · Lucie's planned outbound calls (who, why, when), started by themselves when their time comes
// (page open) or at once with « Appeler maintenant »; and the voice message she leaves when nobody answers.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ExternalLink, Mic, PhoneOutgoing } from "lucide-react";
import type { OutboundAttempt } from "@kit/shared";
import { api } from "@/lib/api";
import { Button, Dot, SECTION_LABEL } from "@/ui";

export interface PlannedCall {
  id: string;
  clientId: string;
  clientName: string;
  contact?: string | null;
  reasons: string[];
  whyTime: string;
  at: number; // epoch seconds
  status: "planned" | OutboundAttempt["status"];
}

interface VoiceMail {
  attemptId: string;
  clientId: string;
  clientName: string;
  contact?: string | null;
  phone?: string | null;
  text: string;
  audioUrl: string;
  sentAt: number;
}

const STATUS: Record<PlannedCall["status"], string> = {
  planned: "Planifié",
  ringing: "Sonne…",
  answered: "En ligne",
  missed: "Sans réponse · message laissé",
  completed: "Appel terminé",
  cancelled: "Annulé",
};

const hour = (epoch: number) => new Date(epoch * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

export function PlannedCalls({ ready, busy, pending }: { ready: boolean; busy: boolean; pending: boolean }) {
  const queryClient = useQueryClient();
  const enabled = useQuery({ queryKey: ["outbound-demo", "status"], queryFn: api.outboundDemo.status, retry: false, staleTime: Infinity })
    .data?.enabled === true;
  const plan = useQuery({ queryKey: ["outbound-plan"], queryFn: api.outboundPlan.list, enabled, refetchInterval: 2000 });
  const fired = useRef(new Set<string>());
  const [tick, setTick] = useState(0);
  useEffect(() => { const t = window.setInterval(() => setTick((n) => n + 1), 1000); return () => window.clearInterval(t); }, []);
  const call = useMutation({
    mutationFn: api.outboundPlan.call,
    onSuccess(attempt) {
      queryClient.setQueryData<OutboundAttempt[]>(["outbound-demo", "attempts"], (previous = []) => [
        attempt, ...previous.filter((a) => a.id !== attempt.id),
      ]);
      void queryClient.invalidateQueries({ queryKey: ["outbound-plan"] });
    },
  });
  const calls = plan.data ?? [];
  const lineBusy = calls.some((c) => c.status === "ringing" || c.status === "answered");
  const canCall = ready && !busy && !pending && !lineBusy && !call.isPending;

  // Lucie keeps her schedule: a planned call whose time has come starts by itself (only while this page is open).
  useEffect(() => {
    void tick;
    if (!canCall) return;
    const due = calls.find((c) => c.status === "planned" && c.at * 1000 <= Date.now() && !fired.current.has(c.id));
    if (due) {
      fired.current.add(due.id);
      call.mutate(due.id);
    }
  }, [tick, canCall, calls, call]);

  if (!enabled) return null;
  return (
    <section className="shrink-0 space-y-2 border-b border-border px-4 py-3">
      <div className="flex items-center justify-between">
        <h2 className={SECTION_LABEL + " flex items-center gap-2"}><CalendarClock size={14} /> Appels planifiés par Lucie</h2>
        <button className="text-[11px] text-muted-foreground underline-offset-2 hover:underline"
          onClick={() => void api.outboundPlan.refresh().then(() => queryClient.invalidateQueries({ queryKey: ["outbound-plan"] }))}>
          Replanifier
        </button>
      </div>
      {plan.isPending ? <p className="text-[12px] text-muted-foreground">Lucie prépare son planning…</p> : null}
      {!plan.isPending && !calls.length ? <p className="text-[12px] text-muted-foreground">Aucun client à appeler pour l'instant.</p> : null}
      <ol className="space-y-2">
        {calls.map((c) => (
          <li key={c.id} className={"rounded-[6px] border p-2.5 text-[12px] " + (c.status === "ringing" ? "border-violet/50 bg-violet/[.06]" : "border-border bg-card")}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{c.status === "ringing" ? <Dot tone="violet" pulse /> : null} {hour(c.at)} · {c.clientName}</span>
              <span className="shrink-0 text-[11px] text-muted-foreground">{STATUS[c.status]}</span>
            </div>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11.5px] text-muted-foreground">
              {c.reasons.map((r) => <li key={r}>{r}</li>)}
            </ul>
            <p className="mt-1 text-[11.5px] italic text-muted-foreground">{c.whyTime}</p>
            {c.status === "planned" ? (
              <Button className="mt-2 w-full" icon={PhoneOutgoing} disabled={!canCall}
                onClick={() => { fired.current.add(c.id); call.mutate(c.id); }}>Appeler maintenant</Button>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The conversation with the client after an unanswered call: Lucie's voice message (her voice + what she said). */
export function VoiceMessage({ attempt }: { attempt: OutboundAttempt }) {
  const message = useQuery({
    queryKey: ["voicemail", attempt.id],
    queryFn: async (): Promise<VoiceMail> => {
      const res = await fetch(`/ai/outbound/voicemail/${encodeURIComponent(attempt.id)}`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: Infinity, retry: 2,
  });
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { if (message.data) box.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [message.data]);
  const m = message.data;
  return (
    <div ref={box} className="overflow-hidden rounded-[8px] border border-border">
      <div className="flex items-center justify-between gap-2 bg-[#075e54] px-3 py-2 text-white">
        <div className="min-w-0">
          <p className="truncate text-[12.5px] font-medium">{attempt.clientName}</p>
          <p className="truncate text-[11px] opacity-80">{m?.contact ?? "Contact"}{m?.phone ? ` · ${m.phone}` : ""}</p>
        </div>
        <Link to={`/clients/${attempt.clientId}`} className="shrink-0 opacity-80 hover:opacity-100" title="Fiche client"><ExternalLink size={14} /></Link>
      </div>
      <div className="space-y-2 bg-[#ece5dd] p-2.5 dark:bg-[#0b141a]">
        <p className="mx-auto w-fit rounded-full bg-white/70 px-2 py-0.5 text-[10.5px] text-muted-foreground dark:bg-white/10">
          Appel manqué · Lucie laisse un message
        </p>
        {message.isPending ? <p className="text-[12px] text-muted-foreground">Lucie enregistre son message…</p> : null}
        {message.isError ? (
          <p className="text-[12px] text-muted-foreground">{attempt.sms ?? "Message indisponible."}</p>
        ) : null}
        {m ? (
          <div className="ml-auto max-w-[95%] rounded-[8px] rounded-tr-none bg-[#dcf8c6] p-2 text-[12px] text-[#111] shadow-sm dark:bg-[#005c4b] dark:text-white">
            <p className="mb-1 flex items-center gap-1.5 font-medium"><Mic size={13} /> Message vocal</p>
            <audio controls src={m.audioUrl} className="h-8 w-full" />
            <p className="mt-1.5 leading-relaxed">{m.text}</p>
            <p className="mt-1 text-right text-[10.5px] opacity-60">Lucie · {hour(m.sentAt)} ✓✓</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
