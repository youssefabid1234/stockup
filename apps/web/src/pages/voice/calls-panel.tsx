// Team 12 (Youssef) · the Standard's right column when no call is on: ONE call at a time, the most urgent.
//   ringing  → big pulsing green button on the call itself to answer, red to decline (+ the same as a banner on top)
//   missed   → the client's conversation with Lucie's voice message (closable)
//   next     → the next planned call: time, countdown, « Appeler maintenant », « Pourquoi ? » folded
// Planned calls still start by themselves when their time comes (page open, line free). Ring: /sounds/ring.mp3.
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ChevronDown, Info, Phone, PhoneOff, PhoneOutgoing, RefreshCw, X } from "lucide-react";
import type { OutboundAttempt } from "@kit/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { StockUpMark } from "@/app/StockUpLogo";
import { VoiceMessage, type PlannedCall } from "./planned";

const hour = (epoch: number) => new Date(epoch * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const initials = (name: string) => name.replace(/^(La|Le|Les|Au|Aux|L')\s+/i, "").split(/[\s-]+/).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
function inMinutes(at: number, now: number) {
  const m = Math.round((at * 1000 - now) / 60000);
  return m <= 0 ? "maintenant" : m === 1 ? "dans 1 min" : m < 60 ? `dans ${m} min` : `dans ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

export function CallsPanel({ ready, busy, pending, onAnswer }: {
  ready: boolean; busy: boolean; pending: boolean; onAnswer: (attemptId: string) => void;
}) {
  const qc = useQueryClient();
  const enabled = useQuery({ queryKey: ["outbound-demo", "status"], queryFn: api.outboundDemo.status, retry: false, staleTime: Infinity }).data?.enabled === true;
  const plan = useQuery({ queryKey: ["outbound-plan"], queryFn: api.outboundPlan.list, enabled, refetchInterval: 1500 });
  const attempts = useQuery({ queryKey: ["outbound-demo", "attempts"], queryFn: api.outboundDemo.attempts, enabled, refetchInterval: 800 });
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  const [why, setWhy] = useState(false);
  const [others, setOthers] = useState(false);
  const [closed, setClosed] = useState<string[]>([]);
  const fired = useRef(new Set<string>());
  const refresh = () => void qc.invalidateQueries({ queryKey: ["outbound-plan"] }).then(() => qc.invalidateQueries({ queryKey: ["outbound-demo"] }));
  const call = useMutation({ mutationFn: api.outboundPlan.call, onSettled: refresh });
  const decline = useMutation({ mutationFn: api.outboundPlan.decline, onSettled: refresh });
  const dismiss = useMutation({ mutationFn: api.outboundDemo.dismiss, onSettled: refresh });

  const calls = useMemo(() => plan.data ?? [], [plan.data]);
  const latest = attempts.data?.[0];
  const ringing = latest?.status === "ringing" ? latest : undefined;
  const lost = latest?.status === "answered" && !busy && !pending ? latest : undefined;
  const missed = latest?.status === "missed" && !closed.includes(latest.id) && now / 1000 - latest.startedAt < 15 * 60 ? latest : undefined;
  const next = calls.find((c) => c.status === "planned");
  const later = calls.filter((c) => c.status === "planned" && c !== next);
  const lineBusy = !!ringing || latest?.status === "answered";
  const canCall = ready && !busy && !pending && !lineBusy && !call.isPending;

  // Lucie keeps her schedule: a due call starts by itself (page open, line free).
  useEffect(() => {
    if (!canCall) return;
    const due = calls.find((c) => c.status === "planned" && c.at * 1000 <= now && !fired.current.has(c.id));
    if (due) { fired.current.add(due.id); call.mutate(due.id); }
  }, [now, canCall, calls, call]);

  // The ring (the team's own sound), unlocked at the first click on the page.
  const ring = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    ring.current = new Audio("/sounds/ring.mp3");
    ring.current.loop = true;
    const unlock = () => { const a = ring.current; if (a) { a.muted = true; void a.play().then(() => { a.pause(); a.currentTime = 0; a.muted = false; }).catch(() => undefined); } };
    window.addEventListener("pointerdown", unlock, { once: true });
    return () => { window.removeEventListener("pointerdown", unlock); ring.current?.pause(); };
  }, []);
  useEffect(() => {
    const a = ring.current;
    if (!a) return;
    if (ringing && !pending) void a.play().catch(() => undefined);
    else { a.pause(); a.currentTime = 0; }
  }, [ringing, pending]);

  if (!enabled) return null;
  const answer = (a: OutboundAttempt) => { ring.current?.pause(); onAnswer(a.id); };
  const ringingPlan = ringing ? calls.find((c) => c.id === ringing.id) : undefined;

  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="flex items-center gap-2 px-1">
        <StockUpMark className="h-5 w-5" />
        <span className="text-[12px] font-semibold uppercase tracking-wide text-[#0F1E45] dark:text-white">Appels de Lucie</span>
        <button onClick={() => void api.outboundPlan.refresh().then(refresh)} title="Replanifier"
          className="ml-auto rounded-full p-1.5 text-muted-foreground transition hover:bg-[#1F6BFF]/10 hover:text-[#1F6BFF]"><RefreshCw size={14} /></button>
      </div>

      {ringing ? (
        <>
          <RingingCard attempt={ringing} contact={ringingPlan?.contact} disabled={!ready || busy || pending}
            onAnswer={() => answer(ringing)} onDecline={() => decline.mutate(ringing.id)} pending={pending} />
          {/* the same, where the eyes are: a banner on top of the page */}
          <div className="fixed left-1/2 top-3 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full bg-[#0F1E45] py-1.5 pl-4 pr-1.5 text-white shadow-2xl ring-4 ring-[#22c55e]/30">
            <span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#22c55e]" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#22c55e]" /></span>
            <span className="text-[13px]">Lucie appelle <b>{ringing.clientName}</b></span>
            <button onClick={() => answer(ringing)} disabled={!ready || busy || pending}
              className="flex items-center gap-1.5 rounded-full bg-[#22c55e] px-3 py-1.5 text-[12.5px] font-semibold transition hover:scale-105 hover:bg-[#16a34a] disabled:opacity-50"><Phone size={14} /> Décrocher</button>
            <button onClick={() => decline.mutate(ringing.id)} className="rounded-full bg-[#ef4444] p-1.5 transition hover:scale-105 hover:bg-[#dc2626]" title="Refuser"><PhoneOff size={14} /></button>
          </div>
        </>
      ) : lost ? (
        <div className="rounded-2xl border border-border bg-card p-4 text-center shadow-sm">
          <p className="text-[13px]">Appel en cours avec <b>{lost.clientName}</b> (session perdue)</p>
          <button onClick={() => dismiss.mutate(lost.id)} className="mt-3 inline-flex items-center gap-2 rounded-full bg-[#ef4444] px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-[#dc2626]">
            <PhoneOff size={15} /> Raccrocher</button>
        </div>
      ) : null}

      {missed && !ringing ? (
        <div className="relative">
          <button onClick={() => setClosed((c) => [...c, missed.id])} title="Fermer"
            className="absolute right-2 top-2 z-10 rounded-full bg-black/20 p-1 text-white transition hover:bg-black/40"><X size={12} /></button>
          <VoiceMessage attempt={missed} />
        </div>
      ) : null}

      {next && !ringing ? (
        <div className="overflow-hidden rounded-2xl border border-[#1F6BFF]/20 bg-card shadow-sm transition hover:shadow-md">
          <div className="flex items-center gap-3 bg-gradient-to-r from-[#0F1E45] to-[#1F6BFF] px-4 py-3 text-white">
            <CalendarClock size={18} className="opacity-90" />
            <div className="flex-1">
              <div className="text-[11px] uppercase tracking-wide opacity-80">Prochain appel</div>
              <div className="text-[22px] font-bold leading-6 tabular-nums">{hour(next.at)}</div>
            </div>
            <span className="rounded-full bg-white/15 px-2.5 py-1 text-[12px] font-medium">{inMinutes(next.at, now)}</span>
          </div>
          <div className="flex items-center gap-3 px-4 pt-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#1F6BFF]/10 text-[15px] font-bold text-[#1F6BFF]">{initials(next.clientName)}</div>
            <div className="min-w-0">
              <div className="truncate text-[15px] font-semibold">{next.clientName}</div>
              <div className="truncate text-[12.5px] text-muted-foreground">{next.contact ?? "Contact principal"}</div>
            </div>
          </div>
          <div className="flex gap-2 p-4">
            <button disabled={!canCall} onClick={() => { fired.current.add(next.id); call.mutate(next.id); }}
              className="flex flex-1 items-center justify-center gap-2 rounded-full bg-[#1F6BFF] py-2.5 text-[13.5px] font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-[#1857d6] hover:shadow-md disabled:translate-y-0 disabled:opacity-40">
              <PhoneOutgoing size={16} /> Appeler maintenant
            </button>
            <button onClick={() => setWhy((w) => !w)} aria-expanded={why} title="Pourquoi Lucie l'appelle"
              className={cn("flex items-center gap-1 rounded-full border px-3 text-[12.5px] font-medium transition", why ? "border-[#1F6BFF] bg-[#1F6BFF]/10 text-[#1F6BFF]" : "border-border hover:border-[#1F6BFF]/50 hover:text-[#1F6BFF]")}>
              <Info size={14} /> Pourquoi ?
            </button>
          </div>
          {why ? (
            <div className="mx-4 mb-4 space-y-1.5 rounded-xl bg-[#1F6BFF]/[.06] p-3 text-[12.5px]">
              {next.reasons.map((r) => <p key={r} className="flex gap-2"><span className="text-[#1F6BFF]">●</span>{r}</p>)}
              <p className="flex gap-2 italic text-muted-foreground"><span className="text-[#1F6BFF]">◷</span>{next.whyTime}</p>
            </div>
          ) : null}
        </div>
      ) : null}

      {!next && !ringing && !missed ? (
        <p className="rounded-2xl border border-dashed border-border p-4 text-center text-[12.5px] text-muted-foreground">
          {plan.isPending ? "Lucie prépare ses appels…" : "Aucun appel prévu. « ⟳ » pour replanifier."}
        </p>
      ) : null}

      {later.length && !ringing ? (
        <div>
          <button onClick={() => setOthers((o) => !o)} className="flex w-full items-center gap-1 px-1 text-[12px] text-muted-foreground transition hover:text-foreground">
            <ChevronDown size={14} className={cn("transition", others && "rotate-180")} /> {later.length} autre{later.length > 1 ? "s" : ""} appel{later.length > 1 ? "s" : ""} prévu{later.length > 1 ? "s" : ""}
          </button>
          {others ? (
            <ul className="mt-1 space-y-1">
              {later.map((c: PlannedCall) => (
                <li key={c.id} className="flex items-center gap-2 rounded-lg px-2 py-1 text-[12.5px] hover:bg-muted">
                  <span className="w-10 tabular-nums text-muted-foreground">{hour(c.at)}</span>
                  <span className="min-w-0 flex-1 truncate">{c.clientName}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function RingingCard({ attempt, contact, disabled, pending, onAnswer, onDecline }: {
  attempt: OutboundAttempt; contact?: string | null; disabled: boolean; pending: boolean; onAnswer: () => void; onDecline: () => void;
}) {
  return (
    <div className="overflow-hidden rounded-2xl bg-gradient-to-b from-[#0F1E45] to-[#163a8a] p-5 text-center text-white shadow-lg">
      <div className="text-[11px] uppercase tracking-[0.15em] opacity-70">Appel sortant · Lucie</div>
      <div className="mx-auto mt-4 flex h-20 w-20 items-center justify-center rounded-full bg-white/10 text-[26px] font-bold">{initials(attempt.clientName)}</div>
      <div className="mt-3 text-[17px] font-semibold">{attempt.clientName}</div>
      <div className="text-[12.5px] opacity-75">{contact ?? ""}{contact ? " · " : ""}{attempt.offer.productName.split(" (")[0]}</div>
      <div className="mt-6 flex items-center justify-center gap-10">
        <div className="flex flex-col items-center gap-1.5">
          <button onClick={onDecline} title="Refuser" className="flex h-14 w-14 items-center justify-center rounded-full bg-[#ef4444] shadow-lg transition hover:scale-110 hover:bg-[#dc2626]">
            <PhoneOff size={24} />
          </button>
          <span className="text-[11.5px] opacity-80">Refuser</span>
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <button onClick={onAnswer} disabled={disabled} title="Décrocher" className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[#22c55e] shadow-lg transition hover:scale-110 hover:bg-[#16a34a] disabled:opacity-50">
            <span className="absolute inset-0 animate-ping rounded-full bg-[#22c55e]/60" />
            <Phone size={24} className="relative animate-[wiggle_0.6s_ease-in-out_infinite]" />
          </button>
          <span className="text-[11.5px] font-semibold">{pending ? "Connexion…" : "Décrocher"}</span>
        </div>
      </div>
      <style>{"@keyframes wiggle { 0%,100% { transform: rotate(-12deg) } 50% { transform: rotate(12deg) } }"}</style>
    </div>
  );
}
