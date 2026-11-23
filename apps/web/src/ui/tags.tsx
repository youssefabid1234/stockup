/**
 * Groups (tags) on clients, products and suppliers.
 *
 *   <TagChip tag={def} />                              // colored dot + label, 3px radius
 *   <TagChip scope="client" id="gastro" />             // resolves the label/color from GET /tags
 *   <TagList scope="product" tags={p.tags} max={3} />  // read-only row of chips, "+2" overflow
 *   <TagEditor scope="client" value={c.tags} onChange={(tags) => save(tags)} />
 *   <TagEditor scope="client" value={c.tags} entityId={c.id} />   // saves itself (PATCH /clients/:id { tags })
 *
 * TagEditor: chips with ×, then a "+ Groupe" button opening a popover with search and a
 * "Créer le groupe « … »" option (POST /tags, slug from the label).
 */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Search, X } from "lucide-react";
import type { TagDef } from "@kit/shared";
import { cn } from "@/lib/cn";
import { api, type TagScope, type TagWithCount } from "@/lib/api";
import { qk, useTags } from "@/lib/queries";
import { AnchoredPopover } from "./popover";

export type TagColor = NonNullable<TagDef["color"]>;
export const TAG_COLORS: TagColor[] = ["green", "teal", "amber", "blue", "rose", "violet", "gray"];
export const TAG_COLOR_LABEL: Record<TagColor, string> = {
  green: "Vert", teal: "Turquoise", amber: "Ambre", blue: "Bleu", rose: "Rose", violet: "Violet", gray: "Gris",
};
/** Tag color → token class for the 6px dot. */
export const TAG_DOT: Record<TagColor, string> = {
  green: "bg-chart-1",
  teal: "bg-chart-2",
  amber: "bg-chart-3",
  blue: "bg-chart-4",
  rose: "bg-chart-5",
  violet: "bg-violet",
  gray: "bg-muted-foreground/50",
};
export const TAG_SCOPE_LABEL: Record<TagScope, string> = { client: "Clients", product: "Produits", supplier: "Fournisseurs" };

/** "Restaurants gastro" → "restaurants-gastro" (API slug rule: a-z, 0-9, -). */
export function tagSlug(label: string, taken: string[] = []): string {
  const base =
    label.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "groupe";
  let id = base;
  for (let i = 2; taken.includes(id); i++) id = `${base}-${i}`;
  return id;
}

export function TagDot({ color, className }: { color?: TagDef["color"]; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-1.5 shrink-0 rounded-full", TAG_DOT[color ?? "gray"], className)} />;
}

/** Map of tag id → def for one scope (from the cached GET /tags?scope=). */
export function useTagDefs(scope: TagScope) {
  const { data } = useTags(scope);
  return useMemo(() => new Map((data ?? []).map((t) => [t.id, t] as const)), [data]);
}

type ChipProps = {
  tag?: Pick<TagDef, "id" | "label" | "color">;
  scope?: TagScope;
  id?: string;
  onRemove?: () => void;
  onClick?: () => void;
  className?: string;
  title?: string;
};

/** Colored dot + label chip. Pass a full `tag`, or `scope` + `id` to resolve it from GET /tags. */
export function TagChip(props: ChipProps) {
  if (!props.tag && props.scope && props.id) return <ResolvedChip {...props} scope={props.scope} id={props.id} />;
  return <ChipView {...props} />;
}

function ResolvedChip(props: ChipProps & { scope: TagScope; id: string }) {
  const defs = useTagDefs(props.scope);
  return <ChipView {...props} tag={defs.get(props.id) ?? { id: props.id, label: props.id }} />;
}

function ChipView({ tag, id, onRemove, onClick, className, title }: ChipProps) {
  const label = tag?.label ?? id ?? "";
  const Comp = onClick ? "button" : "span";
  return (
    <Comp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      title={title ?? label}
      className={cn(
        "inline-flex h-[20px] max-w-[200px] items-center gap-1.5 whitespace-nowrap rounded-[3px] border border-border bg-surface-2 pl-1.5 text-[11.5px] font-medium text-secondary-foreground",
        onRemove ? "pr-0.5" : "pr-1.5",
        onClick && "hover:border-border-hover hover:bg-muted",
        className,
      )}
    >
      <TagDot color={tag?.color} />
      <span className="truncate">{label}</span>
      {onRemove && (
        <span
          role="button"
          tabIndex={-1}
          aria-label={`Retirer ${label}`}
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="grid size-4 place-items-center rounded-[2px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={11} strokeWidth={2} />
        </span>
      )}
    </Comp>
  );
}

/** Read-only chips for tag ids. `max` collapses the rest into "+N". */
export function TagList({ scope, tags, max, empty, className, fit }: {
  scope: TagScope;
  tags?: string[];
  max?: number;
  empty?: ReactNode;
  className?: string;
  /** Table cell mode: one line that never widens its column; chips shrink with an ellipsis, "+N" stays visible. */
  fit?: boolean;
}) {
  const defs = useTagDefs(scope);
  const list = tags ?? [];
  if (!list.length) return <>{empty ?? null}</>;
  const shown = max ? list.slice(0, max) : list;
  const rest = list.length - shown.length;
  return (
    <span className={cn(fit ? "flex w-0 min-w-full flex-nowrap items-center gap-1 overflow-hidden" : "inline-flex flex-wrap items-center gap-1", className)}>
      {shown.map((t) => <TagChip key={t} tag={defs.get(t) ?? { id: t, label: t }} className={fit ? "min-w-0 shrink" : undefined} />)}
      {rest > 0 && (
        <span className={cn("text-[11.5px] text-muted-foreground", fit && "shrink-0")} title={list.slice(shown.length).map((t) => defs.get(t)?.label ?? t).join(", ")}>
          +{rest}
        </span>
      )}
    </span>
  );
}

/**
 * Inline add/remove of groups. Either controlled (`onChange`) or self-saving (`entityId`: PATCH the entity's tags).
 * `onChange` may return a promise; the editor shows the new value optimistically.
 */
export function TagEditor({ scope, value, onChange, entityId, disabled, className, addLabel = "Groupe" }: {
  scope: TagScope;
  value?: string[];
  onChange?: (tags: string[]) => unknown;
  entityId?: string;
  disabled?: boolean;
  className?: string;
  addLabel?: string;
}) {
  const qc = useQueryClient();
  const { data: defsList } = useTags(scope);
  const defs = useMemo(() => new Map((defsList ?? []).map((t) => [t.id, t] as const)), [defsList]);
  const [local, setLocal] = useState<string[] | null>(null);
  const current = local ?? value ?? [];
  useEffect(() => setLocal(null), [value]);

  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const commit = async (next: string[]) => {
    setLocal(next);
    try {
      if (onChange) await onChange(next);
      else if (entityId) {
        await api.tags.setOn(scope, entityId, next);
        const roots = { client: qk.clients.all, product: qk.products.all, supplier: qk.suppliers.all }[scope];
        void qc.invalidateQueries({ queryKey: roots });
      }
      void qc.invalidateQueries({ queryKey: qk.tags.all });
      void qc.invalidateQueries({ queryKey: qk.pricing.all });
    } catch {
      setLocal(null);
    }
  };

  const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const options = useMemo(() => {
    const n = norm(q.trim());
    return (defsList ?? []).filter((t) => !n || norm(`${t.label} ${t.id}`).includes(n));
  }, [defsList, q]);
  const exact = (defsList ?? []).some((t) => norm(t.label) === norm(q.trim()));
  const canCreate = q.trim().length > 1 && !exact;
  const itemCount = options.length + (canCreate ? 1 : 0);

  useEffect(() => {
    if (!open) return;
    setActive(0);
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    const onDown = (e: MouseEvent) => {
      const el = e.target as Node;
      if (popRef.current?.contains(el) || anchorRef.current?.contains(el)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => { clearTimeout(t); document.removeEventListener("mousedown", onDown); };
  }, [open]);
  useEffect(() => setActive(0), [q]);

  const toggle = (id: string) => void commit(current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);
  const create = async () => {
    const label = q.trim();
    const id = tagSlug(label, (defsList ?? []).map((t) => t.id));
    const color = TAG_COLORS[(defsList?.length ?? 0) % (TAG_COLORS.length - 1)];
    try {
      await api.tags.create({ id, scope, label, color });
      qc.setQueryData<TagWithCount[]>(qk.tags.list(scope), (old) => [...(old ?? []), { id, scope, label, color, count: 0 }]);
      setQ("");
      await commit([...current, id]);
    } catch { /* toasted by api */ }
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); anchorRef.current?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(itemCount - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (active < options.length) toggle(options[active].id);
      else if (canCreate) void create();
    }
  };

  return (
    <div className={cn("flex flex-wrap items-center gap-1", className)}>
      {current.map((t) => (
        <TagChip key={t} tag={defs.get(t) ?? { id: t, label: t }} onRemove={disabled ? undefined : () => toggle(t)} />
      ))}
      {!disabled && (
        <button
          ref={anchorRef}
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="inline-flex h-[20px] items-center gap-1 rounded-[3px] border border-dashed border-border px-1.5 text-[11.5px] text-muted-foreground hover:border-border-hover hover:text-foreground"
        >
          <Plus size={11} strokeWidth={2} />
          {addLabel}
        </button>
      )}
      <AnchoredPopover anchorRef={anchorRef} open={open} matchWidth={false} width={260} maxHeight={300} role="dialog" aria-label="Groupes">
        <div ref={popRef} className="flex flex-col">
          <div className="flex items-center gap-1.5 border-b border-border px-2.5">
            <Search size={13} strokeWidth={1.75} className="text-muted-foreground" />
            <input
              ref={inputRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={onKey}
              placeholder="Chercher ou créer un groupe…"
              className="h-8 w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/70"
            />
          </div>
          <div className="py-1" role="listbox">
            {options.map((t, i) => {
              const on = current.includes(t.id);
              return (
                <button
                  key={t.id}
                  type="button"
                  role="option"
                  aria-selected={on}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => toggle(t.id)}
                  className={cn("flex h-7 w-full items-center gap-2 px-2.5 text-left text-[13px]", i === active && "bg-muted")}
                >
                  <TagDot color={t.color} />
                  <span className="min-w-0 flex-1 truncate">{t.label}</span>
                  <span className="text-[11.5px] tabular-nums text-muted-foreground">{t.count}</span>
                  <Check size={13} strokeWidth={2} className={cn("text-primary", !on && "invisible")} />
                </button>
              );
            })}
            {!options.length && !canCreate && (
              <div className="px-2.5 py-2 text-[12.5px] text-muted-foreground">
                {defsList?.length ? "Aucun groupe trouvé" : "Aucun groupe : tapez un nom pour en créer un"}
              </div>
            )}
            {canCreate && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(options.length)}
                onClick={() => void create()}
                className={cn(
                  "flex h-7 w-full items-center gap-2 px-2.5 text-left text-[13px] text-primary",
                  options.length > 0 && "border-t border-border",
                  active === options.length && "bg-muted",
                )}
              >
                <Plus size={13} strokeWidth={2} />
                <span className="truncate">Créer le groupe « {q.trim()} »</span>
              </button>
            )}
          </div>
        </div>
      </AnchoredPopover>
    </div>
  );
}

/** Row of color swatches (groups page). */
export function TagColorPicker({ value, onChange }: { value?: TagDef["color"]; onChange: (c: TagColor) => void }) {
  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label="Couleur">
      {TAG_COLORS.map((c) => (
        <button
          key={c}
          type="button"
          role="radio"
          aria-checked={value === c}
          title={TAG_COLOR_LABEL[c]}
          onClick={() => onChange(c)}
          className={cn(
            "grid size-5 place-items-center rounded-[3px] border",
            value === c ? "border-foreground/40 bg-surface-2" : "border-transparent hover:bg-muted",
          )}
        >
          <span className={cn("size-2.5 rounded-full", TAG_DOT[c])} />
        </button>
      ))}
    </div>
  );
}
