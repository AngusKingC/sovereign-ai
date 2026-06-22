# Plan 52: Wire cognition-loop subsystems into serve.py request path (F4 fix)

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result. If STOP fires, stop and report.
>
> **Mypy**: FILE-SCOPED only (L18). NEVER `mypy .`.
> **Commands**: PowerShell only (L21).

## Opening steps (run BEFORE Step 0)

1. **Start transcript**:
   ```powershell
   $logPath = "logs\execution-log-prompt-52.md"
   Start-Transcript -Path $logPath -Force
   ```
   If you open additional terminals, run `Start-Transcript -Path logs\execution-log-prompt-52-terminal{M}.md -Force` in each.

2. **Verify previous prompt completed**:
   ```powershell
   git ls-remote --tags origin | findstr prompt-51
   ```
   If empty, STOP — previous prompt's tag wasn't pushed.

3. **Pull latest**:
   ```powershell
   git pull origin master
   ```

## Status
- Priority: **P1**
- Effort: M
- Risk: MED
- Depends on: prompt-51
- Planned at: commit prompt-51 (a88ba88), 2026-06-20
- Revision: REV1 (2026-06-20)
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 findings 1-3 (Step 2.0 added to read OutputEvaluator.evaluate() signature before wiring; Step 0.5 added to capture mypy baseline for in-scope files; Step 4.0 added to verify TUI Orchestrator constructor structure).
- **Line numbers verified at clone SHA `50675f2`** (L20).

## Why this matters

F4 has been open since prompt-35.6b. `cli/serve.py` constructs 4 cognition-loop subsystems (`worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory`) but prefixes them with `_` and never passes them to anything. Plan 46 silenced the F841 warnings; this plan actually wires them. Without this, `jarvis serve` doesn't self-improve — the OrchestratorImprovementLoop is connected (it's set on the orchestrator), but the OutputEvaluator and TraceOptimiser that feed it evaluation data are dormant. This is the single highest-leverage next step per the comprehensive review.

## Current state

**File in scope**: `cli/serve.py` (1 file)

**Line numbers verified at SHA `50675f2`**:

The 4 subsystems are constructed but unused (lines 92, 123, 131, 152):
- Line 92: `_worker_persistence = WorkerPersistence(...)` — not passed to anything
- Line 123: `_output_evaluator = OutputEvaluator(...)` — not passed to anything
- Line 131: `_trace_optimiser = TraceOptimiser(...)` — not passed to anything
- Line 152: `_worker_factory = WorkerFactory(...)` — not passed to anything

**What IS already wired** (verified at SHA `50675f2`):
- Line 137: `orchestrator = Orchestrator(...)` — constructed ✅
- Line 162: `improvement_loop = OrchestratorImprovementLoop(...)` — constructed ✅
- Line 167: `orchestrator.improvement_loop = improvement_loop` — wired ✅
- Line 171: `ollama_worker = OllamaWorker(...)` — constructed ✅
- Line 175: `orchestrator.register_worker("ollama_worker", ollama_worker)` — wired ✅

**Key finding from code reading**: the Orchestrator constructor (line 137) does NOT accept `output_evaluator`, `trace_optimiser`, `worker_factory`, or `worker_persistence` as parameters. The orchestrator only accepts `memory_router`, `improvement_loop`, `approval_gate`, `escalation_engine`, `fallback_chain`, `a2a_router`, `input_sanitiser`, `emitter`. The `OrchestratorImprovementLoop` also doesn't use `output_evaluator` or `trace_optimiser` directly — it reads from `memory_router` and records metrics.

**This means**: the "wiring" is NOT passing these as constructor args. The wiring is:
1. `OutputEvaluator` — needs to be called after each worker output to evaluate quality. This happens in `route_task()` (line 317 of `core/orchestrator.py`), but the orchestrator doesn't currently call it. The orchestrator would need an `output_evaluator` attribute.
2. `TraceOptimiser` — needs to analyse trace events periodically. It's not called from the request path at all — it's a background analysis component.
3. `WorkerFactory` — already has `orchestrator` passed in its constructor (line 152). It's used to create workers dynamically. The `_` prefix is the only issue — remove it and it's "wired" (available for future use).
4. `WorkerPersistence` — saves/loads worker profiles. The `_` prefix is the issue — remove it and store it for use by the API endpoints.

**Step 0 — verify (slim per L18):**

0.1. `git rev-parse HEAD` — expected: descendant of prompt-51.
0.2. `git ls-remote --tags origin | findstr prompt-51` — confirm tag on origin (L5/L17/Rule 21).
0.3. `python -m pytest tests/ -q --tb=short | Select-Object -Last 3` — baseline: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing). If different, STOP.
0.4. `Select-String -Path cli/serve.py -Pattern "_worker_persistence|_output_evaluator|_trace_optimiser|_worker_factory"` — confirm 4 matches with `_` prefix. If 0, STOP — already fixed.
0.5. `mypy cli/serve.py core/orchestrator.py cli/tui.py --ignore-missing-imports 2>&1 | Measure-Object -Line` — capture mypy baseline for the 3 in-scope files (REV2). Write count to execution log. Gate 5 expects this count or lower (0 regressions introduced by Plan 52).

## What to change

### Step 1 — Remove `_` prefix from the 4 subsystem variables

In `cli/serve.py`, change the 4 variables from `_` prefixed to non-prefixed:

1.1. Line 92: `_worker_persistence` → `worker_persistence` (remove `_` prefix + the "F4 wiring deferred" comment)

1.2. Line 123: `_output_evaluator` → `output_evaluator`

1.3. Line 131: `_trace_optimiser` → `trace_optimiser`

1.4. Line 152: `_worker_factory` → `worker_factory`

**Verification**:
```powershell
Select-String -Path cli/serve.py -Pattern "_worker_persistence|_output_evaluator|_trace_optimiser|_worker_factory" | Measure-Object -Line
```
Expected: 0 (was 4). All `_` prefixes removed.

### Step 2 — Add `output_evaluator` to Orchestrator

2.0. **Read OutputEvaluator.evaluate() signature** (REV2 — mandatory precondition before wiring). Run:
```powershell
Select-String -Path core/evaluator.py -Pattern "def evaluate|async def evaluate" -Context 3,0
```
Paste the method signature to the execution log. Confirm the parameter names. Adjust the kwargs in Step 2.3 to match the actual parameter names. If the method doesn't exist, STOP (S4).

The orchestrator needs to call `OutputEvaluator` after each worker output to evaluate quality. This requires:

2.1. Add `output_evaluator` parameter to `Orchestrator.__init__` in `core/orchestrator.py`:
```python
def __init__(
    self,
    memory_router: "MemoryRouter",
    improvement_loop: "OrchestratorImprovementLoop | None" = None,
    cloud_fallback_model: str = "gpt-4o",
    approval_gate: "ApprovalGate | None" = None,
    escalation_engine: "EscalationEngine | None" = None,
    fallback_chain: "AdapterFallbackChain | None" = None,
    a2a_router: "A2ARouter | None" = None,
    input_sanitiser: InputSanitiser | None = None,
    output_evaluator: "OutputEvaluator | None" = None,  # NEW
    emitter: TraceEmitter | None = None,
) -> None:
```

2.2. Store it: `self.output_evaluator = output_evaluator` in the `__init__` body.

2.3. In `route_task()`, after the worker produces output (around line 400 where `improvement_loop.record_routing_decision` is called), add evaluation:
```python
# Evaluate output quality if evaluator is available
if self.output_evaluator:
    try:
        evaluation = await self.output_evaluator.evaluate(
            task=task,
            worker_output=output,
        )
        # Store evaluation in metrics
        # The evaluation result feeds into the improvement loop
    except Exception as inner_e:
        # Don't crash the request if evaluation fails
        await self.emitter.emit(TraceEvent(
            event_type=TraceEventType.OPERATION_ERROR,
            component=TraceComponent.ORCHESTRATOR,
            message="Output evaluation failed",
            level=TraceLevel.WARNING,
            data={"error": str(inner_e)},
        ))
```

2.4. In `cli/serve.py`, pass `output_evaluator` to the Orchestrator constructor (line 137):
```python
orchestrator = Orchestrator(
    memory_router=memory_router,
    improvement_loop=None,  # Will set after creating it
    cloud_fallback_model="gpt-4o",
    approval_gate=approval_gate,
    escalation_engine=escalation_engine,
    fallback_chain=fallback_chain,
    a2a_router=None,
    input_sanitiser=input_sanitiser,
    output_evaluator=output_evaluator,  # NEW
    emitter=emitter
)
```

**CAUTION**: the `OutputEvaluator` is constructed at line 123, BEFORE the Orchestrator at line 137. This is correct — the evaluator is passed INTO the orchestrator. Verify the construction order is: output_evaluator (line 123) → orchestrator (line 137).

**Verification**:
```powershell
mypy cli/serve.py core/orchestrator.py --ignore-missing-imports 2>&1 | Select-String "output_evaluator" | Measure-Object -Line
```
Expected: 0 errors related to output_evaluator.
```powershell
Select-String -Path core/orchestrator.py -Pattern "self.output_evaluator" | Measure-Object -Line
```
Expected: ≥1 (the attribute is stored + used).

### Step 3 — Wire `trace_optimiser` and `worker_factory` as available attributes

These two don't need to be passed to the orchestrator constructor — they're used by other components or future features:

3.1. `trace_optimiser` — store it as an attribute on the orchestrator for future use by the improvement loop. Add after line 167 (`orchestrator.improvement_loop = improvement_loop`):
```python
# Wire trace optimiser (analyses trace events for instruction updates)
orchestrator.trace_optimiser = trace_optimiser
```

3.2. `worker_factory` — it's already constructed with `orchestrator` passed in. Just remove the `_` prefix (done in Step 1.4). It's available for the API endpoints to create new workers dynamically.

3.3. `worker_persistence` — same. Remove `_` prefix (done in Step 1.1). Available for API endpoints to save/load worker profiles.

**Verification**:
```powershell
Select-String -Path cli/serve.py -Pattern "orchestrator.trace_optimiser" | Measure-Object -Line
```
Expected: ≥1.

### Step 4 — Update TUI to match (same pattern)

4.0. **Read TUI's Orchestrator constructor call** (REV2 — mandatory precondition). Run:
```powershell
Select-String -Path cli/tui.py -Pattern "Orchestrator(" -Context 5,0
```
Paste the constructor call to the execution log. Confirm it has the same kwarg structure as serve.py. If it differs, adjust Step 4's changes accordingly.

`cli/tui.py` has the same `_` prefixed variables (lines 349, 357, 380). Apply the same changes: remove `_` prefixes, pass `output_evaluator` to the orchestrator constructor, set `trace_optimiser` as an attribute.

**Verification**:
```powershell
Select-String -Path cli/tui.py -Pattern "_output_evaluator|_trace_optimiser|_worker_factory" | Measure-Object -Line
```
Expected: 0 (was 3).

### Step 5 — Verify no regressions

5.1. `ruff check cli/serve.py core/orchestrator.py cli/tui.py`

5.2. `mypy cli/serve.py core/orchestrator.py cli/tui.py --ignore-missing-imports`

5.3. `python -m pytest tests/ -q --tb=short | Select-Object -Last 3` — expected: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing). If NEW failure, STOP.

5.4. Manual smoke (the F4 verification):
```powershell
python -c "
import asyncio
from cli.serve import serve
# Can't call serve() directly (it starts uvicorn), but verify imports work
print('serve.py imports OK')
"
```

## Verification gates

1. `Select-String -Path cli/serve.py -Pattern "_worker_persistence|_output_evaluator|_trace_optimiser|_worker_factory" | Measure-Object -Line` — expected: 0 (was 4).
2. `Select-String -Path cli/tui.py -Pattern "_output_evaluator|_trace_optimiser|_worker_factory" | Measure-Object -Line` — expected: 0 (was 3).
3. `Select-String -Path core/orchestrator.py -Pattern "self.output_evaluator" | Measure-Object -Line` — expected: ≥1.
4. `Select-String -Path cli/serve.py -Pattern "orchestrator.trace_optimiser" | Measure-Object -Line` — expected: ≥1.
4b. `Select-String -Path cli/tui.py -Pattern "output_evaluator=" | Measure-Object -Line` — expected: ≥1 (REV2 — confirms TUI Orchestrator constructor got the kwarg).
5. `mypy cli/serve.py core/orchestrator.py cli/tui.py --ignore-missing-imports 2>&1 | Measure-Object -Line` — expected: count ≤ Step 0.5 baseline (REV2). 0 regressions introduced by Plan 52.
6. `python -m pytest tests/ -q --tb=short | Select-Object -Last 3` — expected: 1166 passed, 55 skipped, 1 failed (pre-existing calendar).
7. Manual smoke: `python -c "from cli.serve import serve; print('imports OK')"` — expected: `imports OK`.

## STOP conditions

- **S0**: HEAD not descendant of prompt-51. STOP.
- **S1**: prompt-51 tag absent from origin. STOP.
- **S2**: `_` prefixed variables not present (already fixed). STOP.
- **S3**: Test baseline not 1166/55/1 (calendar). STOP.
- **S4**: `OutputEvaluator.evaluate()` method doesn't exist or has incompatible signature. STOP — read the method signature before wiring.
- **S5**: File outside in-scope list (cli/serve.py, core/orchestrator.py, cli/tui.py). STOP.
- **S6**: New test failure. STOP.
- **S7**: Gate without evidence. STOP (Rule 19).
- **S8**: >50 lines per step. STOP.
- **S9**: Closing step without evidence. STOP (Rule 21/L17).
- **S10**: C5 reveals out-of-scope file. STOP.
- **S11**: C11 tag-push fails. STOP — retry; if fails, report.

## Closing steps (mandatory — Rule 21)

[Standard C1-C11 from handoff template — see handoff "Opening + Closing steps" section]

**C6 CHANGELOG**:
```
## 2026-06-21 HH:MM — prompt-52

**Plan**: Wire cognition-loop subsystems into serve.py + TUI request path (F4 fix)

**Changed**:
- cli/serve.py: removed _ prefix from 4 subsystems, wired output_evaluator to Orchestrator, set trace_optimiser as attribute
- core/orchestrator.py: added output_evaluator param to __init__, call evaluate() in route_task()
- cli/tui.py: same wiring as serve.py

**Results**:
- Mypy: [paste from execution log]
- Tests: 1166 passed, 55 skipped, 1 failed (pre-existing calendar)
- Tag: prompt-52 verified on origin
```

## Plan completion checklist (paste ALL before reporting done)

```
1. C1 test suite: <paste>
2. C4 tag created: <paste>
3. C5 file list: <paste>
4. C10 pushed: <paste>
5. C11 tag on origin: <paste>
6. Handoff updated: <paste completed prompts row>
7. Handoff baselines updated: <paste test baseline + mypy count>
```

## Out of scope

- Actually starting `jarvis serve` and hitting POST /api/tasks (requires Ollama running — manual verification deferred to user). Gate 7 verifies imports work, not end-to-end.
- Wiring TrajectoryExporter (it's functional but not reachable — deferred to a future plan).
- Adding new API endpoints for worker_factory or worker_persistence (future feature).
- The `_global_emitter` / `_global_registry` DI refactor (P3 deferred).
- Marine stack (Plan 55), test health (Plan 53), F401 bulk (Plan 54).

## For Claude review

1. The plan adds `output_evaluator` to the Orchestrator constructor. Is this the right place to wire it, or should it be passed to `OrchestratorImprovementLoop` instead (since the improvement loop is what uses evaluation data)?

2. Step 2.3 adds an evaluation call in `route_task()`. The plan says "around line 400 where `improvement_loop.record_routing_decision` is called" — is this the right location? The evaluation should happen AFTER the worker produces output, not before.

3. `TraceOptimiser` is set as an attribute on the orchestrator (`orchestrator.trace_optimiser = trace_optimiser`) but nothing calls it. Is this acceptable (available for future use) or should it be wired to something now?

4. The plan touches `core/orchestrator.py` — is this in scope given Rule 1 (core/ never imports from adapters/cli/etc.)? The `OutputEvaluator` is in `core/evaluator.py` — same layer. Should be fine.

5. `WorkerFactory` and `WorkerPersistence` just have their `_` prefixes removed. They're not actively wired to anything new — they're just "available" instead of "silenced". Is this sufficient for "F4 fixed", or should the plan wire them to something concrete?
