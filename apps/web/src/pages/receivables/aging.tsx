/** Aged-balance helpers: bucket definitions (success → warning → destructive) and hand-drawn bars. */
import type { AgingBuckets, ReceivableRow } from "@kit/shared";
import { fmtMoney, fmtPercent } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Money, type Tone } from "@/ui";

export type BucketId = keyof AgingBuckets;

export const BUCKETS: { id: BucketId; label: string; short: string; bar: string; dot: string }[] = [
  { id: "current", label: "Non échu", short: "Non échu", bar: "bg-success", dot: "bg-success" },
  { id: "d1_30", label: "1–30 j", short: "1–30", bar: "bg-warning/55", dot: "bg-warning/55" },
  { id: "d31_60", label: "31–60 j", short: "31–60", bar: "bg-warning", dot: "bg-warning" },
  { id: "d61_90", label: "61–90 j", short: "61–90", bar: "bg-destructive/65", dot: "bg-destructive/65" },
  { id: "d90plus", label: "+90 j", short: "+90", bar: "bg-destructive", dot: "bg-destructive" },
];
export const isBucket = (s: string): s is BucketId => BUCKETS.some((b) => b.id === s);

const sum = (b: AgingBuckets) => b.current + b.d1_30 + b.d31_60 + b.d61_90 + b.d90plus;

/**
 * Big stacked bar of the whole portfolio, with a clickable legend (amount + share) under it.
 * Clicking a segment or legend item toggles the bucket filter.
 */
export function AgingStrip({ buckets, active, onSelect }: {
  buckets: AgingBuckets; active: BucketId | ""; onSelect: (b: BucketId | "") => void;
}) {
  const total = sum(buckets);
  return (
    <div className="flex min-w-0 flex-col gap-2.5 px-5 py-3">
      <div className="flex items-baseline gap-2 text-[12px] text-muted-foreground">
        Balance âgée
        {active ? (
          <button type="button" onClick={() => onSelect("")} className="text-[11.5px] text-primary hover:underline">
            Toutes les tranches
          </button>
        ) : <span className="text-[11.5px] text-muted-foreground/70">cliquer une tranche pour filtrer</span>}
      </div>
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-[3px] bg-muted" role="group" aria-label="Balance âgée">
        {total > 0
          ? BUCKETS.map((b) => {
              const v = buckets[b.id];
              if (v <= 0) return null;
              return (
                <button
                  key={b.id}
                  type="button"
                  title={`${b.label} · ${fmtMoney(v)} · ${fmtPercent(v / total)}`}
                  aria-pressed={active === b.id}
                  onClick={() => onSelect(active === b.id ? "" : b.id)}
                  style={{ flexGrow: v, flexBasis: 0, minWidth: 3 }}
                  className={cn(
                    "h-full transition-opacity hover:opacity-80",
                    b.bar,
                    active && active !== b.id && "opacity-25",
                  )}
                />
              );
            })
          : null}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1.5">
        {BUCKETS.map((b) => {
          const v = buckets[b.id];
          return (
            <button
              key={b.id}
              type="button"
              aria-pressed={active === b.id}
              onClick={() => onSelect(active === b.id ? "" : b.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-[3px] text-left text-[12px] transition-opacity",
                active && active !== b.id && "opacity-45",
                active === b.id && "font-medium",
                "hover:opacity-100",
              )}
            >
              <span className={cn("h-2 w-2 shrink-0 rounded-[2px]", b.dot)} />
              <span className="text-muted-foreground">{b.label}</span>
              <Money value={v} compact zeroMuted className="text-foreground" />
              {total > 0 && v > 0 ? <span className="num text-[11px] text-muted-foreground">{fmtPercent(v / total)}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Mini per-client stacked bar (shares of the client's own outstanding). */
export function MiniAging({ buckets, className }: { buckets: AgingBuckets; className?: string }) {
  const total = sum(buckets);
  const tip = BUCKETS.filter((b) => buckets[b.id] > 0).map((b) => `${b.label} : ${fmtMoney(buckets[b.id])}`).join("\n");
  return (
    <div title={tip || "Rien à encaisser"} className={cn("flex h-1.5 w-full gap-px overflow-hidden rounded-[2px] bg-muted", className)}>
      {total > 0
        ? BUCKETS.map((b) => buckets[b.id] > 0 ? <span key={b.id} className={b.bar} style={{ flexGrow: buckets[b.id], flexBasis: 0, minWidth: 2 }} /> : null)
        : null}
    </div>
  );
}

/** Credit use: tone for a ratio outstanding / limit. */
export const creditTone = (ratio: number): Tone => (ratio > 1 ? "destructive" : ratio > 0.8 ? "warning" : "success");
const BAR_TONE: Record<string, string> = { success: "bg-foreground/35", warning: "bg-warning", destructive: "bg-destructive" };

export function CreditUse({ row, className }: { row: Pick<ReceivableRow, "creditLimit" | "outstanding">; className?: string }) {
  if (!row.creditLimit) return <span className="text-muted-foreground/60">Sans plafond</span>;
  const ratio = row.outstanding / row.creditLimit;
  const tone = creditTone(ratio);
  return (
    <span className={cn("flex min-w-0 items-center gap-2", className)}>
      <span className="relative h-1.5 min-w-0 flex-1 overflow-hidden rounded-[2px] bg-muted">
        <span className={cn("absolute inset-y-0 left-0", BAR_TONE[tone])} style={{ width: `${Math.min(100, ratio * 100)}%` }} />
      </span>
      <span className={cn("num w-10 shrink-0 text-right text-[12px]", tone === "destructive" ? "text-destructive" : tone === "warning" ? "text-warning" : "text-muted-foreground")}>
        {fmtPercent(ratio)}
      </span>
    </span>
  );
}

export const RISK: Record<ReceivableRow["risk"], { label: string; tone: Tone; rank: number }> = {
  ok: { label: "OK", tone: "success", rank: 0 },
  watch: { label: "À surveiller", tone: "warning", rank: 1 },
  high: { label: "Élevé", tone: "destructive", rank: 2 },
};
