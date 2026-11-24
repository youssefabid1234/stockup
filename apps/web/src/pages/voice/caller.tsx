/**
 * Team 12 (Youssef) · "Qui appelle ?" — caller ID before the call.
 * Real life: the phone rings, the screen shows "Maison Sarrailh – Nadine" (the WhatsApp / phone number is known),
 * and Lucie opens the sheet before picking up. Here: pick the calling client (searchable list of the ERP's clients,
 * phones included) and who is on the phone, or tick "Nouveau client"; then "Démarrer l'appel" sends a `caller`
 * message: the AI service loads the client's sheet before the first word (TEAM_PRELOAD).
 */
import { useMemo, useState, type FormEvent } from "react";
import { PhoneCall, PhoneOff, UserPlus } from "lucide-react";
import type { CallerReady } from "@kit/shared";
import { Button, Dot, Field, Input, Segmented, Select, Spinner } from "@/ui";
import { useClients } from "@/lib/queries";
import type { CallerInput } from "@/features/assistant/useVoiceSession";

type Kind = "known" | "new";

export function CallerForm({ disabled, pending, onStart }: { disabled: boolean; pending: boolean; onStart: (c: CallerInput) => void }) {
  const [kind, setKind] = useState<Kind>("known");
  const clients = useClients();
  const [clientId, setClientId] = useState("");
  const [contactIdx, setContactIdx] = useState("");
  const [contactTitle, setContactTitle] = useState<CallerInput["contactTitle"]>();
  const [company, setCompany] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  const options = useMemo(
    () =>
      (clients.data ?? []).map((c) => ({
        value: c.id,
        label: c.name,
        hint: [c.city, ...(c.contacts ?? []).map((x) => x.phone)].filter(Boolean).join(" · "),
      })),
    [clients.data],
  );
  const selected = clients.data?.find((c) => c.id === clientId);
  const contacts = selected?.contacts ?? [];
  const contact = contactIdx !== "" ? contacts[Number(contactIdx)] : contacts[0];

  const canStart = !disabled && !pending && (kind === "known" ? !!clientId : !!(company.trim() || name.trim()) && !!phone.trim());

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canStart) return;
    if (kind === "known") onStart({ clientId, contactName: contact?.name, phone: contact?.phone, contactTitle });
    else onStart({ isNew: true, companyName: company.trim() || undefined, contactName: name.trim() || undefined, phone: phone.trim(), contactTitle });
  };

  return (
    <form onSubmit={submit} className="mx-auto my-auto flex w-full max-w-[520px] flex-col gap-4 rounded-[6px] border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold">Who's calling?</h2>
          <p className="text-[12px] text-muted-foreground">
            Like the number that appears on the standard: the agent will know the customer before even picking up.
          </p>
        </div>
        <Segmented<Kind> value={kind} onChange={(value) => { setKind(value); setContactTitle(undefined); }} options={[{ id: "known", label: "Customer" }, { id: "new", label: "New customer" }]} />
      </div>

      {kind === "known" ? (
        <>
          <Field label="Customer" hint="Type a name, city or phone number">
            <Select
              value={clientId}
              onChange={(v) => { setClientId(v); setContactIdx(""); setContactTitle(undefined); }}
              options={options}
              placeholder={clients.isLoading ? "Loading customers..." : "Select the client who calls"}
              filterable
            />
          </Field>
          {contacts.length > 0 ? (
            <Field label="On the phone">
              <Select
                value={contactIdx === "" ? "0" : contactIdx}
                onChange={(value) => { setContactIdx(value); setContactTitle(undefined); }}
                options={contacts.map((x, i) => ({ value: String(i), label: x.name, hint: [x.role, x.phone].filter(Boolean).join(" · ") }))}
              />
            </Field>
          ) : null}
          {selected?.status === "blocked" ? (
            <p className="flex items-center gap-1.5 text-[12px] text-warning"><Dot tone="warning" /> The agent won't promise anything.</p>
          ) : null}
        </>
      ) : (
        <>
          <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <UserPlus size={14} strokeWidth={1.75} /> Not yet in the ERP The agent takes the application, the team validates the account.
          </p>
          <Field label="Establishment"><Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e. Canal Bakery" /></Field>
          <Field label="Contact name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Camille Durand" /></Field>
          <Field label="Phone"><Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="e.g. 06 12 34 56 78" /></Field>
        </>
      )}

      <Field label="Title (optional)">
        <Select
          value={contactTitle ?? "neutral"}
          onChange={(value) => setContactTitle(value === "madame" || value === "monsieur" ? value : undefined)}
          options={[
            { value: "neutral", label: "None" },
            { value: "madame", label: "Ma'am" },
            { value: "monsieur", label: "Sir" },
          ]}
        />
      </Field>

      <Button type="submit" variant="default" icon={pending ? undefined : PhoneCall} disabled={!canStart}>
        {pending ? <><Spinner size={12} /> Loading the file...</> : "Start call"}
      </Button>
    </form>
  );
}

export function CallerBar({ caller, onHangUp }: { caller: CallerReady; onHangUp: () => void }) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-border bg-violet/[.06] px-5 py-2 text-[12.5px]">
      <Dot tone={caller.isNew ? "warning" : caller.status === "blocked" ? "destructive" : "success"} />
      <span className="font-medium">{caller.name}</span>
      {caller.contactName ? <span className="text-muted-foreground">· {caller.contactName}</span> : null}
      <span className="text-muted-foreground">
        {caller.isNew
          ? "· new customer (to be validated by the team)"
          : caller.usedByAgent
            ? `· file loaded${caller.loadedMs != null ? ` en ${caller.loadedMs} ms` : ""}`
            : "· identified (fiche not available: the agent will look for the client)"}
      </span>
      <Button size="sm" variant="danger" icon={PhoneOff} className="ml-auto" onClick={onHangUp}>Hang up</Button>
    </div>
  );
}
