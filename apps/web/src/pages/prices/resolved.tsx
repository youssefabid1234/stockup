/** ResolvedPrice display: headline price + margin + explanation, and the candidates list (which applied, why not the others). */
import { Check, Minus } from "lucide-react";
import { Link } from "react-router-dom";
import type { ResolvedPrice } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtMoney, fmtPercent } from "@/lib/format";
import { Money, SECTION_LABEL, Skeleton } from "@/ui";
import { MarginCell, SourceLabel } from "./pickers";

/** "Règle « Gastro -8 % » (…)" → "Gastro -8 %" */
export function ruleNameOf(label: string): string | undefined {
  const m = label.match(/«\s*(.+?)\s*»/);
  return m?.[1];
}

export function ResolvedHeadline({ r, size = "lg" }: { r: ResolvedPrice; size?: "lg" | "md" }) {
  const applied = r.candidates.find((c) => c.applied);
  const delta = r.listPrice ? (r.price - r.listPrice) / r.listPrice : 0;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <div className={SECTION_LABEL}>Prix unitaire HT</div>
          <div className={cn("num font-semibold tabular-nums tracking-tight", size === "lg" ? "text-[30px] leading-[36px]" : "text-[22px] leading-7")}>
            {fmtMoney(r.price)}
          </div>
        </div>
        <Metric label="Catalogue" value={<Money value={r.listPrice} />} hint={Math.abs(delta) >= 0.0005 ? `${delta < 0 ? "−" : "+"}${fmtPercent(Math.abs(delta))}` : undefined} />
        <Metric label="Coût" value={<Money value={r.cost} />} />
        <Metric label="Marge" value={<MarginCell value={r.marginPct} />} hint={fmtMoney(r.price - r.cost)} />
        <Metric label="Source" value={<SourceLabel source={r.source} ruleName={applied ? ruleNameOf(applied.label) : undefined} />} />
      </div>
      <p className="text-[13px] leading-5 text-secondary-foreground">{r.explanation}</p>
    </div>
  );
}

export function Metric({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="min-w-0 pb-0.5">
      <div className={SECTION_LABEL}>{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1.5 text-[13.5px]">
        {value}
        {hint ? <span className="text-[11.5px] tabular-nums text-muted-foreground">{hint}</span> : null}
      </div>
    </div>
  );
}

/** Every price that could apply, in resolution order, the applied one highlighted. */
export function CandidatesList({ r, compact }: { r: ResolvedPrice; compact?: boolean }) {
  return (
    <ol className="flex flex-col">
      {r.candidates.map((c, i) => {
        const name = c.source === "rule" ? ruleNameOf(c.label) : undefined;
        const scope = c.source === "rule" ? c.label.replace(/^Règle « .+? » /, "").replace(/^\(|\)$/g, "") : undefined;
        return (
          <li
            key={`${c.source}-${c.ruleId ?? i}`}
            className={cn(
              "flex items-start gap-2.5 border-b border-border py-2 last:border-b-0",
              compact ? "px-0" : "px-1",
            )}
          >
            <span
              className={cn(
                "mt-0.5 grid size-4 shrink-0 place-items-center rounded-full",
                c.applied ? "bg-primary text-primary-foreground" : "border border-border text-muted-foreground",
              )}
            >
              {c.applied ? <Check size={10} strokeWidth={3} /> : <Minus size={9} strokeWidth={2.5} />}
            </span>
            <div className="min-w-0 flex-1">
              <div className={cn("flex items-baseline gap-2 text-[13px]", !c.applied && "text-secondary-foreground")}>
                <span className={cn("min-w-0 flex-1 truncate", c.applied && "font-medium")}>
                  {c.source === "rule" ? (
                    <>Règle « {c.ruleId ? <Link to={`/prices?tab=rules&rule=${c.ruleId}`} className="hover:underline">{name}</Link> : name} »</>
                  ) : c.label}
                </span>
                <span className={cn("num shrink-0 tabular-nums", c.applied ? "font-semibold" : "text-muted-foreground line-through decoration-muted-foreground/40")}>
                  {fmtMoney(c.price)}
                </span>
              </div>
              {scope ? <div className="truncate text-[11.5px] text-muted-foreground" title={scope}>{scope}</div> : null}
              <div className={cn("text-[11.5px]", c.applied ? "text-primary" : "text-muted-foreground")}>
                {c.applied ? "Appliqué" : c.reason ? `Non retenu : ${c.reason}` : "Non retenu"}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function ResolvedSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-3 w-3/4" />
      <Skeleton className="h-16 w-full" />
    </div>
  );
}
