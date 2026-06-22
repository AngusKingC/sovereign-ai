# Plan 37.1: Fix prompt-37 test regressions and codify Rule 18 (tests change with code)

> **Executor instructions**: Small, focused follow-up to prompt-37. Two mandates: (1) fix the 69 test failures that prompt-37 left behind, (2) add a new architecture rule to the handoff that prevents this from recurring. Run gates after each step. If the test count math doesn't reconcile at Gate 5, STOP.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-37..HEAD -- core/memory_router.py tests/test_memory_router.py tests/test_rating_system.py tests/test_orchestrator_improvement.py tests/test_instruction_versioning.py tests/test_trace_optimiser.py tests/test_worker_persistence.py tests/test_instruction_generator.py tests/test_evaluator.py tests/test_scratchpad.py tests/test_model_registry.py tests/test_resource_manager.py tests/test_system_profiler.py SOVEREIGN_AI_HANDOFF.md
> ```
> If any of these files changed since prompt-37, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P0 (blocks Plan 38 — the test suite is red)
- **Effort**: S
- **Risk**: LOW (mechanical test updates + 1 line of production code + 2 documentation sections)
- **Depends on**: prompt-37 (commit `9272bd7`)
- **Planned at**: commit `41dab92`, 2026-06-18
- **In scope**: 11 test files, 1 production file (return-type annotation only), 2 documentation files (handoff + global_rules)
- **Out of scope**: scoped_read/scoped_write (Plan 37.5), trajectory_exporter.py pattern (Plan 37.5), escalation.py:146 fix (Plan 37.5), broad-except audit (Plan 38+)

## Why this matters

Prompt-37 changed the MemoryRouter interface (added `fetch_by_filter`, `write_to_collection`, `get_global_context`, `set_global_context`) and updated 12 production files to call the new methods. The corresponding test files were not updated to match — 67 stale references to `mock_memory_router.fetch.return_value` and `mock_memory_router.write.call_args` remain across 8 test files, plus 3 test files have their own custom `MockMemoryRouter` classes that lack the new methods entirely. Result: 69 test failures, baseline regression from 1072 → 1010 passed.

This is the documented recurring mistake #1 (spec deviation without documentation) in a new guise: the spec was "update callers and their tests together," and the test half was silently skipped. Plan 37's own Gate 5 should have blocked the tag, but Devin tagged and pushed anyway. Plan 37.1 fixes the regression and codifies a new rule (Rule 18: tests change with code) so the next prompt cannot ship with the same gap.

## What's broken (verified against live repo)

### A. Stale mock references in 8 test files (67 occurrences total)

Production code now calls `fetch_by_filter` / `write_to_collection`. Tests still configure `mock_memory_router.fetch.return_value = [...]` and assert `mock_memory_router.write.call_count`. The mock's `fetch_by_filter` returns `[]` (default), so production code sees empty data, and every assertion fails.

| File | Stale refs | Fix shape |
|---|---|---|
| `tests/test_rating_system.py` | 13 | `fetch.return_value` → `fetch_by_filter.return_value`; `write.call_args` → `write_to_collection.call_args` |
| `tests/test_orchestrator_improvement.py` | 11 | Same pattern |
| `tests/test_worker_persistence.py` | 18 | Same pattern |
| `tests/test_trace_optimiser.py` | 11 | Same pattern |
| `tests/test_instruction_generator.py` | 7 | Same pattern |
| `tests/test_instruction_versioning.py` | 4 | Same pattern |
| `tests/test_evaluator.py` | 3 | Same pattern |
| `tests/test_model_registry.py` | 0 stale refs, but mock lacks `fetch_by_filter` | Add method to mock |

**Note on `test_model_registry.py`**: the file uses a custom `MockMemoryRouter` class (not `Mock()` + `AsyncMock()`), and that class's `fetch` method signature is `fetch(task_id, query)` — Pattern 3 from Plan 37's mapping table. The mock class needs `fetch_by_filter` added with the correct return shape.

### B. Custom `MockMemoryRouter` classes missing the new methods (3 files)

These files don't use the `Mock()` + `AsyncMock()` pattern — they define their own `MockMemoryRouter` class with hardcoded method signatures. Prompt-37 updated some of these but not all.

| File | Current method surface | Missing |
|---|---|---|
| `tests/test_resource_manager.py` | `write(data)`, `fetch(task_id, query)` | `fetch_by_filter`, `write_to_collection` (production code in `system/resource_manager.py` now calls these) |
| `tests/test_system_profiler.py` | `write(data)` only | `fetch_by_filter`, `write_to_collection` (production code calls these for profile persistence) |
| `tests/test_model_registry.py` | `write(data)`, `fetch(task_id, query)` | `fetch_by_filter`, `write_to_collection` |

### C. `MockMemoryBackend` in `test_memory_router.py` doesn't round-trip (1 failure)

`tests/test_memory_router.py:20-32`:
```python
class MockMemoryBackend(MemoryBackend):
    def __init__(self):
        self.storage: list[dict[str, Any]] = []
    async def fetch(self, task: Task) -> list[dict[str, Any]]:
        return [{"content": f"Memory for {task.intent}", "source": "mock"}]  # ← IGNORES storage
    async def write(self, data: dict[str, Any]) -> None:
        self.storage.append(data)
```

`set_global_context` → `write_to_collection` → `backend.write(data)` → `storage.append(data)`. Then `get_global_context` → `fetch_by_filter` → `backend.fetch(task)` returns the **hardcoded** mock data, not what was just written. The round-trip test `test_set_and_get_global_context` (line 269) correctly fails. This test is doing its job — the mock is wrong.

### D. `get_global_context` return type is `Any` (Rule 9 violation)

`core/memory_router.py:516`:
```python
async def get_global_context(self, caller_id: str = "orchestrator") -> Any:
```

Architecture Rule 9 requires return type annotations on all public methods. `Any` is not a meaningful annotation. Should be `StrategicContext | None`.

### E. CHANGELOG test count math doesn't reconcile (Rule 18 violation, the existing one)

Prompt-37 CHANGELOG says:
- Baseline: 1072 passed, 23 skipped, 1 failed, 63 warnings
- Final: 1010 passed, 23 skipped, 1 failed, 67 warnings (69 new failures)

Arithmetic check: 1072 + 6 new tests = 1078 expected. 1078 − 69 failures = 1009, not 1010. Off by 1. Either a test was deleted, a test was skipped into non-collection, or the count was miscounted. Plan 37.1 must reconcile this in the CHANGELOG after Gate 5 produces the real final count.

### F. No architecture rule currently prevents this from recurring

The handoff's "Architecture rules" section ends at Rule 17. There is no rule that says "when you change a production interface, you must update its tests in the same prompt, and the test suite must pass before tagging." This needs to be added as Rule 18.

The handoff's "Recurring mistake patterns" section has 4 patterns. A 5th needs to be added: "Tagging with a red test suite."

## What to change

### Step 1 — Fix `MockMemoryBackend` round-trip (unblocks round-trip test)

**File**: `tests/test_memory_router.py`
**Lines**: 26-28 (the `fetch` method body)

Change:
```python
async def fetch(self, task: Task) -> list[dict[str, Any]]:
    """Fetch memory - returns mock data."""
    return [{"content": f"Memory for {task.intent}", "source": "mock"}]
```

To:
```python
async def fetch(self, task: Task) -> list[dict[str, Any]]:
    """Fetch memory - returns from storage (round-trippable)."""
    return list(self.storage)
```

**Why**: The hardcoded return value meant `get_global_context` could never retrieve what `set_global_context` wrote, because `fetch_by_filter` delegates to `backend.fetch()`. Returning from `self.storage` makes the mock actually round-trip.

**Side effect**: Other tests in `test_memory_router.py` that depended on the old hardcoded `{"content": "Memory for ..."}` shape may break. Check each: if a test asserted against that exact shape, update the assertion to match what the test wrote via `backend.write(...)`. Do NOT just revert the mock — the test was asserting against mock infrastructure, not behaviour (recurring mistake #2).

**Verify after this step**: `python -m pytest tests/test_memory_router.py -v --tb=short` — all 18 tests should pass.

### Step 2 — Update 8 test files with stale mock references (the bulk of the work)

For each of these 8 files, in this order (smallest to largest — get quick wins first to build confidence):

1. `tests/test_evaluator.py` (3 stale refs)
2. `tests/test_instruction_versioning.py` (4 stale refs)
3. `tests/test_instruction_generator.py` (7 stale refs)
4. `tests/test_rating_system.py` (13 stale refs)
5. `tests/test_orchestrator_improvement.py` (11 stale refs)
6. `tests/test_trace_optimiser.py` (11 stale refs)
7. `tests/test_model_registry.py` (0 stale refs but mock needs new method)
8. `tests/test_worker_persistence.py` (18 stale refs)

**For each file, the mechanical fix is**:

- Find every `mock_memory_router.fetch.return_value = X` → replace with `mock_memory_router.fetch_by_filter.return_value = X`
- Find every `mock_memory_router.fetch.call_args` / `.call_count` → replace with `mock_memory_router.fetch_by_filter.call_args` / `.call_count`
- Find every `mock_memory_router.write.call_args` / `.call_count` / `.call_args_list` → replace with `mock_memory_router.write_to_collection.call_args` / `.call_count` / `.call_args_list`
- The data structures the tests were using for `fetch.return_value` (lists of dicts with `"content"` keys, etc.) should still work — `fetch_by_filter` returns `list[dict[str, Any]]` same as `fetch` did. Do NOT change the data structures unless a test fails for a real reason.

**After each file**: `python -m pytest tests/<that_file>.py -v --tb=short` — all tests in that file should pass. Do not move to the next file until this is green.

**STOP condition for Step 2**: If a test fails after the mechanical fix AND the failure is not about mock return values (e.g. it's about production logic, a schema mismatch, or a real bug in the production code), STOP. Note the failure in the CHANGELOG under "Implementation Notes" and skip that test with an `xfail` marker and a comment explaining why. Do NOT silently delete the test.

### Step 3 — Update 3 custom `MockMemoryRouter` classes

For each of these 3 files, the production code now calls `fetch_by_filter` and/or `write_to_collection`, but the test's custom `MockMemoryRouter` class doesn't define them. Production code raises `AttributeError` when it tries to call the missing method, swallowed by broad excepts, tests fail.

1. **`tests/test_resource_manager.py`** — `MockMemoryRouter` class at line ~27. Add:
   ```python
   async def fetch_by_filter(self, filter: dict, collection: str | None = None, limit: int | None = None, filter_func=None) -> list:
       return []
   async def write_to_collection(self, data: dict, collection: str, document_id: str | None = None) -> None:
       self.writes.append({"data": data, "collection": collection, "document_id": document_id})
   ```
   Then check each test that calls production code which now uses `fetch_by_filter` — set `fetch_by_filter.return_value` (or the equivalent on the custom class — assign to a method) to realistic data the test expects.

2. **`tests/test_system_profiler.py`** — Same pattern. The mock only has `write(data)`. Add `fetch_by_filter` returning `[]` and `write_to_collection` appending to a list. Look at the failing tests (`test_trace_events_emitted_during_profiling`, `test_all_detection_failures_caught_no_exceptions`, `test_refresh_redetects_profile`) — they probably need `fetch_by_filter.return_value` to return a cached profile when the test is checking the cache path.

3. **`tests/test_model_registry.py`** — Same pattern. The mock has `fetch(task_id, query)` (Pattern 3 — old signature). Production code now calls `fetch_by_filter`. Add the new method, then update test assertions.

**After each file**: `python -m pytest tests/<that_file>.py -v --tb=short` — green.

### Step 4 — Fix `get_global_context` return type

**File**: `core/memory_router.py`
**Line**: 516

Change:
```python
async def get_global_context(self, caller_id: str = "orchestrator") -> Any:
```

To:
```python
async def get_global_context(self, caller_id: str = "orchestrator") -> "StrategicContext | None":
```

The `StrategicContext` import is already inside the method body (line 526: `from core.schemas import StrategicContext`). Move it to the top of the file under `TYPE_CHECKING` if not already there, or keep the string annotation as above to avoid circular imports.

Also update the docstring on lines 518-525 to say `StrategicContext if set, None otherwise.` (it already says this — just verify it matches).

**Why**: Architecture Rule 9 requires return type annotations. `Any` is not a meaningful annotation. This was flagged in Claude's review of the original Plan 37 draft and was not applied.

**Verify after this step**: `mypy core/memory_router.py --ignore-missing-imports` — no new errors on line 516.

### Step 5 — Add Rule 18 to the handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`
**Location**: End of the "Architecture rules (never violate)" section, after Rule 17.

Add:

```
18. **When production code is modified, the corresponding test files MUST be updated in the same prompt.** This includes: (a) updating mocks when interface signatures change, (b) updating assertions when call sites change, (c) adding tests for new public methods. The full test suite MUST pass before tagging. If Gate 5 (full suite) shows a regression from baseline, STOP — do not tag, do not push. Tagging with a red test suite is forbidden. (Currently violated by prompt-37: 69 test failures tagged as "known issues" — Plan 37.1 fixes this.)
```

### Step 6 — Add recurring mistake pattern #5 to the handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`
**Location**: End of "Recurring mistake patterns" section, after pattern #4.

Add:

```
5. **Tagging with a red test suite.** When Gate 5 (full test suite) shows failures beyond the documented baseline, the prompt is not done. Do not tag, do not push, do not move to the next plan. Either fix the failures in the same prompt, or STOP and report. Prompt-37 was this — 69 test failures tagged as "known issues" with a hand-wave to "needs separate plan," when the failures were caused by the prompt's own incomplete test updates and should have been fixed in the same prompt. The cost of cleaning this up afterward (Plan 37.1) is higher than the cost of doing it right the first time.
```

### Step 7 — Add Rule 18 to `global_rules.md`

**File**: `C:\Users\King\.codeium\windsurf\memories\global_rules.md` (Windows path — Devin has this; reviewer does not)

Add a new rule in the "Testing" section, mirroring the handoff's Rule 18:

```
Rule 24: When production code is modified, the corresponding test files MUST be updated in the same prompt. Mocks must match the new interface. The full test suite MUST pass before tagging. If Gate 5 shows a regression, STOP — do not tag, do not push. Tagging with a red test suite is forbidden.
```

(Numbering: the rewrite from the prior conversation brought global_rules to 23 rules. This is rule 24.)

### Step 8 — Reconcile CHANGELOG test count math

**File**: `CHANGELOG.md`

After Gate 5 produces the real final test count, append a "Test count reconciliation" note to the prompt-37.1 entry:

```
### Test count reconciliation
- Prompt-37 reported: 1010 passed, 23 skipped, 1 failed (69 new failures from 1072 baseline)
- Arithmetic check: 1072 + 6 new tests − 69 failures = 1009, but prompt-37 reported 1010. Off by 1.
- Prompt-37.1 actual final: <REAL_FINAL_COUNT> passed, <REAL_SKIPPED> skipped, <REAL_FAILED> failed.
- Reconciliation: <explanation of the off-by-1, e.g. "one test was reclassified from passed to skipped during the mock update" or "the prompt-37 count was miscounted">
```

Be honest. If the off-by-1 can't be explained, say so. Do not invent an explanation.

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-37..HEAD -- core/memory_router.py tests/ SOVEREIGN_AI_HANDOFF.md
```

**Expected**: empty output (no changes to these files since prompt-37).

### Gate 2 — `MockMemoryBackend` round-trip

```
python -m pytest tests/test_memory_router.py::TestMemoryRouter::test_set_and_get_global_context -v --tb=short
```

**Expected**: PASSED.

### Gate 3 — All 8 stale-mock test files green

```
python -m pytest tests/test_rating_system.py tests/test_orchestrator_improvement.py tests/test_worker_persistence.py tests/test_trace_optimiser.py tests/test_instruction_generator.py tests/test_instruction_versioning.py tests/test_evaluator.py tests/test_model_registry.py -v --tb=short
```

**Expected**: 0 failures.

### Gate 4 — All 3 custom-mock test files green

```
python -m pytest tests/test_resource_manager.py tests/test_system_profiler.py tests/test_model_registry.py -v --tb=short
```

**Expected**: 0 failures.

### Gate 5 — Full test suite (the gate prompt-37 should have enforced)

```
python -m pytest tests/ -q --tb=short
```

**Expected**: 
- Baseline (prompt-36.5): 1072 passed, 23 skipped, 1 failed (flaky), 63 warnings
- After prompt-37 + prompt-37.1: **1078 passed** (1072 + 6 new tests from prompt-37), 23 skipped, 1 failed (flaky), ~63 warnings
- Any other number is a regression. STOP and investigate.

**Note on the off-by-1**: If the count is 1077 instead of 1078, that's the prompt-37 off-by-1 surfacing — investigate which test was lost. If the count is 1076 or lower, a real regression was introduced; STOP.

### Gate 6 — Rule 18 in handoff

```
grep -c "^18\. " SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 1 (the new Rule 18).

### Gate 7 — Recurring mistake pattern #5 in handoff

```
grep -c "^5\. \*\*Tagging with a red test suite" SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 1.

### Gate 8 — Return type fix

```
grep "async def get_global_context" core/memory_router.py
```

**Expected**: a line containing `-> "StrategicContext | None":` (or `-> StrategicContext | None:` if the import was moved to module level).

### Gate 9 — mypy on the 1-line production change

```
mypy core/memory_router.py --ignore-missing-imports
```

**Expected**: no NEW errors compared to prompt-37's mypy output. The 40 pre-existing errors should be unchanged.

## STOP conditions

- **If Gate 2 fails** (round-trip test still fails after mock fix), STOP. The mock fix is wrong — investigate before proceeding.
- **If Gate 3 or Gate 4 has any failure that is NOT a mock return-value issue**, STOP. Real production bug found; report it.
- **If Gate 5 shows fewer than 1075 passed tests**, STOP. Regression introduced. Identify the failing test(s) and fix before proceeding.
- **If Gate 5 shows more than 1078 passed tests**, STOP. New tests were added that weren't accounted for. Document them in the CHANGELOG before proceeding.
- **If any file outside the in-scope list needs editing**, STOP. Report which file and why.

## Out of scope

- **`scoped_read` / `scoped_write` phantom methods** (called from `core/approval_trust.py`, `skills/reminder/reminder_skill.py`) — Plan 37.5
- **`trajectory_exporter.py` `fetch(Type, filter_func=...)` pattern** — Plan 37.5
- **`core/escalation.py:146` `ApprovalGate.request` → `request_approval`** — Plan 37.5
- **`core/retention.py` documentation justification** — Plan 37.5
- **Broad-except audit** — Plan 38+
- **InputSanitiser wiring** — Plan 41+
- **TUI memory + cognition stack wiring** — Plan 37.6 (separate from 37.5)

## Closing steps

1. `git add` the 11 test files + `core/memory_router.py` + `SOVEREIGN_AI_HANDOFF.md`
2. `git commit -m "fix: prompt-37.1 — update test mocks for new MemoryRouter interface, codify Rule 18"`
3. `git tag prompt-37.1`
4. `git show prompt-37.1 --stat` — verify file list. If unexpected file appears, `git tag -d prompt-37.1`, clean, re-tag.
5. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail (how many stale refs fixed in each, what new methods added to custom mocks)
   - **Implementation Notes**: any test that needed `xfail`, any unexpected behaviour discovered, the test count reconciliation
   - **Testing Results**: baseline (1010 passed from prompt-37) → final (expected 1078 passed)
   - **Verification Gate Output**: literal output of each gate
6. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-37.1
   - Update test baseline to the Gate 5 final count
   - Move F6 from "PARTIALLY FIXED" to "Recently fixed (prompt-37.1)" — F6 is now actually fixed for the 12 in-scope files (trajectory_exporter.py still open, called out separately)
   - Update "Built but not reachable" table: the 6 self-improvement subsystems + WorkerFactory + WorkerPersistence + TrajectoryExporter are now functionally correct (still not wired)
   - Add Rule 18 (Step 5) and recurring mistake pattern #5 (Step 6) — these are the codified learnings
7. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
8. `git commit -m "docs: prompt-37.1 changelog and handoff update"`
9. `git push origin master && git push origin prompt-37.1`
10. **Post-push verification**: `git ls-remote --tags origin | grep prompt-37.1` — verify the tag exists on the remote.
11. **Update `global_rules.md` locally** (Step 7) — this file is not in the repo; it's Devin's memory file. Add Rule 24 to the Testing section.

## After Plan 37.1 lands

The test suite is green. F6 is properly closed for the 12 in-scope files. Rule 18 is in place to prevent recurrence. The queue can now proceed to:

- **Plan 37.5** — `scoped_read`/`scoped_write` + `trajectory_exporter.py` pattern + `escalation.py:146` + Claude's 4 blocking fixes from the original Plan 37 review
- **Plan 37.6** — TUI memory + cognition stack wiring (mirror of 35.6f for `cli/tui.py`)
- **Plan 38** — F7 trace spam + `cli/__init__.py` (was Plan 38 before resequencing)
- **Plan 38.5** — Broad-except audit, part 1 (core/)
- **Plan 39** — Broad-except audit, part 2 (system/)
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45+** — graphify integration cluster

Plans 37.5 and 37.6 must land before Plan 38. The foundation (F6 fully closed, TUI wired) must be solid before horizontal cleanup work begins.
