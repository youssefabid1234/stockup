/** Order source (canal) display, shared by the orders list and order detail. */
import { AudioLines, Globe, Mail, MessageCircle, PenLine, Phone, type LucideIcon } from "lucide-react";
import type { OrderSource } from "@kit/shared";
import { SOURCE_LABEL } from "@/lib/labels";
import { Badge } from "@/ui";

export const SOURCE_ICON: Record<OrderSource, LucideIcon> = {
  phone: Phone, voice_agent: AudioLines, email: Mail, whatsapp: MessageCircle, manual: PenLine, web: Globe,
};

export const SOURCE_OPTIONS = Object.entries(SOURCE_LABEL).map(([value, label]) => ({ value, label }));

/** Voice agent = violet badge with the waveform icon; other channels = muted icon + word. */
export function SourceLabel({ source }: { source: OrderSource }) {
  const Icon = SOURCE_ICON[source] ?? PenLine;
  if (source === "voice_agent") {
    return <Badge tone="violet"><Icon size={11} strokeWidth={2} />{SOURCE_LABEL[source]}</Badge>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <Icon size={13} strokeWidth={1.75} />{SOURCE_LABEL[source] ?? source}
    </span>
  );
}
