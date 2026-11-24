import {
  createContext, Fragment, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState,
  type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode, type RefObject,
} from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { IconButton } from "./button";
import { AnchoredPopover } from "./popover";

/**
 * Page skeleton. Every page = <Page><PageHeader …/><PageBody>…</PageBody></Page>.
 * Page is `relative` so a <SidePanel> can float over the body.
 */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("relative flex h-full min-w-0 flex-col", className)}>{children}</div>;
}

/** Scrolling content. `flush` = no padding (for full-bleed tables, sticky header). */
export function PageBody({ children, flush, className }: { children: ReactNode; flush?: boolean; className?: string }) {
  return <div className={cn("min-h-0 flex-1 overflow-auto", !flush && "px-5 py-5", className)}>{children}</div>;
}

export interface Crumb { label: ReactNode; to?: string }

/**
 * Shell-provided trailing slot: the shell wraps its <Outlet/> in <PageHeaderSlot trailing={…} register={…}> so every
 * PageHeader ends with the same global control (the Assistant toggle), after the page's own actions and a hairline.
 * `register` lets the shell know a PageHeader is mounted (it renders the control itself otherwise). Pages never use this.
 */
const PageHeaderSlotCtx = createContext<{ trailing?: ReactNode; register?: () => () => void }>({});
export function PageHeaderSlot({ trailing, register, children }: { trailing?: ReactNode; register?: () => () => void; children: ReactNode }) {
  return <PageHeaderSlotCtx.Provider value={{ trailing, register }}>{children}</PageHeaderSlotCtx.Provider>;
}

/**
 * Header row (48px) + optional filter bar (40px), both hairline-separated:
 *   [breadcrumb /] title [count] [meta] · tabs ……… actions | shell tools (voice + Assistant toggle)
 *   [filters …                                                      ]   ← <FilterBar>, only when `filters` is set
 * The title never truncates (detail-page names only as a last resort); tabs take the remaining room and fold the ones
 * that don't fit into a "+N" menu; actions + shell tools never move.
 *   <PageHeader title="Clients" tabs={<Tabs …/>} filters={<SearchInput …/>} actions={<Button variant="primary">Nouveau</Button>} />
 *   <PageHeader breadcrumb={[{label:"Clients", to:"/clients"}]} title={client.name} meta={<StatusDot …/>} tabs={<Tabs …/>} />
 */
export function PageHeader({ title, icon, count, breadcrumb, meta, tabs, filters, actions, className }: {
  title: ReactNode; icon?: ReactNode; count?: number; breadcrumb?: Crumb[]; meta?: ReactNode; tabs?: ReactNode;
  filters?: ReactNode; actions?: ReactNode; className?: string;
}) {
  const slot = useContext(PageHeaderSlotCtx);
  useLayoutEffect(() => slot.register?.(), [slot.register]);
  const ref = useRef<HTMLElement>(null);
  const compact = useHeaderFit(ref);
  return (
    <>
      <header ref={ref} data-compact={compact || undefined} className={cn("flex h-12 shrink-0 items-center gap-3 border-b border-border px-5", className)}>
        {/* Title block never shrinks: very long detail names truncate past 420px only. */}
        <div className="flex shrink-0 items-center gap-1.5">
          {breadcrumb?.map((c, i) => (
            <Fragment key={i}>
              {c.to ? (
                <Link to={c.to} className="whitespace-nowrap rounded-[3px] text-[14px] text-muted-foreground transition-colors hover:text-foreground">{c.label}</Link>
              ) : (
                <span className="whitespace-nowrap text-[14px] text-muted-foreground">{c.label}</span>
              )}
              <ChevronRight size={13} strokeWidth={1.75} className="shrink-0 text-muted-foreground/70" />
            </Fragment>
          ))}
          {icon ? <span className="shrink-0 text-muted-foreground">{icon}</span> : null}
          <h1 data-fit className="max-w-[420px] truncate whitespace-nowrap text-[14px] font-semibold tracking-[-0.005em]">{title}</h1>
          {count !== undefined ? <span className="num ml-0.5 shrink-0 text-[12.5px] text-muted-foreground">{count}</span> : null}
        </div>
        {/* Meta (status, date…) gives way first: it is clipped before anything else moves. */}
        {meta ? <div data-fit className="flex min-w-0 shrink items-center gap-2 overflow-hidden whitespace-nowrap">{meta}</div> : null}
        {/* basis 0: the tabs only get the room the title and actions leave, and overflow into "+N" instead of squeezing them. */}
        <div className="ml-2 flex h-full min-w-0 flex-1 basis-0 items-stretch">{tabs}</div>
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          {slot.trailing ? (
            <>
              {actions ? <span aria-hidden className="mx-1 h-4 w-px shrink-0 bg-border" /> : null}
              {slot.trailing}
            </>
          ) : null}
        </div>
      </header>
      {filters ? <FilterBar>{filters}</FilterBar> : null}
    </>
  );
}

/**
 * Header fit: returns 0 (room enough), 1 (hide the shell tools' shortcut hints) or 2 (icon-only shell tools), set as
 * `data-compact` on the header (CSS in styles/index.css). Level 1 when tabs are folded into "+N"; level 2 only when the
 * row overflows or the title / meta are clipped. Hysteresis: it only relaxes once the row is 24px wider than when it tightened.
 */
function useHeaderFit(ref: RefObject<HTMLElement>) {
  const [level, setLevel] = useState(0);
  const at = useRef<number[]>([]);
  const check = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.clientWidth;
    if (!w) return;
    const clipped = [...el.querySelectorAll<HTMLElement>("[data-fit]")].some((e) => e.scrollWidth > e.clientWidth + 1);
    // Hard = something is clipped or overflows (up to icon-only tools); soft = tabs folded into "+N" (hints only, so
    // the Voix / Assistant labels stay the same on every page).
    const hard = el.scrollWidth > w + 1 || clipped;
    const tight = hard || !!el.querySelector('[data-tabs-folded="true"]');
    setLevel((l) => {
      if (tight && l < (hard ? 2 : 1)) { at.current[l] = w; return l + 1; }
      if (!tight && l > 0 && w > (at.current[l - 1] ?? Infinity) + 24) return l - 1;
      return l;
    });
  }, [ref]);
  useLayoutEffect(check);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => check());
    ro.observe(el);
    el.querySelectorAll("[data-tabs-measure],[data-fit]").forEach((e) => ro.observe(e));
    const mo = new MutationObserver(() => check());
    mo.observe(el, { subtree: true, attributes: true, attributeFilter: ["data-tabs-folded"] });
    return () => { ro.disconnect(); mo.disconnect(); };
  }, [ref, check]);
  return level;
}

/**
 * Slim filter strip under the PageHeader (40px, hairline): search, Selects, DatePickers, "Effacer les filtres".
 * Usually rendered by `PageHeader filters`; use it directly only for a strip that isn't the page's filters.
 * Push an item to the right with `className="ml-auto"`. Scrolls horizontally rather than clipping when too narrow.
 */
export function FilterBar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      data-filter-bar
      className={cn(
        "flex h-10 shrink-0 items-center gap-2 overflow-x-auto overflow-y-hidden border-b border-border px-5 [scrollbar-width:none] [&>*]:shrink-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

export interface TabItem<T extends string = string> { id: T; label: ReactNode; count?: number }

/**
 * Inline underline tabs, fill the 48px header height: <Tabs value={tab} onChange={setTab} items={[…]} />
 * When the row is too narrow, the trailing tabs fold into a "+N" menu (the active tab always stays visible).
 */
export function Tabs<T extends string>({ items, value, onChange, className }: {
  items: TabItem<T>[]; value: T; onChange: (v: T) => void; className?: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLButtonElement>(null);
  const [fit, setFit] = useState(items.length);
  const [menu, setMenu] = useState(false);

  useLayoutEffect(() => {
    const box = boxRef.current;
    const measure = measureRef.current;
    if (!box || !measure) return;
    const GAP = 16;
    const MORE_W = 48;
    const compute = () => {
      const avail = box.clientWidth;
      const widths = [...measure.children].map((c) => (c as HTMLElement).offsetWidth);
      const total = widths.reduce((a, w) => a + w, 0) + GAP * Math.max(0, widths.length - 1);
      if (total <= avail) return setFit(widths.length);
      let used = MORE_W;
      let n = 0;
      for (const w of widths) {
        if (used + w + GAP > avail) break;
        used += w + GAP;
        n++;
      }
      setFit(n);
    };
    compute();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(compute) : null;
    ro?.observe(box);
    ro?.observe(measure);
    return () => ro?.disconnect();
  }, [items.length]);

  // Visible = the first `fit` tabs; if the active one is folded, it takes the last visible slot.
  const activeIdx = items.findIndex((t) => t.id === value);
  const n = Math.min(fit, items.length);
  const shown = n > 0 && n < items.length && activeIdx >= n ? [...items.slice(0, n - 1), items[activeIdx]] : items.slice(0, n);
  const hidden = items.filter((t) => !shown.includes(t));
  // No room for a single tab: the menu button carries the active tab's name.
  const active = shown.length === 0 ? items[activeIdx] : undefined;

  const tabButton = (t: TabItem<T>, measure = false) => {
    const on = t.id === value;
    return (
      <button
        key={t.id}
        role={measure ? undefined : "tab"}
        type="button"
        tabIndex={measure ? -1 : undefined}
        aria-selected={measure ? undefined : on}
        onClick={measure ? undefined : () => onChange(t.id)}
        className={cn(
          "relative inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-[13px] transition-colors focus-visible:outline-offset-[-2px]",
          on ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
      >
        {t.label}
        {t.count !== undefined ? <span className="num text-[11.5px] text-muted-foreground">{t.count}</span> : null}
        {on && !measure ? <span className="absolute inset-x-0 -bottom-px h-[2px] rounded-full bg-foreground" /> : null}
      </button>
    );
  };

  return (
    <div ref={boxRef} data-tabs-folded={hidden.length > 0} className={cn("relative flex h-full min-w-0 flex-1 items-stretch overflow-x-clip", className)}>
      {/* Invisible copy of every tab, used to measure their natural widths. */}
      <div ref={measureRef} data-tabs-measure aria-hidden className="pointer-events-none invisible absolute left-0 top-0 flex h-full items-stretch gap-4">
        {items.map((t) => tabButton(t, true))}
      </div>
      <div role="tablist" className="flex h-full min-w-0 items-stretch gap-4">
        {shown.map((t) => tabButton(t))}
        {hidden.length ? (
          <button
            ref={moreRef}
            type="button"
            aria-haspopup="menu"
            aria-expanded={menu}
            aria-label={active ? "Onglets" : `${hidden.length} autres onglets`}
            onClick={() => setMenu((o) => !o)}
            onBlur={() => setMenu(false)}
            onKeyDown={(e) => { if (e.key === "Escape") setMenu(false); }}
            className={cn(
              "my-auto inline-flex h-6 shrink-0 items-center gap-0.5 rounded-[4px] px-1.5 text-[12.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
              menu && "bg-muted text-foreground",
            )}
          >
            {active ? <span className="whitespace-nowrap font-medium text-foreground">{active.label}</span> : <span className="num">+{hidden.length}</span>}
            <ChevronDown size={13} strokeWidth={1.75} />
          </button>
        ) : null}
      </div>
      <AnchoredPopover anchorRef={moreRef} open={menu && hidden.length > 0} matchWidth={false} width={220} role="menu" className="p-1">
        {hidden.map((t) => (
          <button
            key={t.id}
            type="button"
            role="menuitem"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => { onChange(t.id); setMenu(false); }}
            className="flex h-7 w-full items-center gap-2 whitespace-nowrap rounded-[4px] px-2 text-left text-[13px] text-foreground hover:bg-muted"
          >
            <span className="flex min-w-0 flex-1 items-center gap-1.5">{t.label}</span>
            {t.count !== undefined ? <span className="num text-[11.5px] text-muted-foreground">{t.count}</span> : null}
          </button>
        ))}
      </AnchoredPopover>
    </div>
  );
}

/* ── Resizable panels ─────────────────────────────────────────────────────────────────────────────────────────────
 * const r = useResizableWidth("assistant", 400, 320, 720);   // width persisted in localStorage `kit-w:<key>`
 * <aside style={{ width: r.width }} className="relative"><ResizeHandle r={r} edge="left" />…</aside>
 * Drag the hairline (col-resize), double-click resets to the default, ←/→ when focused. */
export function useResizableWidth(key: string, def: number, min: number, max: number) {
  const sk = `kit-w:${key}`;
  const clamp = (w: number) => Math.round(Math.min(max, Math.max(min, w)));
  const [width, setWidthState] = useState(() => {
    try { const v = Number(localStorage.getItem(sk)); return v ? clamp(v) : def; } catch { return def; }
  });
  const [dragging, setDragging] = useState(false);
  const setWidth = useCallback((w: number, persist = false) => {
    const c = Math.round(Math.min(max, Math.max(min, w)));
    setWidthState(c);
    if (persist) { try { localStorage.setItem(sk, String(c)); } catch { /* ignore */ } }
  }, [sk, min, max]);
  const reset = useCallback(() => {
    setWidthState(def);
    try { localStorage.removeItem(sk); } catch { /* ignore */ }
  }, [sk, def]);
  return { width, setWidth, reset, dragging, setDragging, min, max, def };
}
export type Resizable = ReturnType<typeof useResizableWidth>;

/** Hairline drag handle lying on a panel edge (inside the panel). edge="right" → dragging right grows the panel. */
export function ResizeHandle({ r, edge, label = "Redimensionner" }: { r: Resizable; edge: "left" | "right"; label?: string }) {
  const sign = edge === "right" ? 1 : -1;
  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const el = e.currentTarget;
    const startX = e.clientX;
    const startW = r.width;
    let last = startW;
    el.setPointerCapture(e.pointerId);
    r.setDragging(true);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    const move = (ev: PointerEvent) => { last = startW + sign * (ev.clientX - startX); r.setWidth(last); };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      r.setWidth(last, true);
      r.setDragging(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
  };
  const onKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    r.setWidth(r.width + sign * (e.key === "ArrowRight" ? 16 : -16), true);
  };
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={r.width}
      aria-valuemin={r.min}
      aria-valuemax={r.max}
      tabIndex={0}
      title={`${label} · double-clic : taille par défaut`}
      data-resize-handle={edge}
      onPointerDown={onPointerDown}
      onDoubleClick={r.reset}
      onKeyDown={onKeyDown}
      className={cn(
        "group absolute inset-y-0 z-30 w-[6px] cursor-col-resize touch-none outline-none",
        edge === "right" ? "right-0" : "left-0",
      )}
    >
      <span
        className={cn(
          "absolute inset-y-0 w-px transition-[background-color,width] duration-100 group-hover:w-[2px] group-hover:bg-ring/60 group-focus-visible:w-[2px] group-focus-visible:bg-ring/60",
          edge === "right" ? "right-0" : "left-0",
          r.dragging ? "w-[2px] bg-ring" : "bg-transparent",
        )}
      />
    </div>
  );
}

/**
 * Right side panel (480px default), floats over the page body, no backdrop, Esc closes. Must be inside <Page>.
 * Slides in/out from the right; resizable by its left edge (width remembered per page, or per `id`).
 *   {sel && <SidePanel title={sel.name} onClose={() => setSel(null)} actions={…}>…</SidePanel>}
 */
export function SidePanel({ title, subtitle, actions, onClose, children, width = 480, footer, id }: {
  title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; onClose: () => void; children: ReactNode; width?: number; footer?: ReactNode;
  /** Storage key for the remembered width (defaults to the route's first segment). */
  id?: string;
}) {
  const { pathname } = useLocation();
  const r = useResizableWidth(`panel:${id ?? (pathname.split("/")[1] || "home")}`, width, 360, 880);
  const [leaving, setLeaving] = useState(false);
  const leavingRef = useRef(false);
  const close = useCallback(() => {
    if (leavingRef.current) return;
    let reduce = false;
    try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* ignore */ }
    if (reduce) return onClose();
    leavingRef.current = true;
    setLeaving(true);
    window.setTimeout(() => { leavingRef.current = false; setLeaving(false); onClose(); }, 160);
  }, [onClose]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !e.defaultPrevented) close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);
  return (
    <aside
      style={{ width: r.width }}
      data-side-panel
      className={cn(
        "absolute bottom-0 right-0 top-12 z-20 flex max-w-full animate-slide-in flex-col border-l border-border bg-card shadow-panel",
        "transition-[transform,opacity] duration-150 ease-in motion-reduce:transition-none",
        leaving && "translate-x-4 opacity-0",
      )}
    >
      <ResizeHandle r={r} edge="left" label="Redimensionner le panneau" />
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border pl-4 pr-2">
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13.5px] font-semibold">{title}</div>
          {subtitle ? <div className="truncate text-[11.5px] text-muted-foreground">{subtitle}</div> : null}
        </div>
        {actions}
        <IconButton icon={X} label="Fermer (Échap)" size="sm" onClick={close} />
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-4 py-4">{children}</div>
      {footer ? <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border px-4 py-2.5">{footer}</div> : null}
    </aside>
  );
}
