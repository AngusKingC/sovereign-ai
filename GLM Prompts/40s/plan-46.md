# Plan 46: Clear F821 runtime crash bugs, F811 duplicate definitions, and critical F841 unused-variable lint errors

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first):
> `git diff --stat prompt-45..HEAD -- cli/command_history.py core/session.py core/schemas.py cli/tui.py core/escalation.py core/memory_router.py core/approval_gate.py system/trajectory_exporter.py workers/echo_worker.py adapters/anthropic.py adapters/cohere.py adapters/deepseek.py adapters/groq.py adapters/mistral.py adapters/openai.py adapters/together.py cli/serve.py`
> Also run (read-only drift on files Plan 44/45 touched):
> `git diff --stat prompt-45..HEAD -- cli/serve.py core/input_sanitiser.py tests/test_input_sanitiser.py`
> If any in-scope file changed since prompt-45, compare Current state
> excerpts against live code; on mismatch, STOP. If `cli/serve.py`
> changed, confirm the `input_sanitiser` kwarg is still passed to
> `Orchestrator(...)` — if not, STOP (Plan 44 wiring was reverted).
> If `system/trajectory_exporter.py` changed, confirm Plan 45's
> working fetch implementation is intact (no return to the dead-code
> stub) — if not, STOP (Plan 45 was reverted).

## Status
- Priority: P1
- Effort: L
- Risk: MED
- Depends on: prompt-45 (InputSanitiser redesigned + trajectory_exporter functional)
- Planned at: commit prompt-45, 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft per 2026-06-20 audit section 7 Plan 46 scope, with adjustments for Plan 45's completion (audit item 8 trajectory_exporter dead code is now done; verify in Step 0).
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-3 (broken S11 cross-reference in Step 0.9/S6; Step 1 "two fixes" header vs three actual sub-steps + 1.3 not being a crash bug; "17 files" count incorrectly including verify-only trajectory_exporter.py).
- Revision: REV3 (2026-06-20) — incorporates S2 STOP fire + re-baseline. Actual F821 count is 25 (not 26 as audit claimed). Drift source: 2 new TYPE_CHECKING-only `InputSanitiser` F821s in `core/handlers.py:31,437`, introduced by prompt-44's InputSanitiser wiring work. These are NOT runtime crashes and are deferred to Plan 47/48 alongside existing TYPE_CHECKING-only F821s. Audit's count of 26 was pre-Plan-45 (which removed 3 from trajectory_exporter.py); expected post-Plan-45 was 23; actual is 25 due to prompt-44's +2. Step 0.3 expected count updated 26→25. STOP S2 threshold updated 26→25. Out of scope section updated to enumerate the 2 new InputSanitiser F821s explicitly. Line-number drift in `core/orchestrator.py` (audit 44/721 → actual 46/725) and `core/handlers.py` (audit 28/428 → actual 29/435) noted but does not affect Plan 46 (those files are out of scope).

## Why this matters

The 2026-06-20 audit found 26 F821 undefined-name occurrences across 24 lines. Of these, 10 name-occurrences across 9 line-occurrences in 6 files are RUNTIME CRASH bugs — code that will raise `NameError` the moment the relevant code path executes. Two of these are HIGH severity: `cli/command_history.py:97` (uuid4 missing — crashes when `add_command()` creates a Task) and `core/session.py:237,280` (Task missing — crashes when session resume paths are reached). The remaining F821s are TYPE_CHECKING-only (string annotations not evaluated at runtime) and are not crash bugs, but they generate mypy errors that block Plan 47/48 cleanup. Additionally, 8 F811 redefined-while-unused errors include one real bug (`core/schemas.py` defines `Scratchpad` twice — the second definition silently shadows the first). The 81 F841 unused-variable errors include several that hide real bugs (e.g., `core/approval_gate.py` swallows exceptions into `emit_error` without logging). CI will never pass until these are cleared, and the runtime crash bugs are a P1 landmine: any user hitting the affected code path gets an unhandled `NameError` with no audit trail.

## Current state

**Files in scope (Plan 46 may edit only these — 16 files; plus 1 verify-only file listed separately):**
- `cli/command_history.py` — F821: `uuid4` not imported (line 97). HIGH severity runtime crash.
- `core/session.py` — F821: `Task` not imported at module level (lines 237, 280). HIGH severity runtime crash.
- `core/schemas.py` — F811: duplicate `Scratchpad` class (lines 504 and 600). Real bug — second definition silently shadows the first.
- `cli/tui.py` — F811: `CommandHistory` imported twice (line 53). Also in scope for Plan 45 drift check.
- `core/escalation.py` — F811: `TraceEventType` re-imported 3 times inside functions (lines 60, 130, 185).
- `core/memory_router.py` — F811: `datetime`, `uuid4` re-imported inside methods (lines 391-392). Plan 45 added `fetch_by_type()` here — verify it doesn't add new re-imports.
- `core/approval_gate.py` — F841: `emit_error` assigned but never used (5 occurrences). Per audit section 1: "should use `logger.warning(str(emit_error))` per Rule 17". Rule 17 violation — swallowed exceptions.
- `system/trajectory_exporter.py` — **VERIFY-ONLY** (not editable). F821: dead code after `return 0` (lines 88, 96, 100). **Already addressed by Plan 45 Step 4.3 — verify in Step 0.8.** Editing this file triggers STOP S5 (landmine L6: re-fixing disproved hypothesis).
- `workers/echo_worker.py` — F821: `core` undefined (line 69). String annotation used as type hint — works at runtime via string eval, but is incorrect (NOT a crash bug — see Step 1.3 for clarification).
- `adapters/anthropic.py`, `adapters/cohere.py`, `adapters/deepseek.py`, `adapters/groq.py`, `adapters/mistral.py`, `adapters/openai.py`, `adapters/together.py` — F841: `response` assigned but never used in health check (1 occurrence each, 7 total). Per audit: "Should prefix with `_` or just `await` without assignment."
- `cli/serve.py` — F841: `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory` constructed but never used. Plan 44 added `input_sanitiser` kwarg to Orchestrator constructor here — verify it's still present.

**Step 0 — verify current state (do this before any edits; paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA at plan-start. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-45` — confirm prompt-45 tag is on origin. If absent, STOP (prior prompt's tag-push gate was skipped per landmine L5).

0.3. `ruff check . --select F821` — capture full output. **Expected: 25 errors (REV3 re-baseline — was 26 in audit, but Plan 45 removed 3 from trajectory_exporter.py and prompt-44 added 2 new TYPE_CHECKING-only `InputSanitiser` F821s in `core/handlers.py:31,437`; net = 26 - 3 + 2 = 25)**. Paste full output to CHANGELOG. **Count the F821 errors by file** and paste the per-file count to CHANGELOG. Expected per-file counts (post-Plan-45, post-prompt-44):
  - `system/model_acquisition.py`: 6
  - `core/handlers.py`: 4 (2 `Orchestrator` at lines 29, 435 + 2 `InputSanitiser` at lines 31, 437 — the InputSanitiser occurrences are NEW, introduced by prompt-44, deferred to Plan 47/48)
  - `core/orchestrator.py`: 3 (`A2ARouter` at line 46, `A2ARequest` + `A2AResponse` at line 725 — note line drift from audit's 44/721)
  - `system/resource_manager.py`: 2
  - `core/session.py`: 2
  - `core/worker_factory.py`: 2
  - `workers/echo_worker.py`: 1
  - `core/notification.py`: 1
  - `core/escalation.py`: 1
  - `core/retention.py`: 1
  - `core/worker_base.py`: 1
  - `cli/command_history.py`: 1
  - Total: **25**

  If the total is not 25, OR any in-scope file's count differs from above, STOP — baseline has drifted further since REV3; the plan's "What to change" steps may be stale. Note: line numbers in `core/orchestrator.py` and `core/handlers.py` have drifted from the audit (prompt-44/45 added lines above); use the ACTUAL line numbers from this Step 0.3 output, not the audit table's stale numbers. The 3 in-scope runtime-crash files (`cli/command_history.py:97`, `core/session.py:237,280`, `workers/echo_worker.py:69`) have NOT drifted — verify those line numbers match exactly before proceeding to Step 1.

0.4. `ruff check . --select F811` — capture full output. Expected: 8 errors (per audit section 1). Paste full output to CHANGELOG. Verify the 8 errors match the audit's F811 list: `core/schemas.py:600` (Scratchpad), `cli/tui.py:53` (CommandHistory), `core/escalation.py:60,130,185` (TraceEventType ×3), `core/memory_router.py:391,392` (datetime, uuid4). If any error is missing or extra, STOP — baseline drift.

0.5. `ruff check . --select F841` — capture full output. Expected: 81 errors (per audit section 1). Paste `Select-Object -Last 5` of the count summary to CHANGELOG. Plan 46 only fixes the CRITICAL F841s (`core/approval_gate.py` 5 occurrences, 7 adapter health checks, `cli/serve.py` 4 unused subsystem variables). The remaining F841s are out of scope (deferred to Plan 50).

0.6. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — capture baseline test count. Must match prompt-45 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If it does not match, STOP — baseline has drifted since prompt-45 and the plan's Gate 4 baseline is wrong.

0.7. `Get-Content core/schemas.py | Select-Object -Skip 500 -First 120` — paste lines 501-620 to CHANGELOG. Confirm: `Scratchpad` class is defined twice (around line 504 and around line 600). The second definition (line 600) has the `is_compacted` field; the first (line 504) does not. Per audit section 6a: "Remove the first definition, keep the second."

0.8. `ruff check system/trajectory_exporter.py --select F821` — capture output. Expected: 0 errors (Plan 45 Step 4.3 already removed the dead code). If errors are present, Plan 45 did NOT complete its scope — STOP and report. Do NOT re-fix trajectory_exporter in Plan 46; that's Plan 45's job.

0.9. `Select-String -Path cli/serve.py -Pattern "input_sanitiser"` — confirm Plan 44's InputSanitiser wiring is intact. Expected: at least 1 match. If 0 matches, STOP — Plan 44 wiring was reverted; the precondition for Step 5 (which edits the same `serve()` function) is not met.

0.10. `Select-String -Path core/memory_router.py -Pattern "def fetch_by_type"` — confirm Plan 45's `fetch_by_type` method is present. Expected: 1 match. If 0 matches, STOP — Plan 45 was reverted.

0.11. `Get-Content core/approval_gate.py | Select-String -Pattern "emit_error" -Context 0,2` — paste output to CHANGELOG. Confirm: 5 occurrences where `emit_error` is assigned (likely `except Exception as emit_error:`) but never used. Per audit: "should use `logger.warning(str(emit_error))` per Rule 17."

0.12. For each of the 7 adapter files, run `Get-Content adapters/<name>.py | Select-String -Pattern "response = await client" -Context 0,1` — paste all 7 outputs to CHANGELOG. Confirm: each adapter has 1 occurrence of `response = await client.create(...)` where `response` is never subsequently read.

If any of these do not match the description above, STOP — the plan was written against stale state.

**Repo conventions (Architecture Rules, handoff lines 437-460):**
- `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/` (Rule 1).
- `workers/` may import from `core/` and `adapters/` but never from `cli/` (Rule 2).
- `adapters/` may import from `core/` only (Rule 4).
- `cli/` may import from anywhere (Rule 8).
- No broad `except Exception: pass` without inline comment + WARNING trace (Rule 17). `core/approval_gate.py`'s `emit_error` swallowing is a Rule 17 violation — Plan 46 fixes it.
- All public functions have return type annotations (Rule 9).
- Exemplar for Rule 17 fix pattern: see `core/approval_gate.py` itself (other broad-except patterns in this file were fixed in prompt-41).

## What to change

### Step 1 — Fix F821 undefined-name bugs (P1)

These three fixes address F821 undefined-name errors. Steps 1.1 and 1.2 are HIGH-severity runtime crash bugs (will raise `NameError` if the code path executes). Step 1.3 is a correctness issue, not a crash — string annotations are not evaluated at runtime, so `"core.memory_router.MemoryRouter"` works via string eval, but it is incorrect and generates a ruff F821 + mypy error. All three are in scope for Plan 46 because they share the same ruff selector (F821) and the same fix pattern (add or fix the import).

1.1. **`cli/command_history.py:97`** — fix missing `uuid4` import. The file currently has `from uuid import UUID` but uses `uuid4()` on line 97 when constructing a Task. Edit the import line to `from uuid import UUID, uuid4`. **Verification**:
```
ruff check cli/command_history.py --select F821
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
python -c "from cli.command_history import CommandHistory; ch = CommandHistory(); print('OK')"
```
Expected: `OK` (no ImportError). Paste literal output to CHANGELOG.

1.2. **`core/session.py:237, 280`** — fix missing `Task` import at module level. The file currently imports `Task` inside a function (line ~230) but uses it outside that function's scope (lines 237, 280). Move `from core.schemas import Task` to the module-level imports at the top of the file. Remove the function-level import. **Verification**:
```
ruff check core/session.py --select F821
```
Expected: 0 errors (was 2 before). Paste literal output to CHANGELOG.
```
python -c "from core.session import Session; print('OK')"
```
Expected: `OK`. Paste literal output to CHANGELOG.

1.3. **`workers/echo_worker.py:69`** — fix `core` undefined name. The file uses `"core.memory_router.MemoryRouter"` as a string type annotation (line 69). String annotations are not evaluated at runtime, so this doesn't crash, but it's incorrect. Replace with a proper `TYPE_CHECKING` import:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.memory_router import MemoryRouter
```
Then use `"MemoryRouter"` as the string annotation (forward reference). **Verification**:
```
ruff check workers/echo_worker.py --select F821
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
python -c "from workers.echo_worker import EchoWorker; print('OK')"
```
Expected: `OK`. Paste literal output to CHANGELOG.

### Step 2 — Fix F811 duplicate definitions and redundant re-imports

These fixes address code-quality issues that block mypy and create confusion.

2.1. **`core/schemas.py`** — remove duplicate `Scratchpad` class definition. Per audit section 6a: line 504 defines `Scratchpad` with 5 fields; line 600 redefines it with 6 fields (adds `is_compacted`). The second definition silently shadows the first. **Remove the FIRST definition (lines 504-511)**, keep the SECOND (lines 600-615). Do NOT remove the second — it has the `is_compacted` field that `core/scratchpad.py:155` references. **Verification**:
```
ruff check core/schemas.py --select F811
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.
```
python -c "from core.schemas import Scratchpad; s = Scratchpad(); print(hasattr(s, 'is_compacted'))"
```
Expected: `True`. Paste literal output to CHANGELOG. If `False`, you removed the wrong definition — STOP and revert.
```
python -m pytest tests/ -k "scratchpad" -v
```
Expected: all scratchpad-related tests pass. Paste `Select-Object -Last 5` to CHANGELOG.

2.2. **`cli/tui.py:53`** — remove duplicate `CommandHistory` import. The file imports `CommandHistory` twice (line 53 and elsewhere). Remove the duplicate. Keep the import that's at the correct location (top of file, with other imports). **Verification**:
```
ruff check cli/tui.py --select F811
```
Expected: 0 errors (was 1 before). Paste literal output to CHANGELOG.

2.3. **`core/escalation.py:60, 130, 185`** — remove 3 redundant `TraceEventType` re-imports inside functions. The file imports `TraceEventType` at module level; the 3 function-level re-imports are redundant. Remove all 3 function-level imports. **Verification**:
```
ruff check core/escalation.py --select F811
```
Expected: 0 errors (was 3 before). Paste literal output to CHANGELOG.

2.4. **`core/memory_router.py:391, 392`** — remove redundant `datetime` and `uuid4` re-imports inside methods. The file imports both at module level; the method-level re-imports are redundant. Remove them. **CAUTION (cross-plan hazard)**: Plan 45 added `fetch_by_type()` to this file. Do NOT remove any imports that `fetch_by_type` legitimately needs. If `fetch_by_type` uses `datetime` or `uuid4`, those usages are covered by the module-level imports — the method-level re-imports are still redundant. **Verification**:
```
ruff check core/memory_router.py --select F811
```
Expected: 0 errors (was 2 before). Paste literal output to CHANGELOG.
```
python -m pytest tests/test_memory_router.py -v
```
Expected: all tests pass (no regression from removing the re-imports). Paste `Select-Object -Last 5` to CHANGELOG.

### Step 3 — Fix F841 in core/approval_gate.py (Rule 17 violation)

This fix addresses a Rule 17 violation: `emit_error` is assigned in 5 `except Exception as emit_error:` blocks but never used, silently swallowing exceptions without trace events.

3.1. For each of the 5 occurrences identified in Step 0.11, replace the swallowed exception with a WARNING trace event. The fix pattern (per Rule 17 and prompt-41 exemplar):
```python
# Before:
except Exception as emit_error:
    pass  # or similar

# After:
except Exception as emit_error:
    logger.warning(f"Approval gate error: {emit_error}")  # Rule 17: emit WARNING trace
```

Use `logger.warning()` (not `print()`, not `await self._emitter.emit(...)`) because `core/approval_gate.py` is a sync context — verify by checking the file's existing logging convention in Step 0.11's paste. If the file uses a different convention (e.g., `self._logger.warning`), match it.

3.2. **Verification**:
```
ruff check core/approval_gate.py --select F841
```
Expected: 0 errors (was 5 before). Paste literal output to CHANGELOG.
```
Select-String -Path core/approval_gate.py -Pattern "except Exception" -Context 0,2
```
Expected: every `except Exception` block now has a `logger.warning(...)` (or equivalent) line in its body. Paste literal output to CHANGELOG.
```
python -m pytest tests/test_approval_gate.py -v
```
Expected: all tests pass. Paste `Select-Object -Last 5` to CHANGELOG.

### Step 4 — Fix F841 in 7 adapter health checks

These fixes address unused `response` variables in adapter health check methods.

4.1. For each of the 7 adapters (anthropic, cohere, deepseek, groq, mistral, openai, together), find the line `response = await client.create(...)` in the health check method. The `response` variable is never subsequently read. Fix by removing the assignment:
```python
# Before:
response = await client.create(...)

# After:
await client.create(...)
```

OR, if the call's side effects need to be documented, prefix with `_`:
```python
_response = await client.create(...)  # health check — response intentionally unused
```

**Prefer the first form (remove assignment)** unless the adapter's existing code style uses `_` prefix for intentionally-unused variables. Check each adapter's convention before deciding.

4.2. **Verification (run for each adapter)**:
```
ruff check adapters/anthropic.py adapters/cohere.py adapters/deepseek.py adapters/groq.py adapters/mistral.py adapters/openai.py adapters/together.py --select F841
```
Expected: 0 errors (was 7 before, 1 per file). Paste literal output to CHANGELOG.
```
python -m pytest tests/test_anthropic_adapter.py tests/test_cohere_adapter.py tests/test_deepseek_adapter.py tests/test_groq_adapter.py tests/test_mistral_adapter.py tests/test_openai_adapter.py tests/test_together_adapter.py -v
```
Expected: all tests pass (no regression). Paste `Select-Object -Last 5` to CHANGELOG.

### Step 5 — Fix F841 in cli/serve.py (intentionally-unused subsystem variables)

This fix addresses the 4 unused variables in `cli/serve.py` identified in audit section 6b. **Cross-plan hazard**: Plan 44 added `input_sanitiser` kwarg to `Orchestrator(...)` here. Do NOT modify that line. Only prefix the 4 unused variables.

5.1. Find the 4 variables in `cli/serve.py`'s `serve()` function: `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory`. These are constructed but never passed anywhere. Per audit section 6b note: "these subsystems are constructed for future wiring but not yet in the request path". Prefix each with `_` to acknowledge intentional non-use:
```python
# Before:
worker_persistence = WorkerPersistence(...)
output_evaluator = OutputEvaluator(...)
trace_optimiser = TraceOptimiser(...)
worker_factory = WorkerFactory(...)

# After:
_worker_persistence = WorkerPersistence(...)  # F4 wiring deferred to Plan 48b
_output_evaluator = OutputEvaluator(...)  # F4 wiring deferred to Plan 48b
_trace_optimiser = TraceOptimiser(...)  # F4 wiring deferred to Plan 48b
_worker_factory = WorkerFactory(...)  # F4 wiring deferred to Plan 48b
```

The inline comment "F4 wiring deferred to Plan 48b" is REQUIRED — it documents why the variable is intentionally unused and points to the future plan that will wire it. This satisfies Rule 17's "inline comment explaining why" requirement.

5.2. **Do NOT remove the variables entirely** — they construct subsystems that Plan 48b will wire into the request path. Removing them would create more work later. Prefixing with `_` is the correct fix.

5.3. **Verification**:
```
ruff check cli/serve.py --select F841
```
Expected: 0 errors (was 4 before). Paste literal output to CHANGELOG.
```
Select-String -Path cli/serve.py -Pattern "input_sanitiser"
```
Expected: at least 1 match (Plan 44 wiring intact). Paste literal output to CHANGELOG. If 0 matches, STOP — Plan 44 wiring was reverted by this step; revert and re-investigate.
```
python -m pytest tests/test_serve.py -v
```
Expected: all tests pass. Paste `Select-Object -Last 5` to CHANGELOG.

### Step 6 — Verify no new F821/F811/F841 errors introduced

After all 5 steps, run a final sweep to confirm no new lint errors were introduced.

6.1. **Verification**:
```
ruff check . --select F821
```
Expected: the remaining F821s are TYPE_CHECKING-only (per audit section 1, 16 name-occurrences across 15 lines). Count the remaining errors and paste to CHANGELOG. The runtime crash bugs (items 1.1, 1.2, 1.3) should be gone. If any runtime F821 remains, STOP — incomplete fix.

```
ruff check . --select F811
```
Expected: 0 errors (all 8 fixed by Step 2). Paste literal output to CHANGELOG.

```
ruff check . --select F841
```
Expected: 81 - 5 (approval_gate) - 7 (adapters) - 4 (serve.py) = 65 errors remaining. The remaining F841s are out of scope (deferred to Plan 50). Paste the count to CHANGELOG.

## Verification gates (run in order, all must pass)

1. `python -m pytest tests/test_command_history.py -v` — expected: all tests pass (Step 1.1 fix didn't break anything). Paste `Select-Object -Last 5` literal output.
2. `python -m pytest tests/test_session.py -v` — expected: all tests pass (Step 1.2 fix didn't break anything). Paste `Select-Object -Last 5` literal output.
3. `python -m pytest tests/ -k "scratchpad or approval or memory_router or serve or anthropic or cohere or deepseek or groq or mistral or openai or together" -v` — expected: all touched-area tests pass. Paste `Select-Object -Last 10` literal output.
4. `python -m pytest tests/ -q --tb=no | Select-Object -Last 3` — expected: at-or-above prompt-45 baseline (1167 passed, 55 skipped, 0 failed, 0 warnings). If a previously-passing test now fails, STOP per STOP conditions. If skip count rises above 55, STOP per STOP conditions. Paste literal output.
5. `ruff check cli/command_history.py core/session.py core/schemas.py cli/tui.py core/escalation.py core/memory_router.py core/approval_gate.py workers/echo_worker.py adapters/anthropic.py adapters/cohere.py adapters/deepseek.py adapters/groq.py adapters/mistral.py adapters/openai.py adapters/together.py cli/serve.py --select F821,F811,F841` — expected: 0 errors in the in-scope files (the F841s that remain are out-of-scope files). Paste literal output.
6. `mypy cli/command_history.py core/session.py core/schemas.py cli/tui.py core/escalation.py core/memory_router.py core/approval_gate.py workers/echo_worker.py cli/serve.py --ignore-missing-imports` — expected: 0 NEW errors introduced by this plan. Pre-existing errors must be enumerated (file:line + reason). Paste literal output.
7. Manual smoke (any shell, no interactive requirement — landmine L11):
   ```
   python -c "from cli.command_history import CommandHistory; from core.session import Session; from core.schemas import Scratchpad; from workers.echo_worker import EchoWorker; s = Scratchpad(); print('imports OK, is_compacted:', hasattr(s, 'is_compacted'))"
   ```
   Expected: `imports OK, is_compacted: True`. Paste literal output. If `is_compacted: False`, you removed the wrong Scratchpad definition in Step 2.1 — STOP and revert.

## STOP conditions

- **S0**: If Step 0.1 reveals `HEAD` is not a descendant of `prompt-45` tag, STOP (prompt-45 was not actually merged).
- **S1**: If Step 0.2 shows `prompt-45` tag is absent from origin, STOP (landmine L5: tag-push gate was skipped).
- **S2**: If Step 0.3 reveals the F821 count is not 25 errors (REV3 re-baseline — was 26 in REV2, but Plan 45 removed 3 from trajectory_exporter.py and prompt-44 added 2 new TYPE_CHECKING-only `InputSanitiser` F821s in `core/handlers.py:31,437`; net 26 - 3 + 2 = 25), OR any in-scope file's count differs from the Step 0.3 expected per-file list, STOP — baseline has drifted further since REV3; the plan's "What to change" steps may be stale.
- **S3**: If Step 0.4 reveals the F811 count is not 8 errors, OR the errors don't match the audit's F811 list, STOP — baseline drift.
- **S4**: If Step 0.6 reveals the test baseline is NOT 1167 passed / 55 skipped / 0 failed, STOP — baseline has drifted; the plan's Gate 4 target is wrong. Re-baseline before proceeding.
- **S5**: If Step 0.8 reveals `ruff check system/trajectory_exporter.py --select F821` returns ANY errors, STOP — Plan 45 did not complete its scope (Step 4.3 dead-code removal). Do NOT re-fix trajectory_exporter in Plan 46; report and let the user decide whether to amend Plan 45 or proceed.
- **S6**: If Step 0.9 reveals `cli/serve.py` has 0 matches for `input_sanitiser`, STOP — Plan 44 wiring was reverted; the precondition for Step 5 (which edits the same `serve()` function) is not met.
- **S7**: If Step 0.10 reveals `core/memory_router.py` has 0 matches for `def fetch_by_type`, STOP — Plan 45 was reverted.
- **S8**: If Step 2.1's verification `hasattr(s, 'is_compacted')` returns `False`, STOP — you removed the wrong Scratchpad definition. Revert and keep the SECOND definition (line 600).
- **S9**: If Step 5.3's verification `Select-String -Path cli/serve.py -Pattern "input_sanitiser"` returns 0 matches, STOP — Step 5 inadvertently reverted Plan 44's wiring. Revert Step 5 and re-investigate.
- **S10**: If the fix requires >50 lines of new code in any single step, STOP — the plan was underscoped. File a follow-up plan.
- **S11**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 16 editable in-scope files are listed in "Current state" above; `system/trajectory_exporter.py` is verify-only (STOP S5 covers editing it).
- **S12**: If Gate 4 shows MORE failures than the prompt-45 baseline (1167 passed, 55 skipped, 0 failed) — i.e., any new failure, OR skip count rises above 55 — STOP. A regression was introduced. Do not tag.
- **S13**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S14**: If removing the `datetime`/`uuid4` re-imports in Step 2.4 breaks `fetch_by_type` (Plan 45's method), STOP — the method may have a legitimate need for the re-import that the module-level import doesn't cover. Report and let the user decide.
- **S15**: If any closing step (C1-C10 below) is marked DONE without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S16**: If C5 (`git show prompt-46 --stat`) reveals a file outside the in-scope list (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md`), STOP — delete the tag with `git tag -d prompt-46`, unstage the out-of-scope file, and re-tag. Do not push the bad tag.
- **S17**: If C10 (`git push origin prompt-46`) succeeds locally but `git ls-remote --tags origin | findstr prompt-46` returns empty, STOP — the tag did not reach origin (landmine L5). Retry the push. If retry fails, report to user; do not mark Plan 46 complete.

## Closing steps (mandatory, every prompt)

These run AFTER all verification gates (Gates 1-7) pass. Each step requires literal output pasted to CHANGELOG (landmine L2 / Rule 19). Do not batch.

**C1** — Run full test suite:
```
python -m pytest tests/ -v
```
Confirm: zero new failures vs prompt-45 baseline (1167 passed, 55 skipped, 0 failed). Plan 46 should not change the test count (no new tests added; no tests removed). Paste `Select-Object -Last 5` literal output to CHANGELOG. If a new failure appears, STOP — Gate 4 was false-positive; revert and re-investigate.

**C2** — Ruff check on all touched files:
```
ruff check cli/command_history.py core/session.py core/schemas.py cli/tui.py core/escalation.py core/memory_router.py core/approval_gate.py workers/echo_worker.py adapters/anthropic.py adapters/cohere.py adapters/deepseek.py adapters/groq.py adapters/mistral.py adapters/openai.py adapters/together.py cli/serve.py
```
Expected: 0 NEW errors in the in-scope files for F821, F811, F841 selectors. (Pre-existing errors for other selectors — E402, F401, etc. — are out of scope; enumerate them in CHANGELOG if any remain, but do not fix.) Paste literal output to CHANGELOG.

**C3** — Mypy on all touched files:
```
mypy cli/command_history.py core/session.py core/schemas.py cli/tui.py core/escalation.py core/memory_router.py core/approval_gate.py workers/echo_worker.py cli/serve.py --ignore-missing-imports
```
Expected: 0 NEW errors introduced by Plan 46. Paste literal output to CHANGELOG. Pre-existing errors must be enumerated (file:line + reason), not silently left.

**C4** — Commit and tag:
```
git add .
git commit -m "checkpoint: prompt-46"
git tag prompt-46
```
Verify:
```
git log -1 --oneline
git tag --list prompt-46
```
Expected: `prompt-46` appears in both outputs. Paste literal output to CHANGELOG.

**C5** — Verify file list in the tag:
```
git show prompt-46 --stat
```
Expected: file list contains ONLY the 16 editable in-scope files (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` which are added in C6/C7 — they should NOT appear here because the docs commit is C9, separate from the checkpoint commit in C4). `system/trajectory_exporter.py` is verify-only and must NOT appear in the tag — if it does, STOP (it was edited, violating STOP S5):
- `cli/command_history.py`
- `core/session.py`
- `core/schemas.py`
- `cli/tui.py`
- `core/escalation.py`
- `core/memory_router.py`
- `core/approval_gate.py`
- `workers/echo_worker.py`
- `adapters/anthropic.py`, `adapters/cohere.py`, `adapters/deepseek.py`, `adapters/groq.py`, `adapters/mistral.py`, `adapters/openai.py`, `adapters/together.py`
- `cli/serve.py`

If an unexpected file appears, run `git tag -d prompt-46`, `git reset HEAD~1` (unstage the bad commit), clean, re-commit, re-tag. Do NOT push the bad tag. Paste literal output of `git show prompt-46 --stat` to CHANGELOG.

**C6** — Update `CHANGELOG.md` (append-only). **Per-step CHANGELOG entries required** — do not batch into a single summary at the end (handoff line 263). Each entry must include:
- **Date/time**: `YYYY-MM-DD HH:MM` per handoff line 191.
- **Step reference**: "Plan 46 Step 0", "Plan 46 Step 1.1", etc.
- **What was done**: concrete actions.
- **What failed (if anything)**: mid-prompt failures and how resolved.
- **Files Modified**: per-file detail (which functions/lines changed).
- **Testing Results**: baseline → final, with the exact command run.
- **Verification Gate Output**: literal output of each gate (Gates 1-7 + Closing steps C1-C3).

**Mandatory re-baseline entry (REV3)**: the FIRST CHANGELOG entry for Plan 46 must document the S2 STOP fire and re-baseline. Specifically:
- Date/time of the S2 fire.
- The original REV2 expected count (26) and the actual count (25).
- The drift analysis: Plan 45 removed 3 F821s from `system/trajectory_exporter.py` (-3); prompt-44 added 2 new TYPE_CHECKING-only `InputSanitiser` F821s in `core/handlers.py:31,437` (+2); net = 26 - 3 + 2 = 25.
- The amendment decision: 2 new F821s are TYPE_CHECKING-only and in an out-of-scope file → deferred to Plan 47/48 (consistent with existing TYPE_CHECKING-only deferrals). No new sub-steps added to Plan 46.
- Confirmation that the 3 in-scope runtime-crash F821s (`cli/command_history.py:97`, `core/session.py:237,280`, `workers/echo_worker.py:69`) have NOT drifted — line numbers match exactly.
- The full ruff F821 output (25 lines) pasted as evidence.

Use the CHANGELOG append procedure below (PowerShell, because file locks).

**C7** — Update `SOVEREIGN_AI_HANDOFF.md`:
- Move Plan 46 from "Next 5 prompts" to "Completed prompts" table. Include the same row format as the existing completed-prompt rows: `| 46 | F821 + F811 + critical F841 cleanup | 1167 | <one-line result summary> |`.
- Update "What's broken right now" — remove the F821 runtime crash bugs (cli/command_history.py:97, core/session.py:237,280) from any implicit bug list. F4 stays.
- Update "Static analysis baseline" line (handoff line 11) — change "365 ruff errors, 116 mypy errors" to the new counts (F821: 26 → ~16 TYPE_CHECKING-only; F811: 8 → 0; F841: 81 → ~65; F401: 260 unchanged; E402: 33 unchanged; F541: 15 unchanged). Calculate the new total and update.
- Update test baseline line (handoff line 9) — should remain "1167 passed, 55 skipped" (no test count change in Plan 46).
- **Refill the "Next 5 prompts" queue** so it always has 5 entries (handoff line 264). The queue after Plan 46: Plan 47 (E402 + missing `gateways/__init__.py`, P2), Plan 48 (ApprovalGate API drift + mypy remediation, P2), Plan 49 (test suite health), Plan 50 (F401 bulk cleanup), Plan 48b (F4 wiring — recommended by audit section 6b, deferred until after Plan 47).
- Update the "Last updated" header to `2026-06-20 — post prompt-46, handoff amended by GLM session 8`.

**C8** — Update `global_rules.md` IF a new recurring mistake pattern or landmine was identified during Plan 46 execution. Per handoff line 265. Do NOT cite `global_rules.md` as authority (landmine L1). If no new pattern was identified, skip this step and document the skip in CHANGELOG with reason "no new recurring mistake pattern identified in prompt-46".

**C9** — Commit docs:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md global_rules.md
git commit -m "docs: prompt-46 changelog and handoff update"
```
If `global_rules.md` was not modified in C8, omit it from the `git add`:
```
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-46 changelog and handoff update"
```
Verify:
```
git log -1 --oneline
git show HEAD --stat
```
Expected: commit message is `docs: prompt-46 changelog and handoff update`, file list contains only `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md` (plus `global_rules.md` if C8 ran). Paste literal output to CHANGELOG.

**C10** — Push to origin:
```
git push origin master
git push origin prompt-46
```
**Tag-push gate (landmine L5 — non-negotiable)**: after pushing, verify the tag actually reached origin:
```
git ls-remote --tags origin | findstr prompt-46
```
Expected: a line containing `prompt-46`. If this returns empty, the push was reported as "pushed to remote" but the tag did not actually reach origin (prompt-38 failure mode — handoff line 312). Retry the push. If retry fails, report to user; do NOT mark Plan 46 complete in the CHANGELOG until the tag is verified on origin. Paste literal output of `git ls-remote --tags origin | findstr prompt-46` to CHANGELOG.

## CHANGELOG append procedure (PowerShell, because file locks)

Per handoff lines 269-273. Use these exact PowerShell idioms — do not substitute.

- **Line count**: `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count`. NEVER use `Get-Content | Measure-Object` — it truncates large files.
- **Append**: `Add-Content` only. NEVER paste into editor, NEVER use insert operations.
- **Before appending**: record current line count.
- **After appending**: verify new count exceeds previous, verify last 5 lines with `Select-Object -Last 5`.
- **Close the file in the IDE before running `Add-Content`** — file locks will cause silent truncation.
- **Example session for one CHANGELOG entry**:
  ```powershell
  $before = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Add-Content -Path r"C:\Jarvis\CHANGELOG.md" -Value @"

  ## 2026-06-20 HH:MM — Plan 46 Step 1.1

  **What was done**: Added `uuid4` to the `from uuid import` line in cli/command_history.py. Previously only `UUID` was imported, causing F821 at line 97 where `uuid4()` is called.

  **Files Modified**:
  - cli/command_history.py: line 1 — changed `from uuid import UUID` to `from uuid import UUID, uuid4`.

  **What failed**: <none / mid-prompt failures and resolution>

  **Testing Results**: ruff F821 in cli/command_history.py: 1 → 0. Test suite unchanged.

  **Verification Gate Output**:
  ``<literal output of Step 1.1 verification command>``
  "@
  $after = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Write-Host "Before: $before, After: $after"
  Get-Content r"C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5
  ```

## Out of scope

The following are explicitly out of scope for Plan 46. Each requires its own plan. Do not bundle — bundling is scope creep (landmine L12).

- **E402 import ordering + missing `gateways/__init__.py`** (audit Plan 47) — separate plan.
- **F401 bulk cleanup** (260 unused imports, audit Plan 50) — separate plan.
- **F541 f-string no placeholders** (15 errors, audit section 1) — separate plan. Mechanical, low-risk.
- **F841 cleanup beyond the 16 critical ones in scope** (remaining ~65 errors, audit section 1) — separate plan (Plan 50 or follow-up).
- **ApprovalGate API drift** (audit section 6b, 14+ callers using old `request_approval()` signature) — separate plan (audit recommends Plan 48).
- **F4 wiring fix** (audit section 6b — cognition-loop components built but never used in serve path). Plan 46 Step 5 only silences the F841 lint warnings; it does NOT wire the subsystems. Recommend Plan 48b for F4 wiring after Plan 47 lands.
- **TYPE_CHECKING-only F821s** (18 name-occurrences across 16 lines, post-Plan-45 + post-prompt-44). These are string annotations not evaluated at runtime — not crash bugs. They generate mypy errors but don't affect runtime. Deferred to Plan 47/48 (mypy remediation). The full list (use ACTUAL line numbers from Step 0.3's ruff output, not the audit's stale numbers):
  - `core/escalation.py:32` — `TraceEmitter`
  - `core/handlers.py:29, 435` — `Orchestrator` (×2; audit said lines 28, 428 — line drift from prompt-44/45 edits)
  - `core/handlers.py:31, 437` — `InputSanitiser` (×2; **NEW in REV3** — introduced by prompt-44's InputSanitiser wiring work; not in original audit)
  - `core/notification.py:54` — `TelegramGateway`
  - `core/orchestrator.py:46` — `A2ARouter` (audit said line 44 — line drift)
  - `core/orchestrator.py:725` — `A2ARequest` + `A2AResponse` (2 names on 1 line; audit said line 721 — line drift)
  - `core/retention.py:46` — `MemoryRouter`
  - `core/worker_base.py:78` — `TraceEmitter`
  - `core/worker_factory.py:581` — `LLMResponse` + `WorkerOutput` (2 names on 1 line)
  - `system/model_acquisition.py:255, 256, 304, 305, 734, 810` — `ResourceManager` (×3) + `ModelRegistry` (×3)
  - `system/resource_manager.py:227, 290` — `ModelRegistry` (×2)

  **Note on the 2 new `InputSanitiser` F821s**: these were introduced by prompt-44 when InputSanitiser was wired into the cognition stack. `core/handlers.py` has TYPE_CHECKING references to `InputSanitiser` (string annotations at lines 31 and 437) but the `TYPE_CHECKING` import block does not include `InputSanitiser`. The fix is a 2-line addition to the TYPE_CHECKING import block — but this is OUT OF SCOPE for Plan 46 because (a) it's TYPE_CHECKING-only (not a runtime crash), (b) `core/handlers.py` is not in Plan 46's 16 editable in-scope files, and (c) bundling it would violate landmine L12 (scope creep). Defer to Plan 47/48 mypy remediation, where ALL TYPE_CHECKING-only F821s are addressed uniformly.
- **Marine stack** (handoff's original Plan 49) — deferred until after the audit's P1/P2 cleanup.
- **mypy remediation beyond the 9 in-scope files** — separate plan.
- **Any change to InputSanitiser's public API or Plan 45's trajectory_exporter implementation** — Plan 45 is complete; do not modify its work. Plan 46 only touches the 16 editable in-scope files listed above (`system/trajectory_exporter.py` is verify-only — STOP S5 fires if edited).

**Note on Next 5 queue refill (handoff closing step 7)**: When Plan 46 completes, the "Next 5 prompts" queue must be refilled. The 2026-06-20 audit recommends the new queue be: Plan 47 (E402 + missing `gateways/__init__.py`, P2), Plan 48 (ApprovalGate API drift + mypy remediation, P2), Plan 49 (test suite health), Plan 50 (F401 bulk cleanup), Plan 48b (F4 wiring — recommended by audit section 6b, deferred until after Plan 47).

## For Claude review (Devin: do not execute)

1. **Step 5 inline-comment requirement (Rule 17 compliance)**: the plan requires `_worker_persistence = WorkerPersistence(...)  # F4 wiring deferred to Plan 48b` for all 4 unused variables in `cli/serve.py`. Is the comment text "F4 wiring deferred to Plan 48b" sufficient to satisfy Rule 17's "inline comment explaining why" requirement, or should it be more explicit (e.g., "intentionally unused — these subsystems are constructed for future wiring per Plan 48b; see audit section 6b")?

2. **Step 2.4 cross-plan hazard with Plan 45's `fetch_by_type`**: the plan says "do NOT remove any imports that `fetch_by_type` legitimately needs". But the module-level imports cover all method-level usages — so the method-level re-imports are ALWAYS redundant. Is the caution warranted, or does it create unnecessary ambiguity? STOP S14 covers the case where removing the re-imports breaks `fetch_by_type` — is that STOP too conservative?

3. **Step 3 logging convention**: the plan says "Use `logger.warning()` (not `print()`, not `await self._emitter.emit(...)`) because `core/approval_gate.py` is a sync context — verify by checking the file's existing logging convention in Step 0.11's paste." Is this verification step clear enough, or should the plan dictate the exact logging call (e.g., `logger.warning(f"Approval gate error: {emit_error}")`) without leaving room for Devin to choose a different convention?

4. **Step 4 `_` prefix vs. remove assignment**: the plan says "Prefer the first form (remove assignment) unless the adapter's existing code style uses `_` prefix for intentionally-unused variables." This delegates the decision to Devin. Is this acceptable, or should the plan dictate one approach uniformly to avoid inconsistency across the 7 adapters?

5. **Gate 4 baseline tolerance**: Plan 46 should not change the test count (no new tests, no removed tests). But if a previously-passing test starts failing due to a Plan 46 fix (e.g., the `Scratchpad` duplicate removal breaks a test that depended on the first definition's behavior), the count drops. The plan currently treats ANY new failure as STOP (S12). Is this the right threshold, or should it allow 1-2 failures with documented investigation (since some "tests" may have been smoke checks that relied on the buggy behavior — recurring mistake pattern #2)?
