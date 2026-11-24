/**
 * Team 12 (Youssef) · "Qui appelle ?" — caller ID before the call.
 * Real life: the phone rings, the screen shows "Maison Sarrailh – Nadine" (the WhatsApp / phone number is known),
 * and Lucie opens the sheet before picking up. Here: pick the calling client (searchable list of the ERP's clients,
 * phones included) and who is on the phone, or tick "Nouveau client"; then "Démarrer l'appel" sends a `caller`
 * message: the AI service loads the client's sheet before the first word (TEAM_PRELOAD).
 */
import { useMemo, useState, type FormEvent } from "react";
import { cn } from "@/lib/cn";
import { Check, Phone, PhoneCall, PhoneOff, Search, Store, User, UserPlus, Users } from "lucide-react";
import type { CallerReady } from "@kit/shared";
import { Button, Dot, Spinner } from "@/ui";
import { useClients } from "@/lib/queries";
import type { CallerInput } from "@/features/assistant/useVoiceSession";

type Kind = "known" | "new";

// team 12 (Youssef): the « Qui appelle ? » screen in the call page's messaging style (chat.tsx): two big choice cards,
// a rounded search, the clients as a contact list (initials avatar, city · phone, blocked badge), who is on the
// phone and the civility as tappable pills, and a big green « Démarrer l'appel ».
const AVATAR_COLORS = ["#00a884", "#53bdeb", "#e26a4a", "#a77bca", "#f1a33a", "#3a9b7a", "#d46a92", "#5b7fd6"];
const initials = (s: string) => s.replace(/^(la|le|les|l'|au|aux)\s+/i, "").split(/[\s-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
const colorOf = (s: string) => AVATAR_COLORS[[...s].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_COLORS.length];
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const PILL = "rounded-full px-3 py-1.5 text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60";
const PILL_ON = "bg-[#00a884] text-white shadow-sm";
const PILL_OFF = "bg-[#f0f2f5] text-[#3b4a54] hover:bg-[#e4e8eb] dark:bg-[#2a3942] dark:text-[#d1d7db] dark:hover:bg-[#33444f]";

function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, background: colorOf(name), fontSize: size * 0.36 }}
      aria-hidden
    >
      {initials(name) || "?"}
    </span>
  );
}

function ChoiceCard({ on, icon, title, text, onClick }: { on: boolean; icon: React.ReactNode; title: string; text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={cn(
        "flex flex-1 items-center gap-3 rounded-[14px] border-2 p-3 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60",
        on
          ? "border-[#00a884] bg-[#e7fbf4] shadow-sm dark:bg-[#0b3b31]"
          : "border-transparent bg-[#f0f2f5] hover:bg-[#e4e8eb] dark:bg-[#202c33] dark:hover:bg-[#2a3942]",
      )}
    >
      <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full", on ? "bg-[#00a884] text-white" : "bg-white text-[#54656f] dark:bg-[#2a3942] dark:text-[#aebac1]")}>
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-[14px] font-semibold text-[#111b21] dark:text-[#e9edef]">{title}</span>
        <span className="block text-[12px] leading-snug text-[#667781] dark:text-[#8696a0]">{text}</span>
      </span>
    </button>
  );
}

function RoundField({ icon, ...props }: { icon: React.ReactNode } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex items-center gap-2.5 rounded-full bg-[#f0f2f5] px-4 py-2.5 focus-within:ring-2 focus-within:ring-[#00a884]/50 dark:bg-[#2a3942]">
      <span className="shrink-0 text-[#8696a0]">{icon}</span>
      <input {...props} className="min-w-0 flex-1 bg-transparent text-[14px] text-[#111b21] placeholder:text-[#8696a0] focus:outline-none dark:text-[#e9edef]" />
    </label>
  );
}

export function CallerForm({ disabled, pending, onStart }: { disabled: boolean; pending: boolean; onStart: (c: CallerInput) => void }) {
  const [kind, setKind] = useState<Kind>("known");
  const clients = useClients();
  const [query, setQuery] = useState("");
  const [clientId, setClientId] = useState("");
  const [contactIdx, setContactIdx] = useState(0);
  const [contactTitle, setContactTitle] = useState<CallerInput["contactTitle"]>();
  const [company, setCompany] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  const all = clients.data ?? [];
  const found = useMemo(() => {
    const q = norm(query.trim());
    const digits = query.replace(/\D/g, "");
    const rows = q
      ? all.filter((c) => norm(`${c.name} ${c.city ?? ""}`).includes(q) || (digits.length >= 3 && (c.contacts ?? []).some((x) => (x.phone ?? "").replace(/\D/g, "").includes(digits))))
      : all;
    return rows.slice(0, 40);
  }, [all, query]);
  const selected = all.find((c) => c.id === clientId);
  const contacts = selected?.contacts ?? [];
  const contact = contacts[contactIdx] ?? contacts[0];

  const canStart = !disabled && !pending && (kind === "known" ? !!clientId : !!(company.trim() || name.trim()) && !!phone.trim());
  const choose = (k: Kind) => { setKind(k); setContactTitle(undefined); };
  const pick = (id: string) => { setClientId(id); setContactIdx(0); setContactTitle(undefined); };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canStart) return;
    if (kind === "known") onStart({ clientId, contactName: contact?.name, phone: contact?.phone, contactTitle });
    else onStart({ isNew: true, companyName: company.trim() || undefined, contactName: name.trim() || undefined, phone: phone.trim(), contactTitle });
  };

  return (
    <form onSubmit={submit} className="flex w-full flex-col gap-4 rounded-[18px] bg-white p-4 shadow-[0_2px_10px_rgba(11,20,26,.12)] dark:bg-[#111b21]">
      <div>
        <h2 className="text-[17px] font-semibold text-[#111b21] dark:text-[#e9edef]">Qui appelle ?</h2>
        <p className="text-[12.5px] text-[#667781] dark:text-[#8696a0]">Comme le numéro qui s'affiche au standard : Lucie connaît le client avant de décrocher.</p>
      </div>

      <div className="flex gap-2.5">
        <ChoiceCard on={kind === "known"} onClick={() => choose("known")} icon={<Users size={19} strokeWidth={2} />} title="Client existant" text="Dans l'ERP, sa fiche est chargée" />
        <ChoiceCard on={kind === "new"} onClick={() => choose("new")} icon={<UserPlus size={19} strokeWidth={2} />} title="Nouveau client" text="Pas encore dans l'ERP" />
      </div>

      {kind === "known" ? (
        <>
          <RoundField icon={<Search size={17} strokeWidth={2} />} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rechercher un nom, une ville, un numéro…" aria-label="Rechercher le client" />
          <ul className="-mx-1 max-h-[260px] overflow-y-auto" role="listbox" aria-label="Clients">
            {clients.isLoading ? <li className="flex items-center gap-2 px-3 py-3 text-[13px] text-[#667781]"><Spinner size={12} /> Chargement des clients…</li> : null}
            {!clients.isLoading && found.length === 0 ? <li className="px-3 py-3 text-[13px] text-[#667781] dark:text-[#8696a0]">Aucun client trouvé. Nouveau client ?</li> : null}
            {found.map((c) => {
              const on = c.id === clientId;
              const ph = (c.contacts ?? []).find((x) => x.phone)?.phone;
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={on}
                    onClick={() => pick(c.id)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-[12px] px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60",
                      on ? "bg-[#e7fbf4] dark:bg-[#0b3b31]" : "hover:bg-[#f5f6f6] dark:hover:bg-[#202c33]",
                    )}
                  >
                    <Avatar name={c.name} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2 truncate text-[14px] font-medium text-[#111b21] dark:text-[#e9edef]">
                        <span className="truncate">{c.name}</span>
                        {c.status === "blocked" ? <span className="shrink-0 rounded-full bg-[#ea0038]/10 px-2 py-[1px] text-[10.5px] font-semibold text-[#ea0038]">bloqué</span> : null}
                        {c.status === "prospect" ? <span className="shrink-0 rounded-full bg-[#f1a33a]/15 px-2 py-[1px] text-[10.5px] font-semibold text-[#b86e00] dark:text-[#f1a33a]">prospect</span> : null}
                      </span>
                      <span className="block truncate text-[12.5px] text-[#667781] dark:text-[#8696a0]">{[c.city, ph].filter(Boolean).join(" · ")}</span>
                    </span>
                    {on ? <Check size={20} strokeWidth={2.5} className="shrink-0 text-[#00a884]" /> : null}
                  </button>
                </li>
              );
            })}
          </ul>

          {selected && contacts.length > 0 ? (
            <div className="flex flex-col gap-2">
              <span className="text-[12px] font-medium uppercase tracking-[.06em] text-[#667781] dark:text-[#8696a0]">Au téléphone</span>
              <div className="flex flex-wrap gap-2">
                {contacts.map((x, i) => (
                  <button
                    key={`${x.name}-${i}`}
                    type="button"
                    aria-pressed={i === contactIdx}
                    onClick={() => { setContactIdx(i); setContactTitle(undefined); }}
                    title={[x.role, x.phone].filter(Boolean).join(" · ")}
                    className={cn("flex items-center gap-2 py-1 pl-1 pr-3", PILL, i === contactIdx ? PILL_ON : PILL_OFF)}
                  >
                    <Avatar name={x.name} size={24} />
                    {x.name}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {selected?.status === "blocked" ? (
            <p className="flex items-center gap-2 rounded-[12px] bg-[#ea0038]/10 px-3 py-2 text-[12.5px] text-[#ea0038]"><Dot tone="destructive" /> Compte bloqué : l'agent prend le message, sans rien promettre.</p>
          ) : null}
        </>
      ) : (
        <div className="flex flex-col gap-2.5">
          <RoundField icon={<Store size={17} strokeWidth={2} />} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Établissement (ex. Boulangerie du Canal)" aria-label="Établissement" />
          <RoundField icon={<User size={17} strokeWidth={2} />} value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom du contact (ex. Camille Durand)" aria-label="Nom du contact" />
          <RoundField icon={<Phone size={17} strokeWidth={2} />} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Téléphone (ex. 06 12 34 56 78)" aria-label="Téléphone" inputMode="tel" />
          <p className="px-1 text-[12px] text-[#667781] dark:text-[#8696a0]">L'agent prend la demande sans rien confirmer ; l'équipe valide le compte ensuite.</p>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <span className="text-[12px] font-medium uppercase tracking-[.06em] text-[#667781] dark:text-[#8696a0]">Civilité (pour la salutation)</span>
        <div className="flex flex-wrap gap-2">
          {([["neutral", "Aucune"], ["madame", "Madame"], ["monsieur", "Monsieur"]] as const).map(([v, label]) => {
            const on = (contactTitle ?? "neutral") === v;
            return (
              <button key={v} type="button" aria-pressed={on} onClick={() => setContactTitle(v === "neutral" ? undefined : v)} className={cn(PILL, on ? PILL_ON : PILL_OFF)}>
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <button
        type="submit"
        disabled={!canStart}
        className="flex h-12 items-center justify-center gap-2 rounded-full bg-[#00a884] text-[15px] font-semibold text-white shadow-md transition-all hover:bg-[#008f72] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
      >
        {pending ? <><Spinner size={14} /> Chargement de la fiche…</> : <><PhoneCall size={18} strokeWidth={2.2} /> Démarrer l'appel{kind === "known" && selected ? ` avec ${selected.name}` : ""}</>}
      </button>
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
          ? "· nouveau client (à valider par l'équipe)"
          : caller.usedByAgent
            ? `· fiche chargée${caller.loadedMs != null ? ` en ${caller.loadedMs} ms` : ""}`
            : "· identifié (fiche indisponible : l'agent cherchera le client)"}
      </span>
      <Button size="sm" variant="danger" icon={PhoneOff} className="ml-auto" onClick={onHangUp}>Raccrocher</Button>
    </div>
  );
}
