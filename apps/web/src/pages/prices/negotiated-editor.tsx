/** Set / change / remove the negotiated price of one client × product (PUT/DELETE /clients/:id/prices/:productId). */
import { useState } from "react";
import type { Id, ResolvedPrice } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { qk, useApiMutation } from "@/lib/queries";
import { Button } from "@/ui";
import { MarginCell, PriceInput } from "./pickers";

export function NegotiatedPriceEditor({ clientId, productId, resolved }: { clientId: Id; productId: Id; resolved: ResolvedPrice }) {
  const put = useApiMutation((price: number) => api.prices.setClientPrice(clientId, productId, price), {
    success: (cp) => `Prix négocié : ${fmtMoney(cp.price)}`,
    invalidate: [qk.pricing.all, qk.clients.detail(clientId)],
  });
  const remove = useApiMutation(() => api.prices.removeClientPrice(clientId, productId), {
    success: "Prix négocié supprimé",
    invalidate: [qk.pricing.all, qk.clients.detail(clientId)],
  });
  if (resolved.source === "client_price") {
    return (
      <div className="flex items-center gap-2 text-[13px]">
        <PriceInput value={resolved.price} onCommit={(p) => put.mutate(p)} className="rounded-[4px] border border-border" />
        <Button size="sm" variant="ghost" onClick={() => remove.mutate()} loading={remove.isPending}>Retirer</Button>
        <span className="text-[11.5px] text-muted-foreground">Prime sur toutes les règles</span>
      </div>
    );
  }
  return <NewNegotiated onSave={(p) => put.mutate(p)} pending={put.isPending} suggestion={resolved.price} cost={resolved.cost} />;
}

function NewNegotiated({ onSave, pending, suggestion, cost }: { onSave: (p: number) => void; pending: boolean; suggestion: number; cost: number }) {
  const [v, setV] = useState("");
  const n = Number(v.replace(/\s/g, "").replace(",", "."));
  const ok = !!v.trim() && Number.isFinite(n) && n > 0;
  return (
    <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (ok) onSave(Math.round(n * 100) / 100); }}>
      <div className="relative w-[100px]">
        <input
          inputMode="decimal"
          value={v}
          onChange={(e) => setV(e.target.value)}
          placeholder={suggestion.toFixed(2).replace(".", ",")}
          aria-label="Prix négocié"
          className="num h-[26px] w-full rounded-[4px] border border-border bg-card pl-2 pr-6 text-right text-[12.5px] outline-none hover:border-border-hover focus:border-ring focus:ring-2 focus:ring-ring/20"
        />
        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-[12px] text-muted-foreground">€</span>
      </div>
      <Button size="sm" type="submit" disabled={!ok} loading={pending}>Fixer ce prix</Button>
      {ok ? <span className="text-[11.5px] text-muted-foreground">marge <MarginCell value={(n - cost) / n} /></span>
        : <span className="text-[11.5px] text-muted-foreground">Prime sur toutes les règles</span>}
    </form>
  );
}
