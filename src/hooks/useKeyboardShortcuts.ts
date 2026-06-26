import { useEffect } from "react";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";

const VIEW_KEYS: Record<string, (typeof VIEWS)[keyof typeof VIEWS]> = {
  t: VIEWS.TASKS,
  w: VIEWS.WORKERS,
  a: VIEWS.APPROVALS,
  c: VIEWS.COSTS,
};

const DRAWER_KEYS: Record<string, (typeof DRAWERS)[keyof typeof DRAWERS]> = {
  m: DRAWERS.MEMORY,
};

function isShortcutAvailable(): boolean {
  const active = document.activeElement;
  if (!active) return true;
  const isInput =
    active.tagName === "INPUT" ||
    active.tagName === "TEXTAREA" ||
    (active as HTMLElement).isContentEditable ||
    active.getAttribute("role") === "textbox" ||
    active.getAttribute("contenteditable") === "true";
  const isXterm = active.closest("[data-terminal]") !== null;
  return !isInput && !isXterm;
}

export function useKeyboardShortcuts() {
  const setActiveView = useUiStore((s) => s.setActiveView);
  const openDrawer = useUiStore((s) => s.openDrawer);
  const closeDrawer = useUiStore((s) => s.closeDrawer);
  const activeDrawer = useUiStore((s) => s.activeDrawer);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // Escape closes drawer ONLY if a drawer is open.
        // It does NOT reset activeView to Home. Users expect Escape to close
        // overlays, not navigate away from the current view.
        if (activeDrawer) {
          closeDrawer();
        }
        return;
      }
      if (!isShortcutAvailable()) return;

      const key = e.key.toLowerCase();
      if (DRAWER_KEYS[key]) {
        e.preventDefault();
        openDrawer(DRAWER_KEYS[key]);
      } else if (VIEW_KEYS[key]) {
        e.preventDefault();
        setActiveView(VIEW_KEYS[key]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setActiveView, openDrawer, closeDrawer, activeDrawer]);
}
