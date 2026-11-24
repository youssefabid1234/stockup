import { useSyncExternalStore } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/cn";

export type ToastTone = "success" | "error" | "warning" | "info";
export interface ToastItem { id: number; tone: ToastTone; title: string; description?: string }

let items: ToastItem[] = [];
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function push(tone: ToastTone, title: string, description?: string, ms = tone === "error" ? 6000 : 3500) {
  const dup = items.find((t) => t.tone === tone && t.title === title && t.description === description);
  if (dup) return dup.id; // same message already visible (e.g. API down → many failing queries)
  const id = ++seq;
  items = [...items, { id, tone, title, description }].slice(-5);
  emit();
  window.setTimeout(() => dismiss(id), ms);
  return id;
}
function dismiss(id: number) {
  items = items.filter((t) => t.id !== id);
  emit();
}

/** Imperative toasts, callable anywhere (also outside React): toast.success("Commande confirmée"). */
export const toast = {
  success: (title: string, description?: string) => push("success", title, description),
  error: (title: string, description?: string) => push("error", title, description),
  warning: (title: string, description?: string) => push("warning", title, description),
  info: (title: string, description?: string) => push("info", title, description),
  dismiss,
};

const ICON = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info } as const;
const TONE = { success: "text-success", error: "text-destructive", warning: "text-warning", info: "text-info" } as const;

/** Mounted once in the app shell. */
export function Toaster() {
  const list = useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => items,
  );
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[340px] flex-col gap-2">
      {list.map((t) => {
        const Icon = ICON[t.tone];
        return (
          <div key={t.id} role="status" className="pointer-events-auto flex animate-slide-in items-start gap-2.5 rounded-[6px] border border-border bg-card px-3 py-2.5 shadow-pop">
            <Icon size={15} strokeWidth={1.75} className={cn("mt-px shrink-0", TONE[t.tone])} />
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium">{t.title}</div>
              {t.description ? <div className="mt-0.5 text-[12px] text-muted-foreground">{t.description}</div> : null}
            </div>
            <button type="button" onClick={() => dismiss(t.id)} className="text-muted-foreground hover:text-foreground" aria-label="Fermer">
              <X size={13} strokeWidth={1.75} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
