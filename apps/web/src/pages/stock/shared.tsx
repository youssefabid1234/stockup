/** Stock helpers shared by Produits / Produit / Stocks (owned by the stock pages). */
import { useState } from "react";
import type { Id, IsoDate, Lot, Unit } from "@kit/shared";
import { api } from "@/lib/api";
import { parseDate, todayIso } from "@/lib/format";
import { qk, useApiMutation, useMeta } from "@/lib/queries";
import { cn } from "@/lib/cn";
import { Button, DataTable, DateLabel, Field, Input, Mono, Qty, Segmented, SidePanel, Textarea, type Column } from "@/ui";

/** Business "today" = data pack date when available (demo data is anchored on it). */
export function useToday(): IsoDate {
  const { data } = useMeta();
  return data?.today ?? todayIso();
}

export function daysUntil(date: IsoDate | undefined | null, today: IsoDate): number | undefined {
  if (!date) return undefined;
  return Math.round((parseDate(date).getTime() - parseDate(today).getTime()) / 86_400_000);
}

export const EXPIRY_WARN_DAYS = 2;
export const isExpiringSoon = (date: IsoDate | undefined | null, today: IsoDate) => {
  const d = daysUntil(date, today);
  return d !== undefined && d <= EXPIRY_WARN_DAYS;
};

/** Expiry date with tone: past = destructive, ≤ 2 days = warning, plus "J+n" hint. */
export function ExpiryLabel({ date, today, showDelta = true }: { date?: IsoDate | null; today: IsoDate; showDelta?: boolean }) {
  const d = daysUntil(date, today);
  if (!date || d === undefined) return <span className="text-muted-foreground">—</span>;
  const tone = d < 0 ? "text-destructive" : d <= EXPIRY_WARN_DAYS ? "text-warning" : "text-secondary-foreground";
  const delta = d < 0 ? `périmé` : d === 0 ? "aujourd'hui" : `J+${d}`;
  return (
    <span className={cn("inline-flex items-center gap-1.5", tone)}>
      <DateLabel date={date} />
      {showDelta ? <span className="num text-[11.5px] opacity-80">{delta}</span> : null}
    </span>
  );
}

/** Lots in FEFO order (earliest expiry first), remaining only. */
export const fefo = (lots: Lot[]) => lots.filter((l) => l.qtyRemaining > 0).sort((a, b) => a.expiresAt.localeCompare(b.expiresAt));

export function lotColumns(unit: Unit | string, today: IsoDate, supplierName?: (id?: Id) => string | undefined): Column<Lot>[] {
  return [
    { id: "lot", header: "Lot", width: 130, cell: (l) => <Mono>{l.id}</Mono> },
    { id: "received", header: "Reçu le", width: 120, cell: (l) => <DateLabel date={l.receivedAt} className="text-muted-foreground" /> },
    { id: "expires", header: "DLC", width: 150, cell: (l) => <ExpiryLabel date={l.expiresAt} today={today} /> },
    ...(supplierName ? [{ id: "supplier", header: "Fournisseur", muted: true, cell: (l: Lot) => supplierName(l.supplierId) ?? "—" }] : []),
    { id: "qtyReceived", header: "Reçu", width: 100, numeric: true, muted: true, cell: (l) => <Qty value={l.qtyReceived} unit={unit} /> },
    { id: "qtyRemaining", header: "Restant", width: 100, numeric: true, cell: (l) => <Qty value={l.qtyRemaining} unit={unit} className="font-medium" /> },
  ];
}

/** Stock state of one level: rupture / bas / DLC proche / ok. */
export function stockTone(available: number, low: boolean): { tone: "destructive" | "warning" | "success"; label: string } {
  if (available <= 0) return { tone: "destructive", label: "Rupture" };
  if (low) return { tone: "warning", label: "Stock bas" };
  return { tone: "success", label: "OK" };
}

/** "Ajuster le stock" — adjustment (in/out) or waste, with a note. */
export function AdjustStockPanel({ productId, productName, unit, available, onClose }: {
  productId: Id; productName: string; unit: Unit | string; available: number; onClose: () => void;
}) {
  const [reason, setReason] = useState<"adjustment" | "waste">("adjustment");
  const [dir, setDir] = useState<"in" | "out">("in");
  const [qty, setQty] = useState("");
  const [note, setNote] = useState("");
  const n = Number(qty.replace(",", "."));
  const valid = Number.isFinite(n) && n > 0;
  const delta = !valid ? 0 : reason === "waste" || dir === "out" ? -n : n;

  const adjust = useApiMutation(api.stock.adjust, {
    success: reason === "waste" ? "Perte enregistrée" : "Stock ajusté",
    invalidate: [qk.stock.all, qk.products.all, qk.dashboard],
    onSuccess: onClose,
  });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    adjust.mutate({ productId, qty: delta, reason, note: note.trim() || undefined });
  };

  return (
    <SidePanel
      title="Ajuster le stock"
      subtitle={productName}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Annuler</Button>
          <Button variant="primary" type="submit" form="adjust-stock" loading={adjust.isPending} disabled={!valid}>
            {reason === "waste" ? "Déclarer la perte" : "Enregistrer"}
          </Button>
        </>
      }
    >
      <form id="adjust-stock" onSubmit={submit} className="flex flex-col gap-3.5">
        <Field label="Motif">
          <Segmented value={reason} onChange={setReason} options={[{ id: "adjustment", label: "Ajustement" }, { id: "waste", label: "Perte / casse" }]} />
        </Field>
        {reason === "adjustment" ? (
          <Field label="Sens">
            <Segmented value={dir} onChange={setDir} options={[{ id: "in", label: "Entrée (+)" }, { id: "out", label: "Sortie (−)" }]} />
          </Field>
        ) : null}
        <Field label={`Quantité (${unit})`} hint={reason === "waste" ? "Retirée des lots en FEFO (DLC la plus proche d'abord)." : dir === "out" ? "Retirée des lots en FEFO." : "Crée un nouveau lot."}>
          <Input autoFocus inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="0" className="num" />
        </Field>
        <Field label="Note">
          <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder={reason === "waste" ? "Ex. : odeur, casse en chambre froide" : "Ex. : écart d'inventaire"} />
        </Field>
        <div className="flex items-center justify-between rounded-[4px] border border-border bg-muted/40 px-3 py-2 text-[12.5px]">
          <span className="text-muted-foreground">Disponible après</span>
          <span className="flex items-center gap-2">
            <Qty value={available} unit={unit} className="text-muted-foreground" />
            <span className="text-muted-foreground">→</span>
            <Qty value={Math.round((available + delta) * 1000) / 1000} unit={unit} tone={available + delta <= 0 ? "destructive" : undefined} className="font-medium" />
          </span>
        </div>
      </form>
    </SidePanel>
  );
}

/** Lots table (FEFO) as a framed DataTable. */
export function LotsTable({ lots, unit, today, supplierName, empty, compact }: {
  lots: Lot[]; unit: Unit | string; today: IsoDate; supplierName?: (id?: Id) => string | undefined; empty?: React.ReactNode; compact?: boolean;
}) {
  const rows = fefo(lots);
  return (
    <DataTable
      inset
      pageKey="lotsPage"
      columns={lotColumns(unit, today, supplierName).filter((c) => !compact || (c.id !== "received" && c.id !== "qtyReceived"))}
      rows={rows}
      getRowId={(l) => l.id}
      empty={empty}
    />
  );
}
