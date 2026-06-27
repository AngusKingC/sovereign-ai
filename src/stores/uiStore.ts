import { create } from "zustand";

export const VIEWS = {
  HOME: "home",
  TASKS: "tasks",
  WORKERS: "workers",
  APPROVALS: "approvals",
  COSTS: "costs",
  TOOLS: "tools",
  HELP: "help",
  TERMINAL: "terminal",
  SYSTEM: "system",
  SUBAGENTS: "subagents",
  MODELS: "models",
  RESOURCES: "resources",
} as const;

export const DRAWERS = {
  MEMORY: "memory",
  SETTINGS: "settings",
} as const;

export type View = (typeof VIEWS)[keyof typeof VIEWS];
export type Drawer = (typeof DRAWERS)[keyof typeof DRAWERS];

interface UiState {
  activeView: View;
  activeDrawer: Drawer | null;
  setActiveView: (view: View) => void;
  openDrawer: (drawer: Drawer) => void;
  closeDrawer: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  activeView: VIEWS.HOME,
  activeDrawer: null,
  setActiveView: (activeView) => set({ activeView }),
  openDrawer: (activeDrawer) => set({ activeDrawer }),
  closeDrawer: () => set({ activeDrawer: null }),
}));
