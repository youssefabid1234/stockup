/**
 * Table primitives (full-bleed, hairlines, sticky header, 34px rows) + a generic <DataTable>.
 * Put tables directly inside <PageBody flush> so the header sticks to the page scroll area.
 */
import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type HTMLAttributes, type ReactNode, type RefObject, type TdHTMLAttributes, type ThHTMLAttributes } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/cn";
import { useRecentlyChanged } from "@/lib/queries";
import { Skeleton } from "./section";
import { Pagination, usePagination, type ServerList } from "./pagination";

type Align = "left" | "right" | "center";
/** true = table touches the page edges (20px outer padding, sticky header on page bg); false = inside a Card/Section. */
const EdgeCtx = createContext(true);
const edgePad = (edge: boolean) => (edge ? "first:pl-5 last:pr-5" : "first:pl-3 last:pr-3");
const ALIGN: Record<Align, string> = { left: "text-left", right: "text-right", center: "text-center" };

export function Table({ className, children, fixed }: { className?: string; children: ReactNode; fixed?: boolean }) {
  return <table className={cn("w-full border-separate border-spacing-0 text-[13px]", fixed && "table-fixed", className)}>{children}</table>;
}
export function THead({ children }: { children: ReactNode }) {
  const edge = useContext(EdgeCtx);
  return <thead className={cn(edge ? "sticky top-0 z-10 bg-background" : "bg-muted/40")}>{children}</thead>;
}

/** Hairline frame for a table inside a Section (6px radius, 12px edge padding, no sticky header). */
export function TableFrame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <EdgeCtx.Provider value={false}>
      <div className={cn("overflow-hidden rounded-[6px] border border-border bg-card [&_tbody_tr:last-child_td]:border-b-0", className)}>{children}</div>
    </EdgeCtx.Provider>
  );
}
export function TBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TH({ align = "left", className, children, ...rest }: ThHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  const edge = useContext(EdgeCtx);
  return (
    <th
      className={cn(
        "h-8 whitespace-nowrap border-b border-border px-3 text-[12px] font-medium text-muted-foreground",
        edgePad(edge),
        ALIGN[align],
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

export interface TRProps extends HTMLAttributes<HTMLTableRowElement> {
  selected?: boolean;
  /** entity id: the row flashes violet when a live event touches it */
  liveId?: string;
}
export function TR({ selected, liveId, onClick, className, children, ...rest }: TRProps) {
  const flash = useRecentlyChanged(liveId);
  return (
    <tr
      onClick={onClick}
      aria-selected={selected || undefined}
      className={cn(
        "group h-[34px] transition-colors",
        onClick && "cursor-pointer",
        selected ? "bg-row-selected" : "hover:bg-muted/60",
        flash && "animate-flash",
        className,
      )}
      {...rest}
    >
      {children}
    </tr>
  );
}

export interface TDProps extends TdHTMLAttributes<HTMLTableCellElement> {
  align?: Align;
  /** tabular numbers, right aligned */
  numeric?: boolean;
  mono?: boolean;
  muted?: boolean;
}
export function TD({ align, numeric, mono, muted, className, children, ...rest }: TDProps) {
  const edge = useContext(EdgeCtx);
  return (
    <td
      className={cn(
        "h-[34px] whitespace-nowrap border-b border-border px-3 align-middle",
        edgePad(edge),
        ALIGN[align ?? (numeric ? "right" : "left")],
        numeric && "num",
        mono && "font-mono text-[12px]",
        muted && "text-muted-foreground",
        className,
      )}
      {...rest}
    >
      {children}
    </td>
  );
}

// ── DataTable ──
export interface Column<T> {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  align?: Align;
  numeric?: boolean;
  mono?: boolean;
  muted?: boolean;
  width?: number | string;
  /** enable header-click sorting (client-side lists) */
  sortValue?: (row: T) => string | number | undefined | null;
  /** server-side lists: the API `sort` field of this column (the column is sortable iff set) */
  sortKey?: string;
  className?: string;
  /** Hide the column while the table is narrower than this (px): secondary columns give way at 1024–1440 instead of
   *  pushing the table into a horizontal scroll. */
  hideBelow?: number;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  getRowId: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedId?: string | null;
  loading?: boolean;
  /** shown when rows is an empty array */
  empty?: ReactNode;
  /** muted line under the table, e.g. "42 clients" */
  footer?: ReactNode;
  defaultSort?: { id: string; dir: "asc" | "desc" };
  /** render inside a hairline frame (for tables in a Section on a detail page) */
  inset?: boolean;
  /** number of skeleton rows while loading */
  skeletonRows?: number;
  /** pages of PAGE_SIZE rows (default true); the bar only appears above PAGE_SIZE rows. false for small embedded tables. */
  paginate?: boolean;
  /** URL param for the page (default "page"); give each paginated table of a same screen its own ("ordersPage"…) */
  pageKey?: string;
  /**
   * Server-side pagination + sort: `rows` is the current page, `total` the number of matching rows (from the API Page),
   * `list` the URL page/sort state (useServerList). Columns sort through `sortKey`; `defaultSort` / `pageKey` are ignored.
   */
  server?: { list: ServerList; total: number | undefined };
  className?: string;
}

/**
 * <DataTable columns={cols} rows={data} getRowId={(r) => r.id} onRowClick={(r) => nav(`/clients/${r.id}`)}
 *   loading={isLoading} empty={<EmptyState …/>} footer={`${data?.length ?? 0} clients`} />
 * Client-side (small lists): paginated (PAGE_SIZE, ?page=) automatically: sort the full list, then slice.
 * Server-side (big lists): <DataTable server={{ list, total: data?.total }} rows={data?.items} … /> — the API sorts,
 * filters and slices; compute `footer` from the Page extras (sums, total), never from the page rows.
 */
export function DataTable<T>(props: DataTableProps<T>) {
  if (props.inset) {
    return (
      <TableFrame className={props.className}>
        <DataTableInner {...props} className={undefined} />
      </TableFrame>
    );
  }
  return <DataTableInner {...props} />;
}

function DataTableInner<T>({ columns: allColumns, rows, getRowId, onRowClick, selectedId, loading, empty, footer, defaultSort, skeletonRows, inset, className, paginate = true, pageKey, server }: DataTableProps<T>) {
  const [localSort, setLocalSort] = useState<{ id: string; dir: "asc" | "desc" } | undefined>(defaultSort);
  const sort = server ? server.list.sort : localSort;
  const sorted = useMemo(() => {
    if (server || !rows || !sort) return rows;
    const col = allColumns.find((c) => c.id === sort.id);
    if (!col?.sortValue) return rows;
    const get = col.sortValue;
    return [...rows].sort((a, b) => {
      const va = get(a), vb = get(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const r = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "fr");
      return sort.dir === "asc" ? r : -r;
    });
  }, [rows, sort, allColumns, server]);
  // Client lists: sort the whole list first, then slice; a new sort goes back to page 1. Server lists: rows = the page.
  const pg = usePagination(sorted, server
    ? { key: server.list.pageKey, server: true, total: server.total }
    : { key: pageKey, enabled: paginate, resetKey: sort ? `${sort.id}:${sort.dir}` : "" });
  const width = useElementWidth(pg.anchorRef, allColumns.some((c) => c.hideBelow));
  const columns = useMemo(() => allColumns.filter((c) => !c.hideBelow || !width || width >= c.hideBelow), [allColumns, width]);

  const sortIdOf = (c: Column<T>) => (server ? c.sortKey : c.sortValue ? c.id : undefined);
  const toggle = (c: Column<T>) => {
    const id = sortIdOf(c);
    if (!id) return;
    const next = (s?: { id: string; dir: "asc" | "desc" }) =>
      s?.id === id ? { id, dir: s.dir === "asc" ? "desc" as const : "asc" as const } : { id, dir: c.numeric ? "desc" as const : "asc" as const };
    if (server) server.list.setSort(next(server.list.sort));
    else setLocalSort(next);
  };

  if (!loading && rows && rows.length === 0 && empty && !(server && pg.page > 1)) return <>{empty}</>;
  const edgeFooter = inset ? "border-t border-border px-3 py-2" : "px-5 py-2.5";

  return (
    <div ref={pg.anchorRef} className={className}>
      <Table>
        <colgroup>
          {columns.map((c) => <col key={c.id} style={c.width !== undefined ? { width: c.width } : undefined} />)}
        </colgroup>
        <THead>
          <tr>
            {columns.map((c) => (
              <TH
                key={c.id}
                align={c.align ?? (c.numeric ? "right" : "left")}
                onClick={sortIdOf(c) ? () => toggle(c) : undefined}
                className={cn(sortIdOf(c) && "cursor-pointer select-none hover:text-foreground")}
              >
                <span className={cn("inline-flex items-center gap-1", (c.align === "right" || c.numeric) && "flex-row-reverse")}>
                  {c.header}
                  {sort && sort.id === sortIdOf(c) ? (sort.dir === "asc" ? <ArrowUp size={11} /> : <ArrowDown size={11} />) : null}
                </span>
              </TH>
            ))}
          </tr>
        </THead>
        <TBody>
          {loading && !rows
            ? Array.from({ length: skeletonRows ?? (inset ? 3 : 10) }).map((_, i) => (
                <tr key={i} className="h-[34px]">
                  {columns.map((c) => (
                    <TD key={c.id} align={c.align ?? (c.numeric ? "right" : "left")}>
                      <Skeleton className={cn("h-3", c.numeric ? "ml-auto w-14" : i % 2 ? "w-24" : "w-32")} />
                    </TD>
                  ))}
                </tr>
              ))
            : pg.rows.map((row) => {
                const id = getRowId(row);
                return (
                  <TR key={id} liveId={id} selected={selectedId === id} onClick={onRowClick ? () => onRowClick(row) : undefined}>
                    {columns.map((c) => (
                      <TD key={c.id} align={c.align} numeric={c.numeric} mono={c.mono} muted={c.muted} className={c.className}>
                        {c.cell(row)}
                      </TD>
                    ))}
                  </TR>
                );
              })}
        </TBody>
      </Table>
      {pg.pageCount > 1 ? (
        <Pagination pagination={pg} inset={inset} sticky={!inset}>{footer}</Pagination>
      ) : footer ? (
        <div className={cn(edgeFooter, "text-[12px] text-muted-foreground")}>{footer}</div>
      ) : null}
    </div>
  );
}

/** Width of an element (0 until measured), tracked with a ResizeObserver; only when `enabled`. The element may mount
 *  after the first render (skeleton → rows, empty state → table), so the observer is (re)attached whenever it changes. */
function useElementWidth(ref: RefObject<HTMLElement | null>, enabled: boolean) {
  const [w, setW] = useState(0);
  const observed = useRef<{ el: HTMLElement; ro?: ResizeObserver } | null>(null);
  useLayoutEffect(() => {
    const el = enabled ? ref.current : null;
    if (observed.current?.el === el) return;
    observed.current?.ro?.disconnect();
    observed.current = null;
    if (!el) return;
    setW(el.clientWidth);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => setW(el.clientWidth)) : undefined;
    ro?.observe(el);
    observed.current = { el, ro };
  });
  useEffect(() => () => observed.current?.ro?.disconnect(), []);
  return w;
}
