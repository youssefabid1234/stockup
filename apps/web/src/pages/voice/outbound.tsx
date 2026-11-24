import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, PhoneCall, PhoneOutgoing } from "lucide-react";
import type { OutboundAttempt } from "@kit/shared";
import { api } from "@/lib/api";
import { UNIT_LABEL } from "@/lib/format";
import { Button, DateLabel, Dot, Money, SECTION_LABEL } from "@/ui";

const STATUS: Record<OutboundAttempt["status"], string> = {
  ringing: "Sonnerie en cours",
  answered: "Appel décroché",
  missed: "Sans réponse",
  completed: "Appel terminé",
  cancelled: "Appel annulé",
};

export function OutboundCalls({
  ready, busy, pending, error, onAnswer,
}: {
  ready: boolean;
  busy: boolean;
  pending: boolean;
  error?: string;
  onAnswer: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const switchQuery = useQuery({
    queryKey: ["outbound-demo", "status"], queryFn: api.outboundDemo.status, retry: false, staleTime: Infinity,
  });
  const enabled = switchQuery.data?.enabled === true;
  const attempts = useQuery({
    queryKey: ["outbound-demo", "attempts"], queryFn: api.outboundDemo.attempts, enabled, refetchInterval: 800,
  });
  const candidates = useQuery({
    queryKey: ["outbound-demo", "candidates"], queryFn: api.outboundDemo.candidates, enabled, refetchInterval: 10000,
  });
  const start = useMutation({
    mutationFn: api.outboundDemo.start,
    onSuccess(attempt) {
      queryClient.setQueryData<OutboundAttempt[]>(["outbound-demo", "attempts"], (previous = []) => [
        attempt, ...previous.filter((a) => a.id !== attempt.id),
      ]);
      void queryClient.invalidateQueries({ queryKey: ["outbound-demo", "candidates"] });
    },
  });

  if (!enabled) return null;
  const latest = attempts.data?.[0];
  const ringing = latest?.status === "ringing";
  const active = ringing || latest?.status === "answered";
  const upcoming = candidates.data?.[0];
  const offer = active ? latest.offer : upcoming?.offer;

  return (
    <section className="shrink-0 space-y-3 border-b border-border px-4 py-3">
      <h2 className={SECTION_LABEL + " flex items-center gap-2"}><PhoneOutgoing size={14} /> Appels sortants simulés</h2>
      {offer ? (
        <div className="rounded-[4px] border border-violet/25 bg-violet/[.05] p-2.5">
          <div className="flex items-center gap-1.5 font-medium">
            {ringing ? <Dot tone="violet" pulse /> : null}
            {active ? latest.clientName : upcoming?.clientName}
          </div>
          <div className="mt-1 text-[12px]">{offer.productName}</div>
          <div className="mt-1 text-[11.5px] text-muted-foreground">
            {offer.kind === "promo" && offer.validUntil
              ? <>{offer.purchaseCount} achats récents · Promo jusqu’au <DateLabel date={offer.validUntil} /></>
              : "Nouveauté dans sa gamme habituelle"}
          </div>
          <div className="mt-1 text-[12px]"><Money value={offer.unitPrice} /> HT / {UNIT_LABEL[offer.unit] ?? offer.unit}</div>
        </div>
      ) : (
        <p className="text-[12px] text-muted-foreground">{candidates.isPending ? "Recherche des offres…" : candidates.isError ? "Offres indisponibles." : "Aucun client éligible pour une nouvelle offre."}</p>
      )}
      {ringing ? (
        <Button className="w-full" variant="primary" icon={PhoneCall} disabled={!ready || busy || pending}
          onClick={() => onAnswer(latest.id)}>{pending ? "Connexion…" : "Décrocher"}</Button>
      ) : (
        <Button className="w-full" icon={PhoneOutgoing} disabled={!ready || busy || active || !upcoming || start.isPending}
          onClick={() => start.mutate(crypto.randomUUID())}>{start.isPending ? "Lancement…" : "Lancer un appel"}</Button>
      )}
      {latest ? (
        <div aria-live="polite" className="space-y-2">
          <p className="text-[12px] text-muted-foreground">{STATUS[latest.status]} · {latest.clientName}</p>
          {latest.sms ? (
            <div className="rounded-[4px] border border-border bg-muted px-3 py-2 text-[12px]">
              <p className="mb-1 flex items-center gap-1.5 font-medium"><MessageSquare size={13} /> SMS simulé</p>
              <p className="leading-relaxed">{latest.sms}</p>
            </div>
          ) : null}
          {latest.reason ? <p className="text-[12px] text-muted-foreground">{latest.reason}</p> : null}
        </div>
      ) : null}
      {error ? <p role="alert" className="text-[12px] text-destructive">{error}</p> : null}
    </section>
  );
}
