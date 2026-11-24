/**
 * Lines of a sale or purchase document: inline editing (qty, price, note), add-line product search, totals.
 *  sale     → available stock, prepared qty (prepared+), price-source ⓘ, alternatives, line note.
 *  purchase → stock on hand, usual supplier price + gap, received qty (sent+), optional receive column.
 */
import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRightLeft, PackageOpen, Trash2 } from "lucide-react";
import type { Id, ProductSummary } from "@kit/shared";
import { cn } from "@/lib/cn";
import { UNIT_LABEL } from "@/lib/format";
import { Badge, IconButton, Money, Mono, Qty, Section, Table, TableFrame, TBody, TD, TH, THead, TR } from "@/ui";
import { NumberCell, ProductPicker, TextCell } from "./inline";
import { PriceSourceInfo } from "./price-source";
import { computeTotals, lineQty, useDocOps, type DocLine, type DocModel } from "./model";

interface Col { key: string; header?: ReactNode; title?: string; width?: number; right?: boolean; className?: string; cell: (l: DocLine) => ReactNode }

/** Extra column a page can plug in (purchase receive mode). */
export type ExtraColumn = Omit<Col, "key">;

export function LinesTable({ doc, products, supplierPrices, onAlternatives, extraColumn, title, actions, frameClassName, footnote }: {
  doc: DocModel;
  products: Map<Id, ProductSummary>;
  /** purchase: catalogue price of each product at this supplier (the "usual" price). */
  supplierPrices?: Map<Id, number>;
  onAlternatives?: (l: DocLine) => void;
  extraColumn?: ExtraColumn;
  title?: ReactNode;
  actions?: ReactNode;
  frameClassName?: string;
  footnote?: ReactNode;
}) {
  const sale = doc.kind === "sale";
  const { editable, preparing } = doc;
  const inProgress = sale ? editable || !!preparing : editable;
  const { add, update, remove } = useDocOps(doc);

  const warnOf = useMemo(() => {
    const m = new Map<Id, Set<string>>();
    doc.warnings.forEach((w) => { if (w.productId) m.set(w.productId, (m.get(w.productId) ?? new Set()).add(w.code)); });
    return m;
  }, [doc.warnings]);
  const inDoc = useMemo(() => new Set(doc.lines.map((l) => l.productId)), [doc.lines]);
  const totals = computeTotals(doc, products);
  const unitOf = (l: DocLine) => UNIT_LABEL[l.unit as keyof typeof UNIT_LABEL] ?? l.unit;
  const editCls = "py-0 pr-1";

  const cols: Col[] = [];
  cols.push({
    key: "product", header: "Produit", className: "whitespace-normal py-1.5",
    cell: (l) => {
      const p = products.get(l.productId);
      const w = warnOf.get(l.productId);
      const subOf = l.substituteFor ? products.get(l.substituteFor)?.name ?? l.substituteFor : undefined;
      return (
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 leading-snug">
          <Link to={`/products/${l.productId}`} className="min-w-0 break-words font-medium hover:underline">{l.productName}</Link>
          {p ? <Mono className="hidden text-[11px] text-muted-foreground 2xl:inline">{p.sku}</Mono> : null}
          {subOf ? <Badge tone="info" className="max-w-full"><ArrowRightLeft size={10} strokeWidth={2} className="shrink-0" /><span className="truncate">remplace {subOf}</span></Badge> : null}
          {w?.has("expiring_soon") ? <Badge tone="warning" className="shrink-0">DLC proche</Badge> : null}
          {w?.has("not_in_supplier_catalog") ? <Badge tone="warning" className="shrink-0">Hors catalogue</Badge> : null}
        </div>
      );
    },
  });

  if (sale) {
    cols.push({
      key: "note", header: "Note", width: editable ? 76 : inProgress ? 64 : 140, className: inProgress ? "py-0" : undefined,
      cell: (l) => inProgress
        ? <TextCell value={l.note} placeholder="—" label={`Note : ${l.productName}`} onCommit={(note) => update.mutate({ lineId: l.id, patch: { note } })} />
        : <span className="block truncate text-[12.5px] text-muted-foreground" title={l.note || undefined}>{l.note || "—"}</span>,
    });
  }

  // Stock: what can be sold (sale) / what is already on hand before buying (purchase draft).
  if (inProgress) {
    cols.push({
      key: "stock", header: sale ? "Disponible" : "En stock", width: 92, right: true,
      title: sale ? undefined : "Stock disponible aujourd'hui",
      cell: (l) => {
        if (!sale) {
          const p = products.get(l.productId);
          return p ? <Qty value={p.available} unit={l.unit} className="text-muted-foreground" /> : <span className="text-muted-foreground">—</span>;
        }
        const avail = l.available ?? 0;
        const short = !!warnOf.get(l.productId)?.has("insufficient_stock") || avail < l.qty;
        const empty = avail <= 0;
        return (
          <span className="inline-flex items-center gap-1.5" title={short ? "Stock insuffisant pour cette quantité" : undefined}>
            {short ? <span className={cn("h-1.5 w-1.5 rounded-full", empty ? "bg-destructive" : "bg-warning")} /> : null}
            <Qty value={avail} unit={l.unit} tone={empty ? "destructive" : short ? "warning" : undefined} />
          </span>
        );
      },
    });
  }

  cols.push({
    key: "qty", header: "Qté cdée", title: "Quantité commandée", width: editable ? 106 : 86, right: true, className: editable ? editCls : undefined,
    cell: (l) => editable
      ? <NumberCell compact label={`Quantité : ${l.productName}`} value={l.qty} suffix={unitOf(l)} min={0.001} onCommit={(qty) => update.mutate({ lineId: l.id, patch: { qty } })} />
      : <Qty value={l.qty} unit={l.unit} className={doc.picked && l.preparedQty != null && Math.abs(l.preparedQty - l.qty) > 1e-9 ? "text-muted-foreground" : undefined} />,
  });

  if (sale && doc.picked) {
    cols.push({
      key: "prepared", header: "Qté prép.", title: "Quantité préparée", width: preparing ? 106 : 90, right: true, className: preparing ? editCls : undefined,
      cell: (l) => preparing
        ? <NumberCell compact label={`Quantité préparée : ${l.productName}`} value={l.preparedQty ?? l.qty} suffix={unitOf(l)} onCommit={(preparedQty) => update.mutate({ lineId: l.id, patch: { preparedQty } })} />
        : <Qty value={l.preparedQty ?? l.qty} unit={l.unit} className={l.preparedQty != null && Math.abs(l.preparedQty - l.qty) > 1e-9 ? "font-medium" : undefined} />,
    });
  }

  if (!sale && doc.receiving) {
    cols.push({
      key: "received", header: "Reçu", width: 132, right: true,
      cell: (l) => {
        const got = l.receivedQty ?? 0;
        const done = got >= l.qty;
        return (
          <span className="inline-flex items-center gap-2">
            <ProgressBar value={l.qty ? got / l.qty : 0} tone={done ? "success" : got > 0 ? "warning" : "muted"} />
            <Qty value={got} unit={l.unit} className={got ? undefined : "text-muted-foreground"} />
          </span>
        );
      },
    });
  }
  if (extraColumn) cols.push({ key: "extra", ...extraColumn });

  cols.push({
    key: "price", header: "PU HT", width: sale ? (editable ? 104 : 100) : editable ? 150 : 140, right: true, className: editable ? editCls : undefined,
    cell: (l) => {
      const p = products.get(l.productId);
      if (sale) {
        return (
          <span className="inline-flex items-center justify-end gap-0.5">
            <PriceSourceInfo clientId={doc.partnerId} productId={l.productId} qty={l.qty} date={doc.date} unitPrice={l.unitPrice} />
            {editable
              ? <NumberCell compact label={`Prix unitaire : ${l.productName}`} value={l.unitPrice} suffix="€" onCommit={(unitPrice) => update.mutate({ lineId: l.id, patch: { unitPrice } })} tone={p && l.unitPrice < p.cost ? "destructive" : undefined} />
              : <Money value={l.unitPrice} />}
          </span>
        );
      }
      const usual = supplierPrices?.get(l.productId);
      const above = !!warnOf.get(l.productId)?.has("price_above_usual");
      return (
        <span className="inline-flex items-center justify-end gap-1.5">
          <PriceGap price={l.unitPrice} usual={usual} warn={above} />
          {editable
            ? <NumberCell compact label={`Prix unitaire : ${l.productName}`} value={l.unitPrice} suffix="€" onCommit={(unitPrice) => update.mutate({ lineId: l.id, patch: { unitPrice } })} tone={above ? "warning" : undefined} />
            : <Money value={l.unitPrice} />}
        </span>
      );
    },
  });
  cols.push({ key: "total", header: "Total HT", width: 94, right: true, cell: (l) => <Money value={lineQty(doc, l) * l.unitPrice} className="font-medium" /> });

  if (editable) {
    cols.push({
      key: "actions", width: sale ? 62 : 40, className: "py-0 pl-1 pr-2",
      cell: (l) => {
        const short = sale && (l.available ?? 0) < l.qty;
        return (
          <span className="flex items-center justify-end gap-0.5">
            {sale && onAlternatives ? (
              <IconButton icon={ArrowRightLeft} label="Alternatives" size="sm" onClick={() => onAlternatives(l)} className={short ? "text-warning hover:text-warning" : undefined} />
            ) : null}
            <IconButton icon={Trash2} label="Retirer la ligne" size="sm" disabled={remove.isPending} onClick={() => remove.mutate(l.id)} className="hover:text-destructive" />
          </span>
        );
      },
    });
  }

  const priceOf = !sale && supplierPrices
    ? (p: ProductSummary) => {
        const sp = supplierPrices.get(p.id);
        return sp != null ? { price: sp } : { price: p.cost, hint: supplierPrices.size ? "hors catalogue" : undefined };
      }
    : undefined;
  const hint = editable ? "Cliquez une valeur pour la modifier" : preparing ? "Saisissez les quantités pesées" : null;

  return (
    <Section title={title ?? "Lignes"} count={doc.lines.length} actions={actions ?? (hint ? <span className="text-[11.5px] text-muted-foreground">{hint}</span> : null)}>
      <div className={frameClassName}>
        <TableFrame>
          <Table fixed>
            {/* Fixed layout: every numeric column has a set width, the product column takes all the free width. */}
            <colgroup>{cols.map((c) => <col key={c.key} style={c.width ? { width: c.width } : undefined} />)}</colgroup>
            <THead>
              <tr>{cols.map((c) => <TH key={c.key} align={c.right ? "right" : undefined} title={c.title}>{c.header}</TH>)}</tr>
            </THead>
            <TBody>
              {doc.lines.map((l) => (
                <TR key={l.id} liveId={l.id}>
                  {cols.map((c) => <TD key={c.key} numeric={c.right} className={c.className}>{c.cell(l)}</TD>)}
                </TR>
              ))}
              {doc.lines.length === 0 ? (
                <tr>
                  <td colSpan={cols.length} className="border-b border-border px-3 py-6 text-center text-[12.5px] text-muted-foreground">
                    <span className="inline-flex items-center gap-2">
                      <PackageOpen size={14} strokeWidth={1.75} />Aucune ligne.{" "}
                      {editable ? (sale ? "Ajoutez un produit ou reprenez le panier habituel du client." : "Ajoutez un produit ou reprenez les achats habituels chez ce fournisseur.") : ""}
                    </span>
                  </td>
                </tr>
              ) : null}
            </TBody>
          </Table>
          {editable ? (
            <div className="border-t border-border bg-muted/30 px-3 py-2">
              <ProductPicker products={products} excludeIds={inDoc} priceOf={priceOf} autoFocus={doc.lines.length === 0}
                onPick={(p) => add.mutate({ productId: p.id, qty: 1 })} />
            </div>
          ) : null}
        </TableFrame>
      </div>
      <TotalsBlock totals={totals} footnote={footnote} />
    </Section>
  );
}

/** Totals HT / TVA / TTC, right-aligned under the lines; an optional footnote on the left. */
export function TotalsBlock({ totals, footnote }: { totals: { ht: number; vat: number; ttc: number }; footnote?: ReactNode }) {
  return (
    <div className="mt-3 flex items-start justify-between gap-6">
      <div className="min-w-0 text-[12px] text-muted-foreground">{footnote}</div>
      <dl className="grid w-[280px] shrink-0 grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-[13px]">
        <dt className="text-muted-foreground">Total HT</dt><dd className="text-right"><Money value={totals.ht} /></dd>
        <dt className="text-muted-foreground">TVA</dt><dd className="text-right"><Money value={totals.vat} /></dd>
        <dt className="border-t border-border pt-1.5 font-medium">Total TTC</dt>
        <dd className="border-t border-border pt-1.5 text-right"><Money value={totals.ttc} className="text-[15px] font-semibold" /></dd>
      </dl>
    </div>
  );
}

/** Gap between the line price and the usual supplier price ("+12 %", warning when flagged); nothing when equal or unknown. */
function PriceGap({ price, usual, warn }: { price: number; usual?: number; warn: boolean }) {
  if (usual == null || usual <= 0) return null;
  const gap = price / usual - 1;
  if (Math.abs(gap) < 0.005) return null;
  return (
    <span
      className={cn("num text-[11px]", warn ? "font-medium text-warning" : gap > 0 ? "text-muted-foreground" : "text-success")}
      title={`Prix habituel ${usual.toLocaleString("fr-FR", { style: "currency", currency: "EUR" })}`}
    >
      {`${gap > 0 ? "+" : "−"}${Math.round(Math.abs(gap) * 100)} %`}
    </span>
  );
}

export function ProgressBar({ value, tone }: { value: number; tone: "success" | "warning" | "muted" }) {
  return (
    <span className="h-1 w-10 overflow-hidden rounded-full bg-muted">
      <span className={cn("block h-full rounded-full", tone === "success" ? "bg-success" : tone === "warning" ? "bg-warning" : "bg-muted-foreground/40")}
        style={{ width: `${Math.min(100, Math.round(value * 100))}%` }} />
    </span>
  );
}
