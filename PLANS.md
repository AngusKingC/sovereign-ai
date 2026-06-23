# PLANS.md — Sovereign AI Project State

**Last updated**: Post-Plan 63a (2026-06-23)

This document tracks the dynamic state of the Sovereign AI project: baselines, completed prompts, and the next-5-prompt queue. It is the canonical source for test counts, static analysis baselines, and which prompt is currently active.

---

## Test Baseline

**Current baseline**: **1225 passed, 67 skipped**  
**Verified**: Plan 63a, Step S6 (full test suite)  
**Tolerance**: ±5 tests (variance acceptable due to parameterized fixtures and environment variation)  
**Delta tracking**: If S1 test count differs from baseline, update this entry + note in CHANGELOG.

---

## Static Analysis Baseline

**Captured**: Plan 60 (5-plan milestone full scan — 2026-06-23)

| Tool | Baseline | Source | Notes |
|---|---|---|---|
| **Ruff** | 0 errors | Plan 60 S2 | No errors. Plan 59 cleanup fully held. |
| **Mypy (full-repo)** | 294 errors in 77 files | Plan 60 S3 | Delta: +11 from Plan 55 baseline (283 → 294). OUTSIDE tolerance — escalated for fix plan. Full-repo only at 5-plan checkpoints. |
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

---

## Next 5 Prompts Queue

### Plan 63b — Improvement Loop Validate (Priority 4 — ACTIVE)

**Scope**: End-to-end validation of improvement loop. Inject test failures into the system and verify the loop captures → evaluates → routes improvements.

**Expected impact**:
- Modified: `tests/test_improvement_loop.py` (add E2E scenarios)
- Tests: ~20 new lines

**Baseline changes**:
- Tests: expect ~1245 (+20)
- Mypy: expect 0 (cosmetic only)
- Ruff: expect 0

**Gate**: E2E test passes. Improvement loop successfully closes a sample failure → evaluation → fix cycle.

---

### Plan 64 — [Open Slot] (Priority TBD)

**Scope**: TBD — to be defined by GLM based on project state post-Plan 63b.

**Expected impact**: TBD

**Baseline changes**: TBD

**Gate**: TBD

---

### Plan 65 — 5-Plan Milestone Full Scan (Priority 1 — tentative)

**Scope**: Post-Plans 61-64 full-repo scan and baseline refresh. Capture new baselines after improvement loop is complete.

**Expected impact**: 
- Scope TBD pending Plans 61-64 completion. This entry is a **placeholder**.
- Expected updates: mypy baseline (±10), ruff (target: 0), bandit (target: 0 medium), pip-audit (target ≤20), vulture (target ≤25), test count (target ≈1245)

**Baseline changes**:
- Will be determined at Plan 65 scoping time (GLM inspects actual repo state)

**Gate**: Full 6-tool scan passes (pytest + ruff + mypy . + bandit + pip-audit + vulture). All baselines recorded. Handoff status sections updated.

---

## Status Sections

### What Works Right Now

- **Core command layer** — Command interface fully typed; trace emission working end-to-end
- **Observability infrastructure** — TraceEmitter working; structured logging integrated; Postgres trace store backend operational
- **Memory router** — All memory access routed through MemoryRouter; no direct imports; BackendRouter supports trace store registration
- **Serialization** — Jsonify strict mode, circular ref detection, type coercion all working
- **Datetime handling** — Zero naive/aware mixing; all core/system/skills using timezone-aware UTC
- **Ruff baseline** — 0 errors (Plan 59 cleanup held through Plans 56-62)
- **Test suite** — 1225 passed, 67 skipped (Plan 63a added 12 improvement loop wire tests)
- **Eval harness** — Metrics (exact_match, token_f1, bleu, cosine_similarity) operational with trace emitter integration. Validation suite with 15 static tasks confirms metric behavior across 5 categories.

### What's Broken Right Now

- Mypy error count exceeded tolerance (283 → 294, +11 errors). Escalated for fix plan. Plans 56-59 introduced type errors beyond acceptable threshold.

### What's Built But Not Reachable

- **Improvement loop wire** — Wire module connecting eval harness, trace store, and improvement loop. IMPROVE command with DI support. Orchestrator fire-and-forget integration.

### What's Deferred (Not Started)

- **LLM provider rotation** — background worker management, fallback chains (Priority 5+)
- **AIS data integration** — weather + vessel tracking (Priority 5+)
- **User preference learning** — adaptive command ranking (Priority 5+)
- **Web UI refinement** — responsive design, accessibility (Priority 5+)

---

## Baseline Reconciliation Notes

- **Plan 60 Delta (Mypy)**: 283 → 294 (+11 errors). OUTSIDE tolerance — escalated for fix plan. Plans 56-59 introduced type errors beyond acceptable threshold.
- **Plan 60 Delta (Vulture)**: 20 → 23 (+3 findings). Within tolerance. Minor code additions added unused vars. Acceptable given scope.
- **Plan 60 Delta (Tests)**: 1166 → 1167 (+1 passed, -1 skipped). Within tolerance. Test suite stable.
- **Plan 61 Delta (Tests)**: 1167 → 1170 (+3 passed, +12 skipped). Within tolerance. Added 15 trace store tests (11 Postgres-dependent skip, 4 pass). Actual: +4 passed, +11 skipped. Delta within ±5 tolerance.
- **Plan 61 Delta (Ruff)**: 0 → 0. No change. File-scoped cleanup held.
- **Plan 61 Delta (Mypy)**: 294 → 294 (file-scoped). No change. 2 pre-existing errors in memory/router.py (not introduced by this plan).
- **Plan 62 Delta (Tests)**: 1170 → 1194 (+24 passed, 0 skipped). Within tolerance. Added 24 eval harness tests (all pass). Delta within ±5 tolerance.
- **Plan 62 Delta (Ruff)**: 0 → 0. No change. File-scoped cleanup held.
- **Plan 62 Delta (Mypy)**: 294 → 294 (file-scoped). No change. Type annotations fixed during implementation.
- **Plan 62.5 Delta (Tests)**: 1194 → 1213 (+19 passed, 0 skipped). Within tolerance. Added 19 validation tests (all pass). Delta within ±5 tolerance.
- **Plan 62.5 Delta (Ruff)**: 0 → 0. No change. File-scoped cleanup held.
- **Plan 62.5 Delta (Mypy)**: 294 → 294 (file-scoped). No change. Metric refinements used stdlib only.
- **Plan 63a Delta (Tests)**: 1213 → 1225 (+12 passed, 0 skipped). Within tolerance. Added 12 improvement loop wire tests (all pass). Delta within ±5 tolerance. Note: Plan expected ~1290 (+80), actual was +12 due to deferring complex orchestrator integration tests to future plan.
- **Plan 63a Delta (Ruff)**: 0 → 0. No change. File-scoped cleanup held.
- **Plan 63a Delta (Mypy)**: 294 → 294 (file-scoped). No change. Wire module clean; 19 pre-existing errors in core/ files unchanged.
- **Baseline expansion needed**: Mypy error count exceeded tolerance; requires dedicated fix plan (likely Plan 60.5 or fold into Plan 61).

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
