/** Global shell toggles (no context needed): ⌘K palette, ⌘J assistant panel, ⌘\ / ⌘B sidebar rail. */
import { useSyncExternalStore } from "react";

type State = { commandOpen: boolean; assistantOpen: boolean; sidebarCollapsed: boolean };
const KEY = "kit-assistant-open";
const SIDEBAR_KEY = "kit-sidebar-collapsed";
let state: State = {
  commandOpen: false,
  assistantOpen: (() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } })(),
  sidebarCollapsed: (() => { try { return localStorage.getItem(SIDEBAR_KEY) === "1"; } catch { return false; } })(),
};
const listeners = new Set<() => void>();

function set(patch: Partial<State>) {
  state = { ...state, ...patch };
  if (patch.assistantOpen !== undefined) { try { localStorage.setItem(KEY, patch.assistantOpen ? "1" : "0"); } catch { /* ignore */ } }
  if (patch.sidebarCollapsed !== undefined) { try { localStorage.setItem(SIDEBAR_KEY, patch.sidebarCollapsed ? "1" : "0"); } catch { /* ignore */ } }
  listeners.forEach((l) => l());
}

export const shell = {
  openCommand: () => set({ commandOpen: true }),
  closeCommand: () => set({ commandOpen: false }),
  toggleCommand: () => set({ commandOpen: !state.commandOpen }),
  openAssistant: () => set({ assistantOpen: true }),
  closeAssistant: () => set({ assistantOpen: false }),
  toggleAssistant: () => set({ assistantOpen: !state.assistantOpen }),
  toggleSidebar: () => set({ sidebarCollapsed: !state.sidebarCollapsed }),
};

export function useShell(): State {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => state);
}
