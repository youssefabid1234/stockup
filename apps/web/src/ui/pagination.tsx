/**
 * Shared pagination: PAGE_SIZE (the only place the number lives), usePagination (page in the URL), <Pagination> footer bar,
 * and useServerList (page + sort in the URL → API params) for lists paginated by the server.
 *
 * Server-side lists (every big list: the API returns one page, see TECH.md « Pagination »):
 *   const list = useServerList({ defaultSort: { id: "date", dir: "desc" } });   // ?page= & ?sort=-date
 *   const { data } = useOrdersPage({ status, ...list.params });                  // { items, total, counts… }
 *   <DataTable server={{ list, total: data?.total }} rows={data?.items} columns={…sortKey…} />
 *
 * Client-side (small, already bounded lists): DataTable paginates on its own; usePagination for non-table lists:
 *   const pg = usePagination(events);                 // ?page=, 1-based
 *   <div ref={pg.anchorRef}>{pg.rows.map(…)}</div>    // scrolled back to top on page change
 *   <Pagination pagination={pg} sticky>{events.length} événements</Pagination>
 */
import { useCallback, useEffect, useMemo, useRef, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";
import { useUrlState } from "@/lib/url-state";
import { IconButton } from "./button";

/** Rows per page, everywhere in the app. */
export const PAGE_SIZE = 100;

export interface PaginationOptions {
  /** URL param holding the page (default "page"). Give each paginated list on a same screen its own key ("ordersPage"…). */
  key?: string;
  /** Anything not in the URL that reorders / refilters the input (e.g. the sort). A change sends the list back to page 1. */
  resetKey?: string | number;
  /** false = no pagination, every row returned (small embedded tables). */
  enabled?: boolean;
  /** Server-side pagination: `rows` IS the current page and `total` the number of matching rows (undefined while loading). */
  server?: boolean;
  total?: number;
}

export interface PaginationState<T> {
  /** rows of the current page ([] while the input is undefined) */
  rows: T[];
  /** 1-based, clamped to [1, pageCount] */
  page: number;
  pageCount: number;
  total: number;
  /** 1-based index of the first / last row shown */
  from: number;
  to: number;
  setPage: (page: number) => void;
  /** attach to the top of the list: it is scrolled back into view on page change */
  anchorRef: React.RefObject<HTMLDivElement>;
}

/**
 * Slice `rows` (already filtered AND sorted) into pages of PAGE_SIZE.
 * Page 1 again when: a filter / tab / search URL param changes (useUrlState clears ?page=), or `resetKey` changes.
 * The page is clamped when the list shrinks (live updates, deletes) without rewriting the URL.
 */
export function usePagination<T>(rows: readonly T[] | undefined, { key = "page", resetKey, enabled = true, server, total: serverTotal }: PaginationOptions = {}): PaginationState<T> {
  const [raw, setRaw] = useUrlState(key);
  const anchorRef = useRef<HTMLDivElement>(null);
  const known = server ? serverTotal !== undefined : !!rows;
  const total = server ? serverTotal ?? 0 : rows?.length ?? 0;
  const pageCount = enabled ? Math.max(1, Math.ceil(total / PAGE_SIZE)) : 1;
  const requested = Math.max(1, Number.parseInt(raw, 10) || 1);
  // While loading keep the URL page as is, so a reload on ?page=7 lands on page 7.
  const page = !enabled ? 1 : known ? Math.min(requested, pageCount) : requested;

  // resetKey change (not the first render) → page 1
  const lastReset = useRef(resetKey);
  useEffect(() => {
    if (lastReset.current === resetKey) return;
    lastReset.current = resetKey;
    if (enabled) setRaw("");
  }, [resetKey, enabled, setRaw]);

  // Server lists fetch the URL page: past the end (list shrank, hand-edited URL) → rewrite the URL to the last page.
  useEffect(() => {
    if (server && enabled && known && requested > pageCount) setRaw(pageCount === 1 ? "" : String(pageCount));
  }, [server, enabled, known, requested, pageCount, setRaw]);

  const setPage = useCallback(
    (p: number) => {
      const n = Math.min(Math.max(1, Math.round(p)), pageCount);
      setRaw(n === 1 ? "" : String(n));
      requestAnimationFrame(() => scrollToTop(anchorRef.current));
    },
    [pageCount, setRaw],
  );

  const pageRows = useMemo(() => {
    if (!rows) return [];
    if (!enabled || server) return rows as T[];
    return rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  }, [rows, page, enabled, server]);

  const from = total === 0 ? 0 : enabled ? (page - 1) * PAGE_SIZE + 1 : 1;
  const to = enabled ? Math.min(page * PAGE_SIZE, total) : total;
  return { rows: pageRows, page, pageCount, total, from, to, setPage, anchorRef };
}

// ── Server-side lists: page + sort in the URL → API params ──
export interface SortState { id: string; dir: "asc" | "desc" }

export interface ServerList {
  /** URL param of the page ("page", "ordersPage"…). */
  pageKey: string;
  page: number;
  sort: SortState;
  /** New sort → back to page 1. */
  setSort: (s: SortState) => void;
  /** Spread into the API call: { limit, offset, sort, order }. */
  params: { limit: number; offset: number; sort: string; order: "asc" | "desc" };
}

/** `?sort=-date` ↔ { id: "date", dir: "desc" } (absent = defaultSort). */
const parseSort = (raw: string): SortState | undefined =>
  raw ? (raw.startsWith("-") ? { id: raw.slice(1), dir: "desc" } : { id: raw, dir: "asc" }) : undefined;

/**
 * Page and sort of a server-paginated list, kept in the URL (?page=, ?sort=-field) so lists stay shareable.
 * Give each server list of a same screen its own keys ({ pageKey: "ordersPage", sortKey: "ordersSort" }).
 * Filter / tab changes already reset the page (useUrlState); so does a sort change.
 */
export function useServerList({ pageKey = "page", sortKey = "sort", defaultSort }: {
  pageKey?: string; sortKey?: string; defaultSort: SortState;
}): ServerList {
  const [rawPage] = useUrlState(pageKey);
  const [rawSort, setRawSort] = useUrlState(sortKey);
  const page = Math.max(1, Number.parseInt(rawPage, 10) || 1);
  const sort = parseSort(rawSort) ?? defaultSort;
  const setSort = useCallback(
    (s: SortState) => setRawSort(s.id === defaultSort.id && s.dir === defaultSort.dir ? "" : `${s.dir === "desc" ? "-" : ""}${s.id}`),
    [setRawSort, defaultSort.id, defaultSort.dir],
  );
  return {
    pageKey, page, sort, setSort,
    params: { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, sort: sort.id, order: sort.dir },
  };
}

/** Bring `el`'s top back into its scroll container's viewport (only scrolls up). */
function scrollToTop(el: HTMLElement | null) {
  if (!el) return;
  let parent = el.parentElement;
  while (parent && !/(auto|scroll)/.test(getComputedStyle(parent).overflowY)) parent = parent.parentElement;
  if (!parent) {
    el.scrollIntoView({ block: "start" });
    return;
  }
  const delta = el.getBoundingClientRect().top - parent.getBoundingClientRect().top;
  if (delta < 0) parent.scrollTop += delta;
}

/**
 * Page numbers to show: first, last and a 3-page window around the current one, "…" for gaps.
 *   1 2 3 4 … 22 · 1 … 9 10 11 … 22 · 1 … 19 20 21 22 (a gap of a single page shows the page instead of "…")
 */
export function pageItems(page: number, pageCount: number): (number | "…")[] {
  if (pageCount <= 1) return [1];
  let start = Math.max(2, Math.min(page - 1, pageCount - 3));
  let end = Math.min(pageCount - 1, Math.max(page + 1, 4));
  if (start === 3) start = 2;
  if (end === pageCount - 2) end = pageCount - 1;
  const out: (number | "…")[] = [1];
  if (start > 2) out.push("…");
  for (let p = start; p <= end; p++) out.push(p);
  if (end < pageCount - 1) out.push("…");
  out.push(pageCount);
  return out;
}

const nf = new Intl.NumberFormat("fr-FR");

/**
 * Footer bar: [children (summary / totals)] ……… 1–100 sur 2 192  ‹ 1 2 3 … 22 ›
 * Renders nothing when everything fits on one page. `sticky` pins it to the bottom of the page scroll area (full-bleed lists);
 * `inset` = inside a TableFrame (12px padding).
 */
export function Pagination<T>({ pagination: pg, children, inset, sticky, className }: {
  pagination: PaginationState<T>; children?: ReactNode; inset?: boolean; sticky?: boolean; className?: string;
}) {
  if (pg.pageCount <= 1) return null;
  return (
    <div
      className={cn(
        "flex min-h-10 flex-wrap items-center gap-x-4 gap-y-1 border-t border-border py-1.5 text-[13px] text-muted-foreground",
        inset ? "px-3" : "px-5",
        sticky && "sticky bottom-0 z-10 -mt-px bg-background",
        className,
      )}
    >
      <div className="min-w-0 flex-1 text-[12px]">{children}</div>
      <nav aria-label="Pagination" className="flex items-center gap-3">
        <span className="num whitespace-nowrap">
          {nf.format(pg.from)}–{nf.format(pg.to)} <span className="text-muted-foreground/80">sur</span> {nf.format(pg.total)}
        </span>
        <div className="flex items-center gap-0.5">
          <IconButton icon={ChevronLeft} label="Page précédente" size="sm" disabled={pg.page <= 1} onClick={() => pg.setPage(pg.page - 1)} />
          {pageItems(pg.page, pg.pageCount).map((p, i) =>
            p === "…" ? (
              <span key={`gap-${i}`} className="w-5 text-center text-[12px]" aria-hidden>…</span>
            ) : (
              <button
                key={p}
                type="button"
                aria-label={`Page ${p}`}
                aria-current={p === pg.page ? "page" : undefined}
                onClick={() => pg.setPage(p)}
                className={cn(
                  "num inline-flex h-[26px] min-w-[26px] items-center justify-center rounded-[4px] px-1.5 text-[12.5px] transition-colors",
                  "border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70",
                  p === pg.page ? "border-border-hover bg-surface-2 font-medium text-foreground shadow-sm" : "border-transparent hover:bg-muted hover:text-foreground",
                )}
              >
                {p}
              </button>
            ),
          )}
          <IconButton icon={ChevronRight} label="Page suivante" size="sm" disabled={pg.page >= pg.pageCount} onClick={() => pg.setPage(pg.page + 1)} />
        </div>
      </nav>
    </div>
  );
}
