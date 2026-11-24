/** Tool-call rendering shared by the Assistant panel and the Voice page: compact row, args summary, ERP links. */
import { Link } from "react-router-dom";
import { ArrowUpRight, Check, Wrench, X } from "lucide-react";
import type { ActivityEvent } from "@kit/shared";
import { cn } from "@/lib/cn";
import { entityPath } from "@/lib/links";
import { Spinner } from "@/ui";

export interface ToolRun {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  ok?: boolean; // undefined = running
  ms?: number;
  result?: unknown;
}

export interface EntityLink { to: string; label: string }

/** French verb for each harness tool (unknown tools fall back to their raw name). */
export const TOOL_LABEL: Record<string, string> = {
  search: "Recherche",
  get_client: "Fiche client",
  get_product_stock: "Stock produit",
  find_alternatives: "Alternatives",
  create_draft_order: "Pré-commande",
  add_order_line: "Ajout de ligne",
  confirm_order: "Confirmation",
  get_order: "Commande",
  search_context: "Recherche contexte",
  get_context: "Contexte",
  save_context: "Mémorisation",
};

const ID_ENTITY: [RegExp, ActivityEvent["entity"]][] = [
  [/^cli_/, "client"], [/^prd_/, "product"], [/^ord_|^cmd_/, "order"], [/^sup_|^frn_/, "supplier"],
  [/^po_/, "purchase_order"], [/^inv_/, "invoice"], [/^ctx_/, "context"],
];
const SEARCH_ENTITY: Record<string, ActivityEvent["entity"]> = { client: "client", product: "product", supplier: "supplier", order: "order" };
const TOOL_ENTITY: Record<string, ActivityEvent["entity"]> = {
  get_client: "client", get_product_stock: "product", find_alternatives: "product",
  create_draft_order: "order", add_order_line: "order", confirm_order: "order", get_order: "order",
  search_context: "context", save_context: "context",
};

function guessEntity(id: string): ActivityEvent["entity"] | undefined {
  return ID_ENTITY.find(([re]) => re.test(id))?.[1];
}

function linkOf(entity: ActivityEvent["entity"] | undefined, id: unknown, label: unknown): EntityLink | undefined {
  if (!entity || typeof id !== "string") return undefined;
  const to = entityPath(entity, id);
  return to ? { to, label: typeof label === "string" && label ? label : id } : undefined;
}

/** ERP entities a tool touched: from its result (id/number/name), else from id-looking args. Max 3. */
export function toolLinks(t: ToolRun): EntityLink[] {
  const r = t.result as Record<string, unknown> | Record<string, unknown>[] | undefined;
  const out: EntityLink[] = [];
  if (Array.isArray(r)) {
    for (const x of r.slice(0, 3)) {
      const e = typeof x?.type === "string" ? SEARCH_ENTITY[x.type] : TOOL_ENTITY[t.name] ?? guessEntity(String(x?.id ?? ""));
      const l = linkOf(e, x?.id, x?.label ?? x?.number ?? x?.name);
      if (l) out.push(l);
    }
  } else if (r && typeof r === "object" && typeof r.id === "string") {
    const l = linkOf(TOOL_ENTITY[t.name] ?? guessEntity(r.id), r.id, r.number ?? r.name);
    if (l) out.push(l);
  }
  if (!out.length && t.args) {
    for (const [k, v] of Object.entries(t.args)) {
      if (typeof v !== "string" || !k.endsWith("Id")) continue;
      const e = k === "clientId" ? "client" : k === "productId" ? "product" : k === "orderId" ? "order" : guessEntity(v);
      const l = linkOf(e, v, v);
      if (l) out.push(l);
      if (out.length >= 2) break;
    }
  }
  return out;
}

/** One-line args summary: `« bar de ligne »`, `cli_0012 · 3 lignes`. */
export function argsSummary(args?: Record<string, unknown>): string {
  if (!args) return "";
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    if (v == null || v === "") continue;
    if (k === "query" && typeof v === "string") parts.push(`« ${v} »`);
    else if (Array.isArray(v)) parts.push(k === "lines" ? `${v.length} ligne${v.length > 1 ? "s" : ""}` : v.map(String).join(","));
    else if (typeof v === "object") parts.push(k);
    else parts.push(k.endsWith("Id") ? String(v) : `${k}=${String(v)}`);
  }
  return parts.join(" · ");
}

export function resultSummary(t: ToolRun): string | undefined {
  const r = t.result as Record<string, unknown> | unknown[] | undefined;
  if (t.ok === false) {
    const err = r && !Array.isArray(r) && typeof r === "object" ? (r as Record<string, unknown>).error : r;
    return typeof err === "string" ? err : err ? JSON.stringify(err).slice(0, 120) : "erreur";
  }
  if (Array.isArray(r)) return `${r.length} résultat${r.length > 1 ? "s" : ""}`;
  return undefined;
}

/** Compact violet row: icon · tool name (mono) · args · links · ok/error · ms. */
export function ToolRow({ t, className, onNavigate }: { t: ToolRun; className?: string; onNavigate?: () => void }) {
  const running = t.ok === undefined;
  const links = toolLinks(t);
  const summary = resultSummary(t);
  return (
    <div
      className={cn(
        "group flex min-h-[26px] flex-wrap items-center gap-x-2 gap-y-0.5 rounded-[3px] border border-violet/20 bg-violet/[.05] px-2 py-1 text-[11.5px] animate-fade-in",
        t.ok === false && "border-destructive/30 bg-destructive/[.05]",
        className,
      )}
      title={t.args ? JSON.stringify(t.args, null, 1) : undefined}
    >
      {/* basis auto (not flex-1): the name + args part keeps its width and the summary / links / ms wrap to a second line
          instead of being drawn over the tool name when the row is narrow (HUD, Assistant panel). */}
      <span className="flex min-w-0 max-w-full flex-[1_1_auto] items-center gap-1.5">
        {running ? (
          <Spinner size={11} className="shrink-0 text-violet" />
        ) : t.ok ? (
          <Check size={12} strokeWidth={2} className="shrink-0 text-violet" aria-label="ok" />
        ) : t.ok === false ? (
          <X size={12} strokeWidth={2} className="shrink-0 text-destructive" aria-label="erreur" />
        ) : (
          <Wrench size={12} strokeWidth={1.75} className="shrink-0 text-violet" />
        )}
        <span className="min-w-0 shrink truncate font-mono text-[11px] text-violet">{t.name}</span>
        <span className="min-w-0 max-w-[260px] shrink-[4] truncate text-muted-foreground">{argsSummary(t.args)}</span>
      </span>
      {summary ? <span className={cn("shrink-0", t.ok === false ? "text-destructive" : "text-muted-foreground")}>{summary}</span> : null}
      {links.map((l) => (
        <Link
          key={l.to + l.label}
          to={l.to}
          onClick={onNavigate}
          className="inline-flex max-w-[160px] shrink-0 items-center gap-0.5 truncate text-foreground underline-offset-2 hover:underline"
        >
          <span className="truncate">{l.label}</span>
          <ArrowUpRight size={11} className="shrink-0 text-muted-foreground" />
        </Link>
      ))}
      {t.ms != null ? <span className="num shrink-0 font-mono text-[10.5px] text-muted-foreground">{t.ms} ms</span> : null}
    </div>
  );
}
