import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { useActivityStream } from "@/lib/queries";
import { cn } from "@/lib/cn";
import { CommandK, PageHeaderSlot, ResizeHandle, Toaster, useResizableWidth } from "@/ui";
import { AssistantPanel } from "@/features/assistant/AssistantPanel";
import { VoiceCommandButton, VoiceCommandProvider } from "@/features/voice-command";
import { AssistantButton } from "./AssistantButton";
import { Sidebar } from "./Sidebar";
import { shell, useShell } from "./shell-state";

/**
 * Sidebar 232px (resizable, ⌘\ / ⌘B → 56px rail) | page (Outlet) | Assistant 400px (⌘J, resizable 320–720, pushes
 * content; width + opacity animate 200ms ease-out). Mounts SSE, ⌘K and toasts once.
 * The Assistant toggle sits top-right on every route: inside each PageHeader (via PageHeaderSlot), or — when the
 * current route renders no PageHeader — in a shell-owned slot at the top-right of <main>.
 */
/** Global top-right tools, grouped: hold-to-talk voice command (⌥Space) + Assistant toggle (⌘J). */
function ShellHeaderTools() {
  return (
    <div className="flex shrink-0 items-center gap-1" data-shell-tools>
      <VoiceCommandButton />
      <AssistantButton />
    </div>
  );
}

export function AppShell() {
  useActivityStream();
  const { assistantOpen } = useShell();
  const assistant = useResizableWidth("assistant", 400, 320, 720);
  // Keep the panel mounted while it animates closed (unmounting resets chat focus/scroll, chat state lives in its store).
  const [assistantMounted, setAssistantMounted] = useState(assistantOpen);
  const [assistantShown, setAssistantShown] = useState(assistantOpen);
  useEffect(() => {
    if (assistantOpen) {
      setAssistantMounted(true);
      // Mount at 0 width, let one frame paint it, then grow (a single rAF fires before that first paint).
      let raf = requestAnimationFrame(() => { raf = requestAnimationFrame(() => setAssistantShown(true)); });
      return () => cancelAnimationFrame(raf);
    }
    setAssistantShown(false);
    const t = window.setTimeout(() => setAssistantMounted(false), 220);
    return () => window.clearTimeout(t);
  }, [assistantOpen]);
  const [headers, setHeaders] = useState(0);
  const registerHeader = useCallback(() => {
    setHeaders((n) => n + 1);
    return () => setHeaders((n) => n - 1);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "j") { e.preventDefault(); shell.toggleAssistant(); }
      else if (k === "\\" || k === "b") { e.preventDefault(); shell.toggleSidebar(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="flex h-full min-w-[1024px] overflow-hidden bg-background">
      <Sidebar />
      <main className="relative min-w-0 flex-1 overflow-hidden">
        <PageHeaderSlot trailing={<ShellHeaderTools />} register={registerHeader}>
          <Outlet />
        </PageHeaderSlot>
        {headers === 0 ? (
          <div className="absolute right-5 top-0 z-30 flex h-12 items-center">
            <ShellHeaderTools />
          </div>
        ) : null}
      </main>
      {assistantMounted ? (
        <div
          data-assistant-panel={assistantShown ? "open" : "closed"}
          style={{ width: assistantShown ? assistant.width : 0 }}
          className={cn(
            "relative h-full shrink-0 overflow-hidden",
            !assistant.dragging && "transition-[width,opacity] duration-200 ease-out motion-reduce:transition-none",
            assistantShown ? "opacity-100" : "opacity-0",
          )}
        >
          {/* Fixed inner width: the chat never reflows while the column animates. Pinned right so it slides in. */}
          <aside style={{ width: assistant.width }} className="absolute inset-y-0 right-0 border-l border-border bg-card">
            <AssistantPanel />
            <ResizeHandle r={assistant} edge="left" label="Redimensionner l'assistant" />
          </aside>
        </div>
      ) : null}
      <CommandK />
      <Toaster />
      <VoiceCommandProvider />
    </div>
  );
}
