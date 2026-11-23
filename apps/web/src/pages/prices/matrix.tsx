/**
 * Matrice tab (default): products × client groups (or up to 8 picked clients). Each cell = the resolved price for that column
 * (GET /prices/grid?clientTag=|clientId=, one query per column, in parallel and cached). Click a cell → resolve detail + actions
 * (rule for that group × product/category, negotiated price for a client). One column = the old single-client "Grille" view,
 * with écart / marge / source spelled out.
 */
import { Fragment, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { Calculator, Grid3x3, Pencil, Plus } from "lucide-react";
import type { ClientSummary, PriceGridRow, PriceRule, PriceRuleClientScope, PriceRuleSummary, ProductCategory, ProductSummary } from "@kit/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fmtMoney, fmtPercent, UNIT_LABEL } from "@/lib/format";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { qk, useApiMutation, useClients, usePriceRules, useProducts, useResolvedPrice, useTagMembers, useTags } from "@/lib/queries";
import { useUrlPatch, useUrlState } from "@/lib/url-state";
import {
  Button, Dot, EmptyState, Mono, Money, Pagination, SECTION_LABEL, Segmented, Select, SidePanel, Skeleton, TagChip, TagDot, usePagination,
  type TagColor,
} from "@/ui";
import { NegotiatedPriceEditor } from "./negotiated-editor";
import { useNegotiatedPrices } from "./negotiated";
import { Combobox, DeltaCell, LOW_MARGIN, MarginCell, MultiCombobox, SOURCE_META, SourceLabel, useClientOptions, useTagOptions } from "./pickers";
import { CandidatesList, Metric, ResolvedHeadline, ResolvedSkeleton } from "./resolved";
import { methodShort, RulePanel, ruleState, type RulePrefill } from "./rules";

const MAX_CLIENTS = 8;
const priceFmt = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

type Mode = "groups" | "clients";
interface Col { key: string; kind: "tag" | "client"; id: string; label: string; color?: TagColor; hint: string }

const scopeOf = (c: Col): PriceRuleClientScope => (c.kind === "tag" ? { kind: "tag", tag: c.id } : { kind: "client", clientId: c.id });
const sameScope = (a: PriceRuleClientScope, b: PriceRuleClientScope) =>
  a.kind === b.kind && (a.kind === "all" || (a.kind === "tag" ? a.tag === (b as { tag: string }).tag : a.clientId === (b as { clientId: string }).clientId));

/**
 * Matrice filters, rendered in the page's FilterBar (next to the search): column mode (groups / picked clients),
 * product group, category, and the colour legend on the right. Same URL state as MatrixTab.
 */
export function MatrixFilters() {
  const [mode] = useUrlState("mmode", "groups");
  const [mclients] = useUrlState("mclients");
  const [productTag, setProductTag] = useUrlState("mptag");
  const [category, setCategory] = useUrlState("mcat");
  const patch = useUrlPatch();
  const clientOptions = useClientOptions();
  const productTags = useTagOptions("product");
  const picked = useMemo(() => (mclients ? mclients.split(",").filter(Boolean) : []), [mclients]);
  return (
    <>
      <Segmented<Mode>
        value={mode as Mode}
        onChange={(v) => patch({ mmode: v === "groups" ? "" : v, cell: "" })}
        options={[{ id: "groups", label: "Groupes de clients" }, { id: "clients", label: "Clients" }]}
      />
      {mode === "clients" ? (
        <MultiCombobox
          value={picked}
          onChange={(v) => patch({ mclients: v.join(","), cell: "" })}
          options={clientOptions}
          placeholder="Choisir des clients…"
          unit={["client", "clients"]}
          max={MAX_CLIENTS}
          width={220}
        />
      ) : null}
      <span className="mx-1 h-4 w-px shrink-0 bg-border" />
      <Combobox value={productTag} onChange={setProductTag} options={productTags} placeholder="Tous les groupes de produits" size="sm" width={210} clearable />
      <Select size="sm" value={category} onChange={setCategory} placeholder="Toutes les catégories" options={categoryOptions()} />
      <span className="ml-auto flex items-center gap-3 whitespace-nowrap pl-3 text-[11.5px] text-muted-foreground">
        <span className="flex items-center gap-1.5"><Dot tone={SOURCE_META.client_price.tone} />Négocié</span>
        <span className="flex items-center gap-1.5"><Dot tone={SOURCE_META.rule.tone} />Règle</span>
        <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-muted-foreground/25" />Catalogue</span>
        <span className="text-warning">marge &lt; 15 %</span>
      </span>
    </>
  );
}

export function MatrixTab({ q }: { q: string }) {
  const [mode] = useUrlState("mmode", "groups");
  const [mclients] = useUrlState("mclients");
  const [productTag] = useUrlState("mptag");
  const [category] = useUrlState("mcat");
  const [cell] = useUrlState("cell", "", { keepPage: true });
  const patch = useUrlPatch();
  const [ruleEdit, setRuleEdit] = useState<{ rule?: PriceRule; prefill?: RulePrefill } | null>(null);

  const { data: tags } = useTags("client");
  const { data: clients } = useClients();
  const { data: products } = useProducts();
  const clientOptions = useClientOptions();
  const { rows: negotiated, loading: negLoading } = useNegotiatedPrices();
  const picked = useMemo(() => (mclients ? mclients.split(",").filter(Boolean) : []), [mclients]);

  // Clients mode without a pick: start with the clients that have the most negotiated prices.
  useEffect(() => {
    if (mode !== "clients" || picked.length || !clientOptions.length || negLoading) return;
    const n = new Map<string, number>();
    for (const r of negotiated ?? []) n.set(r.clientId, (n.get(r.clientId) ?? 0) + 1);
    const top = [...n.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([id]) => id);
    patch({ mclients: (top.length ? top : clientOptions.slice(0, 5).map((o) => o.value)).join(",") });
  }, [mode, picked.length, clientOptions, negotiated, negLoading, patch]);

  const cols: Col[] = useMemo(() => {
    if (mode === "groups") {
      return (tags ?? []).map((t) => ({ key: `t:${t.id}`, kind: "tag" as const, id: t.id, label: t.label, color: t.color, hint: `${t.label} · ${t.count} client${t.count > 1 ? "s" : ""}` }));
    }
    const byId = new Map((clients ?? []).map((c) => [c.id, c] as const));
    return picked.map((id) => {
      const c = byId.get(id);
      return { key: `c:${id}`, kind: "client" as const, id, label: c?.name ?? id, hint: c ? `${c.name} · ${c.code}` : id };
    });
  }, [mode, tags, clients, picked]);

  const grids = useQueries({
    queries: cols.map((c) => {
      const p = c.kind === "tag" ? { clientTag: c.id } : { clientId: c.id };
      return { queryKey: qk.pricing.grid(p), queryFn: () => api.prices.grid(p), staleTime: 30_000 };
    }),
  });
  const stamp = grids.map((g) => g.dataUpdatedAt).join(",");
  const byCol = useMemo(
    () => new Map(cols.map((c, i) => [c.key, grids[i]?.data ? new Map(grids[i].data!.map((r) => [r.productId, r] as const)) : undefined] as const)),
    [cols, stamp], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const rows = useMemo(() => {
    if (!products) return undefined;
    const n = norm(q.trim());
    return products
      .filter((p) => p.active && (!category || p.category === category) && (!productTag || (p.tags ?? []).includes(productTag))
        && (!n || norm(`${p.name} ${p.sku} ${(p.aliases ?? []).join(" ")}`).includes(n)))
      .sort((a, b) => categoryIds().indexOf(a.category) - categoryIds().indexOf(b.category) || a.name.localeCompare(b.name, "fr"));
  }, [products, q, category, productTag]);
  const catCount = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of rows ?? []) m.set(p.category, (m.get(p.category) ?? 0) + 1);
    return m;
  }, [rows]);
  const pg = usePagination(rows, { key: "mPage" });

  const [selProduct, selCol] = cell ? cell.split("~") : ["", ""];
  const selectedProduct = products?.find((p) => p.id === selProduct);
  const selectedCol = cols.find((c) => c.key === selCol);
  const openCell = (p: ProductSummary, c: Col) => { setRuleEdit(null); patch({ cell: cell === `${p.id}~${c.key}` ? "" : `${p.id}~${c.key}` }, { keepPage: true }); };
  const single = cols.length === 1;
  const span = 4 + (single ? 4 : cols.length);

  return (
    <div className="flex min-h-full flex-col">

      {!cols.length && mode === "clients" && !picked.length && clientOptions.length && !negLoading ? (
        <EmptyState icon={Grid3x3} title="Choisissez des clients" description={`Jusqu'à ${MAX_CLIENTS} clients côte à côte.`} />
      ) : rows && !rows.length ? (
        <EmptyState icon={Grid3x3} title="Aucun produit" description="Aucun produit actif ne correspond aux filtres." />
      ) : (
        <div ref={pg.anchorRef} className="flex-1">
          <table className="min-w-full border-separate border-spacing-0 text-[13px]">
            <colgroup>
              <col style={{ minWidth: 260 }} />
              <col style={{ width: 56 }} />
              <col style={{ width: 76 }} />
              <col style={{ width: 84 }} />
              {single ? (
                <><col style={{ width: 112 }} /><col style={{ width: 76 }} /><col style={{ width: 80 }} /><col style={{ width: 240 }} /></>
              ) : cols.map((c) => <col key={c.key} style={{ width: 112 }} />)}
            </colgroup>
            <thead className="sticky top-0 z-20 bg-background">
              <tr>
                <Th className="sticky left-0 z-10 bg-background pl-5 text-left">Produit</Th>
                <Th>Unité</Th>
                <Th className="text-right">Coût</Th>
                <Th className="text-right">Catalogue</Th>
                {single ? (
                  <>
                    <Th className="border-l text-right"><ColHead c={cols[0]} /></Th>
                    <Th className="text-right">Écart</Th>
                    <Th className="text-right">Marge</Th>
                    <Th className="pr-5">Source</Th>
                  </>
                ) : cols.map((c, i) => (
                  <Th key={c.key} className={cn("max-w-[112px] text-right", i === 0 && "border-l", i === cols.length - 1 && "pr-5")}><ColHead c={c} /></Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!rows
                ? Array.from({ length: 12 }).map((_, i) => (
                    <tr key={i} className="h-[34px]">
                      <td colSpan={span} className="border-b border-border px-5"><Skeleton className={cn("h-3", i % 2 ? "w-48" : "w-64")} /></td>
                    </tr>
                  ))
                : pg.rows.map((p, i) => {
                    const head = i === 0 || pg.rows[i - 1].category !== p.category;
                    return (
                      <Fragment key={p.id}>
                        {head ? (
                          <tr>
                            <td colSpan={span} className="h-7 border-b border-border bg-muted/40 px-5 align-middle">
                              <span className={cn(SECTION_LABEL, "sticky left-5")}>
                                {categoryLabel(p.category)} <span className="ml-1 font-normal tabular-nums tracking-normal">{catCount.get(p.category)}</span>
                              </span>
                            </td>
                          </tr>
                        ) : null}
                        <MatrixRow
                          p={p}
                          cols={cols}
                          byCol={byCol}
                          single={single}
                          selectedCol={selProduct === p.id ? selCol : undefined}
                          onOpen={openCell}
                        />
                      </Fragment>
                    );
                  })}
            </tbody>
          </table>
          {pg.pageCount > 1 ? (
            <Pagination pagination={pg} sticky>{footerText(rows, cols)}</Pagination>
          ) : rows ? (
            <div className="px-5 py-2.5 text-[12px] text-muted-foreground">{footerText(rows, cols)}</div>
          ) : null}
        </div>
      )}

      {ruleEdit ? (
        <RulePanel
          key={ruleEdit.rule?.id ?? `new-${JSON.stringify(ruleEdit.prefill)}`}
          rule={ruleEdit.rule}
          prefill={ruleEdit.prefill}
          onClose={() => setRuleEdit(null)}
          onSaved={() => setRuleEdit(null)}
        />
      ) : selectedProduct && selectedCol ? (
        <CellPanel
          key={cell}
          product={selectedProduct}
          col={selectedCol}
          row={byCol.get(selectedCol.key)?.get(selectedProduct.id)}
          onClose={() => patch({ cell: "" }, { keepPage: true })}
          onEditRule={(rule) => setRuleEdit({ rule })}
          onNewRule={(prefill) => setRuleEdit({ prefill })}
        />
      ) : null}
    </div>
  );
}

function footerText(rows: ProductSummary[] | undefined, cols: Col[]) {
  if (!rows) return null;
  return `${rows.length} produit${rows.length > 1 ? "s" : ""} × ${cols.length} ${cols[0]?.kind === "client" ? "client" : "groupe"}${cols.length > 1 ? "s" : ""} · prix HT du jour pour 1 unité`;
}

function Th({ className, children }: { className?: string; children?: React.ReactNode }) {
  return <th className={cn("h-10 whitespace-nowrap border-b border-border px-3 text-left text-[12px] font-medium text-muted-foreground", className)}>{children}</th>;
}

function ColHead({ c }: { c: Col }) {
  return (
    <span className="flex max-w-full items-start justify-end gap-1.5 whitespace-normal text-right leading-[15px]" title={c.hint}>
      {c.kind === "tag" ? <TagDot color={c.color} className="mt-[5px]" /> : null}
      <span className="line-clamp-2">{c.label}</span>
    </span>
  );
}

/** Row background for the sticky first cell: opaque, follows the row hover. */
const STICKY_CELL = "sticky left-0 z-[1] bg-background group-hover:[background-image:linear-gradient(hsl(var(--muted)/0.6),hsl(var(--muted)/0.6))]";

function MatrixRow({ p, cols, byCol, single, selectedCol, onOpen }: {
  p: ProductSummary;
  cols: Col[];
  byCol: Map<string, Map<string, PriceGridRow> | undefined>;
  single: boolean;
  selectedCol?: string;
  onOpen: (p: ProductSummary, c: Col) => void;
}) {
  const td = "h-[34px] whitespace-nowrap border-b border-border px-3 align-middle";
  const one = single ? byCol.get(cols[0].key)?.get(p.id) : undefined;
  return (
    <tr className="group transition-colors hover:bg-muted/60">
      <td className={cn(td, STICKY_CELL, "max-w-[340px] pl-5")}>
        <span className="flex min-w-0 items-center gap-2">
          <Link to={`/products/${p.id}`} className="truncate font-medium hover:underline" title={p.name}>{p.name}</Link>
          <Mono className="shrink-0 text-[11px] text-muted-foreground">{p.sku}</Mono>
        </span>
      </td>
      <td className={cn(td, "text-muted-foreground")}>{UNIT_LABEL[p.unit] ?? p.unit}</td>
      <td className={cn(td, "num text-right text-muted-foreground")}>{priceFmt.format(p.cost)}</td>
      <td className={cn(td, "num text-right text-muted-foreground")}>{priceFmt.format(p.price)}</td>
      {single ? (
        <>
          <td className={cn(td, "border-l p-0")}>
            <PriceCell r={one} loading={!byCol.get(cols[0].key)} selected={selectedCol === cols[0].key} onClick={() => onOpen(p, cols[0])} />
          </td>
          <td className={cn(td, "text-right")}>{one ? <DeltaCell price={one.price} list={one.listPrice} /> : null}</td>
          <td className={cn(td, "text-right")}>{one ? <MarginCell value={one.marginPct} /> : null}</td>
          <td className={cn(td, "max-w-[240px] pr-5")}>{one ? <RuleSource r={one} /> : null}</td>
        </>
      ) : cols.map((c, i) => (
        <td key={c.key} className={cn(td, "p-0", i === 0 && "border-l", i === cols.length - 1 && "pr-2")}>
          <PriceCell r={byCol.get(c.key)?.get(p.id)} loading={!byCol.get(c.key)} selected={selectedCol === c.key} onClick={() => onOpen(p, c)} />
        </td>
      ))}
    </tr>
  );
}

function RuleSource({ r }: { r: PriceGridRow }) {
  const { data: rules } = usePriceRules();
  const name = r.ruleId ? rules?.find((x) => x.id === r.ruleId)?.name : undefined;
  return <SourceLabel source={r.source} ruleName={name} className="max-w-full" />;
}

/** "● 17,48" — dot = source, tone = margin; delta vs list shown on hover. */
function PriceCell({ r, loading, selected, onClick }: { r?: PriceGridRow; loading: boolean; selected: boolean; onClick: () => void }) {
  if (!r) {
    return loading ? <span className="flex justify-end px-3"><Skeleton className="h-3 w-12" /></span> : <span className="block px-3 text-right text-muted-foreground">—</span>;
  }
  const d = r.listPrice ? (r.price - r.listPrice) / r.listPrice : 0;
  const tone = r.marginPct < 0 ? "text-destructive" : r.marginPct < LOW_MARGIN ? "text-warning" : r.source === "list" ? "text-muted-foreground/80" : "text-foreground";
  const src = r.source === "list" ? "Catalogue" : SOURCE_META[r.source].label;
  const deltaTxt = Math.abs(d) >= 0.0005 ? `${d < 0 ? "−" : "+"}${fmtPercent(Math.abs(d))}` : "";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      title={`${fmtMoney(r.price)} · ${src}${deltaTxt ? ` · ${deltaTxt} vs catalogue` : ""} · marge ${fmtPercent(r.marginPct)}`}
      className={cn(
        "group/cell relative flex h-[33px] w-full items-center justify-end gap-1.5 px-3 outline-none transition-colors",
        "hover:bg-muted focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/70",
        selected && "bg-row-selected shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.5)] hover:bg-row-selected",
      )}
    >
      {deltaTxt ? (
        <span className="pointer-events-none absolute left-2 text-[10.5px] tabular-nums text-muted-foreground opacity-0 transition-opacity group-hover/cell:opacity-100">
          {deltaTxt}
        </span>
      ) : null}
      {r.source === "list" ? <span className="size-1.5 shrink-0 rounded-full bg-muted-foreground/25" /> : <Dot tone={SOURCE_META[r.source].tone} />}
      <span className={cn("num tabular-nums", tone, r.source !== "list" && "font-medium")}>{priceFmt.format(r.price)}</span>
    </button>
  );
}

// ── Cell panel ──

function CellPanel({ product, col, row, onClose, onEditRule, onNewRule }: {
  product: ProductSummary;
  col: Col;
  row?: PriceGridRow;
  onClose: () => void;
  onEditRule: (r: PriceRule) => void;
  onNewRule: (p: RulePrefill) => void;
}) {
  const { data: members } = useTagMembers("client", col.kind === "tag" ? col.id : undefined);
  const memberOptions = useMemo(() => ((members ?? []) as ClientSummary[]).map((c) => ({ value: c.id, label: c.name, sub: c.code })), [members]);
  const [member, setMember] = useState("");
  useEffect(() => { if (col.kind === "tag" && !member && memberOptions.length) setMember(memberOptions[0].value); }, [col.kind, member, memberOptions]);
  const who = col.kind === "client" ? col.id : member;
  const { data: r, isLoading } = useResolvedPrice({ clientId: who, productId: product.id, qty: 1 });
  const resolved = r && r.clientId === who && r.productId === product.id ? r : undefined;

  const { data: rules } = usePriceRules();
  const scope = scopeOf(col);
  const related = useMemo(
    () => (rules ?? []).filter((x) => sameScope(x.clientScope, scope) && (
      x.productScope.kind === "all"
      || (x.productScope.kind === "product" && x.productScope.productId === product.id)
      || (x.productScope.kind === "category" && x.productScope.category === product.category)
      || (x.productScope.kind === "tag" && (product.tags ?? []).includes(x.productScope.tag)))),
    [rules, scope.kind, col.id, product], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const appliedRuleId = col.kind === "tag" ? row?.ruleId : resolved?.ruleId;

  return (
    <SidePanel
      id="price-cell"
      width={500}
      title={product.name}
      subtitle={<><Mono>{product.sku}</Mono> · {categoryLabel(product.category)} · {UNIT_LABEL[product.unit] ?? product.unit}</>}
      onClose={onClose}
      actions={who ? (
        <Link to={`/prices?tab=sim&sclient=${who}&sproduct=${product.id}`}>
          <Button size="sm" variant="ghost" icon={Calculator}>Simuler</Button>
        </Link>
      ) : null}
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
          Prix pour
          {col.kind === "tag" ? <TagChip tag={{ id: col.id, label: col.label, color: col.color }} title={col.hint} />
            : <Link to={`/clients/${col.id}`} className="font-medium text-foreground hover:underline">{col.label}</Link>}
        </div>

        {col.kind === "tag" ? (
          row ? <GridHeadline row={row} ruleName={rules?.find((x) => x.id === row.ruleId)?.name} /> : <ResolvedSkeleton />
        ) : resolved ? <ResolvedHeadline r={resolved} size="md" /> : <ResolvedSkeleton />}

        <section className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className={SECTION_LABEL}>Prix candidats</span>
            {col.kind === "tag" && memberOptions.length ? (
              <span className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                calcul pour
                <Combobox value={member} onChange={setMember} options={memberOptions} size="sm" width={190} />
              </span>
            ) : null}
          </div>
          {col.kind === "tag" && members && !memberOptions.length ? (
            <p className="text-[12.5px] text-muted-foreground">Ce groupe n'a aucun client.</p>
          ) : resolved ? (
            <>
              {col.kind === "tag" && row && Math.abs(resolved.price - row.price) > 0.004 ? (
                <p className="text-[12px] text-muted-foreground">Ce client paie {fmtMoney(resolved.price)} : {resolved.source === "client_price" ? "il a un prix négocié" : "une règle plus précise s'applique"}.</p>
              ) : null}
              <CandidatesList r={resolved} />
            </>
          ) : isLoading || who ? <ResolvedSkeleton /> : null}
        </section>

        <section className="flex flex-col gap-2 border-t border-border pt-4">
          <span className={SECTION_LABEL}>Règles {col.kind === "tag" ? "du groupe" : "du client"} sur ce produit</span>
          {related.length ? (
            <ul className="flex flex-col">
              {related.map((x) => <RelatedRule key={x.id} r={x} applied={x.id === appliedRuleId} onEdit={() => onEditRule(x)} />)}
            </ul>
          ) : (
            <p className="text-[12.5px] text-muted-foreground">Aucune règle {col.kind === "tag" ? "pour ce groupe" : "pour ce client"} ne couvre ce produit.</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" icon={Plus} onClick={() => onNewRule({ clientScope: scope, productScope: { kind: "product", productId: product.id } })}>Règle sur ce produit</Button>
            <Button size="sm" icon={Plus} onClick={() => onNewRule({ clientScope: scope, productScope: { kind: "category", category: product.category } })}>
              Règle sur {categoryLabel(product.category).toLowerCase()}
            </Button>
          </div>
        </section>

        {col.kind === "client" && resolved ? (
          <section className="flex flex-col gap-2 border-t border-border pt-4">
            <span className={SECTION_LABEL}>Prix négocié pour ce client</span>
            <NegotiatedPriceEditor clientId={col.id} productId={product.id} resolved={resolved} />
          </section>
        ) : null}
      </div>
    </SidePanel>
  );
}

function GridHeadline({ row, ruleName }: { row: PriceGridRow; ruleName?: string }) {
  const delta = row.listPrice ? (row.price - row.listPrice) / row.listPrice : 0;
  return (
    <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
      <div>
        <div className={SECTION_LABEL}>Prix unitaire HT</div>
        <div className="num text-[22px] font-semibold leading-7 tabular-nums tracking-tight">{fmtMoney(row.price)}</div>
      </div>
      <Metric label="Catalogue" value={<Money value={row.listPrice} />} hint={Math.abs(delta) >= 0.0005 ? `${delta < 0 ? "−" : "+"}${fmtPercent(Math.abs(delta))}` : undefined} />
      <Metric label="Coût" value={<Money value={row.cost} />} />
      <Metric label="Marge" value={<MarginCell value={row.marginPct} />} hint={fmtMoney(row.price - row.cost)} />
      <Metric label="Source" value={<SourceLabel source={row.source} ruleName={ruleName} />} />
    </div>
  );
}

function RelatedRule({ r, applied, onEdit }: { r: PriceRuleSummary; applied: boolean; onEdit: () => void }) {
  const st = ruleState(r);
  return (
    <li>
      <button
        type="button"
        onClick={onEdit}
        className="group flex h-8 w-full items-center gap-2 rounded-[4px] px-1.5 text-left text-[13px] hover:bg-muted"
        title={r.note ?? r.name}
      >
        <Dot tone={st === "active" ? "success" : st === "scheduled" ? "info" : "muted"} />
        <span className={cn("min-w-0 flex-1 truncate", st === "active" ? "" : "text-muted-foreground")}>{r.name}</span>
        {applied ? <span className="shrink-0 text-[11.5px] text-primary">appliquée</span> : null}
        <span className="num shrink-0 text-[12.5px] tabular-nums text-secondary-foreground">{methodShort(r.method)}</span>
        <Pencil size={12} strokeWidth={1.75} className="shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100" />
      </button>
    </li>
  );
}
