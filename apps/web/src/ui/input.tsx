import {
  forwardRef, Fragment, useEffect, useId, useMemo, useRef, useState,
  type ButtonHTMLAttributes, type InputHTMLAttributes, type KeyboardEvent, type ReactNode, type TextareaHTMLAttributes,
} from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { AnchoredPopover } from "./popover";

const FIELD =
  "w-full rounded-[4px] border border-border bg-card text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-border-hover focus:border-ring focus:ring-2 focus:ring-ring/20 disabled:opacity-50";

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  size?: "md" | "sm";
  leading?: ReactNode;
}

/** <Input value onChange placeholder /> — 32px (sm 26px). `leading` = icon slot. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ size = "md", leading, className, ...rest }, ref) {
  const h = size === "md" ? "h-8" : "h-[26px] text-[12.5px]";
  if (!leading) return <input ref={ref} className={cn(FIELD, h, "px-2.5", className)} {...rest} />;
  return (
    <div className={cn("relative", className)}>
      <span className="pointer-events-none absolute inset-y-0 left-2 flex items-center text-muted-foreground">{leading}</span>
      <input ref={ref} className={cn(FIELD, h, "pl-7 pr-2.5")} {...rest} />
    </div>
  );
});

/** <SearchInput value={q} onChange={setQ} placeholder="Rechercher…" /> — controlled, with clear button. */
export function SearchInput({ value, onChange, placeholder = "Rechercher…", className, autoFocus }: {
  value: string; onChange: (v: string) => void; placeholder?: string; className?: string; autoFocus?: boolean;
}) {
  return (
    <div className={cn("relative w-[220px]", className)}>
      <Search size={13} strokeWidth={1.75} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <input
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape" && value) { e.stopPropagation(); onChange(""); } }}
        placeholder={placeholder}
        className={cn(FIELD, "h-7 pl-7 pr-6 text-[12.5px]")}
      />
      {value ? (
        <button type="button" aria-label="Effacer" onClick={() => onChange("")} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
          <X size={12} strokeWidth={1.75} />
        </button>
      ) : null}
    </div>
  );
}

/* ── Select — Stockline listbox (never the native select element; guarded by scripts/check-no-native-controls.sh) ───────── */
export interface SelectOption {
  value: string;
  label: string;
  /** Muted secondary text after the label. Defaults to the part after " · " in `label` ("Bigouden Marée · Le Guilvinec"). */
  hint?: string;
  disabled?: boolean;
  /** Group heading; consecutive options with the same group are listed under it. */
  group?: string;
}
export interface SelectProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "size" | "onChange" | "value" | "type"> {
  options: SelectOption[];
  value: string;
  onChange: (v: string) => void;
  placeholder?: string; // listed first as the empty choice ("Tous les types"); shown muted when value is ""
  size?: "md" | "sm";
  /** Type-ahead filter field at the top of the list. Default: shown when there are more than 8 options. */
  filterable?: boolean;
  required?: boolean;
}

const SELECT_FILTER_THRESHOLD = 8;
const splitHint = (o: SelectOption) => {
  if (o.hint !== undefined) return { label: o.label, hint: o.hint };
  const i = o.label.indexOf(" · ");
  return i > 0 ? { label: o.label.slice(0, i), hint: o.label.slice(i + 3) } : { label: o.label, hint: "" };
};
const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/**
 * <Select size="sm" value={type} onChange={setType} placeholder="Tous les types" options={[{ value, label, hint?, group?, disabled? }]} />
 * Trigger looks like <Input>; the list is an AnchoredPopover (portal + fixed + flip), so it works inside SidePanels.
 * Keyboard: Enter/Space/↓/↑ open · ↑↓ Home End PgUp PgDn move · type to jump (or filter when > 8 options) · Enter selects ·
 * Esc closes · Tab closes. `name` renders a hidden input for native forms.
 */
export function Select({
  options, value, onChange, placeholder, size = "md", filterable, required, name, className, disabled, id,
  onKeyDown, onClick, ...rest
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const anchorRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const filterRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const typeahead = useRef({ buf: "", at: 0 });
  const autoId = useId();
  const listId = `${id ?? autoId}-list`;
  const optId = (i: number) => `${listId}-${i}`;

  const all = useMemo<SelectOption[]>(
    () => (placeholder !== undefined ? [{ value: "", label: placeholder, hint: "" }, ...options] : options),
    [options, placeholder],
  );
  const showFilter = filterable ?? options.length > SELECT_FILTER_THRESHOLD;
  const items = useMemo(() => {
    const q = fold(query.trim());
    return all.filter((o) => !q || (o.value !== "" && fold(`${o.label} ${o.hint ?? ""}`).includes(q)));
  }, [all, query]);
  const current = all.find((o) => o.value === value);
  const shown = current && (current.value !== "" || placeholder === undefined) ? splitHint(current) : null;
  const isPlaceholder = !value || !current || current.value === "";

  const enabledFrom = (from: number, dir: 1 | -1) => {
    for (let i = from; i >= 0 && i < items.length; i += dir) if (!items[i].disabled) return i;
    return -1;
  };

  const openList = (initialQuery = "") => {
    if (disabled) return;
    setQuery(initialQuery);
    setOpen(true);
  };
  // On open (and when the filtered list changes) put the cursor on the selected item or the first enabled one.
  useEffect(() => {
    if (!open) return;
    const sel = items.findIndex((o) => o.value === value && !o.disabled);
    setActive(sel >= 0 && !query ? sel : enabledFrom(0, 1));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, query]);

  const close = (refocus = true) => {
    setOpen(false);
    setQuery("");
    if (refocus) requestAnimationFrame(() => triggerRef.current?.focus());
  };
  const choose = (o: SelectOption | undefined) => {
    if (!o || o.disabled) return;
    if (o.value !== value) onChange(o.value);
    close();
  };

  useEffect(() => {
    if (!open) return;
    if (showFilter) filterRef.current?.focus();
    const onDown = (e: MouseEvent) => {
      const n = e.target as Node;
      if (listRef.current?.parentElement?.contains(n) || anchorRef.current?.contains(n)) return;
      close(false);
    };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, showFilter]);

  useEffect(() => {
    if (open && active >= 0) document.getElementById(optId(active))?.scrollIntoView({ block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, active]);

  const jump = (ch: string) => {
    const t = typeahead.current;
    const now = Date.now();
    t.buf = now - t.at > 600 ? ch : t.buf + ch;
    t.at = now;
    const q = fold(t.buf);
    const same = q.split("").every((c) => c === q[0]);
    const start = same && q.length > 1 ? active + 1 : t.buf.length === 1 ? active + 1 : Math.max(active, 0);
    for (let k = 0; k < items.length; k++) {
      const i = (start + k) % items.length;
      const o = items[i];
      if (!o.disabled && fold(o.label).startsWith(same ? q[0] : q)) { setActive(i); return; }
    }
  };

  const onListKey = (e: KeyboardEvent<HTMLElement>, fromFilter: boolean) => {
    const k = e.key;
    let next = -2;
    if (k === "ArrowDown") next = active < 0 ? enabledFrom(0, 1) : enabledFrom(active + 1, 1);
    else if (k === "ArrowUp") next = active < 0 ? enabledFrom(items.length - 1, -1) : enabledFrom(active - 1, -1);
    else if (k === "Home") next = enabledFrom(0, 1);
    else if (k === "End") next = enabledFrom(items.length - 1, -1);
    else if (k === "PageDown") next = enabledFrom(Math.min(items.length - 1, Math.max(active, 0) + 8), -1);
    else if (k === "PageUp") next = enabledFrom(Math.max(0, active - 8), 1);
    else if (k === "Enter" || (k === " " && !fromFilter)) { e.preventDefault(); e.stopPropagation(); choose(items[active]); return; }
    else if (k === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    else if (k === "Tab") { if (fromFilter) { e.preventDefault(); close(); } else close(false); return; }
    else if (!fromFilter && k.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); jump(k); return; }
    if (next !== -2) { e.preventDefault(); if (next >= 0) setActive(next); }
  };

  const onTriggerKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    onKeyDown?.(e);
    if (e.defaultPrevented) return;
    if (open) { if (!showFilter) onListKey(e, false); return; }
    const k = e.key;
    if (k === "Enter" || k === " " || k === "ArrowDown" || k === "ArrowUp") { e.preventDefault(); openList(); }
    else if (k.length === 1 && k !== " " && !e.metaKey && !e.ctrlKey && !e.altKey) {
      e.preventDefault();
      if (showFilter) openList(k);
      else { openList(); requestAnimationFrame(() => jump(k)); }
    }
  };

  const isSm = size === "sm";
  // Auto-width (no width class): an invisible stack of every label sizes the trigger like a native select — as wide as
  // its longest option, never shrunk by the header row, no width jump when the value changes.
  const autoWidth = !/(^|\s)(w-|min-w-|max-w-|flex-1|grow|basis-)/.test(className ?? "");
  const sizer = autoWidth ? all.map((o) => splitHint(o)) : [];
  // List at least as wide as the trigger, widened (≤ 360px) so labels + check icon fit without truncation.
  const longest = all.reduce((m, o) => Math.max(m, o.label.length + (o.hint ? o.hint.length + 3 : 0)), 0);
  const popWidth = Math.min(360, Math.max(180, Math.round(longest * 7 + 56)));
  let lastGroup: string | undefined;

  return (
    <div ref={anchorRef} className={cn("relative inline-flex", autoWidth ? "shrink-0" : "min-w-0", className)}>
      <button
        {...rest}
        ref={triggerRef}
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open && !showFilter && active >= 0 ? optId(active) : undefined}
        aria-required={required || undefined}
        disabled={disabled}
        onClick={(e) => { onClick?.(e); if (!e.defaultPrevented) (open ? close() : openList()); }}
        onKeyDown={onTriggerKey}
        className={cn(
          FIELD,
          "flex min-w-0 cursor-default items-center gap-1.5 text-left disabled:pointer-events-none",
          isSm ? "h-[26px] pl-2 pr-1.5 text-[12.5px]" : "h-8 pl-2.5 pr-2 text-[13px]",
          open && "border-ring ring-2 ring-ring/20",
        )}
      >
        <span className="grid min-w-0 flex-1">
          {sizer.map((s, i) => (
            <span key={i} aria-hidden className="invisible h-0 min-w-0 truncate [grid-area:1/1]">{s.label}{s.hint ? ` · ${s.hint}` : ""}</span>
          ))}
          <span className="min-w-0 truncate [grid-area:1/1]">
            {shown ? (
              <>{shown.label}{shown.hint ? <span className="text-muted-foreground"> · {shown.hint}</span> : null}</>
            ) : (
              <span className="text-muted-foreground/70">{placeholder ?? ""}</span>
            )}
          </span>
        </span>
        <ChevronDown size={13} strokeWidth={1.75} aria-hidden className={cn("shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {name ? <input type="hidden" name={name} value={value} /> : null}
      <AnchoredPopover anchorRef={anchorRef} open={open} width={popWidth} maxHeight={showFilter ? 340 : 300} className="animate-fade-in rounded-[4px] p-0">
        <div onKeyDown={(e) => showFilter && onListKey(e, true)}>
          {showFilter ? (
            <div className="sticky top-0 z-[1] flex h-8 items-center gap-2 border-b border-border bg-card px-2.5">
              <Search size={13} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted-foreground" />
              <input
                ref={filterRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filtrer…"
                aria-label="Filtrer les options"
                role="combobox"
                aria-expanded
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={active >= 0 ? optId(active) : undefined}
                className="h-full min-w-0 flex-1 bg-transparent text-[12.5px] text-foreground outline-none placeholder:text-muted-foreground/60"
              />
            </div>
          ) : null}
          <div ref={listRef} id={listId} role="listbox" aria-label={rest["aria-label"] ?? placeholder} className="p-1">
            {items.length === 0 ? <div className="px-2 py-1.5 text-[12.5px] text-muted-foreground">Aucun résultat</div> : null}
            {items.map((o, i) => {
              const heading = o.group && o.group !== lastGroup ? o.group : null;
              lastGroup = o.group;
              const s = splitHint(o);
              const sel = o.value === value;
              const empty = o.value === "" && placeholder !== undefined;
              return (
                <Fragment key={`${o.value}-${i}`}>
                  {heading ? (
                    <div role="presentation" className={cn("px-2 pb-1 pt-2 text-[11px] font-medium uppercase tracking-[.04em] text-muted-foreground", i === 0 && "pt-1")}>{heading}</div>
                  ) : null}
                  <div
                    id={optId(i)}
                    role="option"
                    aria-selected={sel}
                    aria-disabled={o.disabled || undefined}
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseMove={() => !o.disabled && active !== i && setActive(i)}
                    onClick={() => choose(o)}
                    className={cn(
                      "flex h-7 cursor-pointer select-none items-center gap-2 rounded-[3px] px-2 text-[13px]",
                      i === active && !o.disabled ? "bg-muted text-foreground" : "text-secondary-foreground",
                      sel && "font-medium text-foreground",
                      empty && !sel && "text-muted-foreground",
                      o.disabled && "cursor-not-allowed opacity-40",
                    )}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {s.label}
                      {s.hint ? <span className="font-normal text-muted-foreground"> · {s.hint}</span> : null}
                    </span>
                    <Check size={13} strokeWidth={2} aria-hidden className={cn("shrink-0 text-primary", !sel && "invisible")} />
                  </div>
                </Fragment>
              );
            })}
          </div>
        </div>
      </AnchoredPopover>
    </div>
  );
}

/** <Textarea rows={3} value onChange /> */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(FIELD, "min-h-[64px] resize-y px-2.5 py-1.5 leading-[18px]", className)} {...rest} />;
});

/** <Field label="Quantité" hint="en kg"><Input …/></Field> */
export function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1", className)}>
      <span className="text-[12px] font-medium text-secondary-foreground">{label}</span>
      {children}
      {hint ? <span className="text-[11.5px] text-muted-foreground">{hint}</span> : null}
    </label>
  );
}

/* Shared segmented-control look (Segmented, ThemeToggle): muted track, the selected segment is a raised
 * surface-2 chip with a hairline border-hover + shadow, so it reads in both themes (dark: card is darker than muted). */
export const SEGMENT_TRACK = "inline-flex rounded-[5px] border border-border bg-muted p-0.5";
export const SEGMENT_ITEM = "rounded-[4px] border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70";
export const SEGMENT_ON = "border-border-hover bg-surface-2 text-foreground shadow-sm";
export const SEGMENT_OFF = "border-transparent text-muted-foreground hover:text-foreground";

/** Segmented control (2–4 options): <Segmented value={v} onChange={setV} options={[{id:"all",label:"Tous"}]} /> */
export function Segmented<T extends string>({ value, options, onChange, className }: {
  value: T; options: ReadonlyArray<{ id: T; label: string }>; onChange: (v: T) => void; className?: string;
}) {
  return (
    <div role="radiogroup" className={cn(SEGMENT_TRACK, className)}>
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={o.id === value}
          onClick={() => onChange(o.id)}
          className={cn(
            "h-6 px-2.5 text-[12.5px]",
            SEGMENT_ITEM,
            o.id === value ? cn(SEGMENT_ON, "font-medium") : SEGMENT_OFF,
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
