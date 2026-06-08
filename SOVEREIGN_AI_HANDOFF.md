# Sovereign AI Agent Framework — Project Handoff Document

## Purpose
This document is a complete handoff brief for a prompting agent continuing development of the Sovereign AI Agent Framework. It contains the project vision, current state, completed work, and every remaining implementation in order.

---

## Project Vision

A local-first, self-improving, multi-agent AI framework — a "Jarvis" style assistant that:
- Runs everything locally unless a task demands cloud escalation
- Creates and manages specialist AI workers that improve over time via a rating system
- Monitors open-loop background tasks (weather, AIS, email, news) and interrupts the user only when necessary
- Extends to any domain via a plugin skill architecture
- Is designed for the user's specific context: media production, sailing, 3D printing, CNC machining

**Core philosophy**: Strong, robust, simple core. Functionality added on top without breaking what exists. Every component auditable, every decision logged.

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
└── Adapters (12 LLM providers behind unified protocol)
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

## Standard Prompt Closing Steps

Every prompt must end with these three steps:
1. Run the full test suite and confirm all previously passing tests still pass with zero regressions
2. Verify the project structure in memory matches the Clean Architecture layer boundaries
3. Append a new dated entry to `CHANGELOG.md` documenting what was done and the final test result

---

## Current State (Completed)

### Infrastructure
- `requirements.txt` with all core dependencies
- Python 3.11+, Pydantic v2, async-first, Clean Architecture

### Core Layer
- `core/schemas.py` — Message, Task, WorkerOutput, WorkerProfile, TraceEvent, EscalationDecision, StrategicContext, SessionSummary
- `core/memory_router.py` — MemoryBackend ABC, MemoryRouter with tracing
- `core/worker_base.py` — LLMResponse, LLMAdapter Protocol, WorkerBase ABC
- `core/orchestrator.py` — Real routing with scoring algorithm (complexity + capability keywords)
- `core/handlers.py` — QueryHandler using Orchestrator pattern
- `core/embedder.py` — OllamaEmbedder (moved from memory/ for architecture compliance)
- `core/observability.py` — Global emitter (known violation, marked for future DI refactor)
- `core/commands.py` — Command registry (global registry, known violation, marked for future DI refactor)

### Memory Layer
- `memory/obsidian.py` — Markdown vault storage, async file I/O
- `memory/postgres.py` — Async Postgres with connection pooling, JSONB storage
- `memory/qdrant.py` — Vector embeddings and semantic search

### Adapters (12 total, all async-compliant)
- Ollama, OpenAI, Anthropic, LM Studio, Gemini (sync wrapped in executor), Cohere, Groq, Mistral, DeepSeek, Together, HuggingFace, llama.cpp
- All import LLMAdapter and LLMResponse from `core.worker_base`
- `adapters/base.py` re-exports with deprecation warning for backward compatibility

### Workers
- `workers/ollama_worker.py` — Production worker, default capabilities profile
- `workers/echo_worker.py` — Testing worker

### CLI
- `cli/tui.py` — TUI with adapter/model selection modals
- `cli/rich_cli.py` — Rich terminal interface
- `cli/main.py` — Entry point
- `cli/adapter_factory.py` — create_adapter() and create_worker()

### Observability
- `observability/tracer.py` — Tracer, TraceEvent, Layer enum, EventType enum
- Currently only wired to CLI and handlers

### Session Management
- SessionManager with in-memory fallback (Postgres persistence not yet implemented)

### System Layer
- `system/profiler.py` — SystemProfiler, detects GPU/CPU/RAM/storage/OS/network/Ollama
- `system/model_registry.py` — ModelRegistry with seed data, HW-fit recommendation algorithm
- `system/resource_manager.py` — ResourceManager, eviction priority queue, pinning, approval callbacks
- `system/model_acquisition.py` — ModelAcquisition, HuggingFace integration, adapter-specific downloaders

### Core Layer (additions since initial state)
- `core/embedder.py` — OllamaEmbedder (moved from memory/ for architecture compliance)
- `core/session.py` — SessionManager with in-memory fallback
- `core/observability.py` — Consolidated single tracing system (replaced observability/tracer.py); global emitter known violation, marked for DI refactor
- `core/commands.py` — Command registry; global registry known violation, marked for DI refactor
- `core/exceptions.py` — InvalidStateTransitionError, WorkerNotFoundError, ApprovalDeniedError
- `core/task_state_machine.py` — TaskStateMachine with validated transitions and full history tracking
- `core/scratchpad.py` — ScratchpadManager, per-task ephemeral working memory

### Skills Layer
- `skills/SKILL_SPECIFICATION.md` — formal SKILL.md format specification
- `skills/web_scraper/` — web scraping skill (httpx + BeautifulSoup)
- `skills/file_reader/` — local file reading skill
- `skills/file_writer/` — local file writing skill (approval gate stubbed, implemented in Prompt 14)

### Tests
- **284 passed, 23 skipped, 0 failures** (baseline as of Prompt 13 — project reverted to this point)
- Skipped: test_llama_cpp_adapter.py (missing llama_cpp dependency)

---

## Completed Prompts

| # | Prompt | Result |
|---|--------|--------|
| 1 | Architecture Compliance Audit | 5 violation classes fixed, 187 passing |
| 2 | Type Annotations on CLI Functions | 3 annotations added, 187 passing |
| 3 | Fix Gemini Sync/Async Issue | Gemini fixed, all others already async, 187 passing |
| 4 | Extend Observability Across All Layers | All 12 adapters, memory backends, embedder, workers, orchestrator instrumented, 187 passing |
| 5 | System Profiler | system/ layer created, SystemProfiler + SystemProfile schemas, 196 passing |
| 6 | Model Registry | system/model_registry.py, ModelEntry schemas, seed data, HW-fit recommendation, 208 passing |
| 7 | Resource Manager | system/resource_manager.py, LoadDecision + eviction priority queue, 221 passing |
| 8 | Model Acquisition Layer | system/model_acquisition.py, HuggingFace integration, adapter-specific downloaders, 235 passing |
| 9 | Task State Machine | core/task_state_machine.py, core/exceptions.py, extended TaskStatus, orchestrator integration, 249 passing |
| 10 | Task Scratchpad | core/scratchpad.py, ScratchpadManager, WorkerBase + Orchestrator integration, 261 passing |
| 11 | PostgreSQL Session Persistence | core/session.py updated, CLI wired to PostgresBackend via SOVEREIGN_DB_DSN, no new tests (261 baseline held) |
| 12 | Command History and Completion in CLI | cli/command_history.py, integrated into rich_cli + tui, no new tests (261 baseline held) |
| 13 | Skill Registry and Plugin Specification | core/skill_registry.py, skills/ layer, 3 initial skills (web_scraper, file_reader, file_writer), 284 passing |

---

## Remaining Implementation Plan

### PHASE 2 — Housekeeping (Current Phase)

---

#### Prompt 4 — Extend Observability Across All Layers
**Status**: ✅ COMPLETE

Add trace events to every architectural layer using existing Tracer and TraceEvent infrastructure.

- **Memory backends** (`memory/obsidian.py`, `memory/postgres.py`, `memory/qdrant.py`): emit on fetch/write start, completion, error. Include backend type, task_id, record count, duration.
- **Embedder** (`core/embedder.py`): emit on embedding request and completion. Include model, input length, duration.
- **Adapters** (all 12): emit on generate() start, completion, error. Include adapter name, model name, prompt token estimate, response length, duration.
- **Workers** (`workers/ollama_worker.py`, `workers/echo_worker.py`): emit on build_prompt and parse_output start/completion. Include worker name, task_id, memory records used, confidence score.
- **Orchestrator** (`core/orchestrator.py`): emit on routing start, worker selected, scoring breakdown per candidate, routing duration. Emit on worker register/deregister.

Rules:
- Use existing Tracer and TraceEvent — no new observability mechanisms
- Use existing Layer and EventType enums — add new enum values if needed, no raw strings
- Tracing must never crash the main execution path — all trace calls wrapped
- Tracer injected, never imported directly

---

### PHASE 2a — System Intelligence Layer

---

#### Prompt 5 — System Profiler
**Status**: ✅ COMPLETE

Create `system/profiler.py` — a persistent system profiler that runs on first launch, updates on each session start, and can be queried by any component at runtime.

Detects and stores:
- **GPU**: VRAM total, VRAM available, GPU model, CUDA/ROCm/Metal support
- **CPU**: cores, threads, architecture, clock speed
- **RAM**: total, available, current usage
- **Storage**: total space, available space per drive/partition, read/write speeds
- **Operating System**: type, version, kernel, Docker availability, GPU driver presence
- **Network**: connectivity status, estimated bandwidth
- **Ollama**: which models are downloaded, sizes on disk, which are loaded in VRAM
- **Connected devices**: peripherals, external drives

Storage:
- Postgres (structured, queryable at runtime by any component)
- Obsidian (human-readable snapshot)
- Refreshed on session start and on significant resource change

Layer placement: `system/profiler.py` — new `system/` layer, may import from `core/` only.

---

#### Prompt 6 — Model Registry
**Status**: ✅ COMPLETE

Create `system/model_registry.py` — maps every known model to its resource requirements and compatibility.

Each model entry contains:
- Name, source (Ollama, HuggingFace, LM Studio, etc.)
- Size on disk per quantisation variant
- VRAM requirement per quantisation level
- RAM requirement for CPU offload scenarios
- Adapter compatibility list
- Task suitability tags
- Download status (downloaded, not downloaded, partially downloaded)

Integrates with System Profiler to answer: "Given current hardware state, what is the highest quality quantisation of this model I can load right now?"

---

#### Prompt 7 — Resource Manager
**Status**: ✅ COMPLETE

Create `system/resource_manager.py` — tracks live resource usage and manages model loading/eviction.

Features:
- Tracks which models are currently loaded and their resource footprint
- Enforces resource budget before loading a new model
- Eviction queue using priority: idle time first, then task priority, user-pinned models never evicted without approval
- Integrates with approval gate — evicting a pinned or active model requires user confirmation
- Feeds model evaluation logic in Phase 4 — only recommends models that actually fit current memory state
- Multi-worker aware — when Phase 8 spins up multiple workers, sequences or selects models within real resource constraints

---

#### Prompt 8 — Model Acquisition Layer
**Status**: ✅ COMPLETE

Create `system/model_acquisition.py` — unified model downloader with HuggingFace catalogue integration.

Features:
- **HuggingFace integration**: search models by task type, size, architecture. Filter by quantisation, license, language. Read model cards for capability information. Authenticated requests for gated models (HuggingFace token stored securely).
- **Download flow**: check local registry → query HuggingFace metadata → check hardware fit via System Profiler → present to user for approval (name, size, VRAM requirement, estimated download time) → download with progress tracking → register in model registry
- **Fit checking**: if model doesn't fit, present alternatives at lower quantisation or smaller models that do fit
- **Adapter-specific downloaders**:
  - Ollama — uses Ollama pull API (initial implementation)
  - LM Studio — download to LM Studio model directory
  - llama.cpp — download GGUF files directly from HuggingFace
  - OpenAI/Anthropic/Gemini — API key validation and model availability check only
  - Future adapters — plugin interface, adapters declare their own download mechanism
- **Storage management**: tracks total disk usage, warns before downloading if space is tight, suggests models to delete to make room, deletion requires user approval
- **Quantisation awareness**: shows available quantisation options, recommends highest quality that fits VRAM, user can override

---

### PHASE 3 — Core Infrastructure Upgrades

---

#### Prompt 9 — Task State Machine
**Status**: ✅ COMPLETE

Extend `core/schemas.py` and `core/orchestrator.py` to implement explicit task state machine.

States: `RECEIVED → PLANNED → EXECUTING → VALIDATING → AWAITING_APPROVAL → COMPLETE → FAILED → CANCELLED`

Features:
- Tasks can be paused, inspected, resumed, or redirected at any state
- State transitions emit trace events
- Invalid state transitions raise explicit errors
- State history stored per task (audit trail)
- Integrates with approval gate — tasks requiring approval pause at AWAITING_APPROVAL until user responds

---

#### Prompt 10 — Task Scratchpad
**Status**: ✅ COMPLETE

Add a per-task working memory scratchpad separate from long-term memory.

Features:
- Each task execution gets an isolated scratchpad
- Workers write reasoning, dead ends, and intermediate results to scratchpad during execution
- Scratchpad is readable by the worker mid-task but not persisted to long-term memory during execution
- On task completion: scratchpad is compacted into a summary and written to long-term memory
- On task failure: scratchpad preserved for debugging
- Scratchpad stored in Postgres, scoped strictly to task_id

---

#### Prompt 11 — PostgreSQL Session Persistence
**Status**: ✅ COMPLETE

Replace the current in-memory session fallback with proper Postgres persistence.

Features:
- Sessions survive process restarts
- Session history queryable by session_id, user_id, date range
- Session summary statistics persisted (from existing SessionSummary schema)
- SessionManager loads existing session on startup if session_id provided
- Old sessions expire and are archived after configurable period

---

#### Prompt 12 — Command History and Completion in CLI
**Status**: ✅ COMPLETE

Add persistent command history and tab completion to TUI and rich_cli.

Features:
- Command history persisted to Postgres and readable across sessions
- Up/down arrow navigation through history
- Tab completion for commands, adapter names, model names
- History searchable with Ctrl+R style interaction
- History scoped per user/session

---

### PHASE 4 — The Worker Factory

---

#### Prompt 13 — Skill Registry and Plugin Specification
**Status**: ✅ COMPLETE

Create the formal plugin architecture for skills.

Directory structure per skill:
```
skills/
  web_scraper/
    SKILL.md       ← description, inputs, outputs, dependencies, adapter requirements
    skill.py       ← async implementation
    tests/         ← skill-level tests
  video_script/
    SKILL.md
    skill.py
    tests/
```

`SKILL.md` format declares:
- Skill name and description
- Input parameters and types
- Output format
- External dependencies (services, adapters)
- Hardware requirements if any
- Task suitability tags

Create `core/skill_registry.py`:
- Discovers skills by scanning skills/ directory for SKILL.md files
- Validates each skill against the plugin specification
- Registers skills with their metadata
- Queryable by capability, task type, dependency
- Orchestrator reads skill registry when creating workers

Initial hand-coded skills to implement alongside registry:
- `skills/web_scraper/` — scrape webpage content
- `skills/file_reader/` — read local files
- `skills/file_writer/` — write local files (requires approval gate)

---

#### Prompt 13.5 — DI Refactor: Full Global State Removal
**Status**: ⚠️ IN PROGRESS — INCOMPLETE, POTENTIALLY BROKEN STATE

**What was completed before issues:**
- `core/commands.py` — `_global_registry` and wrappers deleted ✓
- `core/observability.py` — `_global_emitter`, `emit_trace()`, etc. deleted ✓
- `core/task_state_machine.py` — constructor injection added ✓
- `core/worker_base.py` — recreated from scratch with DI ✓
- `core/scratchpad.py` — constructor injection added ✓
- `core/handlers.py` — `emit_trace` replaced with `self.emitter.emit()` BUT handler constructors not updated yet — **BROKEN**

**What is NOT done (remaining files):**
- `core/handlers.py` — constructors missing `emitter` parameter — syntax/runtime errors present
- `core/orchestrator.py`
- `core/memory_router.py`
- `workers/ollama_worker.py`, `workers/echo_worker.py`
- `system/profiler.py`, `system/model_registry.py`, `system/resource_manager.py`, `system/model_acquisition.py`
- `cli/main.py`, `cli/rich_cli.py`, `cli/tui.py` — TraceEmitter and CommandRegistry not yet constructed at startup
- All test files — still using old global patterns

**FIRST ACTION FOR NEXT AGENT SESSION:**
Run a full state assessment before touching anything:
```bash
python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py 2>&1 | tail -30
grep -rn "_global_registry\|_global_emitter\|emit_trace\|get_trace_emitter\|set_trace_emitter" core/ workers/ system/ cli/ tests/ --include="*.py"
python -m py_compile core/commands.py && echo "OK" || echo "BROKEN"
python -m py_compile core/observability.py && echo "OK" || echo "BROKEN"
python -m py_compile core/handlers.py && echo "OK" || echo "BROKEN"
python -m py_compile core/orchestrator.py && echo "OK" || echo "BROKEN"
python -m py_compile core/memory_router.py && echo "OK" || echo "BROKEN"
python -m py_compile core/worker_base.py && echo "OK" || echo "BROKEN"
python -m py_compile core/scratchpad.py && echo "OK" || echo "BROKEN"
python -m py_compile core/task_state_machine.py && echo "OK" || echo "BROKEN"
```
Report all output before taking any action. Fix one file at a time, run full test suite after each file. Do not batch files between test runs.

**If state is too broken to fix forward, do a clean git revert to post-Prompt 13 (284 tests passing) and restart 13.5 from scratch.**

---

#### Prompt 13.6 — Approval Gate Design Document
**Status**: Queued (blocked on 13.5 completion)

Produce `docs/APPROVAL_GATE_DESIGN.md` before any approval gate code is written. Lock in these invariants:

- What happens on **denial**? (fail permanently / return to PLANNED / other)
- What happens on **timeout**? (auto-deny / auto-approve / escalate)
- **Who can approve**? (human only / orchestrator if pre-authorised / per-action-type)
- **Batched approval scopes**? (e.g. "approve all file writes this session", "approve all downloads under 4GB")
- **Expiry duration**? (how long before AWAITING_APPROVAL auto-resolves)
- **Non-blocking guarantee**? (approval must never stall monitor daemon or background jobs)

No implementation — decisions and schema contracts only. User reviews and confirms before Prompt 14 proceeds.

---

#### Prompt 14 — Approval Gate System
**Status**: Queued (blocked on 13.6 user review)

---

#### Prompt 15 — Worker Factory
**Status**: Queued (blocked on Prompt 14 completion)

Extend `core/orchestrator.py` to create new specialist workers from natural language description.

Flow:
1. User describes a task the orchestrator can't route to an existing worker
2. Orchestrator analyses the task and determines a new specialist worker is needed
3. Orchestrator queries skill registry for relevant skills
4. Orchestrator generates a worker capability profile
5. Orchestrator triggers model evaluation (Prompt 16)
6. On model selection: generates INSTRUCTION.md for the worker
7. Creates worker instance and registers it in worker registry
8. Routes original task to new worker

Worker registry stored in:
- Postgres (primary, fast runtime queries)
- Obsidian (human-readable mirror, one .md file per worker)

---

#### Prompt 16 — Model Evaluation Logic
**Status**: Queued

Create `system/model_evaluator.py` — when creating a worker, evaluate and recommend the best available model.

Evaluation criteria (in order):
1. **Hardware fit**: query Resource Manager for what's loadable given current memory state
2. **Task suitability**: query Model Registry for models tagged for this task type
3. **Quality vs speed preference**: user-configurable preference per worker type
4. **Web research**: query HuggingFace model cards for recent benchmark data on task type

Output: ranked list of model recommendations with reasoning, presented to user for confirmation before assignment. User can override. Selection stored against worker profile.

---

#### Prompt 17 — Instruction File Generation
**Status**: Queued

Create `core/instruction_generator.py` — generates structured instruction files for new workers.

Each worker gets two files in Obsidian:

`WORKER_NAME_INSTRUCTION.md` structure:
- Role definition
- Goal
- Backstory/persona
- Capabilities (links to registered skills)
- Constraints
- Output format specification
- Examples (few-shot)
- Model-specific optimisations

`WORKER_NAME_INSTRUCTION_CHANGELOG.md` structure:
- Append-only log
- Each entry: version number, date, change made, rating trend that triggered it, previous vs new content diff summary

Orchestrator has identical files: `ORCHESTRATOR_INSTRUCTION.md` and `ORCHESTRATOR_INSTRUCTION_CHANGELOG.md`

---

#### Prompt 18 — Worker Persistence
**Status**: Queued

Ensure workers fully survive restarts and are available across sessions.

Features:
- Worker definitions serialised to Postgres on creation and update
- Obsidian mirror written on every change
- Worker registry loaded from Postgres on system startup
- Workers restored with their full profile, assigned model, skill list, and instruction file reference
- Worker status tracking (active, idle, deprecated)
- Worker versioning — changes to a worker profile create a new version, old versions preserved

---

#### Prompt 19 — Rating System
**Status**: Queued

Create `core/rating_system.py` — 1-10 rating stored against instruction file version and model used.

Features:
- Rating stored with: worker_id, instruction_file_version, model_used, task_id, score, optional comment
- Multi-worker comparison mode: same task routed to multiple workers simultaneously, responses surfaced side by side, user selection signals which performed better
- Rating history queryable per worker, per model, per instruction version
- Trend analysis: moving average of ratings per worker over time
- Rating data stored in Postgres, summarised in Obsidian worker profile

---

### PHASE 5 — Self-Improvement Loop

---

#### Prompt 20 — Instruction File Versioning and Updates
**Status**: Queued

Implement versioning and update mechanism for instruction files.

Features:
- Each instruction file has a version number (v1, v2, v3...)
- Updates triggered when rating trend drops below threshold over N recent tasks
- Proposed update generated by orchestrator based on rating history and task outputs
- Update presented to user for approval before applying
- On approval: new version written, changelog entry appended, old version archived
- Rollback available to any previous version

---

#### Prompt 21 — Orchestrator Improvement Loop
**Status**: Queued

Wire the orchestrator into the same improvement loop as workers.

Features:
- Orchestrator reviews worker ratings periodically
- Proposes instruction file edits for underperforming workers
- Orchestrator's own performance tracked (routing accuracy, task completion rate)
- Orchestrator's own instruction file updated by same mechanism
- Improvement proposals always require user approval

---

#### Prompt 22 — LLM-as-Judge Evaluator
**Status**: Queued

Create `core/evaluator.py` — automated output scoring using a separate evaluator model.

Features:
- Evaluator model scores outputs on: task completion, accuracy, format compliance, conciseness
- Runs automatically after each task, feeds rating system without requiring manual input on every response
- Evaluator model is separate from the worker model — uses a fast, lightweight model
- Evaluator scores stored alongside manual ratings
- Manual rating overrides evaluator score when provided
- Evaluator model configurable, defaults to a small fast local model

---

### PHASE 6 — Memory Architecture

---

#### Prompt 23 — Memory Scoping
**Status**: Queued

Implement worker-scoped memory partitions and shared global context layer.

Features:
- Every memory read/write tagged with worker_id scope
- Workers can only read/write their own scoped memory partition
- Shared global context layer readable by all workers, writable only by orchestrator
- `StrategicContext` schema (currently orphaned) becomes the data model for shared global context
- `EscalationDecision` schema (currently orphaned) wired into escalation logic
- MemoryRouter enforces scoping — rejects cross-scope access attempts

---

#### Prompt 24 — Wire EscalationDecision
**Status**: Queued

The `EscalationDecision` schema exists in `core/schemas.py` but nothing uses it. Wire the local-first escalation logic throughout the system.

Escalation hierarchy:
1. Local model (default)
2. Better local model (on user request or quality threshold breach)
3. Cloud model (when local isn't feasible for the task)

Features:
- Workers can request escalation mid-task with reason
- Orchestrator evaluates escalation request against hardware state and task priority
- Escalation always requires user approval unless pre-authorised
- Escalation decisions logged to Postgres and Obsidian

---

#### Prompt 25 — Tiered Memory Compaction
**Status**: Queued

Implement hot/warm/cold memory tiers with periodic compaction.

Tiers:
- **Hot**: in-context memory (current conversation/task window)
- **Warm**: Qdrant semantic retrieval (recent, relevant, fast)
- **Cold**: Postgres archival (old, compressed, slow but complete)

Compaction process:
- Periodic job reviews warm memory older than configurable threshold
- Summarises clusters of related memories into compressed form
- Moves originals to cold storage
- Compressed summaries remain in warm tier
- Compaction runs as a background task, never blocking main execution

---

### PHASE 7 — Open Loop System (The Jarvis Layer)

---

#### Prompt 26 — Monitor Daemon
**Status**: Queued

Create `system/monitor_daemon.py` — the heartbeat of the system.

Features:
- Persistent background process that starts with the system
- Scheduler supporting: immediate tasks, deferred tasks (execute at time), recurring tasks (interval or cron), conditional tasks (execute when condition met)
- Task queue persisted in Postgres — survives restarts
- Each scheduled task is a full Task object with state machine
- Daemon status queryable at runtime
- Pause/resume/cancel any scheduled task
- All scheduled task executions logged to observability layer

---

#### Prompt 27 — Event Trigger System
**Status**: Queued

Create `system/event_triggers.py` — conditional tasks that fire on data conditions.

Features:
- Trigger definition: condition expression + action (task to create)
- Condition types: threshold (value > X), change detection (value changed), pattern match (text contains X), schedule (time-based)
- Data sources: weather API, AIS feed, email inbox, news feeds, system metrics, custom APIs
- Triggers stored in Postgres, loaded by monitor daemon on startup
- Trigger evaluation runs on each daemon heartbeat
- Trigger firing creates a new Task in the orchestrator pipeline
- Trigger history logged — when it fired, what condition was met, what task was created

---

#### Prompt 28 — Interrupt and Notification Layer
**Status**: Queued

Create `core/notification.py` — surfaces open loop events to the user naturally.

Features:
- Notification types: info, warning, urgent, requires-action
- Delivery via active interface (TUI, web, eventually voice)
- Urgent notifications interrupt current interaction
- Non-urgent notifications queue and surface at natural break points
- Requires-action notifications pause until user responds (integrates with approval gate)
- Notification history stored in Postgres
- User can configure notification preferences per trigger type

---

### PHASE 8 — Multi-Worker Deliberation

---

#### Prompt 29 — Multi-Worker Mode
**Status**: Queued

Extend `core/orchestrator.py` to route the same task to multiple workers simultaneously.

Features:
- Orchestrator selects top N workers by score (configurable N)
- Tasks dispatched concurrently to all selected workers
- Resource Manager consulted — only dispatch to workers whose models fit in current memory simultaneously, or sequence them if not
- Responses surfaced side by side in TUI/GUI for comparison
- User selection feeds rating system
- Mode toggled per-task or set as default in orchestrator config

---

#### Prompt 30 — Worker-to-Worker Communication
**Status**: Queued

Enable workers to consult each other via the orchestrator.

Features:
- Worker can emit a sub-task request during execution
- Orchestrator intercepts sub-task, routes to appropriate specialist worker
- Result returned to requesting worker before it continues
- Example: ResearchWorker fetches data, passes to WritingWorker for formatting
- Sub-task chain logged in observability layer
- Circular dependency detection — prevent infinite loops
- Sub-tasks inherit parent task priority and approval settings

---

### PHASE 9 — Interfaces

---

#### Prompt 31 — Web GUI
**Status**: Queued

Create `web/` layer — FastAPI backend with WebSockets and a React frontend.

Features:
- FastAPI app in `web/app.py`
- WebSocket endpoint for real-time streaming responses
- REST endpoints for: session management, worker registry, rating submission, system status, model management
- React frontend with: chat interface, worker management panel, system resource display, rating controls, notification panel
- Mirrors all TUI functionality
- Architecture compliance: `web/` layer may import from `core/` only, never from `cli/`

---

#### Prompt 32 — Voice Interface
**Status**: Queued

Add voice input/output as the final Jarvis layer.

Features:
- Wake word detection (always-on, low resource)
- Speech-to-text via local Whisper model
- Text-to-speech for responses
- Voice notifications for open loop events
- Seamless handoff between voice and text interface
- Voice commands integrate with full orchestrator pipeline — same approval gates, same observability

---

## Known Technical Debt

| Item | Location | Notes |
|------|----------|-------|
| Missing test coverage | `core/session.py` (Prompt 11), `cli/command_history.py` (Prompt 12) | No new tests written — should add tests/test_session_postgres.py and tests/test_command_history.py at some point |
| Global mutable state | `core/commands.py` line 147 | `_global_registry` — full removal in Prompt 13.5 |
| Global mutable state | `core/observability.py` line 313 | `_global_emitter` — full removal in Prompt 13.5 |
| llama.cpp tests skipped | `tests/test_llama_cpp_adapter.py` | Missing llama_cpp dependency in test env |
| StrategicContext orphaned | `core/schemas.py` | Addressed in Prompt 23 |
| EscalationDecision orphaned | `core/schemas.py` | Addressed in Prompt 24 |
| Model selection modal incomplete | `cli/tui.py` | Shows "select adapter first" — addressed in Phase 4 |

---

## Hardware Context

- **GPU**: NVIDIA RTX 3060 Mobile — 6GB VRAM
- **RAM**: ~15.6GB available after VRAM
- **OS**: Windows
- **Local LLM**: Ollama with `qwen2.5-coder:7b` recommended for local development
- **IDE**: Devin (SWE 1.6 Slow) — primary agent for implementation
- **Hardware is detected automatically at runtime via system/profiler.py — never hardcode hardware assumptions**

---

## Agent Memory (Critical Patterns — Load Into Agent Memory on Every Session)

These are lessons learned from recurring mistakes. Load all of these into the implementing agent's memory at session start.

### Architecture Laws
- Clean Architecture: core/ never imports from adapters/, workers/, memory/, or cli/
- workers/ imports from core/ and adapters/ only
- memory/ imports from core/ only
- adapters/ imports from core/ only
- cli/ imports from anywhere, nothing imports from cli/
- Async-first: every I/O operation is async
- Pydantic everywhere: no raw dicts cross boundaries
- Typed or rejected: every public function has return type annotation
- Observability built-in: every component emits TraceEvents
- No global state, no magic strings (use enums), no raw LLM calls outside adapters
- No memory access outside MemoryRouter
- Composition over inheritance

### Critical Test Patterns
- Always use AsyncMock (not MagicMock) when patching async functions in tests
- Import: `from unittest.mock import AsyncMock`
- All trace calls must be wrapped in try-except to prevent crashes
- Never use raw strings for enum values — always use the enum class
- Run tests with: `python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py`

### Custom Exceptions (core/exceptions.py)
- Always use `InvalidStateTransitionError` for illegal state transitions
- Always use `WorkerNotFoundError` for worker lookup failures (never raw ValueError)
- Always use `ApprovalDeniedError` for denied approvals
- Never raise raw ValueError or Exception for these cases

### Hardware Detection
- Hardware is detected automatically at runtime via system/profiler.py
- Never hardcode hardware assumptions into any implementation
- Always query SystemProfiler and ResourceManager for current hardware state
- Model selection must always be based on live hardware detection

### CHANGELOG Requirement
- Always maintain CHANGELOG.md (c:\Jarvis\CHANGELOG.md) with every implementation
- Update after each significant implementation or change
- Must include: changes made, architecture decisions, test results, rationale

### Architectural Risk — Read Before Prompt 14+
From Prompt 14 onward, systems begin multiplying interactions (approval ↔ state machine ↔ scheduler, worker factory ↔ model evaluator ↔ resource manager, etc.). Two rules to prevent uncontrolled coupling:
- **Never skip design decisions for load-bearing components.** The approval gate is touched by every subsequent prompt. Its invariants (denial behaviour, timeout handling, who can approve, batching rules) must be locked in writing before implementation.
- **Fix global state before building on it.** `_global_registry` and `_global_emitter` will be needed by monitor daemon, worker factory, and approval gate. Inject them via constructors now, not after 15 prompts have threaded them through.



### General Working Rules
- Run full test suite after every change, confirm zero regressions
- Verify Clean Architecture layer boundaries after every change
- Ask user before proceeding on any ambiguous decision
- Implement incrementally, test each component before moving to the next
- New test count must exceed the baseline after every prompt — if it does not, explain why in the CHANGELOG

### How The User Works With This Project
These are explicit preferences the user has stated. Follow them without being asked:

**Handoff document:**
- Update `SOVEREIGN_AI_HANDOFF.md` after every prompt completes — before sending the next prompt
- The handoff must always reflect true current state so any agent can pick up mid-session
- When a prompt runs out of order or is skipped, record it accurately — do not present incomplete work as complete

**Prompt sequencing:**
- Always update the handoff and confirm it is saved before sending the next prompt to Devin
- Never send the next prompt until the previous one's changelog entry has been received and the handoff updated
- If a prompt produces no new tests, flag it explicitly in the handoff completed table

**When things go wrong:**
- If Devin reports it is stuck, hitting errors, or batching multiple files — stop and assess state first
- Run the full state assessment (compile checks + test run + grep checks) before any further fixes
- If the codebase is in a broken state that cannot be cleanly fixed forward, recommend a git revert rather than piling fixes on top of broken code
- User prefers a clean revert over a messy partial fix

**Design before code on load-bearing components:**
- For any component that will be touched by 5+ future prompts, produce a design document first
- User reviews and confirms the design before implementation begins
- Prompt 13.6 (approval gate design doc) was skipped and caused a revert — do not repeat this

**Complexity management:**
- When multiple AI models flag complexity risks, take them seriously and pause before proceeding
- Insert housekeeping prompts when technical debt accumulates rather than deferring indefinitely
- Do not build new features on top of known broken or deprecated foundations

---

## User Domain Context

The system is being built for a user who works in:
- **Media production** — video scripts, content creation
- **3D printing and CNC machining** — file generation, design workflows
- **Sailing** — route planning, weather monitoring, AIS tracking (primary open-loop use case)

Workers to prioritise once the factory is operational:
- VideoScriptWorker
- ThreeDDesignWorker
- ResearchWorker
- NavigationWorker (sailing/AIS/weather)
- EmailWorker

---

## Source References (All Open Source, For Pattern Extraction)

- AutoGen (multi-agent deliberation): github.com/microsoft/autogen
- LangGraph (task state machines): github.com/langchain-ai/langgraph
- CrewAI (worker personas): github.com/crewAIInc/crewAI
- MemGPT/Letta (tiered memory): github.com/cpacker/MemGPT
- SWE-agent (task scratchpad): github.com/princeton-nlp/SWE-agent
