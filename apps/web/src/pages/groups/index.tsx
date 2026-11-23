/**
 * Groupes — client / product / supplier groups (TagDef). Three columns; create inline; click a group to edit it
 * and manage its members in a SidePanel. Groups drive price rules (Prix → Règles).
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Building2, Package, Plus, Tags, Users, X, type LucideIcon } from "lucide-react";
import type { ClientSummary, ProductSummary, Supplier, TagDef } from "@kit/shared";
import { api, type TagScope, type TagWithCount } from "@/lib/api";
import { cn } from "@/lib/cn";
import { categoryIds, categoryLabel, categoryOptions, CLIENT_TYPE_LABEL } from "@/lib/labels";
import { qk, useApiMutation, useClients, useProducts, useSuppliers, useTagMembers, useTags } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import {
  Button, EmptyState, Field, Input, Mono, Page, PageBody, PageHeader, SECTION_LABEL, SearchInput, SidePanel, Skeleton, Textarea,
  TagColorPicker, TagDot, TAG_COLORS, tagSlug, type TagColor,
} from "@/ui";
import { Combobox } from "../prices/pickers";
import { InlineConfirmDelete } from "../prices/rules";

const SCOPES: { scope: TagScope; label: string; icon: LucideIcon; path: string; noun: string }[] = [
  { scope: "client", label: "Clients", icon: Users, path: "/clients", noun: "client" },
  { scope: "product", label: "Produits", icon: Package, path: "/products", noun: "produit" },
  { scope: "supplier", label: "Fournisseurs", icon: Building2, path: "/suppliers", noun: "fournisseur" },
];

export default function GroupsPage() {
  const [sel, setSel] = useUrlState("g", "", { keepPage: true });
  const [q, setQ] = useUrlState("q");
  const { data: tags, isLoading } = useTags();
  const [selScope, selId] = sel.split(":") as [TagScope | "", string | undefined];
  const selected = tags?.find((t) => t.scope === selScope && t.id === selId);

  return (
    <Page>
      <PageHeader
        title="Groupes"
        count={tags?.length}
        filters={<SearchInput value={q} onChange={setQ} placeholder="Chercher un groupe…" />}
      />
      <PageBody flush>
        <div className="grid min-h-full grid-cols-1 divide-y divide-border md:grid-cols-3 md:divide-x md:divide-y-0">
          {SCOPES.map((s) => (
            <ScopeColumn
              key={s.scope}
              meta={s}
              tags={tags?.filter((t) => t.scope === s.scope)}
              loading={isLoading}
              q={q}
              selected={selScope === s.scope ? selId : undefined}
              onSelect={(id) => setSel(id && !(selScope === s.scope && selId === id) ? `${s.scope}:${id}` : "")}
            />
          ))}
        </div>
      </PageBody>
      {selected ? <GroupPanel key={sel} tag={selected} onClose={() => setSel("")} /> : null}
    </Page>
  );
}

function ScopeColumn({ meta, tags, loading, q, selected, onSelect }: {
  meta: (typeof SCOPES)[number]; tags?: TagWithCount[]; loading: boolean; q: string; selected?: string; onSelect: (id: string) => void;
}) {
  const [creating, setCreating] = useState(false);
  const n = q.trim().toLowerCase();
  const list = useMemo(
    () => (tags ?? []).filter((t) => !n || `${t.label} ${t.id} ${t.description ?? ""}`.toLowerCase().includes(n)).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
    [tags, n],
  );
  const Icon = meta.icon;
  return (
    <section className="flex min-w-0 flex-col">
      <header className="sticky top-0 z-[1] flex h-10 items-center gap-2 border-b border-border bg-background px-4">
        <Icon size={14} strokeWidth={1.75} className="text-muted-foreground" />
        <span className={SECTION_LABEL}>{meta.label}</span>
        <span className="text-[11.5px] tabular-nums text-muted-foreground">{tags?.length ?? ""}</span>
        <Button size="sm" variant="ghost" icon={Plus} className="ml-auto" onClick={() => setCreating(true)}>Groupe</Button>
      </header>
      {creating ? <NewGroupRow scope={meta.scope} taken={(tags ?? []).map((t) => t.id)} onDone={(id) => { setCreating(false); if (id) onSelect(id); }} /> : null}
      {loading && !tags ? (
        <div className="flex flex-col gap-3 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
      ) : !list.length && !creating ? (
        <EmptyState
          compact
          icon={Tags}
          title={n ? "Aucun groupe ne correspond" : `Aucun groupe de ${meta.label.toLowerCase()}`}
          description={n ? undefined : "Regroupez-les pour leur appliquer des règles de prix."}
          action={n ? undefined : <Button size="sm" icon={Plus} onClick={() => setCreating(true)}>Nouveau groupe</Button>}
        />
      ) : (
        <ul className="flex flex-col">
          {list.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => onSelect(t.id)}
                className={cn(
                  "flex w-full items-start gap-2.5 border-b border-border px-4 py-2.5 text-left transition-colors hover:bg-muted/60",
                  selected === t.id && "bg-row-selected hover:bg-row-selected",
                )}
              >
                <TagDot color={t.color} className="mt-[6px]" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="truncate text-[13px] font-medium">{t.label}</span>
                    <Mono className="hidden truncate text-[11px] text-muted-foreground xl:inline">{t.id}</Mono>
                  </span>
                  {t.description ? <span className="block truncate text-[12px] text-muted-foreground">{t.description}</span> : null}
                </span>
                <span className="shrink-0 text-[12px] tabular-nums text-muted-foreground">
                  {t.count} {meta.noun}{t.count > 1 ? "s" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function NewGroupRow({ scope, taken, onDone }: { scope: TagScope; taken: string[]; onDone: (id?: string) => void }) {
  const [label, setLabel] = useState("");
  const [color, setColor] = useState<TagColor>(TAG_COLORS[taken.length % (TAG_COLORS.length - 1)]);
  const create = useApiMutation(api.tags.create, { success: (t) => `Groupe « ${t.label} » créé`, invalidate: [qk.tags.all], onSuccess: (t) => onDone(t.id) });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (label.trim()) create.mutate({ id: tagSlug(label, taken), scope, label: label.trim(), color });
  };
  return (
    <form onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onDone(); } }} className="flex flex-col gap-2 border-b border-border bg-muted/30 px-4 py-2.5">
      <Input size="sm" autoFocus value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Nom du groupe" />
      <div className="flex items-center gap-2">
        <TagColorPicker value={color} onChange={setColor} />
        <span className="ml-auto flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => onDone()}>Annuler</Button>
          <Button size="sm" variant="primary" type="submit" disabled={!label.trim()} loading={create.isPending}>Créer</Button>
        </span>
      </div>
    </form>
  );
}

// ── Group panel: edit + members ──

interface Member { id: string; name: string; sub: string; tags: string[] }

function toMembers(scope: TagScope, rows: unknown[] | undefined): Member[] | undefined {
  if (!rows) return undefined;
  if (scope === "client") return (rows as ClientSummary[]).map((c) => ({ id: c.id, name: c.name, sub: `${c.code} · ${CLIENT_TYPE_LABEL[c.type] ?? c.type}`, tags: c.tags ?? [] }));
  if (scope === "product") return (rows as ProductSummary[]).map((p) => ({ id: p.id, name: p.name, sub: `${p.sku} · ${categoryLabel(p.category)}`, tags: p.tags ?? [] }));
  return (rows as Supplier[]).map((s) => ({ id: s.id, name: s.name, sub: s.categories?.map((c) => categoryLabel(c)).join(", ") ?? "", tags: s.tags ?? [] }));
}

function GroupPanel({ tag, onClose }: { tag: TagWithCount; onClose: () => void }) {
  const qc = useQueryClient();
  const meta = SCOPES.find((s) => s.scope === tag.scope)!;
  const [label, setLabel] = useState(tag.label);
  const [description, setDescription] = useState(tag.description ?? "");
  const { data: memberRows, isLoading } = useTagMembers(tag.scope, tag.id);
  const members = toMembers(tag.scope, memberRows as unknown[] | undefined);

  const { data: clients } = useClients();
  const { data: products } = useProducts();
  const { data: suppliers } = useSuppliers();
  const all = toMembers(tag.scope, (tag.scope === "client" ? clients : tag.scope === "product" ? products : suppliers) as unknown[] | undefined);
  const memberIds = new Set((members ?? []).map((m) => m.id));
  const candidates = (all ?? []).filter((m) => !memberIds.has(m.id)).sort((a, b) => a.name.localeCompare(b.name)).map((m) => ({ value: m.id, label: m.name, sub: m.sub.split(" · ")[0] }));

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: qk.tags.all });
    void qc.invalidateQueries({ queryKey: qk.pricing.all });
    void qc.invalidateQueries({ queryKey: { client: qk.clients.all, product: qk.products.all, supplier: qk.suppliers.all }[tag.scope] });
  };
  const update = useApiMutation((body: Partial<Pick<TagDef, "label" | "color" | "description">>) => api.tags.update(tag.scope, tag.id, body), {
    success: "Groupe enregistré", invalidate: [qk.tags.all, qk.pricing.all],
  });
  const remove = useApiMutation(() => api.tags.remove(tag.scope, tag.id), {
    success: `Groupe « ${tag.label} » supprimé`, onSuccess: () => { invalidate(); onClose(); },
  });
  const setTags = useApiMutation((v: { id: string; tags: string[] }) => api.tags.setOn(tag.scope, v.id, v.tags), { onSuccess: invalidate });
  const addMember = (id: string) => {
    const m = all?.find((x) => x.id === id);
    if (m) setTags.mutate({ id, tags: [...m.tags.filter((t) => t !== tag.id), tag.id] });
  };
  const removeMember = (m: Member) => setTags.mutate({ id: m.id, tags: m.tags.filter((t) => t !== tag.id) });

  const commitText = () => {
    const body: Partial<TagDef> = {};
    if (label.trim() && label.trim() !== tag.label) body.label = label.trim();
    if (description.trim() !== (tag.description ?? "")) body.description = description.trim();
    if (Object.keys(body).length) update.mutate(body);
  };

  return (
    <SidePanel
      id="group"
      title={<span className="flex items-center gap-2"><TagDot color={tag.color} />{tag.label}</span>}
      subtitle={`Groupe de ${meta.label.toLowerCase()} · ${tag.count} ${meta.noun}${tag.count > 1 ? "s" : ""}`}
      onClose={onClose}
      footer={
        <>
          <span className="mr-auto text-[11.5px] text-muted-foreground">Supprimer retire le groupe de chaque {meta.noun} ; les règles qui le visent cessent de s'appliquer.</span>
          <InlineConfirmDelete text onConfirm={() => remove.mutate()} pending={remove.isPending} label="Supprimer" />
        </>
      }
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          <Field label="Nom"><Input value={label} onChange={(e) => setLabel(e.target.value)} onBlur={commitText} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} /></Field>
          <Field label="Description"><Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} onBlur={commitText} placeholder="À quoi sert ce groupe…" /></Field>
          <Field label="Couleur"><TagColorPicker value={tag.color} onChange={(color) => update.mutate({ color })} /></Field>
          <div className="text-[11.5px] text-muted-foreground">Identifiant <Mono>{tag.id}</Mono> · enregistré automatiquement</div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <span className={SECTION_LABEL}>Membres</span>
            <span className="text-[11.5px] tabular-nums text-muted-foreground">{members?.length ?? ""}</span>
          </div>
          <Combobox value="" onChange={addMember} options={candidates} placeholder={`Ajouter un ${meta.noun}…`} size="sm" />
          {isLoading && !members ? (
            <div className="flex flex-col gap-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-7 w-full" />)}</div>
          ) : !members?.length ? (
            <p className="py-3 text-[12.5px] text-muted-foreground">Aucun {meta.noun} dans ce groupe.</p>
          ) : (
            <ul className="rounded-[4px] border border-border">
              {members.sort((a, b) => a.name.localeCompare(b.name)).map((m) => (
                <li key={m.id} className="group flex h-9 items-center gap-2 border-b border-border px-2.5 last:border-b-0">
                  <Link to={`${meta.path}/${m.id}`} className="min-w-0 flex-1 truncate text-[13px] hover:underline">{m.name}</Link>
                  <span className="max-w-[45%] truncate text-[11.5px] text-muted-foreground">{m.sub}</span>
                  <button
                    type="button"
                    aria-label={`Retirer ${m.name} du groupe`}
                    title="Retirer du groupe"
                    onClick={() => removeMember(m)}
                    className="grid size-6 place-items-center rounded-[4px] text-muted-foreground opacity-60 hover:bg-muted hover:text-destructive group-hover:opacity-100"
                  >
                    <X size={13} strokeWidth={1.75} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {tag.scope !== "supplier" ? (
          <Link to={`/prices?tab=rules&q=${encodeURIComponent(tag.label)}`} className="text-[12.5px] text-primary hover:underline">
            Voir les règles de prix de ce groupe →
          </Link>
        ) : null}
      </div>
    </SidePanel>
  );
}
