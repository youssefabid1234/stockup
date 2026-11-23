/**
 * Creating a document, identical on both sides: the "Nouvelle commande" button opens a compact command-style picker
 * anchored to it (type to search the client / supplier, ↑↓ Enter), which creates an empty draft and opens its page.
 * Partner pages skip the picker and call `useCreateDocument(kind)` directly.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import type { Id } from "@kit/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { CLIENT_TYPE_LABEL } from "@/lib/labels";
import { qk, useApiMutation, useClients, useSuppliers } from "@/lib/queries";
import { useDebounced } from "@/lib/url-state";
import { AnchoredPopover, Button, Mono, Spinner, StatusDot, type ButtonProps } from "@/ui";
import { KIND, type DocKind } from "./model";

/** Creates an empty draft for this partner, toasts, then navigates to its detail page. */
export function useCreateDocument(kind: DocKind) {
  const navigate = useNavigate();
  return useApiMutation(
    async (partnerId: Id) => {
      const d = kind === "sale"
        ? await api.orders.create({ clientId: partnerId, source: "manual" })
        : await api.purchaseOrders.create({ supplierId: partnerId, lines: [] });
      return { id: d.id, number: d.number };
    },
    {
      success: (d) => (kind === "sale" ? `Pré-commande ${d.number} créée` : `Commande d'achat ${d.number} créée`),
      invalidate: kind === "sale" ? [qk.orders.all, qk.dashboard] : [qk.purchaseOrders.all, qk.suppliers.all],
      onSuccess: (d) => navigate(`${KIND[kind].detailPath}/${d.id}`),
    },
  );
}

interface PartnerOption { id: Id; name: string; code?: string; detail: string; status?: string }

/** Primary button + anchored partner picker. `open`/`onOpenChange` let the page drive it from the URL (?new=1). */
export function NewDocumentButton({ kind, open: openProp, onOpenChange, size, variant = "primary", label }: {
  kind: DocKind; open?: boolean; onOpenChange?: (o: boolean) => void; size?: ButtonProps["size"]; variant?: ButtonProps["variant"]; label?: string;
}) {
  const [openLocal, setOpenLocal] = useState(false);
  const open = openProp ?? openLocal;
  const setOpen = (o: boolean) => { setOpenLocal(o); onOpenChange?.(o); };
  const anchorRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <Button ref={anchorRef} variant={variant} size={size} icon={Plus} aria-expanded={open} aria-haspopup="listbox" onClick={() => setOpen(!open)}>
        {label ?? KIND[kind].newLabel}
      </Button>
      {open ? <PartnerPicker kind={kind} anchorRef={anchorRef} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function PartnerPicker({ kind, anchorRef, onClose }: { kind: DocKind; anchorRef: React.RefObject<HTMLButtonElement>; onClose: () => void }) {
  const sale = kind === "sale";
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const dq = useDebounced(q, 120);
  const popRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const clients = useClients(sale ? { q: dq } : undefined);
  const suppliers = useSuppliers();
  const create = useCreateDocument(kind);

  const options = useMemo<PartnerOption[]>(() => {
    if (sale) {
      return (clients.data ?? []).filter((c) => c.status !== "prospect" || dq).slice(0, 40)
        .map((c) => ({ id: c.id, name: c.name, code: c.code, status: c.status, detail: [CLIENT_TYPE_LABEL[c.type], c.city, c.zone].filter(Boolean).join(" · ") }));
    }
    const f = fold(dq.trim());
    return (suppliers.data ?? []).filter((s) => !f || fold(`${s.name} ${s.city} ${(s.tags ?? []).join(" ")}`).includes(f))
      .sort((a, b) => a.name.localeCompare(b.name, "fr")).slice(0, 40)
      .map((s) => ({ id: s.id, name: s.name, detail: [s.city, `délai ${s.leadTimeDays} j`, s.minOrderAmount ? `min. ${s.minOrderAmount.toLocaleString("fr-FR")} €` : ""].filter(Boolean).join(" · ") }));
  }, [sale, clients.data, suppliers.data, dq]);
  const loading = sale ? clients.isLoading && !clients.data : suppliers.isLoading && !suppliers.data;

  useEffect(() => { setActive(0); }, [dq]);
  useEffect(() => { listRef.current?.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" }); }, [active]);
  // Close on outside click (the button itself toggles).
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (popRef.current?.contains(t) || anchorRef.current?.contains(t)) return;
      onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [onClose, anchorRef]);

  const pick = (o?: PartnerOption) => { if (o && !create.isPending) create.mutate(o.id, { onSuccess: onClose }); };

  return (
    <AnchoredPopover anchorRef={anchorRef} open matchWidth={false} width={380} maxHeight={420} role="dialog" aria-label={KIND[kind].newLabel}>
      <div ref={popRef} className="flex flex-col">
        <div className="border-b border-border px-3 pb-2 pt-2.5">
          <div className="mb-1.5 text-[11.5px] text-muted-foreground">
            {sale ? "Choisissez le client : la commande est créée en pré-commande." : "Choisissez le fournisseur : la commande est créée en brouillon."}
          </div>
          <div className="relative">
            <Search size={13} strokeWidth={1.75} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              value={q}
              role="combobox"
              aria-expanded
              aria-controls="partner-picker-list"
              aria-label={sale ? "Rechercher un client" : "Rechercher un fournisseur"}
              placeholder={sale ? "Nom, code, ville…" : "Nom, ville, groupe…"}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, options.length - 1)); }
                if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                if (e.key === "Enter") { e.preventDefault(); pick(options[active]); }
                if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); anchorRef.current?.focus(); }
              }}
              className="h-8 w-full rounded-[4px] border border-border bg-card pl-7 pr-7 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-border-hover focus:border-ring focus:ring-2 focus:ring-ring/20"
            />
            {(sale && clients.isFetching) || create.isPending ? <Spinner size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground" /> : null}
          </div>
        </div>
        {loading ? (
          <div className="flex justify-center py-5 text-muted-foreground"><Spinner /></div>
        ) : options.length === 0 ? (
          <div className="px-3 py-4 text-center text-[12.5px] text-muted-foreground">{sale ? "Aucun client" : "Aucun fournisseur"} ne correspond.</div>
        ) : (
          <ul ref={listRef} id="partner-picker-list" role="listbox" className="max-h-[320px] overflow-auto py-1">
            {options.map((o, i) => (
              <li key={o.id} data-i={i} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  disabled={create.isPending}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(o)}
                  className={cn("flex w-full items-center gap-3 px-3 py-1.5 text-left", i === active ? "bg-muted" : "hover:bg-muted/60")}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[13px] font-medium">{o.name}</span>
                      {o.code ? <Mono className="text-[11px] text-muted-foreground">{o.code}</Mono> : null}
                    </div>
                    <div className="truncate text-[11.5px] text-muted-foreground">{o.detail}</div>
                  </div>
                  {o.status && o.status !== "active" ? <StatusDot kind="client" value={o.status} /> : null}
                  {create.isPending && create.variables === o.id ? <Spinner size={12} /> : null}
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="border-t border-border px-3 py-1.5 text-[11px] text-muted-foreground">
          ↑↓ pour naviguer · Entrée pour créer · Échap pour fermer
        </div>
      </div>
    </AnchoredPopover>
  );
}

const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
