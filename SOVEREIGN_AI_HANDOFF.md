# Sovereign AI Agent Framework — Project Handoff Document

## Purpose
This document is a complete handoff brief for a prompting agent continuing
development of the Sovereign AI Agent Framework. It contains the project
vision, current state, completed work, and every remaining implementation
in order.

**Maintained by**: Devin — updated after every prompt as part of standard closing steps. Claude reads this document at session start but does not write to it.

**Last updated**: 2026-06-12 — post Prompt 27.5 completion. Three table-stakes skills implemented: Terminal (shell command execution with approval gating), Web Search (SearXNG/Brave Search with structured results), Code Execution (Python subprocess execution with approval gating). 33 new tests added. Windows compatibility fixes applied (timeout command, multiline code). Async test decorators used per-method in 27.5 — class-level pytestmark required from Prompt 28 onward per global_rules.md.

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

- **Devin** — writes all code, runs tests, updates `c:\Jarvis\CHANGELOG.md`, updates `SOVEREIGN_AI_HANDOFF.md` after every prompt. When Devin encounters a problem and solves it mid-prompt, save the solution to memory files immediately — do not wait for closing steps.
- **Claude** — reads this handoff document at session start to reconstruct state, advises on architecture and sequencing, maintains Devin memory entries
- **This handoff doc** is Devin-maintained. Devin updates it after every prompt as part of standard closing steps. Claude reads it but does not write to it.
- When the user pastes a CHANGELOG entry into Claude, Claude automatically produces the next prompt spec without waiting to be asked.

### Claude Responsibilities (Explicit)
After every coding prompt where a new recurring mistake is identified, Claude MUST:
1. Add a targeted entry to Devin's memory files — paste the text and instruct Devin to add it verbatim as part of the closing steps.
2. Add the pattern to Recurring Mistake Patterns in this document.
3. Embed a guard against the pattern in the next affected prompt spec.

### Claude Prompt Spec Standards (Mandatory — Apply to Every Spec)

Every prompt spec Claude produces MUST include the following structural elements.
These exist because memories and rules alone do not prevent mistakes at file
creation time — the spec itself must trigger the right behaviour at the right moment.

**1. Template instruction for every new system/ file**
When a prompt spec creates any new file in `system/`, the spec MUST include
immediately before that file's instructions:
> "Copy `system/NEWFILE_TEMPLATE.py` as your starting point. Do not create
> this file from blank. The template has the correct constructor signature,
> emitter injection, and TraceEvent pattern already in place."

This prevents the emitter injection mistake (Mistake Pattern 15) at the moment
of file creation, before Devin writes a single line.

**2. Per-file emitter reminder**
Every file spec that involves emitting trace events MUST include this line
immediately before the file's instructions:
> "This file uses constructor-injected emitter — Rule 2 in global_rules.md.
> Never use emit_trace() directly."

**3. Schema verification reminder**
Every file spec that uses schemas MUST include:
> "Read core/schemas.py to verify exact field names before writing any code
> that references those models."

**4. Baseline confirmation gate**
Every prompt spec MUST state the known baseline from the previous prompt's closing
test run. Do NOT instruct Devin to re-run the full suite before starting — the
previous prompt already confirmed it. The baseline run happens between file changes
and at the end of the prompt, not at the start.

Format:
> "The confirmed baseline from the previous prompt is: {N} passed, 23 skipped,
> 0 failed. Do not run the suite now — proceed directly to the pre-edit checklist.
> Run the suite only after each individual file change."

**5. Memory entries at the top**
All active memory entries are listed at the top of every spec, before the goal
and file instructions. They are labelled "active for this prompt" — not "save
these now." Saving happens mid-prompt when problems are solved, or at the end
of the previous prompt's closing steps.

**6. Pre-edit rules confirmation (mandatory before any file work begins)**
Every prompt spec MUST include this instruction block immediately after the
baseline confirmation gate, before any file work begins:

> "Before touching any file, re-read
> `C:\Users\King\.codeium\windsurf\memories\global_rules.md` in full.
> Then paste the following checklist with all boxes checked — do not edit
> any file until you have pasted it:
>
> PRE-EDIT CHECKLIST
> [ ] I have read global_rules.md in full
> [ ] I will fix each production file and its test file together as one unit
>     before moving to the next
> [ ] I will run the full test suite after each production+test pair and
>     confirm zero new failures before proceeding
> [ ] All emitters in files I touch are constructor-injected —
>     no global emit_trace()
> [ ] TraceEvent is imported from core/observability.py — not core/schemas.py
> [ ] I am not expanding scope beyond the files listed in this prompt"

**7. Per-file pre-edit statement (mandatory before each individual file)**
Every prompt spec MUST include this line immediately before each individual
file's instructions:

> "Before editing this file, state which global_rules.md rules apply to it
> and confirm its test file is included in this same step."

This forces an explicit retrieval and acknowledgement at the moment of each
edit, not just once at the start of the prompt. A model that has to articulate
which rules apply to a file before touching it is far less likely to violate
them than one relying on passive recall from earlier in the session.

---

## Architecture Overview

```
PERCEPTION LAYER
├── Open loop monitors (weather, AIS, email, news)
├── Scheduled checks (recurring tasks via MonitorDaemon)
└── Event triggers (conditional task firing)
        ↓
COGNITION LAYER
├── Orchestrator (LLM-driven, own instruction file, improves over time)
├── Worker Registry (persistent specialist agents)
├── Planning (task decomposition, state machines)
└── Deliberation (multi-worker, rating, escalation)
        ↓
ACTION LAYER
├── Skills (atomic capabilities, plugin architecture — see Skills Taxonomy below)
├── Services (Telegram, Email, Calendar, AIS, Weather APIs)
├── Adapters (12 LLM providers + MCP client behind unified protocol)
└── Gateways (Telegram — Prompt 28.5)
        ↓
MEMORY LAYER
├── Postgres (primary, structured, fast)
├── Qdrant (semantic search, scoped per worker)
└── Obsidian (human-readable mirror, audit trail)
        ↓
OUTPUT LAYER
├── TUI (current — Rich terminal interface)
├── Web GUI (Prompt 32 — FastAPI + React, served by jarvis serve)
├── Standalone desktop (wraps web UI — Electron/Tauri, post Phase 9)
└── Voice (Prompt 33)
```

---

## UI Architecture Decisions (Recorded 2026-06-11)

These decisions were made after competitive analysis of Hermes Agent,
OpenClaw, OpenHands, and NemoClaw. They govern all future UI work.

### FastAPI-first, UI-agnostic backend
- `jarvis serve` starts a local FastAPI server (port 7000 default)
- Exposes REST + WebSocket API
- All three surfaces (terminal, web, desktop) are clients of this API
- No feature exists in one surface that does not exist in others
- All logic lives in core — UI layer only renders and sends commands

### Web UI before standalone desktop
- Web UI served locally by FastAPI is effectively standalone (open in browser)
- Electron/Tauri wraps the same web UI later with zero UI code changes
- Build web UI first — desktop comes for free afterward

### Recommended navigation structure (all surfaces)
**Primary navigation:**
- Chat — main interaction, task submission, streaming responses
- Workers — active workers, status, performance scores, instruction files
- Tasks — task queue, state machine view, in-progress/completed/failed
- Memory — hot/warm/cold tier view, scoped memory browser, global context
- Approvals — pending approval queue (always accessible)

**Settings/Config:**
- Models — active adapter, model switching, hardware fit scores, Ollama model pull
- Services — connected services and their status (Postgres, Qdrant, Telegram, etc.)
- Skills — installed skills, enable/disable, MCP servers
- System — hardware profile, resource usage, VRAM/RAM, active model

**Admin:**
- Trace logs — observability stream from TraceEmitter
- Ratings — worker performance over time
- Instruction files — version history, pending proposals, approve/reject
- Setup — re-run setup wizard, reconfigure individual components

### Ollama model management
- On Ollama adapter selection, hit GET /api/tags to get locally available models
- Cross-reference with ModelRegistry and hardware profile — show only models that fit
- Pull new models in-app via POST /api/pull with progress bar (streams NDJSON)
- Never hardcode model names — always query Ollama live
- Show quantization details (Q4_K_M etc.) which map to ModelRegistry scoring

---

## Skills Taxonomy (Recorded 2026-06-11)

Three distinct extension types — never conflate them:

**LLM Adapters** — What model reasons?
Ollama, Gemini, OpenAI, Anthropic, OpenRouter, llama_cpp, etc.
Live in `adapters/`. 12 already built.

**Skills** — What can the agent do?
Atomic capabilities the agent calls during task execution.
Live in `skills/`. Plugin architecture defined in `skills/SKILL_SPECIFICATION.md`.
Currently: web_scraper, file_reader, file_writer (3 total).
Target: 40+ (see Skills Expansion Plan below).

**Services** — What data flows in and out?
External systems the agent monitors or communicates through.
Telegram, Email, Calendar, AIS, Obsidian, Postgres, Qdrant.
Wired via adapters or direct API integration.

**OpenClaw, Hermes, LangGraph** — None of these are integrations.
They are competing agent runtimes. Do not integrate them.
What IS relevant from their ecosystem: Ollama (adapter), MCP servers (skills),
Telegram/Discord (services).

---

## Skills Expansion Plan (Recorded 2026-06-11)

Competitive gap: Hermes ships 55 built-in tools + 80+ bundled skills.
OpenClaw has 2,857+ community skills. Jarvis has 3.
The MCP adapter (Prompt 22.5) closes the gap fastest — unlocks 1,500+
community MCP servers in one prompt. Build it early.

### Tier 1 — Core tools (table stakes, Prompt 27.5)
- `skills/terminal/` — shell command execution, ApprovalGate integration, configurable timeout
- `skills/web_search/` — Brave Search API or SearXNG (local, no API key)
- `skills/code_execution/` — Python sandbox, capture output, ApprovalGate integration

### Tier 2 — Personal assistant core (Prompt 28.6)
- `skills/email/` — IMAP read + SMTP send, works with any provider
- `skills/calendar/` — local ICS file first, Google Calendar later via OAuth
- `skills/reminder/` — persistent reminders in Postgres, delivered via Telegram
- `skills/notes/` — Obsidian integration surfaced as skill (vault already in memory layer)
- `skills/calculator/` — math, unit conversions, works fully offline

### Tier 3 — Jarvis-unique marine stack (Prompt 28.7) — PRIMARY DIFFERENTIATOR
No competitor has any of these. This is the moat.
- `skills/weather/` — OpenMeteo API (free, no key), current + 7-day forecast
- `skills/marine_weather/` — OpenMeteo Marine API (free, no key): wave height, swell period, swell direction, wind waves, GRIB data
- `skills/ais/` — AISStream.io WebSocket API (free tier): track vessels by MMSI, position/speed/heading, collision alerts, anchorage monitoring
- `skills/passage_planner/` — combine weather window + tidal data + AIS traffic, recommend optimal departure time

### Tier 4 — Developer skills (Prompt 29.5)
- `skills/git/` — status, diff, commit, push, pull, branch, PR summaries
- `skills/docker/` — list/start/stop containers, inspect logs, exec
- `skills/http_client/` — generic HTTP requests, enables one-off API integrations
- `skills/database/` — SQL queries against configured Postgres instance

### Tier 5 — Productivity skills (Prompt 29.6)
- `skills/pdf/` — extract text from PDFs, generate PDFs from markdown
- `skills/spreadsheet/` — read/write CSV and Excel files
- `skills/clipboard/` — read/write system clipboard
- `skills/screenshot/` — screen capture, pass to vision model

### Tier 6 — Environment and media skills (Prompt 30.5)
- `skills/home_assistant/` — Home Assistant REST API, list entities, call services (lights, switches, climate, sensors)
- `skills/tts/` — local Piper TTS (no API key, CPU) or ElevenLabs
- `skills/transcription/` — local Whisper (no API key, CPU), transcribe voice/audio
- `skills/image_generation/` — FAL.ai or local ComfyUI

### Tier 7 — Marine specialist skills (Prompt 31.5)
- `skills/vhf_monitor/` — VHF/DSC integration, distress signal monitoring
- `skills/tidal/` — WorldTides API, tidal predictions for passage planning
- `skills/satellite_comms/` — Iridium/Inmarsat integration for offshore connectivity

### MCP Gateway (Prompt 22.5 — highest leverage item)
Once built, unlocks instantly: GitHub, Notion, Slack, Google Calendar,
PostgreSQL, Brave Search, Filesystem, and 1,500+ community MCP servers.
This single prompt closes more of the integration gap than any other.

### Skill development rules
- Every skill follows `skills/SKILL_SPECIFICATION.md` exactly
- Minimum 8 tests per skill
- No new core/ changes — skills import from core/ only
- ApprovalGate integration mandatory for any skill that writes files, executes code, or makes network requests
- Skills grouped 3-5 per prompt, sharing same test infrastructure

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
11. `skills/` may import from `core/` only — never from `adapters/`, `cli/`, or `memory/` directly

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

1. Run full test suite — confirm zero regressions, count exceeds previous baseline. A higher count with failures does NOT satisfy this step.
2. Merge feature branch into master
3. Update `c:\Jarvis\CHANGELOG.md` — must include Implementation Notes documenting any problems hit mid-implementation and how they were resolved. A CHANGELOG entry with no implementation notes is only acceptable for trivial single-file changes.
4. Update `SOVEREIGN_AI_HANDOFF.md` directly with these changes:
   - Add completed prompt row to Completed Prompts table
   - Update Current State section: test baseline, checkpoint tag, warnings count
   - Update Remaining Implementation Plan: mark this prompt DONE, mark next prompt IN PROGRESS
   - Do NOT modify: Recurring Mistake Patterns, Architecture Rules, Project Vision, or prompt spec content
   - Do NOT reformat or restructure any section — append/update only
5. `git add . && git commit -m "checkpoint: prompt-{N}"`
6. `git tag prompt-{N}`
7. `git push origin master`
8. `git push origin prompt-{N}`
9. Update Memory 1 in memory files with new checkpoint and test baseline
10. If any new problems were encountered and solved during this prompt, save solutions to memory files immediately — they should already be saved mid-prompt, but confirm here

---

## Current State

### Test Baseline
- **585 passed, 23 skipped, 8 warnings** (as of Prompt 27.5 / checkpoint prompt-27-5)
- Baseline is dynamic — every prompt must exceed the previous count
- Skipped: `tests/test_llama_cpp_adapter.py` (missing llama_cpp dependency)
- 8 warnings: FutureWarning from adapters/gemini.py — deferred to Phase 9, do not touch; PytestWarning for 2 async decorator marks on sync methods in test_model_evaluator.py — harmless; PytestUnraisableExceptionWarning for unclosed asyncio transports in subprocess tests — Windows-specific, harmless
- Run with: `python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py`

### Known Issues from Prompt 27.5
- None — all three core skills implemented with full test coverage

### Git / Backup
- Repo: `https://github.com/AngusKingC/sovereign-ai` (private)
- Latest checkpoint tag: `prompt-27-5`
- Checkpoint script: `python scripts/checkpoint.py prompt-{N}` (unreliable — do manually)
- Restore script: `python scripts/restore.py`

### Core Layer
- `core/schemas.py` — all Pydantic models including TaskStatus.DENIED, EvaluatorScore, EvaluationRecord, OrchestratorMetrics
- `core/memory_router.py` — MemoryBackend ABC, MemoryRouter with tracing, scoped_write/read, get/set_global_context, compactor integration
- `core/worker_base.py` — LLMResponse, LLMAdapter Protocol, WorkerBase ABC (DI)
- `core/orchestrator.py` — routing with scoring algorithm, deregister_worker, mark_task_completed integration, DI complete (escalation engine integration disabled in Prompt 26 — debt)
- `core/handlers.py` — QueryHandler, DI complete
- `core/embedder.py` — OllamaEmbedder
- `core/escalation.py` — EscalationEngine with evaluate(), request_approval(), execute_escalation() (wiring to orchestrator disabled — debt)
- `core/observability.py` — TraceEmitter, MemoryTraceEmitter, ConsoleTraceEmitter
- `core/commands.py` — CommandRegistry, DI complete
- `core/exceptions.py` — InvalidStateTransitionError, WorkerNotFoundError, ApprovalDeniedError, CrossScopeAccessError
- `core/task_state_machine.py` — validated transitions, DENIED terminal state, full history tracking, checkpoint()/load_checkpoints() stubs
- `core/scratchpad.py` — ScratchpadManager, per-task ephemeral working memory
- `core/session.py` — SessionManager, Postgres persistence
- `core/skill_registry.py` — skill discovery, validation, query
- `core/approval_gate.py` — ApprovalGate, ApprovalRequest, ApprovalResponse, ApprovalScope, session-scoped pre-authorisation, write-through Postgres cache
- `core/worker_factory.py` — WorkerFactory, DynamicWorkerProfile, PlaceholderWorker, rule-based worker creation
- `core/rating_system.py` — RatingSystem, worker rating persistence, trend analysis
- `core/instruction_generator.py` — InstructionGenerator, LLM-based instruction file generation
- `core/instruction_versioning.py` — InstructionVersionManager, version control for instruction files
- `core/orchestrator_improvement.py` — OrchestratorImprovementLoop, orchestrator self-improvement
- `core/evaluator.py` — OutputEvaluator, LLM-as-Judge automated output evaluation
- `core/memory_compactor.py` — MemoryCompactor, MemoryTier enum, TieredMemoryEntry, background compaction

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
- `cli/main.py` — entry point, constructs TraceEmitter and CommandRegistry, first-run setup wizard, setup/doctor commands
- `cli/adapter_factory.py` — create_adapter(), create_worker()
- `cli/command_history.py` — persistent history, tab completion
- `cli/setup_wizard.py` — SetupWizard class, interactive first-run configuration, jarvis.config.yaml and .env generation

### System Layer
- `system/profiler.py` — SystemProfiler
- `system/model_registry.py` — ModelRegistry, seed data, HW-fit recommendation
- `system/resource_manager.py` — ResourceManager, eviction priority queue
- `system/model_acquisition.py` — ModelAcquisition, HuggingFace integration
- `system/monitor_daemon.py` — MonitorDaemon, ScheduledTask, TaskScheduleType, persistent background scheduler

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
| 23 | Memory Scoping | 437 |
| 24 | Escalation Engine | 469 |
| 25 | Tiered Memory Compaction | 488 |
| 26 | Monitor Daemon + Task Checkpointing | 501 |
| 27 | Emitter Injection, Key-Based Query, and Event Trigger System | 535 |
| 26.5 | Setup Wizard (First-Run Configuration) | 551 |
| 27.5 | Core Skills: Terminal, Web Search, Code Execution | 585 |

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
- Implemented as stubs in Prompt 26 — full implementation requires key-pattern
  querying in MemoryRouter

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

### Skills and UI Review Changes (Incorporated 2026-06-11)

Full competitive skills analysis conducted against Hermes Agent (55 built-in
tools, 80+ bundled skills) and OpenClaw (2,857+ community skills).

**Key findings:**
- Jarvis architecture is ahead — hardware-aware model selection, formal worker
  rating + instruction versioning, approval gate built into core, tiered memory
  compaction — none of these exist in competitors
- Jarvis tools/skills are behind — 3 vs 55+ built-in tools
- MCP adapter (Prompt 22.5) is highest-leverage single item — closes integration
  gap faster than any other prompt
- Marine/sailing stack (AIS, marine weather, passage planning) is unique moat —
  no competitor has any of this

**Setup wizard added as Prompt 26.5:**
- First-run interactive wizard using Rich (already in project)
- Detects running Ollama automatically, pre-selects it
- Shows only models that fit detected hardware (unique advantage — no competitor does this)
- Covers: adapter, model, Postgres, Qdrant, Obsidian, approval gate defaults, Telegram
- Writes jarvis.config.yaml (structured config) and .env (API keys, never in config)
- Re-run with: jarvis setup --reconfigure
- jarvis doctor command: diagnose issues without reconfiguring

**Full skills expansion plan added to roadmap (Prompts 27.5 through 31.5):**
- See Skills Expansion Plan section above for complete taxonomy and groupings
- Priority order: terminal + web_search + code_execution → email + calendar →
  marine stack → developer skills → productivity skills → environment/media skills

**FastAPI-first UI architecture adopted:**
- jarvis serve starts local FastAPI server (port 7000)
- All surfaces (terminal, web, desktop) are clients of this API
- Web UI served by FastAPI, desktop wraps web UI later
- See UI Architecture Decisions section above for full specification

---

### PHASE 4 — The Worker Factory (Complete)

#### Prompt 16 — Model Evaluation Logic — DONE
#### Prompt 16.5 — WorkerProfile Schema Lock — DONE
#### Prompt 17 — Worker Persistence — DONE
#### Prompt 18 — Rating System — DONE
#### Prompt 19 — Instruction File Generation — DONE

---

### PHASE 5 — Self-Improvement Loop (Complete)

#### Prompt 20 — Instruction File Versioning and Updates — DONE
#### Prompt 21 — Orchestrator Improvement Loop — DONE
#### Prompt 22 — Unified Evaluation Framework — DONE

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

Tests: minimum 10. Target: exceed 501.

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

### PHASE 6 — Memory Architecture (Complete)

#### Prompt 23 — Memory Scoping — DONE
#### Prompt 24 — Escalation Engine — DONE
#### Prompt 25 — Tiered Memory Compaction — DONE

---

### PHASE 7 — Open Loop System (The Jarvis Layer)

---

#### Prompt 26 — Monitor Daemon + Task Checkpointing
**Status**: DONE

`system/monitor_daemon.py` — persistent background heartbeat process.
Scheduler: immediate, deferred, recurring, conditional tasks.
Task queue persisted via MemoryRouter — survives restarts.
Approval gate integration — daemon never blocks on approval.
TaskStateMachine.checkpoint() and load_checkpoints() implemented as stubs —
full implementation requires key-pattern querying in MemoryRouter.

---

#### Prompt 26.5 — Setup Wizard (New — added 2026-06-11)
**Status**: DONE

First-run interactive setup wizard using Rich terminal UI.
Triggered automatically when no config file exists.
Re-run with: `jarvis setup --reconfigure`.

Files:
- `cli/setup_wizard.py` — SetupWizard class
- `jarvis.config.yaml` — written by wizard (structured settings)
- `.env` — API keys only, never in config file

Wizard flow (in order):
1. Preflight — silently check Python version, Postgres, Qdrant reachable. Report what is missing.
2. LLM Adapter — show available adapters. If Ollama is running locally, auto-detect and pre-select.
3. Model — query Ollama /api/tags, cross-reference with hardware profile, show only models that fit. Flag recommended default.
4. Database — Postgres connection string with default, test connection before proceeding.
5. Memory — Qdrant connection, test connection.
6. Obsidian vault — path to vault, optional, skip-able.
7. Approval gate defaults — always ask / auto-approve low-risk actions.
8. Telegram — optional, skip-able. Requires bot token.
9. Review summary — show all choices before writing config. Allow 'back' at any prompt.
10. Write config — write jarvis.config.yaml, never overwrite without confirmation.

Additional commands:
- `jarvis doctor` — diagnose issues, check connections, verify credentials, report what is broken. Does not reconfigure.
- `jarvis setup --reconfigure` — re-run wizard with current values as defaults. Press Enter to keep.

Architecture:
- `cli/setup_wizard.py` imports from `cli/` and `core/` only
- Reads hardware profile from SystemProfiler (already built)
- Reads model list from Ollama /api/tags directly
- Reads hardware fit from ModelRegistry (already built)
- No core/ changes

Tests: minimum 10.

---

#### Prompt 27 — Event Trigger System
**Status**: DONE

`core/event_trigger.py` — conditional tasks on data conditions.
Trigger types: threshold, schedule, change detection.
TriggerEngine with register, unregister, ingest_metric, evaluate_schedule_triggers.
Integrated into MonitorDaemon with ingest_metric() method and schedule trigger evaluation.
27 tests added for event trigger system.

---

#### Prompt 27.5 — Core Skills: Terminal, Web Search, Code Execution (New — added 2026-06-11)
**Status**: DONE

Table-stakes skills. Without these Jarvis is not a usable product.
Hermes ships all three as built-in tools on day one.

Files:
- `skills/terminal/` — shell command execution
- `skills/web_search/` — Brave Search API or SearXNG (local, no API key required)
- `skills/code_execution/` — Python sandbox

`skills/terminal/`:
- Runs arbitrary shell commands via subprocess
- Captures stdout, stderr, return code
- ApprovalGate integration — commands require approval unless pre-authorised
- Configurable working directory and timeout (default 30s)
- Never executes without user authorisation

`skills/web_search/`:
- SearXNG preferred (self-hosted, no API key, full privacy)
- Brave Search API as fallback (requires API key)
- Returns structured results: title, URL, snippet, source
- Configurable max results

`skills/code_execution/`:
- Executes Python in a subprocess sandbox
- Captures output, handles errors and timeouts
- ApprovalGate integration — execution requires approval
- Isolated from main process

Architecture: all three import only from `core/`. ApprovalGate injected via constructor.
Tests: minimum 8 per skill (24 total). Target: exceed Prompt 27 baseline.

---

#### Prompt 28 — Interrupt and Notification Layer
**Status**: IN PROGRESS

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
- Outbound: receives notifications from NotificationSystem, delivers to configured Telegram chat ID
- Inbound: receives messages from Telegram, routes to QueryHandler as tasks
- ApprovalGate integration: action-request notifications sent via Telegram include approve/reject reply options; responses route through existing gate
- Runs as optional background service — system functions without it
- Config: bot token and chat ID loaded from env vars, never hardcoded
- Emitter injected via constructor, default MemoryTraceEmitter()
- `adapters/telegram_gateway.py` imports only from `core/`

Tests: minimum 10.

---

#### Prompt 28.6 — Personal Assistant Skills: Email, Calendar, Reminder, Notes (New — added 2026-06-11)
**Status**: Queued

Files:
- `skills/email/` — IMAP read + SMTP send
- `skills/calendar/` — local ICS file first, extensible to Google Calendar
- `skills/reminder/` — persistent reminders in Postgres, delivered via Telegram
- `skills/notes/` — Obsidian vault integration surfaced as skill

`skills/email/`: IMAP (imaplib) for reading, SMTP (smtplib) for sending.
Works with Gmail, ProtonMail, any provider. Credentials in .env only.
ApprovalGate for sending.

`skills/calendar/`: Read/write local .ics files. Parse upcoming events,
create/modify/cancel entries. Natural language date parsing.
Extensible to Google Calendar via OAuth in a later prompt.

`skills/reminder/`: Reminders stored in Postgres with target datetime and
delivery channel. Monitor daemon polls and delivers via Telegram when due.

`skills/notes/`: Obsidian vault already in memory layer — surface as skill.
Create, search, edit notes via natural language. Read from vault, write to vault.

Tests: minimum 8 per skill (32 total).

---

#### Prompt 28.7 — Marine Stack: Weather, AIS, Marine Weather (New — added 2026-06-11)
**Status**: Queued

Primary differentiator. No competitor has any of these skills.
This is the moat that makes Jarvis unique for sailing and maritime use cases.

Files:
- `skills/weather/` — general weather via OpenMeteo
- `skills/marine_weather/` — marine-specific data via OpenMeteo Marine API
- `skills/ais/` — vessel tracking via AISStream.io

`skills/weather/`:
- OpenMeteo API (completely free, no API key, open-source)
- Current conditions, 7-day forecast
- Wind speed/direction, precipitation, temperature, UV index
- Works fully offline with cached data for short periods

`skills/marine_weather/`:
- OpenMeteo Marine API (free, no key required)
- Wave height, swell period, swell direction, wind waves
- 7-day marine forecast
- GRIB data parsing for passage planning
- Integrates with monitor daemon for automatic weather window alerts

`skills/ais/`:
- AISStream.io WebSocket API (free tier available)
- Track vessels by MMSI number
- Returns: position, speed, heading, destination, vessel name, vessel type
- Collision alerts: notify when tracked vessel enters defined radius
- Anchorage monitoring: alert when vessel moves unexpectedly
- Integrates with event trigger system for condition-based alerts

Tests: minimum 8 per skill (24 total).

---

### PHASE 8 — Multi-Worker Deliberation

---

#### Prompt 29 — Resource Budgeting
**Status**: Queued

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

#### Prompt 29.5 — Developer Skills: Git, Docker, HTTP Client (New — added 2026-06-11)
**Status**: Queued

Files:
- `skills/git/` — Git operations
- `skills/docker/` — Docker container management
- `skills/http_client/` — generic HTTP requests

`skills/git/`: status, diff, commit, push, pull, branch management.
PR summaries via GitHub/GitLab API. ApprovalGate for write operations.

`skills/docker/`: list containers, start/stop, inspect logs, exec into container.
ApprovalGate for start/stop/exec operations.

`skills/http_client/`: make arbitrary HTTP GET/POST requests.
Enables one-off API integrations without a dedicated skill.
ApprovalGate for POST/PUT/DELETE requests.

Tests: minimum 8 per skill (24 total).

---

#### Prompt 29.6 — Productivity Skills: PDF, Spreadsheet, Clipboard, Calculator (New — added 2026-06-11)
**Status**: Queued

Files:
- `skills/pdf/` — PDF reading and generation
- `skills/spreadsheet/` — CSV and Excel file operations
- `skills/clipboard/` — system clipboard read/write
- `skills/calculator/` — math and unit conversions

Tests: minimum 8 per skill (32 total).

---

#### Prompt 30 — Multi-Worker Mode
**Status**: Queued

Route same task to top N workers concurrently.
Resource budget enforced — only dispatch if budget allows.
ResourceManager consulted for live memory state.
Responses surfaced side by side. User selection feeds rating system.

---

#### Prompt 30.5 — Environment and Media Skills: Home Assistant, Screenshot, TTS, Transcription (New — added 2026-06-11)
**Status**: Queued

Files:
- `skills/home_assistant/` — Home Assistant REST API (Hermes ships this built-in — parity)
- `skills/screenshot/` — screen capture, pass to vision model
- `skills/tts/` — text to speech (local Piper TTS, no API key required)
- `skills/transcription/` — audio transcription (local Whisper, no API key required)

Tests: minimum 8 per skill (32 total).

---

#### Prompt 31 — Worker-to-Worker Communication
**Status**: Queued

Workers emit sub-task requests during execution.
Orchestrator routes sub-tasks to specialist workers.
Circular dependency detection. Sub-tasks inherit parent priority.

**Extended scope (competitive review 2026-06-10):**
Implement internal worker messaging against A2A (Agent-to-Agent) protocol
standard rather than a proprietary schema.

Files:
- `core/a2a_protocol.py` — thin schema + routing layer, imports only from `core/`

A2A-standard task envelope schema:
- Request: `task_id`, `input`, `metadata`, `requester_agent_id`
- Response: `task_id`, `status`, `output`, `artifacts`

---

#### Prompt 31.5 — Marine Specialist Skills: Passage Planner, Tidal, VHF (New — added 2026-06-11)
**Status**: Queued

Files:
- `skills/passage_planner/` — sailing passage planning
- `skills/tidal/` — tidal data and predictions
- `skills/image_generation/` — image generation (FAL.ai or local ComfyUI)

`skills/passage_planner/`:
- Combines weather window (from marine_weather skill) + tidal data + AIS traffic
- Given departure and destination, recommends optimal departure time
- Considers wind angle, sea state, tidal gates, vessel traffic
- Genuinely unique — no competitor has this

`skills/tidal/`:
- WorldTides API for tidal predictions
- Tidal height, time of high/low water, tidal stream direction and rate
- Used by passage_planner skill

Tests: minimum 8 per skill (24 total).

---

### PHASE 9 — Interfaces

---

#### Prompt 32 — Web GUI + FastAPI Server
**Status**: Queued (expanded from original scope — 2026-06-11)

`web/` layer — FastAPI server + WebSockets + React or plain HTML frontend.

**FastAPI server (jarvis serve):**
- Starts on port 7000 by default
- REST API + WebSocket endpoints
- All terminal, web, and future desktop surfaces connect to this API
- Serves web UI static files

**Web UI navigation** (see UI Architecture Decisions section):
- Primary: Chat, Workers, Tasks, Memory, Approvals
- Settings: Models (with Ollama pull), Services, Skills, System
- Admin: Trace logs, Ratings, Instruction files, Setup

**Ollama model management in UI:**
- Queries /api/tags live for locally available models
- Shows hardware fit score from ModelRegistry alongside each model
- Pull new models with progress indicator

Architecture:
- `web/` imports from `core/` only
- `jarvis serve` command added to CLI

---

#### Prompt 33 — Voice Interface
**Status**: Queued

Wake word detection, Whisper STT, TTS.
Voice notifications for open loop events.
Same approval gates and observability as text interface.

---

### PHASE 10 — Model Evolution (New — added 2026-06-10)

---

#### Prompt 34 — Trajectory Export / Fine-tuning Pipeline
**Status**: Queued

Close the self-improvement loop at the model weights level.

Files:
- `system/trajectory_exporter.py` — TrajectoryExporter class

Features:
- Reads completed task traces from TraceEmitter event log via MemoryRouter
- Filters by quality threshold (OutputEvaluator final_score >= configurable minimum — default 0.7)
- Exports in ShareGPT format (.jsonl) — compatible with Axolotl, Unsloth, standard fine-tuning pipelines
- Export modes: manual trigger, scheduled export, minimum trace count threshold
- Trajectory compression: fits training data into token budgets
- No model training infrastructure in scope — export pipeline only

Architecture:
- Emitter injected via constructor, default MemoryTraceEmitter()
- All I/O async, all public methods typed
- Export path configurable via constructor, never hardcoded
- `system/trajectory_exporter.py` imports from `core/` and `system/` only

Tests: minimum 12.

---

## Technical Debt

| Item | Location | Notes |
|------|----------|-------|
| google.generativeai FutureWarning | adapters/gemini.py | Do not touch until Phase 9 |
| RuntimeWarning coroutine never awaited | skills/web_scraper tests | Do not touch |
| llama.cpp tests skipped | tests/test_llama_cpp_adapter.py | Missing dependency |
| Escalation logic removed from orchestrator | core/orchestrator.py | Removed in Prompt 26 regression fix — re-wire correctly in future prompt |
| test_escalation.py skipped | tests/test_escalation.py | Skipped in Prompt 26 — re-enable when escalation re-wired |
| _restore_queue() stub | system/monitor_daemon.py | Requires key-pattern querying in MemoryRouter |
| load_checkpoints() stub | core/task_state_machine.py | Same dependency as above |
| MemoryRouter key-pattern query | core/memory_router.py | Needed for stubs above — add in Prompt 27 or dedicated housekeeping |
| Model selection modal incomplete | cli/tui.py | Phase 9 (Setup Wizard Prompt 26.5 addresses partially) |
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
7. Wrong TraceEvent field names (used layer/payload/success) → correct fields are event_type, component, level, message, data, duration_ms
8. Using `emitter.events` instead of `emitter.get_events()`
9. Raising domain exceptions inside try-except that catches them → exception silently swallowed, raise OUTSIDE try-except
10. Asserting `"string" in event.data` where data is a dict → checks keys not values, use `event.component == X` instead
11. Mock objects don't behave like dicts when calling .get() — use proper dict structures in mock return values, not Mock() objects
12. Test state bleeds between tests when mutating Pydantic model fields directly — always reset fields like version explicitly in each test that depends on them
13. Dual-trigger collision in InstructionVersionManager — rating-trend trigger (Prompt 20) and trace-score trigger (Prompt 22.6) can both fire for the same worker. InstructionVersionManager MUST check for an existing PENDING proposal before creating a new one. If PENDING exists, skip and return it.
14. Removing working logic to fix test failures instead of fixing the tests — escalation logic was removed from orchestrator in Prompt 26 to fix a test failure. The correct fix is to repair the test, not remove the implementation. When a regression appears, find the root cause first.
15. Using global emit_trace() instead of injected emitter in new files — MonitorDaemon was built using global emit_trace() rather than injected emitter, breaking DI rules. All new files must use constructor-injected emitter from the start.
16. Stub methods that depend on unbuilt infrastructure left undocumented — _restore_queue() and load_checkpoints() are stubs with a hidden dependency on key-pattern querying in MemoryRouter. Always document stub dependencies explicitly in CHANGELOG and technical debt table.
17. Fixing production files without simultaneously fixing their tests — DI sweep removed emit_trace from production files but left tests patching module.emit_trace, causing 39 AttributeError failures. Fix is always: production file and its test file as one atomic unit, full suite run, then next file.
18. Using per-method @pytest.mark.asyncio instead of class-level pytestmark — Prompt 27.5 used per-method decorators for async tests, but global_rules.md mandates class-level pytestmark for all async test classes. From Prompt 28 onward, use pytestmark at class level, not per-method decorators.

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
- NavigationWorker (sailing/AIS/weather — highest priority unique capability)
- EmailWorker

---

## Source References

- AutoGen: github.com/microsoft/autogen
- LangGraph: github.com/langchain-ai/langgraph
- CrewAI: github.com/crewAIInc/crewAI
- MemGPT/Letta: github.com/cpacker/MemGPT
- SWE-agent: github.com/princeton-nlp/SWE-agent
- Hermes Agent: github.com/NousResearch/hermes-agent (55 built-in tools, 80+ bundled skills)
- Hermes tools reference: hermes-agent.nousresearch.com/docs/reference/tools-reference
- Hermes skills catalog: hermes-agent.nousresearch.com/docs/reference/skills-catalog
- OpenJarvis: github.com/open-jarvis/OpenJarvis
- OpenClaw: github.com/OpenClaw (2,857+ community skills on ClawHub)
- agentskills.io: open standard for portable agent skills (MCP-compatible)
- A2A Protocol: google-deepmind.github.io/agent-to-agent
- AISStream.io: aisstream.io (free WebSocket API for live vessel tracking)
- OpenMeteo: open-meteo.com (free weather + marine API, no key required)
- WorldTides API: worldtides.info (tidal predictions)
- Ollama API: localhost:11434/api (model management and inference)
