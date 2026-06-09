# Sovereign AI Agent Framework — Project Handoff Document

## Purpose
This document is a complete handoff brief for a prompting agent continuing
development of the Sovereign AI Agent Framework. It contains the project
vision, current state, completed work, and every remaining implementation
in order.

**Maintained by**: Claude (claude.ai) — NOT Devin. Claude updates this
document during each working session. Devin never reads or writes this file.

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

- **Devin** — writes all code, runs tests, updates `c:\Jarvis\CHANGELOG.md`
- **Claude** — tracks project state, manages this handoff document, prepares
  prompts for Devin, advises on architecture and sequencing, maintains Devin
  memory entries
- **This handoff doc** is Claude-to-Claude only. It is never fed to Devin.
- Claude updates this document within each session and produces a new version
  at ~90% context usage to prepare for the next Claude session.

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

---

## Current State

### Test Baseline
- **311 passed, 23 skipped, 0 failures** (as of Prompt 14 / checkpoint prompt-14)
- Baseline is dynamic — every prompt must exceed the previous count
- Skipped: `tests/test_llama_cpp_adapter.py` (missing llama_cpp dependency)
- Run with: `python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py`

### Git / Backup
- Repo: `https://github.com/AngusKingC/sovereign-ai` (private)
- Latest checkpoint tag: `prompt-14`
- Checkpoint script: `python scripts/checkpoint.py prompt-{N}`
- Restore script: `python scripts/restore.py`

### Core Layer
- `core/schemas.py` — all Pydantic models including TaskStatus.DENIED
- `core/memory_router.py` — MemoryBackend ABC, MemoryRouter with tracing
- `core/worker_base.py` — LLMResponse, LLMAdapter Protocol, WorkerBase ABC (DI)
- `core/orchestrator.py` — routing with scoring algorithm, DI complete
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
| 15 | Worker Factory | IN PROGRESS |

---

## Remaining Implementation Plan

### PHASE 4 — The Worker Factory (Current)

---

#### Prompt 15 — Worker Factory
**Status**: ⚠️ IN PROGRESS — prompt sent to Devin, awaiting changelog

Create `core/worker_factory.py` — dynamic worker creation from natural
language description.

Features:
- `WorkerFactory` class with constructor injection
  (SkillRegistry, Orchestrator, MemoryRouter, TraceEmitter)
- `create_worker(description, task)` — rule-based profile generation,
  skill matching, worker registration, memory persistence
- `can_route(task)` — checks if orchestrator has suitable worker
- `get_or_create_worker(task)` — routes or creates as needed
- `list_workers()` — returns all registered profiles
- `deregister_worker(worker_id)` — removes from orchestrator
- Add `deregister_worker` to `core/orchestrator.py`
- No LLM calls — rule-based only (LLM generation in Prompt 17)
- Minimum 14 new tests in `tests/test_worker_factory.py`
- Target: exceed 311 passed

---

#### Prompt 16 — Model Evaluation Logic
**Status**: Queued

Create `system/model_evaluator.py`.

Evaluation criteria (in order):
1. Hardware fit — query ResourceManager
2. Task suitability — query ModelRegistry tags
3. Quality vs speed preference — user-configurable per worker type
4. Web research — HuggingFace model cards for benchmark data

Output: ranked model recommendations with reasoning, user confirms before
assignment. Selection stored against worker profile.

---

#### Prompt 17 — Instruction File Generation
**Status**: Queued

Create `core/instruction_generator.py`.

Each worker gets in Obsidian:
- `WORKER_NAME_INSTRUCTION.md` — role, goal, persona, capabilities,
  constraints, output format, examples, model-specific optimisations
- `WORKER_NAME_INSTRUCTION_CHANGELOG.md` — append-only, version/date/
  change/rating trend/diff summary

Orchestrator gets identical files.
LLM-based worker profile generation replaces rule-based from Prompt 15.

---

#### Prompt 18 — Worker Persistence
**Status**: Queued

Full worker survival across restarts.

Features:
- Worker definitions serialised to Postgres on create/update
- Obsidian mirror on every change
- Registry loaded from Postgres on startup
- Worker versioning — changes create new version, old preserved
- Worker status tracking (active, idle, deprecated)

---

#### Prompt 19 — Rating System
**Status**: Queued

Create `core/rating_system.py`.

Features:
- Rating stored with: worker_id, instruction_file_version, model_used,
  task_id, score, optional comment
- Multi-worker comparison mode
- Rating history queryable per worker/model/instruction version
- Trend analysis: moving average per worker over time
- Postgres primary, Obsidian summary

---

### PHASE 5 — Self-Improvement Loop

---

#### Prompt 20 — Instruction File Versioning and Updates
**Status**: Queued

Version and update mechanism for instruction files.
Update triggered when rating trend drops below threshold.
Proposed update requires user approval. Rollback available.

---

#### Prompt 21 — Orchestrator Improvement Loop
**Status**: Queued

Wire orchestrator into same improvement loop as workers.
Orchestrator reviews worker ratings, proposes instruction edits.
Own performance tracked (routing accuracy, task completion rate).

---

#### Prompt 22 — LLM-as-Judge Evaluator
**Status**: Queued

Create `core/evaluator.py`.
Automated output scoring: task completion, accuracy, format, conciseness.
Separate fast lightweight evaluator model.
Manual rating overrides evaluator score.

---

### PHASE 6 — Memory Architecture

---

#### Prompt 23 — Memory Scoping
**Status**: Queued

Worker-scoped memory partitions + shared global context layer.
`StrategicContext` becomes data model for shared global context.
MemoryRouter enforces scoping — rejects cross-scope access.

---

#### Prompt 24 — Wire EscalationDecision
**Status**: Queued

`EscalationDecision` schema exists but nothing uses it.
Escalation hierarchy: local → better local → cloud.
Always requires user approval unless pre-authorised.

---

#### Prompt 25 — Tiered Memory Compaction
**Status**: Queued

Hot/warm/cold memory tiers with periodic background compaction.
Hot: in-context. Warm: Qdrant. Cold: Postgres archival.

---

### PHASE 7 — Open Loop System (The Jarvis Layer)

---

#### Prompt 26 — Monitor Daemon
**Status**: Queued

`system/monitor_daemon.py` — persistent background heartbeat process.
Scheduler: immediate, deferred, recurring, conditional tasks.
Task queue persisted in Postgres.

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

---

### PHASE 8 — Multi-Worker Deliberation

---

#### Prompt 29 — Multi-Worker Mode
**Status**: Queued

Route same task to top N workers concurrently.
Resource Manager consulted for memory constraints.
Responses surfaced side by side. User selection feeds rating system.

---

#### Prompt 30 — Worker-to-Worker Communication
**Status**: Queued

Workers emit sub-task requests during execution.
Orchestrator routes sub-tasks to specialist workers.
Circular dependency detection. Sub-tasks inherit parent priority.

---

### PHASE 9 — Interfaces

---

#### Prompt 31 — Web GUI
**Status**: Queued

`web/` layer — FastAPI + WebSockets + React frontend.
Mirrors all TUI functionality.
`web/` imports from `core/` only.

---

#### Prompt 32 — Voice Interface
**Status**: Queued

Wake word detection, Whisper STT, TTS.
Voice notifications for open loop events.
Same approval gates and observability as text interface.

---

## Known Technical Debt

| Item | Location | Notes |
|------|----------|-------|
| google.generativeai FutureWarning | adapters/gemini.py | Do not touch |
| RuntimeWarning coroutine never awaited | skills/web_scraper tests | Do not touch |
| llama.cpp tests skipped | tests/test_llama_cpp_adapter.py | Missing dependency |
| StrategicContext orphaned | core/schemas.py | Addressed in Prompt 23 |
| EscalationDecision orphaned | core/schemas.py | Addressed in Prompt 24 |
| Model selection modal incomplete | cli/tui.py | Phase 4 |
| No tests for session postgres | core/session.py | Prompt 11 debt |
| No tests for command_history | cli/command_history.py | Prompt 12 debt |

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

---

## Hardware Context

- **GPU**: NVIDIA RTX 3060 Mobile — 6GB VRAM
- **RAM**: ~15.6GB available after VRAM
- **OS**: Windows
- **Local LLM**: Ollama with `qwen2.5-coder:7b`
- **IDE**: Devin (SWE 1.6 Slow)
- **Hardware detected automatically at runtime — never hardcode**

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
