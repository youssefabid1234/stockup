import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, BookOpen, Building2, CornerDownLeft, Package, Search, ShoppingCart, Users, type LucideIcon } from "lucide-react";
import type { SearchResult } from "@kit/shared";
import { cn } from "@/lib/cn";
import { useSearch } from "@/lib/queries";
import { useDebounced } from "@/lib/url-state";
import { NAV_ITEMS } from "@/app/nav";
import { shell, useShell } from "@/app/shell-state";
import { Kbd, Spinner } from "./button";
import { SECTION_LABEL } from "./section";

const TYPE_ICON: Record<SearchResult["type"], LucideIcon> = { client: Users, product: Package, supplier: Building2, order: ShoppingCart, context: BookOpen };
const TYPE_LABEL: Record<SearchResult["type"], string> = { client: "Client", product: "Produit", supplier: "Fournisseur", order: "Commande", context: "Contexte" };
const TYPE_PATH: Record<SearchResult["type"], string> = { client: "/clients", product: "/products", supplier: "/suppliers", order: "/orders", context: "/context" };

/** Route for a search result: /clients/:id, /products/:id, … */
export const searchResultPath = (r: Pick<SearchResult, "type" | "id">) =>
  r.type === "context" ? `/context?e=${r.id}` : `${TYPE_PATH[r.type]}/${r.id}`;

interface Item { key: string; icon: LucideIcon; label: string; sublabel?: string; hint?: string; run: () => void; group: string }

/** ⌘K palette. Mounted once in the shell; open with shell.openCommand() or ⌘K. Searches GET /api/search. */
export function CommandK() {
  const { commandOpen } = useShell();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const dq = useDebounced(q.trim(), 120);
  const { data, isFetching } = useSearch(commandOpen ? dq : "");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); shell.toggleCommand(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => { if (commandOpen) { setQ(""); setIdx(0); } }, [commandOpen]);

  const items = useMemo<Item[]>(() => {
    const go = (to: string) => () => {
      shell.closeCommand();
      if (to === "#assistant") shell.openAssistant();
      else navigate(to);
    };
    const needle = q.trim().toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
    const pages = NAV_ITEMS.filter((n) => {
      if (!needle) return true;
      const hay = `${n.label} ${n.keywords ?? ""}`.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
      return hay.includes(needle);
    }).map<Item>((n) => ({ key: `nav:${n.to}`, icon: n.icon, label: n.label, hint: "Aller à", run: go(n.to), group: "Pages" }));
    const results = (dq ? data ?? [] : []).slice(0, 12).map<Item>((r) => ({
      key: `${r.type}:${r.id}`, icon: TYPE_ICON[r.type], label: r.label, sublabel: r.sublabel, hint: TYPE_LABEL[r.type],
      run: go(searchResultPath(r)), group: "Résultats",
    }));
    return needle ? [...results, ...pages.slice(0, 4)] : pages;
  }, [q, dq, data, navigate]);

  useEffect(() => { setIdx(0); }, [items.length, dq]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${idx}"]`)?.scrollIntoView({ block: "nearest" });
  }, [idx]);

  if (!commandOpen) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(items.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); items[idx]?.run(); }
    else if (e.key === "Escape") { e.preventDefault(); shell.closeCommand(); }
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex justify-center bg-foreground/10 pt-[12vh] animate-fade-in dark:bg-black/40" onMouseDown={() => shell.closeCommand()}>
      <div
        role="dialog"
        aria-label="Recherche"
        onMouseDown={(e) => e.stopPropagation()}
        className="flex h-fit max-h-[460px] w-[600px] max-w-[calc(100vw-32px)] flex-col overflow-hidden rounded-[6px] border border-border bg-card shadow-pop"
      >
        <div className="flex h-11 shrink-0 items-center gap-2 border-b border-border px-3">
          {isFetching ? <Spinner size={14} className="text-muted-foreground" /> : <Search size={15} strokeWidth={1.75} className="text-muted-foreground" />}
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Rechercher un client, un produit, une commande…"
            className="h-full flex-1 bg-transparent text-[14px] outline-none placeholder:text-muted-foreground/70"
          />
          <Kbd>Échap</Kbd>
        </div>
        <div ref={listRef} className="min-h-0 flex-1 overflow-auto p-1.5">
          {items.length === 0 ? (
            <div className="px-3 py-8 text-center text-[12.5px] text-muted-foreground">
              {isFetching ? "Recherche…" : `Aucun résultat pour « ${q} »`}
            </div>
          ) : (
            items.map((it, i) => {
              const header = it.group !== lastGroup ? it.group : null;
              lastGroup = it.group;
              const Icon = it.icon;
              return (
                <div key={it.key}>
                  {header ? <div className={cn(SECTION_LABEL, "px-2 pb-1 pt-2")}>{header}</div> : null}
                  <button
                    type="button"
                    data-idx={i}
                    onMouseMove={() => setIdx(i)}
                    onClick={it.run}
                    className={cn("flex h-9 w-full items-center gap-2.5 rounded-[4px] px-2 text-left", i === idx ? "bg-muted" : "")}
                  >
                    <Icon size={14} strokeWidth={1.75} className="shrink-0 text-muted-foreground" />
                    <span className="truncate text-[13px]">{it.label}</span>
                    {it.sublabel ? <span className="truncate text-[12px] text-muted-foreground">{it.sublabel}</span> : null}
                    <span className="ml-auto flex shrink-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
                      {it.hint}
                      {i === idx ? <CornerDownLeft size={12} /> : <ArrowRight size={12} className="opacity-0" />}
                    </span>
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
