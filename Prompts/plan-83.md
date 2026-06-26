# Plan 83 — Operational Panels + Drawers

**Tag**: `prompt-83` | **Depends on**: `prompt-82`

### Scope
Build all operational panels (Tasks, Workers, Approvals, Costs), the Memory Drawer, Settings Drawer, and remaining navigation views. This is the "meat" of the UI — everything that makes JArvis an operations center.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-82` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S1. Create `src/components/panels/TasksPanel.tsx`

Full-page task list (sidebar → Tasks). Three sections: Active, Completed, Failed.
Each task card: intent, worker, status badge (colored per state), latency/cost.
- Cancel button: calls cancel API (if exists) or shows "Coming in Plan 89" tooltip
- Retry button: **NOT rendered** — deferred to Plan 89 (Panel C5 — fixed, not deferred to test-only Plan 84)
- View Output button: **NOT rendered** — deferred to Plan 89
Reads from `taskStore`.

### S2. Create `src/components/panels/WorkersPanel.tsx`

Full-page worker registry (sidebar → Workers). Each worker card: ID, type, capabilities, circuit state badge (CLOSED→emerald, OPEN→red, HALF_OPEN→amber), failure count/threshold, last used, task count. Reset Circuit button → calls `resetCircuit()` API. Reads from `workerStore`.

### S3. Create `src/components/panels/ApprovalQueuePanel.tsx`

Full-page approval queue (sidebar → Approvals). Pending requests list: type badge, description, risk level (low→emerald, medium→amber, high→red), expiry countdown (5-minute TTL). Approve/Deny buttons → calls `respondApproval()` API.
- "Always Approve" button: **NOT rendered** — deferred to Plan 88 (Panel S2 — fixed, hidden not disabled)
Reads from `approvalStore`.

### S4. Create `src/components/panels/CostDashboardPanel.tsx`

Full-page cost dashboard (sidebar → Costs). Daily/monthly progress bars (CSS width based on spend/cap ratio). Per-model breakdown (bar chart via CSS). Alert (80%) and fallback (90%) threshold indicators. Reads from `costStore`.

### S5. Create `src/components/panels/MemoryDrawer.tsx`

Slide-in from right (480px). Overlay, not full page. Controlled by `uiStore.activeDrawer`.

**Rev4 H-B fix — MANDATORY root element attributes**: The drawer's root element MUST have `className="drawer-overlay"` and `data-open={true}` so the H7 CSS (position: fixed, z-index: 50, slide transform) attaches to the rendered markup. Without these attributes, the drawer renders as an ordinary block element and the overlay positioning silently fails.

```tsx
"use client";
import { useMemoryStore } from "@/stores/memoryStore";
// ... other imports

export function MemoryDrawer() {
  const slots = useMemoryStore((s) => s.slots);
  // ... other store hooks

  return (
    <div className="drawer-overlay" data-open={true} data-testid="memory-drawer">
      {/* search bar, sortable table, expandable rows, export/import buttons */}
    </div>
  );
}
```

- Search bar (filters by key/value)
- Sortable table: index, key, value preview, last written
- Expandable rows: full value, activation bar, clear slot button
- Export button → `GET /api/memory/slots/export` → JSON download
- Import button → file picker → `POST /api/memory/slots/import`
Reads from `memoryStore` + direct API calls.

### S6. Create `src/components/panels/SettingsDrawer.tsx`

Slide-in from right (480px). Controlled by `uiStore.activeDrawer`.

**Rev4 H-B fix — MANDATORY root element attributes**: The drawer's root element MUST have `className="drawer-overlay"` and `data-open={true}` so the H7 CSS attaches. Same pattern as MemoryDrawer (S5).

```tsx
"use client";
import { useUiStore, DRAWERS } from "@/stores/uiStore";
// ... other imports

export function SettingsDrawer() {
  return (
    <div className="drawer-overlay" data-open={true} data-testid="settings-drawer">
      {/* 4 tabs: Cost Policy, Circuit Breaker, Sandbox, Auth */}
    </div>
  );
}
```

4 tabs: Cost Policy, Circuit Breaker, Sandbox, Auth.
**All fields are visually distinct** (opacity: 0.5, `data-mocked` attribute) with "Coming in Plan 89" tooltip (Panel S1 — accepted). E2E tests in Plan 84 only verify tab switching, not field interaction.

### S7. Create `src/components/panels/SkillsPanel.tsx`

Full-page skill registry (sidebar → Tools). Lists skills from `/api/skills` with tier badge, enabled toggle, methods list. "Run Test Battery" button for testing_battery skill.

### S8. Create `src/components/panels/HelpPanel.tsx`

Static content: keyboard shortcuts table, link to docs.

### S9. Create `src/components/panels/TerminalPlaceholder.tsx`

Simple placeholder for terminal (xterm.js deferred to Plan 89):
```tsx
<div data-testid="terminal-placeholder" data-terminal>
  Terminal (xterm.js — Plan 89)
</div>
```

### S10. Update `src/app/page.tsx`

Wire all polling hooks and render view based on `uiStore.activeView`. Map each view to its panel component using the `VIEWS` constants (Rev3 L8 fix — do NOT use raw string literals like `"home"`; use `VIEWS.HOME` for type safety).

**Rev3 H7 fix**: Drawers (MemoryDrawer, SettingsDrawer) are NO LONGER rendered in `page.tsx`. They are rendered at the shell level in `ShellClient.tsx` (Plan 82 S5) so they overlay the full shell as fixed-position elements. `page.tsx` only renders the active view's panel.

```tsx
"use client";
import { useStatusPolling } from "@/hooks/useStatusPolling";
import { useWorkersPolling } from "@/hooks/useWorkersPolling";
import { useCostsPolling } from "@/hooks/useCostsPolling";
import { useApprovalsPolling } from "@/hooks/useApprovalsPolling";
import { useMemoryPolling } from "@/hooks/useMemoryPolling";
import { useUiStore, VIEWS } from "@/stores/uiStore";
import { TasksPanel } from "@/components/panels/TasksPanel";
import { WorkersPanel } from "@/components/panels/WorkersPanel";
import { ApprovalQueuePanel } from "@/components/panels/ApprovalQueuePanel";
import { CostDashboardPanel } from "@/components/panels/CostDashboardPanel";
import { SkillsPanel } from "@/components/panels/SkillsPanel";
import { HelpPanel } from "@/components/panels/HelpPanel";
import { TerminalPlaceholder } from "@/components/panels/TerminalPlaceholder";

export default function Home() {
  useStatusPolling();
  useWorkersPolling();
  useCostsPolling();
  useApprovalsPolling();
  useMemoryPolling();

  const activeView = useUiStore((s) => s.activeView);

  // Rev3 L8 fix — use VIEWS constants, not raw string literals.
  // Rev3 H7 fix — drawers are NOT rendered here; they render in ShellClient.tsx.
  switch (activeView) {
    case VIEWS.HOME:
      return <TerminalPlaceholder />;
    case VIEWS.TASKS:
      return <TasksPanel />;
    case VIEWS.WORKERS:
      return <WorkersPanel />;
    case VIEWS.APPROVALS:
      return <ApprovalQueuePanel />;
    case VIEWS.COSTS:
      return <CostDashboardPanel />;
    case VIEWS.TOOLS:
      return <SkillsPanel />;
    case VIEWS.HELP:
      return <HelpPanel />;
    default:
      return <TerminalPlaceholder />;
  }
}
```

### S11. Update `src/components/shell/StatusBar.tsx`

Wire model picker button and settings gear. Model picker button opens a simple tooltip/modal saying "Model picker — Plan 89" (deferred). Settings gear opens `SettingsDrawer` via `uiStore.openDrawer(DRAWERS.SETTINGS)` (Rev3 L9 fix — was previously marked "Coming in Plan 89" in Plan 82 S6, but Plan 83 creates the drawer so the gear is now wired).

### S12. Verify build

Run `cd src && npx tsc --noEmit && npm run build`.

### STOP condition
If any panel throws a TypeScript error due to missing store methods or API types, STOP and fix.

### Files WILL create (10)
- `src/components/panels/TasksPanel.tsx`
- `src/components/panels/WorkersPanel.tsx`
- `src/components/panels/ApprovalQueuePanel.tsx`
- `src/components/panels/CostDashboardPanel.tsx`
- `src/components/panels/MemoryDrawer.tsx`
- `src/components/panels/SettingsDrawer.tsx`
- `src/components/panels/SkillsPanel.tsx`
- `src/components/panels/HelpPanel.tsx`
- `src/components/panels/TerminalPlaceholder.tsx`

### Files WILL edit (3)
- `src/app/page.tsx` (wire hooks + view routing using VIEWS constants — Rev3 L8 fix; drawers removed per H7)
- `src/components/shell/StatusBar.tsx` (wire settings gear to open SettingsDrawer — Rev3 L9 fix)
- `src/components/shell/Sidebar.tsx` (already updated in Plan 82 S7 — verify drawer buttons call openDrawer)

### Closing

Run `/jarvis-close`. Tag `prompt-83`. CHANGELOG entry for Plan 83. Update PLANS.md.

---
