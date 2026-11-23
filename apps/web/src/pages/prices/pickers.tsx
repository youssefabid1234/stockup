/** Searchable pickers for the pricing screens (client, product, group) + small shared cells. */
import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import type { PriceSource } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtPercent } from "@/lib/format";
import { useClients, useProducts, useTags } from "@/lib/queries";
import type { TagScope } from "@/lib/api";
import { AnchoredPopover, Dot, TagDot, type Tone } from "@/ui";

export interface ComboOption { value: string; label: string; sub?: string; dot?: React.ReactNode; group?: string }

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Text input that filters a list in a popover; shows the chosen label when closed. */
export function Combobox({ value, onChange, options, placeholder = "Choisir…", size = "md", clearable, className, autoFocus, width }: {
  value: string;
  onChange: (v: string) => void;
  options: ComboOption[];
  placeholder?: string;
  size?: "md" | "sm";
  clearable?: boolean;
  className?: string;
  autoFocus?: boolean;
  width?: number;
}) {
  const anchorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const selected = options.find((o) => o.value === value);
  const list = useMemo(() => {
    const n = norm(q.trim());
    const r = n ? options.filter((o) => norm(`${o.label} ${o.sub ?? ""}`).includes(n)) : options;
    return r.slice(0, 200);
  }, [options, q]);
  useEffect(() => setActive(0), [q, open]);

  const pick = (v: string) => { onChange(v); setOpen(false); setQ(""); inputRef.current?.blur(); };
  const h = size === "md" ? "h-8 text-[13px]" : "h-[26px] text-[12.5px]";

  return (
    <div ref={anchorRef} className={cn("relative", className)} style={width ? { width } : undefined}>
      <input
        ref={inputRef}
        autoFocus={autoFocus}
        value={open ? q : selected?.label ?? ""}
        placeholder={selected ? selected.label : placeholder}
        onFocus={() => setOpen(true)}
        onBlur={() => { setOpen(false); setQ(""); }}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(list.length - 1, a + 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
          else if (e.key === "Enter") { e.preventDefault(); if (list[active]) pick(list[active].value); }
          else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); inputRef.current?.blur(); }
        }}
        className={cn(
          "w-full truncate rounded-[4px] border border-border bg-card pl-2.5 pr-7 text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-border-hover focus:border-ring focus:ring-2 focus:ring-ring/20",
          h,
        )}
      />
      {clearable && value ? (
        <button
          type="button"
          aria-label="Effacer"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => onChange("")}
          className="absolute inset-y-0 right-1.5 my-auto grid size-5 place-items-center rounded-[3px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={12} strokeWidth={2} />
        </button>
      ) : (
        <ChevronDown size={13} strokeWidth={1.75} className="pointer-events-none absolute inset-y-0 right-2 my-auto text-muted-foreground" />
      )}
      <AnchoredPopover anchorRef={anchorRef} open={open} matchWidth width={Math.max(width ?? 0, 260)} maxHeight={300} role="listbox">
        <div className="py-1">
          {list.map((o, i) => {
            const header = o.group && (i === 0 || list[i - 1].group !== o.group);
            return (
              <div key={o.value}>
                {header ? <div className="px-2.5 pb-0.5 pt-1.5 text-[10.5px] font-semibold uppercase tracking-[.08em] text-muted-foreground">{o.group}</div> : null}
                <button
                  type="button"
                  role="option"
                  aria-selected={o.value === value}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(o.value)}
                  className={cn("flex h-7 w-full items-center gap-2 px-2.5 text-left text-[13px]", i === active && "bg-muted", o.value === value && "font-medium")}
                >
                  {o.dot}
                  <span className="min-w-0 flex-1 truncate">{o.label}</span>
                  {o.sub ? <span className="shrink-0 truncate text-[11.5px] text-muted-foreground">{o.sub}</span> : null}
                </button>
              </div>
            );
          })}
          {!list.length ? <div className="px-2.5 py-2 text-[12.5px] text-muted-foreground">Aucun résultat</div> : null}
        </div>
      </AnchoredPopover>
    </div>
  );
}

/** Multi-select with search (popover checklist). Trigger: "Choisir…" / "3 clients". `max` disables the rest once reached. */
export function MultiCombobox({ value, onChange, options, placeholder = "Choisir…", unit, max, width = 240 }: {
  value: string[];
  onChange: (v: string[]) => void;
  options: ComboOption[];
  placeholder?: string;
  unit: [string, string];
  max?: number;
  width?: number;
}) {
  const anchorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const set = useMemo(() => new Set(value), [value]);
  const list = useMemo(() => {
    const n = norm(q.trim());
    const r = n ? options.filter((o) => norm(`${o.label} ${o.sub ?? ""}`).includes(n)) : options;
    // Chosen ones first so they're easy to remove.
    return [...r.filter((o) => set.has(o.value)), ...r.filter((o) => !set.has(o.value))].slice(0, 200);
  }, [options, q, set]);
  useEffect(() => setActive(0), [q, open]);
  const full = max !== undefined && value.length >= max;
  const toggle = (v: string) => {
    if (set.has(v)) onChange(value.filter((x) => x !== v));
    else if (!full) onChange([...value, v]);
  };
  const summary = value.length === 0 ? "" : value.length === 1 ? options.find((o) => o.value === value[0])?.label ?? "1 " + unit[0]
    : `${value.length} ${unit[1]}`;

  return (
    <div ref={anchorRef} className="relative" style={{ width }}>
      <input
        ref={inputRef}
        value={open ? q : summary}
        placeholder={open ? "Chercher…" : placeholder}
        onFocus={() => setOpen(true)}
        onBlur={() => { setOpen(false); setQ(""); }}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(list.length - 1, a + 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
          else if (e.key === "Enter") { e.preventDefault(); if (list[active]) toggle(list[active].value); }
          else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); inputRef.current?.blur(); }
        }}
        className="h-[26px] w-full truncate rounded-[4px] border border-border bg-card pl-2.5 pr-7 text-[12.5px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-border-hover focus:border-ring focus:ring-2 focus:ring-ring/20"
      />
      <ChevronDown size={13} strokeWidth={1.75} className="pointer-events-none absolute inset-y-0 right-2 my-auto text-muted-foreground" />
      <AnchoredPopover anchorRef={anchorRef} open={open} matchWidth={false} width={Math.max(width, 280)} maxHeight={340} role="listbox" aria-label={placeholder}>
        {max !== undefined ? (
          <div className="flex h-7 items-center justify-between border-b border-border px-2.5 text-[11.5px] text-muted-foreground">
            <span>{value.length} / {max} {unit[1]}</span>
            {value.length ? (
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => onChange([])} className="hover:text-foreground">Tout retirer</button>
            ) : null}
          </div>
        ) : null}
        <div className="py-1">
          {list.map((o, i) => {
            const on = set.has(o.value);
            const disabled = !on && full;
            return (
              <button
                key={o.value}
                type="button"
                role="option"
                aria-selected={on}
                aria-disabled={disabled || undefined}
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => toggle(o.value)}
                className={cn("flex h-7 w-full items-center gap-2 px-2.5 text-left text-[13px]", i === active && "bg-muted", disabled && "opacity-45")}
              >
                <span className={cn("grid size-3.5 shrink-0 place-items-center rounded-[3px] border", on ? "border-primary bg-primary text-primary-foreground" : "border-border-hover")}>
                  {on ? <Check size={10} strokeWidth={3} /> : null}
                </span>
                {o.dot}
                <span className="min-w-0 flex-1 truncate">{o.label}</span>
                {o.sub ? <span className="shrink-0 truncate text-[11.5px] text-muted-foreground">{o.sub}</span> : null}
              </button>
            );
          })}
          {!list.length ? <div className="px-2.5 py-2 text-[12.5px] text-muted-foreground">Aucun résultat</div> : null}
        </div>
      </AnchoredPopover>
    </div>
  );
}

export function useClientOptions(): ComboOption[] {
  const { data } = useClients();
  return useMemo(() => (data ?? []).slice().sort((a, b) => a.name.localeCompare(b.name)).map((c) => ({ value: c.id, label: c.name, sub: c.code })), [data]);
}
export function useProductOptions(): ComboOption[] {
  const { data } = useProducts();
  return useMemo(
    () => (data ?? []).filter((p) => p.active).sort((a, b) => a.name.localeCompare(b.name)).map((p) => ({ value: p.id, label: p.name, sub: p.sku })),
    [data],
  );
}
export function useTagOptions(scope: TagScope): ComboOption[] {
  const { data } = useTags(scope);
  return useMemo(
    () => (data ?? []).map((t) => ({ value: t.id, label: t.label, sub: `${t.count}`, dot: <TagDot color={t.color} /> })),
    [data],
  );
}

// ── Cells ──

export const SOURCE_META: Record<PriceSource, { label: string; tone: Tone }> = {
  client_price: { label: "Négocié", tone: "violet" },
  rule: { label: "Règle", tone: "info" },
  list: { label: "Catalogue", tone: "muted" },
};

/** Dot + word: Négocié / Règle « nom » / Catalogue. */
export function SourceLabel({ source, ruleName, className }: { source: PriceSource; ruleName?: string; className?: string }) {
  const m = SOURCE_META[source];
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5 text-[12.5px] text-secondary-foreground", className)} title={ruleName ? `Règle « ${ruleName} »` : m.label}>
      <Dot tone={m.tone} />
      <span className="truncate">{source === "rule" && ruleName ? <>Règle <span className="text-muted-foreground">« {ruleName} »</span></> : m.label}</span>
    </span>
  );
}

export const LOW_MARGIN = 0.15;
/** Margin % with warning tone under 15 % (destructive when negative). */
export function MarginCell({ value, className }: { value: number; className?: string }) {
  const tone = value < 0 ? "text-destructive" : value < LOW_MARGIN ? "text-warning" : "text-secondary-foreground";
  return (
    <span className={cn("num inline-flex items-center gap-1.5 tabular-nums", tone, className)}>
      {value < LOW_MARGIN ? <span className={cn("size-1.5 rounded-full", value < 0 ? "bg-destructive" : "bg-warning")} /> : null}
      {fmtPercent(value)}
    </span>
  );
}

/** Signed discount vs list price: "−8 %", "+3 %", "—". */
export function deltaPct(price: number, list: number) {
  if (!list) return 0;
  return (price - list) / list;
}
export function DeltaCell({ price, list }: { price: number; list: number }) {
  const d = deltaPct(price, list);
  if (Math.abs(d) < 0.0005) return <span className="text-muted-foreground">—</span>;
  return <span className={cn("num tabular-nums", d < 0 ? "text-secondary-foreground" : "text-info")}>{d > 0 ? "+" : "−"}{fmtPercent(Math.abs(d))}</span>;
}

const parseNum = (s: string) => {
  const n = Number(s.replace(/\s/g, "").replace(",", "."));
  return s.trim() === "" || !Number.isFinite(n) ? NaN : n;
};
const showNum = (n: number | undefined) => (n == null ? "" : n.toFixed(2).replace(".", ","));

/** Borderless-until-hover € input for tables. Commits on blur/Enter when changed and > 0; Esc reverts. */
export function PriceInput({ value, onCommit, className, tone }: { value: number; onCommit: (v: number) => void; className?: string; tone?: "warning" | "destructive" }) {
  const [draft, setDraft] = useState(showNum(value));
  const focused = useRef(false);
  const cancelled = useRef(false);
  useEffect(() => { if (!focused.current) setDraft(showNum(value)); }, [value]);
  const commit = () => {
    if (cancelled.current) { cancelled.current = false; return; }
    const n = parseNum(draft);
    if (Number.isNaN(n) || n <= 0) { setDraft(showNum(value)); return; }
    if (Math.abs(n - value) > 1e-9) onCommit(Math.round(n * 100) / 100);
  };
  return (
    <span className={cn("inline-flex items-center justify-end gap-1", className)} onClick={(e) => e.stopPropagation()}>
      <input
        inputMode="decimal"
        value={draft}
        aria-label="Prix négocié"
        onFocus={(e) => { focused.current = true; e.currentTarget.select(); }}
        onBlur={() => { focused.current = false; commit(); }}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancelled.current = true; setDraft(showNum(value)); e.currentTarget.blur(); }
        }}
        className={cn(
          "num h-[26px] w-[72px] rounded-[4px] border border-transparent bg-transparent px-1.5 text-right text-[13px] font-medium outline-none transition-colors hover:border-border focus:border-ring focus:bg-card focus:ring-2 focus:ring-ring/20",
          tone === "warning" && "text-warning",
          tone === "destructive" && "text-destructive",
        )}
      />
      <span className="w-2.5 text-[12px] text-muted-foreground">€</span>
    </span>
  );
}
