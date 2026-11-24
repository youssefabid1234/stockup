import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

/** 10.5px uppercase label. Use for every group heading. */
export const SECTION_LABEL = "text-[10.5px] font-semibold uppercase tracking-[.08em] text-muted-foreground";

/** <Section title="Contacts" actions={<Button size="sm">…</Button>}>…</Section> */
export function Section({ title, count, actions, children, className, bodyClassName }: {
  title: ReactNode; count?: number; actions?: ReactNode; children: ReactNode; className?: string; bodyClassName?: string;
}) {
  return (
    <section className={cn("min-w-0", className)}>
      <div className="mb-2 flex h-6 items-center gap-2">
        <h2 className={SECTION_LABEL}>{title}</h2>
        {count !== undefined ? <span className="num text-[11px] text-muted-foreground/80">{count}</span> : null}
        <div className="ml-auto flex items-center gap-1.5">{actions}</div>
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

/** Hairline box for grouped content (6px radius max). */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("rounded-[6px] border border-border bg-card", className)}>{children}</div>;
}

export interface KV { label: ReactNode; value: ReactNode; mono?: boolean }
/** <KeyValue items={[{label:"Zone", value:"Paris Ouest"}]} /> — label column 140px, hairline-free, dense. */
export function KeyValue({ items, className, labelWidth = 140 }: { items: KV[]; className?: string; labelWidth?: number }) {
  return (
    <dl className={cn("grid gap-x-4 gap-y-1.5 text-[13px]", className)} style={{ gridTemplateColumns: `${labelWidth}px minmax(0,1fr)` }}>
      {items.map((it, i) => (
        <div key={i} className="contents">
          <dt className="py-0.5 text-muted-foreground">{it.label}</dt>
          <dd className={cn("min-w-0 py-0.5 text-foreground", it.mono && "font-mono text-[12px]")}>{it.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/** KPI tile: <Stat label="CA du jour" value={<Money value={x} />} hint="+12 % vs hier" tone="success" /> */
export function Stat({ label, value, hint, icon: Icon, tone, className, onClick }: {
  label: ReactNode; value: ReactNode; hint?: ReactNode; icon?: LucideIcon; tone?: "success" | "warning" | "destructive" | "violet" | "info";
  className?: string; onClick?: () => void;
}) {
  const toneCls = tone ? { success: "text-success", warning: "text-warning", destructive: "text-destructive", violet: "text-violet", info: "text-info" }[tone] : "";
  return (
    <div
      onClick={onClick}
      className={cn("flex min-w-0 flex-col gap-1 px-4 py-3", onClick && "cursor-pointer transition-colors hover:bg-muted/50", className)}
    >
      <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
        {Icon ? <Icon size={13} strokeWidth={1.75} /> : null}
        {label}
      </div>
      <div className={cn("num text-[20px] font-semibold leading-7 tracking-[-0.01em]", toneCls)}>{value}</div>
      {hint ? <div className="text-[12px] text-muted-foreground">{hint}</div> : null}
    </div>
  );
}
/** Row of Stats separated by hairlines: <StatGrid><Stat…/><Stat…/></StatGrid> */
export function StatGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-2 divide-x divide-border border-b border-border md:grid-cols-4", className)}>{children}</div>;
}

/** <EmptyState icon={Users} title="Aucun client" description="…" action={<Button>…</Button>} /> */
export function EmptyState({ icon: Icon, title, description, action, className, compact }: {
  icon?: LucideIcon; title: ReactNode; description?: ReactNode; action?: ReactNode; className?: string; compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "gap-1.5 py-6" : "gap-2 py-16", className)}>
      {Icon ? (
        <div className="mb-1 flex h-8 w-8 items-center justify-center rounded-[6px] border border-border bg-muted text-muted-foreground">
          <Icon size={15} strokeWidth={1.75} />
        </div>
      ) : null}
      <div className="text-[13px] font-medium text-foreground">{title}</div>
      {description ? <div className="max-w-[360px] text-[12.5px] text-muted-foreground">{description}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

/** Shimmer placeholder: <Skeleton className="h-3 w-24" /> */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-[3px] bg-muted", className)} />;
}

/** Error block for a failed query (toasts already fired): <ErrorState onRetry={refetch} /> */
export function ErrorState({ message = "Impossible de charger les données.", onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <EmptyState
      title="Erreur de chargement"
      description={message}
      action={onRetry ? <button type="button" onClick={onRetry} className="text-[12.5px] font-medium text-primary hover:underline">Réessayer</button> : undefined}
    />
  );
}
