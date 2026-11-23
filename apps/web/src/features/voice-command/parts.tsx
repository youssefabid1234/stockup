/** Small pieces shared by the HUD and the Voix page "Commande" mode: level meter, entity links, latency chips. */
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { TurnTimings } from "@kit/shared";
import { cn } from "@/lib/cn";
import { toolLinks, type EntityLink } from "@/features/assistant/tools";
import type { CommandRun } from "./engine";

export function LevelMeter({ level, n = 16, className }: { level: number; n?: number; className?: string }) {
  const lit = Math.round(level * n);
  return (
    <span className={cn("inline-flex h-3.5 items-end gap-[2px]", className)} aria-hidden>
      {Array.from({ length: n }).map((_, i) => (
        <span
          key={i}
          className={cn("w-[3px] rounded-[1px] transition-[height,background-color] duration-75", i < lit ? "bg-violet" : "bg-border")}
          style={{ height: `${30 + (i / (n - 1)) * 70}%` }}
        />
      ))}
    </span>
  );
}

const WRITE_TOOLS = /^(create|add|confirm|update|set|mark|cancel|delete|record|register)/;

/** Entities the command touched, most relevant first: the "navigate" target, then written entities, then the rest. Max 3. */
export function runLinks(r: CommandRun): EntityLink[] {
  const out: EntityLink[] = [];
  const push = (l: EntityLink) => { if (!out.some((x) => x.to === l.to)) out.push(l); };
  if (r.navigate) push({ to: r.navigate.path, label: r.navigate.label ?? "Ouvrir" });
  const done = r.tools.filter((t) => t.ok);
  for (const t of done.filter((t) => WRITE_TOOLS.test(t.name)).reverse()) toolLinks(t).slice(0, 1).forEach(push);
  for (const t of done.filter((t) => !WRITE_TOOLS.test(t.name) && t.name !== "search").reverse()) toolLinks(t).slice(0, 1).forEach(push);
  if (!out.length) for (const t of done) toolLinks(t).slice(0, 1).forEach(push);
  return out.slice(0, 3);
}

export function RunLinks({ r, onNavigate, className }: { r: CommandRun; onNavigate?: () => void; className?: string }) {
  const links = runLinks(r);
  if (!links.length) return null;
  return (
    <span className={cn("flex flex-wrap items-center gap-x-3 gap-y-1", className)}>
      {links.map((l, i) => (
        <Link
          key={l.to}
          to={l.to}
          onClick={onNavigate}
          className={cn(
            "inline-flex max-w-[220px] items-center gap-1 truncate text-[12px] underline-offset-2 hover:underline",
            i === 0 ? "font-medium text-violet" : "text-secondary-foreground",
          )}
        >
          <span className="truncate">{i === 0 ? `Ouvrir ${l.label}` : l.label}</span>
          <ArrowUpRight size={12} strokeWidth={1.75} className="shrink-0" />
        </Link>
      ))}
    </span>
  );
}

export const fmtMs = (ms: number) =>
  ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;

export type MetricKey = keyof TurnTimings | "perceivedMs";
export const COMMAND_METRICS: { key: MetricKey; label: string; title: string }[] = [
  { key: "sttMs", label: "STT", title: "Transcription de la commande" },
  { key: "llmFirstTokenMs", label: "LLM 1er", title: "Premier token du modèle (après les outils éventuels)" },
  { key: "llmTotalMs", label: "LLM", title: "Modèle, outils ERP compris" },
  { key: "ttsFirstByteMs", label: "TTS", title: "Premier octet de la réponse vocale" },
  { key: "totalMs", label: "Total", title: "Réception de la commande → réponse prête (serveur)" },
  { key: "perceivedMs", label: "Perçu", title: "Relâchement de la touche → réponse affichée / entendue (navigateur)" },
];

export const metricValue = (r: CommandRun, k: MetricKey) => (k === "perceivedMs" ? r.perceivedMs : r.timings?.[k]);

function tone(k: MetricKey, ms: number) {
  if (k !== "totalMs" && k !== "perceivedMs") return "text-secondary-foreground";
  return ms < 1500 ? "text-success" : ms < 3000 ? "text-warning" : "text-destructive";
}

export function MsChip({ k, label, ms, title }: { k: MetricKey; label: string; ms?: number; title?: string }) {
  return (
    <span title={title} className="inline-flex h-[18px] items-center gap-1 rounded-[3px] border border-border bg-card px-1.5 font-mono text-[10.5px]">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("num", ms == null ? "text-muted-foreground/60" : tone(k, ms))}>{ms == null ? "—" : fmtMs(ms)}</span>
    </span>
  );
}

export function RunChips({ r }: { r: CommandRun }) {
  const chips = COMMAND_METRICS.map((m) => ({ ...m, ms: metricValue(r, m.key) })).filter((m) => m.ms != null);
  if (!chips.length) return null;
  return (
    <span className="flex flex-wrap items-center gap-1">
      {chips.map((m) => <MsChip key={m.key} k={m.key} label={m.label} ms={m.ms} title={m.title} />)}
    </span>
  );
}
