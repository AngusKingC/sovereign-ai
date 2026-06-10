# Sovereign AI Agent Framework — Project Handoff Document

## Purpose
This document is a complete handoff brief for a prompting agent continuing
development of the Sovereign AI Agent Framework. It contains the project
vision, current state, completed work, and every remaining implementation
in order.

**Maintained by**: Devin — updated after every prompt as part of standard closing steps. Claude reads this document at session start but does not write to it.

**Last updated**: 2026-06-10 — post Prompt 22 completion + competitive
landscape review incorporated (Hermes Agent, OpenJarvis, LangGraph, CrewAI,
AutoGPT, OpenHands, SuperAGI, Google ADK, OpenAI Agents SDK, Microsoft Agent
Framework reviewed and actioned by Claude). Six new features added to roadmap:
MCP Adapter (22.5), Trace-Based Skill Optimiser (22.6), crash-resume extended
into Prompt 26, Telegram Gateway (28.5), A2A Protocol extended into Prompt 31,
Trajectory Export / Fine-tuning Pipeline (34, new Phase 10).

---

## Project Vision

A local-first, self-improving, multi-agent AI framework — a "Jarvis" style
assistant that:
- Runs everything locally unless a task demands cloud escalation
- Creates and manages specialist AI workers that improve over time via a
  rating system
- Monitors open-loop background tasks (weather, AIS, email, news) and
  interrupts the user only when necessary
- Extends to any domain via a plugin skill architecture
- Is designed for the user's specific context: media production, sailing,
  3D printing, CNC machining

**Core philosophy**: Strong, robust, simple core. Functionality added on top
without breaking what exists. Every component auditable, every decision logged.

---

## Workflow

- **Devin** — writes all code, runs tests, updates `c:\Jarvis\CHANGELOG.md`, updates `SOVEREIGN_AI_HANDOFF.md` after every prompt
- **Claude** — reads this handoff document at session start to reconstruct state, advises on architecture and sequencing, maintains Devin memory entries
- **This handoff doc** is Devin-maintained. Devin updates it after every prompt as part of standard closing steps. Claude reads it but does not write to it.
- When the user pastes a CHANGELOG entry into Claude, Claude automatically produces the next prompt spec without waiting to be asked.

---

## Architecture Overview

```
PERCEPTION LAYER
├── Open loop monitors (weather, AIS, email, news)
├── Scheduled checks (recurring tasks)
└── Event triggers (conditional task firing)
        ↓
COGNITION LAYER
├── Orchestrator (LLM-driven, own instruction file, improves over time)
├── Worker Registry (persistent specialist agents)
├── Planning (task decomposition, state machines)
└── Deliberation (multi-worker, rating, escalation)
        ↓
ACTION LAYER
├── Skills (atomic capabilities, plugin architecture)
├── Services (Gmail, calendar, AIS, weather APIs)
├── Adapters (12 LLM providers + MCP client behind unified protocol)
└── Gateways (Telegram — future)
        ↓
MEMORY LAYER
├── Postgres (primary, structured, fast)
├── Qdrant (semantic search, scoped per worker)
└── Obsidian (human-readable mirror, audit trail)
        ↓
OUTPUT LAYER
├── TUI (current)
├── Web GUI (future)
└── Voice (future)
```

---

## Clean Architecture Rules (Never Violate)

1. `core/` never imports from `adapters/`, `cli/`, `workers/`, or `memory/`
2. `workers/` may import from `core/` and `adapters/` but never from `cli/`
3. `memory/` may import from `core/` only
4. `adapters/` may import from `core/` only
5. `cli/` may import from anywhere but nothing imports from `cli/`
6. All public functions and methods have return type annotations
7. No raw LLM calls outside of `adapters/`
8. No memory access outside of `MemoryRouter`
9. No global mutable state
10. All I/O operations are async

---

## Dependency Injection Rules (Mandatory — DI Refactor Complete)

- `TraceEmitter` and `CommandRegistry` constructed ONCE in `cli/main.py`
- All components receive emitter via constructor:
  `emitter: TraceEmitter | None = None`
- Default to `MemoryTraceEmitter()` if None
- **Never** import `get_trace_emitter`, `set_trace_emitter`, `emit_trace`,
  `_global_emitter`, or `_global_registry` anywhere
- When passing emitter to `super().__init__()`, the parameter MUST appear
  in the subclass `__init__` signature BEFORE the `super()` call

---

## Standard Prompt Closing Steps (Mandatory)

1. Run full test suite — confirm zero regressions, count exceeds previous baseline
2. `python scripts/checkpoint.py prompt-{N}`
3. Confirm local tag: `git tag | grep prompt-{N}`
4. Confirm remote push: `git ls-remote --tags origin | grep prompt-{N}`
5. Update `c:\Jarvis\CHANGELOG.md` — must include Implementation Notes
   documenting any problems hit mid-implementation and how they were resolved
6. Update `SOVEREIGN_AI_HANDOFF.md` directly with these changes:
   - Add completed prompt row to Completed Prompts table
     (prompt number, description, test count, checkpoint tag)
   - Update Current State section: test baseline, checkpoint tag, warnings count
   - Update Remaining Implementation Plan: mark this prompt DONE,
     mark next prompt IN PROGRESS
   - Do NOT modify: Recurring Mistake Patterns, Architecture Rules,
     Project Vision, or prompt spec content
   - Do NOT reformat or restructure any section — append/update only

---

## Current State

### Test Baseline
- **463 passed, 23 skipped, 3 warnings** (as of Prompt 23 / checkpoint prompt-23)
- Baseline is dynamic — every prompt must exceed the previous count
- Skipped: `tests/test_llama_cpp_adapter.py` (missing llama_cpp dependency)
- 3 remaining warnings: FutureWarning from adapters/gemini.py — deferred to Phase 9, do not touch; PytestWarning for 2 async decorator marks on sync methods in test_model_evaluator.py — harmless
- Run with: `python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py`

### Git / Backup
- Repo: `https://github.com/AngusKingC/sovereign-ai` (private)
- Latest checkpoint tag: `prompt-23`
- Checkpoint script: `python scripts/checkpoint.py prompt-{N}`
- Restore script: `python scripts/restore.py`

### Core Layer
- `core/schemas.py` — all Pydantic models including TaskStatus.DENIED, EvaluatorScore, EvaluationRecord, OrchestratorMetrics
- `core/memory_router.py` — MemoryBackend ABC, MemoryRouter with tracing
- `core/worker_base.py` — LLMResponse, LLMAdapter Protocol, WorkerBase ABC (DI)
- `core/orchestrator.py` — routing with scoring algorithm, deregister_worker, mark_task_completed integration, DI complete
- `core/handlers.py` — QueryHandler, DI complete
- `core/embedder.py` — OllamaEmbedder
- `core/observability.py` — TraceEmitter, MemoryTraceEmitter, ConsoleTraceEmitter
- `core/commands.py` — CommandRegistry, DI complete
- `core/exceptions.py` — InvalidStateTransitionError, WorkerNotFoundError,
  ApprovalDeniedError
- `core/task_state_machine.py` — validated transitions, DENIED terminal state,
  full history tracking
- `core/scratchpad.py` — ScratchpadManager, per-task ephemeral working memory
- `core/session.py` — SessionManager, Postgres persistence
- `core/skill_registry.py` — skill discovery, validation, query
- `core/approval_gate.py` — ApprovalGate, ApprovalRequest, ApprovalResponse,
  ApprovalScope, session-scoped pre-authorisation, write-through Postgres cache
- `core/worker_factory.py` — WorkerFactory, DynamicWorkerProfile, PlaceholderWorker,
  rule-based worker creation from natural language description
- `core/rating_system.py` — RatingSystem, worker rating persistence, trend analysis
- `core/instruction_generator.py` — InstructionGenerator, LLM-based instruction file generation
- `core/instruction_versioning.py` — InstructionVersionManager, version control for instruction files
- `core/orchestrator_improvement.py` — OrchestratorImprovementLoop, orchestrator self-improvement
- `core/evaluator.py` — OutputEvaluator, LLM-as-Judge automated output evaluation

### Memory Layer
- `memory/obsidian.py` — Markdown vault storage
- `memory/postgres.py` — Async Postgres, connection pooling, JSONB
- `memory/qdrant.py` — Vector embeddings, semantic search

### Adapters (12 total, all async)
- Ollama, OpenAI, Anthropic, LM Studio, Gemini, Cohere, Groq, Mistral,
  DeepSeek, Together, HuggingFace, llama.cpp
- All import LLMAdapter and LLMResponse from `core.worker_base`

### Workers
- `workers/ollama_worker.py` — production worker
- `workers/echo_worker.py` — testing worker

### CLI
- `cli/tui.py` — TUI, DI complete
- `cli/rich_cli.py` — Rich terminal interface
- `cli/main.py` — entry point, constructs TraceEmitter and CommandRegistry
- `cli/adapter_factory.py` — create_adapter(), create_worker()
- `cli/command_history.py` — persistent history, tab completion

### System Layer
- `system/profiler.py` — SystemProfiler
- `system/model_registry.py` — ModelRegistry, seed data, HW-fit recommendation
- `system/resource_manager.py` — ResourceManager, eviction priority queue
- `system/model_acquisition.py` — ModelAcquisition, HuggingFace integration

### Skills Layer
- `skills/SKILL_SPECIFICATION.md` — formal plugin specification
- `skills/web_scraper/` — httpx + BeautifulSoup
- `skills/file_reader/` — local file reading
- `skills/file_writer/` — local file writing, integrated with ApprovalGate

### Design Documents
- `docs/APPROVAL_GATE_DESIGN.md` — approval gate contracts (locked)

---

## Completed Prompts

| # | Prompt | Tests |
|---|--------|-------|
| 1 | Architecture Compliance Audit | 187 |
| 2 | Type Annotations on CLI Functions | 187 |
| 3 | Fix Gemini Sync/Async Issue | 187 |
| 4 | Extend Observability Across All Layers | 187 |
| 5 | System Profiler | 196 |
| 6 | Model Registry | 208 |
| 7 | Resource Manager | 221 |
| 8 | Model Acquisition Layer | 235 |
| 9 | Task State Machine | 249 |
| 10 | Task Scratchpad | 261 |
| 11 | PostgreSQL Session Persistence | 261 (no new tests — justified) |
| 12 | Command History and Completion in CLI | 261 (no new tests — justified) |
| 13 | Skill Registry and Plugin Specification | 284 |
| 13.5 | DI Refactor: Full Global State Removal | 288 |
| 13.6 amendments | DENIED state + scope storage design decisions | 291 |
| 14 | Approval Gate System | 311 |
| 15 | Worker Factory | 328 |
| 16 | Model Evaluation Logic | 357 |
| 16.5 | WorkerProfile Schema Lock | 357 |
| 17 | Worker Persistence | 370 |
| 18 | Rating System | 386 |
| 19 | Instruction File Generation | 401 |
| 20 | Instruction File Versioning and Updates | 416 |
| 21 | Orchestrator Improvement Loop | 431 |
| 22 | Unified Evaluation Framework | 446 |
| 23 | Memory Scoping | 463 |

---

## Remaining Implementation Plan

### Architecture Review Changes (Incorporated 2026-06-09)

Three external reviews (ChatGPT, Grok, Gemini) were conducted and reviewed
by Claude. The following changes were made to the roadmap as a result:

**Roadmap resequenced (Prompts 17-19):**
- Worker Persistence moved BEFORE Instruction Generation and Rating System
- Rating System moved BEFORE Instruction Generation
- Instruction Generation now has real persistence and rating data to work with
- Old order: 16 Eval → 17 Instructions → 18 Persistence → 19 Rating
- New order: 16 Eval → 17 Persistence → 18 Rating → 19 Instructions

**Worker lifecycle states added to Prompt 17:**
- WorkerStatus enum: ACTIVE, IDLE, ARCHIVED, DEPRECATED
- Only ACTIVE workers participate in routing
- Prevents worker proliferation degrading routing quality

**WorkerProfile schema locked before Prompt 17:**
- DynamicWorkerProfile created in Prompt 15 must be finalised before
  Prompt 17 writes it permanently to Postgres
- Prompt 16 housekeeping step added to lock the schema

**New technical debt items flagged:**
- Qdrant hardcoded vector size (768) — latent bug if embedder changes
- ResourceManager missing KV cache VRAM buffer — risk of OOM on 6GB card
- Model registry seed data may include oversized models — standardise on
  Qwen 2.5 7B Q4_K_M as default

**Memory Scoping moved earlier:**
- Prompt 23 (Memory Scoping) moved to immediately after Prompt 17
  (Worker Persistence) rather than sitting in Phase 6
- Scoped memory is load-bearing for safe multi-worker and open-loop work

**Prompts 22 and old-16 merged:**
- Model Evaluator (hardware fit + task suitability) and LLM-as-Judge
  (output quality scoring) unified into a single evaluation framework
  in a later housekeeping prompt rather than two separate half-systems

---

### PHASE 4 — The Worker Factory (Current)

---

#### Prompt 16 — Model Evaluation Logic
**Status**: DONE

Create `system/model_evaluator.py`.

Scoring formula:
- hardware_score: 1.0 fits_vram / 0.5 fits_ram / 0.0 neither
- suitability_score: tag overlap / total task_tags
- quality_score: quantisation quality_score from ModelEntry
- speed_score: quantisation speed_score from ModelEntry
- final = (hardware * 0.4) + (suitability * 0.3) +
          (quality * quality_preference * 0.3) +
          (speed * (1-quality_preference) * 0.3)

Models: ModelRecommendation, EvaluationResult
Methods: evaluate(), get_best(), record_selection()
Minimum 13 new tests. Target: exceed 328.

---

#### Prompt 16.5 — WorkerProfile Schema Lock (Housekeeping)
**Status**: DONE

Before Worker Persistence writes WorkerProfile to Postgres permanently,
finalise the schema to include all fields needed by future prompts:

DynamicWorkerProfile fields to confirm/add:
- worker_id: str (slug)
- name: str
- purpose: str
- capabilities: list[str]
- preferred_models: list[str]
- performance_score: float (default 0.0, updated by rating system)
- active_tasks: int (default 0)
- version: int (default 1)
- status: WorkerStatus enum (ACTIVE/IDLE/ARCHIVED/DEPRECATED)
- creation_date: datetime
- instruction_file_ref: str | None (Obsidian path, set in Prompt 19)

Add WorkerStatus enum to core/schemas.py.
No new implementation — schema definition and tests only.
Design-only prompt: justify zero new implementation tests in CHANGELOG,
but add schema validation tests.

---

#### Prompt 17 — Worker Persistence
**Status**: DONE

Full worker survival across restarts. Builds on finalised WorkerProfile
schema from Prompt 16.5.

Features:
- Worker definitions serialised to Postgres on create/update
- Obsidian mirror written on every change (one .md file per worker)
- Worker registry loaded from Postgres on system startup
- Workers restored with full profile, assigned model, skill list
- Worker versioning — changes create new version, old versions preserved
- WorkerStatus tracking: ACTIVE/IDLE/ARCHIVED/DEPRECATED
- Only ACTIVE workers participate in routing (orchestrator enforces)
- Worker deprecation flow: mark DEPRECATED → remove from routing →
  preserve in Postgres for audit trail
- WorkerFactory updated to load existing workers from Postgres on init

---

#### Prompt 18 — Rating System
**Status**: DONE

Create `core/rating_system.py`.

Features:
- Rating stored with: worker_id, instruction_file_version, model_used,
  task_id, score (1-10), optional comment
- Multi-worker comparison mode: same task to multiple workers,
  user selection signals which performed better
- Rating history queryable per worker, per model, per instruction version
- Trend analysis: moving average of ratings per worker over time
- Rating data in Postgres, summarised in Obsidian worker profile
- Feeds ModelEvaluator in Prompt 16 — historical performance outweighs
  benchmark rankings when sufficient data exists (>10 ratings)

---

#### Prompt 19 — Instruction File Generation
**Status**: DONE

Create `core/instruction_generator.py`.

Each worker gets in Obsidian:
- `WORKER_NAME_INSTRUCTION.md` — role, goal, persona, capabilities,
  constraints, output format, examples, model-specific optimisations
- `WORKER_NAME_INSTRUCTION_CHANGELOG.md` — append-only log,
  version/date/change/rating trend that triggered it/diff summary

Orchestrator gets identical files.
LLM-based worker profile generation replaces rule-based from Prompt 15.
Generation informed by rating history (from Prompt 18) and persistence
(from Prompt 17).

---

### PHASE 5 — Self-Improvement Loop

---

#### Prompt 20 — Instruction File Versioning and Updates
**Status**: DONE

Version and update mechanism for instruction files.
Update triggered when rating trend drops below threshold over N recent tasks.
Proposed update requires user approval. Rollback available to any version.

---

#### Prompt 21 — Orchestrator Improvement Loop
**Status**: DONE

Wire orchestrator into same improvement loop as workers.
Orchestrator reviews worker ratings, proposes instruction edits.
Own performance tracked: routing accuracy, task completion rate.
Own instruction file updated by same mechanism.

---

#### Prompt 22 — Unified Evaluation Framework
**Status**: DONE

Extend `system/model_evaluator.py` and create `core/evaluator.py`.

Combines:
- Hardware fit scoring (from Prompt 16)
- Historical worker performance weighting (outweighs benchmarks at >10 ratings)
- LLM-as-Judge automated output quality scoring

Features:
- OutputEvaluator class with evaluate_output(), record_evaluation(), get_worker_evaluations()
- Component scores: task_completion, accuracy, format_compliance, conciseness
- Composite score: weighted average (0.4*task_completion + 0.3*accuracy + 0.2*format_compliance + 0.1*conciseness)
- Manual rating override (1-10 scale normalized to 0.1-1.0)
- Historical performance weighting in ModelEvaluator (70% historical, 30% base when >10 records)
- OrchestratorMetrics.task_completed updated when task reaches COMPLETE state
- Evaluation records persisted to memory router with key pattern: evaluation:{task_id}:{worker_id}

---

#### Prompt 23 — Memory Scoping
**Status**: DONE

Implement worker-scoped memory partitions with shared global context layer.
MemoryRouter enforces scoping — workers can only access their own partition and the shared global context.
Cross-scope access attempts raise CrossScopeAccessError.
StrategicContext and EscalationDecision schemas activated from orphan status and integrated into orchestrator.

---

### Competitive Landscape Review Changes (Incorporated 2026-06-10)

Competitive analysis conducted against Hermes Agent, OpenJarvis, LangGraph,
CrewAI, AutoGPT, OpenHands, SuperAGI, Google ADK, OpenAI Agents SDK, and
Microsoft Agent Framework. Six improvements added to the roadmap:

**MCP Adapter added as Prompt 22.5:**
- MCP (Model Context Protocol) is the 2026 industry standard for agent-to-tool
  communication, adopted by all major frameworks
- Adds `adapters/mcp_adapter.py` (MCP client) and `skills/mcp_server.py`
  (exposes SkillRegistry as MCP endpoint)
- Purely additive — no core/ changes. Enables community skill catalogs
  (agentskills.io) and external tool interoperability
- Must land before Phase 7 so open-loop monitors can consume community skills

**Trace-Based Skill Optimiser added as Prompt 22.6:**
- Complements existing rating-trend trigger with a continuous trace-scoring path
- Reads TraceEmitter event logs, scores instruction performance from tool call
  success/failure patterns, feeds InstructionVersionManager as a second trigger
- Placed after 22.5 so MCP tool call outcomes flow into traces first
- If both triggers fire simultaneously, proposals queue — never collide
  (policy must be documented in InstructionVersionManager before implementation)

**Crash-resume extended into Prompt 26 (Monitor Daemon):**
- TaskStateMachine gains checkpoint() / load_checkpoints() for Postgres-serialised
  task resume after daemon restart
- No new prompt needed — Prompt 26 already plans Postgres task queue persistence

**Telegram Gateway added as Prompt 28.5:**
- Delivers notifications from the Notification Layer (Prompt 28) to mobile
- Critical for sailing use case — AIS/weather alerts reachable on the water
- Depends on Prompt 28 (NotificationSystem) — cannot be built before it
- ApprovalGate integration: action requests via Telegram route through existing gate

**A2A Protocol extended into Prompt 31 (Worker-to-Worker Communication):**
- Worker sub-task messages implemented against A2A standard schema rather than
  proprietary protocol — near-zero extra cost at implementation time
- Adds thin `core/a2a_protocol.py` schema + routing layer
- External A2A interop (calling agents in other frameworks) deferred — internal
  compliance first

**Trajectory Export / Fine-tuning Pipeline added as Prompt 34 (new Phase 10):**
- Exports TraceEmitter logs in ShareGPT format for local model fine-tuning
- Prerequisite chain: Phases 7+8 must be complete, meaningful trace history
  must exist before export is useful
- Closes self-improvement loop at model weights level, not just instruction level

---

#### Prompt 22.5 — MCP Adapter (Housekeeping)
**Status**: Queued

Add MCP (Model Context Protocol) as a standard protocol surface.

Files:
- `adapters/mcp_adapter.py` — MCP client: calls external MCP tool servers,
  wraps responses as LLMAdapter-compatible results. Async, DI for emitter.
- `skills/mcp_server.py` — MCP server: exposes SkillRegistry as MCP-compliant
  tool endpoint. No core/ imports.

Architecture:
- `adapters/mcp_adapter.py` imports only from `core/` (LLMAdapter, LLMResponse)
- `skills/mcp_server.py` imports only from `core/` (SkillRegistry)
- No changes to core/ layer
- Emitter injected via constructor, default MemoryTraceEmitter()

Tests: minimum 10. Target: exceed 446.

---

#### Prompt 22.6 — Trace-Based Skill Optimiser (Housekeeping)
**Status**: Queued

Add continuous trace-scoring as a second trigger path for instruction updates,
complementing the existing rating-trend trigger from Prompt 20.

Files:
- `core/trace_optimiser.py` — TraceOptimiser class

Constructor injection: MemoryRouter, InstructionVersionManager, TraceEmitter.

Methods (all async, all typed):
- `score_recent_traces(worker_id, n)` — reads last N traces for worker from
  MemoryRouter, computes tool call success rate and error frequency as a
  composite trace score (0.0–1.0)
- `check_and_trigger_update(worker_id)` — if trace score < trace_threshold
  (default 0.65), calls InstructionVersionManager.check_and_trigger_update()
  as a second trigger path. Returns VersionUpdateProposal | None.
- Emits trace events: trace_score_computed, trace_update_triggered

Collision policy (mandatory — implement before any trigger can fire):
- InstructionVersionManager must check for an existing PENDING proposal before
  creating a new one. If a PENDING proposal exists for a worker, skip and return
  the existing proposal. Document this rule in InstructionVersionManager.

Architecture:
- `core/trace_optimiser.py` imports only from `core/`
- Configurable: trace_threshold and min_traces (default 10) via constructor
- All trace calls wrapped in try-except

Tests: minimum 12. Target: exceed new 22.5 baseline.

---

### PHASE 6 — Memory Architecture

---

#### Prompt 23 — Memory Scoping
**Status**: Queued (moved earlier — load-bearing for multi-worker and
open-loop safety)

Worker-scoped memory partitions + shared global context layer.
`StrategicContext` schema becomes data model for shared global context.
MemoryRouter enforces scoping — raises on cross-scope access attempts.
`EscalationDecision` schema wired into escalation logic concurrently.

---

#### Prompt 24 — Wire EscalationDecision
**Status**: Queued

`EscalationDecision` schema exists but nothing uses it.
Escalation hierarchy: local → better local → cloud.
Always requires user approval unless pre-authorised via ApprovalScope.

---

#### Prompt 25 — Tiered Memory Compaction
**Status**: Queued

Hot/warm/cold memory tiers with periodic background compaction.
Hot: in-context. Warm: Qdrant. Cold: Postgres archival.
Compaction runs as background task, never blocks main execution.

---

### PHASE 7 — Open Loop System (The Jarvis Layer)

---

#### Prompt 26 — Monitor Daemon
**Status**: Queued

`system/monitor_daemon.py` — persistent background heartbeat process.
Scheduler: immediate, deferred, recurring, conditional tasks.
Task queue persisted in Postgres — survives restarts.
Approval gate integration — daemon never blocks on approval.

**Extended scope (competitive review 2026-06-10):**
Task-level crash resume — extends `core/task_state_machine.py`:
- `checkpoint(task_id)` — serialises current task state + last completed step
  to Postgres at each step boundary
- `load_checkpoints()` — called at daemon startup, restores any tasks that were
  IN_PROGRESS at shutdown
- Tasks resume from last checkpoint step, not from scratch
- Checkpoint records keyed: `task_checkpoint:{task_id}`

---

#### Prompt 27 — Event Trigger System
**Status**: Queued

`system/event_triggers.py` — conditional tasks on data conditions.
Trigger types: threshold, change detection, pattern match, schedule.
Data sources: weather, AIS, email, news, system metrics, custom APIs.

---

#### Prompt 28 — Interrupt and Notification Layer
**Status**: Queued

`core/notification.py`.
Types: info, warning, urgent, requires-action.
Urgent interrupts current interaction.
Requires-action integrates with approval gate.
Non-urgent queues and surfaces at natural break points.

---

#### Prompt 28.5 — Telegram Gateway
**Status**: Queued

Deliver notifications from the NotificationSystem to mobile via Telegram.
Critical for sailing use case — AIS/weather alerts reachable on the water.
Depends on Prompt 28 (NotificationSystem must exist before delivery channel).

Files:
- `adapters/telegram_gateway.py` — inbound message handler + outbound delivery

Features:
- Outbound: receives notifications from NotificationSystem, delivers to
  configured Telegram chat ID
- Inbound: receives messages from Telegram, routes to QueryHandler as tasks
- ApprovalGate integration: action-request notifications sent via Telegram
  include approve/reject reply options; responses route through existing gate
- Runs as optional background service — system functions without it
- Config: bot token and chat ID loaded from env vars, never hardcoded
- Emitter injected via constructor, default MemoryTraceEmitter()
- `adapters/telegram_gateway.py` imports only from `core/`

Tests: minimum 10.

---

### PHASE 8 — Multi-Worker Deliberation

---

#### Prompt 29 — Resource Budgeting
**Status**: Queued (new — inserted before multi-worker as prerequisite)

Create `core/resource_budget.py`.
Prevent exponential resource usage in multi-worker mode.

Budget types:
- Token budget (per task, per session)
- Memory budget (VRAM + RAM caps per concurrent execution)
- Execution budget (max concurrent workers)
- Time budget (per task timeout)

ResourceManager integration: enforce budgets before dispatching workers.
Approval gate integration: budget overrun requires user approval.

---

#### Prompt 30 — Multi-Worker Mode
**Status**: Queued (was Prompt 29)

Route same task to top N workers concurrently.
Resource budget enforced — only dispatch if budget allows.
ResourceManager consulted for live memory state.
Responses surfaced side by side. User selection feeds rating system.

---

#### Prompt 31 — Worker-to-Worker Communication
**Status**: Queued (was Prompt 30)

Workers emit sub-task requests during execution.
Orchestrator routes sub-tasks to specialist workers.
Circular dependency detection. Sub-tasks inherit parent priority.

**Extended scope (competitive review 2026-06-10):**
Implement internal worker messaging against A2A (Agent-to-Agent) protocol
standard rather than a proprietary schema. Near-zero extra cost at
implementation time; preserves future interoperability with LangGraph,
CrewAI, and other A2A-compliant frameworks.

Files:
- `core/a2a_protocol.py` — thin schema + routing layer, imports only from `core/`

A2A-standard task envelope schema:
- Request: `task_id`, `input`, `metadata`, `requester_agent_id`
- Response: `task_id`, `status`, `output`, `artifacts`

Note: External A2A interop (calling agents in other frameworks) is deferred.
Internal compliance first — use the standard schema, external bridge later.

---

### PHASE 9 — Interfaces

---

#### Prompt 32 — Web GUI
**Status**: Queued (was Prompt 31)

`web/` layer — FastAPI + WebSockets + React frontend.
Mirrors all TUI functionality including worker management.
`web/` imports from `core/` only.

---

#### Prompt 33 — Voice Interface
**Status**: Queued (was Prompt 32)

Wake word detection, Whisper STT, TTS.
Voice notifications for open loop events.
Same approval gates and observability as text interface.

---

### PHASE 10 — Model Evolution (New — added 2026-06-10)

---

#### Prompt 34 — Trajectory Export / Fine-tuning Pipeline
**Status**: Queued

Close the self-improvement loop at the model weights level, not just the
instruction/prompt level.

Prerequisite: Phases 7 and 8 complete, meaningful trace history accumulated
(minimum configurable threshold before export is triggered).

Files:
- `system/trajectory_exporter.py` — TrajectoryExporter class

Features:
- Reads completed task traces from TraceEmitter event log via MemoryRouter
- Filters by quality threshold (only traces where OutputEvaluator final_score
  exceeds configurable minimum — default 0.7)
- Exports in ShareGPT format (.jsonl) — compatible with Axolotl, Unsloth,
  and standard fine-tuning pipelines
- Export modes: manual trigger, scheduled export, minimum trace count threshold
- Trajectory compression: fits training data into token budgets
- No model training infrastructure in scope — export pipeline only
- `system/trajectory_exporter.py` imports from `core/` and `system/` only

Architecture:
- Emitter injected via constructor, default MemoryTraceEmitter()
- All I/O async
- All public methods typed
- Export path configurable via constructor, never hardcoded

Tests: minimum 12.

---

| Item | Location | Notes |
|------|----------|-------|
| google.generativeai FutureWarning | adapters/gemini.py | Do not touch until Phase 9 |
| RuntimeWarning coroutine never awaited | skills/web_scraper tests | Do not touch |
| llama.cpp tests skipped | tests/test_llama_cpp_adapter.py | Missing dependency |
| StrategicContext orphaned | core/schemas.py | Addressed in Prompt 23 |
| EscalationDecision orphaned | core/schemas.py | Addressed in Prompt 24 |
| Model selection modal incomplete | cli/tui.py | Phase 4 |
| No tests for session postgres | core/session.py | Prompt 11 debt |
| No tests for command_history | cli/command_history.py | Prompt 12 debt |
| Qdrant hardcoded vector size 768 | memory/qdrant.py | Latent bug — fix before Phase 6 |
| ResourceManager missing KV cache buffer | system/resource_manager.py | OOM risk on 6GB card — fix before Prompt 29 |
| Model registry may seed oversized models | system/model_registry.py | Standardise on Qwen 2.5 7B Q4_K_M — fix in Prompt 16.5 |
| WorkerPersistence not passed to WorkerFactory in CLI | cli/tui.py, cli/rich_cli.py | Intentional deferral — requires CLI refactor |
| WorkerPersistence in TYPE_CHECKING block | core/worker_factory.py | Verify no runtime issues in future prompt |

---

## Recurring Mistake Patterns (For Claude Context — Not Sent to Devin)

These are tracked here so Claude can write targeted Devin memory entries
and prompt guards when patterns recur.

1. Patching `emit_trace` after DI refactor removed it → AttributeError
2. Batching multiple files between test runs → can't isolate regressions
3. Forgetting `emitter` in subclass `__init__` signature → NameError
4. Wrong checkpoint label (used next prompt number not current)
5. Design-only prompts with no justification for zero new tests in CHANGELOG
6. Retaining old `emit_trace` imports after DI migration
7. Wrong TraceEvent field names (used layer/payload/success) →
   correct fields are event_type, component, level, message, data, duration_ms
8. Using `emitter.events` instead of `emitter.get_events()`
9. Raising domain exceptions inside try-except that catches them →
   exception silently swallowed, raise OUTSIDE try-except
10. Asserting `"string" in event.data` where data is a dict →
    checks keys not values, use `event.component == X` instead
11. Mock objects don't behave like dicts when calling .get() —
    use proper dict structures in mock return values, not Mock() objects
12. Test state bleeds between tests when mutating Pydantic model fields directly —
    always reset fields like version explicitly in each test that depends on them
13. Dual-trigger collision in InstructionVersionManager — rating-trend trigger
    (Prompt 20) and trace-score trigger (Prompt 22.6) can both fire for the same
    worker. InstructionVersionManager MUST check for an existing PENDING proposal
    before creating a new one. If PENDING exists, skip and return it. Implement
    this guard in Prompt 22.6 before the trace trigger is wired up.

---

## Hardware Context

- **GPU**: NVIDIA RTX 3060 Mobile — 6GB VRAM
- **RAM**: ~15.6GB available after VRAM
- **OS**: Windows
- **Local LLM**: Ollama with `qwen2.5-coder:7b` (Q4_K_M — fits comfortably)
- **IDE**: Devin (SWE 1.6 Slow)
- **Hardware detected automatically at runtime — never hardcode**
- **KV cache consumes VRAM dynamically** — ResourceManager must budget for
  context window overhead, not just model weights

---

## User Domain Context

- **Media production** — video scripts, content creation
- **3D printing and CNC machining** — file generation, design workflows
- **Sailing** — route planning, weather monitoring, AIS tracking

Priority workers once factory is operational:
- VideoScriptWorker
- ThreeDDesignWorker
- ResearchWorker
- NavigationWorker (sailing/AIS/weather)
- EmailWorker

---

## Source References

- AutoGen: github.com/microsoft/autogen
- LangGraph: github.com/langchain-ai/langgraph
- CrewAI: github.com/crewAIInc/crewAI
- MemGPT/Letta: github.com/cpacker/MemGPT
- SWE-agent: github.com/princeton-nlp/SWE-agent
- Hermes Agent: github.com/NousResearch/hermes-agent
- OpenJarvis: github.com/open-jarvis/OpenJarvis
- agentskills.io: open standard for portable agent skills (MCP-compatible)
- A2A Protocol: google-deepmind.github.io/agent-to-agent
