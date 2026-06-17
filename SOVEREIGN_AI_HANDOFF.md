# Sovereign AI Agent Framework — Project Handoff Document

## Purpose
This document is a complete handoff brief for a prompting agent continuing
development of the Sovereign AI Agent Framework. It contains the project
vision, current state, completed work, and every remaining implementation
in order.

**Maintained by**: Devin — updated after every prompt as part of standard closing steps. Claude reads this document at session start but does not write to it.

**Last updated**: 2026-06-17 — post Prompt 35.6b completion. submit_task/list_tasks added to Orchestrator, jarvis serve wired into CLI, full cognition stack wired into cli/serve.py. Test baseline: 1065 passed, 23 skipped, 64 warnings, 0 failed.

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

- **Devin** — writes all code, runs tests, updates `c:\Jarvis\CHANGELOG.md`, updates `SOVEREIGN_AI_HANDOFF.md` after every prompt. When Devin encounters a problem and solves it mid-prompt, save the solution to memory files immediately — do not wait for closing steps. When updating CHANGELOG.md, always append new entries to the bottom of the file. Never prepend. Every entry date must include time in format YYYY-MM-DD HH:MM.
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

Before stating the baseline, Claude must also include this tag verification instruction in every spec:

> "Before writing any code, run `git show prompt-{N-1} --stat | head -30` and read the output.
> Confirm the file list contains only files expected from Prompt N-1.
> If any unexpected file or test class appears, stop and raise it with the user before proceeding."

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

SECURITY LAYER (cross-cutting — Prompt 31.7, before Web GUI)
├── AuthManager — bearer token for all FastAPI/WebSocket surfaces
├── InputSanitiser — prompt injection hardening on all external inputs
├── ApprovalTrustRegistry — per-command trust memory, session blanket approval
└── Secrets audit — startup check that no keys are in config YAML
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
12. `web/` may import from `core/` only — never from `cli/`, `workers/`, or `adapters/` directly
13. `InputSanitiser` MUST be called on all externally-sourced content before it enters LLM context: web scraper output, Telegram inbound, user task input
14. `ApprovalTrustRegistry` MUST be consulted by `ApprovalGate` before raising any approval request — never bypass TrustRegistry even in tests
15. Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes — no unauthenticated endpoints except the health check

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
2. git add . && git commit -m "checkpoint: prompt-{N}"
3. git tag prompt-{N}
4. Verify the tag is clean: run `git show prompt-{N} --stat` and confirm the file list contains only files modified in this prompt. If any unexpected file appears — especially any file from a future prompt or test class that should not exist yet — stop, delete the tag with `git tag -d prompt-{N}`, clean the working tree, and re-tag before continuing.
5. Update c:\Jarvis\CHANGELOG.md — must include Implementation Notes documenting any problems hit mid-implementation and how they were resolved. A CHANGELOG entry with no implementation notes is only acceptable for trivial single-file changes.
6. Update SOVEREIGN_AI_HANDOFF.md directly with these changes:
   - Add completed prompt row to Completed Prompts table
   - Update Current State section: test baseline, checkpoint tag, warnings count
   - Update Remaining Implementation Plan: mark this prompt DONE, mark next prompt IN PROGRESS
   - Do NOT modify: Recurring Mistake Patterns, Architecture Rules, Project Vision, or prompt spec content
   - Do NOT reformat or restructure any section — append/update only
7. git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
8. git commit -m "docs: prompt-{N} changelog and handoff update"
9. git push origin master
10. git push origin prompt-{N}
11. Update Memory 1 in memory files with new checkpoint and test baseline
12. If any new problems were encountered and solved during this prompt, save solutions to memory files immediately — they should already be saved mid-prompt, but confirm here

### CHANGELOG Append Procedure (Mandatory — violations caused repeated prompt failures)

- Always use `[System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count` for line counts — never `Get-Content | Measure-Object` (truncates large files)
- Always use `Add-Content` to append — never paste into editor, never use insert operations
- Before appending: record current line count with `ReadAllLines().Count`
- After appending: verify new count exceeds previous count, verify last 5 lines with `Select-Object -Last 5`, verify boundary with `$lines[N-5..N-1]` where N is the old line count
- Close the file in the IDE before running `Add-Content` — a locked file causes IOException

The critical changes from the old steps:

Code is committed and tagged BEFORE docs are updated (old steps updated docs first, then committed everything together — this caused the tag to capture stale or next-prompt code)
Step 4 is a mandatory tag verification before any docs work begins
Docs are committed separately in steps 7–8 after the tag is already clean and pushed

---

## Current State

### Test Baseline
- **1065 passed, 23 skipped, 64 warnings** (as of Prompt 35.6b / checkpoint prompt-35.6b)
- Baseline is dynamic — every prompt must exceed the previous count
- Skipped: `tests/test_llama_cpp_adapter.py` (missing llama_cpp dependency)
- 64 warnings: FutureWarning from adapters/gemini.py — deferred to Phase 9, do not touch; PytestWarning for async decorator marks on sync methods (test_web_server.py) — harmless; DeprecationWarning from FastAPI Lifespan events — deferred to Phase 9, do not touch. Warning count increased from 56 to 64 in prompt-35.6b — all pre-existing warnings in test_web_server.py, none new.
- Run with: `python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py`

### Known Issues from Prompt 35.5.2
- None — prompt-35.6b landed cleanly

### Git / Backup
- Repo: `https://github.com/AngusKingC/sovereign-ai` (private)
- Latest checkpoint tag: `prompt-35.6b`
- Checkpoint script: `python scripts/checkpoint.py prompt-{N}` (unreliable — do manually)
- Restore script: `python scripts/restore.py`

### Core Layer
- `core/schemas.py` — all Pydantic models including TaskStatus.DENIED, EvaluatorScore, EvaluationRecord, OrchestratorMetrics
- `core/memory_router.py` — MemoryBackend ABC, MemoryRouter with tracing, scoped_write/read, get/set_global_context, compactor integration
- `core/worker_base.py` — LLMResponse, LLMAdapter Protocol, WorkerBase ABC (DI), fallback_chain parameter for adapter fallback chain
- `core/orchestrator.py` — routing with scoring algorithm, deregister_worker, mark_task_completed integration, DI complete (escalation engine integration disabled in Prompt 26 — debt), fallback_chain parameter and worker injection
- `core/handlers.py` — QueryHandler, DI complete
- `core/embedder.py` — OllamaEmbedder
- `core/escalation.py` — EscalationEngine with evaluate(), request_approval(), execute_escalation() (wiring to orchestrator disabled — debt)
- `core/observability.py` — TraceEmitter, MemoryTraceEmitter, ConsoleTraceEmitter, TraceComponent.ADAPTER_FALLBACK_CHAIN, TraceComponent.APPROVAL_TRUST, TraceComponent.VERBOSITY, TraceEventType.ADAPTER_FALLBACK, ADAPTER_UNAVAILABLE, CIRCUIT_BREAKER_OPEN, CIRCUIT_BREAKER_RESET, TRUST_GRANTED, TRUST_REVOKED, TRUST_BLOCKED, VERBOSITY_CHANGED, MODEL_THINKING_CAPTURED
- `core/verbosity.py` — VerbosityLevel enum (SILENT, NORMAL, VERBOSE, DEBUG), VerbosityManager with constructor-injected emitter, set_level() async method, should_emit() filtering, filter_events()
- `core/commands.py` — CommandRegistry, DI complete
- `core/exceptions.py` — InvalidStateTransitionError, WorkerNotFoundError, ApprovalDeniedError, CrossScopeAccessError
- `core/task_state_machine.py` — validated transitions, DENIED terminal state, full history tracking, checkpoint()/load_checkpoints() stubs
- `core/scratchpad.py` — ScratchpadManager, per-task ephemeral working memory
- `core/session.py` — SessionManager, Postgres persistence
- `core/skill_registry.py` — skill discovery, validation, query
- `core/approval_gate.py` — ApprovalGate, ApprovalRequest, ApprovalResponse, ApprovalScope, session-scoped pre-authorisation, write-through Postgres cache, trust_registry parameter for command trust levels
- `core/approval_trust.py` — ApprovalTrustRegistry with trust levels (ALWAYS_ASK, SESSION_TRUST, PERMANENT_TRUST, NEVER_ALLOW) and command trust persistence
- `core/worker_factory.py` — WorkerFactory, DynamicWorkerProfile, PlaceholderWorker, rule-based worker creation
- `core/rating_system.py` — RatingSystem, worker rating persistence, trend analysis
- `core/instruction_generator.py` — InstructionGenerator, LLM-based instruction file generation
- `core/instruction_versioning.py` — InstructionVersionManager, version control for instruction files
- `core/orchestrator_improvement.py` — OrchestratorImprovementLoop, orchestrator self-improvement
- `core/evaluator.py` — OutputEvaluator, LLM-as-Judge automated output evaluation
- `core/memory_compactor.py` — MemoryCompactor, MemoryTier enum, TieredMemoryEntry, background compaction
- `core/notification.py` — NotificationSystem, NotificationType enum, urgency-based routing
- `core/resource_budget.py` — ResourceBudget, BudgetCheckResult, async budget checks (token, worker, VRAM, all)
- `core/trace_optimiser.py` — TraceOptimiser, continuous trace-scoring as second trigger path for instruction updates, collision-prevention policy
- `core/adapter_fallback.py` — AdapterFallbackChain with circuit breaker pattern for graceful degradation

### Memory Layer
- `memory/obsidian.py` — Markdown vault storage
- `memory/postgres.py` — Async Postgres, connection pooling, JSONB
- `memory/qdrant.py` — Vector embeddings, semantic search

### Adapters (13 total, all async)
- Ollama, OpenAI, Anthropic, LM Studio, Gemini, Cohere, Groq, Mistral,
  DeepSeek, Together, HuggingFace, llama.cpp
- MCPAdapter — MCP (Model Context Protocol) client for calling external MCP tool servers
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
- `system/resource_manager.py` — ResourceManager, eviction priority queue, KV cache budget (kv_cache_budget_mb parameter, available_vram_mb() async method)
- `system/model_acquisition.py` — ModelAcquisition, HuggingFace integration
- `system/monitor_daemon.py` — MonitorDaemon, ScheduledTask, TaskScheduleType, persistent background scheduler

### Skills Layer
- `skills/SKILL_SPECIFICATION.md` — formal plugin specification
- `skills/mcp_server.py` — MCPServer, exposes SkillRegistry over MCP HTTP protocol (GET /mcp/tools, POST /mcp/call)
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
| 28 | Interrupt and Notification Layer | 599 |
| 28.5 | Telegram Gateway | 617 |
| 29 | ResourceManager KV Cache Fix and Resource Budget | 637 |
| 22.5 | MCP Adapter | 658 |
| 22.6 | Trace-Based Skill Optimiser | 676 |
| 22.7 | Escalation Engine Re-wiring | 676 (no-op - work already done) |
| 22.8 | Real Embeddings + Qdrant Vector Validation | 676 (partial no-op - embedding already done, only fixed hardcoded vector_size) |
| 29.5 | Developer Skills: Git, Docker, HTTP Client | 704 (+28 new tests) |
| 29.6 | Productivity Skills: PDF, Spreadsheet, Clipboard, Calculator | 734 (+30 new tests) |
| 29.7 | Adapter Fallback Chain | 750 (+16 new tests) |
| 29.8 | Approval Trust Levels | 767 (+17 new tests) |
| 30 | Multi-Worker Mode | 795 (+28 new tests) |
| 30.5 | Environment and Media Skills | 827 (+32 new tests) |
| 31 | Worker-to-Worker Communication | 847 (+20 new tests) |
| 31.5 | Data Retention and Memory Housekeeping | 867 (+20 new tests) |
| 31.6 | Data Retention Manager | 882 (+15 new tests) |
| 31.7 | Security Baseline | 907 (+25 new tests) |
| 32 | Web GUI + FastAPI Server | 922 (+15 new tests) |
| 33 | Voice Interface | 942 (+20 new tests) |
| 33.5 | Voice Interface Enhancements (Audio Capture and STT Wiring) | 957 (+15 new tests) |
| 34 | Fine-Tuning Data Export (TrajectoryExporter) | 970 (+13 new tests) |
| 35 | Personal Assistant Skills (Email, Calendar, Reminder, Notes) | 1026 (+56 new tests) |
| 35.5 | Verbosity Control + Model Thinking Capture + Async I/O Improvements | 1049 (+23 new tests) |
| 35.5.1 | Spec Deviation Correction | 1051 (+2 new tests) |
| 35.5.2 | Integrity Check and Final Tag Creation | 1051 (no new tests - checkpoint for user manual correction) |
| 35.6b | Runtime Bug Fixes + Minimum Cognition Wiring | 1065 (+14 new tests) |

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
**Status**: DONE

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
**Status**: DONE

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

**Auto-rating gap (background tasks):**
- Background task outputs (weather, AIS, email monitors) are never seen by the user
  at completion time and therefore never manually rated. The rating system has a
  blind spot for all open-loop work.
- OutputEvaluator (already built in Prompt 22) MUST be wired as the automatic rater
  for all background task completions. When a MonitorDaemon task completes without
  a user-facing session, OutputEvaluator scores it and records a rating via RatingSystem.
- This wiring must be implemented in Prompt 27 or a dedicated housekeeping prompt
  before Phase 8 — without it, background workers never improve.

Architecture:
- `core/trace_optimiser.py` imports only from `core/`
- Configurable: trace_threshold and min_traces (default 10) via constructor
- All trace calls wrapped in try-except

Tests: minimum 12. Target: exceed new 22.5 baseline.

---

#### Prompt 22.7 — Escalation Engine Re-wiring (Housekeeping)
**Status**: DONE

Re-wire the escalation engine that was disconnected from the orchestrator in the Prompt 26 regression fix. core/escalation.py is complete — the orchestrator simply stopped calling it. This prompt reconnects it and re-enables the skipped test file.

Files to modify:
- `core/orchestrator.py` — re-wire EscalationEngine calls at the correct points in the task execution flow
- `tests/test_escalation.py` — remove skip markers, fix any tests broken by the Prompt 26 removal

Architecture constraint: no changes to core/escalation.py — the implementation is correct. Only the wiring in orchestrator.py and the test file are in scope.

Tests: minimum 8 re-enabled or new tests in test_escalation.py. All previously skipped escalation tests must pass.

---

#### Prompt 22.8 — Real Embeddings + Qdrant Vector Validation (Housekeeping)
**Status**: DONE

MemoryRouter currently writes zero vectors to Qdrant — semantic search is non-functional. Wire OllamaEmbedder into the MemoryRouter.write() path and fix the hardcoded vector size bug in memory/qdrant.py.

Files to modify:
- `memory/qdrant.py` — fix hardcoded vector size 768; derive from embedder output at collection creation time
- `core/memory_router.py` — wire OllamaEmbedder into the write() path so vectors are real embeddings, not zeros

Architecture constraint: OllamaEmbedder already exists — do not rebuild it. Only the wiring and the Qdrant collection initialisation are in scope.

Tests: minimum 8. Cover: real embedding vector written on memory_router.write(), Qdrant collection created with correct vector size from embedder, zero-vector write path removed, semantic search returns results when embeddings match.

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

**⚠ Critical debt:** _restore_queue() and load_checkpoints() stubs mean the daemon
cannot survive a process restart. The "monitors open-loop background tasks" promise
is not fulfilled until these stubs are resolved. MemoryRouter key-pattern query
(also a stub dependency) must land before or alongside the stub resolution.
This must be scheduled before Phase 9 — the Web GUI has no value if the daemon
it surfaces cannot recover from a restart.

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
**Status**: DONE

`core/notification.py`.
Types: info, warning, urgent, requires-action.
Urgent interrupts current interaction.
Requires-action integrates with approval gate.
Non-urgent queues and surfaces at natural break points.

---

#### Prompt 28.5 — Telegram Gateway
**Status**: DONE

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
**Status**: DONE

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
**Status**: DONE

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
**Status**: DONE

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
**Status**: DONE

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
**Status**: DONE

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

#### Prompt 31.5 — Data Retention and Memory Housekeeping
**Status**: DONE

The memory layer accumulates data indefinitely — Postgres rows, Qdrant vectors, Obsidian notes, scratchpad entries. This prompt adds a RetentionPolicy engine that enforces configurable TTLs, archives expired data, and runs as a background daemon.

Files:
- `core/retention.py` — RetentionRule, RetentionReport Pydantic models and RetentionEngine class
- `system/retention_daemon.py` — RetentionDaemon class for scheduled retention runs
- `tests/test_retention.py` — 20 tests covering all retention functionality

Features:
- RetentionEngine enforces configurable TTLs on memory data with scope and data_type filtering
- RetentionEngine.run() applies all rules, scans for expired records, archives (if archive=True), deletes, and accumulates counts
- RetentionEngine.run() catches per-record errors and appends to report.errors without aborting the entire run
- RetentionEngine._scan() is a stub for Phase 10 — calls memory_router.fetch() and filters in Python based on TTL
- RetentionEngine._archive() writes to "archive:{scope}:{data_type}:{id}" key via memory router
- RetentionEngine._delete() writes deletion marker (stub for Phase 10)
- RetentionDaemon runs RetentionEngine on configurable schedule (default: hourly)
- RetentionDaemon.start() launches background loop task and emits COMPONENT_START event
- RetentionDaemon.stop() cancels task and emits COMPONENT_STOP event
- RetentionDaemon.run_once() runs engine.run() once without starting daemon

Architecture:
- All classes use constructor-injected emitters (no global emit_trace())
- All trace events use correct fields from core/observability.py (event_type, component, level, message, data, duration_ms)
- All imports only from core/ (Clean Architecture compliance)
- All tests use class-level pytestmark = pytest.mark.asyncio
- All tests mock MemoryRouter (never use real router instance)
- All tests check trace events via emitter.get_events()

Tests: 20 implemented.

---

#### Prompt 31.6 — Data Retention Manager
**Status**: DONE

Concrete retention layer targeting Postgres trace events, task history, Qdrant vectors, and Obsidian mirror files. Distinct from the generic rule engine stub in core/retention.py — this file contains actual storage-specific pruning logic with dry-run mode and MonitorDaemon integration hook.

Files:
- `system/retention_manager.py` — RetentionConfig Pydantic model and RetentionManager class
- `tests/test_retention_manager.py` — 15 tests covering RetentionConfig and RetentionManager

Features:
- RetentionConfig defines TTLs for different data types (trace_events_ttl_days=90, task_history_ttl_days=365, qdrant_ttl_days=90, obsidian_archive_ttl_days=90) with dry_run mode
- RetentionManager provides storage-specific pruning logic distinct from the generic RetentionEngine in core/retention.py
- prune_trace_events() deletes trace event records older than config.trace_events_ttl_days via memory router
- prune_task_history() deletes task history records older than config.task_history_ttl_days, skipping tasks in AWAITING_APPROVAL or IN_PROGRESS state
- prune_qdrant_vectors() deletes Qdrant vector entries older than config.qdrant_ttl_days via memory router
- archive_obsidian_notes() moves Obsidian daily note files older than config.obsidian_archive_ttl_days to /archive/ subfolder (never delete)
- All four prune methods support dry_run parameter — when True, count records but do not delete or archive
- run_all() calls all four prune methods in order, accumulates counts into RetentionReport, and catches per-method errors without aborting the entire run
- run_all() emits RETENTION_RUN_STARTED and RETENTION_RUN_COMPLETED trace events
- schedule_hook() provides MonitorDaemon integration entry point that calls run_all()

Architecture:
- All classes use constructor-injected emitters (no global emit_trace())
- All trace events use correct fields from core/observability.py (event_type, component, level, message, data, duration_ms)
- All imports only from core/ and memory/ (Clean Architecture compliance)
- All tests use class-level pytestmark = pytest.mark.asyncio
- All tests mock MemoryRouter (never use real router instance)
- All tests check trace events via emitter.get_events()

Tests: 15 implemented.

---

#### Prompt 29.7 — Adapter Fallback Chain
**Status**: DONE

Every TerminalSkill and CodeExecutionSkill call currently requires explicit approval,
including commands the user has approved dozens of times. This creates approval
fatigue that defeats the purpose of an autonomous assistant.

Files:
- `core/approval_trust.py` — ApprovalTrustRegistry class

Features:
- Trust levels: ALWAYS_ASK, SESSION_TRUST, PERMANENT_TRUST, NEVER_ALLOW
- Per-command trust memory: user approves `git status` once → remembered
- Session-scoped blanket approval: "approve all read-only terminal commands this session"
- Trust entries persisted in Postgres (PERMANENT) or in-memory (SESSION)
- ApprovalGate consults TrustRegistry before raising approval request — skips gate if trusted
- Trust can be revoked: `jarvis trust revoke <command>`
- NEVER_ALLOW list: hardcoded dangerous patterns (rm -rf /, format, etc.) that cannot be trusted
- All trust decisions emitted as trace events for audit

Architecture:
- `core/approval_trust.py` imports only from `core/`
- Emitter and MemoryRouter injected via constructor
- ApprovalGate updated to consult TrustRegistry (one additional constructor param)

Tests: minimum 12 (17 implemented).

---

#### Prompt 30 — Multi-Worker Mode
**Status**: DONE

Route same task to top N workers concurrently.
Resource budget enforced — only dispatch if budget allows.
ResourceManager consulted for live memory state.
Responses surfaced side by side. User selection feeds rating system.

Files:
- `core/multi_worker.py` — MultiWorkerDispatcher class
- `core/observability.py` — Added MULTI_WORKER trace events
- `core/orchestrator.py` — Added get_top_candidates() method
- `system/resource_manager.py` — Added release_model() and ensure_model() methods

Features:
- MultiWorkerDispatcher supports parallel (concurrent) and sequential (one-at-a-time) dispatch modes
- Parallel mode: dispatches all workers concurrently, records failures without aborting
- Sequential mode: dispatches workers one at a time, ensures/releases model VRAM around each worker
- Resource budget checks filter eligible workers before dispatch
- Orchestrator model VRAM released before dispatch (best-effort)
- Worker model VRAM ensured/released in sequential mode (best-effort)
- Results stored in-memory keyed by UUID
- Rating system records winner (1.0) and non-winner (0.9) ratings
- get_top_candidates() returns top n workers ordered by routing score
- release_model() marks adapter's model as lowest eviction priority
- ensure_model() restores adapter's model to normal priority, attempts reload if evicted

Architecture:
- MultiWorkerDispatcher uses constructor-injected emitter
- MultiWorkerDispatcher imports only from `core/`
- All trace events use correct fields: event_type, component, level, message, data, duration_ms
- No global emit_trace() usage

Tests: 25 new tests (20 for multi_worker, 2 for orchestrator, 3 for resource_manager).

---

#### Prompt 30.5 — Environment and Media Skills: Home Assistant, Screenshot, TTS, Transcription (New — added 2026-06-11)
**Status**: DONE

Files:
- `skills/home_assistant/` — HomeAssistantSkill
- `skills/screenshot/` — ScreenshotSkill
- `skills/tts/` — TTSSkill
- `skills/transcription/` — TranscriptionSkill

Features:
- Home Assistant: list entities, call services (lights, switches, climate, sensors)
- Screenshot: screen capture, pass to vision model
- TTS: local Piper TTS (no API key, CPU) or ElevenLabs
- Transcription: local Whisper (no API key, CPU), transcribe voice/audio

Architecture:
- All skills import from `core/` and `skills/base.py` only
- Emitter injected via constructor
- All I/O async, all public methods typed

Tests: minimum 8 (2 per skill).

---

#### Prompt 31.6 — Data Retention and Memory Housekeeping
**Status**: IN PROGRESS

Without a retention policy the Postgres trace table and Qdrant collections grow
indefinitely. After months of use this becomes a performance and disk space problem.

Files:
- `system/retention_manager.py` — RetentionManager class

Features:
- Configurable retention windows per table: trace_events (default 90 days), task_history (default 365 days), worker_ratings (keep all — small)
- Qdrant vector pruning: delete entries older than retention window, or entries whose source document has been deleted
- Obsidian mirror compaction: archive daily note files older than retention window to a `/archive/` subfolder — never delete
- Dry-run mode: report what would be pruned without deleting
- Scheduled via MonitorDaemon (weekly by default)
- All deletions emitted as trace events

Architecture:
- `system/retention_manager.py` imports from `core/` and `memory/` only
- Emitter and MemoryRouter injected via constructor
- Copy `system/NEWFILE_TEMPLATE.py` as starting point

Tests: minimum 10.

---

#### Prompt 31.7 — Security Baseline
**Status**: DONE

The FastAPI server (Prompt 32) will be network-accessible. Without a security
baseline it is open to anyone who can reach the port. This prompt establishes
the minimum viable security layer before any network surface is exposed.

Files:
- `core/auth.py` — AuthManager class
- `web/middleware/auth_middleware.py` — FastAPI auth middleware (created in this prompt, used in Prompt 32)

Features:

**Token-based auth:**
- Single bearer token generated at first run, stored in .env (never in config YAML)
- All FastAPI routes require `Authorization: Bearer <token>` header
- WebSocket connections require token as query param on handshake
- Token rotation: `jarvis auth rotate` regenerates token, old token immediately invalid
- 401 response on invalid/missing token, no information leakage

**Prompt injection hardening:**
- `core/input_sanitiser.py` — strip/escape known injection patterns before LLM context insertion
- Applied to: WebScraper output, user task input, Telegram inbound messages
- Patterns blocked: `<|system|>`, `IGNORE PREVIOUS INSTRUCTIONS`, `</s>`, role-switching patterns
- Logs every sanitisation as a WARNING trace event

**Secrets audit:**
- At startup, verify no API keys or tokens are present in `jarvis.config.yaml` (they belong in `.env` only)
- Warn loudly (console + trace event) if secrets found in config file

Architecture:
- `core/auth.py` and `core/input_sanitiser.py` import only from `core/`
- `web/middleware/` imports from `core/` only
- No changes to existing core/ files except adding sanitiser call in WebScraper

Tests: minimum 12.

---

#### Prompt 32 — Web GUI + FastAPI Server
**Status**: DONE

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
**Status**: DONE

Wake word detection, Whisper STT, TTS.
Voice notifications for open loop events.
Same approval gates and observability as text interface.

---

#### Prompt 33.5 — Voice Audio Capture and Whisper STT
**Status**: DONE

Real audio capture via PyAudio, Whisper STT wiring, TTS notification.
AudioCapture class isolates PyAudio interactions.
VoiceInterface and VoiceDaemon updated with skill injection.

---

### PHASE 10 — Model Evolution (New — added 2026-06-10)

---

#### Prompt 34 — Trajectory Export / Fine-tuning Pipeline
**Status**: DONE

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

#### Prompt 35 — Personal Assistant Skills: Email, Calendar, Reminder, Notes
**Status**: DONE

Files:
- `skills/email/` — IMAP read + SMTP send
- `skills/calendar/` — local ICS file first, extensible to Google Calendar
- `skills/reminder/` — persistent reminders in Postgres, delivered via Telegram
- `skills/notes/` — Obsidian vault integration surfaced as skill

Features:
- EmailSkill uses asyncio executors for blocking imaplib and smtplib calls
- CalendarSkill uses asyncio executors for blocking file I/O and icalendar parsing
- ReminderSkill and NotesSkill use MemoryRouter for persistence (async by design)
- Approval gates are optional for low-risk operations but required for destructive operations
- Environment variable fallback for credentials

Tests: 56 new tests.

---

#### Prompt 35.5 — Verbosity Control + Model Thinking Capture + Async I/O Improvements (Housekeeping)
**Status**: DONE

Files:
- `core/verbosity.py` — VerbosityLevel enum, VerbosityManager class
- `tests/test_verbosity.py` — 9 tests for verbosity manager
- `adapters/ollama.py` — <thinking> tag extraction from LLM responses
- `tests/test_ollama_adapter.py` — 4 tests for thinking extraction
- `core/skill_registry.py` — async file I/O wrapping
- `system/profiler.py` — async psutil call wrapping
- `tests/test_profiler.py` — 10 tests for profiler

Features:
- VerbosityManager filters trace events by level (SILENT, NORMAL, VERBOSE, DEBUG)
- Ollama adapter extracts <thinking> content and emits as separate trace event
- Skill registry file I/O wrapped in loop.run_in_executor()
- Profiler psutil calls wrapped in loop.run_in_executor()

Tests: 23 new tests.

---

#### Prompt 35.5.1 — Spec Deviation Correction (Housekeeping)
**Status**: DONE

Files:
- adapters/ollama.py — <thinking> tag format corrected to <thought>
- tests/test_ollama_adapter.py — test mock content updated to <thought>
- core/verbosity.py — set_level() async deviation documented
- core/skill_registry.py — run_in_executor vs aiofiles choice documented
- system/profiler.py — _detect_gpu and _detect_os async wrapping added
- tests/test_profiler.py — 2 new tests for _detect_gpu and _detect_os

Features:
- Corrected tag format from <thinking> to <thought> (Qwen and DeepSeek-R1 use <thought>)
- Documented why set_level() is async (must await emitter.emit())
- Documented why run_in_executor is used instead of aiofiles (avoid new dependency)
- Wrapped blocking pynvml calls in _detect_gpu with async executor
- Wrapped blocking platform/shutil calls in _detect_os with async executor

Tests: 2 new tests.

---

## Technical Debt

| Item | Location | Notes |
|------|----------|-------|
| google.generativeai FutureWarning | adapters/gemini.py | Do not touch until Phase 9 |
| RuntimeWarning coroutine never awaited | skills/web_scraper tests | Do not touch |
| llama.cpp tests skipped | tests/test_llama_cpp_adapter.py | Missing dependency |
| Escalation logic removed from orchestrator | core/orchestrator.py | Removed in Prompt 26 regression fix — scheduled for re-wiring in Prompt 22.7 |
| test_escalation.py skipped | tests/test_escalation.py | Skipped in Prompt 26 — re-enable in Prompt 22.7 |
| MemoryRouter writes zero vectors | core/memory_router.py | OllamaEmbedder not wired into write() path — semantic search non-functional. Fix in Prompt 22.8 |
| _restore_queue() stub | system/monitor_daemon.py | Requires key-pattern querying in MemoryRouter |
| load_checkpoints() stub | core/task_state_machine.py | Same dependency as above |
| MemoryRouter key-pattern query | core/memory_router.py | Needed for stubs above — add in Prompt 27 or dedicated housekeeping |
| Model selection modal incomplete | cli/tui.py | Phase 9 (Setup Wizard Prompt 26.5 addresses partially) |
| No tests for session postgres | core/session.py | Prompt 11 debt |
| No tests for command_history | cli/command_history.py | Prompt 12 debt |
| Qdrant hardcoded vector size 768 | memory/qdrant.py | Latent bug — fix before Phase 6 |
| Model registry may seed oversized models | system/model_registry.py | Standardise on Qwen 2.5 7B Q4_K_M — fix in Prompt 16.5 |
| WorkerPersistence not passed to WorkerFactory in CLI | cli/tui.py, cli/rich_cli.py | Intentional deferral — requires CLI refactor |
| WorkerPersistence in TYPE_CHECKING block | core/worker_factory.py | Verify no runtime issues in future prompt |
| No auth on FastAPI server | web/ (Prompt 32) | Prompt 32 must include token-based auth before any network exposure — see Security Baseline section |
| TerminalSkill/CodeExecutionSkill approval is UX not security | skills/terminal/, skills/code_execution/ | Approval gate stops accidental misuse, not a compromised model. Sandboxing (Prompt 29.5) must add OS-level restriction |
| WebScraper passes raw HTML to LLM context | skills/web_scraper/ | No prompt injection sanitisation — add in Prompt 29.5 or dedicated housekeeping |
| No adapter fallback chain | core/orchestrator.py | If primary model/adapter is unavailable, task fails hard. Fallback chain needed before Phase 8 multi-worker mode |
| Trace event table unbounded | memory/postgres.py | No retention or pruning policy. Will grow indefinitely. Add retention policy in Prompt 32 housekeeping |
| Qdrant collections unbounded | memory/qdrant.py | No compaction or staleness eviction for vector entries beyond scratchpad compaction |
| Monitor daemon restart loses queue | system/monitor_daemon.py | _restore_queue() stub — daemon cannot survive restart. Blocks autonomous operation promise |
| Auto-rating path missing for background tasks | core/rating_system.py | Background task outputs (weather/AIS/email) are never seen by user so never manually rated. OutputEvaluator must be wired as automatic rater for MonitorDaemon completions before Phase 8. Logged in Prompt 22.6. |
| Fine-tuned model re-ingestion not planned | system/ | Prompt 34 exports ShareGPT but no prompt re-ingests fine-tuned model into Ollama and re-routes workers to it |
| Approval gate has no trust levels or memory | core/approval_gate.py | Every TerminalSkill/CodeExecutionSkill call requires approval. No session blanket approval, no per-command trust memory. Will cause approval fatigue |

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
19. Case-sensitive string comparison on enum-like fields in tests — TraceEvent.level is stored lowercase ("warning") but tests asserting `e.level == "WARNING"` fail silently (0 matches, no error). Always use `e.level.upper() == "WARNING"` or normalise at the emitter. When a test asserts on a string field, verify the actual stored value before writing the assertion.
20. Budget/quota checks that test the request alone instead of accumulated + request — check_token_budget approved a request because it only compared requested_tokens > limit, ignoring session_used. Any method that enforces a cumulative limit MUST fetch the running total first and test (total + requested) > limit, not requested > limit alone.
21. Asserting file content as fact without verification — When reporting on file content (e.g., regex patterns, tag formats, method signatures), never assert specific values from memory or estimation. Always derive the expected value by reading the actual file content first: use open(..., 'rb').read() for byte-level verification, or read the file directly and paste the relevant lines. This pattern caused two failures in Prompt 35.5.2: a Step 6 report claiming the regex was r'<thinking>(.*?)</thinking>' when it was actually r'(.*?)', and a CHANGELOG entry repeating the same error. Both were fluent, specific, and completely wrong.
22. TraceEventType enums vs raw strings — Prompt 22.5 used TraceEventType.OPERATION_COMPLETE and TraceComponent.ADAPTER enum values rather than raw strings (e.g. "mcp_discover"). Both work if the enum is defined in core/observability.py, but raw strings are the pattern used across all other components. Before writing any new trace emission, verify whether the codebase uses enum or string literals for event_type and component — do not mix them within a prompt. If enums are used, import TraceEventType and TraceComponent from core/observability.py, never define them locally.
23. Spec deviation without documentation — When a spec specifies an exact value, format, method name, or scope (e.g., a tag string, a function call signature, a list of files), implement exactly that. If a different approach seems better, STOP and flag it in Implementation Notes as an explicit deviation with rationale before writing the code. Do not silently substitute. A test suite that passes 100% green proves nothing if the tests were written to match the deviation rather than the spec.

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
