
# JArvis UI — Design Specification
## Inspired by Hermes Agent Dashboard, Mapped to Sovereign AI Codebase
## Commit a5cff19 | 2026-06-26

---

## DESIGN PHILOSOPHY

Hermes Agent uses a **three-panel layout**: left sidebar (sessions/nav), center chat (xterm.js TUI embed), right workspace (file browser). JArvis adapts this pattern but replaces Hermes' generic chat-centric design with **Sovereign AI's operational dashboards** — because JArvis is not a chatbot, it's a local-first AI operations center.

**Key differences from Hermes:**
| Dimension | Hermes | JArvis |
|---|---|---|
| Primary purpose | Chat + session management | Task orchestration + system monitoring |
| Center pane | Chat TUI embed | Terminal + Task Stream hybrid |
| Right panel | File browser | Operational dashboards (circuit breaker, costs, approvals) |
| Bottom bar | Token ring + composer | Activation grid + system status |
| Accent color | Electric blue `#0000f2` | Amber `#f59e0b` (per build plan §10) |
| Visual density | Moderate (chat-focused) | Dense (dashboard-focused) |

---

## LAYOUT SHELL

```
┌─────────────────────────────────────────────────────────────────┐
│  Status Bar (sticky, 48px)                                     │
│  [Session] [Phase●] [Model▼] [Latency: 45ms] [▶/⏸] [⚙]      │
├──────────┬──────────────────────────────┬─────────────────────┤
│          │                              │                     │
│ Sidebar  │  Main Pane                   │  Right Panel        │
│ (64px)   │  ┌────────────────────────┐  │  (tab switcher)    │
│          │  │  Terminal / Task Stream │  │                     │
│ [🏠]     │  │  (xterm.js embed)       │  │  [Tool Inspector]  │
│ [💬]     │  │                         │  │  [Timeline]        │
│ [⚡]     │  │  OR when task active:   │  │  [Reasoning]       │
│ [🔒]     │  │  ┌──────────────────┐   │  │                     │
│ [💰]     │  │  │ Task Detail Card │   │  │  OR when expanded:  │
│ [🧠]     │  │  │ (intent, status, │   │  │  [Circuit Breaker]  │
│ [🔧]     │  │  │  worker, output) │   │  │  [Cost Dashboard]   │
│ [⚙]      │  │  └──────────────────┘   │  │  [Approval Queue]   │
│ [?]      │  │                         │  │  [Worker Registry]  │
│          │  │  ┌──────────────────┐   │  │                     │
│          │  │  │ Live Output      │   │  │                     │
│          │  │  │ (streaming)      │   │  │                     │
│          │  │  └──────────────────┘   │  │                     │
│          │  └────────────────────────┘  │                     │
├──────────┴──────────────────────────────┴─────────────────────┤
│  Bottom Bar (64px)                                             │
│  [Activation Grid 32×16]          [Token: 4.2K/8K] [Ctx: 52%] │
└─────────────────────────────────────────────────────────────────┘
```

**CSS Grid definition:**
```css
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
}
```

---

## 1. STATUS BAR (48px, sticky top)

**Inspired by:** Hermes composer footer + model picker, but elevated to top bar for persistent visibility.

| Element | Source | Behavior |
|---|---|---|
| **Session ID** | `orchestrator.py` — `session_id` | Short hash `SES-8f2a`, copy on click |
| **Phase Badge** | `orchestrator.py` — `current_phase` | `Sovereign · Planning` (amber), `Sovereign · Acting` (emerald), `Sovereign · Reflecting` (violet), `Sovereign · Idle` (slate). 300ms color transition. |
| **Model Slug** | `orchestrator.py` — `active_model` | `GLM-4.5 Flash` — clickable → **Model Picker Modal** |
| **Latency Chip** | `orchestrator.py` — per-task latency | Live ms counter, updates on each turn |
| **Run/Pause** | `orchestrator.py` — `process_task()` toggle | Single button, `Space` shortcut. Amber when running, slate when idle. |
| **Settings Gear** | Global settings | Opens **Settings Drawer** (right slide-in) |

**Model Picker Modal** (not in Hermes — JArvis-specific):
- Fuzzy search through `ModelRegistry` (`core/schemas.py:ModelEntry`)
- Shows: model name, provider, quantisation, download status, VRAM estimate
- Filter by: downloaded only, quantisation tier, provider
- "Load" / "Unload" buttons for model management

---

## 2. SIDEBAR (64px icon-only, 200px on hover)

**Inspired by:** Hermes sidebar (sessions, nav, control center launcher). JArvis maps icons to operational domains.

| Icon | Label | Navigates To | Source File |
|---|---|---|---|
| 🏠 | Home | Terminal / Task Stream (default) | `web/server.py` |
| 💬 | Tasks | Task list + detail view | `core/orchestrator.py` |
| ⚡ | Workers | Worker registry + circuit status | `core/worker_circuit_breaker.py` |
| 🔒 | Approvals | Approval queue + trust registry | `core/approval_gate.py` |
| 💰 | Costs | Cost dashboard + policy settings | `core/cost_tracker.py` |
| 🧠 | Memory | Memory inspector drawer | `core/memory_router.py` |
| 🔧 | Tools | Tool call inspector + testing battery | `skills/testing_battery/skill.py` |
| ⚙ | Settings | Global settings drawer | Multiple |
| ? | Help | Keyboard shortcuts + docs | Static |

**Hover expansion:** Sidebar expands to 200px on hover, showing labels. Icons remain visible when collapsed.

**Active indicator:** Amber left border (2px) on active nav item.

---

## 3. MAIN PANE (flexible, primary content)

**Inspired by:** Hermes center chat pane, but JArvis has two modes:

### Mode A: Terminal (default, no active task)
- xterm.js embed via WebSocket `/api/pty`
- Full Hermes parity: ANSI colors, box-drawing, mouse tracking
- `@xterm/addon-fit` on ResizeObserver
- Custom theme matching JArvis color tokens

### Mode B: Task Stream (when task is active)
When `orchestrator.process_task()` is running, the main pane switches to task-centric view:

```
┌─────────────────────────────────────┐
│ Task Detail Card                     │
│ ┌─────────────────────────────────┐ │
│ │ Intent: "Analyze weather data   │ │
│ │ Worker: ollama_worker           │ │
│ │ Status: ● EXECUTING             │ │
│ │ Confidence: 0.87                  │ │
│ │ Cost: $0.0042 | Tokens: 1,240   │ │
│ └─────────────────────────────────┘ │
│                                      │
│ Live Output Stream                   │
│ ┌─────────────────────────────────┐ │
│ │ > Parsing weather API response  │ │
│ │ > Extracting temperature data   │ │
│ │ > Generating summary...         │ │
│ │                                 │ │
│ │ [reasoning tokens streaming]  │ │
│ └─────────────────────────────────┘ │
│                                      │
│ Worker Output (when complete)        │
│ ┌─────────────────────────────────┐ │
│ │ {                               │ │
│ │   "summary": "Sunny, 22°C",    │ │
│ │   "confidence": 0.92           │ │
│ │ }                               │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

**Task Detail Card fields** (from `core/schemas.py:Task`):
- `intent` — task description
- `worker_id` — assigned worker
- `current_state` — RECEIVED / EXECUTING / VALIDATING / COMPLETE / FAILED / CANCELLED
- `confidence_score` — output confidence
- `cost_usd` — from `cost_tracker.record_usage()`
- `token_count` — tokens in + out
- `validation_failures` — retry count
- `created_at` / `completed_at` — timestamps

**State transitions** animate: EXECUTING → VALIDATING → COMPLETE with progress bar.

---

## 4. RIGHT PANEL (320px, tab switcher)

**Inspired by:** Hermes right panel (file browser). JArvis replaces files with operational dashboards.

### Tab 1: Tool Inspector (default)
From build plan §3.3 — live tool call log.

| Field | Source |
|---|---|
| Tool name | `TraceEvent.data["tool"]` |
| Status | `TraceEvent.event_type` (COMPONENT_START → OPERATION_COMPLETE/ERROR) |
| Duration | `TraceEvent.duration_ms` |
| Args | `TraceEvent.data` |
| Output | `WorkerOutput.result` |

### Tab 2: Session Timeline
From build plan §3.4 — Gantt-style phase segments.

| Field | Source |
|---|---|
| Phase segments | `orchestrator._task_history` (needs new field) |
| Duration | `completed_at - created_at` |
| Confidence | `Task.confidence_score` |
| Tool count | `len(tool_calls)` |

### Tab 3: Reasoning Stream
From build plan §3.5 — collapsible chain-of-thought.

| Field | Source |
|---|---|
| Reasoning tokens | `WorkerOutput.reasoning` (needs new field) or streaming from adapter |
| Token count | `len(reasoning_tokens)` |

### Tab 4: Circuit Breaker (when expanded)
**JArvis-specific** — not in Hermes. Shows worker circuit status.

```
┌─ Circuit Breaker ─────────────────┐
│ Workers: 5 total, 1 degraded     │
│                                    │
│ ollama_worker    ● CLOSED  0/3   │
│ multi_worker     ● CLOSED  0/3   │
│ prism_llama      ● OPEN    3/3 ⚠│  ← click to reset
│ web_search       ● CLOSED  1/3   │
│ code_exec        ● CLOSED  0/3   │
│                                    │
│ Degraded ratio: 20%              │
│ [Reset All Circuits]             │
└────────────────────────────────────┘
```

**Data source:** `WorkerCircuitBreaker.get_status()` + `get_degraded_worker_ratio()`

### Tab 5: Cost Dashboard (when expanded)
**JArvis-specific** — not in Hermes.

```
┌─ Cost Dashboard ──────────────────┐
│ Daily:  $4.20 / $10.00  ████░░  │
│ Monthly: $42.00 / $100.00 ████░░ │
│                                    │
│ Per-model breakdown:              │
│ GLM-4.5 Flash  $2.10  ████░░░░  │
│ Ollama (local) $0.00  ░░░░░░░░  │
│ Claude 3.5     $1.80  ███░░░░░  │
│ GPT-4o         $0.30  █░░░░░░░  │
│                                    │
│ [⚠ Alert at 80%] [↻ Fallback at 90%]
└────────────────────────────────────┘
```

**Data source:** `CostTracker.get_spend_summary()` + `get_model_spend()`

### Tab 6: Approval Queue (when expanded)
**JArvis-specific** — not in Hermes.

```
┌─ Pending Approvals ──────────────┐
│ 2 pending requests               │
│                                    │
│ ┌─ FILE_WRITE ──────────────────┐│
│ │ Create note: "Meeting notes"  ││
│ │ Risk: low | Expires: 2m       ││
│ │ [✓ Approve] [✗ Deny] [✓✓ Always]││
│ └─────────────────────────────────┘│
│                                    │
│ ┌─ CLOUD_ESCALATION ────────────┐│
│ │ Fall back to cloud: GPT-4o    ││
│ │ Risk: high | Expires: 4m      ││
│ │ [✓ Approve] [✗ Deny]          ││
│ └─────────────────────────────────┘│
└────────────────────────────────────┘
```

**Data source:** `ApprovalGate._pending_requests` (needs API endpoint)

---

## 5. BOTTOM BAR (64px)

**Inspired by:** Hermes token ring + composer footer. JArvis adds the activation grid.

### Left: Activation Grid (32×16 Canvas)
From build plan §3.2 — memory slot activations.

- 512 cells (32 cols × 16 rows)
- Cell size: 4px gap, scales with container
- Colors: slate (0–0.4), amber (0.4–0.7), emerald (0.7–1.0)
- Decay: −0.015/frame when not written
- Click → tooltip: slot index, timestamp, key, value preview
- Legend: `● Inactive ● Recall ● Write`

**Data source:** `/api/memory/activations` SSE stream

### Right: Token Counter + Context Bar
```
Tokens: 4,240 / 8,192  [████████░░░░░░░░] 52%
Context: 12% system | 23% memory | 65% conversation
```

**Data source:** `Task.token_count` + `StrategicContext` size estimate

---

## 6. MEMORY DRAWER (slide-in from right, 480px)

**Inspired by:** Hermes memory/context management. JArvis makes it explicit and inspectable.

```
┌─ Memory Inspector ─────────────────────────┐
│ [🔍 Search...]  [/]                        │
│                                            │
│ Slot #  Key              Value    Written  │
│ ───────────────────────────────────────────│
│ 042     notes:meeting    "Q2..."  2m ago   │
│ 128     global_context   {...}    5m ago   │
│ 256     worker:metrics   [...]    1h ago   │
│ 511     ░░░░░░░░░░░░░░░░ ░░░░░░  never     │
│                                            │
│ [↑] [↓] Sort  [Export ↓] [Import ↑]       │
│                                            │
│ Expanded row (click to expand):            │
│ ┌─────────────────────────────────────────┐│
│ │ Slot 042: notes:meeting                ││
│ │ Last written: 2026-06-26T13:15:00Z    ││
│ │ Activation: 0.85 ████████████░░░░      ││
│ │                                          ││
│ │ Value:                                   ││
│ │ {"title":"Q2 Review","content":"..."}    ││
│ │                                          ││
│ │ [Clear Slot]                            ││
│ └─────────────────────────────────────────┘│
└────────────────────────────────────────────┘
```

**Data source:** `MemoryRouter.fetch_by_filter()` + `scoped_read()`

---

## 7. SETTINGS DRAWER (slide-in from right, 480px)

**Inspired by:** Hermes Control Center (sidebar launcher). JArvis consolidates all config.

### Tab 1: Cost Policy
| Setting | Source | UI |
|---|---|---|
| Daily cap | `CostPolicy.daily_cap_usd` | Number input |
| Monthly cap | `CostPolicy.monthly_cap_usd` | Number input |
| Alert threshold | `CostPolicy.alert_threshold_pct` | Slider (0–100%) |
| Fallback threshold | `CostPolicy.fallback_threshold_pct` | Slider (0–100%) |
| Fallback model | `CostPolicy.fallback_model` | Model picker |

### Tab 2: Circuit Breaker
| Setting | Source | UI |
|---|---|---|
| Failure threshold | `WorkerCircuitBreaker._failure_threshold` | Number input |
| Reset timeout | `WorkerCircuitBreaker._reset_timeout` | Number input (seconds) |

### Tab 3: Sandbox
| Setting | Source | UI |
|---|---|---|
| Policy | `SandboxConfig.sandbox_policy` | Toggle: strict / fallback |
| Memory limit | `SandboxConfig.memory_limit` | Number input |
| CPU limit | `SandboxConfig.cpu_limit` | Number input |
| Timeout | `SandboxConfig.timeout` | Number input |

### Tab 4: Auth
| Setting | Source | UI |
|---|---|---|
| Bearer token | `AuthMiddleware` | Display + regenerate button |

---

## 8. TASKS PANEL (sidebar nav → 💬)

**JArvis-specific** — not in Hermes. Task management is central to Sovereign AI.

```
┌─ Tasks ────────────────────────────────────┐
│ [🔍 Search...]  [+ New Task]               │
│                                            │
│ Active (3)                                 │
│ ┌─ ● Analyze weather data                │
│ │   ollama_worker | EXECUTING | 45ms     │
│ │   [Cancel]                             │
│ └──────────────────────────────────────────│
│ ┌─ ○ Summarize email                     │
│ │   multi_worker | QUEUED | --           │
│ │   [Cancel]                             │
│ └──────────────────────────────────────────│
│                                            │
│ Completed (12)                             │
│ ┌─ ✓ Generate report                     │
│ │   prism_llama | COMPLETE | 2.3s | $0.01│
│ │   [View Output] [Rerun]                │
│ └──────────────────────────────────────────│
│                                            │
│ Failed (2)                                 │
│ ┌─ ✗ Parse PDF                           │
│ │   ollama_worker | FAILED | 0.5s      │
│ │   [View Error] [Retry]                 │
│ └──────────────────────────────────────────│
└────────────────────────────────────────────┘
```

**Data source:** `Orchestrator.list_tasks()` + `list_workers()`

---

## 9. WORKERS PANEL (sidebar nav → ⚡)

**JArvis-specific** — worker registry with circuit breaker integration.

```
┌─ Workers ──────────────────────────────────┐
│ 5 registered workers                       │
│                                            │
│ ┌─ ollama_worker ────────────────────────┐│
│ │ Type: local_llm | Capabilities: text   ││
│ │ Complexity: 0.5 | Preference: fast     ││
│ │ Circuit: ● CLOSED | Failures: 0/3      ││
│ │ Last used: 2m ago | Tasks: 42          │
│ │ [Deregister] [Reset Circuit]           ││
│ └──────────────────────────────────────────││
│                                            │
│ ┌─ prism_llama ──────────────────────────┐│
│ │ Type: local_llm | Capabilities: text   ││
│ │ Complexity: 0.8 | Preference: quality  ││
│ │ Circuit: ● OPEN ⚠ | Failures: 3/3     ││
│ │ Last used: 15m ago | Tasks: 12         ││
│ │ [Deregister] [Reset Circuit]           ││
│ └──────────────────────────────────────────││
│                                            │
│ [+ Register New Worker]                    │
└────────────────────────────────────────────┘
```

**Data source:** `Orchestrator.list_workers()` + `WorkerCircuitBreaker.get_status()`

---

## 10. SKILLS PANEL (sidebar nav → 🔧)

**Inspired by:** Hermes Skills tab. JArvis maps to actual skills.

```
┌─ Skills & Tools ───────────────────────────┐
│ [🔍 Search...]  [Categories ▼]             │
│                                            │
│ Notes               [● Enabled]            │
│ ├─ create, list, get, update, delete     │
│ ├─ search_by_tag                           │
│ └─ Requires: approval_gate, memory_router  │
│                                            │
│ Calendar            [● Enabled]            │
│ ├─ get_upcoming, create_event, cancel    │
│ └─ Requires: CALENDAR_ICS_PATH env var     │
│                                            │
│ Reminders           [● Enabled]            │
│ ├─ create, list_pending, mark_delivered  │
│ └─ Requires: approval_gate, memory_router  │
│                                            │
│ Testing Battery     [● Enabled]            │
│ ├─ run_battery (mypy, vulture, bandit)   │
│ ├─ Requires: sandbox_executor              │
│ └─ Quality threshold: 85%                  │
│                                            │
│ [Run Test Battery]  [Configure]            │
└────────────────────────────────────────────┘
```

**Data source:** Skill classes in `skills/` directory

---

## KEYBOARD SHORTCUTS

| Shortcut | Action | Context |
|---|---|---|
| `Space` | Run/Pause agent | Global (when no input focused) |
| `Ctrl+K` | Command palette | Global |
| `/` | Focus search | Memory drawer, Skills panel |
| `M` | Toggle memory drawer | Global |
| `T` | Toggle tasks panel | Global |
| `W` | Toggle workers panel | Global |
| `A` | Toggle approvals panel | Global |
| `C` | Toggle costs panel | Global |
| `Esc` | Close drawer/modal | Global |
| `Ctrl+Enter` | Submit task | Task input focused |

**Conflict resolution:** When xterm.js has focus, all shortcuts require `Ctrl+` prefix. When input element is focused, shortcuts are disabled.

---

## COLOR TOKENS (Tailwind v4 CSS vars)

From build plan §6, adapted for JArvis:

```css
:root {
  --color-surface-base:    #0c0c0f;
  --color-surface-raised:  #13131a;
  --color-surface-overlay: #1a1a24;
  --color-border:          #ffffff14;
  --color-border-strong:   #ffffff28;
  --color-text-primary:    #e8e6e0;
  --color-text-secondary:  #9b9890;
  --color-text-muted:      #5c5a56;
  --color-accent-amber:    #f59e0b;   /* primary: planning, active elements */
  --color-accent-emerald:  #10b981;   /* success, acting phase, closed circuit */
  --color-accent-violet:   #8b5cf6;   /* reflecting phase */
  --color-accent-red:      #ef4444;   /* error, open circuit, denied approval */
  --color-accent-slate:    #64748b;   /* idle, inactive, disabled */
  --color-accent-blue:     #3b82f6;   /* info, links, in-flight tools */
}
```

---

## RESPONSIVE BEHAVIOR

| Width | Layout Changes |
|---|---|
| ≥1280px (desktop) | Full three-panel layout |
| 1024–1279px | Right panel collapses to tab bar (320px → 48px icons, click to expand) |
| <1024px | Not supported (desktop-only per build plan §9) |

---

## DATA FLOW ARCHITECTURE

```
┌─────────────┐     SSE/WebSocket      ┌─────────────┐
│   Backend   │ ◄────────────────────► │   Frontend  │
│  (FastAPI)  │                        │  (Next.js)  │
└─────────────┘                        └─────────────┘
       │                                      │
       │  ┌────────────────────────────────┐  │
       ├──┤ 1. /api/status (polling 2s)    ├──┤  │ Status bar
       │  │    → phase, session, latency   │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 2. /api/tasks (polling 2s)     ├──┤  │ Tasks panel
       │  │    → active/completed/failed   │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 3. /api/workers (polling 5s)   ├──┤  │ Workers panel
       │  │    → registry + circuit status   │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 4. /api/approvals/pending      ├──┤  │ Approvals panel
       │  │    (polling 2s)                │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 5. /api/costs/summary          ├──┤  │ Cost dashboard
       │  │    (polling 10s)               │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 6. /api/memory/activations     ├──┤  │ Activation grid
       │  │    (SSE stream)                │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 7. /api/tools/stream           ├──┤  │ Tool inspector
       │  │    (SSE stream)                │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 8. /api/agent/reasoning        ├──┤  │ Reasoning stream
       │  │    (SSE stream)                │  │
       │  ├────────────────────────────────┤  │
       ├──┤ 9. /ws (WebSocket)             ├──┤  │ Terminal (xterm.js)
       │  │    → PTY bidirectional         │  │
       │  └────────────────────────────────┘  │
       │                                      │
       │  ┌────────────────────────────────┐  │
       └──┤ POST /api/tasks              ├──┘  │ Task submission
          │ POST /api/approvals/{id}/respond    │ Approval response
          │ POST /api/circuit-breaker/reset     │ Circuit reset
          │ POST /api/memory/import             │ Memory import
          └────────────────────────────────┘
```

---

## MISSING API ENDPOINTS (Critical for v1)

| Endpoint | Method | For Panel | Priority |
|---|---|---|---|
| `/api/approvals/pending` | GET | Approvals | CRITICAL |
| `/api/approvals/{id}/respond` | POST | Approvals | CRITICAL |
| `/api/costs/summary` | GET | Cost dashboard | CRITICAL |
| `/api/costs/daily` | GET | Cost dashboard | CRITICAL |
| `/api/costs/monthly` | GET | Cost dashboard | HIGH |
| `/api/circuit-breaker/status` | GET | Workers | CRITICAL |
| `/api/circuit-breaker/reset` | POST | Workers | CRITICAL |
| `/api/memory/slots` | GET | Memory drawer | CRITICAL |
| `/api/memory/export` | GET | Memory drawer | HIGH |
| `/api/memory/import` | POST | Memory drawer | HIGH |
| `/api/skills` | GET | Skills panel | MEDIUM |
| `/api/skills/{name}/run` | POST | Skills panel | MEDIUM |
| `/api/sessions/{id}/timeline` | GET | Session timeline | MEDIUM |
| `/api/subagents` | GET | Subagent panel | LOW |
| `/api/subagents/{id}` | DELETE | Subagent panel | LOW |

---

## IMPLEMENTATION PRIORITY

1. **Shell layout** — CSS Grid, status bar, sidebar, bottom bar
2. **Backend stubs** — all API endpoints returning mocked data
3. **usePolling hook** — generic polling with configurable interval
4. **useSSE hook** — generic SSE with reconnect
5. **Terminal pane** — xterm.js + WebSocket PTY
6. **Tasks panel** — task list + detail card
7. **Tool inspector** — tool call log (highest info density)
8. **Activation grid** — Canvas 2D with simulated data
9. **Workers panel** — registry + circuit breaker status
10. **Approvals panel** — queue + respond
11. **Cost dashboard** — spend gauges + breakdown
12. **Memory drawer** — table + search + export/import
13. **Settings drawer** — cost policy, circuit breaker, sandbox
14. **Skills panel** — skill registry + test battery runner
15. **Session timeline** — SVG Gantt
16. **Reasoning stream** — collapsible CoT
17. **Subagent panel** — polling cards

---

*Design specification complete. All UI elements traced to specific methods in the Sovereign AI codebase.*
