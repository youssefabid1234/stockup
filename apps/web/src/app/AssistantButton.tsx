import { Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import { buttonClass, Kbd } from "@/ui";
import { shell, useShell } from "./shell-state";

/**
 * Top-right Assistant toggle, rendered at the far right of every PageHeader (via PageHeaderSlot in AppShell),
 * or by the shell itself on a route without a PageHeader. Same state as ⌘J and the sidebar entry.
 * Closed: ghost "✦ Assistant ⌘J". Open: pressed look, icon-only (the panel header already names it) to free header room.
 */
export function AssistantButton({ className }: { className?: string }) {
  const { assistantOpen } = useShell();
  return (
    <button
      type="button"
      onClick={shell.toggleAssistant}
      aria-pressed={assistantOpen}
      aria-label={assistantOpen ? "Fermer l'assistant (⌘J)" : "Ouvrir l'assistant (⌘J)"}
      title={assistantOpen ? "Fermer l'assistant (⌘J)" : "Ouvrir l'assistant (⌘J)"}
      data-assistant-toggle
      className={cn(
        buttonClass({ variant: "ghost", size: "sm", iconOnly: assistantOpen }),
        !assistantOpen && "px-2 text-secondary-foreground",
        assistantOpen && "border-border-hover bg-row-selected text-foreground shadow-[inset_0_1px_1px_rgb(0_0_0/0.06)] hover:bg-row-selected",
        className,
      )}
    >
      <Sparkles size={13} strokeWidth={1.75} className="shrink-0 text-violet" aria-hidden />
      {assistantOpen ? null : (
        <>
          <span className="shell-label">Assistant</span>
          <Kbd className="shell-kbd ml-0.5">⌘J</Kbd>
        </>
      )}
    </button>
  );
}
