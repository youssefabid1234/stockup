/** Shared document blocks: KPI strip, editable date, note, warnings list, usual basket, page layout and skeleton. */
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Plus, ShoppingBasket } from "lucide-react";
import type { Id, ProductSummary, UsualBasketLine, Warning } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtPercent, fmtQty } from "@/lib/format";
import { useClientUsual, useSupplierUsual } from "@/lib/queries";
import {
  Button, DateLabel, DatePicker, EmptyState, Money, Page, PageBody, PageHeader, SECTION_LABEL, Section, Skeleton, Stat, StatGrid, Textarea,
} from "@/ui";
import { computeTotals, KIND, roundQty, useDocOps, usualQty, type DocKind, type DocModel } from "./model";

// ── KPI strip: partner · date · total HT · total TTC · created ──
export function DocumentKpis({ doc, products, partnerHint, dateHint, dateTone, totalHint, createdHint }: {
  doc: DocModel; products: Map<Id, ProductSummary>;
  partnerHint?: ReactNode; dateHint?: ReactNode; dateTone?: "destructive"; totalHint?: ReactNode; createdHint?: ReactNode;
}) {
  const k = KIND[doc.kind];
  const totals = computeTotals(doc, products);
  const n = doc.lines.length;
  return (
    <StatGrid className="md:grid-cols-5">
      <Stat label={k.partner} value={<Link to={`${k.partnerPath}/${doc.partnerId}`} className="block truncate text-[15px] font-semibold hover:underline">{doc.partnerName}</Link>} hint={partnerHint} />
      <Stat label={k.date} value={<DocumentDate doc={doc} />} tone={dateTone} hint={dateHint ?? (doc.headerEditable ? k.dateHint : undefined)} />
      <Stat label="Total HT" value={<Money value={totals.ht} />} hint={totalHint ?? `${n} ligne${n > 1 ? "s" : ""}`} />
      <Stat label="Total TTC" value={<Money value={totals.ttc} />} hint={<>TVA <Money value={totals.vat} /></>} />
      <Stat label="Créée" value={<DateLabel date={doc.createdAt} className="text-[15px]" />} hint={createdHint} />
    </StatGrid>
  );
}

export function DocumentDate({ doc }: { doc: DocModel }) {
  const { setDate } = useDocOps(doc);
  if (!doc.headerEditable) return <DateLabel date={doc.date} className="text-[15px]" />;
  return (
    <DatePicker
      variant="inline"
      aria-label={`Modifier : ${KIND[doc.kind].date.toLowerCase()}`}
      value={doc.date}
      disabled={setDate.isPending}
      onChange={(v) => { if (v && v !== doc.date) setDate.mutate(v); }}
      className="text-[15px]"
    />
  );
}

// ── Note ──
export function DocumentNote({ doc }: { doc: DocModel }) {
  const [text, setText] = useState(doc.note ?? "");
  const [focused, setFocused] = useState(false);
  useEffect(() => { if (!focused) setText(doc.note ?? ""); }, [doc.note, focused]);
  const { setNote } = useDocOps(doc);
  if (!doc.headerEditable && !doc.note) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <span className={SECTION_LABEL}>Note de commande</span>
      {doc.headerEditable ? (
        <Textarea
          rows={2}
          value={text}
          aria-label="Note de commande"
          placeholder={KIND[doc.kind].notePlaceholder}
          onFocus={() => setFocused(true)}
          onBlur={() => { setFocused(false); if (text.trim() !== (doc.note ?? "")) setNote.mutate(text.trim()); }}
          onChange={(e) => setText(e.target.value)}
          className="max-w-[640px]"
        />
      ) : (
        <div className="whitespace-pre-wrap text-[13px] text-secondary-foreground">{doc.note}</div>
      )}
    </div>
  );
}

// ── Warnings ──
const BLOCKING: Warning["code"][] = ["client_blocked", "credit_limit"];
const WARNING_TITLE: Record<Warning["code"], string> = {
  credit_limit: "Encours", client_blocked: "Client bloqué", insufficient_stock: "Stock", expiring_soon: "DLC",
  no_route: "Tournée", price_below_cost: "Prix",
  below_min_order: "Minimum", price_above_usual: "Prix inhabituel", not_in_supplier_catalog: "Hors catalogue",
};

export function WarningList({ warnings, note, onDismiss }: { warnings: Warning[]; note?: string; onDismiss?: () => void }) {
  if (!warnings.length) return null;
  return (
    <div className="overflow-hidden rounded-[6px] border border-warning/40 bg-warning/[.06]" role="status" aria-label="Points d'attention">
      <div className="flex items-center gap-2 border-b border-warning/25 px-3 py-2">
        <AlertTriangle size={14} strokeWidth={1.75} className="text-warning" />
        <span className="text-[12.5px] font-medium">
          {warnings.length} point{warnings.length > 1 ? "s" : ""} d'attention{note ? ` · ${note}` : ""}
        </span>
        {onDismiss ? <button type="button" onClick={onDismiss} className="ml-auto text-[12px] text-muted-foreground hover:text-foreground">Masquer</button> : null}
      </div>
      <ul className="flex flex-col">
        {warnings.map((w, i) => (
          <li key={i} className="flex items-center gap-2.5 px-3 py-1.5 text-[12.5px]">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", BLOCKING.includes(w.code) ? "bg-destructive" : "bg-warning")} />
            <span className="w-[96px] shrink-0 text-muted-foreground">{WARNING_TITLE[w.code] ?? w.code}</span>
            <span className="min-w-0 flex-1">{w.message}</span>
            {w.productId ? <Link to={`/products/${w.productId}`} className="text-[12px] text-muted-foreground hover:text-foreground">Produit</Link> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Usual basket: client's usual order (sale) / what we usually buy from the supplier (purchase) ──
export function UsualBasket({ doc }: { doc: DocModel }) {
  const sale = doc.kind === "sale";
  const clientQ = useClientUsual(sale ? doc.partnerId : undefined);
  const supplierQ = useSupplierUsual(sale ? undefined : doc.partnerId);
  const { data, isLoading } = sale ? clientQ : supplierQ;
  const { add } = useDocOps(doc);
  const addLine = (l: UsualBasketLine) => add.mutateAsync({ productId: l.productId, qty: usualQty(l.avgQty, l.unit) });
  const inDoc = new Set(doc.lines.map((l) => l.productId));
  const lines = (data ?? []).slice().sort((a, b) => b.frequency - a.frequency).slice(0, 10);
  const missing = lines.filter((l) => !inDoc.has(l.productId));
  const addAll = async () => { for (const l of missing) await addLine(l).catch(() => undefined); };

  return (
    <Section
      title={sale ? "Panier habituel" : "Achats habituels"}
      count={data?.length}
      actions={doc.editable && missing.length > 1 ? <Button size="sm" variant="ghost" icon={Plus} loading={add.isPending} onClick={addAll}>Tout ajouter</Button> : null}
    >
      {isLoading ? (
        <div className="flex flex-col gap-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}</div>
      ) : lines.length === 0 ? (
        <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
          <ShoppingBasket size={14} strokeWidth={1.75} />{KIND[doc.kind].usualEmpty}
        </div>
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border bg-card" aria-label={sale ? "Panier habituel" : "Achats habituels"}>
          {lines.map((l) => {
            const there = inDoc.has(l.productId);
            return (
              <li key={l.productId} className="flex h-9 items-center gap-2 px-3">
                <div className="min-w-0 flex-1">
                  <div className={cn("truncate text-[12.5px]", there ? "text-muted-foreground" : "font-medium")}>{l.productName}</div>
                </div>
                <span className="num text-[11.5px] text-muted-foreground" title={`Présent dans ${fmtPercent(l.frequency)} des commandes`}>
                  ~{fmtQty(roundQty(l.avgQty, l.unit), l.unit)} · {fmtPercent(l.frequency)}
                </span>
                {doc.editable ? (
                  there ? (
                    <span className="w-[60px] text-right text-[11.5px] text-muted-foreground">sur la cde</span>
                  ) : (
                    <Button size="sm" variant="ghost" icon={Plus} className="w-[60px]" disabled={add.isPending} aria-label={`Ajouter ${l.productName}`}
                      onClick={() => addLine(l).catch(() => undefined)}>Ajouter</Button>
                  )
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

// ── Layout ──
/** Same frame on both sides: KPI strip, then main column (warnings, lines, note…) + 300/340px side column. */
export function DocumentLayout({ kpis, main, aside }: { kpis: ReactNode; main: ReactNode; aside: ReactNode }) {
  return (
    <>
      {kpis}
      <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_300px] 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">{main}</div>
        <aside className="flex min-w-0 flex-col gap-7">{aside}</aside>
      </div>
    </>
  );
}

export function DocumentSkeleton({ kind }: { kind: DocKind }) {
  const k = KIND[kind];
  return (
    <Page>
      <PageHeader breadcrumb={[{ label: k.listLabel, to: k.list }]} title={<Skeleton className="h-4 w-40" />} />
      <PageBody flush>
        <DocumentLayout
          kpis={<StatGrid className="md:grid-cols-5">{Array.from({ length: 5 }).map((_, i) => <Stat key={i} label={<Skeleton className="h-3 w-20" />} value={<Skeleton className="mt-1 h-5 w-24" />} />)}</StatGrid>}
          main={<div className="flex flex-col gap-3">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)}</div>}
          aside={<div className="flex flex-col gap-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}</div>}
        />
      </PageBody>
    </Page>
  );
}

export function DocumentNotFound({ kind, id, icon }: { kind: DocKind; id: string; icon: Parameters<typeof EmptyState>[0]["icon"] }) {
  const k = KIND[kind];
  return (
    <Page>
      <PageHeader breadcrumb={[{ label: k.listLabel, to: k.list }]} title={id} />
      <PageBody><EmptyState icon={icon} title={`${k.noun[0].toUpperCase()}${k.noun.slice(1)} introuvable`} description={`Aucune ${k.noun} ne correspond à l'identifiant ${id}.`} /></PageBody>
    </Page>
  );
}

/** Two-step destructive action (Annuler → Confirmer l'annulation): the first click arms it for 4 s. */
export function useArm(): [boolean, (v: boolean) => void] {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = window.setTimeout(() => setArmed(false), 4000);
    return () => window.clearTimeout(t);
  }, [armed]);
  return [armed, setArmed];
}
