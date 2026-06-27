# Sovereign AI — UI/UX Gap Analysis & Remediation Roadmap

**Prepared for**: GLM (Prompt Creator)
**Date**: 2026-06-26
**Repo State**: Post-Plan 87, `prompt-87` tag, `03a2fe7` commit
**Scope**: Web UI (Next.js 15 + TypeScript + Tailwind v4), CLI (Textual TUI + Rich CLI), and Backend API (FastAPI)

> **⚠️ ARCHITECTURE UPDATE (2026-06-27, commit `c48ce4c`)**: The Next.js 15 + TypeScript + Tailwind v4 frontend described in this document was **abandoned and removed**. The current web UI is **vanilla JavaScript** in `web/static/`, served by FastAPI `StaticFiles` at the same origin as the API. See `DECISIONS.md` Decision 11, `LANDMINES.md` L23, and `AGENTS.md` AR21b for full context. The gap analysis below is still valid — the UI-UX gaps it identifies (model management, worker creation, debate UI, security panels, observability, etc.) apply equally to the vanilla JS UI. However, all `src/components/panels/*.tsx`, `src/stores/*.ts`, `src/hooks/*.ts`, and `src/lib/api.ts` file path references throughout this document are **historical** — the equivalent files now live in `web/static/*.js` (e.g., `web/static/workers.js` ≈ old `src/components/panels/WorkersPanel.tsx`). Plans 96–99 should target the vanilla JS UI, not the deleted React components.

---

## Executive Summary

The Sovereign AI backend has **~30 major subsystems** operational or partially built. The Web UI exposes **only ~8 of them** through clickable interfaces. The CLI exposes **~12**. This leaves the majority of the framework's capabilities **invisible and unreachable** to users — including model management, adapter selection, worker creation, skill configuration, debate orchestration, cost controls, and security settings.

This document catalogs every gap, maps it to existing backend capabilities, and proposes a phased remediation approach that GLM can turn into concrete plans.

---

## 1. Methodology: How This Analysis Was Built

1. **Backend inventory**: Scanned all Python modules in `core/`, `system/`, `adapters/`, `memory/`, `skills/`, `workers/`, `cli/`, `api/`, `backend/`, `web/`, `evals/`, `orchestrator/`
2. **CLI inventory**: Read `cli/tui.py`, `cli/rich_cli.py`, `cli/main.py`, `core/commands.py`, `core/handlers.py`
3. **Web UI inventory**: Read all `src/components/panels/`, `src/components/shell/`, `src/stores/`, `src/hooks/`, `src/lib/api.ts`
4. **API inventory**: Read `backend/main.py`, `web/server.py`, `api/main.py`, `api/websocket.py`
5. **Cross-reference**: Mapped every backend capability against every UI surface to find disconnects

---

## 2. The Gap Matrix: Backend Capabilities vs. UI Exposure

### 2.1 LLM Model & Adapter Management

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **15 LLM Adapters** (Ollama, OpenAI, Anthropic, Groq, Gemini, DeepSeek, Mistral, Cohere, Together, LM Studio, Llama.cpp, PrismLLaMA, HuggingFace, MCP) | Operational | `/adapter` command | **None** | **CRITICAL** |
| **Model Registry** (`system/model_registry.py`) — tracks model requirements, compatibility, download status | Operational | None | **None** | **CRITICAL** |
| **Model Acquisition** (`system/model_acquisition.py`) — HuggingFace search/download, Ollama pull, quantisation variants | Operational | None | **None** | **CRITICAL** |
| **Model Evaluator** (`system/model_evaluator.py`) — recommends best model for task + hardware | Operational | None | **None** | **HIGH** |
| **Model Tier Router** (`core/model_tier_router.py`) — SIMPLE/MEDIUM/COMPLEX routing with cost downgrade | Operational | None | **None** | **HIGH** |
| **Adapter Fallback Chain** (`core/adapter_fallback.py`) — automatic failover between adapters | Operational | None | **None** | **HIGH** |

**Current UI State**:
- `StatusBar.tsx` shows hardcoded `modelSlug: "GLM-4.5 Flash"` with `title="Coming in Plan 89"` tooltip
- `agentStore.ts` has `setModel()` but no UI calls it
- No adapter configuration panel
- No model browser/downloader
- No hardware compatibility check before model selection

---

### 2.2 Worker & Agent Management

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Worker Factory** (`core/worker_factory.py`) — create workers from natural language descriptions | Operational | None | **None** | **CRITICAL** |
| **Dynamic Worker Profiles** (`DynamicWorkerProfile`) — complexity, depth, verbosity, skepticism preferences | Operational | None | **None** | **HIGH** |
| **Worker Circuit Breaker** (`core/worker_circuit_breaker.py`) — failure tracking, auto-reset, degraded mode | Operational | Partial (reset button only) | Partial (status badge only) | **MEDIUM** |
| **Multi-Worker** (`core/multi_worker.py`) — parallel worker dispatch | Operational | None | **None** | **HIGH** |
| **Worker Persistence** (`system/worker_persistence.py`) — save/load worker state | Operational | None | **None** | **MEDIUM** |

**Current UI State**:
- `WorkersPanel.tsx` shows worker list with circuit status badge and "Reset Circuit" button
- No worker creation UI
- No worker configuration (complexity, model preference, capabilities)
- No worker persistence controls

---

### 2.3 Skill & Tool Management

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Skill Registry** (`core/skill_registry.py`) — discovers 25+ skills from `skills/` directory | Operational | None | Partial (list + toggle only) | **MEDIUM** |
| **Skill Taxonomy** (`core/skill_taxonomy.py`) — USER_INVOKED / AGENT_INVOKED / HYBRID tiers | Operational | None | Partial (tier badge only) | **MEDIUM** |
| **Skill Parameters** (`SkillMetadata.parameters`) — input/output schemas, dependencies, hardware reqs | Operational | None | **None** | **HIGH** |
| **Tool Inspector** (`RightPanel.tsx` "tools" tab) — real-time tool call monitoring | Operational | None | Partial (`ToolInspector` component exists but minimal) | **MEDIUM** |

**Current UI State**:
- `SkillsPanel.tsx` lists skills, shows tier badge, toggle enabled/disabled, run test battery
- No skill parameter configuration
- No skill dependency visualization
- No skill hardware requirement display
- ToolInspector exists but is minimal

---

### 2.4 Debate & Expert Panel System (PEMADS)

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Debate Pool** (`memory/debate_pool.py`) — multi-round debate orchestration | Operational | None | **None** | **CRITICAL** |
| **Expert Panel Manager** (`core/expert_panel_manager.py`) — expert registration, selection, debate triggering | Operational | None | **None** | **CRITICAL** |
| **PEMADS Judge** (Plan 88 scope) — evaluates debate quality, gates implementation | Planned | None | **None** | **HIGH** |
| **Implementation Gate** (Plan 88 scope) — quality threshold + approval before code changes | Planned | None | **None** | **HIGH** |

**Current UI State**:
- No debate UI whatsoever
- No expert panel configuration
- No debate result viewer
- Plan 88 (current) covers Judge + Implementation Gate backend — no UI scope

---

### 2.5 Cost, Budget & Resource Management

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Cost Tracker** (`core/cost_tracker.py`) — daily/monthly caps, alerts, tier downgrade | Operational | None | Partial (dashboard display only) | **HIGH** |
| **Resource Budget** (`core/resource_budget.py`) — VRAM/RAM/CPU budget enforcement | Operational | None | **None** | **HIGH** |
| **VRAM Manager** (`core/vram_manager.py`) — GPU memory tracking and allocation | Operational | None | Partial (`/api/vram/status` endpoint exists) | **MEDIUM** |
| **Resource Manager** (`system/resource_manager.py`) — system-wide resource coordination | Operational | None | **None** | **MEDIUM** |

**Current UI State**:
- `CostDashboardPanel.tsx` shows daily/monthly spend bars with hardcoded caps ($10/$100)
- `SettingsDrawer.tsx` has Cost Policy tab with **disabled inputs** (`opacity-50`, `data-mocked="Coming in Plan 89"`)
- No actual cost configuration possible
- No VRAM visualization (endpoint exists but no UI component)
- No resource budget configuration

---

### 2.6 Security, Approval & Sandbox

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Approval Gate** (`core/approval_gate.py`) — multi-risk-level approval requests | Operational | None | Partial (approve/deny buttons only) | **MEDIUM** |
| **Approval Trust Registry** (`core/approval_trust.py`) — auto-approve trusted actions | Operational | None | **None** | **HIGH** |
| **Multi-Channel Approvals** (Plan 89 scope) — Web/Telegram/Email channels | Planned | None | **None** | **HIGH** |
| **Sandbox Executor** (`core/sandbox.py`) — Docker-isolated code execution | Operational | None | **None** | **CRITICAL** |
| **Input Sanitiser** (`core/input_sanitiser.py`) — security filtering on all inputs | Operational | None | **None** | **HIGH** |

**Current UI State**:
- `ApprovalQueuePanel.tsx` shows pending approvals with risk badge and approve/deny buttons
- No trust registry configuration
- No sandbox execution viewer/logs
- No input sanitiser status/controls

---

### 2.7 Communication & Integration

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **A2A Protocol** (`core/a2a_protocol.py`) — agent-to-agent communication | Operational | None | **None** | **HIGH** |
| **Telegram Gateway** (`gateways/telegram/`) — Telegram bot integration | Operational | None | **None** | **MEDIUM** |
| **Voice Interface** (`core/voice_interface.py`, `system/voice_daemon.py`) — TTS/STT | Operational | None | **None** | **MEDIUM** |
| **Audio Capture** (`system/audio_capture.py`) — microphone input | Operational | None | **None** | **MEDIUM** |
| **Notification System** (`core/notification.py`) — push notifications | Operational | None | **None** | **MEDIUM** |
| **Event Trigger** (`core/event_trigger.py`) — background task triggers | Operational | None | **None** | **MEDIUM** |

**Current UI State**:
- No gateway configuration UI
- No voice controls
- No notification center
- No event trigger management

---

### 2.8 Observability, Tracing & Diagnostics

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Trace Emitter** (`core/observability.py`) — structured event logging | Operational | None | **None** | **HIGH** |
| **Trace Optimiser** (`core/trace_optimiser.py`) — trace deduplication and compression | Operational | None | **None** | **MEDIUM** |
| **Postgres Trace Store** (`memory/postgres_trace_store.py`) — persistent trace storage | Operational | None | **None** | **MEDIUM** |
| **System Profiler** (`system/profiler.py`) — performance profiling | Operational | None | **None** | **MEDIUM** |
| **Monitor Daemon** (`system/monitor_daemon.py`) — background system monitoring | Operational | None | **None** | **MEDIUM** |
| **Retention Manager** (`system/retention_manager.py`) — data retention policies | Operational | None | **None** | **MEDIUM** |

**Current UI State**:
- `SystemStatsPanel.tsx` — minimal placeholder (not found in components, may not exist)
- `RightPanel.tsx` "Timeline" tab — placeholder text: "Session timeline — placeholder. Full implementation deferred"
- `RightPanel.tsx` "Reasoning" tab — placeholder text: "Reasoning stream — placeholder. Full implementation deferred"
- No trace viewer
- No profiler output display
- No retention policy configuration

---

### 2.9 Session, Memory & State Management

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Session Manager** (`core/session.py`) — session creation, persistence, switching | Operational | Via CLI | **None** | **HIGH** |
| **Command History** (`cli/command_history.py`) — persistent command history | Operational | Via CLI | **None** | **MEDIUM** |
| **Memory Router** (`core/memory_router.py`) — unified memory access | Operational | None | Partial (MemoryDrawer slots only) | **MEDIUM** |
| **Debate Pool** (`memory/debate_pool.py`) — debate persistence | Operational | None | **None** | **HIGH** |
| **Obsidian Backend** (`memory/obsidian.py`) — Obsidian vault integration | Operational | None | **None** | **LOW** |
| **Qdrant Backend** (`memory/qdrant.py`) — vector DB integration | Operational | None | **None** | **LOW** |

**Current UI State**:
- `MemoryDrawer.tsx` — search/sort/export/import memory slots
- No session management (create, switch, rename, delete sessions)
- No command history browser
- No debate pool viewer
- No Obsidian/Qdrant configuration

---

### 2.10 Self-Improvement & Evaluation

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Eval Harness** (`evals/harness.py`) — model evaluation with 4 metrics | Operational | None | **None** | **HIGH** |
| **Improvement Loop** (`orchestrator/improvement_loop.py`) — self-improvement orchestration | Operational | None | **None** | **HIGH** |
| **Auto Corrector** (`core/auto_corrector.py`) — automatic error correction | Operational | None | **None** | **MEDIUM** |
| **Rating System** (`core/rating_system.py`) — output quality rating | Operational | None | **None** | **MEDIUM** |

**Current UI State**:
- No eval harness UI
- No improvement loop trigger/viewer
- No auto corrector status
- No rating system UI

---

### 2.11 Task & Orchestration

| Backend Capability | Status | CLI Exposure | Web UI Exposure | Gap Severity |
|---|---|---|---|---|
| **Orchestrator** (`core/orchestrator.py`) — task routing, dispatch, coordination | Operational | Via CLI | Partial (TasksPanel shows list only) | **MEDIUM** |
| **Task Classifier** (`core/task_classifier.py`) — automatic task categorization | Operational | None | **None** | **MEDIUM** |
| **Task State Machine** (`core/task_state_machine.py`) — state transitions | Operational | None | **None** | **MEDIUM** |
| **Escalation Engine** (`core/escalation.py`) — cloud fallback on local failure | Operational | None | **None** | **HIGH** |
| **Scratchpad** (`core/scratchpad.py`) — intermediate reasoning storage | Operational | None | **None** | **MEDIUM** |

**Current UI State**:
- `TasksPanel.tsx` — lists tasks by status (Active/Completed/Failed), shows priority and creation time
- No task creation UI
- No task detail view (steps, reasoning, scratchpad)
- No escalation configuration
- No task classifier configuration

---

## 3. Critical UI Gaps Requiring Immediate Attention

### 3.1 Gap #1: Model & Adapter Selection (CRITICAL)

**Problem**: The framework supports 15 LLM adapters. The Web UI supports 0. The StatusBar shows a hardcoded model name with a "Coming in Plan 89" tooltip that has been there since at least Plan 83.

**Backend Support**:
- `cli/adapter_factory.py` creates adapters by name
- `core/adapter_fallback.py` manages fallback chains
- `system/model_registry.py` tracks model metadata
- `system/model_acquisition.py` searches/downloads from HuggingFace
- `system/model_evaluator.py` recommends models based on hardware + task

**What the UI Needs**:
1. **Model Browser Panel** — browse installed models from registry with filtering by task type, hardware compatibility, quantisation
2. **Model Downloader** — search HuggingFace/Ollama catalogues, select quantisation variant, download with progress, verify checksum
3. **Adapter Selector** — dropdown/config panel to switch active adapter, configure API keys, test connection
4. **Fallback Chain Editor** — drag-and-drop or ordered list to configure adapter priority for failover
5. **Hardware Compatibility Check** — before downloading/running a model, check VRAM/RAM requirements against current system

---

### 3.2 Gap #2: Worker Creation & Configuration (CRITICAL)

**Problem**: Workers are the primary execution units. The UI shows a read-only list with circuit status. Users cannot create, configure, or customize workers.

**Backend Support**:
- `core/worker_factory.py` creates workers from natural language descriptions
- `DynamicWorkerProfile` has 15+ configurable parameters (complexity, depth, verbosity, skepticism, preferred model, etc.)
- `core/worker_base.py` defines the worker interface

**What the UI Needs**:
1. **Worker Creator** — natural language input ("Create a Python code review worker") generates profile
2. **Worker Editor** — modify complexity range, verbosity, preferred model, capabilities, standing instructions
3. **Worker Cloner** — duplicate existing worker with modifications
4. **Worker Tester** — run a test task against a worker and show results

---

### 3.3 Gap #3: Debate & Expert Panel UI (CRITICAL)

**Problem**: PEMADS (Plan 76-88) is a major feature arc. The backend has debate pools, expert panels, judges, and implementation gates. The UI has nothing.

**Backend Support**:
- `memory/debate_pool.py` — debate rounds, persistence, scoring
- `core/expert_panel_manager.py` — expert registration, selection, triggering
- Plan 88 adds PEMADSJudge and ImplementationGate

**What the UI Needs**:
1. **Expert Panel Configurator** — register experts, assign models, set expertise domains
2. **Debate Trigger** — select task, choose experts, set rounds, start debate
3. **Debate Viewer** — real-time or replay of debate rounds, expert responses, judge scores
4. **Implementation Gate** — view quality threshold, judge recommendation, approve/reject implementation

---

### 3.4 Gap #4: Cost & Resource Controls (HIGH)

**Problem**: Cost Tracker and Resource Budget exist but are display-only (and even then, settings are mocked). Users cannot configure budgets, set alerts, or view resource allocation.

**Backend Support**:
- `core/cost_tracker.py` — daily/monthly caps, alert thresholds, fallback thresholds, tier downgrade
- `core/resource_budget.py` — VRAM/RAM/CPU budgets
- `core/vram_manager.py` — GPU memory tracking

**What the UI Needs**:
1. **Cost Policy Editor** — editable daily/monthly caps, alert/fallback thresholds, per-model cost limits
2. **Resource Monitor** — real-time CPU/RAM/VRAM/Disk usage with history charts
3. **Budget Alerts** — configure notification channels (in-app, Telegram, email) for threshold breaches
4. **Cost Breakdown** — per-adapter, per-model, per-task cost attribution

---

### 3.5 Gap #5: Security & Sandbox Visibility (HIGH)

**Problem**: Sandbox execution and approval trust are critical security features. The UI has no visibility into them.

**Backend Support**:
- `core/sandbox.py` — Docker-isolated execution
- `core/approval_trust.py` — trust registry for auto-approval
- `core/input_sanitiser.py` — security filtering

**What the UI Needs**:
1. **Sandbox Dashboard** — view running containers, execution logs, resource usage
2. **Trust Registry Editor** — add/remove trusted patterns, view auto-approval history
3. **Input Sanitiser Status** — show filtering rules, recent blocked inputs, false positive reporting

---

## 4. API Endpoint Inventory: What's Already Exposed vs. What's Missing

### 4.1 Existing Backend API Endpoints (`backend/main.py` + `web/server.py`)

| Endpoint | Purpose | UI Consumer |
|---|---|---|
| `GET /health` | Health check | None (indirect) |
| `GET /api/status` | Agent status | `useStatusPolling` |
| `GET /api/tasks` | Task list | `TasksPanel` |
| `POST /api/tasks` | Create task | **No UI** |
| `GET /api/workers` | Worker list | `WorkersPanel` |
| `GET /api/subagents` | Subagent list | `SubagentPanel` |
| `DELETE /api/subagents/{id}` | Kill subagent | `SubagentPanel` |
| `GET /api/agent/reasoning` | SSE reasoning stream | **No UI** (placeholder in RightPanel) |
| `GET /api/tools/stream` | SSE tool stream | `ToolInspector` (partial) |
| `GET /api/memory/activations` | SSE activation stream | `BottomBar` (partial) |
| `GET /api/costs/summary` | Cost summary | `CostDashboardPanel` |
| `GET /api/costs/daily` | Daily cost breakdown | **No UI** |
| `GET /api/circuit-breaker/status` | Circuit breaker status | `WorkersPanel` (partial) |
| `POST /api/workers/reset-circuit` | Reset circuit | `WorkersPanel` |
| `GET /api/approvals/pending` | Pending approvals | `ApprovalQueuePanel` |
| `POST /api/approvals/{id}/respond` | Respond to approval | `ApprovalQueuePanel` |
| `GET /api/vram/status` | VRAM status | **No UI** |
| `GET /api/memory/slots` | Memory slots | `MemoryDrawer` |
| `GET /api/memory/slots/export` | Export memory | `MemoryDrawer` |
| `POST /api/memory/slots/import` | Import memory | `MemoryDrawer` |
| `DELETE /api/memory/slots/{id}` | Clear slot | `MemoryDrawer` |
| `GET /api/skills` | Skill list | `SkillsPanel` |
| `POST /api/skills/{name}/toggle` | Toggle skill | `SkillsPanel` |
| `POST /api/skills/testing_battery/run` | Run test battery | `SkillsPanel` |
| `GET /api/sessions/{id}/timeline` | Session timeline | **No UI** (placeholder) |
| `WS /api/pty` | PTY terminal | `TerminalPanel` |

### 4.2 Missing API Endpoints (Backend Has Code, No API Surface)

| Backend Module | Missing Endpoints | Needed For |
|---|---|---|
| `system/model_registry.py` | `GET /api/models`, `GET /api/models/{id}`, `POST /api/models/register`, `DELETE /api/models/{id}` | Model Browser |
| `system/model_acquisition.py` | `GET /api/models/search?query=`, `POST /api/models/download`, `GET /api/models/download/{id}/status` | Model Downloader |
| `system/model_evaluator.py` | `POST /api/models/evaluate`, `GET /api/models/recommendations` | Model Evaluator UI |
| `core/worker_factory.py` | `POST /api/workers/create`, `PUT /api/workers/{id}`, `DELETE /api/workers/{id}` | Worker Creator |
| `core/skill_registry.py` | `GET /api/skills/{name}/details`, `PUT /api/skills/{name}/config` | Skill Configurator |
| `memory/debate_pool.py` | `GET /api/debates`, `POST /api/debates`, `GET /api/debates/{id}`, `POST /api/debates/{id}/rounds` | Debate Viewer |
| `core/expert_panel_manager.py` | `GET /api/experts`, `POST /api/experts`, `DELETE /api/experts/{id}` | Expert Panel Config |
| `core/cost_tracker.py` | `PUT /api/costs/policy`, `GET /api/costs/alerts` | Cost Policy Editor |
| `core/vram_manager.py` | `GET /api/vram/allocations`, `POST /api/vram/release` | Resource Monitor |
| `core/approval_trust.py` | `GET /api/approvals/trust`, `PUT /api/approvals/trust` | Trust Registry |
| `core/sandbox.py` | `GET /api/sandbox/containers`, `GET /api/sandbox/logs/{id}` | Sandbox Dashboard |
| `core/session.py` | `GET /api/sessions`, `POST /api/sessions`, `PUT /api/sessions/{id}` | Session Manager |
| `evals/harness.py` | `POST /api/evals/run`, `GET /api/evals/results` | Eval Harness UI |
| `orchestrator/improvement_loop.py` | `POST /api/improvements/trigger`, `GET /api/improvements` | Improvement Loop UI |

---

## 5. CLI vs. Web UI Feature Parity

| Feature | CLI (Textual/Rich) | Web UI | Gap |
|---|---|---|---|
| Natural language query | `/query` or direct input | TerminalPanel | Parity |
| Model switch | `/model` | **Missing** | CLI ahead |
| Adapter switch | `/adapter` | **Missing** | CLI ahead |
| Session management | Via `SessionManager` | **Missing** | CLI ahead |
| Command history | `CommandHistory` | **Missing** | CLI ahead |
| Worker list | Displayed | `WorkersPanel` | Parity |
| Worker creation | **Missing** | **Missing** | Both missing |
| Skill toggle | **Missing** | `SkillsPanel` | Web ahead |
| Approval respond | **Missing** | `ApprovalQueuePanel` | Web ahead |
| Cost view | **Missing** | `CostDashboardPanel` | Web ahead |
| Memory slots | **Missing** | `MemoryDrawer` | Web ahead |
| Settings | **Missing** | `SettingsDrawer` (mocked) | Web ahead (barely) |

**Key insight**: The CLI has model/adapter switching that the Web UI completely lacks. This is the most glaring parity gap.

---

## 6. Recommended Remediation Plan (Phased)

### Phase 1: Foundation — Model & Adapter Management (Plans 92-93)
**Priority**: CRITICAL | **User Impact**: Highest

1. **Model Registry API** — expose `GET /api/models`, `GET /api/models/{id}` endpoints
2. **Model Browser Panel** — new `ModelsPanel.tsx` with filtering, sorting, compatibility badges
3. **Adapter Selector** — dropdown in StatusBar or new panel to switch active adapter
4. **Model Store** — new Zustand store for model state
5. **Backend Integration** — wire `ModelRegistry` to API endpoints

### Phase 2: Worker Management (Plan 94)
**Priority**: CRITICAL | **User Impact**: High

1. **Worker Factory API** — expose `POST /api/workers/create`, `PUT /api/workers/{id}`
2. **Worker Creator UI** — natural language input + advanced parameter editor
3. **Worker Detail View** — click worker to see profile, capabilities, task history
4. **Worker Store Updates** — extend `workerStore.ts` with creation/editing actions

### Phase 3: Cost & Resource Controls (Plan 95 or Scan 96)
**Priority**: HIGH | **User Impact**: High

1. **Cost Policy API** — expose `PUT /api/costs/policy` (un-mock the SettingsDrawer)
2. **Resource Monitor Panel** — real-time CPU/RAM/VRAM charts
3. **Alert Configuration** — threshold editing with save functionality

### Phase 4: Debate & Expert Panel (Plans 97-98)
**Priority**: HIGH | **User Impact**: Medium-High (depends on PEMADS usage)

1. **Expert Panel API** — CRUD endpoints for experts
2. **Debate API** — create, view, and manage debates
3. **Debate Viewer Panel** — real-time debate display with judge scores
4. **Implementation Gate UI** — quality threshold display, approve/reject buttons

### Phase 5: Security & Observability (Plans 99-100)
**Priority**: MEDIUM | **User Impact**: Medium

1. **Sandbox Dashboard** — container list, logs, execution history
2. **Trust Registry Editor** — add/remove trusted patterns
3. **Trace Viewer** — search, filter, visualize trace events
4. **Session Manager** — create, switch, rename, delete sessions

### Phase 6: Advanced Features (Plans 101+)
**Priority**: LOW | **User Impact**: Low-Medium

1. **Eval Harness UI** — run evaluations, view metrics over time
2. **Improvement Loop UI** — trigger improvements, view suggestions
3. **Voice Controls** — push-to-talk, voice settings
4. **Gateway Configurator** — Telegram bot settings, webhook configuration
5. **Notification Center** — in-app notification history and preferences

---

## 7. Specific Technical Recommendations

### 7.1 Frontend Architecture

1. **Add a `modelStore.ts`** — Zustand store for model state (installed models, active model, download progress)
2. **Add a `resourceStore.ts`** — Zustand store for system resources (CPU, RAM, VRAM usage)
3. **Extend `agentStore.ts`** — Add `availableModels`, `availableAdapters`, `setAdapter()` actions
4. **Create `ModelsPanel.tsx`** — New main panel for model browsing
5. **Create `ModelDownloader.tsx`** — Modal or panel for HuggingFace/Ollama search and download
6. **Un-mock `SettingsDrawer.tsx`** — Remove `opacity-50` and `disabled` attributes, wire to real API endpoints

### 7.2 Backend API Additions

1. **Create `api/models.py`** — FastAPI router for model registry endpoints
2. **Create `api/workers.py`** — FastAPI router for worker CRUD endpoints
3. **Create `api/debates.py`** — FastAPI router for debate/expert endpoints
4. **Create `api/resources.py`** — FastAPI router for system resource endpoints
5. **Wire routers in `web/server.py`** — Add `app.include_router()` calls

### 7.3 CLI Parity

1. **Add `/model` and `/adapter` to TUI** — The Rich CLI has these; the Textual TUI should too
2. **Add session management to TUI** — List, switch, create sessions
3. **Add command history browser to TUI** — Searchable history with reuse

---

## 8. Files That Need Creation/Modification

### New Files (Frontend)
- `src/stores/modelStore.ts`
- `src/stores/resourceStore.ts`
- `src/components/panels/ModelsPanel.tsx`
- `src/components/panels/ModelDownloader.tsx`
- `src/components/panels/WorkerDetailPanel.tsx`
- `src/components/panels/ResourceMonitorPanel.tsx`
- `src/components/panels/DebatePanel.tsx`
- `src/components/panels/ExpertPanel.tsx`
- `src/components/panels/SandboxPanel.tsx`
- `src/components/panels/SessionManagerPanel.tsx`

### New Files (Backend)
- `api/models.py`
- `api/workers.py`
- `api/debates.py`
- `api/resources.py`
- `api/sessions.py`
- `api/sandbox.py`

### Modified Files (Frontend)
- `src/stores/uiStore.ts` — add `VIEWS.MODELS`, `VIEWS.RESOURCES`
- `src/stores/agentStore.ts` — add model/adapter management
- `src/components/shell/Sidebar.tsx` — add Models, Resources nav items
- `src/components/panels/SettingsDrawer.tsx` — un-mock cost settings, add adapter config
- `src/components/shell/StatusBar.tsx` — make model slug clickable, show adapter selector

### Modified Files (Backend)
- `web/server.py` — include new routers
- `backend/main.py` — add missing endpoints or consolidate into `web/server.py`

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Backend API bloat** — adding 20+ endpoints without proper testing | Medium | High | Add tests incrementally; follow Plan 80-81 pattern (backend tests per endpoint) |
| **Frontend state explosion** — too many Zustand stores | Low | Medium | Consolidate related state; use derived stores where possible |
| **Security exposure** — model download API could be abused | Medium | High | Require approval for downloads >1GB; use approval gate |
| **Performance** — real-time resource monitoring could be expensive | Medium | Medium | Use SSE for push updates, not polling; sample every 5s |
| **Scope creep** — UI work could expand to consume all plans | High | High | Strict phased approach; each phase is a standalone plan with STOP conditions |

---

## 10. Conclusion

The Sovereign AI backend is **significantly more capable than its UI surfaces suggest**. The Web UI is currently a **dashboard shell** — it displays status but offers minimal control. The CLI is slightly better (model/adapter switching) but still lacks worker creation, debate management, and configuration controls.

**The highest-impact fixes** (in order):
1. **Model/Adapter Selection** — unblocks users from using the 15 adapters they've built
2. **Worker Creation** — unblocks users from leveraging the dynamic worker system
3. **Cost Controls** — unblocks users from actually using the budget system (currently mocked)
4. **Debate/Expert Panel** — unblocks the PEMADS feature arc from being usable

These four items should be the **next 4-plan batch** (Plans 92-95) after the current PEMADS batch (88-91) completes. Each item is substantial enough to be its own plan, and each has clear backend support — the work is primarily **API exposure + frontend components**, not new backend architecture.

---

**Document prepared by**: Kimi (Prompt Creator substitute)
**For**: GLM (Primary Prompt Creator)
**Action**: Convert Phase 1-3 into concrete plan files for Devin execution.
