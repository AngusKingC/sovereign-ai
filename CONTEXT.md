# CONTEXT.md — Sovereign AI Shared Vocabulary

This file defines the domain terms, conventions, and shared vocabulary used across all agents and skills in the Sovereign AI framework. Every agent and skill SHOULD reference this file for consistent terminology.

## Core Concepts

| Term | Definition |
|---|---|
| **Task** | A unit of work submitted to the orchestrator. Has a UUID, intent, priority, and state machine lifecycle. |
| **Worker** | An entity that processes tasks. Registered with the orchestrator. Has a profile (worker_id, model, capabilities). |
| **Skill** | A modular capability that can be dynamically discovered and loaded. Classified by invocation tier (see Skill Taxonomy). |
| **Adapter** | An LLM provider integration (OpenAI, Anthropic, Ollama, etc.). Translates worker requests into provider-specific API calls. |
| **Orchestrator** | The central coordinator. Routes tasks to workers, manages the task lifecycle, and emits trace events. |
| **Memory Router** | The single entry point for all memory operations. Routes read/write to appropriate backends (SQLite, Qdrant, Obsidian). |
| **Trace Emitter** | Structured observability event emitter. Injected via constructor. Fire-and-forget persistence to trace store. |
| **Eval Harness** | Metrics engine (exact_match, token_f1, bleu, cosine_similarity) for evaluating worker outputs. |
| **Improvement Loop** | Closed loop: execute → evaluate → store → improve. Currently wired but not reachable from CLI. |

## Skill Tiers

| Tier | Meaning | Example |
|---|---|---|
| **USER_INVOKED** (user_invoked) | Only activated by explicit user request | calculator, terminal, docker |
| **AGENT_INVOKED** (agent_invoked) | Orchestrator decides to use based on task analysis | calendar, notes, reminder |
| **HYBRID** (hybrid) | Both user and agent can invoke | email |

> Examples reflect current classifications as of Plan 68. See `skills/classifications.py` for the authoritative list.

## Domain Context

### User Profile
- **Primary domains**: Media production, sailing, 3D printing, CNC machining
- **Environment**: Single-user, local-first, Windows workstation
- **Cloud escalation**: Only when local resources are insufficient

> **Note**: This section is deployment-specific. If forking Sovereign AI for a different context, replace these entries with your own domain profile.

### Decision Framework
- **Local first**: Run on local hardware by default
- **Escalate when needed**: Use cloud APIs (OpenAI, Anthropic) when local models can't handle the task
- **Interrupt only when necessary**: Background monitors (weather, AIS, email) should not interrupt unless action is required
- **Approval gates**: Destructive or expensive operations require explicit user approval

### Conventions
- All datetimes are timezone-aware UTC: `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- All public functions have return type annotations (AR14)
- No raw LLM calls outside adapters/ (AR9)
- No memory access outside MemoryRouter (AR10)
- TraceEmitter via constructor injection only (AR11)

## Sandbox Vocabulary (NEW — Plan 73)

| Term | Definition |
|---|---|
| **SandboxExecutor** | The single entry point for all code and command execution. Runs code in a Docker container with resource limits (memory, CPU, network, timeout). Falls back to subprocess if Docker unavailable AND approval gate explicitly allows it. |
| **Sandbox Image** | The Docker image used for execution. Default: `python:3.12-slim`. Configurable per-task via `image` parameter. |
| **Sandbox Policy** | Configuration determining whether Docker is required (strict) or optional (fallback to subprocess with approval). Default: strict. |
| **Sandbox Result** | Result dict from SandboxExecutor: `{success, stdout, stderr, return_code, error, sandboxed, container_id}`. `sandboxed: True` if Docker was used, `False` if subprocess fallback. |

## Cost Tracking Vocabulary (NEW — Plan 74)

| Term | Definition |
|---|---|
| **CostTracker** | The central module that aggregates token usage × cost_per_token per model, enforces daily/monthly $ caps, and emits cost traces. Single source of truth for spend. |
| **Spend Cap** | Configurable $ limit (daily or monthly). When hit, CostTracker blocks further execution and triggers fallback to cheaper model (if configured) or hard-fail. |
| **Cost Trace** | Trace event emitted by CostTracker with `model`, `tokens_in`, `tokens_out`, `cost_usd`, `cumulative_daily`, `cumulative_monthly` fields. |
| **Cost Policy** | Configuration determining cap amounts, fallback behavior, and alert thresholds. Default: $10/day, $100/month, alert at 80%, fallback to cheapest model at 90%. |

## Modified llama.cpp Vocabulary (NEW — Plan 74.5)

| Term | Definition |
|---|---|
| **Modified llama.cpp** | A fork of `llama.cpp` that adds quantization formats not in the upstream release (e.g., PrismML's Q1_0 ternary weight support). The user installs the binary externally; Sovereign AI does not download it. |
| **Q1_0 Quantization** | The 1-bit/ternary quantization format added by PrismML's `llama.cpp` fork. Required to load models with ternary weights (e.g., Ternary Bonsai). NOT supported by stock `llama-cpp-python` from PyPI. |
| **PrismLlamaAdapter** | The Sovereign AI adapter (`adapters/prism_llama.py`) that manages a modified `llama-server` subprocess and exposes it as an `LLMAdapter`. Single responsibility: binary lifecycle + HTTP translation. Does NOT download binaries or models. |
| **Adapter-Managed Subprocess** | Pattern (AR20): adapter launches an external binary as a subprocess, health-checks it, and calls its API. Used when a custom C++ build is needed but a Python binding would be fragile. |

## PEMADS Phase 1 Vocabulary (NEW — Plan 76)

| Term | Definition |
|---|---|
| **PEMADS** | Pruned Expert Multi-Agent Debate System. Feature arc (Plans 76, 81-84) that creates specialized pruned-expert models, orchestrates turn-based debates between diverse architectures, and gates implementation on a quality threshold. |
| **DebatePool** | Persistent filesystem storage (`memory/debate_pool.py`) for debate history across rounds — task, solutions, critiques, scores, feedback. No LLM calls; pure data structure. |
| **TaskClassifier** | Module (`core/task_classifier.py`) that classifies coding tasks into types (game, ai_agent, data_pipeline, api_backend, script) via keyword heuristics. No LLM calls. |
| **TestingBattery** | Skill (`skills/testing_battery/`) that orchestrates mypy, vulture, pytest, bandit, hypothesis runs against a solution in SandboxExecutor. Returns `TestBatteryResult` with per-tool scores. No LLM calls. |
| **TaskType** | Classification of a coding task — determines quality threshold and scoring weights. Values: game (85% threshold), ai_agent (90%), data_pipeline (80%), api_backend (88%), script (75%). |
| **TestBatteryResult** | Aggregated result of testing battery runs — per-tool `ToolResult` objects, weighted quality %, total duration. |
| **Quality %** | Weighted score (0-100) from testing battery, calculated per task type weights. Must exceed task-specific threshold for implementation to proceed. |
| **Phase 1** | PEMADS infrastructure — debate pool, task classifier, testing battery framework. No LLM calls, no debates, no safety risks. (Plan 76) |
| **Phase 2** | PEMADS expert panel manager + VRAM hot-swap. Live debates. Requires Plan 77-79 prerequisites. (Plan 81) |
| **Phase 3** | PEMADS judge + implementation gate + full testing battery. Autonomous decisions. Requires Plan 82 multi-channel approvals. (Plan 83) |

## Self-Healing Vocabulary (NEW — Plan 77)

| Term | Definition |
|---|---|
| **AutoCorrector** | Module (`core/auto_corrector.py`) that classifies `VersionUpdateProposal`s as safe or unsafe based on `proposal_type`, auto-applies safe proposals via `InstructionVersionManager.approve_update()`, and escalates unsafe proposals to `ApprovalGate`. Closes the "self-improving AI" promise — instruction tweaks no longer need manual approval. |
| **ProposalClassification** | Enum returned by `AutoCorrector.classify()`. Values: `SAFE` (auto-apply), `UNSAFE` (escalate). Unknown proposal types default to `UNSAFE` (defense in depth). |
| **ApplyStatus** | Enum returned by `AutoCorrector.apply_proposal()`. Values: `APPLIED` (safe proposal applied), `ESCALATED` (unsafe proposal sent to ApprovalGate), `ERROR` (application or escalation failed — see message). Caller (`InstructionVersionManager`) MUST clear `_pending_proposals` on ERROR to prevent worker freeze. |
| **ApplyResult** | Pydantic model returned by `AutoCorrector.apply_proposal()`. Fields: `proposal_id`, `status`, `classification`, `message`, `applied_at`. |
| **proposal_type** | Field on `VersionUpdateProposal` (added Plan 77). Determines AutoCorrector classification. Values: `instruction_tweak` (safe, default), `routing_weight` (safe), `code_change` (unsafe), `model_download` (unsafe). Defaults to `instruction_tweak` for backward compatibility (OR27). |
| **Safe proposal** | A proposal whose `proposal_type` is in `{instruction_tweak, routing_weight}`. Auto-applied without human approval. Reversible via `InstructionVersionManager.rollback()`. |
| **Unsafe proposal** | A proposal whose `proposal_type` is in `{code_change, model_download}` or is unknown. Escalated to `ApprovalGate` for human-in-the-loop review. |

## Model Routing Vocabulary (NEW — Plan 79)

| Term | Definition |
|---|---|
| **ModelTierRouter** | Module (`core/model_tier_router.py`) that classifies tasks by complexity (SIMPLE/MEDIUM/COMPLEX) via keyword heuristics and routes to the cheapest capable model. No LLM calls for classification. Integrates with CostTracker for budget-aware tier downgrade. |
| **TaskComplexity** | Enum returned by `ModelTierRouter.classify()`. Values: SIMPLE (arithmetic, lookups), MEDIUM (summarization, single-file edits), COMPLEX (debates, multi-file refactors, analysis). Default: MEDIUM (safer for unknown tasks). |
| **ModelChoice** | Dataclass returned by `ModelTierRouter.route()`. Fields: model_name, complexity, reason, downgraded. `downgraded=True` when CostTracker fallback forced a lower tier. |
| **Tier Downgrade** | When CostTracker indicates spend cap approaching, router downgrades: COMPLEX → MEDIUM → SIMPLE. SIMPLE cannot be downgraded further — CostTracker's hard fail takes over. |

## UI Architecture Vocabulary (NEW — Web GUI Rebuild, 2026-06-27)

| Term | Definition |
|---|---|
| **Vanilla JS UI** | The current web frontend in `web/static/` — plain HTML + CSS + JavaScript (ES modules), no build step, no React, no TypeScript. Served via FastAPI `StaticFiles` mount at `/`. Replaced the abandoned Next.js/React stack (see L23, Decision 11). |
| **Panel Module** | A single `.js` file in `web/static/` exposing one object (e.g., `Workers`, `Approvals`, `Costs`) with `init()` and `update()` methods. Mirrors the role of a React component but with no lifecycle methods, no hooks, no virtual DOM. |
| **API Wrapper** | The `API` object in `web/static/api.js`. All `fetch()` calls go through this wrapper, which attaches `Authorization: Bearer <token>` from `localStorage.sovereign_token` and clears the token on 401 (triggering the token-entry modal). |
| **Token-Entry Modal** | First-load UX in `index.html`. If `localStorage.sovereign_token` is missing or rejected (401), a modal prompts the user to paste the auth token printed by the server at startup. Token is stored in `localStorage` and attached to all subsequent requests. |
| **Same-Origin Mount** | FastAPI serves both the static frontend (`/`) and the API (`/api/*`) on the same port (`:8000`). Eliminates CORS configuration that plagued the Next.js dev server (`:3000`) → FastAPI (`:8000`) split. |
| **Exempt Prefixes** | List of `/api/*` path prefixes in `web/middleware/auth_middleware.py` that bypass auth: `/api/status`, `/api/workers`, `/api/costs`, `/api/approvals`, `/api/memory`, `/api/logs` (GET only), `/health`, `/api/errors/log` (POST only). All other `/api/*` paths require bearer token. WebSocket `/ws/pty` accepts `?token=` query param (browsers cannot set headers on WS handshake). |
| **CDN-loaded xterm.js** | The terminal emulator library is loaded via `<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.min.js">` in `index.html`. No npm install, no bundler. Trade-off: requires internet on first load (cached thereafter). |
| **AR21b** | Governance rule in `AGENTS.md` for the vanilla JS frontend. Supersedes AR21 (which governed the deleted TypeScript/React `src/` directory). |
