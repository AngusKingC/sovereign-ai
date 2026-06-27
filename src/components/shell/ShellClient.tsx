"use client";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { useUiStore } from "@/stores/uiStore";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { StatusBar } from "./StatusBar";
import { Sidebar } from "./Sidebar";
import { MainPane } from "./MainPane";
import { RightPanel } from "./RightPanel";
import { BottomBar } from "./BottomBar";
import { MemoryDrawer } from "@/components/panels/MemoryDrawer";
import { SettingsDrawer } from "@/components/panels/SettingsDrawer";

export function ShellClient({ children }: { children: React.ReactNode }) {
  useKeyboardShortcuts();
  const activeDrawer = useUiStore((s) => s.activeDrawer);
  const closeDrawer = useUiStore((s) => s.closeDrawer);

  return (
    <div className="jarvis-shell" data-testid="jarvis-shell">
      <ErrorBoundary componentName="StatusBar"><StatusBar /></ErrorBoundary>
      <ErrorBoundary componentName="Sidebar"><Sidebar /></ErrorBoundary>
      <MainPane>{children}</MainPane>
      <ErrorBoundary componentName="RightPanel"><RightPanel /></ErrorBoundary>
      <ErrorBoundary componentName="BottomBar"><BottomBar /></ErrorBoundary>

      {/* Drawers render at shell level (outside CSS Grid) as fixed overlays.
          Rev3 H7 fix — render here, NOT inside page.tsx/MainPane. */}
      {activeDrawer && (
        <>
          <div className="drawer-backdrop" onClick={closeDrawer} data-testid="drawer-backdrop" />
          {activeDrawer === "memory" && <ErrorBoundary componentName="MemoryDrawer"><MemoryDrawer /></ErrorBoundary>}
          {activeDrawer === "settings" && <ErrorBoundary componentName="SettingsDrawer"><SettingsDrawer /></ErrorBoundary>}
        </>
      )}
    </div>
  );
}
