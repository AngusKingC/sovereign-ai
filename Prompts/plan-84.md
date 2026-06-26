# Plan 84 — Test Suite + Playwright E2E

**Tag**: `prompt-84` | **Depends on**: `prompt-83`

### Scope
Complete test coverage for everything built in Plans 81–83. Vitest unit tests for stores, hooks, components, shell. Playwright E2E tests for shell navigation, SSE streams, and CORS. This plan is test-only — no new features.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-83` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S1. Vitest store tests (18 tests in `src/__tests__/stores.test.ts`) (Rev4 L-A fix — was 16, arithmetic error)

Add to existing file:
- taskStore: adds a task, updates by id, sets active task, clears all tasks (4)
- workerStore: sets workers, sets degraded ratio, resets circuit for worker, preserves other workers on reset (4)
- costStore: sets summary, handles null summary (2)
- approvalStore: sets pending requests, removes responded request, removes by id (3)
- memoryStore: sets slots, filters by search query (2) (Panel C1 — added)
- uiStore: sets active view, opens drawer, closes drawer (3) (Panel C8 — added)

**Total**: 4+4+2+3+2+3 = **18 tests** (Rev4 L-A fix — was incorrectly stated as 16 in Rev3)

### S2. Vitest hook tests (7 tests in `src/__tests__/hooks.test.ts`)

New file:
- usePolling: returns data after fetch, returns error on failed fetch, pauses when tab hidden (3)
- useStatusPolling: updates agent store on data (1)
- useKeyboardShortcuts: changes view on key press, opens drawer on key press (2)
- useMemoryPolling: updates memory store on data (1) (Panel C1 — added)

### S3. Vitest component tests (6 tests in `src/__tests__/components.test.tsx`)

New file:
- TasksPanel: renders active tasks section (1)
- WorkersPanel: renders worker cards with circuit status (1)
- ApprovalQueuePanel: renders pending approvals (1)
- CostDashboardPanel: renders daily progress bar (1)
- MemoryDrawer: renders slot table (1)
- SettingsDrawer: renders 4 tabs (1)

### S4. Vitest shell tests (5 tests in `src/__tests__/shell.test.tsx`)

Add to existing file:
- Sidebar: renders 7 nav items + 2 drawer buttons (1)
- Sidebar: sets active view on click (1)
- StatusBar: renders phase badge (1)
- BottomBar: renders activation grid canvas (1)
- RightPanel: renders 3 tabs (1)

### S5. Playwright E2E setup

**Rev3 H1 fix**: The Rev2 `sh -c` webServer command is POSIX-only and fails on Windows PowerShell (Devin's environment). Replace with a cross-platform Node.js bootstrap script using `concurrently`.

**Step 1**: Add `concurrently` to `src/package.json` devDependencies:
```json
{
  "devDependencies": {
    "concurrently": "^9.0.0",
    "@playwright/test": "^1.40.0"
  }
}
```

**Step 2**: Add npm script to `src/package.json`:
```json
{
  "scripts": {
    "e2e:serve": "concurrently -k -n backend,frontend \"cd .. && python -m sovereign_ai.web.server\" \"next dev\""
  }
}
```
`concurrently -k` kills all processes when one exits, working identically on Windows/Linux/macOS.

**Step 3**: Create `src/playwright.config.ts`:
```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    // Rev3 H1 fix — cross-platform via concurrently (was POSIX-only sh -c).
    command: "npm run e2e:serve",
    url: "http://localhost:3000",
    timeout: 120000,
    reuseExistingServer: !process.env.CI,
  },
});
```

**Note**: Only Chromium for SSE tests (Panel O2 from Panel 4 — accepted). WebKit/Firefox SSE reconnect behavior varies.

Add `@playwright/test` to devDependencies in `src/package.json`.

### S6. Playwright E2E tests (8 tests)

**`src/e2e/shell.spec.ts`** (4 tests):
- status bar renders
- sidebar has 7 nav items + 2 drawer buttons
- sidebar click changes view
- bottom bar has activation grid

**`src/e2e/sse.spec.ts`** (2 tests — Panel C4 — reduced from 3):
- tool call events stream via SSE (verify connection opens)
- memory activations SSE connects (verify connection opens)
- **REMOVED**: SSE reconnect test — deferred to Plan 89 when SSE hook is implemented

**`src/e2e/cors.spec.ts`** (2 tests):
- proxy path works: request to :3000/api/status returns data (Panel S8 — fixed)
- backend CORS allows localhost origin (direct :8000 test)

### S7. Test count reconciliation (Rev4 L-A fix — corrected arithmetic)

| Category | New | Existing | Total |
|----------|-----|----------|-------|
| Python backend (Plan 81) | 9 | 6 | 15 |
| Vitest stores | 18 | — | 18 |
| Vitest hooks | 7 | — | 7 |
| Vitest components | 6 | — | 6 |
| Vitest shell | 5 | — | 5 |
| Playwright E2E | 8 | — | 8 |
| **Total** | **53** | **6** | **59** |

### S8. Run full test suite

1. `pytest tests/test_ui_backend.py -v` — all 15 tests pass
2. `cd src && npm test` — all 36 Vitest tests pass (Rev4 L-A fix — was 34; corrected: 18+7+6+5=36)
3. `cd src && npx playwright test` — all 8 E2E tests pass
4. `ruff check .` — 0 errors
5. `mypy core/ system/` — 0 errors
6. `cd src && npx tsc --noEmit` — 0 errors
7. Coverage ≥78% (83% baseline -5% tolerance)

### STOP condition
If any test fails and the failure is not a trivial fixture issue, STOP and report. Do not suppress test failures.

### Files WILL create
- `src/__tests__/hooks.test.ts`
- `src/__tests__/components.test.tsx`
- `src/e2e/shell.spec.ts`
- `src/e2e/sse.spec.ts`
- `src/e2e/cors.spec.ts`
- `src/playwright.config.ts`

### Files WILL edit
- `src/__tests__/stores.test.ts` (add new tests)
- `src/__tests__/shell.test.tsx` (add new tests)
- `src/package.json` (add @playwright/test + concurrently devDependencies, add e2e:serve script — Rev3 H1 fix)

### Closing

Run `/jarvis-close`. Tag `prompt-84`. CHANGELOG entry for Plan 84. Update PLANS.md with new baselines (Vitest + Playwright first baselines) and queue shift.

---
