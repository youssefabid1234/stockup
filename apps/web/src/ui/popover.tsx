/**
 * Anchored popovers that escape `overflow: hidden/auto` ancestors (table frames, scroll panes, side panels).
 * The panel is portaled to <body> with `position: fixed`, placed below the anchor (flipped above when it does not
 * fit), clamped to the viewport, and re-placed on scroll (any ancestor) and resize.
 *
 *   const anchorRef = useRef<HTMLDivElement>(null);
 *   <div ref={anchorRef}><input …/></div>
 *   <AnchoredPopover anchorRef={anchorRef} open={open} matchWidth>…</AnchoredPopover>
 */
import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";

const GAP = 4;
const MARGIN = 8;

export interface AnchoredPosition { top: number; left: number; width: number; maxHeight: number; above: boolean }

/** Computes a fixed position for `popRef` next to `anchorRef` while `open`. Returns null until measured. */
export function useAnchoredPosition(
  anchorRef: RefObject<HTMLElement | null>,
  popRef: RefObject<HTMLElement | null>,
  open: boolean,
  { width, matchWidth, maxHeight = 320 }: { width?: number; matchWidth?: boolean; maxHeight?: number } = {},
) {
  const [pos, setPos] = useState<AnchoredPosition | null>(null);

  const place = useCallback(() => {
    const a = anchorRef.current;
    if (!a) return;
    const r = a.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const w = Math.min(matchWidth ? Math.max(r.width, width ?? 0) : width ?? r.width, vw - 2 * MARGIN);
    const natural = Math.min(popRef.current?.scrollHeight ?? maxHeight, maxHeight);
    const below = vh - MARGIN - (r.bottom + GAP);
    const aboveSpace = r.top - GAP - MARGIN;
    const above = natural > below && aboveSpace > below;
    const mh = Math.max(80, Math.min(maxHeight, above ? aboveSpace : below));
    const h = Math.min(natural, mh);
    const top = above ? r.top - GAP - h : r.bottom + GAP;
    const left = Math.max(MARGIN, Math.min(r.left, vw - w - MARGIN));
    setPos((p) =>
      p && p.top === top && p.left === left && p.width === w && p.maxHeight === mh && p.above === above ? p : { top, left, width: w, maxHeight: mh, above },
    );
  }, [anchorRef, popRef, width, matchWidth, maxHeight]);

  useLayoutEffect(() => {
    if (!open) { setPos(null); return; }
    place();
    const onWin = () => place();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    // Content height changes (results arriving) must re-place, e.g. to flip above.
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onWin) : null;
    if (popRef.current) ro?.observe(popRef.current);
    if (anchorRef.current) ro?.observe(anchorRef.current);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
      ro?.disconnect();
    };
  }, [open, place, anchorRef, popRef]);

  return { pos, place };
}

/** Fixed, portaled panel anchored to `anchorRef`. Keep focus on the anchor: add onMouseDown preventDefault on items. */
export function AnchoredPopover({ anchorRef, open, children, className, width, matchWidth = true, maxHeight = 320, style, ...rest }: {
  anchorRef: RefObject<HTMLElement | null>;
  open: boolean;
  children: ReactNode;
  className?: string;
  width?: number;
  matchWidth?: boolean;
  maxHeight?: number;
  style?: CSSProperties;
  role?: string;
  id?: string;
  "aria-label"?: string;
}) {
  const popRef = useRef<HTMLDivElement>(null);
  const { pos } = useAnchoredPosition(anchorRef, popRef, open, { width, matchWidth, maxHeight });
  if (!open) return null;
  return createPortal(
    <div
      ref={popRef}
      {...rest}
      style={{
        top: pos?.top ?? -9999,
        left: pos?.left ?? -9999,
        width: pos?.width,
        maxHeight: pos?.maxHeight ?? maxHeight,
        opacity: pos ? 1 : 0,
        ...style,
      }}
      className={cn("fixed z-[55] overflow-auto rounded-[6px] border border-border bg-card text-foreground shadow-pop", className)}
    >
      {children}
    </div>,
    document.body,
  );
}
