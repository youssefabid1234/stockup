/** Simulateur tab: client + product + qty (+ date) → ResolvedPrice, with every candidate and why it did or didn't apply. */
import { useEffect, useMemo } from "react";
import { Calculator } from "lucide-react";
import { fmtMoney, fmtQty, todayIso } from "@/lib/format";
import { useProducts, useResolvedPrice } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import { DatePicker, EmptyState, ErrorState, Field, Input, SECTION_LABEL } from "@/ui";
import { Combobox, useClientOptions, useProductOptions } from "./pickers";
import { CandidatesList, ResolvedHeadline, ResolvedSkeleton } from "./resolved";

export function SimulatorTab() {
  const [clientId, setClientId] = useUrlState("sclient");
  const [productId, setProductId] = useUrlState("sproduct");
  const [qtyStr, setQty] = useUrlState("sqty", "1");
  const [date, setDate] = useUrlState("sdate");
  const clientOptions = useClientOptions();
  const productOptions = useProductOptions();
  const { data: products } = useProducts();
  const product = useMemo(() => products?.find((p) => p.id === productId), [products, productId]);

  useEffect(() => {
    if (!clientId && clientOptions.length) setClientId(clientOptions[0].value);
  }, [clientId, clientOptions, setClientId]);

  const qty = Number(qtyStr.replace(",", "."));
  const qtyOk = Number.isFinite(qty) && qty > 0;
  const { data, isLoading, isError, refetch } = useResolvedPrice({ clientId, productId, qty: qtyOk ? qty : undefined, date: date || undefined }, qtyOk);
  const r = data && data.clientId === clientId && data.productId === productId ? data : undefined;

  return (
    <div className="grid min-h-full grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="flex flex-col gap-3.5 border-b border-border p-4 lg:border-b-0 lg:border-r">
        <div className={SECTION_LABEL}>Simulation</div>
        <Field label="Client"><Combobox value={clientId} onChange={setClientId} options={clientOptions} placeholder="Chercher un client…" /></Field>
        <Field label="Produit"><Combobox value={productId} onChange={setProductId} options={productOptions} placeholder="Chercher un produit…" autoFocus={!productId} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={`Quantité${product ? ` (${fmtQty(1, product.unit).replace(/^1\s*/, "")})` : ""}`} hint={!qtyOk ? "Quantité invalide" : undefined}>
            <Input inputMode="decimal" value={qtyStr} onChange={(e) => setQty(e.target.value)} className="num" />
          </Field>
          <Field label="Date">
            <DatePicker value={date || todayIso()} onChange={setDate} presets={[{ label: "Aujourd'hui", days: 0 }, { label: "Dans 7 j", days: 7 }, { label: "Dans 30 j", days: 30 }]} />
          </Field>
        </div>
        <p className="text-[11.5px] leading-4 text-muted-foreground">
          Le même calcul que les lignes de commande : prix négocié, puis la règle la plus précise valable à cette date et pour cette quantité, sinon le prix catalogue.
        </p>
      </aside>
      <section className="min-w-0 p-5">
        {!clientId || !productId ? (
          <EmptyState icon={Calculator} title="Choisissez un client et un produit" description="Le simulateur montre le prix appliqué, la marge et toutes les règles envisagées." />
        ) : isError && !r ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !r || isLoading ? (
          <div className="max-w-[760px]"><ResolvedSkeleton /></div>
        ) : (
          <div className="flex max-w-[760px] flex-col gap-6">
            <ResolvedHeadline r={r} />
            {qtyOk && qty !== 1 ? (
              <div className="text-[13px] text-secondary-foreground">
                Ligne de {fmtQty(qty, product?.unit)} : <span className="font-semibold text-foreground">{fmtMoney(r.price * qty)}</span> HT
                <span className="text-muted-foreground"> · marge {fmtMoney((r.price - r.cost) * qty)}</span>
              </div>
            ) : null}
            <div>
              <div className="mb-1 flex items-baseline justify-between">
                <span className={SECTION_LABEL}>Prix candidats</span>
                <span className="text-[11.5px] text-muted-foreground">dans l'ordre de résolution</span>
              </div>
              <div className="rounded-[6px] border border-border px-3">
                <CandidatesList r={r} />
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
