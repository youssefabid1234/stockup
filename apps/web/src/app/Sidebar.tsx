import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { cn } from "@/lib/cn";
import { useMeta, useStreamStatus } from "@/lib/queries";
import { Dot, IconButton, Kbd, ResizeHandle, SECTION_LABEL, ThemeToggle, useResizableWidth } from "@/ui";
import { NAV, type NavItem } from "./nav";
import { shell, useShell } from "./shell-state";

/** Collapsed rail width: icons stay at the exact same x as when expanded, so collapsing never shifts them. */
export const RAIL_WIDTH = 56;

const ROW = "flex h-[30px] items-center gap-2.5 rounded-[4px] px-2 text-[13px] transition-colors duration-100";
const LABEL = "truncate transition-opacity duration-200 ease-out motion-reduce:transition-none";

function Item({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const { assistantOpen } = useShell();
  const Icon = item.icon;
  const width = collapsed ? "w-[31px]" : "w-full";
  if (item.to === "#assistant") {
    return (
      <button
        type="button"
        onClick={shell.toggleAssistant}
        title={collapsed ? `${item.label} (⌘J)` : undefined}
        aria-label={item.label}
        aria-pressed={assistantOpen}
        className={cn(ROW, width, assistantOpen ? "bg-row-selected font-medium text-foreground" : "text-secondary-foreground hover:bg-muted")}
      >
        <Icon size={15} strokeWidth={1.75} className="shrink-0 text-violet" />
        <span className={cn(LABEL, collapsed && "opacity-0")}>{item.label}</span>
        {collapsed ? null : <Kbd className="ml-auto">⌘J</Kbd>}
      </button>
    );
  }
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      title={collapsed ? item.label : undefined}
      aria-label={item.label}
      className={({ isActive }) =>
        cn(ROW, width, isActive ? "bg-row-selected font-medium text-foreground" : "text-secondary-foreground hover:bg-muted")
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={15} strokeWidth={1.75} className={cn("shrink-0", isActive ? "text-foreground" : "text-muted-foreground")} />
          <span className={cn(LABEL, collapsed && "opacity-0")}>{item.label}</span>
        </>
      )}
    </NavLink>
  );
}

/** Stockline mark (three stacked bars): black in light mode, white in dark mode. Never redrawn. */
function StocklineMark() {
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center" aria-hidden>
      <img src="/brand/stockline-mark-black.svg" alt="" width={18} height={18} className="h-[18px] w-[18px] dark:hidden" />
      <img src="/brand/stockline-mark-white.svg" alt="" width={18} height={18} className="hidden h-[18px] w-[18px] dark:block" />
    </span>
  );
}

/**
 * Left nav. Expanded: resizable by its right edge (200–360px, double-click → 232). Collapsed (⌘\ or ⌘B): a 56px
 * icon rail with tooltips. Width + label opacity animate (200ms ease-out, off with prefers-reduced-motion).
 */
export function Sidebar() {
  const { data: meta } = useMeta();
  useEffect(() => {
    if (meta?.company) document.title = `${meta.company} — ERP`;
  }, [meta?.company]);
  const status = useStreamStatus();
  const { sidebarCollapsed: collapsed } = useShell();
  const r = useResizableWidth("sidebar", 232, 200, 360);
  const fade = cn("transition-opacity duration-200 ease-out motion-reduce:transition-none", collapsed && "pointer-events-none opacity-0");
  return (
    <div
      data-sidebar={collapsed ? "collapsed" : "expanded"}
      style={{ width: collapsed ? RAIL_WIDTH : r.width }}
      className={cn(
        "relative h-full shrink-0 overflow-hidden border-r border-border bg-background",
        !r.dragging && "transition-[width] duration-200 ease-out motion-reduce:transition-none",
      )}
    >
      {/* Content keeps the expanded width while the outer box animates, so nothing reflows mid-animation. */}
      <nav style={{ width: Math.max(r.width, RAIL_WIDTH) }} className="flex h-full flex-col">
        <div className="group/head relative flex h-12 shrink-0 items-center gap-2.5 px-4">
          <StocklineMark />
          <div className={cn("min-w-0 flex-1", fade)}>
            <div className="truncate text-[13.5px] font-semibold leading-4">{meta?.company ?? "ERP"}</div>
            <div className="truncate text-[11px] leading-4 text-muted-foreground">
              {meta?.trade ? `Grossiste ${meta.trade}` : "Grossiste alimentaire"}
            </div>
          </div>
          {/* Linear-like: the collapse control appears on header hover / focus, over the end of the subtitle. */}
          {collapsed ? null : (
            <IconButton
              icon={PanelLeftClose}
              label="Réduire la barre latérale (⌘\)"
              size="sm"
              onClick={shell.toggleSidebar}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-background opacity-0 transition-opacity focus-visible:opacity-100 group-hover/head:opacity-100"
            />
          )}
        </div>
        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={shell.openCommand}
            title={collapsed ? "Rechercher (⌘K)" : undefined}
            aria-label="Rechercher"
            className={cn(
              "flex h-8 items-center gap-2 overflow-hidden rounded-[4px] border border-border bg-card px-2.5 text-[12.5px] text-muted-foreground transition-colors hover:border-border-hover hover:text-foreground",
              collapsed ? "w-[31px] justify-center px-0" : "w-full",
            )}
          >
            <Search size={13} strokeWidth={1.75} className="shrink-0" />
            {collapsed ? null : (
              <>
                <span className="truncate">Rechercher…</span>
                <Kbd className="ml-auto">⌘K</Kbd>
              </>
            )}
          </button>
        </div>
        <div className={cn("min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-3")}>
          {NAV.map((g, i) => (
            <div key={i} className={cn(i > 0 && "mt-3")}>
              {g.label ? (
                <div className={cn(SECTION_LABEL, "relative mb-1 px-2")}>
                  <span className={fade}>{g.label}</span>
                  {collapsed ? <span aria-hidden className="absolute left-2 top-1/2 h-px w-[15px] bg-border" /> : null}
                </div>
              ) : null}
              <div className="flex flex-col gap-px">
                {g.items.map((it) => <Item key={it.to} item={it} collapsed={collapsed} />)}
              </div>
            </div>
          ))}
        </div>
        <div className="flex h-11 shrink-0 items-center gap-2 border-t border-border px-4">
          {collapsed ? (
            <IconButton icon={PanelLeftOpen} label="Déplier la barre latérale (⌘\)" size="sm" onClick={shell.toggleSidebar} className="-ml-[1px]" />
          ) : (
            <>
              <span
                className="flex items-center gap-1.5 whitespace-nowrap text-[11.5px] text-muted-foreground"
                title="Flux d'activité temps réel (/api/events/stream)"
              >
                <Dot tone={status === "live" ? "success" : status === "connecting" ? "warning" : "destructive"} pulse={status === "live"} />
                {status === "live" ? "En direct" : status === "connecting" ? "Connexion…" : "Hors ligne"}
              </span>
              <ThemeToggle className="ml-auto" />
            </>
          )}
        </div>
      </nav>
      {collapsed ? null : <ResizeHandle r={r} edge="right" label="Redimensionner la barre latérale" />}
    </div>
  );
}
