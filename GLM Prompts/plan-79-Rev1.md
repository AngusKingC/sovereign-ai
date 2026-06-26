# Plan 79 — Model Routing / Tiered Selection

## Context

PLANS.md queue entry (verified at commit `1973da0`, post-prompt-78):

> **Plan 79 — Model Routing / Tiered Selection (Priority 2 — Kimi High)**
> Scope: `ModelTierRouter` — classifies tasks by complexity (simple/medium/complex), routes to cheapest capable model, integrates with CostTracker (Plan 74) for budget-aware fallback. Required before PEMADS Phase 2 (avoids running full debate on trivial tasks).
> Expected impact: 60-90% cost optimization potential. Prerequisite for PEMADS Phase 2 cost control.

**Existing hook** (verified in `core/orchestrator.py:267-270` at commit `f54e488`):
```python
if cost_decision.fallback_model is not None:
    # Route to fallback model (will be wired in Plan 78 — Model Routing)
    logger.warning(
        f"Cost fallback triggered: routing to {cost_decision.fallback_model}"
    )
```
Plan 79 wires this hook. The comment "will be wired in Plan 78" was a planning error — Plan 78 was Circuit Breaker, not Model Routing. Plan 79 is the correct plan.

**prompt-78 S5 omission (remediation needed)**: prompt-78's S5 (CLI wiring of `WorkerCircuitBreaker` into `cli/serve.py` and `cli/tui.py`) was NOT executed. The circuit breaker feature is built but unreachable from production. Plan 79's S0.5 remediates this by wiring S5 of prompt-78 before Plan 79's body begins. This is in-scope for Plan 79 because (a) Plan 79 also needs CLI wiring for `ModelTierRouter`, establishing the pattern, and (b) leaving prompt-78's feature unreachable blocks PEMADS Phase 2's cascade-failure safety prerequisite.

**Author's reasoning**: Three-tier classification (simple/medium/complex) via keyword heuristics + task metadata, no LLM call for classification (keeps it cheap). Route to cheapest capable model per tier. Integrate with CostTracker: when spend cap approaches, downgrade tier (complex → medium → simple) before failing. The router is a pure function of (task, cost_state) → model_choice, no I/O, no side effects — testable in isolation.

**Confidence**: 78% overall. 85% on ModelTierRouter class (clear pattern, similar to TaskClassifier from Plan 76). 75% on orchestrator integration (touching the 1143-line `process_task` method). 70% on CostTracker fallback integration (the hook at line 267 needs careful wiring — the current code just logs, doesn't actually route). 80% on CLI wiring (mechanical, but prompt-78's S5 omission shows it can be skipped).

---

## Opening (S0)

### S0.1. Run `/jarvis-open`

Verify `prompt-78` tag exists on origin:
```powershell
git ls-remote --tags origin | Select-String "prompt-78"
```
If empty, push failed — STOP and report.

Confirm working copy is clean and on master:
```powershell
git status -s
git branch --show-current
```

**Applying OR26**: If `git status -s` shows modified/untracked governance docs or plan files, commit them as `docs: cleanup pre-prompt-79` tagged `docs-cleanup-79` BEFORE proceeding.

**Applying OR39**: If `plan-78*.md` files are untracked in `GLM Prompts/`, they are an OR26 violation — commit them in the `docs-cleanup-79` commit. The current plan's file (`plan-79*.md`) will be added in C12.

If the workflow is missing or fails, STOP and report.

### S0.2. Read AGENTS.md in full

AGENTS.md is always-on. Pay special attention to:
- AR1: `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, `system/`. (`ModelTierRouter` lives in `core/`; it must not import from `adapters/`.)
- AR9: No raw LLM calls outside `adapters/`. (Router classifies via heuristics, not LLM — no LLM calls in this plan.)
- AR11: `TraceEmitter` via constructor injection only.
- AR14: All public functions have return type annotations.
- AR18: No broad `except Exception: pass` without inline comment + WARNING trace.
- OR15: Pre-declare scope before editing.
- OR16: HARD STOP on scope expansion.
- OR22: Re-read AGENTS.md before any file edit.
- OR23: Cite rules by number when applying them.
- OR34: Execute steps in strict numerical order.

If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for diagnostic context.

### S0.3. Add any new AGENTS.md rules and commit

No new AGENTS.md rules this prompt. The existing rules are sufficient; prompt-78's S5 omission was an execution failure (OR16 scope deviation not reported), not a rule gap.

Commit as `docs: no new rules for plan-79` before proceeding.

### S0.4. Re-read AI_HANDOFF.md for GR1 compliance (GLM-side)

This step is for GLM's benefit — Devin does not need to execute it. Documented here for traceability: GLM should re-read `AI_HANDOFF.md` to verify GR1 (installed in prompt-78) is being followed. No action needed by Devin.

### S0.5. Remediate prompt-78 S5 omission (CLI wiring of WorkerCircuitBreaker)

**Applying OR16**: This step remediates a scope deviation from prompt-78. It is declared in Plan 79's scope (see Scope Declaration) because Plan 79 also does CLI wiring and the pattern should be established once. This is NOT scope creep — it is explicitly pre-declared.

**Applying AR8**: `cli/` may import from anywhere.

#### S0.5.1. Wire WorkerCircuitBreaker into `cli/serve.py`

Find where `Orchestrator` is instantiated (search for `Orchestrator(`). Add:
```python
from core.worker_circuit_breaker import WorkerCircuitBreaker

worker_circuit_breaker = WorkerCircuitBreaker(
    emitter=emitter,
    failure_threshold=3,
    reset_timeout=60,
)

orchestrator = Orchestrator(
    ...,
    worker_circuit_breaker=worker_circuit_breaker,
    # Issue #6 from Plan 78: 0.2 threshold for PEMADS Phase 2 (3-5 expert panel).
    # Any single expert failure (1/5 = 20%) triggers degraded mode.
    degraded_mode_threshold=0.2,
)
```

#### S0.5.2. Wire WorkerCircuitBreaker into `cli/tui.py` (if it instantiates Orchestrator)

Search for `Orchestrator(` in `cli/tui.py`. If found, add the same wiring.

#### S0.5.3. Verification

```powershell
python -c "import ast; ast.parse(open('cli/serve.py').read())"
python -c "import ast; ast.parse(open('cli/tui.py').read())"
ruff check cli/serve.py cli/tui.py
mypy cli/serve.py cli/tui.py --ignore-missing-imports
pytest tests/test_serve.py tests/test_tui.py -q --tb=short 2>&1 | Select-Object -Last 20
```

If no `test_serve.py` or `test_tui.py` exists, skip the pytest step — CLI smoke testing is manual.

**STOP condition**: If syntax/ruff/mypy fails, fix before proceeding to S1.

---

## Plan Body

### S1 — ModelTierRouter Implementation

**Applying AR1**: `ModelTierRouter` lives in `core/` (new file `core/model_tier_router.py`). It MUST NOT import from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, `system/`. It imports from `core/observability.py` only (for TraceEmitter).

**Applying AR11**: `TraceEmitter` injected via constructor.

**Applying AR14**: All public methods have return type annotations.

#### S1.1. Create `core/model_tier_router.py`

New module containing `ModelTierRouter` class. Pure function of (task, cost_state) → model_choice. No I/O, no side effects.

**Public API**:
```python
from enum import Enum
from dataclasses import dataclass

class TaskComplexity(str, Enum):
    """Complexity tier for routing decisions."""
    SIMPLE = "simple"      # e.g., arithmetic, lookups, single-step
    MEDIUM = "medium"      # e.g., summarization, single-file edits
    COMPLEX = "complex"    # e.g., multi-file refactors, debates, analysis

@dataclass
class ModelChoice:
    """Routing decision from ModelTierRouter."""
    model_name: str
    complexity: TaskComplexity
    reason: str            # e.g., "keyword match: 'calculate'", "cost cap downgrade"
    downgraded: bool       # True if cost cap forced a lower tier

class ModelTierRouter:
    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        # Tier → model mapping. Defaults are examples; production config in S5.
        simple_model: str = "llama3.2:1b",
        medium_model: str = "llama3.2:8b",
        complex_model: str = "gpt-4o",
    ) -> None: ...

    def classify(self, task: Task) -> TaskComplexity: ...
        """Classify task complexity via keyword heuristics + metadata.
        No LLM call. Returns SIMPLE/MEDIUM/COMPLEX.
        (Mirrors TaskClassifier pattern from Plan 76.)"""

    def route(
        self,
        task: Task,
        cost_decision: CostDecision | None = None,
    ) -> ModelChoice: ...
        """Route task to cheapest capable model.
        If cost_decision is provided and indicates fallback, downgrade tier.
        Returns ModelChoice with model_name, complexity, reason, downgraded flag."""

    def get_tier_for_model(self, model_name: str) -> TaskComplexity: ...
        """Reverse lookup: given a model name, return its tier.
        Used for logging and cost tracking."""
```

**Classification heuristics** (keyword-based, no LLM):
- SIMPLE: keywords like "calculate", "lookup", "define", "convert", "format", task has no file_path, output_length estimate < 100 tokens
- MEDIUM: keywords like "summarize", "edit", "refactor" (single file), "translate", output_length 100-1000 tokens
- COMPLEX: keywords like "debate", "analyze", "design", "implement", "refactor" (multi-file), task.assigned_worker_id indicates expert panel, output_length > 1000 tokens
- Default: MEDIUM (safer than SIMPLE for unknown tasks)

**CostTracker integration**: When `cost_decision.fallback_model is not None` (spend cap approaching), downgrade:
- COMPLEX → MEDIUM (use medium_model instead of complex_model)
- MEDIUM → SIMPLE (use simple_model instead of medium_model)
- SIMPLE → SIMPLE (already cheapest, no further downgrade — let CostTracker's hard fail take over)

#### S1.2. Syntax check + file-scoped ruff + mypy

```powershell
python -c "import ast; ast.parse(open('core/model_tier_router.py').read())"
ruff check core/model_tier_router.py
mypy core/model_tier_router.py --ignore-missing-imports
```

**STOP condition**: If any check fails, fix before proceeding.

#### S1.3. Create `tests/test_model_tier_router.py`

**Applying OR24**: Every new implementation MUST have a corresponding test file.

Test cases:
1. `test_classify_returns_simple_for_arithmetic_keywords` — "calculate 2+2" → SIMPLE
2. `test_classify_returns_simple_for_lookup_keywords` — "define photosynthesis" → SIMPLE
3. `test_classify_returns_medium_for_summarize` — "summarize this article" → MEDIUM
4. `test_classify_returns_medium_for_single_file_edit` — "edit main.py" → MEDIUM
5. `test_classify_returns_complex_for_debate` — "debate the best approach" → COMPLEX
6. `test_classify_returns_complex_for_multi_file_refactor` — "refactor across core/ and adapters/" → COMPLEX
7. `test_classify_returns_medium_for_unknown_tasks` — default fallback
8. `test_route_returns_simple_model_for_simple_task` — SIMPLE → simple_model
9. `test_route_returns_medium_model_for_medium_task` — MEDIUM → medium_model
10. `test_route_returns_complex_model_for_complex_task` — COMPLEX → complex_model
11. `test_route_downgrades_complex_to_medium_on_cost_fallback` — cost_decision.fallback_model set, COMPLEX task → medium_model, downgraded=True
12. `test_route_downgrades_medium_to_simple_on_cost_fallback` — cost_decision.fallback_model set, MEDIUM task → simple_model, downgraded=True
13. `test_route_does_not_downgrade_simple_below_simple` — cost_decision.fallback_model set, SIMPLE task → simple_model, downgraded=False (already cheapest)
14. `test_route_returns_correct_reason_string` — verify reason field is descriptive
15. `test_get_tier_for_model_returns_correct_tier` — reverse lookup works
16. `test_classify_handles_empty_task` — empty task → MEDIUM (default)
17. `test_classify_handles_none_metadata` — task with no metadata → MEDIUM (default)

#### S1.4. Run tests

```powershell
pytest tests/test_model_tier_router.py -q --tb=short
```

**STOP condition**: If any test fails, fix before proceeding.

---

### S2 — Wire ModelTierRouter into Orchestrator

**Applying AR11**: `ModelTierRouter` injected into `Orchestrator` via constructor.

#### S2.1. Update `core/orchestrator.py`

Add `model_tier_router` parameter to `Orchestrator.__init__`:
```python
def __init__(
    self,
    ...,
    model_tier_router: "ModelTierRouter | None" = None,
    ...
) -> None:
    self.model_tier_router = model_tier_router
```

#### S2.2. Wire the cost fallback hook (line 267-270)

Replace the current placeholder:
```python
# BEFORE (placeholder from prompt-78):
if cost_decision.fallback_model is not None:
    # Route to fallback model (will be wired in Plan 78 — Model Routing)
    logger.warning(
        f"Cost fallback triggered: routing to {cost_decision.fallback_model}"
    )

# AFTER (Plan 79 wires this):
if cost_decision.fallback_model is not None:
    if self.model_tier_router is not None:
        model_choice = self.model_tier_router.route(
            task, cost_decision=cost_decision
        )
        logger.warning(
            f"Cost fallback triggered: routing to {model_choice.model_name} "
            f"(downgraded: {model_choice.downgraded}, reason: {model_choice.reason})"
        )
        # Emit trace event
        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COST_FALLBACK_TRIGGERED,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Task routed to {model_choice.model_name} due to cost fallback",
                    data={
                        "task_id": task.task_id,
                        "original_tier": model_choice.complexity.value,
                        "model": model_choice.model_name,
                        "downgraded": model_choice.downgraded,
                        "reason": model_choice.reason,
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            logger.warning("Trace emission failed: %s", e)
    else:
        # No router configured — log and continue (backward compatible)
        logger.warning(
            f"Cost fallback triggered but no model_tier_router configured: "
            f"fallback_model={cost_decision.fallback_model}"
        )
```

**Applying AR18**: The `except Exception` block has inline comment explaining why it's broad (trace emission failure should not crash task processing) and logs. No `pass`.

#### S2.3. Add pre-execution routing (use router to select model before worker.run)

Before `worker.run(task)` (or `self._execute_task(task, worker_id)` if prompt-78's helper exists), add:
```python
# Pre-execution model routing (Plan 79)
if self.model_tier_router is not None:
    model_choice = self.model_tier_router.route(task)
    # Log routing decision (no enforcement yet — workers select their own adapters)
    # Plan 81 (PEMADS Phase 2) will use this for expert panel selection
    logger.info(
        f"Task {task.task_id} routed to {model_choice.model_name} "
        f"(tier: {model_choice.complexity.value})"
    )
```

**Note**: Plan 79 logs the routing decision but does NOT enforce it on workers (workers select their own adapters via `LLMAdapter` Protocol). Enforcement is deferred to Plan 81 (PEMADS Phase 2 Expert Panel Manager) where the panel manager will use `ModelTierRouter.route()` to select which expert model handles each turn. Plan 79 delivers the router + logging; Plan 81 delivers enforcement.

#### S2.4. Update existing orchestrator tests

Check `tests/test_orchestrator.py` for tests that instantiate `Orchestrator`. Add `model_tier_router=None` to those constructors (backward compatible — defaults to None).

**Applying OR25**: Test deletion is a scope deviation. If a test cannot be made to pass, STOP and report — do NOT delete or comment out.

#### S2.5. Syntax check + file-scoped ruff + mypy + tests

```powershell
python -c "import ast; ast.parse(open('core/orchestrator.py').read())"
ruff check core/orchestrator.py
mypy core/orchestrator.py --ignore-missing-imports
pytest tests/test_orchestrator.py -q --tb=short
```

**STOP condition**: If any test fails, fix before proceeding.

---

### S3 — CLI Wiring of ModelTierRouter

**Applying AR8**: `cli/` may import from anywhere.

#### S3.1. Update `cli/serve.py`

Find where `Orchestrator` is instantiated (already updated in S0.5.1 for WorkerCircuitBreaker). Add `ModelTierRouter`:
```python
from core.model_tier_router import ModelTierRouter

model_tier_router = ModelTierRouter(
    emitter=emitter,
    simple_model="llama3.2:1b",    # configurable via env/config in future
    medium_model="llama3.2:8b",
    complex_model="gpt-4o",
)

orchestrator = Orchestrator(
    ...,
    worker_circuit_breaker=worker_circuit_breaker,  # from S0.5.1
    degraded_mode_threshold=0.2,                    # from S0.5.1
    model_tier_router=model_tier_router,             # NEW — Plan 79
)
```

#### S3.2. Update `cli/tui.py` (if it instantiates Orchestrator)

Same wiring as S3.1.

#### S3.3. Verification

```powershell
python -c "import ast; ast.parse(open('cli/serve.py').read())"
python -c "import ast; ast.parse(open('cli/tui.py').read())"
ruff check cli/serve.py cli/tui.py
mypy cli/serve.py cli/tui.py --ignore-missing-imports
pytest tests/test_serve.py tests/test_tui.py -q --tb=short 2>&1 | Select-Object -Last 20
```

---

### S4 — Context Vocabulary Update

**Applying GR5**: Domain vocabulary lives in `CONTEXT.md` only.

#### S4.1. Add Model Routing vocabulary to `CONTEXT.md`

Append to the "Cost Tracking Vocabulary" section (or create a new "Model Routing Vocabulary" section):
```markdown
## Model Routing Vocabulary (NEW — Plan 79)

| Term | Definition |
|---|---|
| **ModelTierRouter** | Module (`core/model_tier_router.py`) that classifies tasks by complexity (SIMPLE/MEDIUM/COMPLEX) via keyword heuristics and routes to the cheapest capable model. No LLM calls for classification. Integrates with CostTracker for budget-aware tier downgrade. |
| **TaskComplexity** | Enum returned by `ModelTierRouter.classify()`. Values: SIMPLE (arithmetic, lookups), MEDIUM (summarization, single-file edits), COMPLEX (debates, multi-file refactors, analysis). Default: MEDIUM (safer for unknown tasks). |
| **ModelChoice** | Dataclass returned by `ModelTierRouter.route()`. Fields: model_name, complexity, reason, downgraded. `downgraded=True` when CostTracker fallback forced a lower tier. |
| **Tier Downgrade** | When CostTracker indicates spend cap approaching, router downgrades: COMPLEX → MEDIUM → SIMPLE. SIMPLE cannot be downgraded further — CostTracker's hard fail takes over. |
```

#### S4.2. Verification

```powershell
python -c "import ast; ast.parse(open('CONTEXT.md').read())" 2>&1 | Select-Object -Last 3
# CONTEXT.md is markdown, not Python — syntax check is a no-op but confirms file exists
```

---

## Closing

Run `/jarvis-close` per workflow file `.windsurf/workflows/jarvis-close.md`.

**Applying OR39**: Ensure `GLM Prompts/plan-79*.md` is added in the C12 docs commit:
```powershell
git add CHANGELOG.md PLANS.md LANDMINES.md "GLM Prompts/plan-79*.md"
```

**Applying OR38**: Plan 79 is in the 70s decade. No decade-boundary cleanup triggered (decade boundary is at prompt-80).

### Expected results

- **Tests**: 1386 + ~17 new tests = ~1403 passed, 67 skipped (delta +17, exceeds OR17 ±5 tolerance. OR17 invoked. Justification: all 17 tests are in-scope new tests for ModelTierRouter (S1.3). No existing tests modified or deleted except backward-compatible constructor param additions in test_orchestrator.py. Document in CHANGELOG.)
- **Ruff**: 0 errors
- **Mypy**: 0 errors (file-scoped on edited files)
- **New module**: `core/model_tier_router.py` with `ModelTierRouter`, `TaskComplexity`, `ModelChoice`
- **New Orchestrator param**: `model_tier_router`
- **New CLI wiring**: `cli/serve.py` and `cli/tui.py` instantiate `ModelTierRouter` and inject into `Orchestrator`
- **prompt-78 S5 remediation**: `WorkerCircuitBreaker` now wired into CLI (S0.5)
- **Cost fallback hook wired**: `core/orchestrator.py:267-270` placeholder replaced with actual routing logic

### Landmine capture (C11)

Candidate landmine to watch for: **prompt-78 S5 omission pattern** — Devin skipped S5 (CLI wiring) without reporting a STOP. This is an OR16 violation that went unreported. If this pattern recurs in Plan 79 (S3 skipped), capture as L22: "Devin skips CLI wiring steps (S5/S3) without reporting OR16 STOP — feature built but unreachable from production."

If any new failure pattern is discovered during execution, capture it in `LANDMINES.md` per GR11 (trigger + impact only, append-only).

---

## Scope Declaration

**Applying OR15 (pre-declare scope) and GR12 (GLM pre-declares scope before drafting)**:

### WILL edit (exhaustive list)

| File | Change |
|---|---|
| `core/model_tier_router.py` | NEW — `ModelTierRouter`, `TaskComplexity`, `ModelChoice` (S1.1) |
| `core/orchestrator.py` | Add `model_tier_router` param; wire cost fallback hook at line 267; add pre-execution routing log (S2.1, S2.2, S2.3) |
| `cli/serve.py` | Wire `WorkerCircuitBreaker` (S0.5.1 — prompt-78 remediation) + `ModelTierRouter` (S3.1) into `Orchestrator` instantiation |
| `cli/tui.py` | Wire `WorkerCircuitBreaker` (S0.5.2) + `ModelTierRouter` (S3.2) into `Orchestrator` instantiation IF it instantiates Orchestrator |
| `tests/test_model_tier_router.py` | NEW — 17 tests for `ModelTierRouter` (S1.3) |
| `tests/test_orchestrator.py` | Add `model_tier_router=None` to existing `Orchestrator` instantiations (S2.4, backward compatible) |
| `CONTEXT.md` | Add "Model Routing Vocabulary" section (S4.1) |
| `CHANGELOG.md` | Append entry at closing (C12) |
| `LANDMINES.md` | Append entry at closing IF new pattern discovered (C11) |
| `PLANS.md` | Update at closing (C12) — completed prompts row, baseline, queue shift |

### WILL NOT edit

- `AGENTS.md` (no new AR/OR rules — S0.3 says "No new AGENTS.md rules this prompt")
- `AI_HANDOFF.md` (GR1 already installed in prompt-78; no new GR rules this plan)
- `core/cost_tracker.py` (Plan 74 implementation is unchanged — Plan 79 integrates with it, doesn't modify it)
- `core/worker_circuit_breaker.py` (prompt-78 implementation is unchanged — S0.5 wires it, doesn't modify it)
- `core/schemas.py` (no new TaskStatus values needed)
- `core/task_state_machine.py` (no new transitions needed)
- `core/worker_base.py` (workers remain router-unaware — orchestrator logs routing, doesn't enforce)
- `core/worker_factory.py` (no changes — factory creates workers, doesn't route)
- `tests/test_worker_circuit_breaker.py` (prompt-78 tests unchanged)
- `tests/test_cost_tracker.py` (Plan 74 tests unchanged)
- `workers/`, `adapters/`, `memory/`, `system/`, `skills/`, `web/`, `scripts/` (no changes)

### Tests added

- 17 tests in `tests/test_model_tier_router.py` (S1.3)
- **Total**: 17 new tests (delta +17, exceeds OR17 ±5 tolerance — justification documented in CHANGELOG)

### Tests modified

- `tests/test_orchestrator.py`: existing tests that instantiate `Orchestrator` may need `model_tier_router=None` added (backward compatible — defaults to None)

### Baseline changes expected

- Test count: 1386 → ~1403 (+17, OR17 invoked)
- Ruff: 0 (baseline held)
- Mypy: 0 (baseline held, file-scoped)
- Coverage: 83% (may increase slightly due to new router tests)
- All other baselines unchanged

### HARD STOP conditions

- Any test fails after a file edit (OR16)
- Any file outside the "WILL edit" list needs editing (OR16, GR12)
- Syntax error after a file edit (OR6)
- Test count drops below 1386 (data integrity)
- Mypy errors increase (type safety)
- S0.5 (prompt-78 remediation) fails — STOP and report, do NOT proceed to S1 with prompt-78's feature still unreachable

**If any HARD STOP condition fires**: STOP and report per OR16. Do not fix unilaterally.
