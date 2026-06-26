# Plan 82 — Frontend State + Shell Layout

**Tag**: `prompt-82` | **Depends on**: `prompt-81`

### Scope
Build all Zustand stores, data-fetching hooks, and the persistent dashboard shell (status bar, sidebar, main pane, right panel, bottom bar). Fix the broken frontend build. No operational panels yet — just the shell and navigation.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-81` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S1. Create Zustand stores

Create these stores (all new files):
- `src/stores/taskStore.ts` — tasks array, activeTask, add/update/set/clear actions
- `src/stores/workerStore.ts` — workers array, degradedRatio, setWorkers, setDegradedRatio, resetCircuit
- `src/stores/costStore.ts` — summary object, setSummary action
- `src/stores/approvalStore.ts` — pending array, setPending, respond, remove actions
- `src/stores/memoryStore.ts` — slots array, searchQuery, sortColumn, sortDirection, setSlots, setSearchQuery, setSort actions (Panel C1 — added)
- `src/stores/uiStore.ts` — activeView, activeDrawer, **setActiveView(view)** (Rev3 H3 fix — was missing), openDrawer(drawerName), closeDrawer() actions (Panel C8 — added)

**State transition rules** (Rev3 H9 fix — disambiguate Escape and drawer/view interaction):
- Opening a drawer preserves `activeView` (drawer overlays the view).
- Setting `activeView` does NOT close open drawers (user must explicitly close).
- Escape closes the drawer ONLY. It does NOT reset `activeView` to Home. Users expect Escape to close overlays, not navigate away from the current view.

**activeView enum** (Panel C8 — centralized, not raw strings):
```typescript
export const VIEWS = {
  HOME: "home",
  TASKS: "tasks",
  WORKERS: "workers",
  APPROVALS: "approvals",
  COSTS: "costs",
  TOOLS: "tools",
  HELP: "help",
} as const;

export const DRAWERS = {
  MEMORY: "memory",
  SETTINGS: "settings",
} as const;
```

Update existing:
- `src/stores/agentStore.ts` — keep phase/session/model/latency/isRunning. Do NOT add activeView (moved to uiStore).

### S2. Create data-fetching hooks

**usePolling.ts with visibility detection** (Panel S1):
```typescript
import { useEffect, useState, useCallback, useRef } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  options: { enabled?: boolean; onError?: (err: Error) => void } = {}
) {
  const { enabled = true, onError } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  const tick = useCallback(async () => {
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      onError?.(e);
    } finally {
      setIsLoading(false);
    }
  }, [fetcher, onError]);

  useEffect(() => {
    if (!enabled) return;

    const handleVisibility = () => {
      if (document.hidden) {
        clearInterval(intervalRef.current);
      } else {
        tick();
        intervalRef.current = setInterval(tick, intervalMs);
      }
    };

    tick();
    intervalRef.current = setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(intervalRef.current);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled, intervalMs, tick]);

  return { data, error, isLoading };
}
```

Create these polling hooks:
- `src/hooks/useStatusPolling.ts` — 2s interval, updates agentStore
- `src/hooks/useWorkersPolling.ts` — 5s interval, updates workerStore
- `src/hooks/useCostsPolling.ts` — 10s interval, updates costStore
- `src/hooks/useApprovalsPolling.ts` — 2s interval, updates approvalStore
- `src/hooks/useMemoryPolling.ts` — **10s interval** (Rev3 L1 fix — was unspecified; matches costs polling cadence), updates memoryStore (Panel C1 — added). **Note**: pagination deferred to Plan 89 if memory slots exceed 1000 (Rev3 L6 fix).

### S3. Create `src/hooks/useKeyboardShortcuts.ts`

**Broadened focus check** (Panel M3 — accepted):
```typescript
import { useEffect } from "react";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";

const VIEW_KEYS: Record<string, string> = {
  t: VIEWS.TASKS,
  w: VIEWS.WORKERS,
  a: VIEWS.APPROVALS,
  c: VIEWS.COSTS,
};

const DRAWER_KEYS: Record<string, string> = {
  m: DRAWERS.MEMORY,  // Rev4 other-concern fix — use constant, not raw string (consistent with L8 rationale)
};

function isShortcutAvailable(): boolean {
  const active = document.activeElement;
  if (!active) return true;
  const isInput =
    active.tagName === "INPUT" ||
    active.tagName === "TEXTAREA" ||
    active.isContentEditable ||
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
        // Rev3 H9 fix — Escape closes drawer ONLY if a drawer is open.
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
```

**Note**: Space shortcut is NOT implemented. It will be added in Plan 85 when xterm.js terminal is built. (Panel C4 — accepted, removed from Plan 82)

### S4. Update `src/app/globals.css`

Add missing tokens + CSS Grid shell styles:
```css
:root {
  /* existing tokens from Plan 80... */
  --color-accent-blue: #3b82f6;
  --color-surface-hover: #1f1f2e;
  --color-border-accent: rgba(245, 158, 11, 0.40);
  --color-text-inverse: #0c0c0f;
}

.jarvis-shell {
  display: grid;
  grid-template-rows: 48px 1fr 64px;
  grid-template-columns: 64px 1fr 320px;
  grid-template-areas:
    "status status status"
    "sidebar main right"
    "bottom bottom bottom";
  height: 100vh;
  overflow: hidden;
  background: var(--color-surface-base);
  color: var(--color-text-primary);
  font-family: var(--font-sans);
}

.status-bar { grid-area: status; }
.sidebar { grid-area: sidebar; }
.main-pane { grid-area: main; overflow: auto; }
.right-panel { grid-area: right; }
.bottom-bar { grid-area: bottom; }

/* Rev3 H7 fix — Drawer overlay styles. Drawers render at layout level (outside CSS Grid)
   with position: fixed so they overlay the full shell, not just MainPane. */
.drawer-overlay {
  position: fixed;
  top: 48px;
  right: 0;
  bottom: 64px;
  width: 480px;
  z-index: 50;
  background: var(--color-surface-elevated, #1a1a2e);
  border-left: 1px solid var(--color-border-default, #2a2a3e);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
  overflow-y: auto;
  transform: translateX(100%);
  transition: transform 200ms ease-out;
}
.drawer-overlay[data-open="true"] {
  transform: translateX(0);
}
.drawer-backdrop {
  position: fixed;
  top: 48px;
  left: 0;
  right: 0;
  bottom: 64px;
  background: rgba(0, 0, 0, 0.3);
  z-index: 40;
}
```

### S5. Update `src/app/layout.tsx` and create `src/components/shell/ShellClient.tsx`

**Rev3 H5 fix**: Next.js App Router layouts are Server Components by default. Calling `useKeyboardShortcuts()` (a hook) in `layout.tsx` directly would force adding `"use client"`, which strips the layout's ability to export `metadata` and breaks SSR.

**Solution**: Keep `layout.tsx` as a Server Component. Create a new client component `src/components/shell/ShellClient.tsx` with `"use client"` that:
1. Calls `useKeyboardShortcuts()`
2. Renders the CSS Grid shell (StatusBar, Sidebar, MainPane, RightPanel, BottomBar)
3. Renders drawer overlays (MemoryDrawer, SettingsDrawer) at the shell level — OUTSIDE the CSS Grid — so they overlay the full shell (Rev3 H7 fix)

**`layout.tsx` (Server Component — keep metadata export)**:
```tsx
import type { Metadata } from "next";
import { ShellClient } from "@/components/shell/ShellClient";
import "./globals.css";

export const metadata: Metadata = {
  title: "JArvis — Sovereign AI Operations",
  description: "Operational dashboard for Sovereign AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ShellClient>{children}</ShellClient>
      </body>
    </html>
  );
}
```

**`ShellClient.tsx` (Client Component)**:
```tsx
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
```

**Note**: Drawers are rendered here in `ShellClient`, NOT in `page.tsx` (Plan 83 S10 was updated to remove drawer rendering). The drawers use the `.drawer-overlay` CSS class added in S4.

### S6. Update `src/components/shell/StatusBar.tsx`

- Remove "(deferred)" labels from model picker and settings buttons
- Wire phase badge colors: idle→slate, planning→amber, acting→emerald, reflecting→violet
- Add `data-testid="status-bar"`
- Model picker button: opens modal (deferred to Plan 89 — button exists but shows tooltip "Coming in Plan 89")
- Settings gear: opens SettingsDrawer via `uiStore.openDrawer('settings')` (Rev3 L9 fix — Plan 83 S11 wires this; Plan 82 S6 no longer says "Coming in Plan 89")

### S7. Update `src/components/shell/Sidebar.tsx`

7 nav items + 2 drawer buttons (Rev3 H8 fix — was incorrectly labeled "9 nav items" in Rev2). The VIEWS enum defines exactly 7 entries: Home, Tasks, Workers, Approvals, Costs, Tools, Help. Memory and Settings are NOT nav items — they are drawer buttons that call `uiStore.openDrawer()` (Panel C8).

Each nav item sets `uiStore.setActiveView(view)` using the VIEWS constant (not raw string). Active indicator: amber left border 2px. Add `data-testid="sidebar"`.

**Drawer buttons**: Memory (icon: Database) and Settings (icon: Gear) appear below the nav items, separated by a divider. Each calls `uiStore.openDrawer(DRAWERS.MEMORY)` or `uiStore.openDrawer(DRAWERS.SETTINGS)`.

### S8. Create `src/components/shell/MainPane.tsx`

Renders `{children}` from layout. Does NOT switch on activeView — view routing is owned by `page.tsx`. MainPane is a simple container with `overflow: auto`.

### S9. Update `src/components/shell/RightPanel.tsx`

3 main tabs: Tool Inspector (existing), Timeline (deferred to Plan 89), Reasoning (deferred to Plan 89).
Tab switching via local state. Deferred tabs show placeholder content.

### S10. Create `src/components/shell/BottomBar.tsx`

Left side: ActivationGrid placeholder (canvas element, 32×16, colored cells). **Use `useEffect` with `cancelAnimationFrame` cleanup** (Panel M3/M10 — accepted).
Right side: Token counter placeholder.
Add `data-testid="bottom-bar"`.

### S11. Verify build

Run `cd src && npx tsc --noEmit && npm run build`.

### STOP condition
If `npx tsc --noEmit` reports errors in any store or hook, STOP and fix before proceeding.

### Files WILL create (11)
- `src/stores/taskStore.ts`
- `src/stores/workerStore.ts`
- `src/stores/costStore.ts`
- `src/stores/approvalStore.ts`
- `src/stores/memoryStore.ts` (NEW — Panel C1)
- `src/stores/uiStore.ts` (NEW — Panel C8)
- `src/hooks/usePolling.ts`
- `src/hooks/useStatusPolling.ts`
- `src/hooks/useWorkersPolling.ts`
- `src/hooks/useCostsPolling.ts`
- `src/hooks/useApprovalsPolling.ts`
- `src/hooks/useMemoryPolling.ts` (NEW — Panel C1)
- `src/hooks/useKeyboardShortcuts.ts`
- `src/components/shell/MainPane.tsx`

### Files WILL edit (7)
- `src/stores/agentStore.ts` (remove activeView — moved to uiStore)
- `src/app/layout.tsx` (CSS Grid shell)
- `src/app/globals.css` (add tokens + grid styles)
- `src/components/shell/StatusBar.tsx` (remove deferred labels)
- `src/components/shell/Sidebar.tsx` (7 nav items + drawer buttons)
- `src/components/shell/RightPanel.tsx` (3 tabs)
- `src/components/shell/BottomBar.tsx` (activation grid placeholder)

### Closing

Run `/jarvis-close`. Tag `prompt-82`. CHANGELOG entry for Plan 82. Update PLANS.md.

---
