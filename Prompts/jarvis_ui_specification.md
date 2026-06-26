
# JArvis UI Specification Document
## Derived from Hermes Agent Dashboard Analysis | Mapped to Sovereign AI Codebase
## Version 1.0 | 2026-06-26 | For GLM Development Team

---

# PART 1: HERMES AGENT UI ANALYSIS

## 1.1 Overall Layout and Structure

Hermes Agent uses a **three-panel dashboard layout** with a persistent sidebar navigation system.

### Primary Layout Grid
```
┌─────────────────────────────────────────────────────────────────┐
│  [No top status bar — Hermes uses inline headers]              │
├──────────┬──────────────────────────────┬─────────────────────┤
│          │                              │                     │
│ Sidebar  │  Main Content Area           │  Right Panel        │
│ (64px    │  (flexible, primary)         │  (contextual,       │
│  icon-   │                              │   collapsible)      │
│  only)   │                              │                     │
│          │                              │                     │
│ [🏠]     │  Chat / Sessions / Logs /    │  File browser /     │
│ [💬]     │  Config / Skills / etc.        │  Session list /     │
│ [⚙]      │                              │  Tool details       │
│ [?]      │                              │                     │
│          │                              │                     │
├──────────┴──────────────────────────────┴─────────────────────┤
│  [No persistent bottom bar — content flows to footer]        │
└─────────────────────────────────────────────────────────────────┘
```

**Key structural observations:**
- **No global status bar** at the top. Status information (model, phase) is context-dependent and appears within each view's header.
- **Icon-only sidebar** (64px) with hover expansion to show labels. Active item indicated by left border accent.
- **Right panel is contextual** — it changes based on the main view. In Chat, it shows the session list. In Sessions, it shows session details. In Config, it may not appear at all.
- **Main content area is single-pane** — no split views within the main area. Each page is a full replacement.

### Page Architecture
Hermes has **dedicated pages** (not panels within a shell):
- `/chat` — Chat interface with embedded TUI
- `/sessions` — Session browser with search and stats
- `/logs` — Log viewer with filtering
- `/profiles` — Profile management cards
- `/skills` — Skill browser and hub
- `/mcp` — MCP server management
- `/config` — Configuration editor
- `/cron` — Cron job scheduler
- `/pairing` — Messaging user onboarding
- `/channels` — Messaging platform connections
- `/system` — System status and operations

Each page has its own URL, own header, own right-panel content (if any). This is **page-based navigation**, not a single-page dashboard with persistent panels.

### Profile Switcher
A critical Hermes pattern: the sidebar contains a **profile switcher** (dropdown or button) that changes the active profile. When switched:
- URL updates to `?profile=<name>`
- All management pages (Config, Skills, MCP) now show that profile's data
- Chat spawns a new PTY with that profile's `HERMES_HOME`
- An **amber banner** appears naming the managed profile to prevent ambiguity

---

## 1.2 Key UI Components

### Component Hierarchy (observed)

**Layout Components:**
- `Sidebar` — Fixed left, icon-only, hover-expand
- `MainContent` — Flexible center, scrollable
- `RightPanel` — Collapsible right rail, context-dependent
- `PageHeader` — Each page has its own header with title + actions

**Navigation Components:**
- `NavItem` — Icon + label (label hidden when sidebar collapsed)
- `ProfileSwitcher` — Dropdown in sidebar, shows active profile name
- `Breadcrumb` — Some pages use breadcrumbs for nested navigation

**Data Display Components:**
- `Card` — Profile cards, skill cards, MCP server cards
- `Table` — Sessions list, cron jobs, pairing users
- `ExpandableRow` — Session rows that expand to show message history
- `LogLine` — Color-coded log entries with filtering
- `StatBar` — Summary statistics (total sessions, active count, etc.)
- `Timeline` — Not explicitly observed, but session history implies chronological display

**Form Components:**
- `ConfigField` — Dynamically rendered based on schema type (text, number, select, toggle)
- `Toggle` — Enable/disable skills, MCP servers, channels
- `CodeEditor` — Config YAML editor, MCP command editor
- `SearchInput` — Full-text search with highlighted results

**Feedback Components:**
- `Toast` — Cron completion alerts, background errors
- `Badge` — Live session indicator (pulsing), update available
- `Modal` — Confirmation dialogs, form overlays
- `LoadingSpinner` — Inline loading for async operations

**Chat-Specific Components:**
- `TerminalEmbed` — xterm.js canvas filling the main area
- `Composer` — Message input at bottom of chat
- `MessageBubble` — User/assistant/system/tool messages
- `ToolCallCard` — Collapsible function call display with JSON args
- `SessionRail` — Right-side session list in chat view
- `ModelPicker` — Fuzzy search dropdown for model selection

---

## 1.3 Visual Design Patterns

### Color Scheme
Hermes uses a **dark theme with electric blue accent** (`#0000f2`).

Observed palette:
- **Background**: Deep charcoal (`#0a0a0f` to `#111118`)
- **Surface**: Slightly lighter charcoal for cards/panels (`#1a1a24`)
- **Border**: Subtle hairlines (`rgba(255,255,255,0.08)`)
- **Primary accent**: Electric blue (`#0000f2`) — buttons, active states, links
- **Success**: Green (`#22c55e`) — online status, success messages
- **Warning**: Amber (`#f59e0b`) — pending states, alerts
- **Error**: Red (`#ef4444`) — failures, errors
- **Text primary**: Off-white (`#e8e8e8`)
- **Text secondary**: Muted gray (`#9ca3af`)
- **Text muted**: Dark gray (`#6b7280`)

### Typography
- **Body**: System sans-serif stack (`system-ui, -apple-system, sans-serif`)
- **Monospace**: Used for code blocks, tool args, log lines, terminal output
- **Size hierarchy**: Page title (large), Section header (medium), Body (base), Caption/Metadata (small)
- **Weight**: Regular (400) for body, Medium (500) for headers, no bold-heavy usage

### Spacing
- **Sidebar width**: 64px collapsed, ~200px expanded
- **Right panel width**: ~320px (chat session rail)
- **Card padding**: 16px–24px
- **Section gaps**: 24px–32px between major sections
- **Inline gaps**: 8px–12px between related elements
- **Border radius**: 8px for cards, 4px for buttons/inputs

### Iconography
- **Lucide React** (inferred from modern React stack)
- Icons are **stroke-based** (outlined), not filled
- Icon size: 20px in sidebar, 16px inline
- Active state: Icon + left border accent (not background change)

### Animation Patterns
- **Page transitions**: None observed (full page replacement)
- **Sidebar hover**: Smooth width expansion (~200ms ease)
- **Expandable rows**: Slide-down animation for session detail
- **Toast notifications**: Slide-in from top-right, auto-dismiss
- **Loading states**: Inline spinners, skeleton screens for async data
- **No decorative looping animations** — all motion conveys state change

---

## 1.4 User Flows and Interaction Patterns

### Flow 1: Starting a Chat
1. Click 💬 Chat in sidebar (or default route)
2. Terminal embed loads with xterm.js
3. Type message in composer (bottom) or directly in terminal
4. Message sends via WebSocket to backend
5. Response streams back token-by-token
6. Tool calls appear as collapsible cards within the message stream

### Flow 2: Managing a Profile
1. Click profile switcher in sidebar
2. Select profile from dropdown (or create new)
3. Amber banner appears: "Managing profile: worker"
4. Navigate to Config page — settings are scoped to selected profile
5. Changes persist to that profile's `config.yaml`

### Flow 3: Browsing Sessions
1. Click 📋 Sessions in sidebar
2. Table loads with recent sessions
3. Use search bar for full-text search across messages
4. Click row to expand — loads message history with markdown rendering
5. Click ▶ to resume session in Chat view

### Flow 4: Configuring MCP Servers
1. Navigate to MCP page
2. See list of configured servers with status indicators
3. Click "Add" — form appears with URL or command+args
4. Fill fields, click "Test" — backend verifies connection
5. Toggle enable/disable without deleting
6. Changes written to `config.yaml`, gateway restart required

### Flow 5: Handling Approval (in Chat)
1. Agent requests approval for tool call
2. Inline prompt appears in chat stream
3. User clicks Approve/Deny/Always Approve
4. Agent continues or aborts based on response

---

## 1.5 Notable UX Decisions

1. **Terminal-as-Chat**: Hermes embeds the full TUI in the browser via xterm.js. This means the web UI has **perfect parity** with the CLI — no feature gap. But it also means the chat experience is terminal-like (monospace, ANSI colors) rather than rich-text bubbles.

2. **Profile Scoping**: Every management page is implicitly scoped to the active profile. There is no "global" view — you always manage one profile at a time. This prevents accidental cross-profile changes but makes cross-profile comparison harder.

3. **Lazy Loading for Skills**: Skills are loaded by description cheaply; full content only when needed. The UI reflects this with short descriptions in the list and expandable detail.

4. **Redacted Secrets**: All API keys, tokens, and passwords are redacted in the UI (shown as `••••••`). Raw values only reach the agent, never the frontend.

5. **Config Schema-Driven UI**: The frontend fetches `/api/config/schema` and renders the correct input widget for each field. This means the UI auto-updates when new config options are added — no frontend code changes needed.

6. **No Mobile Support**: Desktop-only (1280px+). No responsive breakpoints observed.

7. **OAuth-First Auth**: The default auth is Nous Portal OAuth. Username/password is secondary and explicitly warned as "not for public internet."

---

# PART 2: JARVIS UI SPECIFICATION

## 2.1 UI Architecture Overview

### Philosophy Shift: From Chat-First to Operations-First

Hermes is a **chat-centric agent** — the terminal/chat is the primary interface, and management is secondary. JArvis is an **operations center** — task orchestration, system monitoring, and resource management are primary, with chat/terminal as one of several tools.

This changes the layout fundamentally:

```
HERMES (Chat-First)                    JARVIS (Operations-First)
┌─────────────────────────┐            ┌──────────────────────────────┐
│  Sidebar                │            │  Status Bar (persistent)   │
│  ├─ Chat (primary)      │            │  ├─ Session / Phase / Model  │
│  ├─ Sessions            │            │  ├─ Latency / Run-Pause     │
│  ├─ Logs                │            ├──────────────────────────────┤
│  ├─ Profiles            │            │  Sidebar    │ Main       │ Right    │
│  ├─ Skills              │            │  ├─ Terminal │  (adaptive) │ (tabs)   │
│  ├─ MCP                 │            │  ├─ Tasks    │             │          │
│  ├─ Config              │            │  ├─ Workers  │             │          │
│  ├─ Cron                │            │  ├─ Approvals│             │          │
│  ├─ Pairing             │            │  ├─ Costs    │             │          │
│  ├─ Channels            │            │  ├─ Memory   │             │          │
│  └─ System              │            │  ├─ Skills   │             │          │
│                         │            │  ├─ Settings │             │          │
│  Main: Single-page      │            │  └─ Help     │             │          │
│  (one view at a time)   │            ├──────────────────────────────┤
│                         │            │  Bottom Bar                  │
│  Right: Contextual        │            │  ├─ Activation Grid          │
│  (changes per page)       │            │  ├─ Token/Context Counter    │
└─────────────────────────┘            └──────────────────────────────┘
```

### Layout Grid Specification

JArvis uses a **persistent dashboard shell** (not page-based navigation). All panels are always present; the main area adapts its content.

```css
.jarvis-shell {
  display: grid;
  grid-template-rows: 48px 1fr 64px;
  grid-template-columns: 64px 1fr 320px;
  grid-template-areas:
    "status   status   status"
    "sidebar  main     right"
    "bottom   bottom   bottom";
  height: 100vh;
  overflow: hidden;
  background: var(--color-surface-base);
}

/* Collapsed right panel */
.jarvis-shell.right-collapsed {
  grid-template-columns: 64px 1fr 0px;
}

/* Expanded sidebar */
.jarvis-shell.sidebar-expanded {
  grid-template-columns: 200px 1fr 320px;
}
```

**Why this matters:**
- The status bar is **always visible** — critical for monitoring agent state
- The bottom bar is **always visible** — activation grid provides ambient awareness
- The right panel is **persistent** — tool inspector, timeline, and reasoning are always accessible via tabs
- The main area **adapts** — terminal when idle, task stream when active

### Page vs. Panel Navigation

| Hermes Pattern | JArvis Adaptation | Rationale |
|---|---|---|
| Page-based (`/chat`, `/sessions`) | Panel-based (sidebar toggles main content) | Operations center needs multi-panel visibility |
| Profile switcher | No profile switcher (single-user, single-profile) | Sovereign AI is single-user by design |
| Right panel changes per page | Right panel is persistent tab switcher | Tool inspector + timeline + reasoning are always relevant |
| Full-screen terminal | Terminal shares space with task stream | Task monitoring is as important as terminal access |

---

## 2.2 Component Inventory

### Layout Components

| Component | Description | Props / Config |
|---|---|---|
| `StatusBar` | Persistent top bar (48px) | `sessionId`, `phase`, `model`, `latency`, `isRunning` |
| `Sidebar` | Icon-only nav (64px), hover-expand (200px) | `activeItem`, `items[]`, `onNavigate` |
| `MainPane` | Flexible center area | `mode: 'terminal' | 'task'` |
| `RightPanel` | Tabbed dashboard panel (320px) | `activeTab`, `tabs[]`, `onTabChange` |
| `BottomBar` | Persistent bottom bar (64px) | `activationData`, `tokenCount`, `contextPercent` |
| `MemoryDrawer` | Slide-in from right (480px) | `isOpen`, `slots[]`, `onSearch`, `onExport`, `onImport` |
| `SettingsDrawer` | Slide-in from right (480px) | `isOpen`, `activeTab`, `onSave` |
| `ModelPickerModal` | Center modal | `models[]`, `onSelect`, `onClose` |
| `ApprovalModal` | Center modal for pending approvals | `request`, `onApprove`, `onDeny`, `onAlwaysApprove` |

### Data Display Components

| Component | Description | Data Source |
|---|---|---|
| `TaskCard` | Active task detail view | `Task` schema |
| `TaskList` | List of tasks with status | `orchestrator.list_tasks()` |
| `WorkerCard` | Worker registry entry with circuit status | `orchestrator.list_workers()` + `circuit_breaker.get_status()` |
| `CircuitStatus` | Open/closed indicator with failure count | `WorkerCircuitBreaker` |
| `ApprovalQueue` | Pending approval requests | `approval_gate._pending_requests` |
| `ApprovalRequestCard` | Single approval with actions | `ApprovalRequest` schema |
| `CostGauge` | Daily/monthly spend progress bar | `cost_tracker.get_spend_summary()` |
| `CostBreakdown` | Per-model cost chart | `cost_tracker.get_model_spend()` |
| `MemorySlotTable` | Sortable table of memory slots | `memory_router.fetch_by_filter()` |
| `MemorySlotRow` | Expandable row with full value | `MemorySlot` |
| `ActivationGrid` | 32x16 Canvas visualization | `/api/memory/activations` SSE |
| `ToolCallCard` | Expandable tool invocation log | `TraceEvent` + `WorkerOutput` |
| `ToolCallList` | Scrollable list of tool calls (max 50) | `toolStore` |
| `SessionTimeline` | SVG Gantt chart of phase segments | `/api/sessions/{id}/timeline` |
| `ReasoningStream` | Collapsible chain-of-thought | `/api/agent/reasoning` SSE |
| `SubagentCard` | Subagent status with mini grid | `/api/subagents` polling |
| `SystemStats` | CPU/RAM/GPU gauges | `SystemProfile` schema |
| `LogViewer` | Filtered, color-coded log tail | `/api/logs` |

### Form Components

| Component | Description | Used In |
|---|---|---|
| `TaskInput` | Intent + priority + submit | Main pane (terminal mode) |
| `CostPolicyForm` | Daily cap, monthly cap, thresholds | Settings drawer |
| `CircuitBreakerForm` | Failure threshold, reset timeout | Settings drawer |
| `SandboxConfigForm` | Policy, memory, CPU, timeout | Settings drawer |
| `SkillToggle` | Enable/disable individual skills | Skills panel |
| `MemorySearch` | Filter memory slots by key/value | Memory drawer |
| `ModelSelector` | Fuzzy search through model registry | Model picker modal |

### Feedback Components

| Component | Description | Trigger |
|---|---|---|
| `PhaseBadge` | Color-coded phase indicator | `agentStore.phase` changes |
| `LatencyChip` | Live ms counter | Every agent turn |
| `CostAlert` | Toast when spend threshold hit | `cost_tracker._emit_alert()` |
| `CircuitAlert` | Toast when circuit opens | `circuit_breaker._emit_circuit_open_event()` |
| `ApprovalNotification` | Badge on sidebar approvals icon | `approval_gate._pending_requests.length > 0` |
| `TaskStateTransition` | Animated progress bar | `task.current_state` changes |

---

## 2.3 Design Tokens

### Color Palette

JArvis shifts from Hermes' electric blue to **amber/slate** to match the Sovereign AI brand and differentiate from Hermes.

```css
:root {
  /* Surface colors */
  --color-surface-base:    #0c0c0f;   /* Page background — deeper than Hermes */
  --color-surface-raised:  #13131a;   /* Cards, panels — subtle lift */
  --color-surface-overlay: #1a1a24;   /* Modals, drawers — highest elevation */
  --color-surface-hover:   #1f1f2e;   /* Hover states */

  /* Border colors */
  --color-border:          rgba(255, 255, 255, 0.08);  /* Hairline — matches Hermes */
  --color-border-strong:   rgba(255, 255, 255, 0.16);  /* Focused/active */
  --color-border-accent:   rgba(245, 158, 11, 0.40);   /* Amber accent border */

  /* Text colors */
  --color-text-primary:    #e8e6e0;   /* Warm off-white — softer than Hermes' pure white */
  --color-text-secondary:  #9b9890;   /* Warm gray — readable but de-emphasized */
  --color-text-muted:      #5c5a56;   /* Dark gray — timestamps, metadata */
  --color-text-inverse:    #0c0c0f;   /* For text on accent backgrounds */

  /* Accent colors */
  --color-accent-amber:    #f59e0b;   /* Primary — planning, active elements, focus rings */
  --color-accent-emerald:  #10b981;   /* Success — acting phase, closed circuit, approved */
  --color-accent-violet:   #8b5cf6;   /* Reflecting phase, model picker highlight */
  --color-accent-red:      #ef4444;   /* Error — failed task, open circuit, denied approval */
  --color-accent-blue:     #3b82f6;   /* Info — in-flight tool, links, pending approval */
  --color-accent-slate:    #64748b;   /* Idle — inactive slots, disabled workers */
}
```

**Color usage rules:**
- Phase badges: `idle` = slate, `planning` = amber, `acting` = emerald, `reflecting` = violet
- Circuit status: `closed` = emerald, `open` = red, `half-open` = amber
- Approval status: `pending` = blue, `approved` = emerald, `denied` = red
- Tool call status: `running` = blue (pulsing), `success` = emerald, `error` = red, `warning` = amber

### Typography

```css
:root {
  /* Font families */
  --font-sans:  system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono:  'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;

  /* Font sizes */
  --text-xs:    12px;  /* Captions, metadata, timestamps */
  --text-sm:    14px;  /* Body text, agent output */
  --text-base:  16px;  /* Form inputs, buttons */
  --text-lg:    18px;  /* Section headers */
  --text-xl:    20px;  /* Page titles */
  --text-2xl:   24px;  /* Major headings */

  /* Font weights */
  --font-normal:   400;
  --font-medium:   500;  /* Maximum for chrome elements — no bold UI chrome */
  --font-semibold: 600;  /* Only for data emphasis (numbers, status) */

  /* Line heights */
  --leading-tight:  1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;  /* Agent response text */
}
```

**Typography rules:**
- All agent output, tool args, code, logs: `font-mono`
- All chrome (buttons, labels, headers): `font-sans`
- Minimum size in any element: `text-xs` (12px)
- Never use `font-bold` (700) in chrome — maximum is `font-medium` (500)
- Agent response text: `text-sm` (14px), `leading-relaxed`

### Spacing Scale

```css
:root {
  /* Base unit: 4px */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;

  /* Layout dimensions */
  --status-bar-height: 48px;
  --sidebar-width: 64px;
  --sidebar-width-expanded: 200px;
  --right-panel-width: 320px;
  --bottom-bar-height: 64px;
  --drawer-width: 480px;

  /* Border radius */
  --radius-sm: 4px;   /* Buttons, inputs, tags */
  --radius-md: 8px;   /* Cards, panels */
  --radius-lg: 12px;  /* Modals, drawers */
  --radius-full: 9999px; /* Pills, badges */
}
```

**Spacing rules:**
- Card padding: `--space-4` (16px) to `--space-5` (20px)
- Section gaps: `--space-6` (24px) to `--space-8` (32px)
- Inline element gaps: `--space-2` (8px) to `--space-3` (12px)
- Status bar items: `--space-3` (12px) horizontal padding
- Sidebar icon padding: `--space-4` (16px)

### Shadows and Elevation

```css
:root {
  /* Elevation levels */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.2);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5), 0 4px 6px rgba(0, 0, 0, 0.3);
  --shadow-drawer: -4px 0 24px rgba(0, 0, 0, 0.6);  /* Right-side shadow for drawers */
}
```

---

## 2.4 Interaction Patterns

### Pattern 1: Mode Switching (Terminal ↔ Task Stream)

**Trigger:** Agent phase changes from `idle` to `planning` (task submitted)

**Behavior:**
1. Main pane transitions from Terminal view to Task Stream view
2. Transition animation: fade-out terminal (150ms) → fade-in task card (150ms)
3. Task card slides in from bottom with staggered content reveal
4. Terminal remains mounted but hidden (`display: none`) — preserves scrollback

**Trigger:** Task completes or is cancelled

**Behavior:**
1. Task output remains visible for 5 seconds (or until user clicks "Done")
2. "Done" button appears in task card header
3. Clicking "Done" fades task view out, restores terminal view
4. Terminal receives focus automatically

**Why this matters:** Users need to monitor task execution without losing terminal context. The terminal is "paused" during task execution, not destroyed.

### Pattern 2: Approval Flow

**Trigger:** `approval_gate.request_approval()` is called

**Behavior:**
1. Backend sends approval request via WebSocket or SSE
2. Frontend receives request, adds to `approvalStore`
3. Sidebar approvals icon shows red badge with count
4. If user is on Approvals panel, request animates in (slide-down, 200ms)
5. If user is elsewhere, a toast notification appears (top-right, auto-dismiss 10s)

**User actions:**
- **Approve**: Request transitions to `approved`, agent continues
- **Deny**: Request transitions to `denied`, agent aborts
- **Always Approve**: Adds command pattern to trust registry, auto-approves future matches

**Edge case:** Request expires (5-minute TTL). Frontend auto-removes expired requests with fade-out animation.

### Pattern 3: Circuit Breaker Monitoring

**Trigger:** `circuit_breaker.record_failure()` crosses threshold

**Behavior:**
1. Circuit opens for affected worker
2. Workers panel updates: status dot turns red, failure count shows `3/3`
3. Toast notification: "Worker 'prism_llama' circuit opened — too many failures"
4. Task routing automatically excludes open-circuit workers
5. Degraded ratio updates in status bar (if >20%, amber warning)

**User actions:**
- **Reset Circuit**: Click reset button on worker card. Backend calls `reset_circuit()`. Frontend shows spinner for 2s, then updates to closed.
- **Reset All**: Button in Workers panel header. Confirmation modal required.

**Ambient awareness:** Open circuits are visible at a glance in the Workers panel. No need to navigate to a separate page.

### Pattern 4: Cost Alert Flow

**Trigger:** `cost_tracker.record_usage()` crosses alert threshold (default 80%)

**Behavior:**
1. Backend emits `COST_ALERT` trace event
2. Frontend receives event, shows toast: "Daily spend at $8.00 / $10.00 (80%)"
3. Cost dashboard badge turns amber
4. Status bar cost chip pulses briefly

**Trigger:** Fallback threshold crossed (default 90%)

**Behavior:**
1. Backend emits `COST_FALLBACK_TRIGGERED` trace event
2. Frontend shows toast: "Falling back to local model — cost threshold reached"
3. Model slug in status bar updates to fallback model
4. Cost dashboard shows fallback event in history

### Pattern 5: Memory Grid Interaction

**Trigger:** User clicks a cell in the activation grid (bottom bar)

**Behavior:**
1. Cell highlights with amber border (2px)
2. Inline tooltip appears above cell:
   - Slot index: `042`
   - Key: `notes:meeting`
   - Last written: `2m ago`
   - Value preview: `"Q2 Review..."` (truncated to 40 chars)
   - Activation: `0.85` (mini bar)
3. Clicking tooltip opens Memory Drawer, scrolled to that slot, row expanded

**Trigger:** User clicks "Export Memory" in Memory Drawer

**Behavior:**
1. Frontend calls `GET /api/memory/slots` (not local store — ensures complete data)
2. Receives full slot array
3. Generates `memory.json` blob
4. Triggers browser download via `<a download>`

**Trigger:** User imports memory

**Behavior:**
1. File picker opens
2. User selects JSON file
3. Frontend validates JSON structure (must be array of `{key, value, scope}`)
4. POSTs to `/api/memory/import`
5. On success: Memory Drawer refreshes, activation grid updates
6. On error: Toast with specific error message

### Pattern 6: Tool Call Inspection

**Trigger:** Agent executes a tool

**Behavior:**
1. Backend sends tool call event via SSE (`/api/tools/stream`)
2. Frontend adds to `toolStore` (max 50 entries, evicts oldest)
3. New entry animates in: slide-down from top (200ms)
4. Status indicator: pulsing blue dot while `running`
5. On completion: dot turns green (`success`) or red (`error`)

**User actions:**
- **Expand**: Click header row → body reveals args (key/value grid), output (pre-formatted, syntax-highlighted JSON), latency bar
- **Collapse**: Click header again or click another entry
- **Filter**: Use right panel tabs to show only errors, only recent, etc.

### Pattern 7: Keyboard Shortcuts

| Shortcut | Action | Context | Conflict Resolution |
|---|---|---|---|
| `Space` | Run/Pause agent | Global | Disabled when any input/textarea focused, or when xterm.js has focus |
| `Ctrl+K` | Open command palette | Global | Always active, modal overlay |
| `/` | Focus search | Memory drawer, Skills panel | Disabled when xterm.js focused |
| `M` | Toggle memory drawer | Global | Disabled when input focused |
| `T` | Toggle tasks panel | Global | Disabled when input focused |
| `W` | Toggle workers panel | Global | Disabled when input focused |
| `A` | Toggle approvals panel | Global | Disabled when input focused |
| `C` | Toggle costs panel | Global | Disabled when input focused |
| `Esc` | Close drawer/modal/palette | Global | Always active |
| `Ctrl+Enter` | Submit task | Task input focused | Only when task input has focus |

**Conflict resolution system:**
```typescript
function isShortcutAvailable(): boolean {
  const activeElement = document.activeElement;
  const isInput = activeElement?.tagName === 'INPUT' ||
                  activeElement?.tagName === 'TEXTAREA' ||
                  activeElement?.isContentEditable;
  const isXterm = activeElement?.closest('.xterm') !== null;
  return !isInput && !isXterm;
}
```

---

## 2.5 Do's and Don'ts

### DO: Replicate from Hermes

| Pattern | Why It Works | Where to Use |
|---|---|---|
| **xterm.js terminal embed** | Perfect CLI parity, ANSI colors, box-drawing | Main pane — Terminal mode |
| **Icon-only sidebar with hover-expand** | Clean, space-efficient, scalable to many items | JArvis sidebar (10 items) |
| **Redacted secrets display** | Security — raw values never reach frontend | API keys in Settings, credential pool |
| **Schema-driven config UI** | Auto-updates when backend adds new fields | Settings drawer forms |
| **Expandable rows for detail** | Progressive disclosure, clean lists | Task list, memory slots, tool calls |
| **Color-coded status indicators** | Instant recognition at a glance | Circuit status, task state, approval status |
| **Inline approval prompts** | Don't break user flow with modals | Chat/task stream for simple approvals |
| **Full-text search with highlighted snippets** | Fast information retrieval | Sessions, memory, logs |
| **Polling with auto-refresh toggle** | User controls data freshness | Logs, subagents, system stats |

### DON'T: Replicate from Hermes

| Pattern | Why It Doesn't Fit JArvis | What to Do Instead |
|---|---|---|
| **Page-based navigation** | JArvis needs multi-panel visibility | Persistent dashboard shell with adaptive main pane |
| **Profile switcher** | Sovereign AI is single-user, single-profile | Remove entirely — no profile concept |
| **Chat as primary interface** | JArvis is operations, not conversation | Terminal is one of many tools, not the center |
| **Right panel as session list** | Sessions are secondary to operations | Right panel shows tool inspector, timeline, reasoning |
| **Electric blue accent** | Hermes branding, not Sovereign AI | Amber (`#f59e0b`) as primary accent |
| **Cyberpunk aesthetic** | Not aligned with "mission-critical" philosophy | Dense, purposeful, slate-based design |
| **OAuth-first auth** | Single-user local install | Bearer token only, no external identity |
| **Mobile-responsive layout** | Desktop-only per constraints | Fixed 1280px+ minimum, no breakpoints |
| **Plugin SDK** | Out of scope for v1 | Panels are first-class, not plugins |

### DO: JArvis-Specific Innovations

| Innovation | Rationale | Implementation |
|---|---|---|
| **Persistent status bar** | Agent phase, model, latency are always relevant | 48px top bar, always visible |
| **Activation grid** | Visual memory state provides ambient awareness | 32x16 Canvas in bottom bar |
| **Task Stream mode** | Task execution is primary, not secondary | Main pane adapts to show live task progress |
| **Circuit breaker dashboard** | Worker health is critical for operations | Workers panel with real-time status |
| **Cost dashboard** | Spend tracking prevents bill shock | Persistent cost gauges in right panel |
| **Approval queue panel** | Human-in-the-loop is core to Sovereign AI | Dedicated panel with batch actions |
| **Bottom bar with token counter** | Context window awareness prevents failures | Token count + context percentage |
| **Command palette (Ctrl+K)** | Fast navigation in dense interface | Modal overlay with fuzzy search |

### DON'T: JArvis Anti-Patterns

| Anti-Pattern | Why It Fails | Prevention |
|---|---|---|
| **Modal-heavy workflows** | Breaks operational flow | Use drawers for secondary tasks, inline for primary |
| **Decorative animations** | Distracts from mission-critical data | Only animate state changes, no loops |
| **Hidden state** | User must navigate to see status | All critical state visible in persistent bars |
| **Generic error messages** | Operations require precise diagnostics | Every error includes component, context, suggestion |
| **Auto-refresh without control** | Wastes resources, causes jitter | All polling has toggle + interval selector |
| **Monolithic components** | Hard to test, hard to extend | Each panel is independent, data via props |

---

## 2.6 Data Flow Architecture

### State Management

JArvis uses **Zustand** with domain-specific stores (per build plan §2):

```typescript
// stores/agentStore.ts
interface AgentStore {
  phase: 'idle' | 'planning' | 'acting' | 'reflecting';
  sessionId: string;
  model: string;
  latency: number;
  isRunning: boolean;
  setPhase: (phase: AgentStore['phase']) => void;
  // ...
}

// stores/taskStore.ts
interface TaskStore {
  activeTasks: Task[];
  completedTasks: Task[];
  failedTasks: Task[];
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  // ...
}

// stores/approvalStore.ts
interface ApprovalStore {
  pending: ApprovalRequest[];
  history: ApprovalResponse[];
  addRequest: (req: ApprovalRequest) => void;
  respond: (id: string, approved: boolean, always?: boolean) => void;
  // ...
}

// stores/costStore.ts
interface CostStore {
  dailySpend: number;
  monthlySpend: number;
  dailyCap: number;
  monthlyCap: number;
  alertThreshold: number;
  fallbackThreshold: number;
  modelBreakdown: Record<string, number>;
  // ...
}

// stores/memoryStore.ts
interface MemoryStore {
  slots: MemorySlot[];
  activations: Float32Array;  // 512-length array
  searchQuery: string;
  sortColumn: string;
  sortDirection: 'asc' | 'desc';
  // ...
}

// stores/toolStore.ts
interface ToolStore {
  calls: ToolCall[];
  maxEntries: 50;
  filter: 'all' | 'running' | 'success' | 'error';
  addCall: (call: ToolCall) => void;
  updateCall: (id: string, updates: Partial<ToolCall>) => void;
  // ...
}
```

### API Integration

```typescript
// hooks/usePolling.ts
function usePolling<T>(
  fetcher: () => Promise<T>,
  interval: number,
  enabled: boolean = true
): { data: T | null; isLoading: boolean; error: Error | null };

// hooks/useSSE.ts
function useSSE<T>(
  url: string,
  onMessage: (data: T) => void,
  onError?: (error: Event) => void
): { isConnected: boolean; reconnectCount: number };

// hooks/useMemoryGrid.ts
function useMemoryGrid(): {
  activations: Float32Array;
  decayRate: number;
  writeSlot: (index: number, value: number) => void;
};
```

### Polling vs. SSE Strategy

| Data Source | Transport | Interval | Rationale |
|---|---|---|---|
| Agent status | Polling | 2s | Small payload, frequent updates |
| Tasks | Polling | 2s | Task list changes on user action + background |
| Workers | Polling | 5s | Worker registry is relatively stable |
| Approvals | Polling | 2s | User needs responsive approval queue |
| Costs | Polling | 10s | Spend changes gradually |
| Memory activations | SSE | Real-time | High-frequency, streaming data |
| Tool calls | SSE | Real-time | Event-driven, needs immediate display |
| Reasoning | SSE | Real-time | Token-by-token streaming |
| Terminal | WebSocket | Real-time | Bidirectional PTY |
| Logs | Polling | 5s (with live tail toggle) | Large payload, user controls refresh |
| Subagents | Polling | 2s | Subagent state changes on action + background |

---

## 2.7 Responsive Behavior

JArvis is **desktop-only** (1280px+ minimum). No mobile breakpoints.

| Width Range | Layout Changes |
|---|---|
| ≥1440px | Full layout: sidebar 64px, right panel 320px |
| 1280–1439px | Right panel collapses to 48px icon tabs (click to expand) |
| <1280px | Not supported — show "Minimum 1280px width required" message |

---

## 2.8 Accessibility Requirements

- All interactive elements have visible focus rings: `outline: 2px solid var(--color-accent-amber)`
- All icon-only buttons have `aria-label`
- Activation grid canvas has `role="img" aria-label="Memory activation grid — {N} active slots"`
- SSE-driven live regions use `aria-live="polite"` on their container
- Color is not the sole indicator of state — always pair with icon or text
- Keyboard navigation: Tab order follows visual layout, Escape closes modals/drawers
- Reduced motion: Wrap all animations in `@media (prefers-reduced-motion: no-preference)`

---

## 2.9 File Structure

```
sovereign-ai/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Shell: status bar + sidebar + panels
│   │   ├── globals.css             # Design tokens + Tailwind v4 config
│   │   └── page.tsx                # Default route → terminal pane
│   ├── components/
│   │   ├── shell/
│   │   │   ├── StatusBar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── MainPane.tsx
│   │   │   ├── RightPanel.tsx
│   │   │   └── BottomBar.tsx
│   │   ├── panels/
│   │   │   ├── TerminalEmbed.tsx      # xterm.js wrapper
│   │   │   ├── TaskStream.tsx         # Task detail + live output
│   │   │   ├── TaskList.tsx           # Active/completed/failed tasks
│   │   │   ├── WorkerRegistry.tsx     # Worker cards + circuit status
│   │   │   ├── ApprovalQueue.tsx      # Pending approvals
│   │   │   ├── CostDashboard.tsx      # Spend gauges + breakdown
│   │   │   ├── MemoryDrawer.tsx       # Slide-in memory inspector
│   │   │   ├── ActivationGrid.tsx     # 32x16 Canvas panel
│   │   │   ├── ToolInspector.tsx      # Tool call log
│   │   │   ├── SessionTimeline.tsx    # SVG Gantt chart
│   │   │   ├── ReasoningStream.tsx    # Collapsible CoT
│   │   │   ├── SubagentPanel.tsx      # Subagent cards
│   │   │   ├── SkillsPanel.tsx        # Skill registry
│   │   │   ├── SettingsDrawer.tsx     # Slide-in settings
│   │   │   ├── ModelPickerModal.tsx   # Model selection
│   │   │   ├── LogViewer.tsx          # Filtered log tail
│   │   │   └── SystemStats.tsx        # CPU/RAM/GPU gauges
│   │   ├── ui/                     # shadcn/ui primitives
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Toggle.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Slider.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Drawer.tsx
│   │   │   ├── Toast.tsx
│   │   │   ├── Tooltip.tsx
│   │   │   └── CommandPalette.tsx
│   │   └── shared/
│   │       ├── PhaseBadge.tsx
│   │       ├── CircuitStatus.tsx
│   │       ├── CostGauge.tsx
│   │       ├── ToolCallCard.tsx
│   │       └── MemorySlotRow.tsx
│   ├── hooks/
│   │   ├── usePolling.ts
│   │   ├── useSSE.ts
│   │   ├── useMemoryGrid.ts
│   │   ├── useToolStream.ts
│   │   ├── useKeyboardShortcuts.ts
│   │   ├── useCommandPalette.ts
│   │   └── useTimeline.ts
│   ├── stores/
│   │   ├── agentStore.ts
│   │   ├── taskStore.ts
│   │   ├── workerStore.ts
│   │   ├── approvalStore.ts
│   │   ├── costStore.ts
│   │   ├── memoryStore.ts
│   │   ├── toolStore.ts
│   │   └── subagentStore.ts
│   ├── lib/
│   │   ├── api.ts                  # Typed fetch/SSE/WS wrappers
│   │   ├── utils.ts                # cn(), timeAgo(), formatMs()
│   │   ├── keyboard.ts             # Shortcut registration
│   │   └── constants.ts            # API endpoints, defaults
│   └── types/
│       ├── api.ts                  # Shared frontend/backend types
│       ├── models.ts               # Pydantic model TypeScript equivalents
│       └── events.ts               # SSE/WebSocket event types
├── backend/
│   ├── main.py                     # FastAPI app
│   ├── routers/
│   │   ├── status.py               # GET /api/status
│   │   ├── tasks.py                # GET/POST /api/tasks
│   │   ├── workers.py              # GET /api/workers
│   │   ├── approvals.py            # GET/POST /api/approvals
│   │   ├── costs.py                # GET /api/costs
│   │   ├── memory.py               # GET/POST/DELETE /api/memory
│   │   ├── tools.py                # SSE /api/tools/stream
│   │   ├── reasoning.py            # SSE /api/agent/reasoning
│   │   ├── activations.py          # SSE /api/memory/activations
│   │   ├── subagents.py            # GET/DELETE /api/subagents
│   │   ├── skills.py               # GET /api/skills
│   │   ├── logs.py                 # GET /api/logs
│   │   ├── sessions.py             # GET /api/sessions
│   │   └── system.py               # GET /api/system
│   ├── pty_handler.py              # WebSocket PTY bridge
│   └── middleware/
│       └── auth.py                 # Bearer token validation
├── prisma/
│   └── schema.prisma               # Sessions, memory slots, tool log, approvals
└── DECISIONS.md
```

---

## 2.10 Implementation Priority

### Phase 1: Shell (Week 1)
1. CSS Grid shell layout
2. Status bar with static data
3. Sidebar with navigation
4. Main pane (Terminal mode only)
5. Right panel shell (empty tabs)
6. Bottom bar with placeholder activation grid

### Phase 2: Backend Stubs (Week 1)
1. All API endpoints returning mocked data
2. SSE streams with simulated events
3. WebSocket PTY with echo server

### Phase 3: Core Hooks (Week 2)
1. `usePolling` — generic polling hook
2. `useSSE` — generic SSE with reconnect
3. `useKeyboardShortcuts` — global shortcut manager
4. `useCommandPalette` — fuzzy search overlay

### Phase 4: Terminal + Task Stream (Week 2)
1. xterm.js integration with WebSocket
2. Task Stream mode with detail card
3. Mode switching logic

### Phase 5: Operational Panels (Week 3–4)
1. Tool Inspector (SSE streaming)
2. Workers panel with circuit status
3. Approval queue with actions
4. Cost dashboard with gauges

### Phase 6: Memory + System (Week 4–5)
1. Activation grid with real data
2. Memory drawer with search/sort
3. Memory import/export
4. System stats panel

### Phase 7: Polish (Week 5–6)
1. Session timeline
2. Reasoning stream
3. Subagent panel
4. Skills panel
5. Settings drawer
6. Model picker
7. Log viewer

---

*Specification complete. All components mapped to specific methods in the Sovereign AI codebase.*
