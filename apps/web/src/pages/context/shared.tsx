/**
 * Contexte — shared pieces: kind tones, the source mark (AI / voice
 * entries tinted violet), the side panel (view + autosaved edit, or create), and <EntityContext/>, the section shown on
 * client / supplier / product pages (its own entries + related ones, add / edit in the panel).
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Plus } from "lucide-react";
import type { Actor, ContextEntry, ContextForEntity, ContextEntryInput, ContextEntrySummary, ContextKind, ContextScope, ContextSource } from "@kit/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Markdown, MarkdownEditor } from "@/ui/markdown";
import { categoryIds, categoryLabel, categoryOptions, CONTEXT_KIND_LABEL, CONTEXT_SCOPE_LABEL, CONTEXT_SOURCE_LABEL } from "@/lib/labels";
import { qk, useApiMutation, useClients, useContextFor, useProducts, useSuppliers } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import {
  ActorIcon, Button, DateLabel, EmptyState, Field, Input, Mono, Section, Select, SidePanel, Skeleton, StatusDot,
  isAiActor, type Tone,
} from "@/ui";
import { InlineConfirmDelete } from "../prices/rules";

// ── Labels & tones ──

export const KIND_TONE: Record<ContextKind, Tone> = {
  policy: "warning", procedure: "info", preference: "success", fact: "muted",
  relationship: "foreground", pricing: "success", logistics: "info", risk: "destructive",
};
export const KIND_OPTIONS = (Object.keys(CONTEXT_KIND_LABEL) as ContextKind[]).map((k) => ({ value: k, label: CONTEXT_KIND_LABEL[k] }));
export const SCOPE_OPTIONS = (Object.keys(CONTEXT_SCOPE_LABEL) as ContextScope[]).map((s) => ({ value: s, label: CONTEXT_SCOPE_LABEL[s] }));
export const SOURCE_OPTIONS = (Object.keys(CONTEXT_SOURCE_LABEL) as ContextSource[]).map((s) => ({ value: s, label: CONTEXT_SOURCE_LABEL[s] }));

export const isAiSource = (s?: ContextSource) => s === "ai_chat" || s === "voice_agent";
const ENTITY_PATH: Partial<Record<ContextScope, string>> = { client: "/clients", supplier: "/suppliers", product: "/products" };
export const entityHref = (e: Pick<ContextEntry, "entityType" | "entityId">) =>
  e.entityId && ENTITY_PATH[e.entityType] ? `${ENTITY_PATH[e.entityType]}/${e.entityId}` : undefined;

export function KindDot({ kind }: { kind: ContextKind }) {
  return <StatusDot tone={KIND_TONE[kind]} label={CONTEXT_KIND_LABEL[kind]} />;
}

/** Who wrote it: AI / voice entries get the violet actor chip, the others a muted word. */
export function SourceMark({ source, compact }: { source?: ContextSource; compact?: boolean }) {
  const s = source ?? "seed";
  if (isAiSource(s)) {
    return (
      <span className="inline-flex items-center gap-1.5 text-violet">
        <ActorIcon actor={s as Actor} size={18} />
        {compact ? null : <span className="text-[12px]">{CONTEXT_SOURCE_LABEL[s]}</span>}
      </span>
    );
  }
  return compact ? null : <span className="text-[12px] text-muted-foreground">{CONTEXT_SOURCE_LABEL[s]}</span>;
}

/** Context entries render with the app-wide Markdown component. */
export function ContextMarkdown({ text, className }: { text: string; className?: string }) {
  return <Markdown text={text} className={cn("text-secondary-foreground", className)} />;
}

// ── Entity choices (create panel) ──

export function useEntityOptions(scope: ContextScope) {
  const { data: clients } = useClients();
  const { data: suppliers } = useSuppliers();
  const { data: products } = useProducts();
  return useMemo(() => {
    switch (scope) {
      case "client": return (clients ?? []).map((c) => ({ value: c.id, label: c.name, hint: c.code })).sort((a, b) => a.label.localeCompare(b.label));
      case "supplier": return (suppliers ?? []).map((s) => ({ value: s.id, label: s.name, hint: s.city })).sort((a, b) => a.label.localeCompare(b.label));
      case "product": return (products ?? []).map((p) => ({ value: p.id, label: p.name, hint: p.sku })).sort((a, b) => a.label.localeCompare(b.label));
      case "category": return categoryOptions();
      default: return [];
    }
  }, [scope, clients, suppliers, products]);
}

const tagsFrom = (s: string) => s.split(",").map((t) => t.trim()).filter(Boolean);

// ── Side panel: edit (autosaved) ──

export function ContextPanel({ entry, onClose }: { entry: ContextEntrySummary; onClose: () => void }) {
  const [title, setTitle] = useState(entry.title);
  const [body, setBody] = useState(entry.body);
  const [tags, setTags] = useState((entry.tags ?? []).join(", "));
  const update = useApiMutation((patch: Partial<ContextEntryInput>) => api.context.update(entry.id, patch), { invalidate: [qk.context.all] });
  const remove = useApiMutation(() => api.context.remove(entry.id), { success: "Fiche supprimée", invalidate: [qk.context.all], onSuccess: onClose });

  const commit = () => {
    const patch: Partial<ContextEntryInput> = {};
    if (title.trim() && title.trim() !== entry.title) patch.title = title.trim();
    if (body.trim() && body.trim() !== entry.body) patch.body = body.trim();
    if (tags !== (entry.tags ?? []).join(", ")) patch.tags = tagsFrom(tags);
    if (Object.keys(patch).length) update.mutate(patch);
  };
  const href = entityHref(entry);
  const ai = isAiSource(entry.source);

  return (
    <SidePanel
      id="context"
      title={<span className="flex min-w-0 items-center gap-2">{ai ? <SourceMark source={entry.source} compact /> : null}<span className="truncate">{entry.title}</span></span>}
      subtitle={<>{CONTEXT_SCOPE_LABEL[entry.entityType]} · {href ? <Link to={href} className="hover:underline">{entry.entityLabel}</Link> : entry.entityLabel}</>}
      onClose={onClose}
      footer={
        <>
          <span className="mr-auto flex min-w-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <SourceMark source={entry.source} /> · modifiée <DateLabel date={entry.updatedAt} format="relative" />
            {update.isPending ? " · enregistrement…" : ""}
          </span>
          <InlineConfirmDelete text onConfirm={() => remove.mutate()} pending={remove.isPending} label="Supprimer" />
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className={cn("flex flex-col gap-3", ai && "rounded-[4px] border-l-2 border-violet/60 pl-3")}>
          <Field label="Titre">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Genre">
              <Select value={entry.kind} onChange={(kind) => kind !== entry.kind && update.mutate({ kind: kind as ContextKind })} options={KIND_OPTIONS} className="w-full" />
            </Field>
            <Field label="Mots-clés" hint="Séparés par des virgules">
              <Input value={tags} onChange={(e) => setTags(e.target.value)} onBlur={commit} placeholder="substitution, appel" />
            </Field>
          </div>
          <MarkdownEditor
            label="Contenu"
            hint="Markdown : listes, **gras**, tableaux, liens. Enregistré automatiquement. L'aperçu est ce que lit l'agent."
            value={body}
            onChange={setBody}
            onCommit={commit}
          />
        </div>
        <div className="text-[11.5px] text-muted-foreground">
          Identifiant <Mono>{entry.id}</Mono>{entry.entityId ? <> · <Mono>{entry.entityId}</Mono></> : null} · créée <DateLabel date={entry.createdAt} format="relative" />
        </div>
      </div>
    </SidePanel>
  );
}

// ── Side panel: create ──

export function NewContextPanel({ defaults, lockTarget, onClose, onCreated }: {
  defaults?: { scope?: ContextScope; entityId?: string; kind?: ContextKind };
  /** Scope + entity fixed (detail pages). */
  lockTarget?: { label: string };
  onClose: () => void;
  onCreated?: (e: ContextEntry) => void;
}) {
  const [scope, setScope] = useState<ContextScope>(defaults?.scope ?? "company");
  const [entityId, setEntityId] = useState(defaults?.entityId ?? "");
  const [kind, setKind] = useState<ContextKind>(defaults?.kind ?? "fact");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState("");
  const options = useEntityOptions(scope);
  const create = useApiMutation(api.context.create, {
    success: (e) => `Fiche « ${e.title} » ajoutée`,
    invalidate: [qk.context.all],
    onSuccess: (e) => { onCreated?.(e); onClose(); },
  });
  const needsEntity = scope !== "company";
  const ok = title.trim() && body.trim() && (!needsEntity || entityId);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ok) return;
    create.mutate({ entityType: scope, ...(needsEntity ? { entityId } : {}), kind, title: title.trim(), body: body.trim(), tags: tagsFrom(tags) });
  };

  return (
    <SidePanel
      id="context"
      title="Nouvelle fiche de contexte"
      subtitle={lockTarget ? `${CONTEXT_SCOPE_LABEL[scope]} · ${lockTarget.label}` : "Ce que les agents doivent savoir"}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Annuler</Button>
          <Button variant="primary" type="submit" form="new-context" loading={create.isPending} disabled={!ok}>Ajouter</Button>
        </>
      }
    >
      <form id="new-context" onSubmit={submit} className="flex flex-col gap-3.5">
        {lockTarget ? null : (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Concerne">
              <Select value={scope} onChange={(v) => { setScope(v as ContextScope); setEntityId(""); }} options={SCOPE_OPTIONS} className="w-full" />
            </Field>
            {needsEntity ? (
              <Field label={CONTEXT_SCOPE_LABEL[scope]}>
                <Select value={entityId} onChange={setEntityId} options={options} placeholder="Choisir…" filterable className="w-full" />
              </Field>
            ) : <div />}
          </div>
        )}
        <Field label="Titre"><Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Livraison par la porte de service" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Genre"><Select value={kind} onChange={(v) => setKind(v as ContextKind)} options={KIND_OPTIONS} className="w-full" /></Field>
          <Field label="Mots-clés"><Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="livraison, accès" /></Field>
        </div>
        <MarkdownEditor label="Contenu" hint="1 à 5 lignes, markdown." value={body} onChange={setBody} defaultMode="raw" placeholder="- Le chauffeur passe par la cour, code 4821." />
      </form>
    </SidePanel>
  );
}

// ── One entry, as a block (detail pages) ──

function EntryBlock({ e, onOpen, showEntity, clamp }: { e: ContextEntrySummary; onOpen: () => void; showEntity?: boolean; clamp?: boolean }) {
  const ai = isAiSource(e.source);
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className={cn(
          "block w-full border-b border-border px-3.5 py-3 text-left transition-colors last:border-b-0 hover:bg-muted/50",
          ai && "border-l-2 border-l-violet/70 bg-violet/[0.04] hover:bg-violet/[0.08]",
        )}
      >
        <span className="mb-1 flex min-w-0 items-center gap-2">
          <span className="truncate text-[13px] font-medium text-foreground">{e.title}</span>
          {showEntity ? <span className="truncate text-[12px] text-muted-foreground">· {e.entityLabel}</span> : null}
          <span className="ml-auto flex shrink-0 items-center gap-2.5">
            <SourceMark source={e.source} compact />
            <KindDot kind={e.kind} />
          </span>
        </span>
        <ContextMarkdown text={e.body} className={cn(clamp && "line-clamp-3")} />
      </button>
    </li>
  );
}

/** Entries written in the app or by an agent first (newest first), then the data pack ones in document order. */
const learnedFirst = (list: ContextEntrySummary[]) => [
  ...list.filter((e) => e.source && e.source !== "seed").sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
  ...list.filter((e) => !e.source || e.source === "seed"),
];

/**
 * Contexte section of a client / supplier / product page: its entries (click → edit panel), "Ajouter", and related
 * entries (category, company rules citing it). `layout="tab"` = two columns (detail tab), "section" = stacked.
 */
export function EntityContext({ scope, id, label, layout = "section", newOpen, onNewClose }: {
  scope: Exclude<ContextScope, "company">;
  id: string;
  label: string;
  layout?: "tab" | "section";
  /** Controlled "new" panel (the detail tab puts its button in the page header). */
  newOpen?: boolean;
  onNewClose?: () => void;
}) {
  const { data, isLoading } = useContextFor(scope, id);
  const [sel, setSel] = useUrlState("ctx", "", { keepPage: true });
  const [localNew, setLocalNew] = useState(false);
  const creating = newOpen ?? localNew;
  const closeNew = onNewClose ?? (() => setLocalNew(false));
  const all = [...(data?.entries ?? []), ...(data?.related ?? [])];
  const selected = all.find((e) => e.id === sel);

  const own = (
    <Section
      title="Ce que l'agent sait"
      count={data?.entries.length}
      actions={newOpen === undefined ? <Button size="sm" variant="ghost" icon={Plus} onClick={() => setLocalNew(true)}>Ajouter</Button> : undefined}
    >
      {isLoading && !data ? (
        <div className="flex flex-col gap-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
      ) : !data?.entries.length ? (
        <EmptyState compact icon={BookOpen} title="Aucune fiche de contexte" description="Ajoutez ce qu'un agent doit savoir avant d'en parler." />
      ) : (
        <ul className="overflow-hidden rounded-[4px] border border-border">
          {learnedFirst(data.entries).map((e) => <EntryBlock key={e.id} e={e} onOpen={() => setSel(e.id)} />)}
        </ul>
      )}
    </Section>
  );
  const related = data?.related.length ? (
    <Section title="Fiches liées" count={data.related.length}>
      <ul className="overflow-hidden rounded-[4px] border border-border">
        {data.related.map((e) => <EntryBlock key={e.id} e={e} onOpen={() => setSel(e.id)} showEntity clamp />)}
      </ul>
      <Link to={`/context?q=${encodeURIComponent(id)}`} className="mt-2 inline-block text-[12.5px] text-primary hover:underline">
        Chercher « {id} » dans tout le contexte →
      </Link>
    </Section>
  ) : null;

  return (
    <>
      {layout === "tab" ? (
        <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0">{own}</div>
          <aside className="min-w-0">{related ?? <p className="pt-8 text-[12.5px] text-muted-foreground">Aucune fiche liée.</p>}</aside>
        </div>
      ) : (
        <div className="flex flex-col gap-5">{own}{related}</div>
      )}
      {selected ? <ContextPanel key={selected.id} entry={selected} onClose={() => setSel("")} /> : null}
      {creating ? (
        <NewContextPanel defaults={{ scope, entityId: id }} lockTarget={{ label }} onClose={closeNew} onCreated={(e) => setSel(e.id)} />
      ) : null}
    </>
  );
}

export { CONTEXT_KIND_LABEL, CONTEXT_SCOPE_LABEL, CONTEXT_SOURCE_LABEL };

/** Compact "Ce que l'agent sait" block for an entity overview (client / supplier): kind + title + first line, "Tout voir" opens the Contexte tab. */
export function ContextSummary({ data, onOpen, max = 6 }: { data?: ContextForEntity; onOpen: () => void; max?: number }) {
  const entries = data?.entries ?? [];
  return (
    <Section
      title="Ce que l'agent sait"
      count={entries.length}
      actions={<Button size="sm" variant="ghost" icon={BookOpen} onClick={onOpen}>Tout voir</Button>}
    >
      {entries.length ? (
        <ul className="flex flex-col divide-y divide-border overflow-hidden rounded-[4px] border border-border">
          {entries.slice(0, max).map((e) => (
            <li key={e.id}>
              <button
                type="button"
                onClick={onOpen}
                className={cn("flex w-full flex-col gap-0.5 px-3 py-2 text-left hover:bg-muted/50", isAiSource(e.source) && "border-l-2 border-violet/60")}
              >
                <span className="flex items-center gap-2">
                  <KindDot kind={e.kind} />
                  <span className="truncate text-[12.5px] font-medium text-foreground">{e.title}</span>
                </span>
                <span className="line-clamp-1 text-[12px] text-muted-foreground">{e.body.replace(/[#*_`>|-]+/g, " ").replace(/\s+/g, " ").trim()}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <button type="button" onClick={onOpen} className="w-full rounded-[4px] border border-dashed border-border px-3 py-3 text-left text-[12.5px] text-muted-foreground hover:border-border-hover">
          Aucune fiche. Ajouter ce que l'agent doit savoir…
        </button>
      )}
      {entries.length > max ? <div className="mt-1.5 text-[12px] text-muted-foreground">+ {entries.length - max} autres fiches</div> : null}
    </Section>
  );
}
