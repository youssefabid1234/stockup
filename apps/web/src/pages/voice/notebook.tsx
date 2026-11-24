// Team 12 (Youssef) · Lucie's notebook: what she retains during the call, handwritten-like — notes appear, get crossed
// out or corrected (the old version stays visible), questions still to ask are circled with a « ? », the capital things
// are circled in red, links are drawn as arrows. Someone supervising the agent sees what she does at a glance.
// Also: after hanging up, a summary of the call goes to the client's ERP history (so the next call remembers it).
import { useEffect, useRef, useState } from "react";
import type { CallerReady } from "@kit/shared";
import type { VoiceTurn } from "@/features/assistant/useVoiceSession";

interface NoteItem {
  id: string;
  text: string;
  kind: string;
  important?: boolean;
  status: "active" | "struck";
  reason?: string;
  replacedBy?: string;
  at: number;
}
interface LinkItem { from: string; to: string; label: string }
type Op =
  | { op: "add"; text: string; kind: string; important?: boolean }
  | { op: "strike"; id: string; reason?: string }
  | { op: "edit"; id: string; text: string }
  | { op: "link"; from: string; to: string; label: string };

const KIND_MARK: Record<string, string> = {
  commande: "🛒", "préférence": "♥", info: "•", question: "?", "à faire": "☐", "réclamation": "⚠",
};
const INK = "#1f3a93";
const RED = "#c0392b";

function said(turns: VoiceTurn[]) {
  return turns.flatMap((t) => [
    ...(t.caller.text.trim() && !t.caller.silent ? [{ who: "client", text: t.caller.text }] : []),
    ...(t.agent.done && t.agent.text.trim() ? [{ who: "lucie", text: t.agent.text }] : []),
  ]);
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/ai${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function AgentNotebook({ caller, turns }: { caller?: CallerReady; turns: VoiceTurn[] }) {
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [links, setLinks] = useState<LinkItem[]>([]);
  const [writing, setWriting] = useState(false);
  const [saved, setSaved] = useState<string>();
  const done = turns.filter((t) => t.agent.done).length;
  const seen = useRef(0);
  const busy = useRef(false);
  const notesRef = useRef(notes);
  notesRef.current = notes;
  const counter = useRef(0);

  // After each finished reply: ask the notebook what changes.
  useEffect(() => {
    if (!caller || done === 0 || done === seen.current || busy.current) return;
    seen.current = done;
    busy.current = true;
    setWriting(true);
    postJson<{ ops: Op[] }>("/calls/notebook", {
      clientName: caller.name, turns: said(turns).slice(-8),
      notes: notesRef.current.map(({ id, text, kind, status }) => ({ id, text, kind, status })),
    }).then(({ ops }) => {
      setNotes((prev) => {
        let next = [...prev];
        for (const op of ops) {
          if (op.op === "add") next.push({ id: `n${++counter.current}`, text: op.text, kind: op.kind, important: op.important, status: "active", at: Date.now() });
          if (op.op === "strike") next = next.map((n) => (n.id === op.id ? { ...n, status: "struck", reason: op.reason } : n));
          if (op.op === "edit") {
            const id = `n${++counter.current}`;
            const old = next.find((n) => n.id === op.id);
            next = next.map((n) => (n.id === op.id ? { ...n, status: "struck", replacedBy: id, reason: "corrigé" } : n));
            next.push({ id, text: op.text, kind: old?.kind ?? "info", important: old?.important, status: "active", at: Date.now() });
          }
        }
        return next;
      });
      setLinks((prev) => [...prev, ...ops.filter((o): o is Extract<Op, { op: "link" }> => o.op === "link")]);
    }).catch(() => undefined).finally(() => { busy.current = false; setWriting(false); });
  }, [caller, done, turns]);

  // Hang up / new call: the summary goes to the client's history, and the notebook starts a fresh page.
  const last = useRef<{ caller?: CallerReady; turns: VoiceTurn[] }>({ turns: [] });
  useEffect(() => {
    const prev = last.current;
    const ended = prev.caller && (caller?.clientId !== prev.caller.clientId || (turns.length === 0 && prev.turns.length > 0));
    if (ended && prev.caller?.clientId && said(prev.turns).length >= 2) {
      postJson<{ saved: boolean; text?: string }>("/calls/summary", {
        clientId: prev.caller.clientId, clientName: prev.caller.name, turns: said(prev.turns),
      }).then((r) => setSaved(r.saved ? `Résumé ajouté à l'historique de ${prev.caller?.name} : ${r.text}` : undefined)).catch(() => undefined);
    }
    if (ended) { setNotes([]); setLinks([]); seen.current = 0; }
    last.current = { caller, turns };
  }, [caller, turns]);

  if (!caller && !saved) return null;
  const byId = Object.fromEntries(notes.map((n) => [n.id, n]));
  return (
    <section className="shrink-0 border-b border-border px-3 py-3">
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&display=swap');
        @keyframes nb-write { from { clip-path: inset(0 100% 0 0) } to { clip-path: inset(0 0 0 0) } }
        @keyframes nb-draw { from { stroke-dashoffset: 400 } to { stroke-dashoffset: 0 } }
        .nb-paper { background: #fffdf4; background-image: repeating-linear-gradient(transparent 0 25px, #c9d8ee 25px 26px),
          linear-gradient(90deg, transparent 26px, #f0b8b8 26px 27px, transparent 27px); font-family: Caveat, 'Segoe Print', 'Comic Sans MS', cursive; }
        .nb-line { animation: nb-write .7s ease-out both; }
        .nb-draw { stroke-dasharray: 400; animation: nb-draw .9s ease-out both; }`}</style>
      <div className="nb-paper relative overflow-hidden rounded-[6px] border border-[#e8dfc4] shadow-sm" style={{ color: INK }}>
        <div className="flex items-baseline justify-between pl-9 pr-3 pt-1 text-[22px] font-bold leading-[26px]">
          <span>Carnet de Lucie</span>
          <span className="text-[16px] font-medium opacity-70">{caller?.name ?? ""}</span>
        </div>
        <ul className="pb-2 pl-9 pr-3 text-[19px] leading-[26px]">
          {notes.length === 0 ? <li className="opacity-50">{caller ? "J'écoute…" : ""}</li> : null}
          {notes.map((n) => (
            <li key={n.id} className="nb-line relative" title={new Date(n.at).toLocaleTimeString("fr-FR")}>
              <span className="mr-1.5 inline-block w-4 text-center" style={{ color: n.kind === "réclamation" || n.kind === "question" ? RED : INK }}>
                {n.kind === "question" ? (
                  <svg width="20" height="20" viewBox="0 0 20 20" className="-mb-1 inline"><circle className="nb-draw" cx="10" cy="10" r="8" fill="none" stroke={RED} strokeWidth="1.6" /><text x="10" y="15" textAnchor="middle" fontSize="15" fill={RED}>?</text></svg>
                ) : (KIND_MARK[n.kind] ?? "•")}
              </span>
              <span className="relative inline-block">
                <span style={n.status === "struck" ? { opacity: 0.55 } : undefined}>{n.text}</span>
                {n.status === "struck" ? (
                  <svg className="pointer-events-none absolute inset-0 h-full w-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 10">
                    <path className="nb-draw" d="M0 6 Q 25 3, 50 6 T 100 5" fill="none" stroke={RED} strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
                  </svg>
                ) : null}
                {n.important && n.status === "active" ? (
                  <svg className="pointer-events-none absolute -inset-x-2 -inset-y-1 h-[calc(100%+8px)] w-[calc(100%+16px)] overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 40">
                    <path className="nb-draw" d="M6 22 C 4 6, 92 2, 96 18 C 99 34, 10 40, 4 24 C 3 18, 12 10, 22 9" fill="none" stroke={RED} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                  </svg>
                ) : null}
              </span>
              {n.status === "struck" ? (
                <span className="ml-2 text-[15px]" style={{ color: RED }}>
                  {n.replacedBy ? "→ corrigé" : `✗ ${n.reason ?? "barré"}`}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
        {links.length ? (
          <div className="border-t border-dashed border-[#c9d8ee] px-3 pb-2 pl-9 text-[17px] leading-[24px]">
            {links.map((l, i) => byId[l.from] && byId[l.to] ? (
              <div key={i} className="nb-line flex items-center gap-1">
                <span className="truncate">{byId[l.from].text}</span>
                <svg width="46" height="16" viewBox="0 0 46 16" className="shrink-0"><path className="nb-draw" d="M2 10 C 14 2, 30 2, 42 8 M36 4 L42 8 L35 12" fill="none" stroke={INK} strokeWidth="1.4" /></svg>
                <span className="truncate">{byId[l.to].text}</span>
                {l.label ? <span className="ml-1 shrink-0 text-[14px] opacity-70">({l.label})</span> : null}
              </div>
            ) : null)}
          </div>
        ) : null}
        <div className="flex items-center justify-between px-3 pb-1 pl-9 text-[14px] opacity-60">
          <span>{writing ? "✎ Lucie écrit…" : `${notes.filter((n) => n.status === "active").length} notes · ${notes.filter((n) => n.status === "struck").length} barrées`}</span>
          <span>🛒 commande · ♥ préférence · ? à demander</span>
        </div>
      </div>
      {saved ? <p className="mt-2 text-[11.5px] text-muted-foreground">✓ {saved}</p> : null}
    </section>
  );
}
