"use client";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { useUiStore } from "@/stores/uiStore";
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
      <StatusBar />
      <Sidebar />
      <MainPane>{children}</MainPane>
      <RightPanel />
      <BottomBar />

      {/* Drawers render at shell level (outside CSS Grid) as fixed overlays.
          Rev3 H7 fix — render here, NOT inside page.tsx/MainPane. */}
      {activeDrawer && (
        <>
          <div className="drawer-backdrop" onClick={closeDrawer} data-testid="drawer-backdrop" />
          {activeDrawer === "memory" && <MemoryDrawer />}
          {activeDrawer === "settings" && <SettingsDrawer />}
        </>
      )}
    </div>
  );
}
