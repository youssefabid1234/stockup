/** Who did it: user / ai_chat / voice_agent / system. Voice & AI are tinted violet everywhere. */
import { AudioLines, Cpu, Sparkles, User, type LucideIcon } from "lucide-react";
import type { Actor } from "@kit/shared";
import { cn } from "@/lib/cn";
import { ACTOR_LABEL } from "@/lib/labels";

export const ACTOR_ICON: Record<Actor, LucideIcon> = { user: User, ai_chat: Sparkles, voice_agent: AudioLines, system: Cpu };
export const isAiActor = (a: Actor) => a === "ai_chat" || a === "voice_agent";

/** 24px round icon chip for an actor: <ActorIcon actor="voice_agent" /> */
export function ActorIcon({ actor, size = 24, className }: { actor: Actor; size?: number; className?: string }) {
  const Icon = ACTOR_ICON[actor] ?? User;
  const ai = isAiActor(actor);
  return (
    <span
      title={ACTOR_LABEL[actor]}
      style={{ width: size, height: size }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border",
        ai ? "border-violet/30 bg-violet/10 text-violet" : "border-border bg-muted text-muted-foreground",
        className,
      )}
    >
      <Icon size={Math.round(size * 0.52)} strokeWidth={1.75} />
    </span>
  );
}
