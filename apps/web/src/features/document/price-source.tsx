/** Small "i" next to a line's unit price: where the price comes from (Négocié / Règle « … » / Catalogue), via GET /prices/resolve. */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Info } from "lucide-react";
import type { Id } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtMoney } from "@/lib/format";
import { useResolvedPrice } from "@/lib/queries";
import { AnchoredPopover, SECTION_LABEL, Skeleton, TONE_DOT } from "@/ui";
import { MarginCell, SOURCE_META, SourceLabel } from "@/pages/prices/pickers";
import { ruleNameOf } from "@/pages/prices/resolved";

export function PriceSourceInfo({ clientId, productId, qty, date, unitPrice }: { clientId: Id; productId: Id; qty: number; date?: string; unitPrice: number }) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const hoverT = useRef<number>();
  // Resolve lazily: on first hover/click, then keep it fresh (it is cheap and cached).
  const [wanted, setWanted] = useState(false);
  const { data, isLoading } = useResolvedPrice({ clientId, productId, qty: qty > 0 ? qty : 1, date }, wanted);
  const r = data && data.productId === productId && data.clientId === clientId ? data : undefined;
  const manual = r && Math.abs(r.price - unitPrice) > 0.004;

  useEffect(() => {
    if (!pinned) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t) || popRef.current?.contains(t)) return;
      setPinned(false); setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); setPinned(false); setOpen(false); } };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => { document.removeEventListener("mousedown", onDown); window.removeEventListener("keydown", onKey, true); };
  }, [pinned]);

  const enter = () => { setWanted(true); window.clearTimeout(hoverT.current); hoverT.current = window.setTimeout(() => setOpen(true), 180); };
  const leave = () => { window.clearTimeout(hoverT.current); if (!pinned) hoverT.current = window.setTimeout(() => setOpen(false), 120); };
  const tone = r ? (manual ? "warning" : SOURCE_META[r.source].tone) : undefined;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        aria-label="Origine du prix"
        aria-expanded={open}
        onMouseEnter={enter}
        onMouseLeave={leave}
        onFocus={() => setWanted(true)}
        onClick={(e) => { e.stopPropagation(); setWanted(true); setPinned((p) => !p); setOpen((o) => (pinned ? !o : true)); }}
        className={cn(
          "relative grid size-[18px] shrink-0 place-items-center rounded-[3px] text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground",
          open && "bg-muted text-foreground",
        )}
      >
        <Info size={12} strokeWidth={1.75} />
        {tone && tone !== "muted" ? <span className={cn("absolute right-0 top-0 size-[5px] rounded-full", TONE_DOT[tone])} /> : null}
      </button>
      <AnchoredPopover anchorRef={btnRef} open={open} matchWidth={false} width={320} maxHeight={360} role="dialog" aria-label="Origine du prix">
        <div ref={popRef} onMouseEnter={() => window.clearTimeout(hoverT.current)} onMouseLeave={leave} className="flex flex-col gap-2 p-3 text-left">
          <div className={SECTION_LABEL}>Origine du prix</div>
          {!r ? (
            isLoading || !wanted ? <div className="flex flex-col gap-2"><Skeleton className="h-3 w-32" /><Skeleton className="h-3 w-full" /></div>
              : <div className="text-[12.5px] text-muted-foreground">Origine indisponible.</div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2">
                <SourceLabel source={r.source} ruleName={ruleNameOf(r.candidates.find((c) => c.applied)?.label ?? "")} className="text-[13px] font-medium text-foreground" />
                <span className="num shrink-0 text-[13px] font-semibold tabular-nums">{fmtMoney(r.price)}</span>
              </div>
              <p className="text-[12.5px] leading-[18px] text-secondary-foreground">{r.explanation}</p>
              {manual ? (
                <p className="rounded-[4px] border border-warning/30 bg-warning/10 px-2 py-1.5 text-[12px] leading-4 text-secondary-foreground">
                  Prix de la ligne modifié à la main : {fmtMoney(unitPrice)} au lieu de {fmtMoney(r.price)}.
                </p>
              ) : null}
              <div className="flex items-center gap-3 border-t border-border pt-2 text-[12px] text-muted-foreground">
                <span>Catalogue {fmtMoney(r.listPrice)}</span>
                <span>Coût {fmtMoney(r.cost)}</span>
                <span className="inline-flex items-center gap-1">Marge <MarginCell value={unitPrice > 0 ? (unitPrice - r.cost) / unitPrice : 0} /></span>
              </div>
              {r.candidates.length > 1 ? (
                <div className="text-[11.5px] text-muted-foreground">
                  {r.candidates.filter((c) => !c.applied).length} autre{r.candidates.filter((c) => !c.applied).length > 1 ? "s" : ""} prix envisagé{r.candidates.filter((c) => !c.applied).length > 1 ? "s" : ""} ·{" "}
                  <Link to={`/prices?tab=sim&sclient=${clientId}&sproduct=${productId}&sqty=${qty}${date ? `&sdate=${date}` : ""}`} className="text-primary hover:underline">
                    Voir le détail
                  </Link>
                </div>
              ) : null}
            </>
          )}
        </div>
      </AnchoredPopover>
    </>
  );
}
