# PLANS.md — Sovereign AI Project State

**Last updated**: Post-Plan 60 (2026-06-22)

This document tracks the dynamic state of the Sovereign AI project: baselines, completed prompts, and the next-5-prompt queue. It is the canonical source for test counts, static analysis baselines, and which prompt is currently active.

---

## Test Baseline

**Current baseline**: **1166 passed, 56 skipped**  
**Verified**: Plan 60, Step 1.1 (5-plan milestone full scan)  
**Tolerance**: ±5 tests (variance acceptable due to parameterized fixtures and environment variation)  
**Delta tracking**: If S1 test count differs from baseline, update this entry + note in CHANGELOG.

---

## Static Analysis Baseline

**Captured**: Plan 60 (5-plan milestone full scan — 2026-06-22)

| Tool | Baseline | Source | Notes |
|---|---|---|---|
| **Ruff** | 0 errors | Plan 60 S1.2 | No errors. Plan 59 cleanup fully held. |
| **Mypy (full-repo)** | 277 errors in 67 files | Plan 60 S1.3 | Delta: -6 from Plan 55 baseline (283 → 277). Within tolerance. Full-repo only at 5-plan checkpoints. |
| **Bandit** | 3,179 low severity | Plan 60 S1.4 | Plan 59 suppressed all 22 B108 findings. Zero medium, zero high. |
| **pip-audit** | 19 CVEs (4 packages) | Plan 60 S1.5 | Stable across Plans 56-60. No actionable fixes (upstream only). |
| **Vulture** | 22 high-confidence findings | Plan 60 S1.6 | Delta: +2 from Plan 55 baseline (20 → 22). Within tolerance. Dead code analysis only. |

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
| 60 | 5-plan checkpoint (mypy 277, bandit clean, pip-audit 19) | 1166 | Full 5-plan scan. Mypy: 283→277 (-6). Bandit medium: 22→0. pip-audit: 19 CVEs (stable). Vulture: 22 findings. |

---

## Next 5 Prompts Queue

### Plan 61 — Trace Store Implementation (Priority 2 — ACTIVE)

**Scope**: Implement persistent trace event storage in Postgres for measurement layer.

**Expected impact**:
- New file: `memory/postgres_trace_store.py` (~200 lines)
- Modified: `memory/__init__.py`, `core/observability.py` (trace emission routing)
- Tests: `tests/test_postgres_trace_store.py` (~150 lines)

**Baseline changes**: 
- Tests: expect ~1180 (+14 for trace store tests)
- Mypy: expect +5-10 errors (Postgres typing)
- Ruff: expect 0 (file-scoped cleanup)

**Gate**: Full test suite passes. Postgres connection pooling verified in test environment.

---

### Plan 62 — Eval Harness Implementation (Priority 3)

**Scope**: Implement offline evaluation harness for improvement loop. Evals compare LLM outputs against gold-standard responses.

**Expected impact**:
- New files: `evals/harness.py` (~250 lines), `evals/metrics.py` (~150 lines)
- Modified: `core/observability.py` (eval result recording)
- Tests: `tests/test_eval_harness.py` (~200 lines)

**Baseline changes**:
- Tests: expect ~1400 (+100 for eval tests)
- Mypy: expect +10-15 errors (metric typing, fuzzy matching)
- Ruff: expect 0

**Gate**: Eval harness runs on held-out validation set. Metrics (BLEU, cosine similarity) compute without errors.

---

### Plan 62.5 — Eval Validation (Priority 3)

**Scope**: Validate eval harness with held-out task suite. Run sample tasks through the harness and verify metric output.

**Expected impact**:
- Modified: `evals/harness.py` (minor refinements based on real data)
- Tests: expand `tests/test_eval_harness.py` (~50 new lines)

**Baseline changes**:
- Tests: expect ~1420 (+20)
- Mypy: expect -2-5 (clarified types from Plan 62 feedback)
- Ruff: expect 0

**Gate**: Harness runs 50+ validation tasks without errors. Metrics align with human judgment on sample outputs.

---

### Plan 63a — Improvement Loop Wire (Priority 4)

**Scope**: Wire up improvement loop components: trace store (Plan 61) + eval harness (Plan 62) + orchestrator. Route improvement tasks into the loop.

**Expected impact**:
- New files: `orchestrator/improvement_loop.py` (~200 lines)
- Modified: `core/commands.py` (improvement task routing), `memory/__init__.py` (trace store integration)
- Tests: `tests/test_improvement_loop.py` (~150 lines)

**Baseline changes**:
- Tests: expect ~1550 (+80)
- Mypy: expect +5-8 (orchestrator typing)
- Ruff: expect 0

**Gate**: Full integration test passes. Trace store receives eval results. Orchestrator routes improvement tasks to workers.

---

### Plan 63b — Improvement Loop Validate (Priority 4)

**Scope**: End-to-end validation of improvement loop. Inject test failures into the system and verify the loop captures → evaluates → routes improvements.

**Expected impact**:
- Modified: `tests/test_improvement_loop.py` (add E2E scenarios)
- Tests: ~20 new lines

**Baseline changes**:
- Tests: expect ~1560 (+10)
- Mypy: expect 0 (cosmetic only)
- Ruff: expect 0

**Gate**: E2E test passes. Improvement loop successfully closes a sample failure → evaluation → fix cycle.

---

### Plan 65 — 5-Plan Milestone Full Scan (Priority 1 — tentative)

**Scope**: Post-Plans 61-64 full-repo scan and baseline refresh. Capture new baselines after improvement loop is complete.

**Expected impact**: 
- Scope TBD pending Plans 61-64 completion. This entry is a **placeholder**.
- Expected updates: mypy baseline (±10), ruff (target: 0), bandit (target: 0 medium), pip-audit (target ≤20), vulture (target ≤25), test count (target ≈1560)

**Baseline changes**:
- Will be determined at Plan 65 scoping time (GLM inspects actual repo state)

**Gate**: Full 6-tool scan passes (pytest + ruff + mypy . + bandit + pip-audit + vulture). All baselines recorded. Handoff status sections updated.

---

## Status Sections

### What Works Right Now

- **Core command layer** — Command interface fully typed; trace emission working end-to-end
- **Observability infrastructure** — TraceEmitter working; structured logging integrated
- **Memory router** — All memory access routed through MemoryRouter; no direct imports
- **Serialization** — Jsonify strict mode, circular ref detection, type coercion all working
- **Datetime handling** — Zero naive/aware mixing; all core/system/skills using timezone-aware UTC
- **Ruff baseline** — 0 errors (Plan 59 cleanup held through Plans 56-60)
- **Test suite** — 1166 passed, 56 skipped (stable across Plans 56-60)

### What's Broken Right Now

- (None currently — baseline is clean.)

### What's Built But Not Reachable

- **Trace store interface** (core/observability.py) — defined but no backend yet. Plan 61 will implement Postgres backend.
- **Eval metrics** (evals/) — infrastructure exists for extensibility but no production integration. Plans 62+ wire this in.
- **Improvement loop orchestrator** — Commands defined, but loop wiring incomplete. Plans 63a/b will complete.

### What's Deferred (Not Started)

- **LLM provider rotation** — background worker management, fallback chains (Priority 5+)
- **AIS data integration** — weather + vessel tracking (Priority 5+)
- **User preference learning** — adaptive command ranking (Priority 5+)
- **Web UI refinement** — responsive design, accessibility (Priority 5+)

---

## Baseline Reconciliation Notes

- **Plan 60 Delta (Mypy)**: 283 → 277 (-6 errors). Within tolerance. New datetime fixes introduced 2 errors; plan cleanup eliminated 8. Net negative (good).
- **Plan 60 Delta (Vulture)**: 20 → 22 (+2 findings). Within tolerance. Minor code additions added 2 unused vars. Acceptable given scope.
- **No baseline expansion needed**: Test count stable; ruff holds at 0; no new critical issues.

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
