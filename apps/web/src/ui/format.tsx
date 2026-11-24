/** Inline formatters. Always use these for money/qty/dates in JSX (tabular, French). */
import type { Unit } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtDate, fmtDateLong, fmtDateTime, fmtMoney, fmtQty, fmtRelative, parseDate } from "@/lib/format";

/** <Money value={1234.5} /> → 1 234,50 €. `compact` drops cents. `zeroMuted` greys 0. `tone` colors it. */
export function Money({ value, compact, zeroMuted, tone, className }: {
  value: number | null | undefined; compact?: boolean; zeroMuted?: boolean; tone?: "destructive" | "warning" | "success" | "muted"; className?: string;
}) {
  const muted = tone === "muted" || (zeroMuted && (!value || Math.abs(value) < 0.005));
  return (
    <span className={cn(
      "num whitespace-nowrap",
      muted && "text-muted-foreground",
      !muted && tone === "destructive" && "text-destructive",
      !muted && tone === "warning" && "text-warning",
      !muted && tone === "success" && "text-success",
      className,
    )}>
      {fmtMoney(value, { compact })}
    </span>
  );
}

/** <Qty value={12.5} unit="kg" /> → 12,5 kg (unit muted) */
export function Qty({ value, unit, tone, className }: { value: number | null | undefined; unit?: Unit | string; tone?: "destructive" | "warning"; className?: string }) {
  const [n, ...u] = fmtQty(value, unit).split(" ");
  return (
    <span className={cn("num whitespace-nowrap", tone === "destructive" && "text-destructive", tone === "warning" && "text-warning", className)}>
      {n}
      {u.length ? <span className="ml-0.5 text-muted-foreground">{u.join(" ")}</span> : null}
    </span>
  );
}

/**
 * <DateLabel date="2026-11-23" /> → lun. 23 nov.
 * format: "short" (default) | "long" | "datetime" | "relative" ("il y a 3 min"). Full date in the tooltip.
 */
export function DateLabel({ date, format = "short", className }: { date?: string | null; format?: "short" | "long" | "datetime" | "relative"; className?: string }) {
  if (!date) return <span className={cn("text-muted-foreground", className)}>—</span>;
  const txt = format === "long" ? fmtDateLong(date) : format === "datetime" ? fmtDateTime(date) : format === "relative" ? fmtRelative(date) : fmtDate(date);
  return (
    <time dateTime={date} title={parseDate(date).toLocaleString("fr-FR")} className={cn("num whitespace-nowrap", className)}>
      {txt}
    </time>
  );
}

/** Ids, SKUs, document numbers: <Mono>CMD-2026-000123</Mono> */
export function Mono({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[12px] text-secondary-foreground", className)}>{children}</span>;
}
