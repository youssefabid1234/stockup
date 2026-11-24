/** Règles tab: PriceRuleSummary table + create/edit SidePanel with scope pickers, method, live preview. */
import { useEffect, useMemo, useState } from "react";
import { Percent, Plus, Trash2 } from "lucide-react";
import type {
  PriceRule, PriceRuleClientScope, PriceRuleInput, PriceRuleMethod, PriceRuleProductScope, PriceRuleSummary, ProductCategory, ProductSummary,
} from "@kit/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fmtDate, fmtMoney, parseDate, todayIso } from "@/lib/format";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { qk, useApiMutation, useProducts, useTags } from "@/lib/queries";
import {
  Button, DataTable, DatePicker, Dot, EmptyState, Field, Input, Money, SECTION_LABEL, Segmented, Select, SidePanel, TagDot, Textarea, useTagDefs,
  type Column, type TagColor, type Tone,
} from "@/ui";
import { Combobox, MarginCell, useClientOptions, useProductOptions, useTagOptions } from "./pickers";


// ── Small inline controls ──

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(e) => { e.stopPropagation(); onChange(!checked); }}
      className={cn(
        "relative inline-flex h-4 w-7 shrink-0 items-center rounded-full border transition-colors disabled:opacity-50",
        checked ? "border-primary bg-primary" : "border-border bg-muted",
      )}
    >
      <span className={cn("size-3 rounded-full bg-card shadow-sm transition-transform", checked ? "translate-x-[13px]" : "translate-x-[1px]")} />
    </button>
  );
}

/** Two-step delete without a modal: first click arms, second click deletes, blur/timeout disarms. */
export function InlineConfirmDelete({ onConfirm, label = "Delete", pending, size = "sm", text }: {
  onConfirm: () => void; label?: string; pending?: boolean; size?: "sm" | "md"; text?: boolean;
}) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = window.setTimeout(() => setArmed(false), 4000);
    return () => window.clearTimeout(t);
  }, [armed]);
  if (armed) {
    return (
      <span className="inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        {text ? <Button size={size} variant="ghost" onMouseDown={(e) => e.preventDefault()} onClick={() => setArmed(false)}>Cancel</Button> : null}
        <Button size={size} variant="danger" loading={pending} onClick={onConfirm} onBlur={() => setArmed(false)} autoFocus title="Click again to delete">
          {text ? "Confirm deletion" : "Delete?"}
        </Button>
      </span>
    );
  }
  return text ? (
    <Button size={size} variant="ghost" icon={Trash2} className="text-muted-foreground hover:text-destructive" onClick={(e) => { e.stopPropagation(); setArmed(true); }}>{label}</Button>
  ) : (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={(e) => { e.stopPropagation(); setArmed(true); }}
      className="grid size-[26px] place-items-center rounded-[4px] text-muted-foreground hover:bg-muted hover:text-destructive"
    >
      <Trash2 size={14} strokeWidth={1.75} />
    </button>
  );
}

export function validityLabel(r: Pick<PriceRule, "validFrom" | "validTo">, today = todayIso()) {
  if (r.validTo && r.validTo < today) return { text: `Expires on ${fmtDate(r.validTo)}`, muted: true };
  if (r.validFrom && r.validFrom > today) return { text: `From ${fmtDate(r.validFrom)}${r.validTo ? ` → ${fmtDate(r.validTo)}` : ""}`, muted: false, future: true };
  if (r.validFrom && r.validTo) return { text: `${fmtDate(r.validFrom)} → ${fmtDate(r.validTo)}`, muted: false };
  if (r.validTo) return { text: `Until ${fmtDate(r.validTo)}`, muted: false };
  if (r.validFrom) return { text: `Since ${fmtDate(r.validFrom)}`, muted: false };
  return { text: "Permanent", muted: true };
}

// ── Table ──

const dayFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short" });
const dayOf = (d: string) => Number(d.slice(8, 10));
/** "15 déc." (+ " 2027" when not the current year). */
function shortDay(d: string, today: string) {
  const s = dayFmt.format(parseDate(d));
  return d.slice(0, 4) === today.slice(0, 4) ? s : `${s} ${d.slice(0, 4)}`;
}
/** "15–31 déc.", "1 janv. – 31 déc.", "jusqu'au 31 déc.", "dès le 1 avr." */
export function shortPeriod(from: string | undefined, to: string | undefined, today = todayIso()) {
  if (from && to) {
    if (from.slice(0, 7) === to.slice(0, 7)) return `${dayOf(from)}–${dayOf(to)} ${monthFmt.format(parseDate(to))}${to.slice(0, 4) === today.slice(0, 4) ? "" : ` ${to.slice(0, 4)}`}`;
    return `${shortDay(from, today)} – ${shortDay(to, today)}`;
  }
  if (to) return `until ${shortDay(to, today)}`;
  if (from) return `from ${shortDay(from, today)}`;
  return "";
}

export type RuleState = "active" | "inactive" | "expired" | "scheduled";
export function ruleState(r: Pick<PriceRule, "active" | "validFrom" | "validTo">, today = todayIso()): RuleState {
  if (!r.active) return "inactive";
  if (r.validTo && r.validTo < today) return "expired";
  if (r.validFrom && r.validFrom > today) return "scheduled";
  return "active";
}
const STATE_META: Record<RuleState, { tone: Tone; label: string }> = {
  active: { tone: "success", label: "Active" },
  scheduled: { tone: "info", label: "Programm" },
  expired: { tone: "muted", label: "Expires" },
  inactive: { tone: "muted", label: "Disabled" },
};

/** "−5 %", "Coût +20 %", "12,15 €" */
export function methodShort(m: PriceRuleMethod) {
  const n = (x: number) => String(x).replace(".", ",");
  return m.kind === "fixed" ? fmtMoney(m.price) : m.kind === "discount_pct" ? `−${n(m.pct)} %` : `Cost +${n(m.pct)} %`;
}

/** "dès 10 u. · 15–31 déc." or "expirée" — empty for a permanent rule without minimum. */
function conditionsShort(r: PriceRule, today: string) {
  if (r.validTo && r.validTo < today) return `expired on ${shortDay(r.validTo, today)}`;
  const parts: string[] = [];
  if (r.minQty) parts.push(`from ${String(r.minQty).replace(".", ",")} u.`);
  // A start date already passed says nothing once the rule runs: keep it only with an end date or when still to come.
  const p = r.validTo || (r.validFrom && r.validFrom > today) ? shortPeriod(r.validFrom, r.validTo, today) : "";
  if (p) parts.push(p);
  return parts.join(" · ");
}

export function RulesTable({ rules, loading, selectedId, onOpen, onCreate, filtered }: {
  rules: PriceRuleSummary[] | undefined;
  loading: boolean;
  selectedId?: string;
  onOpen: (r: PriceRuleSummary) => void;
  onCreate: () => void;
  filtered: boolean;
}) {
  const toggle = useApiMutation((r: PriceRuleSummary) => api.priceRules.update(r.id, { active: !r.active }), {
    success: (r) => (r.active ? `Rule " ${r.name} » enabled` : `Rule " ${r.name} » disabled`),
    invalidate: [qk.pricing.all],
  });
  const remove = useApiMutation((r: PriceRuleSummary) => api.priceRules.remove(r.id), { success: "Rule deleted", invalidate: [qk.pricing.all] });
  const today = todayIso();
  const dim = (r: PriceRule) => ruleState(r, today) === "inactive" || ruleState(r, today) === "expired";

  const columns: Column<PriceRuleSummary>[] = [
    {
      id: "state", header: "", width: 36, sortValue: (r) => ["active", "scheduled", "expired", "inactive"].indexOf(ruleState(r, today)),
      cell: (r) => {
        const m = STATE_META[ruleState(r, today)];
        return <span className="flex justify-center" title={m.label}><Dot tone={m.tone} /></span>;
      },
    },
    {
      id: "name", header: "Policy", sortValue: (r) => r.name, className: "w-[38%] max-w-0",
      cell: (r) => <span className={cn("block truncate", dim(r) ? "text-muted-foreground" : "font-medium")} title={r.note ? `${r.name}\n${r.note}` : r.name}>{r.name}</span>,
    },
    {
      id: "scope", header: "Scope", sortValue: (r) => `${r.clientScopeLabel} ${r.productScopeLabel}`, className: "w-[34%] max-w-0",
      cell: (r) => <ScopeCell r={r} dim={dim(r)} />,
    },
    {
      id: "method", header: "Method", width: 112, numeric: true, sortValue: (r) => r.methodLabel,
      cell: (r) => <span className={cn("tabular-nums", dim(r) ? "text-muted-foreground" : "text-foreground")} title={r.methodLabel}>{methodShort(r.method)}</span>,
    },
    {
      id: "validity", header: "Conditions", width: 176, sortValue: (r) => r.validTo ?? r.validFrom ?? "",
      cell: (r) => <span className="block truncate text-[12.5px] text-muted-foreground" title={validityLabel(r, today).text}>{conditionsShort(r, today)}</span>,
    },
    { id: "priority", header: "Prio.", width: 56, numeric: true, sortValue: (r) => r.priority, cell: (r) => <span className="text-[12px] text-muted-foreground">{r.priority}</span> },
    {
      id: "actions", header: "", width: 92, align: "right", className: "py-0",
      cell: (r) => (
        <span className="flex items-center justify-end gap-1.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100 group-aria-selected:opacity-100">
          <Switch checked={r.active} label={r.active ? "Disable" : "Enable"} disabled={toggle.isPending} onChange={() => toggle.mutate(r)} />
          <InlineConfirmDelete onConfirm={() => remove.mutate(r)} pending={remove.isPending} label="Delete Rule" />
        </span>
      ),
    },
  ];

  const active = rules?.filter((r) => ruleState(r, today) === "active").length ?? 0;
  return (
    <DataTable
      columns={columns}
      rows={rules}
      loading={loading}
      getRowId={(r) => r.id}
      selectedId={selectedId}
      onRowClick={onOpen}
      defaultSort={{ id: "priority", dir: "desc" }}
      pageKey="rulesPage"
      footer={rules ? `${rules.length} rule${rules.length > 1 ? "s" : ""} · ${active} in force` : undefined}
      empty={
        filtered ? (
          <EmptyState icon={Percent} title="No rules match" description="Edit the search or filter." />
        ) : (
          <EmptyState
            icon={Percent}
            title="No price rules"
            description="A rule applies a discount, margin or fixed price to a group of customers over a group of products."
            action={<Button size="sm" icon={Plus} onClick={onCreate}>New Rule</Button>}
          />
        )
      }
    />
  );
}

/** "● Gastronomie × ● Crustacés" — tag dots for groups, plain text for a client / product / category; counts in the tooltip. */
function ScopeCell({ r, dim }: { r: PriceRuleSummary; dim: boolean }) {
  const clientTags = useTagDefs("client");
  const productTags = useTagDefs("product");
  const cs = r.clientScope, ps = r.productScope;
  const client = cs.kind === "tag" ? <ScopePart dot={clientTags.get(cs.tag)?.color ?? "gray"} label={clientTags.get(cs.tag)?.label ?? cs.tag} />
    : cs.kind === "all" ? <ScopePart muted label="All customers" /> : <ScopePart label={r.clientScopeLabel} />;
  const product = ps.kind === "tag" ? <ScopePart dot={productTags.get(ps.tag)?.color ?? "gray"} label={productTags.get(ps.tag)?.label ?? ps.tag} />
    : ps.kind === "category" ? <ScopePart label={categoryLabel(ps.category)} />
    : ps.kind === "all" ? <ScopePart muted label="all products" /> : <ScopePart label={r.productScopeLabel} />;
  const n = (c: number, u: string) => `${c} ${u}${c > 1 ? "s" : ""}`;
  return (
    <span
      className={cn("flex min-w-0 items-center gap-1.5 text-[12.5px]", dim ? "text-muted-foreground" : "text-secondary-foreground")}
      title={`${r.clientScopeLabel} × ${r.productScopeLabel}\n${n(r.affectedClients, "client")} · ${n(r.affectedProducts, "produit")}`}
    >
      <span className="flex min-w-0 max-w-[55%] shrink-0">{client}</span>
      <span className="shrink-0 text-muted-foreground/70">×</span>
      {product}
    </span>
  );
}

function ScopePart({ label, dot, muted }: { label: string; dot?: TagColor; muted?: boolean }) {
  return (
    <span className={cn("flex min-w-0 shrink items-center gap-1.5", muted && "text-muted-foreground")}>
      {dot ? <TagDot color={dot} /> : null}
      <span className="truncate">{label}</span>
    </span>
  );
}

// ── Editor panel ──

type ClientKind = PriceRuleClientScope["kind"];
type ProductKind = PriceRuleProductScope["kind"];
type MethodKind = PriceRuleMethod["kind"];

interface Draft {
  name: string;
  active: boolean;
  priority: string;
  clientKind: ClientKind;
  clientId: string;
  clientTag: string;
  productKind: ProductKind;
  productId: string;
  productTag: string;
  category: string;
  methodKind: MethodKind;
  amount: string;
  minQty: string;
  validFrom: string;
  validTo: string;
  note: string;
}

const num = (s: string) => {
  const n = Number(s.replace(/\s/g, "").replace(",", "."));
  return s.trim() === "" || !Number.isFinite(n) ? NaN : n;
};
const show = (n?: number) => (n == null ? "" : String(n).replace(".", ","));

/** Scope prefill for a new rule (from a matrix cell). */
export interface RulePrefill { clientScope?: PriceRuleClientScope; productScope?: PriceRuleProductScope }

function toDraft(r?: PriceRule, pre?: RulePrefill): Draft {
  if (!r && pre) {
    const d = toDraft();
    const c = pre.clientScope, p = pre.productScope;
    if (c) Object.assign(d, { clientKind: c.kind, clientId: c.kind === "client" ? c.clientId : "", clientTag: c.kind === "tag" ? c.tag : "" });
    if (p) Object.assign(d, {
      productKind: p.kind, productId: p.kind === "product" ? p.productId : "", productTag: p.kind === "tag" ? p.tag : "",
      category: p.kind === "category" ? p.category : "",
    });
    return d;
  }
  return {
    name: r?.name ?? "",
    active: r?.active ?? true,
    priority: show(r?.priority ?? 0),
    clientKind: r?.clientScope.kind ?? "tag",
    clientId: r?.clientScope.kind === "client" ? r.clientScope.clientId : "",
    clientTag: r?.clientScope.kind === "tag" ? r.clientScope.tag : "",
    productKind: r?.productScope.kind ?? "category",
    productId: r?.productScope.kind === "product" ? r.productScope.productId : "",
    productTag: r?.productScope.kind === "tag" ? r.productScope.tag : "",
    category: r?.productScope.kind === "category" ? r.productScope.category : "",
    methodKind: r?.method.kind ?? "discount_pct",
    amount: r ? show(r.method.kind === "fixed" ? r.method.price : r.method.pct) : "",
    minQty: show(r?.minQty),
    validFrom: r?.validFrom ?? "",
    validTo: r?.validTo ?? "",
    note: r?.note ?? "",
  };
}

function scopes(d: Draft): { clientScope?: PriceRuleClientScope; productScope?: PriceRuleProductScope; method?: PriceRuleMethod } {
  const clientScope: PriceRuleClientScope | undefined =
    d.clientKind === "all" ? { kind: "all" } : d.clientKind === "client" ? (d.clientId ? { kind: "client", clientId: d.clientId } : undefined)
    : d.clientTag ? { kind: "tag", tag: d.clientTag } : undefined;
  const productScope: PriceRuleProductScope | undefined =
    d.productKind === "all" ? { kind: "all" }
    : d.productKind === "product" ? (d.productId ? { kind: "product", productId: d.productId } : undefined)
    : d.productKind === "tag" ? (d.productTag ? { kind: "tag", tag: d.productTag } : undefined)
    : d.category ? { kind: "category", category: d.category as ProductCategory } : undefined;
  const a = num(d.amount);
  const method: PriceRuleMethod | undefined = Number.isNaN(a)
    ? undefined
    : d.methodKind === "fixed" ? (a > 0 ? { kind: "fixed", price: a } : undefined) : { kind: d.methodKind, pct: a };
  return { clientScope, productScope, method };
}

/** Same formula as the API resolver (preview only). */
function previewPrice(m: PriceRuleMethod, p: Pick<ProductSummary, "price" | "cost">) {
  const v = m.kind === "fixed" ? m.price : m.kind === "discount_pct" ? p.price * (1 - m.pct / 100) : p.cost * (1 + m.pct / 100);
  return Math.round(v * 100) / 100;
}

const METHOD_HINT: Record<MethodKind, string> = {
  fixed: "Price HT by unit, regardless of the catalogue",
  discount_pct: "% discount on the catalogue price",
  markup_pct: "Margin in % added at purchase cost",
};

export function RulePanel({ rule, prefill, onClose, onSaved }: {
  rule?: PriceRule; prefill?: RulePrefill; onClose: () => void; onSaved?: (r: PriceRule) => void;
}) {
  const [d, setD] = useState<Draft>(() => toDraft(rule, prefill));
  useEffect(() => setD(toDraft(rule, prefill)), [rule?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = <K extends keyof Draft>(k: K) => (v: Draft[K]) => setD((x) => ({ ...x, [k]: v }));

  const clientOptions = useClientOptions();
  const productOptions = useProductOptions();
  const clientTags = useTagOptions("client");
  const productTags = useTagOptions("product");
  const { data: tagDefs } = useTags();
  const { data: products } = useProducts();

  const s = scopes(d);
  const prio = num(d.priority);
  const minQty = num(d.minQty);
  const datesOk = !d.validFrom || !d.validTo || d.validFrom <= d.validTo;
  const valid = !!(d.name.trim() && s.clientScope && s.productScope && s.method && datesOk && (d.minQty.trim() === "" || minQty > 0));

  // Suggest a name from the choices until the user types one.
  const [nameTouched, setNameTouched] = useState(!!rule);
  const autoName = useMemo(() => {
    const tagLabel = (scope: "client" | "product", id: string) => tagDefs?.find((t) => t.scope === scope && t.id === id)?.label ?? id;
    const c = d.clientKind === "all" ? "All" : d.clientKind === "client" ? clientOptions.find((o) => o.value === d.clientId)?.label : d.clientTag && tagLabel("client", d.clientTag);
    const p = d.productKind === "all" ? "tout" : d.productKind === "product" ? productOptions.find((o) => o.value === d.productId)?.label
      : d.productKind === "tag" ? d.productTag && tagLabel("product", d.productTag) : d.category && categoryLabel(d.category as ProductCategory).toLowerCase();
    const a = num(d.amount);
    const m = Number.isNaN(a) ? "" : d.methodKind === "fixed" ? fmtMoney(a) : d.methodKind === "discount_pct" ? `-${show(a)} %` : `cost +${show(a)} %`;
    if (!c || !p || !m) return "";
    return `${c} : ${m} sur ${p}`;
  }, [d, clientOptions, productOptions, tagDefs]);
  useEffect(() => { if (!nameTouched) setD((x) => ({ ...x, name: autoName })); }, [autoName, nameTouched]);

  const sample = useMemo(() => {
    if (!products || !s.productScope) return { rows: [] as ProductSummary[], total: 0 };
    const ps = s.productScope;
    const match = products.filter((p) =>
      p.active && (ps.kind === "all" || (ps.kind === "product" && p.id === ps.productId) || (ps.kind === "tag" && (p.tags ?? []).includes(ps.tag)) || (ps.kind === "category" && p.category === ps.category)));
    // Spread the sample over the price range: cheapest, middle, most expensive.
    const sorted = match.slice().sort((a, b) => a.price - b.price);
    if (sorted.length <= 3) return { rows: sorted, total: sorted.length };
    return { rows: [sorted[0], sorted[Math.floor(sorted.length / 2)], sorted[sorted.length - 1]], total: sorted.length };
  }, [products, s.productScope]);
  const sampleRows = sample.rows;
  const sampleTotal = sample.total;

  const body = (): PriceRuleInput => ({
    name: d.name.trim(),
    active: d.active,
    priority: Number.isNaN(prio) ? 0 : Math.round(prio),
    clientScope: s.clientScope!,
    productScope: s.productScope!,
    method: s.method!,
    ...(d.minQty.trim() ? { minQty: minQty } : {}),
    ...(d.validFrom ? { validFrom: d.validFrom } : {}),
    ...(d.validTo ? { validTo: d.validTo } : {}),
    ...(d.note.trim() ? { note: d.note.trim() } : {}),
  });
  const save = useApiMutation(
    (b: PriceRuleInput) => (rule ? api.priceRules.update(rule.id, b) : api.priceRules.create(b)),
    { success: (r) => (rule ? `Rule " ${r.name} » recorded` : `Rule " ${r.name} » created`), invalidate: [qk.pricing.all], onSuccess: (r) => onSaved?.(r) },
  );
  const remove = useApiMutation(() => api.priceRules.remove(rule!.id), { success: "Rule deleted", invalidate: [qk.pricing.all], onSuccess: onClose });
  const submit = (e: React.FormEvent) => { e.preventDefault(); if (valid) save.mutate(body()); };

  return (
    <SidePanel
      id="price-rule"
      width={520}
      title={rule ? rule.name : "New price rule"}
      subtitle={rule ? `Created on ${fmtDate(rule.createdAt)}` : "Discount, margin or fixed price for a group of customers × a group of products"}
      onClose={onClose}
      footer={
        <>
          {rule ? <span className="mr-auto"><InlineConfirmDelete text onConfirm={() => remove.mutate()} pending={remove.isPending} /></span> : null}
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="price-rule-form" loading={save.isPending} disabled={!valid}>{rule ? "Save" : "Create Rule"}</Button>
        </>
      }
    >
      <form id="price-rule-form" onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex items-end gap-3">
          <Field label="Name" className="flex-1">
            <Input value={d.name} onChange={(e) => { setNameTouched(true); set("name")(e.target.value); }} placeholder="Gastro: -8% on crustaceans" autoFocus={!rule} />
          </Field>
          <label className="flex h-8 items-center gap-2 text-[12.5px] text-secondary-foreground">
            <Switch checked={d.active} onChange={set("active")} label="Active" /> Active
          </label>
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className={cn(SECTION_LABEL, "mb-1.5")}>Customers</legend>
          <Segmented<ClientKind> value={d.clientKind} onChange={set("clientKind")} options={[{ id: "all", label: "All" }, { id: "tag", label: "Group" }, { id: "client", label: "A customer" }]} className="self-start" />
          {d.clientKind === "client" ? <Combobox value={d.clientId} onChange={set("clientId")} options={clientOptions} placeholder="Look for a client..." /> : null}
          {d.clientKind === "tag" ? (
            clientTags.length ? <Combobox value={d.clientTag} onChange={set("clientTag")} options={clientTags} placeholder="Choose a group of clients..." />
              : <p className="text-[12.5px] text-muted-foreground">No customer group. Create one in Groups.</p>
          ) : null}
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className={cn(SECTION_LABEL, "mb-1.5")}>Products</legend>
          <Segmented<ProductKind>
            value={d.productKind}
            onChange={set("productKind")}
            options={[{ id: "all", label: "All" }, { id: "category", label: "Category" }, { id: "tag", label: "Group" }, { id: "product", label: "A product" }]}
            className="self-start"
          />
          {d.productKind === "product" ? <Combobox value={d.productId} onChange={set("productId")} options={productOptions} placeholder="Search for a product..." /> : null}
          {d.productKind === "tag" ? (
            productTags.length ? <Combobox value={d.productTag} onChange={set("productTag")} options={productTags} placeholder="Choose a product group..." />
              : <p className="text-[12.5px] text-muted-foreground">No product groups. Create one in Groups.</p>
          ) : null}
          {d.productKind === "category" ? <Select value={d.category} onChange={set("category")} options={categoryOptions()} placeholder="Choose a category..." className="w-full" /> : null}
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className={cn(SECTION_LABEL, "mb-1.5")}>Price</legend>
          <Segmented<MethodKind>
            value={d.methodKind}
            onChange={set("methodKind")}
            options={[{ id: "discount_pct", label: "Discount % catalogue" }, { id: "markup_pct", label: "Margin % on cost" }, { id: "fixed", label: "Fixed price" }]}
            className="self-start"
          />
          <div className="flex items-center gap-2">
            <div className="relative w-[120px]">
              <Input inputMode="decimal" value={d.amount} onChange={(e) => set("amount")(e.target.value)} placeholder={d.methodKind === "fixed" ? "24,50" : "8"} className="num pr-8 text-right" />
              <span className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-[12.5px] text-muted-foreground">{d.methodKind === "fixed" ? "€" : "%"}</span>
            </div>
            <span className="text-[12px] text-muted-foreground">{METHOD_HINT[d.methodKind]}</span>
          </div>
          <Preview rows={sampleRows} total={sampleTotal} method={s.method} hasScope={!!s.productScope} />
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className={cn(SECTION_LABEL, "mb-1.5")}>Conditions</legend>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Valid for"><DatePicker value={d.validFrom} onChange={set("validFrom")} max={d.validTo || undefined} clearable placeholder="From now on" presets={false} /></Field>
            <Field label="To" hint={!datesOk ? "The end precedes the beginning" : undefined}>
              <DatePicker value={d.validTo} onChange={set("validTo")} min={d.validFrom || undefined} clearable placeholder="Endless" presets={[{ label: "In 7 days", days: 7 }, { label: "In 30 days", days: 30 }, { label: "90 days", days: 90 }]} />
            </Field>
            <Field label="Minimum quantity" hint="By command line">
              <Input inputMode="decimal" value={d.minQty} onChange={(e) => set("minQty")(e.target.value)} placeholder="None" className="num" />
            </Field>
            <Field label="Priority" hint="At equal specificity, the highest wins">
              <Input inputMode="numeric" value={d.priority} onChange={(e) => set("priority")(e.target.value)} className="num" />
            </Field>
          </div>
          <Field label="Note"><Textarea rows={2} value={d.note} onChange={(e) => set("note")(e.target.value)} placeholder="Trade agreement, context..." /></Field>
        </fieldset>

        <p className="text-[11.5px] leading-4 text-muted-foreground">
          Order of application: negotiated price of the customer, then the most precise rule (client &gt; group of clients &gt; All; product &gt; group or category &gt; then priority, then the most recent. Otherwise, catalogue price.
        </p>
      </form>
    </SidePanel>
  );
}

function Preview({ rows, total, method, hasScope }: { rows: ProductSummary[]; total: number; method?: PriceRuleMethod; hasScope: boolean }) {
  return (
    <div className="rounded-[4px] border border-border">
      <div className="flex h-7 items-center justify-between border-b border-border bg-muted/40 px-2.5">
        <span className={SECTION_LABEL}>Overview</span>
        {total > 3 ? <span className="text-[11.5px] text-muted-foreground">3 examples on {total} products</span> : null}
      </div>
      {!hasScope || !rows.length ? (
        <div className="px-2.5 py-3 text-[12.5px] text-muted-foreground">{hasScope ? "No active products in this perimeter." : "Choose the products to see the prices obtained."}</div>
      ) : (
        <table className="w-full table-fixed text-[12.5px]">
          <colgroup><col /><col style={{ width: 84 }} /><col style={{ width: 100 }} /><col style={{ width: 70 }} /></colgroup>
          <thead>
            <tr className="text-[11px] text-muted-foreground">
              <th className="px-2.5 py-1 text-left font-medium">Product</th>
              <th className="px-2 py-1 text-right font-medium">Catalogue</th>
              <th className="px-2 py-1 text-right font-medium">New price</th>
              <th className="px-2.5 py-1 text-right font-medium">Margin</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const price = method ? previewPrice(method, p) : undefined;
              const margin = price ? (price - p.cost) / price : undefined;
              return (
                <tr key={p.id} className="border-t border-border">
                  <td className="max-w-0 truncate px-2.5 py-1.5" title={p.name}>{p.name}</td>
                  <td className="px-2 py-1.5 text-right"><Money value={p.price} className="text-muted-foreground" /></td>
                  <td className="px-2 py-1.5 text-right font-medium">{price != null ? <Money value={price} /> : <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-2.5 py-1.5 text-right">{margin != null ? <MarginCell value={margin} /> : <span className="text-muted-foreground">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

