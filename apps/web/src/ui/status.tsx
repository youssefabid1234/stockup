/**
 * Status = 6px dot + word. Every domain status has ONE entry in STATUS below (label + tone).
 * To add a status: add the value to the right map. To add a kind: add a map + key in STATUS.
 *   <StatusDot kind="order" value={order.status} />
 *   <StatusDot tone="warning" label="Stock bas" />
 *   <Badge tone="violet">IA</Badge>
 */
import type { ReactNode } from "react";
import type { Client, InvoiceStatus, OrderStatus, PurchaseOrderStatus, RouteRun, StopStatus } from "@kit/shared";
import { cn } from "@/lib/cn";

export type Tone = "muted" | "info" | "violet" | "success" | "warning" | "destructive" | "foreground";

export const TONE_DOT: Record<Tone, string> = {
  muted: "bg-muted-foreground/45",
  info: "bg-info",
  violet: "bg-violet",
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  foreground: "bg-foreground/60",
};
export const TONE_TEXT: Record<Tone, string> = {
  muted: "text-muted-foreground",
  info: "text-info",
  violet: "text-violet",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
  foreground: "text-foreground/70",
};
const TONE_BADGE: Record<Tone, string> = {
  muted: "border-border bg-muted text-muted-foreground",
  info: "border-info/25 bg-info/10 text-info",
  violet: "border-violet/25 bg-violet/10 text-violet",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-[hsl(32_80%_36%)] dark:text-warning",
  destructive: "border-destructive/25 bg-destructive/10 text-destructive",
  foreground: "border-border bg-muted text-foreground/80",
};

type StatusMap<K extends string> = Record<K, { label: string; tone: Tone }>;

export const ORDER_STATUS: StatusMap<OrderStatus> = {
  draft: { label: "Brouillon", tone: "muted" },
  confirmed: { label: "Confirmée", tone: "info" },
  prepared: { label: "Préparée", tone: "violet" },
  delivered: { label: "Livrée", tone: "success" },
  invoiced: { label: "Facturée", tone: "foreground" },
  cancelled: { label: "Annulée", tone: "destructive" },
};
export const INVOICE_STATUS: StatusMap<InvoiceStatus> = {
  draft: { label: "Brouillon", tone: "muted" },
  issued: { label: "Émise", tone: "info" },
  partially_paid: { label: "Partiellement payée", tone: "warning" },
  paid: { label: "Payée", tone: "success" },
  overdue: { label: "En retard", tone: "destructive" },
  cancelled: { label: "Annulée", tone: "muted" },
};
export const PO_STATUS: StatusMap<PurchaseOrderStatus> = {
  draft: { label: "Brouillon", tone: "muted" },
  sent: { label: "Envoyée", tone: "info" },
  partially_received: { label: "Reçue partiellement", tone: "warning" },
  received: { label: "Reçue", tone: "success" },
  cancelled: { label: "Annulée", tone: "destructive" },
};
export const CLIENT_STATUS: StatusMap<Client["status"]> = {
  active: { label: "Actif", tone: "success" },
  blocked: { label: "Bloqué", tone: "destructive" },
  prospect: { label: "Prospect", tone: "info" },
};
export const ROUTE_RUN_STATUS: StatusMap<RouteRun["status"]> = {
  planned: { label: "Planifiée", tone: "muted" },
  in_progress: { label: "En cours", tone: "info" },
  done: { label: "Terminée", tone: "success" },
};
export const STOP_STATUS: StatusMap<StopStatus> = {
  pending: { label: "À livrer", tone: "muted" },
  delivered: { label: "Livré", tone: "success" },
  failed: { label: "Échec", tone: "destructive" },
};

export const STATUS = {
  order: ORDER_STATUS,
  invoice: INVOICE_STATUS,
  purchaseOrder: PO_STATUS,
  client: CLIENT_STATUS,
  routeRun: ROUTE_RUN_STATUS,
  stop: STOP_STATUS,
} as const;
export type StatusKind = keyof typeof STATUS;

/** Options for a status filter <Select>: statusOptions("order") */
export const statusOptions = (kind: StatusKind) =>
  Object.entries(STATUS[kind]).map(([value, s]) => ({ value, label: (s as { label: string }).label }));

export function Dot({ tone, className, pulse }: { tone: Tone; className?: string; pulse?: boolean }) {
  return (
    <span className={cn("relative inline-flex h-1.5 w-1.5 shrink-0", className)} aria-hidden>
      {pulse ? <span className={cn("absolute inset-0 animate-ping rounded-full opacity-60", TONE_DOT[tone])} /> : null}
      <span className={cn("relative h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} />
    </span>
  );
}

type StatusDotProps =
  | { kind: StatusKind; value: string; tone?: never; label?: never; className?: string }
  | { kind?: never; value?: never; tone: Tone; label: ReactNode; className?: string };

/** Dot + word. Either a domain status (kind+value) or a free tone+label. */
export function StatusDot(props: StatusDotProps) {
  let tone: Tone = "muted";
  let label: ReactNode = props.label;
  if (props.kind) {
    const s = (STATUS[props.kind] as Record<string, { label: string; tone: Tone }>)[props.value];
    tone = s?.tone ?? "muted";
    label = s?.label ?? props.value;
  } else if (props.tone) tone = props.tone;
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap text-[12.5px] text-secondary-foreground", props.className)}>
      <Dot tone={tone} />
      {label}
    </span>
  );
}

/** Small 3px-radius chip, for counts/tags (not statuses): <Badge tone="violet">Agent vocal</Badge> */
export function Badge({ tone = "muted", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex h-[18px] items-center gap-1 whitespace-nowrap rounded-[3px] border px-1.5 text-[11px] font-medium", TONE_BADGE[tone], className)}>
      {children}
    </span>
  );
}
