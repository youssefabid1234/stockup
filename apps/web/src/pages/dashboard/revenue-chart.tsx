/** Hand-rolled SVG bar chart for revenue by day (chart tokens, no chart lib). Hover = tooltip, click = that day's orders. */
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { fmtDate, fmtMoney } from "@/lib/format";

interface Point { date: string; revenue: number }

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/** 1-2-5 "nice" ceiling for the y axis. */
function niceMax(v: number) {
  if (v <= 0) return 100;
  const p = 10 ** Math.floor(Math.log10(v));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}

const H = 176;
const PAD = { top: 10, right: 4, bottom: 22, left: 48 };

export function RevenueChart({ data, today, onPick }: { data: Point[]; today: string; onPick?: (date: string) => void }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d.revenue))), [data]);

  const innerW = Math.max(0, width - PAD.left - PAD.right);
  const innerH = H - PAD.top - PAD.bottom;
  const step = data.length ? innerW / data.length : 0;
  const barW = Math.max(2, Math.min(22, step * 0.66));
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const ticks = [0, max / 2, max];
  const h = hover != null ? data[hover] : undefined;

  return (
    <div ref={ref} className="relative w-full" style={{ height: H }} onMouseLeave={() => setHover(null)}>
      {width > 0 ? (
        <svg width={width} height={H} role="img" aria-label="Chiffre d'affaires des 30 derniers jours" className="block">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="hsl(var(--border))" strokeDasharray={t === 0 ? undefined : "2 3"} />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-muted-foreground text-[10.5px]">
                {fmtMoney(t, { compact: true })}
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const x = PAD.left + i * step + (step - barW) / 2;
            const top = y(d.revenue);
            const isToday = d.date === today;
            const on = hover === i;
            return (
              <g key={d.date}>
                <rect
                  x={x} y={top} width={barW} height={Math.max(0, PAD.top + innerH - top)} rx={1.5}
                  fill={isToday ? "hsl(var(--primary))" : "hsl(var(--chart-1))"}
                  fillOpacity={hover == null ? (isToday ? 1 : 0.72) : on ? 1 : 0.38}
                  className="transition-[fill-opacity] duration-100"
                />
                <rect
                  x={PAD.left + i * step} y={PAD.top} width={step} height={innerH} fill="transparent"
                  className={cn(onPick && "cursor-pointer")}
                  onMouseEnter={() => setHover(i)}
                  onClick={() => onPick?.(d.date)}
                />
                {i % 7 === (data.length - 1) % 7 ? (
                  <text x={PAD.left + i * step + step / 2} y={H - 6} textAnchor="middle" className={cn("text-[10.5px]", isToday ? "fill-foreground font-medium" : "fill-muted-foreground")}>
                    {isToday ? "auj." : fmtDate(d.date).replace(/^\S+\s/, "")}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      ) : null}
      {h && hover != null ? (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-[4px] border border-border bg-card px-2 py-1 text-[12px] shadow-pop"
          style={{ left: Math.min(Math.max(PAD.left + hover * step + step / 2, 70), width - 70), top: Math.max(y(h.revenue) - 6, 40) }}
        >
          <div className="text-muted-foreground">{fmtDate(h.date)}</div>
          <div className="num font-medium">{fmtMoney(h.revenue)}</div>
        </div>
      ) : null}
    </div>
  );
}
