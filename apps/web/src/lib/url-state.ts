import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** Pagination params (`?page=`, `?ordersPage=`…). See usePagination in @/ui/pagination. */
export const isPageParam = (key: string) => key === "page" || key.endsWith("Page");

export interface UrlStateOptions {
  /**
   * Changing this param keeps the current page. Default false: any filter / tab / search change
   * sends every list on the page back to page 1. Set it for params that only open a panel (`?new=1`, `?p=<id>`).
   */
  keepPage?: boolean;
}

/*
 * Same-tick safety. react-router's `setSearchParams(fn)` hands `fn` the params of the LAST RENDER, not the result of a
 * previous call in the same tick, so `setA(x); setB(y)` used to compute two URLs from the same stale params and the
 * second one erased the first. Every write below goes through `writeParams`, which keeps the params it produced in
 * `pending` until the end of the tick (microtask): the next write in the same tick starts from them instead of the
 * stale render. Each navigation therefore carries all the patches so far, and the last one wins with everything.
 */
let pending: { path: string; params: URLSearchParams } | null = null;

function writeParams(
  setSp: ReturnType<typeof useSearchParams>[1],
  mutate: (next: URLSearchParams) => void,
) {
  setSp(
    (prev) => {
      const path = window.location.pathname;
      const base = pending && pending.path === path ? pending.params : prev;
      const next = new URLSearchParams(base);
      mutate(next);
      if (!pending) queueMicrotask(() => { pending = null; });
      pending = { path, params: next };
      return next;
    },
    { replace: true },
  );
}

/**
 * Filter state kept in the URL (?q=&type=) so lists are shareable and survive reloads.
 *   const [q, setQ] = useUrlState("q");
 *   const [sel, setSel] = useUrlState("p", "", { keepPage: true }); // side panel: don't reset pagination
 * Setting a value also clears the pagination params (back to page 1) unless `keepPage`.
 * Safe to call several setters in the same tick (`setQ(""); setType("")`): the patches merge.
 */
export function useUrlState(key: string, fallback = "", opts?: UrlStateOptions): [string, (v: string) => void] {
  const [sp, setSp] = useSearchParams();
  const value = sp.get(key) ?? fallback;
  const keepPage = !!opts?.keepPage || isPageParam(key);
  const set = useCallback(
    (v: string) =>
      writeParams(setSp, (next) => {
        const stored = !v || v === fallback ? null : v;
        if (next.get(key) === stored) return;
        if (stored === null) next.delete(key);
        else next.set(key, stored);
        if (!keepPage) for (const k of [...next.keys()]) if (isPageParam(k)) next.delete(k);
      }),
    [key, fallback, keepPage, setSp],
  );
  return [value, set];
}

/**
 * Several params at once: `patch({ tab: "sim", rule: "", add: "" })`. "" / undefined removes a key.
 * Pagination params not named in the patch are reset unless `keepPage`. Merges with same-tick `useUrlState` setters.
 */
export function useUrlPatch() {
  const [, setSp] = useSearchParams();
  return useCallback(
    (patch: Record<string, string | undefined>, opts?: { keepPage?: boolean }) =>
      writeParams(setSp, (next) => {
        for (const [k, v] of Object.entries(patch)) {
          if (!v) next.delete(k);
          else next.set(k, v);
        }
        if (!opts?.keepPage) for (const k of [...next.keys()]) if (isPageParam(k) && !(k in patch)) next.delete(k);
      }),
    [setSp],
  );
}

/** Debounced copy of a value (search boxes). */
export function useDebounced<T>(value: T, ms = 200): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}
