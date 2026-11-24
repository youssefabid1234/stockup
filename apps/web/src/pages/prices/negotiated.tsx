/** Prix négociés tab: every ClientPrice (client × product), inline edit (PUT), delete, add. */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Handshake, Plus } from "lucide-react";
import type { Id } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtMoney, UNIT_LABEL } from "@/lib/format";
import { qk, useApiMutation, useClients, useProducts, useResolvedPrice } from "@/lib/queries";
import { Button, DataTable, EmptyState, Input, Money, Mono, TagList, type Column } from "@/ui";
import { Combobox, DeltaCell, MarginCell, PriceInput, SourceLabel, useClientOptions, useProductOptions } from "./pickers";
import { InlineConfirmDelete } from "./rules";
import { ruleNameOf } from "./resolved";

export interface NegotiatedRow {
  key: string;
  clientId: Id;
  clientName: string;
  clientCode: string;
  clientTags: string[];
  productId: Id;
  productName: string;
  sku: string;
  unit: string;
  price: number;
  listPrice: number;
  cost: number;
}

/** All client prices, assembled from the client details (cached per client, shared with the client page). */
export function useNegotiatedPrices() {
  const { data: clients } = useClients();
  const { data: products } = useProducts();
  const results = useQueries({
    queries: (clients ?? []).map((c) => ({ queryKey: qk.clients.detail(c.id), queryFn: () => api.clients.get(c.id), staleTime: 30_000 })),
  });
  const loading = !clients || results.some((r) => r.isLoading);
  const rows = useMemo(() => {
    if (!clients) return undefined;
    const pm = new Map((products ?? []).map((p) => [p.id, p] as const));
    const out: NegotiatedRow[] = [];
    results.forEach((r, i) => {
      const c = clients[i];
      if (!r.data || !c) return;
      for (const cp of r.data.prices ?? []) {
        const p = pm.get(cp.productId);
        out.push({
          key: `${c.id}|${cp.productId}`,
          clientId: c.id, clientName: c.name, clientCode: c.code, clientTags: c.tags ?? [],
          productId: cp.productId, productName: cp.productName, sku: p?.sku ?? "", unit: p?.unit ?? "",
          price: cp.price, listPrice: cp.listPrice, cost: p?.cost ?? 0,
        });
      }
    });
    return out;
    // results identity changes every render; depend on the data stamps instead.
  }, [clients, products, results.map((r) => r.dataUpdatedAt).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  return { rows, loading };
}

export function NegotiatedTab({ clientId, clientTag, productId, q, adding, onCloseAdd, onAdd }: {
  clientId: string; clientTag: string; productId: string; q: string; adding: boolean; onCloseAdd: () => void; onAdd: () => void;
}) {
  const { rows, loading } = useNegotiatedPrices();
  const filtered = useMemo(() => {
    if (!rows) return undefined;
    const n = q.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (!clientId || r.clientId === clientId) &&
        (!clientTag || r.clientTags.includes(clientTag)) &&
        (!productId || r.productId === productId) &&
        (!n || `${r.clientName} ${r.productName} ${r.sku}`.toLowerCase().includes(n)),
    );
  }, [rows, clientId, clientTag, productId, q]);

  const qc = useQueryClient();
  const invalidateClient = (id: Id) => void qc.invalidateQueries({ queryKey: qk.clients.detail(id) });
  const put = useApiMutation((v: { clientId: Id; productId: Id; price: number }) => api.prices.setClientPrice(v.clientId, v.productId, v.price), {
    success: (cp) => `Prix négocié : ${fmtMoney(cp.price)}`,
    invalidate: [qk.pricing.all],
    onSuccess: (_, v) => invalidateClient(v.clientId),
  });
  const remove = useApiMutation((v: { clientId: Id; productId: Id }) => api.prices.removeClientPrice(v.clientId, v.productId), {
    success: "Prix négocié supprimé",
    invalidate: [qk.pricing.all],
    onSuccess: (_, v) => invalidateClient(v.clientId),
  });

  const columns: Column<NegotiatedRow>[] = [
    {
      id: "client", header: "Client", sortValue: (r) => r.clientName, className: "w-1/2 max-w-0",
      cell: (r) => (
        <span className="flex min-w-0 items-center gap-2">
          <Link to={`/clients/${r.clientId}`} className="truncate font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{r.clientName}</Link>
          <TagList scope="client" tags={r.clientTags} max={1} className="shrink-0 flex-nowrap" />
        </span>
      ),
    },
    {
      id: "product", header: "Produit", sortValue: (r) => r.productName, className: "w-1/2 max-w-0",
      cell: (r) => (
        <span className="flex min-w-0 items-center gap-2">
          <Link to={`/products/${r.productId}`} className="truncate hover:underline" onClick={(e) => e.stopPropagation()}>{r.productName}</Link>
          <Mono className="hidden shrink-0 text-[11px] text-muted-foreground 2xl:inline">{r.sku}</Mono>
        </span>
      ),
    },
    { id: "unit", header: "Unité", width: 64, muted: true, cell: (r) => UNIT_LABEL[r.unit as keyof typeof UNIT_LABEL] ?? r.unit },
    { id: "list", header: "Catalogue", width: 100, numeric: true, sortValue: (r) => r.listPrice, cell: (r) => <Money value={r.listPrice} className="text-muted-foreground" /> },
    {
      id: "price", header: "Négocié", width: 120, numeric: true, sortValue: (r) => r.price, className: "py-0 pr-2",
      cell: (r) => (
        <PriceInput value={r.price} tone={r.price < r.cost ? "destructive" : undefined}
          onCommit={(price) => put.mutate({ clientId: r.clientId, productId: r.productId, price })} />
      ),
    },
    { id: "delta", header: "Écart", width: 80, numeric: true, sortValue: (r) => (r.price - r.listPrice) / (r.listPrice || 1), cell: (r) => <DeltaCell price={r.price} list={r.listPrice} /> },
    { id: "margin", header: "Marge", width: 90, numeric: true, sortValue: (r) => (r.price - r.cost) / r.price, cell: (r) => <MarginCell value={r.price ? (r.price - r.cost) / r.price : 0} /> },
    {
      id: "actions", header: "", width: 100, align: "right",
      cell: (r) => <span className="flex justify-end"><InlineConfirmDelete onConfirm={() => remove.mutate({ clientId: r.clientId, productId: r.productId })} label="Supprimer le prix négocié" /></span>,
    },
  ];

  const any = !!(clientId || clientTag || productId || q);
  return (
    <div className="flex min-h-full flex-col">
      {adding ? <AddBar onClose={onCloseAdd} defaultClientId={clientId} onAdded={(v) => invalidateClient(v)} existing={rows} /> : null}
      <DataTable
        columns={columns}
        rows={filtered}
        loading={loading && !filtered?.length}
        getRowId={(r) => r.key}
        defaultSort={{ id: "client", dir: "asc" }}
        pageKey="cpPage"
        footer={filtered ? `${filtered.length} prix négocié${filtered.length > 1 ? "s" : ""}${any ? " · filtrés" : ""}${filtered.length ? ` · écart moyen ${avgDelta(filtered)}` : ""}` : undefined}
        empty={
          any ? <EmptyState icon={Handshake} title="Aucun prix négocié ne correspond" description="Modifiez les filtres." />
            : <EmptyState icon={Handshake} title="Aucun prix négocié" description="Un prix négocié fixe le prix d'un produit pour un client. Il prime sur toutes les règles." action={<Button size="sm" icon={Plus} onClick={onAdd}>Nouveau prix négocié</Button>} />
        }
      />
    </div>
  );
}

function avgDelta(rows: NegotiatedRow[]) {
  const ds = rows.filter((r) => r.listPrice).map((r) => (r.price - r.listPrice) / r.listPrice);
  if (!ds.length) return "—";
  const a = ds.reduce((s, x) => s + x, 0) / ds.length;
  return `${a < 0 ? "−" : "+"}${Math.abs(a * 100).toFixed(1).replace(".", ",")} %`;
}

function AddBar({ onClose, defaultClientId, onAdded, existing }: { onClose: () => void; defaultClientId?: string; onAdded: (clientId: Id) => void; existing?: NegotiatedRow[] }) {
  const [clientId, setClientId] = useState(defaultClientId ?? "");
  const [productId, setProductId] = useState("");
  const [price, setPrice] = useState("");
  const clientOptions = useClientOptions();
  const productOptions = useProductOptions();
  const current = useResolvedPrice({ clientId, productId, qty: 1 });
  const n = Number(price.replace(/\s/g, "").replace(",", "."));
  const ok = clientId && productId && price.trim() && Number.isFinite(n) && n > 0;
  const already = existing?.some((r) => r.clientId === clientId && r.productId === productId);
  const add = useApiMutation((v: { clientId: Id; productId: Id; price: number }) => api.prices.setClientPrice(v.clientId, v.productId, v.price), {
    success: (cp) => `Prix négocié enregistré : ${fmtMoney(cp.price)}`,
    invalidate: [qk.pricing.all],
    onSuccess: (_, v) => { onAdded(v.clientId); setProductId(""); setPrice(""); },
  });
  const r = current.data && current.data.productId === productId && current.data.clientId === clientId ? current.data : undefined;
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (ok) add.mutate({ clientId, productId, price: Math.round(n * 100) / 100 }); }}
      onKeyDown={(e) => { if (e.key === "Escape" && !e.defaultPrevented) onClose(); }}
      className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/30 px-4 py-2.5"
    >
      <Combobox value={clientId} onChange={setClientId} options={clientOptions} placeholder="Client…" size="sm" width={240} autoFocus={!clientId} />
      <Combobox value={productId} onChange={setProductId} options={productOptions} placeholder="Produit…" size="sm" width={260} autoFocus={!!clientId} />
      <div className="relative w-[96px]">
        <Input size="sm" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder={r ? String(r.price).replace(".", ",") : "Prix"} className="num pr-6 text-right" />
        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-[12px] text-muted-foreground">€</span>
      </div>
      <Button size="sm" variant="primary" type="submit" disabled={!ok} loading={add.isPending}>{already ? "Remplacer" : "Ajouter"}</Button>
      <Button size="sm" variant="ghost" onClick={onClose}>Fermer</Button>
      {r ? (
        <span className="ml-2 flex min-w-0 items-center gap-2 text-[12px] text-muted-foreground">
          Aujourd'hui <span className="font-medium text-foreground">{fmtMoney(r.price)}</span>
          <SourceLabel source={r.source} ruleName={ruleNameOf(r.candidates.find((c) => c.applied)?.label ?? "")} />
          · catalogue {fmtMoney(r.listPrice)} · coût {fmtMoney(r.cost)}
          {Number.isFinite(n) && n > 0 ? <> · marge <MarginCell value={(n - r.cost) / n} /></> : null}
        </span>
      ) : null}
    </form>
  );
}
