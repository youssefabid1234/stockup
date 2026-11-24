/** Inline-edit primitives for sale and purchase documents (borderless until hover/focus, commit on blur/Enter, Esc reverts),
 *  and the product search used to add lines. */
import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import type { Id, ProductSummary } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtMoney, fmtQty, UNIT_LABEL } from "@/lib/format";
import { useQueries } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { qk, useSearch } from "@/lib/queries";
import { useDebounced } from "@/lib/url-state";
import { AnchoredPopover, Spinner } from "@/ui";

const CELL =
  "h-[26px] w-full rounded-[4px] border border-transparent bg-transparent px-1.5 text-[13px] text-foreground outline-none transition-colors hover:border-border focus:border-ring focus:bg-card focus:ring-2 focus:ring-ring/20 disabled:opacity-60 placeholder:text-muted-foreground/60";

const parseNum = (s: string) => {
  const n = Number(s.replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
};
const showNum = (n: number | undefined) => (n == null ? "" : String(n).replace(".", ","));

/** Numeric inline input. Calls onCommit only when the value actually changed and is valid. */
export function NumberCell({ value, onCommit, suffix, min = 0, disabled, className, placeholder, tone, compact, label }: {
  value: number | undefined; onCommit: (v: number) => void; suffix?: string; min?: number; disabled?: boolean;
  /** Accessible name ("Quantité : Bar de ligne"), the cell has no visible label. */
  label?: string;
  className?: string; placeholder?: string; tone?: "warning" | "destructive";
  /** Narrower input + suffix sized to its text when it is a single symbol ("€"). For dense tables. */
  compact?: boolean;
}) {
  const [draft, setDraft] = useState(showNum(value));
  const focused = useRef(false);
  const cancelled = useRef(false);
  useEffect(() => { if (!focused.current) setDraft(showNum(value)); }, [value]);
  const commit = () => {
    if (cancelled.current) { cancelled.current = false; return; }
    const n = parseNum(draft);
    if (draft.trim() === "" || Number.isNaN(n) || n < min) { setDraft(showNum(value)); return; }
    if (n !== value) onCommit(n);
  };
  return (
    <span className={cn("inline-flex items-center justify-end gap-1", className)}>
      <input
        inputMode="decimal"
        aria-label={label}
        value={draft}
        disabled={disabled}
        placeholder={placeholder}
        onFocus={(e) => { focused.current = true; e.currentTarget.select(); }}
        onBlur={() => { focused.current = false; commit(); }}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; setDraft(showNum(value)); e.currentTarget.blur(); }
        }}
        className={cn(CELL, "num text-right", compact ? "w-[54px]" : "w-[76px]", tone === "warning" && "text-warning", tone === "destructive" && "text-destructive")}
      />
      {suffix ? <span className={cn("shrink-0 text-left text-[12px] text-muted-foreground", compact && suffix.length <= 1 ? "w-2.5" : "w-8")}>{suffix}</span> : null}
    </span>
  );
}

/** Free-text inline input (line note). */
export function TextCell({ value, onCommit, placeholder, disabled, label }: { value?: string; onCommit: (v: string) => void; placeholder?: string; disabled?: boolean; label?: string }) {
  const [draft, setDraft] = useState(value ?? "");
  const focused = useRef(false);
  const cancelled = useRef(false);
  useEffect(() => { if (!focused.current) setDraft(value ?? ""); }, [value]);
  return (
    <input
      aria-label={label}
      value={draft}
      disabled={disabled}
      placeholder={placeholder}
      onFocus={() => { focused.current = true; }}
      onBlur={() => {
        focused.current = false;
        if (cancelled.current) { cancelled.current = false; return; }
        if (draft.trim() !== (value ?? "")) onCommit(draft.trim());
      }}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; setDraft(value ?? ""); e.currentTarget.blur(); }
      }}
      className={cn(CELL, "text-[12.5px] text-secondary-foreground")}
    />
  );
}

/**
 * Product search with a dropdown. Uses /api/search (fuzzy, accents-insensitive, product aliases: "loup" → Bar),
 * enriched with stock/price from the products list (fetched one by one when a hit is missing from it).
 * The dropdown is portaled (AnchoredPopover) so the lines table frame (overflow-hidden) cannot clip it.
 */
export function ProductPicker({ products, onPick, autoFocus, excludeIds, priceOf }: {
  products: Map<Id, ProductSummary>; onPick: (p: ProductSummary) => void; autoFocus?: boolean; excludeIds?: Set<Id>;
  /** Price shown per hit. Default = catalogue sell price; purchases pass the supplier price (hint "hors catalogue" when missing). */
  priceOf?: (p: ProductSummary) => { price: number; hint?: string };
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const anchorRef = useRef<HTMLDivElement>(null);
  const dq = useDebounced(q, 120);
  const { data, isFetching } = useSearch(dq, ["product"]);
  const hits = useMemo(() => (dq.trim() ? (data ?? []).filter((r) => r.type === "product").slice(0, 8) : []), [data, dq]);

  // Fallback: a hit not in the products map is fetched on its own instead of being silently dropped.
  const missing = hits.filter((r) => !products.has(r.id)).map((r) => r.id);
  const fetched = useQueries({
    queries: missing.map((id) => ({ queryKey: qk.products.detail(id), queryFn: () => api.products.get(id), staleTime: 30_000 })),
  });
  const extra = new Map<Id, ProductSummary>();
  fetched.forEach((f) => { if (f.data) extra.set(f.data.id, f.data); });

  const results = hits
    .map((r) => ({ r, p: products.get(r.id) ?? extra.get(r.id) }))
    .filter((x) => !x.p || x.p.active !== false);

  const pick = (p?: ProductSummary) => {
    if (!p) return;
    onPick(p);
    setQ(""); setOpen(false); setActive(0);
  };
  const showList = open && !!q.trim();

  return (
    <div ref={anchorRef} className="relative">
      <Search size={13} strokeWidth={1.75} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <input
        autoFocus={autoFocus}
        value={q}
        role="combobox"
        aria-expanded={showList}
        aria-autocomplete="list"
        placeholder="Ajouter un produit (nom, alias, SKU)…"
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, results.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); pick(results[Math.min(active, results.length - 1)]?.p); }
          if (e.key === "Escape") {
            if (open && q) { e.preventDefault(); e.stopPropagation(); setOpen(false); }
            else if (q) { e.preventDefault(); e.stopPropagation(); setQ(""); }
          }
        }}
        className="h-7 w-full rounded-[4px] border border-border bg-card pl-7 pr-7 text-[12.5px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-border-hover focus:border-ring focus:ring-2 focus:ring-ring/20"
      />
      {isFetching && dq ? <Spinner size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground" /> : null}
      <AnchoredPopover anchorRef={anchorRef} open={showList} role="listbox" aria-label="Produits" className="py-1">
        {results.length === 0 ? (
          <div className="px-3 py-2 text-[12.5px] text-muted-foreground">{isFetching || q !== dq ? "Recherche…" : "Aucun produit"}</div>
        ) : results.map(({ r, p }, i) => {
          const already = excludeIds?.has(r.id);
          return (
            <button
              key={r.id}
              type="button"
              role="option"
              aria-selected={i === active}
              disabled={!p}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(p)}
              className={cn("flex w-full items-center gap-3 px-3 py-1.5 text-left", i === active ? "bg-muted" : "hover:bg-muted/60")}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-medium">{p?.name ?? r.label}</span>
                  {already ? <span className="text-[11px] text-muted-foreground">déjà sur la commande</span> : null}
                  {p && priceOf?.(p).hint ? <span className="text-[11px] text-warning">{priceOf(p).hint}</span> : null}
                </div>
                <div className="truncate text-[11.5px] text-muted-foreground">
                  {p ? <span className="font-mono text-[11px]">{p.sku}</span> : r.sublabel}
                </div>
              </div>
              {p ? (
                <>
                  <span className={cn("num text-[12px]", p.available <= 0 ? "text-destructive" : "text-muted-foreground")}>
                    {fmtQty(p.available, p.unit)} dispo
                  </span>
                  <span className="num w-[86px] text-right text-[12px]">{fmtMoney(priceOf ? priceOf(p).price : p.price)}<span className="text-muted-foreground">/{UNIT_LABEL[p.unit]}</span></span>
                </>
              ) : <Spinner size={12} className="text-muted-foreground" />}
            </button>
          );
        })}
      </AnchoredPopover>
    </div>
  );
}
