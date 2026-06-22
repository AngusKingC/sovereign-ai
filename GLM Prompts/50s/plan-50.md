# Plan 50: Fix MockMemoryRouter/MockStateMachine inheritance to eliminate 122 mypy errors

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise.
>
> Drift check (run first):
> `git diff --stat prompt-49b..HEAD -- tests/`
> If any test file changed since prompt-49b, compare Current state
> excerpts against live code; on mismatch, STOP.

## Status
- Priority: P2
- Effort: M
- Risk: LOW (test-only changes — no production code touched)
- Depends on: prompt-49b (old-API callers migrated, mypy baseline established)
- Planned at: commit prompt-49b (2db2cc7), 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft.
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-2 (S4 clarified to cover ALL 8 files; S10 parenthetical updated for Step 6's 3-file combination).

## Why this matters

The 2026-06-20 scan found 122 mypy errors across 8 test files — all caused by `MockMemoryRouter` and `MockStateMachine` classes that don't inherit from the real classes they're mocking. When these mocks are passed to constructors like `ApprovalGate(state_machine, memory_router)`, mypy flags "Argument has incompatible type MockMemoryRouter; expected MemoryRouter". The tests run fine (Python is duck-typed), but mypy can't verify type safety. This is the single largest category of mypy errors remaining (122 of 435 total). The fix is mechanical: make each mock inherit from the real class (`class MockMemoryRouter(MemoryRouter)`) and implement only the methods that need mocking. This satisfies mypy without changing test behavior.

## Current state

**Files in scope (Plan 50 may edit only these — 8 test files):**
- `tests/test_approval_gate.py` — 32 errors (MockMemoryRouter + MockStateMachine)
- `tests/test_resource_manager.py` — 19 errors (MockMemoryRouter)
- `tests/test_task_state_machine.py` — 17 errors (MockMemoryRouter)
- `tests/test_model_acquisition.py` — 13 errors (MockMemoryRouter)
- `tests/test_ollama_worker.py` — 12 errors (MockMemoryRouter)
- `tests/test_model_registry.py` — 11 errors (MockMemoryRouter)
- `tests/test_scratchpad.py` — 10 errors (MockMemoryRouter)
- `tests/test_system_profiler.py` — 8 errors (MockMemoryRouter)

**Additional files with MockMemoryRouter but 0 mypy errors** (not in scope — their mocks aren't passed to type-checked constructors):
- `tests/test_approval_trust.py`, `tests/test_model_evaluator.py`, `tests/test_worker_factory.py` — these have `MockMemoryRouter` but don't trigger mypy errors. Leave them alone (STOP S6 if they need editing).

**Step 0 — verify current state (paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA. Expected: `2db2cc7` (prompt-49b) or descendant. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-49b` — confirm tag on origin. If absent, STOP (landmine L5).

0.3. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "MockMemoryRouter\|MockStateMachine" | wc -l` — capture actual count (L13). Expected: ~122. Paste actual count to CHANGELOG. If 0, STOP — someone already fixed it.

0.4. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "MockMemoryRouter\|MockStateMachine" | cut -d: -f1 | sort | uniq -c | sort -rn` — paste per-file breakdown. Confirm the 8 files match the in-scope list.

0.5. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep -c "error:"` — capture TOTAL mypy count. Expected: ~435. Paste actual count. This is the baseline for Gate 2.

0.6. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match prompt-49b baseline (1167 passed, 55 skipped, 0 failed on Windows; on Linux subset: ~1087 passed, 1 skipped, 2 pre-existing failures). Paste actual output.

0.7. For each of the 8 in-scope test files, run `grep -n "class MockMemoryRouter\|class MockStateMachine" tests/<file>.py` — paste all 8 outputs. Confirm: each file defines its own mock class that does NOT inherit from the real class (i.e., `class MockMemoryRouter:` not `class MockMemoryRouter(MemoryRouter):`).

0.8. `grep -n "class MemoryRouter" core/memory_router.py` and `grep -n "class TaskStateMachine" core/task_state_machine.py` — confirm the real class names and locations. Paste output.

0.9. `grep -n "async def \|def " core/memory_router.py | head -20` — paste the MemoryRouter method signatures. The mocks need to implement (or override) these: `fetch`, `write`, `list_keys`, `scoped_read`, `scoped_write`, `fetch_by_type`, `get_global_context`, `set_global_context`. Note which methods each mock currently implements vs which it inherits.

0.10. `grep -n "async def \|def " core/task_state_machine.py | head -15` — paste TaskStateMachine method signatures. The mock needs: `transition`, `can_transition`, `is_terminal`, `get_valid_next_states`, `checkpoint`, `load_checkpoints`.

If any of these do not match, STOP — the plan was written against stale state.

**Repo conventions:**
- `tests/` can import from anywhere (no architecture rule restriction on test imports).
- All I/O operations are async (Rule 13). Mock methods must be `async def` if the real method is async.
- No broad `except Exception: pass` without inline comment + WARNING trace (Rule 17).
- All public functions have return type annotations (Rule 9). Mock methods should have return type annotations matching the real class.

## What to change

### Step 1 — Fix MockMemoryRouter in tests/test_approval_gate.py (32 errors, has MockStateMachine too)

This is the most complex file — it has both `MockMemoryRouter` AND `MockStateMachine`.

1.1. Read the current `MockMemoryRouter` and `MockStateMachine` classes in `tests/test_approval_gate.py`. Note which methods they implement.

1.2. Change `class MockMemoryRouter:` to `class MockMemoryRouter(MemoryRouter):` and add the import: `from core.memory_router import MemoryRouter`.

1.3. The mock must call `super().__init__()` (or provide the required args). Read `MemoryRouter.__init__` signature — it takes `backends: dict[str, MemoryBackend] | None = None`. The mock's `__init__` should call `super().__init__()` with no backends (the mock overrides all methods that would use backends).

1.4. Change `class MockStateMachine:` to `class MockStateMachine(TaskStateMachine):` and add the import: `from core.task_state_machine import TaskStateMachine`.

1.5. `TaskStateMachine.__init__` takes `memory_router: MemoryRouter`. The mock's `__init__` should call `super().__init__(memory_router=MockMemoryRouter())` (or pass the mock instance).

1.6. **CAUTION**: if `super().__init__()` does any real work (creates tables, connects to backends), the mock must override `__init__` to skip that work. Check the real `__init__` — if it does I/O, the mock should NOT call `super().__init__()` and instead just set the attributes it needs. Use `# type: ignore[override]` if needed, but prefer proper inheritance.

1.7. **Verification**:
```
mypy tests/test_approval_gate.py --ignore-missing-imports 2>&1 | grep "MockMemoryRouter\|MockStateMachine" | wc -l
```
Expected: 0 (was 32). Paste literal output.
```
python -m pytest tests/test_approval_gate.py -v
```
Expected: all tests pass (0 skipped, 0 failed). Paste `Select-Object -Last 5`.

### Step 2 — Fix MockMemoryRouter in tests/test_resource_manager.py (19 errors)

2.1. Change `class MockMemoryRouter:` to `class MockMemoryRouter(MemoryRouter):`, add import.

2.2. Call `super().__init__()` or override `__init__` to skip real work.

2.3. **Verification**:
```
mypy tests/test_resource_manager.py --ignore-missing-imports 2>&1 | grep "MockMemoryRouter" | wc -l
```
Expected: 0 (was 19). Paste literal output.
```
python -m pytest tests/test_resource_manager.py -v
```
Expected: all pass. Paste `Select-Object -Last 5`.

### Step 3 — Fix MockMemoryRouter in tests/test_task_state_machine.py (17 errors)

Same pattern as Step 2.

3.1. Change class declaration, add import, fix `__init__`.

3.2. **Verification**: `mypy tests/test_task_state_machine.py --ignore-missing-imports 2>&1 | grep "MockMemoryRouter" | wc -l` — expected: 0 (was 17). `python -m pytest tests/test_task_state_machine.py -v` — all pass. Paste outputs.

### Step 4 — Fix MockMemoryRouter in tests/test_model_acquisition.py (13 errors)

Same pattern.

4.1. Change class, add import, fix `__init__`.

4.2. **Verification**: `mypy tests/test_model_acquisition.py --ignore-missing-imports 2>&1 | grep "MockMemoryRouter" | wc -l` — expected: 0 (was 13). `python -m pytest tests/test_model_acquisition.py -v` — all pass. Paste outputs.

### Step 5 — Fix MockMemoryRouter in tests/test_ollama_worker.py (12 errors)

Same pattern.

5.1. Change class, add import, fix `__init__`.

5.2. **Verification**: `mypy tests/test_ollama_worker.py --ignore-missing-imports 2>&1 | grep "MockMemoryRouter" | wc -l` — expected: 0 (was 12). `python -m pytest tests/test_ollama_worker.py -v` — all pass. Paste outputs.

### Step 6 — Fix MockMemoryRouter in tests/test_model_registry.py, tests/test_scratchpad.py, tests/test_system_profiler.py (11 + 10 + 8 = 29 errors)

6.1. For each of the 3 files: change class, add import, fix `__init__`.

6.2. **Verification** (all 3 together):
```
mypy tests/test_model_registry.py tests/test_scratchpad.py tests/test_system_profiler.py --ignore-missing-imports 2>&1 | grep "MockMemoryRouter" | wc -l
```
Expected: 0 (was 29). Paste literal output.
```
python -m pytest tests/test_model_registry.py tests/test_scratchpad.py tests/test_system_profiler.py -v
```
Expected: all pass. Paste `Select-Object -Last 5`.

### Step 7 — Verify total mypy error reduction

7.1. **Verification**:
```
mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "MockMemoryRouter\|MockStateMachine" | wc -l
```
Expected: 0 (was 122 per Step 0.3). Paste literal output AND the count comparison.

```
mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep -c "error:"
```
Expected: (Step 0.5 baseline - 122). Paste literal output AND the count comparison. **If the reduction is less than 122**, STOP — investigate (some mocks may have additional errors, or inheritance introduced new errors from the real class's `__init__`).

```
python -m pytest tests/ -q --tb=no | Select-Object -Last 3
```
Expected: 1167 passed, 55 skipped, 0 failed (Windows) — unchanged from baseline. On Linux: ~1087 passed, 1 skipped, 2 pre-existing failures — unchanged. If a NEW failure appears, STOP — the inheritance change broke a test. Fix it (don't skip — landmine L3).

## Verification gates (run in order, all must pass)

1. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep "MockMemoryRouter\|MockStateMachine" | wc -l` — expected: 0 (was 122). Paste literal output.
2. `mypy . --ignore-missing-imports --explicit-package-bases 2>&1 | grep -c "error:"` — expected: (Step 0.5 baseline - 122). Paste literal output + count comparison.
3. `ruff check tests/test_approval_gate.py tests/test_resource_manager.py tests/test_task_state_machine.py tests/test_model_acquisition.py tests/test_ollama_worker.py tests/test_model_registry.py tests/test_scratchpad.py tests/test_system_profiler.py` — expected: 0 errors. Paste literal output.
4. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: baseline unchanged (1167/55/0 on Windows). Paste literal output.
5. Manual smoke:
   ```python
   python -c "
   from tests.test_approval_gate import MockMemoryRouter, MockStateMachine
   from core.memory_router import MemoryRouter
   from core.task_state_machine import TaskStateMachine
   print('MockMemoryRouter is MemoryRouter subclass:', issubclass(MockMemoryRouter, MemoryRouter))
   print('MockStateMachine is TaskStateMachine subclass:', issubclass(MockStateMachine, TaskStateMachine))
   "
   ```
   Expected: both `True`. Paste literal output.

## STOP conditions

- **S0**: If Step 0.1 reveals HEAD is not a descendant of prompt-49b, STOP.
- **S1**: If Step 0.2 shows prompt-49b tag absent from origin, STOP (landmine L5).
- **S2**: If Step 0.3 reveals 0 mock inheritance errors (someone already fixed them), STOP — plan has nothing to do.
- **S3**: If Step 0.6 reveals test baseline has drifted significantly from 1167/55/0, STOP — baseline drift.
- **S4**: If Step 1.6 reveals that `MemoryRouter.__init__` or `TaskStateMachine.__init__` does real I/O (creates tables, connects to Postgres/Qdrant) that can't be safely called in a mock, STOP — the inheritance approach won't work. **This STOP applies to ALL 8 in-scope files** — if `MemoryRouter.__init__` does real I/O, the inheritance approach fails for the entire plan, not just Step 1. Stop after Step 1.6's check; do not proceed to Steps 2-6. Alternative: use `typing.Protocol` instead (define a `MemoryRouterProtocol` with the methods the mocks implement, and type-hint the constructors to accept `MemoryRouterProtocol` instead of `MemoryRouter`). This is a bigger change — report and let the user decide.
- **S5**: If any per-step verification reveals a test failure due to the inheritance change, fix the test (don't skip — landmine L3). If fixing requires >50 lines, STOP (S10).
- **S6**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 8 in-scope files are listed in "Current state" above. The 3 additional files with MockMemoryRouter (test_approval_trust, test_model_evaluator, test_worker_factory) are NOT in scope — leave them alone.
- **S7**: If Step 7.1's mypy reduction is less than 122, STOP — investigate.
- **S8**: If Gate 4 shows MORE failures than the prompt-49b baseline, STOP. Do not tag.
- **S9**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S10**: If any single step requires >50 lines of new code, STOP — underscoped. (Note: each mock class fix is ~5-10 lines. 8 files × ~10 lines = ~80 lines total, but split across 7 steps. Each step is well under 50 lines. **Step 6 covers 3 files × ~10 lines = ~30 lines total — still under the 50-line limit. S10 does not apply to Step 6.**)
- **S11**: If any closing step (C1-C11 below) is marked DONE without literal output, STOP (landmine L2 / Rule 19).
- **S12**: If C5 reveals a file outside the in-scope list, STOP — delete tag, unstage, re-tag.
- **S13**: If C11 tag-push fails verification (L17 — the prompt-49b issue), STOP — retry the push. If retry fails, report to user. Do NOT claim the plan is complete without `git ls-remote --tags origin | findstr prompt-50` returning the tag.

## Closing steps (mandatory, every prompt — Rule 21)

**ALL closing steps C1-C11 are MANDATORY. A plan is NOT complete until C11 passes (Rule 21, L17). Use the temp-file CHANGELOG pattern (L15) for ALL entries >20 lines.**

**C1** — Run full test suite: `python -m pytest tests/ -v`. Confirm zero new failures. Paste `Select-Object -Last 5`.

**C2** — Ruff on all 8 in-scope files: `ruff check tests/test_approval_gate.py tests/test_resource_manager.py tests/test_task_state_machine.py tests/test_model_acquisition.py tests/test_ollama_worker.py tests/test_model_registry.py tests/test_scratchpad.py tests/test_system_profiler.py`. Expected: 0 errors. Paste literal output.

**C3** — Mypy full scan: `mypy . --ignore-missing-imports --explicit-package-bases`. Expected: (Step 0.5 baseline - 122) errors. Paste literal output + count comparison.

**C4** — Commit and tag:
```
git add tests/test_approval_gate.py tests/test_resource_manager.py tests/test_task_state_machine.py tests/test_model_acquisition.py tests/test_ollama_worker.py tests/test_model_registry.py tests/test_scratchpad.py tests/test_system_profiler.py
git commit -m "checkpoint: prompt-50"
git tag prompt-50
```
Verify: `git log -1 --oneline` + `git tag --list prompt-50`. Paste literal output.

**C5** — Verify file list: `git show prompt-50 --stat`. Expected: ONLY the 8 in-scope test files (plus CHANGELOG + handoff in the docs commit). If unexpected file, delete tag, unstage, re-tag. Paste literal output.

**C6** — Update `CHANGELOG.md` (per-step entries, temp-file pattern for >20 lines). Each entry: date/time, step ref, what was done, files modified, testing results, gate output.

**C7** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 50 from "Next 5 prompts" to "Completed prompts": `| 50 | MockMemoryRouter/MockStateMachine inheritance fix | 1167 | 122 mypy errors eliminated across 8 test files. Test-only, no production code changes. |`
- Update "Static analysis baseline" — mypy: (Step 0.5 baseline - 122) errors remaining.
- **Refill the "Next 5 prompts" queue**: Plan 51 (adapter type fixes + del e, P2), Plan 52 (F4 wiring, P1), Plan 53 (test suite health + B108 + calendar fix, P2), Plan 54 (F401 bulk cleanup, P3), Plan 55 (marine stack, P2).
- Update "Last updated" header.

**C8** — Update `SOVEREIGN_AI_HANDOFF.md` IF a new landmine was identified. Candidate: "mock classes that don't inherit from the real class cause mypy errors — always inherit or use Protocol." If no new pattern, skip with documented reason. (Do NOT update `global_rules.md` — landmine L1.)

**C9** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-50 changelog and handoff update"
```
Verify with `git log -1 --oneline` + `git show HEAD --stat`. Paste literal output.

**C10** — Push:
```
git push origin master
git push origin prompt-50
```
**Tag-push gate (L5, L17, Rule 21 — MANDATORY)**: after pushing, verify:
```
git ls-remote --tags origin | findstr prompt-50
```
Expected: a line containing `prompt-50`. If empty, retry the push. If retry fails, report to user; do NOT mark Plan 50 complete. Paste literal output.

**C11** — Verify tag on origin: paste literal output of `git ls-remote --tags origin | findstr prompt-50`. **If this output is empty, the plan is NOT complete (Rule 21, L17).**

## CHANGELOG append procedure (PowerShell — L15 temp-file pattern)

Per handoff lines 324-350. For entries >20 lines, use temp-file pattern. The closing `"@` MUST be at column 1.

## Out of scope

- **Adapter type fixes** (14 `tokens_used: float vs int` + 13 `del e` = 27 errors) — Plan 51.
- **F4 wiring** (cognition loop into serve request path) — Plan 52.
- **Test suite health** (calendar test failure, B108 in tests, datetime.utcnow deprecation) — Plan 53.
- **F401 bulk cleanup** (246 unused imports) — Plan 54.
- **Marine stack** — Plan 55.
- **Dependency updates** — Plan 56.
- **Dead code cleanup** — Plan 57.
- **Production code changes** — Plan 50 is test-only. If a mock can't inherit from the real class because the real class does I/O in `__init__` (S4), STOP — do not modify the production class to make the mock work. Use `Protocol` instead (but that requires changing production constructors, which is out of scope — report and let the user decide).
- **The 3 additional test files with MockMemoryRouter** (test_approval_trust, test_model_evaluator, test_worker_factory) — they have 0 mypy errors, so they're not in scope. Leave them alone.
- **Consolidating MockMemoryRouter into a shared test fixture** (e.g., `tests/conftest.py`) — good idea but out of scope. Each test file currently has its own mock. A future plan could consolidate, but Plan 50 only fixes the inheritance to clear mypy errors.

## For Claude review (Devin: do not execute)

1. **Inheritance vs Protocol**: the plan uses inheritance (`class MockMemoryRouter(MemoryRouter)`) as the primary fix. If `MemoryRouter.__init__` does real I/O (S4), the plan falls back to `Protocol`. Is this the right approach, or should the plan use `Protocol` from the start (more flexible, no `super().__init__()` issues, but requires changing production constructors)?

2. **S4 fallback**: if `MemoryRouter.__init__` creates Postgres tables or connects to Qdrant, calling `super().__init__()` in a mock will fail. The plan says "override `__init__` to skip that work". Is this clear enough, or should the plan investigate `MemoryRouter.__init__` upfront and dictate the exact override pattern?

3. **3 additional test files excluded**: test_approval_trust, test_model_evaluator, test_worker_factory have `MockMemoryRouter` but 0 mypy errors. The plan excludes them. Is this correct, or should they be fixed proactively (in case a future change starts passing their mocks to type-checked constructors)?

4. **MockStateMachine only in test_approval_gate.py**: only 1 file has `MockStateMachine`. The plan fixes it in Step 1. Is this the right scope, or should the plan check if other test files have similar state machine mocks under different names?

5. **Rule 21 enforcement**: C10/C11 now explicitly reference Rule 21 and L17 (the prompt-49b tag-push failure). Is the enforcement text strong enough to prevent recurrence?
