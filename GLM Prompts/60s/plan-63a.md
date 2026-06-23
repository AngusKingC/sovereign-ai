# Plan 63a -- Improvement Loop Wire

## Opening (S0)

1. **Run `/jarvis-open`** -- verify `prompt-62.5` tag on origin, confirm working copy clean and on master. If workflow missing or fails, STOP and report.
2. **Read AGENTS.md in full** -- no new rules this prompt. Apply all existing rules (AR1-AR18, OR1-OR24). Cite rules by number per OR23.
3. **Scope declaration** -- will edit:
   - `core/commands.py` -- add `IMPROVE` to `CommandType` enum, add `ImproveCommandHandler`
   - `core/orchestrator.py` -- wire improvement loop invocation after task completion (via wire module, not direct)
   - `orchestrator/__init__.py` -- new (export `ImprovementLoopOrchestrator`)
   - `orchestrator/improvement_loop.py` -- new module: wire eval harness + trace store + improvement loop
   - `tests/test_improvement_loop.py` -- new integration tests (~150 lines)
   - Will NOT edit: `core/orchestrator_improvement.py` (already exists), `evals/` (already validated), `memory/` (pre-check exports first), `adapters/`, `skills/`, `web/`, `cli/`, `workers/`, `gateways/`, `system/`

## Plan Body (S1-S6)

### S0.5 -- Pre-Check: memory/__init__.py Exports

Before S2, check if `PostgresTraceStore` is already exported from `memory/__init__.py`. If not, add it. If already exported, do not edit `memory/__init__.py`.

Verification: `python -c "from memory import PostgresTraceStore; print('OK')"` -- if this fails, add `from memory.postgres_trace_store import PostgresTraceStore` to `memory/__init__.py`.

### S1 -- Add IMPROVE Command Type and Handler

In `core/commands.py`:

1. Add `IMPROVE = "improve"` to `CommandType` enum (after `STATUS`)
2. Create `ImproveCommandHandler` class extending `CommandHandler`:
   - `execute()` -- accepts a `Command` with optional `kwargs["task_id"]` for targeted improvement, or `kwargs["recent_count"]` for batch improvement over last N tasks. Routes to `ImprovementLoopOrchestrator.process_improvement_task()` via the wire module.
   - `get_help()` -- returns help text for `/improve` command
   - `get_menu_item()` -- returns menu item for GUI interfaces
3. Register handler: `register_command(CommandType.IMPROVE, ImproveCommandHandler())`
4. Register alias: `register_command_alias("/improve", CommandType.IMPROVE)`

**Constraint**: `ImproveCommandHandler.execute()` must be async and return `CommandResult`. It does NOT directly call `OrchestratorImprovementLoop` -- it calls `ImprovementLoopOrchestrator.process_improvement_task()` which handles the orchestration.

### S2 -- Create orchestrator/improvement_loop.py (Wire Module)

New module (~200 lines). This is the **wire layer** -- it connects existing components without adding new logic.

**Responsibilities**:
- Connect `EvalHarness` -> `PostgresTraceStore` -> `OrchestratorImprovementLoop`
- Provide a single entry point for improvement tasks
- Handle async I/O and error boundaries

**Class: `ImprovementLoopOrchestrator`**

```python
class ImprovementLoopOrchestrator:
    """Orchestrates the improvement loop by wiring eval harness, trace store, and improvement logic.

    This is a thin wire layer -- all heavy logic lives in existing components:
    - EvalHarness (evals/) for evaluation
    - PostgresTraceStore (memory/) for trace persistence
    - OrchestratorImprovementLoop (core/) for improvement decisions
    """

    def __init__(
        self,
        eval_harness: EvalHarness,
        trace_store: PostgresTraceStore | None,
        improvement_loop: OrchestratorImprovementLoop,
        emitter: TraceEmitter | None = None,
    ) -> None:
        ...

    async def process_improvement_task(
        self,
        task_id: str | None = None,
        recent_count: int = 10,
    ) -> dict[str, Any]:
        """Process an improvement task.

        If task_id is provided, evaluate that specific task's traces.
        If task_id is None, evaluate the last `recent_count` tasks from trace store.

        Returns dict with:
        - "eval_results": list of EvalResult
        - "accuracy": float (routing accuracy from improvement loop)
        - "update_triggered": bool (whether instruction update was triggered)
        - "proposal": VersionUpdateProposal | None
        """
        ...
```

**Implementation details**:
1. Query trace store for recent traces (filter by `event_type` = `EVAL_COMPLETE` or `OPERATION_COMPLETE`)
2. Run eval harness on predicted vs gold outputs (extract from trace `data` field)
3. Feed eval results to `improvement_loop.record_routing_decision()` for each task
4. Call `improvement_loop.check_and_trigger_update()` to check if update needed
5. Return results dict

**Error handling**: Per AR18, any exception in the wire layer logs a WARNING trace and returns partial results -- never crashes the caller. The wire module is the **single integration point** for all improvement loop calls.

**Circular import protection**: Use `TYPE_CHECKING` guards for type annotations that reference `core/orchestrator.py`:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.orchestrator_improvement import OrchestratorImprovementLoop
```
Runtime imports go inside method bodies.

### S2.5 -- Create orchestrator/__init__.py

One line: `from orchestrator.improvement_loop import ImprovementLoopOrchestrator`

### S3 -- Wire Orchestrator to Invoke Improvement Loop (Via Wire Module)

In `core/orchestrator.py`, modify `process_task()` method:

After task transitions to `COMPLETE` (around line where scratchpad is compacted):

```python
# Improvement loop integration -- fire-and-forget via wire module
if self.improvement_loop_orchestrator is not None:
    try:
        # Route through wire module for full error handling
        task = asyncio.create_task(
            self.improvement_loop_orchestrator.process_improvement_task(
                task_id=str(task.task_id)
            )
        )
        # Suppress "Task exception was never retrieved" warning
        task.add_done_callback(lambda t: t.exception() if t.exception() else None)
    except Exception:
        # Per AR18: improvement loop failure should not crash task processing
        pass
```

**Key changes from previous draft**:
- Routes through `ImprovementLoopOrchestrator.process_improvement_task()` (wire module) rather than calling `improvement_loop` methods directly
- Adds `task.add_done_callback()` to suppress unretrieved exception warnings
- Uses `self.improvement_loop_orchestrator` (new attribute) instead of `self.improvement_loop` (old attribute)

**Orchestrator.__init__ update**: Add `improvement_loop_orchestrator: ImprovementLoopOrchestrator | None = None` parameter. Keep existing `improvement_loop` parameter for backward compatibility but mark it deprecated in docstring.

### S4 -- Create Integration Tests

`tests/test_improvement_loop.py` (~150 lines):

1. `test_improvement_loop_orchestrator_initialization` -- verify `ImprovementLoopOrchestrator` initializes with mocked dependencies
2. `test_process_improvement_task_queries_trace_store` -- verify trace store `query_traces` is called with correct filters
3. `test_process_improvement_task_runs_eval_harness` -- verify eval harness `evaluate` is called on trace data
4. `test_process_improvement_task_feeds_improvement_loop` -- verify `record_routing_decision` and `check_and_trigger_update` are called
5. `test_process_improvement_task_returns_results_dict` -- verify return dict has all expected keys
6. `test_orchestrator_invokes_wire_module_on_completion` -- verify orchestrator calls `ImprovementLoopOrchestrator.process_improvement_task()` via `asyncio.create_task` after task completion
7. `test_improve_command_handler_routes_to_wire` -- verify `ImproveCommandHandler.execute()` calls `ImprovementLoopOrchestrator.process_improvement_task()`
8. `test_improvement_loop_error_handling` -- verify exception in wire layer returns partial results, doesn't crash (AR18)
9. `test_orchestrator_done_callback_suppresses_warning` -- verify `add_done_callback` is attached to the task (mock `asyncio.create_task`, verify callback added)

**Mock strategy**:
- `EvalHarness`: mock `evaluate` to return `EvalResult` with dummy metrics
- `PostgresTraceStore`: mock `query_traces` to return list of dummy trace dicts
- `OrchestratorImprovementLoop`: mock `record_routing_decision` and `check_and_trigger_update`
- `Orchestrator`: mock `improvement_loop_orchestrator` attribute, verify `asyncio.create_task` called with wire module method

### S5 -- File-Scoped Verification (Fail Fast)

After each file edit, run `/jarvis-verify`. Then:

1. Syntax check on all edited files
2. Ruff: `ruff check core/commands.py core/orchestrator.py orchestrator/ tests/test_improvement_loop.py`
3. **Mypy on wire module first**: `mypy orchestrator/improvement_loop.py --ignore-missing-imports` -- check for new typing errors before full suite
4. Mypy on remaining edited files: `mypy core/commands.py core/orchestrator.py --ignore-missing-imports`
5. Targeted tests: `python -m pytest tests/test_improvement_loop.py -v`
6. Full harness tests: `python -m pytest tests/test_eval_harness.py tests/test_orchestrator_improvement.py -v`

If step 3 (mypy on wire module) fails, fix before proceeding. If step 5 fails, fix before step 6.

### S6 -- Baseline Reconciliation

Run full test suite: `python -m pytest tests/ -q --tb=short`

- Expected: ~1290 passed (+80 from new tests), 67 skipped
- If actual count differs by >5 from expected, update PLANS.md baseline per OR17.
- If ruff/mypy errors appear outside edited files, STOP and report -- do not fix unilaterally (OR16).

## Closing

**Run `/jarvis-close`** -- handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md, rule proposal, docs commit, push, post-push verification. If workflow missing or fails, STOP and report.

**Closing checklist:**
- [ ] ~1290 passed, 67 skipped
- [ ] Ruff: 0 errors
- [ ] Mypy: 0-8 errors (orchestrator typing, expected per PLANS.md); wire module mypy clean
- [ ] Tag `prompt-63a` created and pushed
- [ ] CHANGELOG entry appended
- [ ] PLANS.md: Plan 63a completed, Plan 63b promoted to ACTIVE
- [ ] No new LANDMINES.md entries (or capture if pattern found)
- [ ] C9: No new rules (unless pattern found)
