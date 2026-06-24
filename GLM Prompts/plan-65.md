# Plan 65 -- Mypy Remediation Phase 2

## Opening (S0)

1. **Run `/jarvis-open`** -- verify `prompt-64` tag on origin, confirm working copy clean and on master. If workflow missing or fails, STOP and report.
2. **Read AGENTS.md in full** -- apply all existing rules (AR1-AR18, OR1-OR26). Cite rules by number per OR23.
3. **Check OR27 in AGENTS.md** -- if missing, add it now. OR27 text: "When fixing type errors requires interface changes that would break existing tests, add compatibility shims to maintain backward compatibility. The shim should delegate to the new implementation while accepting the old signature. Mark the shim as deprecated with a docstring noting the legacy status. This allows type fixes without test modifications, which are outside scope for type-remediation plans. (Source: L9)"
4. **Check L9 in LANDMINES.md** -- if missing, append it now. L9 text: "Runtime type changes for mypy break test assertions. Trigger: Plan 64, Devin changed runtime types (wrapping dicts as Message objects, changing string returns to enum values) to satisfy mypy. Tests asserting on dict-like access or string values broke. Impact: 2 failed test rounds, time lost reverting. Fix: per OR27, add compatibility shims that preserve old runtime behavior while satisfying type checker. Never change runtime types in type-remediation plans without verifying test assertions first."
5. **Commit governance docs** -- if AGENTS.md or LANDMINES.md were changed in S0.3 or S0.4: `git add AGENTS.md LANDMINES.md` (whichever changed), `git commit -m "docs: add OR27 and L9 from Plan 64 retrospective"`. If no changes, skip.
6. **Scope declaration** -- will edit:
   - `core/session.py` -- enum vs string fixes
   - `core/task_state_machine.py` -- UUID/string + enum fixes
   - `core/escalation.py` -- enum fix
   - `core/retention.py` -- enum fix
   - `core/worker_factory.py` -- type mismatch fixes
   - `core/orchestrator.py` -- return type fix
   - Will NOT edit: `system/model_acquisition.py` (deferred to system-focused plan), `evals/`, `adapters/`, `skills/`, `web/`, `cli/`, `workers/`, `gateways/`, `memory/`, `orchestrator/`, `tests/`

## Plan Body (S1-S6)

### S1 -- READ-ONLY STOP Gate: Enumerate Remaining Mypy Errors

Run: `mypy core/session.py core/task_state_machine.py core/escalation.py core/retention.py core/worker_factory.py core/orchestrator.py --ignore-missing-imports`

Save output to `plan-65-baseline.log`:
```powershell
mypy core/session.py core/task_state_machine.py core/escalation.py core/retention.py core/worker_factory.py core/orchestrator.py --ignore-missing-imports > plan-65-baseline.log 2>&1
```

Document exact errors below. Do NOT proceed to S2 until documented.

**Expected errors** (verify against actual output):
- `core/session.py`: 6 errors -- all `TaskPriority`/`TaskStatus` string vs enum
- `core/task_state_machine.py`: 2 errors -- UUID string, `TaskPriority` string
- `core/escalation.py`: 1 error -- `ApprovalActionType` string
- `core/retention.py`: 1 error -- `TaskPriority` string
- `core/worker_factory.py`: 2 errors -- `DynamicWorkerProfile` vs `WorkerProfile`, UUID string
- `core/orchestrator.py`: 1 error -- return type `WorkerOutput` vs `Task | None`

**STOP thresholds**:
- If any file has error count differing by >1 from expected, STOP and report.
- If any error type differs from expected (e.g., "import error" instead of "enum vs string"), STOP and report.
- If total errors <10 or >14, STOP and report.

### S2 -- Enum vs String Fixes

**Fix template**:
```python
# Before: hardcoded string
priority = "normal"  # type: str

# After: enum value
priority = TaskPriority.NORMAL

# Before: dynamic string from config
status = get_status_from_config()  # returns str

# After: enum with validation
try:
    status = TaskStatus[status.upper()]
except (KeyError, ValueError):
    status = TaskStatus.RECEIVED  # fallback to default
```

**Decision tree**:
1. Hardcoded string literal -> replace with enum value
2. Pydantic model with `ConfigDict(use_enum_values=True)` -> no fix needed
3. Dynamic string from config/user input -> `EnumClass[value.upper()]` with try/except KeyError
4. Intermediate calculation -> trace to source, change source to enum if possible; else cast

**Per OR27**: If fixing an enum reference breaks a test that asserts on the string value, add a compatibility shim:
```python
@property
def priority_str(self) -> str:
    """Deprecated: use .priority directly. Kept for test compatibility."""
    return self.priority.value
```

**Files**:
- `core/session.py` ~lines 114, 115, 240, 241, 283, 284
- `core/task_state_machine.py` ~lines 294, 297
- `core/escalation.py` ~line 140
- `core/retention.py` ~line 161

### S3 -- UUID vs String Fixes

**Fix template**:
```python
# Before: str where UUID expected
task_id = "550e8400-e29b-41d4-a716-446655440000"

# After: UUID constructor
task_id = UUID("550e8400-e29b-41d4-a716-446655440000")
```

**Decision tree**:
1. Valid UUID string where UUID expected -> wrap with `UUID(value)`
2. Parameter accepts both -> update annotation to `str | UUID` (check schema first)
3. Already UUID but typed as str -> `typing.cast(UUID, value_str)`

**Files**:
- `core/task_state_machine.py` ~line 294
- `core/worker_factory.py` ~line 584

### S4 -- Type Mismatch Fixes

**worker_factory.py ~line 353: DynamicWorkerProfile vs WorkerProfile**

Decision tree:
1. Check if `DynamicWorkerProfile` inherits from `WorkerProfile`:
   - Yes -> `typing.cast(WorkerProfile, profile)`
   - No -> check if parameter can accept `DynamicWorkerProfile`:
     - Yes -> update parameter type to `WorkerProfile | DynamicWorkerProfile`
     - No -> STOP and report (logic error outside scope)

**orchestrator.py ~line 721: Return type WorkerOutput vs Task | None**

Decision tree:
1. Read all return paths in the method
2. If returns `WorkerOutput` in some paths and `Task` in others:
   - Change return type to `WorkerOutput | Task | None`
   - Verify callers handle all types
3. If always returns `WorkerOutput` but annotation says `Task | None`:
   - Fix annotation to `WorkerOutput`

### S5 -- File-Scoped Verification

After each file edit, run `/jarvis-verify`. Then:

1. Syntax check: `python -c "import ast; ast.parse(open('<file>').read())"`
2. Ruff: `ruff check <edited_file>`
3. Mypy: `mypy <edited_file> --ignore-missing-imports`
4. If mypy shows >0 errors on the edited file, fix before proceeding to next file.

After ALL files edited, run:
5. Full ruff: `ruff check core/session.py core/task_state_machine.py core/escalation.py core/retention.py core/worker_factory.py core/orchestrator.py`
6. Full mypy: `mypy core/session.py core/task_state_machine.py core/escalation.py core/retention.py core/worker_factory.py core/orchestrator.py --ignore-missing-imports`
7. Targeted tests: `python -m pytest tests/test_session.py tests/test_task_state_machine.py tests/test_escalation.py tests/test_worker_factory.py tests/test_orchestrator.py -v --tb=short`
   - Skip any test file that doesn't exist
   - If tests fail, revert the change and report (do not attempt to fix test)

### S6 -- Baseline Reconciliation

Run full test suite: `python -m pytest tests/ -q --tb=short`

**Expected**: 1232 passed, 67 skipped

**Tolerance rules**:
- 1230-1234 passed: acceptable (flaky or order-dependent tests)
- 1229 or fewer: investigate. Are failures unrelated to our 6 files? If yes, STOP and report.
- 1235 or more: investigate. Did we add tests? If not, STOP and report.

If ruff/mypy errors appear outside edited files, STOP and report -- do not fix unilaterally (OR16).

## Abort & Rollback

If S5 or S6 fails and cannot be fixed within the file's scope:
1. `git checkout -- <file>` to revert individual file
2. If multiple files affected: `git reset --hard HEAD` to last known good state
3. Report which file failed and the error message
4. Do NOT proceed to closing

## Closing

**Run `/jarvis-close`** -- handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md, rule proposal, docs commit, push, post-push verification. If workflow missing or fails, STOP and report.

**Closing checklist**:
- [ ] S6 baseline reconciliation passed (1230-1234 passed, 67 skipped)
- [ ] Ruff: 0 errors on all 6 edited files AND no new errors outside scope
- [ ] Mypy: 0 errors on all 6 edited files (file-scoped)
- [ ] `/jarvis-close` executed successfully:
      - [ ] Tag `prompt-65` created and pushed
      - [ ] CHANGELOG entry appended
      - [ ] PLANS.md updated (Plan 65 -> completed, Plan 66 -> ACTIVE)
      - [ ] OR27 present in AGENTS.md (verified in S0.3)
      - [ ] L9 present in LANDMINES.md (verified in S0.4)
      - [ ] C9 rule proposal: Option B (none) -- no new patterns this plan, OR27/L9 already captured

**If any checklist item fails, mark Plan 65 as BLOCKED and report the failure.**
