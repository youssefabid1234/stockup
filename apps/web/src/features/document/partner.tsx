/** Partner card of a document side column: same frame for the client (sale) and the supplier (purchase) —
 *  name + code/status, terms, notes, links to the record and its history. */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, History } from "lucide-react";
import type { Client, Supplier } from "@kit/shared";
import { cn } from "@/lib/cn";
import { CLIENT_TYPE_LABEL } from "@/lib/labels";
import { useClient } from "@/lib/queries";
import { DateLabel, KeyValue, Money, Mono, Section, Skeleton, StatusDot, type KV } from "@/ui";

function PartnerFrame({ title, path, name, badge, items, notes, children }: {
  title: string; path: string; name: string; badge?: ReactNode; items: KV[]; notes?: string; children?: ReactNode;
}) {
  return (
    <Section
      title={title}
      actions={
        <span className="flex items-center gap-3">
          <Link to={`${path}?tab=history`} className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground"><History size={12} />Historique</Link>
          <Link to={path} className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground">Fiche<ArrowUpRight size={12} /></Link>
        </span>
      }
    >
      <div className="mb-2.5 flex items-center gap-2">
        <Link to={path} className="truncate font-medium hover:underline">{name}</Link>
        {badge}
      </div>
      <KeyValue labelWidth={110} items={items} />
      {notes ? (
        <div className="mt-3 rounded-[4px] border border-border bg-muted/40 px-3 py-2 text-[12.5px] text-secondary-foreground" title={notes}>
          <p className="line-clamp-4">{notes}</p>
        </div>
      ) : null}
      {children}
    </Section>
  );
}

export function ClientCard({ client: base }: { client: Client }) {
  const { data: c, isLoading } = useClient(base.id);
  const client = c ?? base;
  const limit = client.creditLimit;
  const outstanding = c?.outstanding;
  const use = limit > 0 && outstanding != null ? outstanding / limit : 0;
  const notes = [...client.notes].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 3);
  return (
    <PartnerFrame
      title="Client"
      path={`/clients/${client.id}`}
      name={client.name}
      badge={<><Mono className="text-muted-foreground">{client.code}</Mono>{client.status !== "active" ? <StatusDot kind="client" value={client.status} /> : null}</>}
      notes={client.preferences}
      items={[
        { label: "Type", value: CLIENT_TYPE_LABEL[client.type] },
        { label: "Zone", value: client.zone || "—" },
        { label: "Conditions", value: client.paymentTermsDays ? `${client.paymentTermsDays} jours` : "Comptant" },
        {
          label: "Encours",
          value: isLoading && !c ? <Skeleton className="mt-1 h-3 w-24" /> : (
            <span className="flex flex-col gap-1">
              <span>
                <Money value={outstanding ?? 0} tone={use > 1 ? "destructive" : use > 0.9 ? "warning" : undefined} />
                <span className="text-muted-foreground"> / {limit > 0 ? <Money value={limit} compact /> : "sans plafond"}</span>
              </span>
              {limit > 0 ? (
                <span className="h-1 w-full overflow-hidden rounded-full bg-muted">
                  <span className={cn("block h-full rounded-full", use > 1 ? "bg-destructive" : use > 0.9 ? "bg-warning" : "bg-primary")} style={{ width: `${Math.min(100, Math.round(use * 100))}%` }} />
                </span>
              ) : null}
            </span>
          ),
        },
        ...(c && c.overdue > 0 ? [{ label: "En retard", value: <Money value={c.overdue} tone="destructive" /> }] : []),
        { label: "Commercial", value: client.salesRep || "—" },
      ]}
    >
      {notes.length ? (
        <ol className="mt-3 flex flex-col gap-2.5">
          {notes.map((n, i) => (
            <li key={`${n.at}-${i}`} className="border-l-2 border-border pl-3">
              <div className="line-clamp-3 whitespace-pre-wrap text-[12.5px] leading-[18px]">{n.text}</div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">{n.author} · <DateLabel date={n.at} format="relative" /></div>
            </li>
          ))}
        </ol>
      ) : null}
    </PartnerFrame>
  );
}

export function SupplierCard({ supplier: s }: { supplier: Supplier }) {
  const contact = s.contacts[0];
  return (
    <PartnerFrame
      title="Fournisseur"
      path={`/suppliers/${s.id}`}
      name={s.name}
      badge={s.city ? <span className="truncate text-[12px] text-muted-foreground">{s.city}</span> : null}
      notes={s.notes}
      items={[
        { label: "Délai", value: `${s.leadTimeDays} jour${s.leadTimeDays > 1 ? "s" : ""}` },
        { label: "Conditions", value: s.paymentTermsDays ? `${s.paymentTermsDays} jours` : "Comptant" },
        { label: "Minimum", value: s.minOrderAmount > 0 ? <Money value={s.minOrderAmount} /> : "Aucun" },
        ...(contact ? [{ label: "Contact", value: <>{contact.name}{contact.phone ? <div className="text-[12px] text-muted-foreground">{contact.phone}</div> : null}</> }] : []),
      ]}
    />
  );
}
