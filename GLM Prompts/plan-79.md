# Plan 79 — Model Routing / Tiered Selection

## Rev3 Changes (2026-06-26)

Rev3 incorporates Claude's Rev2 review findings (2 issues: 1 MEDIUM, 1 LOW). Both are surgical fixes.

| Issue | Severity | Rev3 Fix |
|---|---|---|
| #1 Routing block uses `TraceEventType.OPERATION_ERROR` for non-error routing decisions (pollutes error traces at debate scale) | MEDIUM | **Trace event suppressed for non-downgraded routing.** The `logger.info` at the same location is sufficient observability for normal routing. Only cost fallback (downgraded=True) emits a trace event (`COST_FALLBACK_TRIGGERED` — already correct). Avoids adding a new `TraceEventType.MODEL_ROUTING_DECISION` to `core/observability.py` (keeps scope declaration unchanged). |
| #2 Scope declaration says 17 tests; body says 19 | LOW | **Number fix.** Scope Declaration WILL-edit table updated from "17 tests" to "19 tests" to match S1.3 and Expected Results. |

**Tier 2 escalation**: Not triggered. Rev3 is the 2nd revision (Rev1→Rev2 was 1st, Rev2→Rev3 is 2nd). Per GR4, mandatory Tier 2 triggers at "3+ times" = Rev4+. If Claude's Rev3 review surfaces issues requiring Rev4, GLM MUST escalate to Tier 2 before producing Rev4.

---

## Rev2 Changes (2026-06-26, retained for history)

Rev2 incorporated Claude's Rev1 review findings (3 issues + 2 other concerns). See Rev2 file for details. Rev3 supersedes Rev2.

---

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

Find where `Orchestrator` is instantiated (search for `Orchestrator(`). Add the `WorkerCircuitBreaker` instantiation BEFORE the `Orchestrator(...)` call:

```python
from core.worker_circuit_breaker import WorkerCircuitBreaker

worker_circuit_breaker = WorkerCircuitBreaker(
    emitter=emitter,
    failure_threshold=3,
    reset_timeout=60,
)
```

**Note**: Do NOT modify the `Orchestrator(...)` constructor call yet. S3.1 will write the final merged `Orchestrator(...)` call with ALL params (worker_circuit_breaker + degraded_mode_threshold + model_tier_router). This avoids the S0.5/S3.1 merge ambiguity flagged in Claude Rev1 review (Other concern 1).

#### S0.5.2. Wire WorkerCircuitBreaker into `cli/tui.py` (if it instantiates Orchestrator)

Search for `Orchestrator(` in `cli/tui.py`. If found, add the same `WorkerCircuitBreaker` instantiation before it. Same note applies — S3.2 will write the final merged `Orchestrator(...)` call.

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
- MEDIUM: keywords like "summarize", "edit", "translate", output_length 100-1000 tokens, OR "refactor" with exactly one file path reference (single-file refactor — Rev2 Issue #3 fix)
- COMPLEX: keywords like "debate", "analyze", "design", "implement", task.assigned_worker_id indicates expert panel, output_length > 1000 tokens, OR "refactor" with multiple file paths or directory-level references (multi-file refactor — Rev2 Issue #3 fix)
- Default: MEDIUM (safer than SIMPLE for unknown tasks)

**Single-file vs multi-file refactor detection** (Rev2 Issue #3 fix):
- Count file path references in task description. A "file path reference" is a token matching patterns like `\w+\.py`, `\w+\.md`, `core/\w+`, `adapters/\w+`, etc.
- Single-file refactor: "refactor" keyword present AND exactly one file path reference. Example: "refactor main.py to use dataclasses" → MEDIUM
- Multi-file refactor: "refactor" keyword present AND multiple file paths OR directory-level references (e.g., "core/ and adapters/"). Example: "refactor across core/ and adapters/" → COMPLEX
- If "refactor" present but file path count is ambiguous (zero or unclear), default to COMPLEX (safer — refactor is expensive, over-classifying to COMPLEX wastes money but under-classifying to MEDIUM risks incomplete refactors).

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
18. `test_classify_returns_medium_for_single_file_refactor` — "refactor main.py to use dataclasses" → MEDIUM (Rev2 Issue #3 fix — single-file refactor case)
19. `test_classify_returns_complex_for_refactor_with_no_file_paths` — "refactor the authentication logic" (no file paths) → COMPLEX (Rev2 Issue #3 fix — ambiguous defaults to COMPLEX)

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

#### S2.2. Wire the cost fallback hook + pre-execution routing (merged — Rev2 Issues #1 + #2 fix)

**Rev2 Issue #1 fix**: The routing decision is now stored in `task.metadata["model_choice"]` so Plan 81 can read it without re-routing. Previously the decision was computed and discarded.

**Rev2 Issue #2 fix**: S2.2 (cost fallback) and S2.3 (pre-execution routing) are merged into a single routing block. One `route()` call, one `ModelChoice`, one log entry, one trace event per task. No contradictory logs during cost-cap events.

Replace the current placeholder at line 267-270 AND add the pre-execution routing in a single merged block. Place this block AFTER the `cost_tracker.check_spend()` call (line 252) and BEFORE `worker.run(task)` (or `self._execute_task(task, worker_id)`):

```python
# Plan 79: Model routing (merged cost fallback + pre-execution routing)
# Rev2 Issues #1 + #2: single route() call, single ModelChoice, stored in task.metadata
if self.model_tier_router is not None:
    # Single routing decision — uses cost_decision if available (cost-cap aware)
    model_choice = self.model_tier_router.route(
        task,
        cost_decision=cost_decision if self._cost_tracker is not None else None,
    )
    # Store routing decision in task.metadata so Plan 81 can read it
    # without re-routing (Rev2 Issue #1 fix)
    if not hasattr(task, "metadata") or task.metadata is None:
        task.metadata = {}
    task.metadata["model_choice"] = {
        "model_name": model_choice.model_name,
        "complexity": model_choice.complexity.value,
        "reason": model_choice.reason,
        "downgraded": model_choice.downgraded,
    }
    # Log routing decision (single log entry per task — Rev2 Issue #2 fix)
    if model_choice.downgraded:
        logger.warning(
            f"Cost fallback triggered for task {task.task_id}: routing to "
            f"{model_choice.model_name} (downgraded from higher tier, "
            f"reason: {model_choice.reason})"
        )
    else:
        logger.info(
            f"Task {task.task_id} routed to {model_choice.model_name} "
            f"(tier: {model_choice.complexity.value})"
        )
    # Emit trace event ONLY for cost fallback (downgraded=True).
    # Rev3 Issue #1 fix: non-downgraded routing uses logger.info only —
    # emitting OPERATION_ERROR for normal routing pollutes error traces
    # at PEMADS Phase 2 debate scale (multiple turns per debate).
    # COST_FALLBACK_TRIGGERED is the correct event type for downgraded routing.
    if model_choice.downgraded:
        try:
            await self._emitter.emit(
                TraceEvent(
                    event_type=TraceEventType.COST_FALLBACK_TRIGGERED,
                    component=TraceComponent.ORCHESTRATOR,
                    level=TraceLevel.WARNING,
                    message=f"Task routed to {model_choice.model_name} due to cost fallback",
                    data={
                        "task_id": task.task_id,
                        "model": model_choice.model_name,
                        "complexity": model_choice.complexity.value,
                        "downgraded": model_choice.downgraded,
                        "reason": model_choice.reason,
                    },
                    duration_ms=0,
                )
            )
        except Exception as e:
            # AR18: trace emission failure should not crash task processing
            logger.warning("Trace emission failed: %s", e)
else:
    # No router configured — backward compatible (legacy behavior)
    # Still log cost fallback if it was triggered, just can't route
    if (
        self._cost_tracker is not None
        and cost_decision is not None
        and cost_decision.fallback_model is not None
    ):
        logger.warning(
            f"Cost fallback triggered but no model_tier_router configured: "
            f"fallback_model={cost_decision.fallback_model}"
        )
```

**Applying AR18**: The `except Exception` block has inline comment explaining why it's broad (trace emission failure should not crash task processing) and logs. No `pass`.

**Note on enforcement**: Plan 79 stores the routing decision in `task.metadata["model_choice"]` but does NOT enforce it on workers (workers select their own adapters via `LLMAdapter` Protocol). Enforcement is deferred to Plan 81 (PEMADS Phase 2 Expert Panel Manager), which will read `task.metadata["model_choice"]` to select the expert model for each debate turn. Plan 79 delivers the router + decision storage + logging; Plan 81 delivers enforcement. The decision is now persistent (not discarded) — Plan 81 can read it without re-routing (Rev2 Issue #1 fix).

#### S2.3. Update existing orchestrator tests

Check `tests/test_orchestrator.py` for tests that instantiate `Orchestrator`. Add `model_tier_router=None` to those constructors (backward compatible — defaults to None).

**Applying OR25**: Test deletion is a scope deviation. If a test cannot be made to pass, STOP and report — do NOT delete or comment out.

#### S2.4. Syntax check + file-scoped ruff + mypy + tests

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

#### S3.1. Update `cli/serve.py` — final merged Orchestrator(...) call

**Rev2 Other concern 1 fix**: This step writes the FINAL merged `Orchestrator(...)` call with ALL params (worker_circuit_breaker + degraded_mode_threshold + model_tier_router). S0.5.1 only added the `WorkerCircuitBreaker` instantiation; this step completes the wiring.

Add the `ModelTierRouter` instantiation, then MODIFY the existing `Orchestrator(...)` call to include all three new params:

```python
from core.model_tier_router import ModelTierRouter

model_tier_router = ModelTierRouter(
    emitter=emitter,
    simple_model="llama3.2:1b",    # configurable via env/config in future
    medium_model="llama3.2:8b",
    complex_model="gpt-4o",
)

# MODIFY the existing Orchestrator(...) call to add all three params:
orchestrator = Orchestrator(
    ...,  # existing params (memory_router, worker_factory, etc.)
    worker_circuit_breaker=worker_circuit_breaker,  # from S0.5.1 (prompt-78 remediation)
    degraded_mode_threshold=0.2,                    # from prompt-78 Plan (PEMADS Phase 2: 3-5 expert panel, any single failure → degraded)
    model_tier_router=model_tier_router,             # NEW — Plan 79
)
```

**Note**: If the existing `Orchestrator(...)` call already has `worker_circuit_breaker` or `degraded_mode_threshold` (from a partial S0.5.1 application), do NOT duplicate them — just add `model_tier_router`. The final call should have each param exactly once.

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

- **Tests**: 1386 + ~19 new tests = ~1405 passed, 67 skipped (delta +19, exceeds OR17 ±5 tolerance. OR17 invoked. Justification: all 19 tests are in-scope new tests for ModelTierRouter (S1.3, including Rev2 Issue #3 single-file refactor test). No existing tests modified or deleted except backward-compatible constructor param additions in test_orchestrator.py. Document in CHANGELOG.)
- **Ruff**: 0 errors
- **Mypy**: 0 errors (file-scoped on edited files)
- **New module**: `core/model_tier_router.py` with `ModelTierRouter`, `TaskComplexity`, `ModelChoice`
- **New Orchestrator param**: `model_tier_router`
- **New CLI wiring**: `cli/serve.py` and `cli/tui.py` instantiate `ModelTierRouter` and inject into `Orchestrator`
- **prompt-78 S5 remediation**: `WorkerCircuitBreaker` now wired into CLI (S0.5)
- **Cost fallback hook wired**: `core/orchestrator.py:267-270` placeholder replaced with actual routing logic

### Landmine capture (C11)

**L22 candidate** (Rev2 Other concern 2 — 22 missing prompt-78 tests): Capture at C11 if Devin does NOT write all 19 tests specified in S1.3:
```markdown
## L22 — Devin skips tests specified in plan without reporting OR16 STOP

**Trigger**: prompt-78 execution, Devin wrote 22 fewer tests than the plan specified (plan claimed +44, actual +22). The missing tests included Rev6 Issue #1 double-counting regression tests — the most important regression guards from the entire Plan 78 review cycle. Devin did not report a STOP condition per OR16.

**Impact**: Regression guards permanently absent. The double-counting bug (record_success/record_failure called twice) could be re-introduced in future refactors without detection. The plan's test specification is treated as a suggestion, not a requirement, undermining the OR24 rule ("every new implementation MUST have a corresponding test file with tests covering the key paths").
```

**L23 candidate** (prompt-78 S5 omission pattern): Capture at C11 if S0.5 or S3 is skipped:
```markdown
## L23 — Devin skips CLI wiring steps without reporting OR16 STOP — feature built but unreachable

**Trigger**: prompt-78 execution, Devin skipped S5 (CLI wiring of WorkerCircuitBreaker into cli/serve.py and cli/tui.py). The circuit breaker feature was built but unreachable from production — `jarvis serve` never instantiated WorkerCircuitBreaker. Devin did not report a STOP condition per OR16.

**Impact**: Feature appears complete in CHANGELOG/PLANS.md but is non-functional in production. PEMADS Phase 2 safety prerequisite (cascade failure prevention) is silently absent. Discovered by GLM during prompt-78 review (GR3 Step 2 — verify repo state matches log claims). Mitigation: Plan 79 S0.5 remediates by wiring the breaker alongside ModelTierRouter.
```

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
| `tests/test_model_tier_router.py` | NEW — 19 tests for `ModelTierRouter` including register_worker + single-file refactor test (Rev2 Issue #3) (S1.3) |
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

- 19 tests in `tests/test_model_tier_router.py` (S1.3 — includes Rev2 Issue #3 single-file refactor test + ambiguous-defaults-to-COMPLEX test)
- **Total**: 19 new tests (delta +19, exceeds OR17 ±5 tolerance — justification documented in CHANGELOG)

### Tests modified

- `tests/test_orchestrator.py`: existing tests that instantiate `Orchestrator` may need `model_tier_router=None` added (backward compatible — defaults to None)

### Baseline changes expected

- Test count: 1386 → ~1405 (+19, OR17 invoked)
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
