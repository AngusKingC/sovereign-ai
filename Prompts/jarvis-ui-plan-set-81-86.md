# JArvis UI — Complete Plan Set (Plans 81–86)
## GLM Planning Document | 2026-06-26
## For Round Table Review

---

# PLAN 81 — 5-Plan Milestone Full Scan (Priority 1 — Mandatory)

**Tag**: `prompt-81` | **No sub-parts** | **Unchanged from PLANS.md**

## S0. Opening

S0.1. Run `/jarvis-open` — verifies prompt-80 tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full.
S0.3. No new AGENTS.md rules this prompt.

## S1. Full 6-tool checkpoint scan

Run all tools sequentially (OR3):
1. `pytest` — collect and run full suite. Expected: 1411 passed, 67 skipped. Tolerance: ±5.
2. `ruff check .` — Expected: 0 errors.
3. `mypy core/ system/` — Expected: 0 errors.
4. `bandit -r core/ system/ workers/ skills/ adapters/ memory/ cli/ web/ backend/ -f json` — Expected: ~3,384 low, 1 medium, 0 high.
5. `pip-audit` — Expected: 19 CVEs (stable, no actionable fixes).
6. `vulture --min-confidence 80 core/ system/ workers/ skills/ adapters/ memory/ cli/ web/ backend/` — Expected: 41 findings (all whitelisted).

## S2. Vitest baseline verification

Run `cd src && npm test` — first baseline capture for Vitest. Record test count.

## S3. Coverage verification

`pytest --cov --cov-report=term-missing` — Expected: ≥78% (83% baseline -5% tolerance).

## S4. Baseline reconciliation

Compare all counts against PLANS.md baselines. Update any deltas with reconciliation notes.

## S5. New test: `test_ui_backend.py` baseline

Verify existing 6 backend tests still pass. Record as baseline.

## Closing

Run `/jarvis-close`.

**Scope**: Scan-only — no file edits except PLANS.md, CHANGELOG.md, docs.

---

# PLAN 82 — JArvis UI Shell + Backend Integration

**Tag**: `prompt-82` | **7 sub-parts (82a–82g)** | **Shares one tag, one closing**

This is the primary UI build plan. It delivers the full three-panel dashboard shell, all backend API endpoints, all frontend stores/hooks, all core panels, and the complete test suite. Sub-parts are sequential phases within one plan — Devin completes 82a, then 82b, then 82c, etc., running `jarvis-verify` between each phase.

## S0. Opening

S0.1. Run `/jarvis-open` — verifies prompt-81 tag.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt.

---

## 82a — Critical Fix + Backend API + Environment

**Purpose**: Fix the broken app (missing `lib/api.ts`) and add all backend API endpoints.

### 82a.1. Create `src/lib/api.ts`

The app cannot compile without this file. Must export:
- Types: `AgentStatus`, `MemorySlot`, `ToolCallEvent`, `TimelineSegment`, `Subagent`, `CostSummary`, `CircuitStatusResponse`, `ApprovalRequest`, `SkillInfo`
- Functions: `login()`, `getStatus()`, `sseUrl(path)`
- `BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"`

`login()`: POST `/api/auth/login` → sets `sovereign_token` httponly cookie.
`getStatus()`: GET `/api/status` → returns `AgentStatus`.
`sseUrl(path)`: Returns direct backend URL (SSE doesn't work through Next.js rewrites — cookies don't forward).

### 82a.2. Update `src/next.config.ts`

Add rewrites to proxy REST API requests to backend:
```typescript
rewrites: () => [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }, { source: "/health", destination: "http://localhost:8000/health" }]
```

### 82a.3. Create `src/.env.local` and `src/.env.example`

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
SOVEREIGN_DEV_TOKEN=dev-token
```

### 82a.4. Add backend API endpoints to `backend/main.py`

Add these endpoints (all returning mocked data):

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/costs/summary` | GET | `{ dailySpend, dailyCap, monthlySpend, monthlyCap, modelBreakdown }` |
| `/api/costs/daily` | GET | `{ date, totalUsd, entries[] }` |
| `/api/circuit-breaker/status` | GET | `{ workers[], degradedRatio }` |
| `/api/circuit-breaker/reset` | POST | `{ status, worker_id }` |
| `/api/approvals/pending` | GET | `[{ id, type, description, risk, expiresAt }]` |
| `/api/approvals/{id}/respond` | POST | `{ status, id }` |
| `/api/memory/export` | GET | All 512 slots |
| `/api/skills` | GET | `[{ name, tier, enabled, methods }]` |

Verify: `python -c "import ast; ast.parse(open('backend/main.py').read())"` + `ruff check backend/main.py` + `mypy backend/main.py --ignore-missing-imports`

---

## 82b — Frontend State + Data Hooks

**Purpose**: Create all Zustand stores and data-fetching hooks. These are the foundation every panel component depends on.

### 82b.1. Create `src/stores/taskStore.ts`

State: `tasks: Task[]`, `activeTask: Task | null`
Actions: `addTask`, `updateTask(id, partial)`, `setActiveTask(task | null)`, `clearTasks`
Task type: `{ id, intent, workerId, status, confidence, costUsd, tokenCount, createdAt, completedAt }`

### 82b.2. Create `src/stores/workerStore.ts`

State: `workers: Worker[]`, `circuitStatus: Record<string, CircuitState>`
Actions: `setWorkers`, `setCircuitStatus`, `resetCircuit(workerId)`

### 82b.3. Create `src/stores/costStore.ts`

State: `dailySpend`, `dailyCap`, `monthlySpend`, `monthlyCap`, `modelBreakdown[]`
Actions: `setSummary(data)`

### 82b.4. Create `src/stores/approvalStore.ts`

State: `pending: ApprovalRequest[]`
Actions: `setPending`, `respond(id, approved)`, `remove(id)`

### 82b.5. Update `src/stores/agentStore.ts`

Add: `activeView: string` (default `"home"`), `setActiveView(view: string)`

### 82b.6. Create `src/hooks/usePolling.ts`

Generic: `usePolling<T>(url, intervalMs, { enabled?, parser? }) → { data, error, isLoading }`

### 82b.7. Create polling hooks

- `useStatusPolling.ts` — 2s, updates agentStore
- `useWorkersPolling.ts` — 5s, updates workerStore
- `useCostsPolling.ts` — 10s, updates costStore
- `useApprovalsPolling.ts` — 2s, updates approvalStore

### 82b.8. Create `src/hooks/useKeyboardShortcuts.ts`

Global keydown: Space (run/pause), M/T/W/A/C (view switches), Esc (home), Ctrl+K (deferred). Disabled when input/textarea focused. When `[data-terminal]` focused, shortcuts require Ctrl+ prefix.

Verify: `cd src && npx tsc --noEmit`

---

## 82c — Shell Layout + Status Bar + Sidebar + Bottom Bar

**Purpose**: Build the persistent dashboard shell. Every subsequent panel lives inside this shell.

### 82c.1. Update `src/app/globals.css`

Add missing tokens: `--color-accent-blue: #3b82f6`, `--color-surface-hover: #1f1f2e`, `--color-border-accent`, `--color-text-inverse`. Update `--font-mono` to include JetBrains Mono and Fira Code.

### 82c.2. Update `src/app/layout.tsx`

CSS Grid: `48px 1fr 64px` rows, `64px 1fr 320px` columns. Named areas: `"status status status"`, `"sidebar main right"`, `"bottom bottom bottom"`. Add `useKeyboardShortcuts()` call.

### 82c.3. Update `src/components/shell/StatusBar.tsx`

- Remove "(deferred)" labels from model picker and settings buttons
- Add `data-testid="status-bar"`
- Wire model picker to tooltip "Coming in Plan 83"
- Wire settings to tooltip "Coming in Plan 83"

### 82c.4. Update `src/components/shell/Sidebar.tsx`

9 nav items per spec §2: Home, Tasks, Workers, Approvals, Costs, Memory, Tools, Settings, Help. Each sets `agentStore.activeView`. Active indicator: amber left border 2px. Add `data-testid="sidebar"`.

### 82c.5. Create `src/components/panels/ActivationGrid.tsx`

Canvas 2D, 32×16 cells. Colors: 0–0.4 slate, 0.4–0.7 amber, 0.7–1.0 emerald. requestAnimationFrame decay loop (−0.015/frame). Click → tooltip. Add `data-testid="activation-grid"`.

### 82c.6. Update `src/components/shell/BottomBar.tsx`

Replace placeholder text with `<ActivationGrid />`. Add `data-testid="bottom-bar"`.

Verify: `cd src && npx tsc --noEmit && npm run build`

---

## 82d — Main Content + Right Panel

**Purpose**: Build the main pane (terminal + task stream) and the right panel tabs.

### 82d.1. Create `src/components/panels/MainPane.tsx`

Mode A (no active task): terminal placeholder with `[data-terminal]` attribute. Mode B (active task): `<TaskDetailCard />` + live output area.

### 82d.2. Create `src/components/panels/TaskDetailCard.tsx`

Display task fields: intent, workerId, status badge (colored per state), confidence, cost, tokens, timestamps. Status colors: EXECUTING→amber, VALIDATING→blue, COMPLETE→emerald, FAILED→red, CANCELLED→slate, QUEUED→violet.

### 82d.3. Update `src/components/shell/RightPanel.tsx`

3 main tabs: Tool Inspector (existing), Timeline, Reasoning. 3 expandable sub-tabs: Circuit Breaker, Cost Dashboard, Approval Queue.

### 82d.4. Create `src/components/panels/TimelinePanel.tsx`

SVG Gantt with phase segments from `/api/sessions/{id}/timeline`. Horizontal bars colored per phase.

### 82d.5. Create `src/components/panels/ReasoningPanel.tsx`

SSE from `/api/agent/reasoning`. Collapsible token blocks. Token count.

### 82d.6. Update `src/components/panels/ToolInspector.tsx`

Add `data-testid="tool-inspector"` to root div. Add `data-testid="tool-call-card"` to ToolCallCard root div.

### 82d.7. Update `src/app/page.tsx`

Wire all hooks (useStatusPolling, useWorkersPolling, useCostsPolling, useApprovalsPolling, useKeyboardShortcuts, 3 SSE hooks). Render view based on `agentStore.activeView`. Deferred views show "Coming in Plan 83" placeholder.

Verify: `cd src && npx tsc --noEmit && npm run build`

---

## 82e — Operational Dashboards

**Purpose**: Build the four operational panels — the core reason JArvis is an operations center, not a chatbot.

### 82e.1. Create `src/components/panels/CircuitBreakerPanel.tsx`

Per-worker rows: ID, state badge (CLOSED→emerald, OPEN→red, HALF_OPEN→amber), failure count/threshold. Reset button per worker → `POST /api/circuit-breaker/reset`. "Reset All" button. Degraded ratio display. Reads from `workerStore`.

### 82e.2. Create `src/components/panels/CostDashboardPanel.tsx`

Daily/monthly progress bars. Per-model breakdown (CSS width bars). Alert (80%) and fallback (90%) thresholds. Reads from `costStore`.

### 82e.3. Create `src/components/panels/ApprovalQueuePanel.tsx`

Pending requests list: type badge, description, risk level (low→emerald, medium→amber, high→red), expiry countdown. Approve/Deny buttons per request. "Always Approve" button (disabled — deferred to Plan 84). Reads from `approvalStore`.

### 82e.4. Create `src/components/panels/WorkersPanel.tsx`

Full-page worker registry (sidebar → Workers). Each worker card: ID, type, capabilities, circuit state, failure count, last used, task count. Register/deregister placeholder. Reads from `workerStore`.

### 82e.5. Create `src/components/panels/TasksPanel.tsx`

Full-page task list (sidebar → Tasks). Three sections: Active, Completed, Failed. Each task card: intent, worker, status, latency/cost. Cancel/Retry/View Output buttons. Reads from `taskStore`.

Verify: `cd src && npx tsc --noEmit && npm run build`

---

## 82f — Memory + Settings Drawers

**Purpose**: Build the slide-in drawers for memory inspection and system configuration.

### 82f.1. Create `src/components/panels/MemoryDrawer.tsx`

Slide-in from right (480px). Search bar, sortable table (index, key, value preview, last written), expandable rows. Export (GET /api/memory/export → JSON download) and Import (file picker → POST /api/memory/import).

### 82f.2. Create `src/components/panels/SettingsDrawer.tsx`

Slide-in from right (480px). 4 tabs: Cost Policy (daily cap, monthly cap, alert %, fallback %, fallback model), Circuit Breaker (failure threshold, reset timeout), Sandbox (policy toggle, memory, CPU, timeout), Auth (token display + regenerate). All fields write to backend via POST endpoints (mocked — real integration in Plan 84).

### 82f.3. Create HelpPanel placeholder

Static content: keyboard shortcuts table, link to docs.

Verify: `cd src && npx tsc --noEmit && npm run build`

---

## 82g — Test Suite

**Purpose**: Complete test coverage for everything built in 82a–82f.

### 82g.1. Python backend tests (7 new in `tests/test_ui_backend.py`)

- test_get_costs_summary, test_get_costs_daily
- test_get_circuit_breaker_status, test_post_circuit_breaker_reset
- test_get_approvals_pending, test_post_approvals_respond
- test_get_skills

### 82g.2. Vitest store tests (14 new in `src/__tests__/stores.test.ts`)

taskStore (4), workerStore (4), costStore (2), approvalStore (3), agentStore.activeView (1)

### 82g.3. Vitest component tests (6 new in `src/__tests__/components.test.tsx`)

TaskDetailCard, CircuitBreakerPanel, CostDashboardPanel, ApprovalQueuePanel, ActivationGrid, MainPane — each renders with mocked store data.

### 82g.4. Vitest hook tests (3 new in `src/__tests__/hooks.test.ts`)

usePolling (mock fetch), useStatusPolling (store update), useKeyboardShortcuts (key → view change)

### 82g.5. Update shell tests (5 new in `src/__tests__/shell.test.tsx`)

Sidebar 9 nav items, sidebar click routing, StatusBar phase badge, BottomBar canvas, RightPanel 3 tabs.

### 82g.6. Playwright E2E setup + tests (9 new)

Create `src/playwright.config.ts` with dual webServer (backend :8000 + frontend :3000). Add `@playwright/test` devDependency.

- `src/e2e/shell.spec.ts` (4): status bar renders, sidebar 9 items + click, sidebar hover expand (auto-waiting, no waitForTimeout), bottom bar canvas
- `src/e2e/sse.spec.ts` (3): tool call events stream (15s timeout), memory activations, SSE reconnect with real assertion
- `src/e2e/cors.spec.ts` (2): CORS allows localhost (page.evaluate + fetch), CORS rejects other origins

**Test count reconciliation**:

| Category | Count |
|----------|-------|
| Python backend | +7 |
| Vitest stores | +14 |
| Vitest components | +6 |
| Vitest hooks | +3 |
| Vitest shell | +5 |
| Playwright E2E | +9 |
| **Total new** | **44** |

## Closing

Run `/jarvis-close`. Single tag `prompt-82`. Single CHANGELOG entry. All sub-parts committed under one tag.

**Scope declaration — Files WILL create (27)**:
`src/lib/api.ts`, `src/.env.local`, `src/.env.example`, 4 stores, 1 store update, `usePolling.ts`, 4 polling hooks, `useKeyboardShortcuts.ts`, `ActivationGrid.tsx`, `MainPane.tsx`, `TaskDetailCard.tsx`, `TimelinePanel.tsx`, `ReasoningPanel.tsx`, `CircuitBreakerPanel.tsx`, `CostDashboardPanel.tsx`, `ApprovalQueuePanel.tsx`, `WorkersPanel.tsx`, `TasksPanel.tsx`, `MemoryDrawer.tsx`, `SettingsDrawer.tsx`, `components.test.tsx`, `hooks.test.ts`, `playwright.config.ts`, 3 e2e specs

**Files WILL edit (11)**:
`src/next.config.ts`, `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css`, `StatusBar.tsx`, `Sidebar.tsx`, `BottomBar.tsx`, `RightPanel.tsx`, `ToolInspector.tsx`, `agentStore.ts`, `backend/main.py`, `test_ui_backend.py`, `stores.test.ts`, `shell.test.tsx`

**Files will NOT edit**: `core/`, `cli/`, `web/server.py`, `adapters/`, `workers/`, `memory/`, `skills/`, `system/`, `gateways/`, `orchestrator/`

---

# PLAN 83 — PEMADS Phase 2 + Model/Skills UI

**Tag**: `prompt-83` | **5 sub-parts (83a–83e)**

Combines backend PEMADS Expert Panel Manager + VRAM hot-swap with frontend Model Picker + Command Palette + Skills Panel. These UI components display and control the expert panel system, so they should be built together.

## S0. Opening

S0.1. Run `/jarvis-open` — verifies prompt-82 tag.
S0.2. Read AGENTS.md in full.
S0.3. No new AGENTS.md rules this prompt.

---

## 83a — ExpertPanelManager (backend)

Create `core/expert_panel_manager.py`:
- `ExpertPanelManager` class: manages a pool of expert workers for PEMADS debates
- `create_panel(task_type: str, num_experts: int) -> Panel`: selects diverse architectures, creates worker pool
- `run_debate_round(panel: Panel, task: Task) -> DebateRound`: orchestrates one round of turn-based debate
- `get_panel_status(panel_id: str) -> PanelStatus`: returns current debate state
- Integrates with `WorkerCircuitBreaker` (Plan 78) and `ModelTierRouter` (Plan 79)
- Reads debate history from `DebatePool` (Plan 76)

## 83b — VRAM Hot-Swap (backend)

Add VRAM management to `system/resource_manager.py`:
- `VRAMManager` class: tracks VRAM usage per loaded model
- `swap_in(model_name: str) -> bool`: load model, evict least-recently-used if insufficient VRAM
- `swap_out(model_name: str) -> bool`: unload model, free VRAM
- `get_vram_status() -> VRAMStatus`: current usage, loaded models, available capacity
- Integrates with `ExpertPanelManager` — experts are swapped in/out between debate rounds

## 83c — Backend API endpoints for PEMADS + VRAM

Add to `backend/main.py` (mocked) or `web/server.py` (real):

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/panels` | GET | Active expert panels |
| `/api/panels/{id}` | GET | Panel detail + debate state |
| `/api/panels/{id}/debate` | POST | Start a debate round |
| `/api/vram/status` | GET | VRAM usage + loaded models |
| `/api/vram/swap` | POST | Swap model in/out |
| `/api/models` | GET | Model registry (downloaded + available) |
| `/api/models/{name}/load` | POST | Load model |
| `/api/models/{name}/unload` | POST | Unload model |

## 83d — Model Picker + Command Palette + Skills Panel (frontend)

**ModelPickerModal**: Fuzzy search through model registry (`/api/models`). Shows model name, provider, quantisation, download status, VRAM estimate. Load/Unload buttons. Replaces the "Coming in Plan 83" tooltip from Plan 82.

**CommandPalette** (`Ctrl+K`): Modal overlay with fuzzy search over all nav items, commands, and recent tasks. Replaces the "Coming soon" placeholder.

**SkillsPanel** (`src/components/panels/SkillsPanel.tsx`): Lists skills from `/api/skills` with tier badge (USER_INVOKED/AGENT_INVOKED/HYBRID), enabled toggle, methods list. "Run Test Battery" button for testing_battery skill.

## 83e — Tests

**Python** (8 new): ExpertPanelManager CRUD, VRAMManager swap in/out/status, panel API, VRAM API
**Vitest** (5 new): ModelPickerModal renders + fuzzy search, CommandPalette renders + nav, SkillsPanel renders
**Playwright** (2 new): Model picker opens from status bar, command palette opens with Ctrl+K

## Closing

Run `/jarvis-close`. Tag `prompt-83`.

---

# PLAN 84 — Multi-Channel Approval Gates + Approval Enhancements

**Tag**: `prompt-84` | **4 sub-parts (84a–84d)**

Combines backend multi-channel approval infrastructure with frontend approval panel enhancements. Approval UI needs real channels to approve through — build them together.

## S0. Opening

S0.1. Run `/jarvis-open` — verifies prompt-83 tag.
S0.2. Read AGENTS.md in full.
S0.3. No new AGENTS.md rules this prompt.

---

## 84a — Multi-channel approval infrastructure (backend)

Extend `core/approval_gate.py`:
- `ApprovalChannel` enum: `WEB_UI`, `TELEGRAM`, `EMAIL`
- `MultiChannelApprovalGate` class: routes approval requests to configured channels
- Each channel has a `send_request()` and `receive_response()` method
- `WebUIChannel`: uses SSE to push approval requests to frontend, receives POST responses
- `TelegramChannel`: sends via Telegram Bot API, receives via webhook
- `EmailChannel`: sends via SMTP, receives via IMAP polling
- Configuration: `ApprovalChannelConfig` with channel priority and routing rules

## 84b — Telegram + Email channel implementations

- `gateways/telegram/approval_bot.py`: Telegram bot that receives approval requests and sends inline keyboard buttons (Approve/Deny/Always)
- `gateways/email/approval_sender.py`: Email template + SMTP sender for approval requests
- `gateways/email/approval_poller.py`: IMAP poller that checks for approval replies

## 84c — Backend API for real approval data

Replace `backend/main.py` mocked approval endpoints with real `web/server.py` endpoints connected to `MultiChannelApprovalGate`:
- `GET /api/approvals/pending` → reads from `ApprovalGate._pending_requests`
- `POST /api/approvals/{id}/respond` → calls `ApprovalGate.respond()`
- `POST /api/approvals/{id}/always-approve` → adds to `ApprovalTrustRegistry`
- `GET /api/approvals/history` → returns recent approval decisions

## 84d — Frontend approval enhancements

- **Always Approve button**: Enabled. Calls `POST /api/approvals/{id}/always-approve`. Adds pattern to trust registry.
- **Batch actions**: "Approve All Low Risk" button for quick bulk approval.
- **Expiry countdown**: Live countdown timer per request (5-minute TTL).
- **Channel indicator**: Shows which channel the request was received on (Web/Telegram/Email).
- **Toast notifications**: Real SSE-driven notifications when new approval requests arrive.
- **ApprovalNotification badge**: Red badge count on sidebar approvals icon.

## 84e — Tests

**Python** (10 new): MultiChannelApprovalGate routing, WebUIChannel send/receive, TelegramChannel, EmailChannel, trust registry integration, real API endpoints
**Vitest** (4 new): Always Approve flow, batch actions, expiry countdown, channel indicator
**Playwright** (2 new): Approval flow end-to-end (submit → approve → agent continues), batch approve

## Closing

Run `/jarvis-close`. Tag `prompt-84`.

---

# PLAN 85 — PEMADS Phase 3 + Terminal + System Panels

**Tag**: `prompt-85` | **5 sub-parts (85a–85e)**

Combines backend PEMADS Judge + Implementation Gate with frontend terminal integration (xterm.js) and remaining monitoring panels. The judge needs a UI to display debate results and gate decisions — build them together.

## S0. Opening

S0.1. Run `/jarvis-open` — verifies prompt-84 tag.
S0.2. Read AGENTS.md in full.
S0.3. No new AGENTS.md rules this prompt.

---

## 85a — PEMADSJudge (backend)

Create `core/pemads_judge.py`:
- `PEMADSJudge` class: evaluates debate quality, decides whether to implement
- `judge_round(round: DebateRound) -> Judgment`: scores solutions, selects best, explains reasoning
- `implementation_gate(judgment: Judgment) -> GateDecision`: requires Plan 84 multi-channel approval for autonomous decisions
- Quality thresholds per `TaskType` (per CONTEXT.md): game 85%, ai_agent 90%, data_pipeline 80%, api_backend 88%, script 75%

## 85b — Implementation Gate (backend)

Create `core/implementation_gate.py`:
- `ImplementationGate` class: gates implementation on quality threshold + approval
- `evaluate(judgment: Judgment) -> GateResult`: returns PROCEED/ESCALATE/REJECT
- PROCEED: quality above threshold, auto-implement (if safe) or route to approval
- ESCALATE: quality near threshold, requires explicit approval via multi-channel gate
- REJECT: quality below threshold, request re-debate with adjusted parameters

## 85c — Backend API for judge + gate

Add to `web/server.py`:
- `GET /api/debates/{id}/judgment` → returns judgment for a debate
- `POST /api/debates/{id}/gate` → evaluate gate decision
- `GET /api/debates/{id}/rounds` → returns all debate rounds with scores

Add to `backend/main.py` (mocked):
- Same endpoints with simulated debate data

## 85d — Terminal WebSocket PTY + Remaining Panels (frontend)

**TerminalEmbed** (`src/components/panels/TerminalEmbed.tsx`):
- xterm.js integration with WebSocket `/api/pty`
- Custom theme matching JArvis color tokens
- `@xterm/addon-fit` on ResizeObserver
- `[data-terminal]` attribute for keyboard shortcut conflict detection
- Replaces the terminal placeholder from Plan 82d

**LogViewer** (`src/components/panels/LogViewer.tsx`):
- Color-coded log entries with level filtering (INFO/WARNING/ERROR)
- Auto-scroll with toggle
- Search bar with highlighted matches

**SystemStats** (`src/components/panels/SystemStats.tsx`):
- CPU/RAM/GPU gauges (mocked from `/api/system`)
- Uptime display
- Active worker count

**SubagentPanel** (`src/components/panels/SubagentPanel.tsx`):
- Subagent cards from `/api/subagents` polling (2s)
- Status: running/waiting/complete/failed
- Kill button per subagent
- Token cost display

## 85e — Tests

**Python** (8 new): PEMADSJudge scoring, gate decisions (PROCEED/ESCALATE/REJECT), quality thresholds per TaskType, API endpoints
**Vitest** (4 new): TerminalEmbed renders canvas, LogViewer filtering, SystemStats gauges, SubagentPanel
**Playwright** (3 new): Terminal WebSocket connects, log viewer filters, system stats render

## Closing

Run `/jarvis-close`. Tag `prompt-85`.

---

# PLAN 86 — PEMADS Phase 4 + CLI Improvements

**Tag**: `prompt-86` | **4 sub-parts (86a–86d)**

Combines backend pruned expert model generation with CLI TUI improvements. The CLI should show the same operational data (tasks, workers, costs, approvals) that the Web UI shows — just in a terminal format.

## S0. Opening

S0.1. Run `/jarvis-open` — verifies prompt-85 tag.
S0.2. Read AGENTS.md in full.
S0.3. No new AGENTS.md rules this prompt.

---

## 86a — PrunedExpertGenerator (backend)

Create `core/pruned_expert_generator.py`:
- `PrunedExpertGenerator` class: creates task-specialized models by pruning base models
- `generate_expert(task_type: str, debate_history: DebateRound) -> ExpertConfig`: produces pruning configuration
- `apply_pruning(base_model: str, config: ExpertConfig) -> str`: applies pruning, returns path to pruned model
- Integrates with `DebatePool` (Plan 76) for debate history data
- Integrates with `VRAMManager` (Plan 83) for model loading

## 86b — CLI TUI: Operational Dashboard Screens

Extend `cli/tui.py` with new Textual screens:

- **TaskListScreen**: Rich table of tasks (active/completed/failed) with status colors
- **WorkerScreen**: Worker registry table with circuit breaker status
- **CostScreen**: Cost gauges using Rich BarColumns (daily/monthly spend)
- **ApprovalScreen**: Pending approval requests with approve/deny keyboard shortcuts

Each screen reads from the same `Orchestrator` instance that the Web UI backend uses.

## 86c — CLI Rich CLI: New Slash Commands

Add to `cli/rich_cli.py` and `core/commands.py`:

- `/tasks` — list active tasks
- `/workers` — list registered workers with circuit status
- `/costs` — show daily/monthly spend
- `/approvals` — show pending approvals
- `/approve {id}` — approve an approval request
- `/deny {id}` — deny an approval request
- `/circuit-reset {worker}` — reset a worker's circuit breaker

## 86d — Tests

**Python** (8 new): PrunedExpertGenerator, CLI slash commands, TUI screens
**Vitest** (0 — no frontend changes)

## Closing

Run `/jarvis-close`. Tag `prompt-86`.

---

# PLAN infra-remediation — AR18 + AR1 + print() Fixes

**Named plan** — does not consume a prompt number. Tag: `infra-remediation`.

## 86a. Fix test_ar18_compliance.py

Current test passes while 264 violations exist. Root cause: regex only catches `except Exception:` immediately followed by `pass`, misses the common `except Exception:\n    # comment\n    pass` pattern. Fix the regex to catch all bare except patterns including comments and logging between except and pass.

## 86b. AR18 remediation

Fix all 264 bare `except Exception: pass` violations across 43 files. Add inline comments + WARNING trace per AR18. Top files: `skills/notes/notes_skill.py` (36), `skills/calendar/calendar_skill.py` (24), `skills/reminder/reminder_skill.py` (18).

## 86c. AR1 violations

Fix 2 violations: `core/worker_factory.py:38` and `core/resource_budget.py:23` — inline imports of `system/`. Refactor to use dependency injection or move the import to a function boundary.

## 86d. print() → logging

Replace 38 `print()` statements with proper `logging` calls. Top: `core/observability.py` (5).

## Closing

Run `/jarvis-close`. Tag `infra-remediation`.

---

# Updated PLANS.md Queue (Post-Restructure)

| Plan | Name | Type | Sub-Parts |
|------|------|------|-----------|
| 81 | 5-Plan Milestone Full Scan | Scan | None |
| 82 | JArvis UI Shell + Backend Integration | UI + Backend | 82a–82g (7) |
| 83 | PEMADS Phase 2 + Model/Skills UI | Feature + UI | 83a–83e (5) |
| 84 | Multi-Channel Approvals + Approval UI | Feature + UI | 84a–84e (5) |
| 85 | PEMADS Phase 3 + Terminal + System Panels | Feature + UI | 85a–85e (5) |
| 86 | PEMADS Phase 4 + CLI Improvements | Feature + CLI | 86a–86d (4) |
| infra-remediation | AR18 + AR1 + print() | Infrastructure | a–d (4) |

**Plans 87–90 (post-scan)**:
- **Plan 87**: 5-Plan Milestone Full Scan (mandatory, after Plan 86)
- **Plan 88**: PEMADS Phase 5 — Integration & Hardening
- **Plan 89**: [Open Slot]
- **Plan 90**: [Open Slot]
