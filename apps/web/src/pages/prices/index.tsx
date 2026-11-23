/**
 * Prix — price matrix (products × client groups / clients), pricing rules, negotiated client prices and a price simulator.
 * Resolution order (API): ClientPrice > most specific active PriceRule (then priority, then newest) > list price.
 */
import { useMemo } from "react";
import { Plus } from "lucide-react";
import type { PriceRule } from "@kit/shared";
import { usePriceRules } from "@/lib/queries";
import { useDebounced, useUrlPatch, useUrlState } from "@/lib/url-state";
import { Button, Page, PageBody, PageHeader, SearchInput, Tabs } from "@/ui";
import { MatrixFilters, MatrixTab } from "./matrix";
import { NegotiatedTab, useNegotiatedPrices } from "./negotiated";
import { Combobox, useClientOptions, useProductOptions, useTagOptions } from "./pickers";
import { RulePanel, RulesTable } from "./rules";
import { SimulatorTab } from "./simulator";

type Tab = "matrix" | "rules" | "negotiated" | "sim";

export default function PricesPage() {
  const [tab] = useUrlState("tab", "matrix");
  const patch = useUrlPatch();
  const [q, setQ] = useUrlState("q");
  const [ruleSel, setRuleSel] = useUrlState("rule", "", { keepPage: true });
  const [ruleActive] = useUrlState("ractive");
  const [cpClient, setCpClient] = useUrlState("cpclient");
  const [cpTag, setCpTag] = useUrlState("cptag");
  const [cpProduct, setCpProduct] = useUrlState("cpproduct");
  const [adding, setAdding] = useUrlState("add", "", { keepPage: true });
  const dq = useDebounced(q, 200);

  const { data: rules, isLoading } = usePriceRules();
  const { rows: negotiated } = useNegotiatedPrices();
  const clientOptions = useClientOptions();
  const productOptions = useProductOptions();
  const clientTags = useTagOptions("client");

  const filteredRules = useMemo(() => {
    if (!rules) return undefined;
    const n = dq.trim().toLowerCase();
    return rules.filter(
      (r) =>
        (!ruleActive || String(r.active) === ruleActive) &&
        (!n || `${r.name} ${r.clientScopeLabel} ${r.productScopeLabel} ${r.methodLabel} ${r.note ?? ""}`.toLowerCase().includes(n)),
    );
  }, [rules, dq, ruleActive]);
  const editing: PriceRule | undefined = ruleSel && ruleSel !== "new" ? rules?.find((r) => r.id === ruleSel) : undefined;

  // Old links (?tab=grid) land on the matrix.
  const t: Tab = tab === "grid" || !["matrix", "rules", "negotiated", "sim"].includes(tab) ? "matrix" : (tab as Tab);
  // One URL write for the tab switch and the params it clears.
  const switchTab = (v: Tab) => patch({ tab: v === "matrix" ? "" : v, rule: "", add: "", cell: "", q: "" });

  return (
    <Page>
      <PageHeader
        title="Prix"
        tabs={
          <Tabs<Tab>
            value={t}
            onChange={switchTab}
            items={[
              { id: "matrix", label: "Matrice" },
              { id: "rules", label: "Règles", count: rules?.length },
              { id: "negotiated", label: "Prix négociés", count: negotiated?.length },
              { id: "sim", label: "Simulateur" },
            ]}
          />
        }
        filters={
          t === "matrix" ? <><SearchInput value={q} onChange={setQ} placeholder="Produit, SKU…" /><MatrixFilters /></>
          : t === "rules" ? <SearchInput value={q} onChange={setQ} placeholder="Règle, groupe, produit…" />
          : t === "negotiated" ? (
            <>
              <SearchInput value={q} onChange={setQ} placeholder="Client, produit…" />
              <Combobox value={cpClient} onChange={setCpClient} options={clientOptions} placeholder="Tous les clients" size="sm" width={220} clearable />
              <Combobox value={cpTag} onChange={setCpTag} options={clientTags} placeholder="Tous les groupes de clients" size="sm" width={220} clearable />
              <Combobox value={cpProduct} onChange={setCpProduct} options={productOptions} placeholder="Tous les produits" size="sm" width={240} clearable />
            </>
          )
          : null
        }
        actions={
          t === "rules" ? <Button variant="primary" icon={Plus} onClick={() => setRuleSel("new")}>Nouvelle règle</Button>
          : t === "negotiated" ? <Button variant="primary" icon={Plus} onClick={() => setAdding("1")}>Nouveau prix négocié</Button>
          : null
        }
      />
      <PageBody flush>
        {t === "matrix" ? (
          <MatrixTab q={dq} />
        ) : t === "rules" ? (
          <RulesTable
            rules={filteredRules}
            loading={isLoading}
            selectedId={ruleSel || undefined}
            onOpen={(r) => setRuleSel(r.id === ruleSel ? "" : r.id)}
            onCreate={() => setRuleSel("new")}
            filtered={!!(dq || ruleActive)}
          />
        ) : t === "negotiated" ? (
          <NegotiatedTab clientId={cpClient} clientTag={cpTag} productId={cpProduct} q={dq} adding={!!adding} onCloseAdd={() => setAdding("")} onAdd={() => setAdding("1")} />
        ) : (
          <SimulatorTab />
        )}
      </PageBody>
      {t === "rules" && (ruleSel === "new" || editing) ? (
        <RulePanel key={ruleSel} rule={editing} onClose={() => setRuleSel("")} onSaved={(r) => setRuleSel(r.id)} />
      ) : null}
    </Page>
  );
}
