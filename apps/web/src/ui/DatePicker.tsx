/**
 * Stockline date picker — the ONLY way to pick a date in the app (never `<input type="date">`).
 *
 * <DatePicker value={iso} onChange={setIso} min={today} placeholder="Choisir une date" />
 * <DatePicker size="sm" value={date} onChange={setDate} className="w-[150px]" />             // header filter row
 * <DatePicker variant="inline" value={d} onChange={save} className="text-[15px]" />          // editable text, dotted underline
 *
 * Value is ISO "YYYY-MM-DD" ("" = empty). The popover is portalled to <body> (fixed, z-[55]): it floats above
 * SidePanels and is never clipped by a scrolling body. Keyboard: ←→↑↓ day/week, PageUp/PageDown month
 * (+Shift = year), Home/End week start/end, Enter selects, Esc closes. The top field accepts typed dates
 * ("25/11", "25/11/2026", "2026-11-25"). "Today" is the business day (src/lib/clock.ts), not the real one.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CalendarDays, ChevronLeft, ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { businessToday } from "@/lib/clock";

/* ── Date math on ISO strings (UTC arithmetic → no DST surprises) ─────────────────────────────────────────────── */
const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;
const pad = (n: number) => String(n).padStart(2, "0");
const toIso = (y: number, m0: number, d: number) => {
  const t = new Date(Date.UTC(y, m0, d));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
};
const parts = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return { y, m0: m - 1, d };
};
const utc = (iso: string) => { const p = parts(iso); return new Date(Date.UTC(p.y, p.m0, p.d)); };
const daysInMonth = (y: number, m0: number) => new Date(Date.UTC(y, m0 + 1, 0)).getUTCDate();
/** Monday = 0 … Sunday = 6 */
const weekdayMon = (iso: string) => (utc(iso).getUTCDay() + 6) % 7;
const addDaysIso = (iso: string, n: number) => { const p = parts(iso); return toIso(p.y, p.m0, p.d + n); };
const addMonthsIso = (iso: string, n: number) => {
  const p = parts(iso);
  const t = new Date(Date.UTC(p.y, p.m0 + n, 1));
  return toIso(t.getUTCFullYear(), t.getUTCMonth(), Math.min(p.d, daysInMonth(t.getUTCFullYear(), t.getUTCMonth())));
};
const clampIso = (iso: string, min?: string, max?: string) => (min && iso < min ? min : max && iso > max ? max : iso);
const inRange = (iso: string, min?: string, max?: string) => !(min && iso < min) && !(max && iso > max);

/* ── fr-FR labels ─────────────────────────────────────────────────────────────────────────────────────────────── */
const fMonth = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric", timeZone: "UTC" });
const fShort = new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const fShortY = new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const fFull = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const fNarrow = new Intl.DateTimeFormat("fr-FR", { weekday: "narrow", timeZone: "UTC" });
const fLongDay = new Intl.DateTimeFormat("fr-FR", { weekday: "long", timeZone: "UTC" });
// 2024-01-01 is a Monday.
const WEEKDAYS = Array.from({ length: 7 }, (_, i) => {
  const d = new Date(Date.UTC(2024, 0, 1 + i));
  return { short: fNarrow.format(d).toUpperCase(), long: fLongDay.format(d) };
});
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** "mar. 24 nov." (year added when it is not the business year). */
export function fmtPickerDate(iso: string, today = businessToday()) {
  if (!ISO_RE.test(iso)) return "";
  return (iso.slice(0, 4) === today.slice(0, 4) ? fShort : fShortY).format(utc(iso));
}

/** Parse what people type: "25/11", "25/11/26", "25.11.2026", "25-11-2026", "2026-11-25". Returns ISO or null. */
export function parseTypedDate(text: string, today = businessToday()): string | null {
  const s = text.trim();
  if (!s) return null;
  if (ISO_RE.test(s)) return isValidIso(s) ? s : null;
  const m = /^(\d{1,2})\s*[/.\- ]\s*(\d{1,2})(?:\s*[/.\- ]\s*(\d{2}|\d{4}))?$/.exec(s);
  if (!m) return null;
  const d = Number(m[1]);
  const mo = Number(m[2]);
  let y = m[3] ? Number(m[3]) : Number(today.slice(0, 4));
  if (m[3] && m[3].length === 2) y += 2000;
  const iso = `${y}-${pad(mo)}-${pad(d)}`;
  return isValidIso(iso) ? iso : null;
}
const isValidIso = (iso: string) => {
  if (!ISO_RE.test(iso)) return false;
  const p = parts(iso);
  return p.m0 >= 0 && p.m0 < 12 && p.d >= 1 && p.d <= daysInMonth(p.y, p.m0);
};

/* ── Presets ──────────────────────────────────────────────────────────────────────────────────────────────────── */
/** `days` = offset from business today; `value` = fixed ISO date. */
export type DatePreset = { label: string; days: number } | { label: string; value: string };
export const DEFAULT_DATE_PRESETS: DatePreset[] = [
  { label: "Aujourd'hui", days: 0 },
  { label: "Demain", days: 1 },
  { label: "+7 j", days: 7 },
];
const presetIso = (p: DatePreset, today: string) => ("value" in p ? p.value : addDaysIso(today, p.days));

/* ── Component ────────────────────────────────────────────────────────────────────────────────────────────────── */
export interface DatePickerProps {
  value: string | null | undefined;
  onChange: (iso: string) => void;
  min?: string;
  max?: string;
  placeholder?: string;
  /** md = 32px (forms), sm = 26px (header filter rows). */
  size?: "md" | "sm";
  /** field = looks like <Input> (default); inline = the formatted date as editable text (dotted underline). */
  variant?: "field" | "inline";
  /** Quick picks under the grid. `false` hides them. */
  presets?: DatePreset[] | false;
  /** Shows a clear (×) button; onChange("") when cleared. */
  clearable?: boolean;
  disabled?: boolean;
  className?: string;
  id?: string;
  "aria-label"?: string;
  autoFocus?: boolean;
  /** Custom trigger content (variant inline): defaults to the formatted date. */
  children?: ReactNode;
}

const POP_W = 260;

export function DatePicker({
  value, onChange, min, max, placeholder = "Choisir une date", size = "md", variant = "field",
  presets = DEFAULT_DATE_PRESETS, clearable, disabled, className, id, autoFocus, children, ...aria
}: DatePickerProps) {
  const today = businessToday();
  const current = value && isValidIso(value) ? value : "";
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(() => clampIso(current || today, min, max));
  const [typed, setTyped] = useState("");
  const [pos, setPos] = useState<{ top: number; left: number; above: boolean } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const openPicker = useCallback(() => {
    if (disabled) return;
    setCursor(clampIso(current || today, min, max));
    setTyped("");
    setOpen(true);
  }, [disabled, current, today, min, max]);

  const close = useCallback((refocus = true) => {
    setOpen(false);
    setPos(null);
    if (refocus) requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);

  const commit = (iso: string) => {
    if (!inRange(iso, min, max)) return;
    if (iso !== current) onChange(iso);
    close();
  };

  // Anchor: below the trigger, flipped above when it does not fit, clamped to the viewport.
  const place = useCallback(() => {
    const t = triggerRef.current;
    if (!t) return;
    const r = t.getBoundingClientRect();
    const h = popRef.current?.offsetHeight ?? 340;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const above = r.bottom + 4 + h > vh - 8 && r.top - 4 - h > 8;
    const top = above ? r.top - 4 - h : r.bottom + 4;
    const left = Math.max(8, Math.min(r.left, vw - POP_W - 8));
    setPos({ top, left, above });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    place();
    const onWin = () => place();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    return () => { window.removeEventListener("resize", onWin); window.removeEventListener("scroll", onWin, true); };
  }, [open, place]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onDown = (e: MouseEvent) => {
      const n = e.target as Node;
      if (popRef.current?.contains(n) || triggerRef.current?.contains(n)) return;
      close(false);
    };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
  }, [open, close]);

  // Grid of 42 days starting on the Monday on/before the 1st of the cursor's month.
  const { y: cy, m0: cm } = parts(cursor);
  const first = toIso(cy, cm, 1);
  const gridStart = addDaysIso(first, -weekdayMon(first));
  const days = useMemo(() => Array.from({ length: 42 }, (_, i) => addDaysIso(gridStart, i)), [gridStart]);
  const monthLabel = cap(fMonth.format(utc(first)));
  const prevDisabled = !!min && addDaysIso(first, -1) < min;
  const nextDisabled = !!max && toIso(cy, cm + 1, 1) > max;

  const parsed = parseTypedDate(typed, today);
  const parsedOk = parsed && inRange(parsed, min, max) ? parsed : null;

  // Typing a valid date moves the grid there.
  useEffect(() => { if (parsedOk) setCursor(parsedOk); }, [parsedOk]);

  const move = (iso: string) => setCursor(clampIso(iso, min, max));

  const onKey = (e: KeyboardEvent) => {
    const k = e.key;
    const caretFree = !typed; // arrows edit the text once something is typed
    let next: string | null = null;
    if (k === "ArrowLeft" && caretFree) next = addDaysIso(cursor, -1);
    else if (k === "ArrowRight" && caretFree) next = addDaysIso(cursor, 1);
    else if (k === "ArrowUp") next = addDaysIso(cursor, -7);
    else if (k === "ArrowDown") next = addDaysIso(cursor, 7);
    else if (k === "PageUp") next = e.shiftKey ? addMonthsIso(cursor, -12) : addMonthsIso(cursor, -1);
    else if (k === "PageDown") next = e.shiftKey ? addMonthsIso(cursor, 12) : addMonthsIso(cursor, 1);
    else if (k === "Home" && caretFree) next = addDaysIso(cursor, -weekdayMon(cursor));
    else if (k === "End" && caretFree) next = addDaysIso(cursor, 6 - weekdayMon(cursor));
    else if (k === "Enter") { e.preventDefault(); e.stopPropagation(); commit(parsedOk ?? cursor); return; }
    else if (k === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    else if (k === "Tab") { close(false); return; }
    if (next) { e.preventDefault(); if (typed) setTyped(""); move(next); }
  };

  const label = current ? fmtPickerDate(current, today) : "";
  const isSm = size === "sm";

  const trigger = variant === "inline" ? (
    <button
      ref={triggerRef}
      type="button"
      id={id}
      disabled={disabled}
      autoFocus={autoFocus}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-label={aria["aria-label"] ?? "Choisir une date"}
      title={current ? cap(fFull.format(utc(current))) : undefined}
      onClick={() => (open ? close() : openPicker())}
      className={cn(
        "num inline-flex cursor-pointer items-center whitespace-nowrap rounded-[3px] text-foreground underline decoration-muted-foreground/50 decoration-dotted underline-offset-4 outline-none transition-colors hover:decoration-foreground focus-visible:ring-2 focus-visible:ring-ring/70 disabled:cursor-default disabled:no-underline disabled:opacity-60",
        open && "decoration-foreground",
        !current && "text-muted-foreground",
        className,
      )}
    >
      {children ?? (label || placeholder)}
    </button>
  ) : (
    <div className={cn("relative inline-flex w-full", className)}>
      <button
        ref={triggerRef}
        type="button"
        id={id}
        disabled={disabled}
        autoFocus={autoFocus}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={aria["aria-label"]}
        title={current ? cap(fFull.format(utc(current))) : undefined}
        onClick={() => (open ? close() : openPicker())}
        onKeyDown={(e) => { if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) { e.preventDefault(); openPicker(); } }}
        className={cn(
          "flex w-full min-w-0 items-center gap-1.5 rounded-[4px] border border-border bg-card text-left text-foreground outline-none transition-colors hover:border-border-hover focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20 disabled:pointer-events-none disabled:opacity-50",
          isSm ? "h-[26px] pl-2 text-[12.5px]" : "h-8 pl-2.5 text-[13px]",
          clearable && current ? (isSm ? "pr-6" : "pr-7") : isSm ? "pr-2" : "pr-2.5",
          open && "border-ring ring-2 ring-ring/20",
        )}
      >
        <CalendarDays size={isSm ? 13 : 14} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted-foreground" />
        <span className={cn("num truncate", !current && "text-muted-foreground/70")}>{label || placeholder}</span>
      </button>
      {clearable && current && !disabled ? (
        <button
          type="button"
          aria-label="Effacer la date"
          onClick={() => onChange("")}
          className="absolute right-1.5 top-1/2 flex h-4 w-4 -translate-y-1/2 items-center justify-center rounded-[3px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={12} strokeWidth={1.75} />
        </button>
      ) : null}
    </div>
  );

  const presetList = presets === false ? [] : presets;

  const popover = open
    ? createPortal(
        <div
          ref={popRef}
          role="dialog"
          aria-label="Choisir une date"
          onKeyDown={onKey}
          style={{ top: pos?.top ?? -9999, left: pos?.left ?? -9999, width: POP_W, opacity: pos ? 1 : 0 }}
          className={cn(
            "fixed z-[55] overflow-hidden rounded-[4px] border border-border bg-card text-[13px] text-foreground shadow-pop",
            "animate-fade-in",
          )}
        >
          {/* Typed entry */}
          <div className="flex h-9 items-center gap-2 border-b border-border px-3">
            <input
              ref={inputRef}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="JJ/MM ou JJ/MM/AAAA"
              aria-label="Saisir une date"
              className="num h-full min-w-0 flex-1 bg-transparent text-[12.5px] text-foreground outline-none placeholder:text-muted-foreground/60"
            />
            {typed ? (
              <span className={cn("shrink-0 text-[11.5px]", parsedOk ? "text-muted-foreground" : "text-destructive/80")}>
                {parsedOk ? fmtPickerDate(parsedOk, today) : parsed ? "Hors limites" : "Date invalide"}
              </span>
            ) : (
              <span className="shrink-0 text-[11px] text-muted-foreground/70">↵ valider</span>
            )}
          </div>

          {/* Month header */}
          <div className="flex items-center justify-between px-3 pb-1 pt-2.5">
            <span className="text-[13px] font-medium" aria-live="polite">{monthLabel}</span>
            <div className="flex items-center gap-0.5">
              <NavBtn label="Mois précédent" disabled={prevDisabled} onClick={() => move(addMonthsIso(cursor, -1))}><ChevronLeft size={14} strokeWidth={1.75} /></NavBtn>
              <NavBtn label="Mois suivant" disabled={nextDisabled} onClick={() => move(addMonthsIso(cursor, 1))}><ChevronRight size={14} strokeWidth={1.75} /></NavBtn>
            </div>
          </div>

          {/* Grid */}
          <div role="grid" aria-label={monthLabel} className="px-2.5 pb-2">
            <div role="row" className="grid grid-cols-7">
              {WEEKDAYS.map((w, i) => (
                <div key={i} role="columnheader" aria-label={w.long} className="flex h-7 items-center justify-center text-[10.5px] font-medium tracking-[.04em] text-muted-foreground">
                  {w.short}
                </div>
              ))}
            </div>
            {Array.from({ length: 6 }, (_, r) => (
              <div key={r} role="row" className="grid grid-cols-7 gap-y-0.5">
                {days.slice(r * 7, r * 7 + 7).map((iso) => {
                  const outside = parts(iso).m0 !== cm;
                  const sel = iso === current;
                  const isToday = iso === today;
                  const focus = iso === cursor;
                  const off = !inRange(iso, min, max);
                  return (
                    <button
                      key={iso}
                      type="button"
                      role="gridcell"
                      tabIndex={-1}
                      aria-selected={sel}
                      aria-current={isToday ? "date" : undefined}
                      aria-label={cap(fFull.format(utc(iso)))}
                      disabled={off}
                      onMouseEnter={() => !off && setCursor(iso)}
                      onClick={() => commit(iso)}
                      className={cn(
                        "num relative mx-auto flex h-[30px] w-[32px] items-center justify-center rounded-[4px] text-[12.5px] transition-colors",
                        outside ? "text-muted-foreground/55" : "text-foreground",
                        !sel && focus && !off && "bg-muted",
                        !sel && isToday && "font-semibold text-primary ring-1 ring-inset ring-primary/45",
                        sel && "bg-primary font-medium text-primary-foreground",
                        off && "cursor-not-allowed text-muted-foreground/30 line-through decoration-muted-foreground/30",
                      )}
                    >
                      {parts(iso).d}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          {/* Presets + clear */}
          {presetList.length || clearable ? (
            <div className="flex items-center gap-1 border-t border-border px-2 py-1.5">
              {presetList.map((p) => {
                const iso = presetIso(p, today);
                const ok = inRange(iso, min, max);
                return (
                  <button
                    key={p.label}
                    type="button"
                    disabled={!ok}
                    onClick={() => commit(iso)}
                    title={fmtPickerDate(iso, today)}
                    className={cn(
                      "h-6 rounded-[4px] px-2 text-[12px] transition-colors disabled:pointer-events-none disabled:opacity-40",
                      iso === current ? "bg-row-selected font-medium text-foreground" : "text-secondary-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    {p.label}
                  </button>
                );
              })}
              {clearable && current ? (
                <button
                  type="button"
                  onClick={() => { onChange(""); close(); }}
                  className="ml-auto h-6 rounded-[4px] px-2 text-[12px] text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  Effacer
                </button>
              ) : null}
            </div>
          ) : null}
        </div>,
        document.body,
      )
    : null;

  return (
    <>
      {trigger}
      {popover}
    </>
  );
}

function NavBtn({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      tabIndex={-1}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex h-6 w-6 items-center justify-center rounded-[4px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-30"
    >
      {children}
    </button>
  );
}
