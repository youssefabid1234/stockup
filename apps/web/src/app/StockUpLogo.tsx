// Team 12 · StockUp brand: the mark (blue roof over a navy « S » box) and the wordmark, crisp in light and dark.
import { cn } from "@/lib/cn";

export const BRAND = { blue: "#1F6BFF", navy: "#0F1E45" };

export function StockUpMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 240 256" className={cn("h-8 w-8 shrink-0", className)} aria-hidden="true">
      <path d="M10 66 L120 2 L234 68 L234 112 L224 116 L120 56 L48 98 Z" fill={BRAND.blue} />
      <path d="M2 104 L104 158 L172 120 L172 206 L92 252 L2 202 L2 170 L96 220 L96 190 L2 138 Z" className="fill-[#0F1E45] dark:fill-white" />
    </svg>
  );
}

export function StockUpLogo({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)} aria-label="StockUp">
      <StockUpMark className="shrink-0" />
      <span style={{ fontSize: size, lineHeight: 1 }} className="font-[800] tracking-[-0.035em]">
        <span className="text-[#0F1E45] dark:text-white">Stock</span><span className="text-[#1F6BFF]">Up</span>
      </span>
    </span>
  );
}
