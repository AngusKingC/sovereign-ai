# PLANS.md — Sovereign AI Project State

**Last updated**: Post-Plan 69 (2026-06-24)

This document tracks the dynamic state of the Sovereign AI project: baselines, completed prompts, and the next-5-prompt queue. It is the canonical source for test counts, static analysis baselines, and which prompt is currently active.

---

## Test Baseline

**Current baseline**: **1253 passed, 67 skipped**
**Verified**: Plan 69, Step S7 (full test suite)
**Tolerance**: ±5 tests (variance acceptable due to parameterized fixtures and environment variation)
**Delta tracking**: If S1 test count differs from baseline, update this entry + note in CHANGELOG.

---

## Static Analysis Baseline

**Captured**: Plan 60 (5-plan milestone full scan — 2026-06-23), verified Plan 69 (no changes)

| Tool | Baseline | Source | Notes |
|---|---|---|---|
| **Ruff** | 0 errors | Plan 60 S2 | No errors. Plan 59 cleanup fully held. |
| **Mypy (core/system)** | 0 errors | Plan 66 S3 | Delta: -294 from Plan 60 baseline (294 → 0). Core and system directories fully clean. |
| **Mypy (full-repo)** | 0 errors | Plan 67 S6 | Delta: -294 from Plan 60 baseline (294 → 0). Full remediation of adapters, CLI, memory, workers, skills, tests, scripts (181 source files). |
| **Bandit** | 3,179 low, 0 medium, 0 high | Plan 60 S4 | Plan 59 suppressed all B108 findings. Zero medium, zero high. |
| **pip-audit** | 19 CVEs across 4 packages | Plan 60 S5 | Stable across Plans 56-60. No actionable fixes (upstream only). |
| **Vulture** | 23 high-confidence findings | Plan 60 S6 | Delta: +3 from Plan 55 baseline (20 → 23). Within tolerance. Dead code analysis only. |

**Per-plan verification cadence**:
- **Every plan**: Ruff (file-scoped) + Mypy (file-scoped) + Pytest
- **Every 5th plan** (55, 60, 65...): Full scan (all 6 tools + pytest)
- **Security-sensitive plans**: Add bandit
- **Dependency-touching plans**: Add pip-audit
- **Docs-only plans**: Skip ruff, mypy (no code); test count + tag + push verification only

---

## Completed Prompts

| # | Plan Name | Test Count | Notes |
|---|---|---|---|
| 55 | 5-plan checkpoint (ruff 0, mypy baseline) | 1166 | Full 5-plan scan. Established ruff baseline (0 errors). Mypy baseline: 283 errors. |
| 56 | Observability core + trace emitter | 1166 | TraceEmitter injection, structured logging, trace context propagation. |
| 57 | Core serialization audit + JSON safety | 1166 | Jsonify strict mode, serializer audit, circular ref detection. |
| 58 | Datetime UTC consolidation (core + system) | 1166 | 58 datetime.utcnow() calls replaced with datetime.now(timezone.utc). Eliminated naive/aware mixing. |
| 59 | Ruff cleanup (110→0) + B108 suppression | 1166 | 104 ruff fixes (F541=14, F401=2, F811=3, F841=41, E402=21, F821=21, E731=1, E741=1). All 22 B108 scoped. |
| 60 | 5-plan checkpoint (mypy 294, bandit clean, pip-audit 19) | 1167 | Full 5-plan scan. Mypy: 283→294 (+11, OUTSIDE tolerance — escalated). Bandit: 3179 low/0 medium/0 high. pip-audit: 19 CVEs (stable). Vulture: 23 findings. |
| 61 | Trace Store Implementation (Postgres Backend) | 1170 | Postgres trace store backend with asyncpg. BackendRouter trace_store registration. TraceEmitter fire-and-forget persistence. 15 new tests (11 skip, 4 pass). |
| 62 | Eval Harness Implementation | 1194 | Eval harness with metrics (exact_match, token_f1, bleu, cosine_similarity). Trace emitter integration. 24 new tests. |
| 62.5 | Eval Harness Validation | 1213 | Validation suite with 15 static tasks across 5 categories. Metric refinements: space collapsing (exact_match), punctuation stripping (token_f1). 19 new validation tests. |
| 63a | Improvement Loop Wire | 1225 | Wire module connecting eval harness, trace store, and improvement loop. IMPROVE command with DI support. Orchestrator fire-and-forget integration. 12 new tests. |
| 63b | Improvement Loop Validate + Restore Integration Tests | 1232 | Restored TestOrchestratorIntegration class with 2 integration tests (fixed mocking strategy). Added TestEndToEndValidation class with 5 E2E tests. Moved inline import asyncio to top-of-file in core/orchestrator.py. Added OR25 and OR26 to AGENTS.md. 7 new tests. |
| 64 | Core Mypy Remediation | 1232 | Fixed 33 mypy errors across 14 core files. Added compatibility shims for backward compatibility with tests. Added OR27 to AGENTS.md. |
| 65 | Mypy Remediation Phase 2 | 1232 | Fixed 16 mypy errors across 7 core files (session, task_state_machine, escalation, retention, worker_factory, orchestrator, rating_system). Enum replacements, UUID constructors, type annotations. Added L9 to LANDMINES. |
| 66 | System Cleanup and Final Core Hardening | 1231 | Fixed 23 mypy errors across 7 system files (model_acquisition, voice_daemon, trajectory_exporter, retention_manager, retention_daemon, monitor_daemon, model_evaluator). Added RETENTION_DAEMON to TraceComponent enum. Core mypy clean (0 errors). |
| 67 | Mypy Remediation: Adapters, CLI, Memory, Tests, Skills | 1230 | Fixed 172 mypy errors across 45 files (adapters, CLI, memory, workers, skills, tests, scripts). Union types, None handling, enum values, API compatibility, type annotations. Full-repo mypy clean (0 errors, 181 source files). |
| 68 | Phase 1 Foundation: Skill Taxonomy + CONTEXT.md | 1253 | SkillTier enum, SkillClassification dataclass, SkillTaxonomyRegistry. Default registry with 25 built-in skill classifications (15 user, 9 agent, 1 hybrid). CONTEXT.md project-level shared vocabulary. 20 new tests (14 taxonomy + 6 context). Fixed 2 pre-existing test failures (notes delete, qdrant embedder fallback). |
| 69 | Repo Hygiene: Governance Doc Fixes + Stale File Cleanup | 1253 | CHANGELOG fixes (date, timestamps, tag note, filename references). PLANS.md duplicate section removed. AGENTS.md header updated. AI_HANDOFF.md CONTEXT.md governance added. core/verbosity.py stale reference fixed. 5 new __init__.py files. exports/trajectories.jsonl untracked. Stale temp file deleted. |

---

## Next 5 Prompts Queue

### Plan 70 — [Open Slot] (Priority TBD)

**Scope**: TBD — to be defined by GLM based on project state post-Plan 69.

**Expected impact**: TBD

**Baseline changes**: TBD

**Gate**: TBD

---

### Plan 71 — [Open Slot] (Priority TBD)

**Scope**: TBD — to be defined by GLM based on project state post-Plan 69.

**Expected impact**: TBD

**Baseline changes**: TBD

**Gate**: TBD

---

### Plan 72 — 5-Plan Milestone Full Scan (Priority 1 — tentative)

**Scope**: Post-Plans 67-71 full-repo scan and baseline refresh. Capture new baselines after skill taxonomy foundation.

**Expected impact**:
- Scope TBD pending Plans 67-71 completion. This entry is a **placeholder**.
- Expected updates: mypy baseline (core/system clean, full-repo TBD), ruff (target: 0), bandit (target: 0 medium), pip-audit (target ≤20), vulture (target ≤25), test count (target ≈1253)

**Baseline changes**:
- Will be determined at Plan 72 scoping time (GLM inspects actual repo state)

**Gate**: Full 6-tool scan passes (pytest + ruff + mypy . + bandit + pip-audit + vulture). All baselines recorded. Handoff status sections updated.

---

### Plan 73 — [Open Slot] (Priority TBD)

**Scope**: TBD — to be defined by GLM based on project state post-Plan 71.

**Expected impact**: TBD

**Baseline changes**: TBD

**Gate**: TBD

---

### Plan 74 — [Open Slot] (Priority TBD)

**Scope**: TBD — to be defined by GLM based on project state post-Plan 73.

**Expected impact**: TBD

**Baseline changes**: TBD

**Gate**: TBD

---

### Plan 75 — [Open Slot] (Priority TBD)

**Scope**: TBD — to be defined by GLM based on project state post-Plan 74.

**Expected impact**: TBD

**Baseline changes**: TBD

**Gate**: TBD

---

## Baseline Reconciliation Notes

- **Test count delta**: 1253 → 1253 (no change). Docs-only plan, no test changes. Baseline held.
- **Mypy delta**: 0 → 0 (no change). Docs-only plan, no code changes. Baseline held.
- **Ruff delta**: 0 → 0 (no change). Docs-only plan baselines held.

---

## Status Sections

### What Works Right Now

- **Core command layer** — Command interface fully typed; trace emission working end-to-end
- **Observability infrastructure** — TraceEmitter working; structured logging integrated; Postgres trace store backend operational
- **Memory router** — All memory access routed through MemoryRouter; no direct imports; BackendRouter supports trace store registration
- **Serialization** — Jsonify strict mode, circular ref detection, type coercion all working
- **Datetime handling** — Zero naive/aware mixing; all core/system/skills using timezone-aware UTC
- **Ruff baseline** — 0 errors (Plan 59 cleanup held through Plans 56-66)
- **Mypy baseline** — Full-repo mypy clean (0 errors, 181 source files). Adapters, CLI, memory, workers, skills, tests, scripts all remediated through Plan 67.
- **Test suite** — 1253 passed, 67 skipped (Plan 68 skill taxonomy + CONTEXT.md; Plan 67 mypy remediation; Plan 66 system cleanup; Plan 63b added 7 integration + E2E tests; restored 2 orchestrator integration tests)
- **Eval harness** — Metrics (exact_match, token_f1, bleu, cosine_similarity) operational with trace emitter integration. Validation suite with 15 static tasks confirms metric behavior across 5 categories.
- **Skill taxonomy** — SkillTier enum (USER_INVOKED, AGENT_INVOKED, HYBRID), SkillClassification dataclass, SkillTaxonomyRegistry. Default registry with 25 built-in skill classifications. CONTEXT.md project-level shared vocabulary.

### What's Broken Right Now

None

### What's Built But Not Reachable

- **Improvement loop wire** — Wire module connecting eval harness, trace store, and improvement loop. IMPROVE command with DI support. Orchestrator fire-and-forget integration. Restored integration tests with correct mocking strategy. E2E validation scenarios operational.

### What's Deferred (Not Started)

- **LLM provider rotation** — background worker management, fallback chains (Priority 5+)
- **AIS data integration** — weather + vessel tracking (Priority 5+)
- **User preference learning** — adaptive command ranking (Priority 5+)
- **Web UI refinement** — responsive design, accessibility (Priority 5+)

---

## Research-Backed Feature Roadmap (Plan 67+)

Source: Analysis of 5 GitHub projects (DeerFlow 2.0, codebase-memory-mcp, mattpocock/skills, g-stack, hermes-agent). 16 replicable features identified, organized by integration phase.

### Phase 1 — Foundation (Plans 71–74, after Plan 70 milestone scan)

These features are high-impact, high-feasibility, and require minimal architectural changes:

| # | Feature | Source | Description |
|---|---|---|---|
| F1 | **Skill taxonomy** | mattpocock/skills | Classify skills as user-invoked (CLI triggers) vs agent-invoked (automatic). Enables skill discovery, routing, and permission scoping. |
| F2 | **CONTEXT.md shared language** | mattpocock/skills | Project-level CONTEXT.md file defining domain terms, conventions, and shared vocabulary. Reduces ambiguity in multi-agent coordination. |
| F3 | **Persist-nudge memory** | DeerFlow 2.0 | Persistent memory store with nudge-based retrieval. Agents store observations and are nudged when relevant context surfaces. Lightweight alternative to full RAG. |
| F4 | **Trust tier system** | g-stack | Three-tier trust model (trusted internal / semi-trusted external / untrusted user input) with graduated validation and sandboxing. Strengthens prompt injection defense. |

### Phase 2 — Intelligence (Plans 75–78)

These features add code intelligence and learning loops:

| # | Feature | Source | Description |
|---|---|---|---|
| F5 | **Code knowledge graph** | codebase-memory-mcp | SQLite-backed knowledge graph with sub-ms queries. Stores symbol definitions, call chains, and dependency edges. Replaces grep-based code search. |
| F6 | **Closed learning loop** | hermes-agent | Automated cycle: execute → evaluate → store → retrieve. Session outcomes feed back into future decisions without manual intervention. |
| F7 | **Session search (FTS5)** | hermes-agent | Full-text search over past session transcripts using SQLite FTS5. Enables "how did I solve X last time?" queries. |
| F8 | **Taste memory with decay** | g-stack | Preference scoring with exponential decay. Recent successes weighted higher than old ones. Prevents stale preference drift. |

### Phase 3 — Orchestration (Plans 79–82)

These features enhance agent coordination and lifecycle management:

| # | Feature | Source | Description |
|---|---|---|---|
| F9 | **SuperAgent harness** | DeerFlow 2.0 | Orchestrator that delegates to specialized sub-agents in Docker sandboxes. Isolates execution, enables parallel workstreams. |
| F10 | **Sprint lifecycle pipeline** | g-stack | Structured sprint workflow: backlog → in-progress → review → done. Integrates with plan-based development for status tracking. |
| F11 | **User modeling (Honcho)** | hermes-agent | Per-user behavioral modeling via Honcho. Adapts agent responses and priorities based on user interaction patterns. |
| F12 | **Cron scheduler** | hermes-agent | Built-in cron system for scheduled tasks (health checks, data refresh, periodic evaluations). Replaces external cron dependencies. |

### Phase 4 — Hardening (Plans 83–86)

These features add defense, portability, and resilience:

| # | Feature | Source | Description |
|---|---|---|---|
| F13 | **Docker sandbox execution** | DeerFlow 2.0 | Isolate agent code execution in Docker containers. Prevents runaway processes from affecting host. Complements OR28 zombie process prevention. |
| F14 | **Markdown skill definitions** | DeerFlow 2.0 | Skills defined as structured Markdown files (purpose, inputs, outputs, examples). Human-readable, version-controllable, LLM-parseable. |
| F15 | **Prompt injection defense** | g-stack | Multi-layer defense: input sanitization, output filtering, and trust-tier-based validation. Protects against adversarial prompts across trust boundaries. |
| F16 | **Incremental knowledge sync** | codebase-memory-mcp | Watch filesystem for changes and incrementally update the code knowledge graph. Avoids full re-index on every code change. |

### Integration Principles

- **No external dependencies required** — All features implementable with Python stdlib + existing Sovereign AI stack (SQLite, async, etc.).
- **Incremental adoption** — Each feature is self-contained; can be adopted independently without blocking others.
- **Plan-scoped delivery** — Each plan delivers 1–2 features with full test coverage. No big-bang integrations.
- **Baseline preservation** — Every feature plan must pass the same gates: pytest ±5, mypy file-scoped clean, ruff 0 errors.

### Source Projects

| Project | Key Insight |
|---|---|
| **DeerFlow 2.0** | SuperAgent orchestration with Docker isolation + Markdown-defined skills + persistent nudge memory |
| **codebase-memory-mcp** | Sub-ms code intelligence via SQLite knowledge graph + incremental sync |
| **mattpocock/skills** | Clean skill taxonomy (user/agent invocation) + CONTEXT.md shared vocabulary |
| **g-stack** | Sprint lifecycle + taste memory decay + multi-layer prompt injection defense + trust tiers |
| **hermes-agent** | Closed learning loop + FTS5 session search + Honcho user modeling + cron scheduler |

---

## Key Document Cross-References

- **Architecture rules** → `AGENTS.md` (always-on, every file edit MUST comply)
- **Git workflow** → `jarvis-open.md` (opening), `jarvis-close.md` (closing)
- **Verification procedure** → `jarvis-verify.md` (post-edit checks)
- **Full scan procedure** → `jarvis-scan.md` (5-plan checkpoints only)
- **GLM review process** → `AI_HANDOFF.md` (7-step workflow)
- **Known failure patterns** → `LANDMINES.md` (append-only; trigger + impact only)

---

## How to Update This Document

1. **After every plan**: Update "Completed Prompts" table with new row (add to bottom).
2. **At baseline changes**: Update "Test Baseline" or "Static Analysis Baseline" sections with new counts + source.
3. **When shifting queue**: Move active plan to completed table, promote Plan {N+1} to active, add new open slot at bottom.
4. **Status sections**: Update if a feature moved from "Built but not reachable" → "Works right now" or vice versa.
5. **Use Edit tool only** — never PowerShell `-replace` or `Set-Content` on this file (see AGENTS.md rule 23).

---

**Maintained by**: Devin (at plan closing), GLM (review only, does not edit directly)  
**Format**: Markdown, append-only where applicable (completed prompts, queue shift)  
**Governance**: Source of truth for baselines and queue. All references to test counts point here.
