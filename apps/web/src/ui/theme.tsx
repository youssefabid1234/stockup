import { useSyncExternalStore } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/cn";
import { SEGMENT_ITEM, SEGMENT_OFF, SEGMENT_ON, SEGMENT_TRACK } from "./input";

export type ThemePref = "light" | "dark" | "system";
const KEY = "kit-theme"; // keep in sync with the inline script in index.html
const listeners = new Set<() => void>();
const media = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function read(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch { return "system"; }
}
let pref: ThemePref = read();

function apply() {
  const dark = pref === "dark" || (pref === "system" && !!media?.matches);
  document.documentElement.classList.toggle("dark", dark);
}
media?.addEventListener("change", () => { if (pref === "system") { apply(); listeners.forEach((l) => l()); } });
apply();

export function setTheme(p: ThemePref) {
  pref = p;
  try { p === "system" ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, p); } catch { /* ignore */ }
  apply();
  listeners.forEach((l) => l());
}

/** const { theme, resolved, setTheme } = useTheme() */
export function useTheme() {
  const theme = useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => pref);
  const resolved: "light" | "dark" = theme === "system" ? (media?.matches ? "dark" : "light") : theme;
  return { theme, resolved, setTheme };
}

const OPTS: { id: ThemePref; icon: typeof Sun; label: string }[] = [
  { id: "light", icon: Sun, label: "Clair" },
  { id: "dark", icon: Moon, label: "Sombre" },
  { id: "system", icon: Monitor, label: "Système" },
];

/** Three-way light / dark / system switch (sidebar footer). */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme } = useTheme();
  return (
    <div role="radiogroup" aria-label="Thème" className={cn(SEGMENT_TRACK, className)}>
      {OPTS.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={theme === id}
          aria-label={label}
          title={label}
          onClick={() => setTheme(id)}
          className={cn("flex h-[22px] w-[26px] items-center justify-center", SEGMENT_ITEM, theme === id ? SEGMENT_ON : SEGMENT_OFF)}
        >
          <Icon size={13} strokeWidth={theme === id ? 2 : 1.75} aria-hidden />
        </button>
      ))}
    </div>
  );
}
