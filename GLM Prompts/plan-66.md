# Plan 66 -- System Cleanup and Final Core Hardening

## Opening (S0)

1. **Run `/jarvis-open`** -- verify `prompt-65` tag on origin, confirm working copy clean and on master. If workflow missing or fails, STOP and report.
2. **Read AGENTS.md in full** -- apply all existing rules (AR1-AR18, OR1-OR27). Cite rules by number per OR23.
3. **Pre-check: system/ test coverage** -- check if `tests/test_system.py` or `tests/test_model_acquisition.py` exists. If not, note this for S2 verification (no targeted tests available).
4. **Scope declaration** -- will edit:
   - `system/model_acquisition.py` -- 4 mypy errors (deferred from Plan 65)
   - Any `core/` files with mypy errors discovered in S1 full-repo scan (see S1.5 STOP threshold)
   - Will NOT edit: `evals/`, `adapters/`, `skills/`, `web/`, `cli/`, `workers/`, `gateways/`, `memory/`, `orchestrator/`, `tests/`

## Plan Body (S1-S6)

### S1 -- Full-Repo Mypy Scan

Run: `mypy core/ system/ --ignore-missing-imports`

Save output to `plan-66-baseline.log`:
```powershell
mypy core/ system/ --ignore-missing-imports > plan-66-baseline.log 2>&1
```

Document all errors. Categorize by:
- **Enum vs string**: String literals where enum expected
- **UUID vs string**: str/UUID mismatches
- **Type mismatch**: Other incompatible types
- **Import errors**: Missing or wrong imports
- **Return type**: Function return type mismatches

Count errors per file. Expected: `system/model_acquisition.py` has 4 errors, `core/` files have 0-2 errors (minor cross-file issues from Plan 65).

**Note for Plan 68**: Save `plan-66-baseline.log` for reference to avoid duplication in the milestone scan.

### S1.5 -- Scope STOP Gate

**STOP thresholds**:
- If `system/model_acquisition.py` has >6 errors, STOP and report (expected 4, some drift acceptable)
- If total errors across all `system/` files >8, STOP and report (catches unexpected system/ drift)
- If any single `core/` file has >3 errors, STOP and report (Plan 65 should have fixed core/)
- If total errors across all files >15, STOP and report (core should be cleaner after Plans 64-65)
- If errors are in files outside `core/` and `system/` that are **caused by** changes in `core/` or `system/` (e.g., evals/ importing a changed core/ type), note them but do not STOP -- they may need fixing as part of this plan's scope
- If errors are in files outside `core/` and `system/` that are **pre-existing** (not caused by this plan's changes), note them but do not STOP -- they are out of scope

If STOP triggered, report: file names, error counts, and recommended scope adjustment.

### S2 -- Fix system/model_acquisition.py

**Pre-step: Verify `from __future__ import annotations`**
- Check if present at line 1 of `system/model_acquisition.py`
- If **missing**: ADD it before making any `X | None` syntax fixes
- If **present**: proceed with fixes
- Rationale: Python <3.10 requires this import for `X | None` union syntax. Even on 3.10+, it's recommended for forward compatibility.

**Per OR27**: If fixing a type error requires changing a runtime type that would break existing tests, add a compatibility shim instead of modifying the test.

**After each fix**:
- Run `mypy system/model_acquisition.py --ignore-missing-imports` to verify the target error is gone
- If **new errors appear** (different from the one just fixed), report them before proceeding to the next error fix
- Do NOT proceed to the next error fix until current error is fully resolved

**Expected errors and fix templates**:

**Error 1: Line 36 -- ModelRegistry import [attr-defined or import]**
```python
# Before (line 36):
from system.model_acquisition import ModelRegistry  # Module has no attribute "ModelRegistry"

# Decision tree:
# 1. Check if this is a self-import (importing from the same file):
#    - If yes: remove the import and use ModelRegistry directly if defined in this file
#    - If no: proceed to step 2
#    - Note: self-import often indicates circular import. Check __all__ definitions or refactor imports.
# 2. grep -r "class ModelRegistry" . --include="*.py" (search entire repo, not just system/)
#    - If found in another module: fix import path to that module
#    - If not found anywhere: check if it's a stale reference:
#      - grep -r "ModelRegistry" system/ -- if only used in this file, remove import and usage
#      - If used elsewhere, the class may need to be defined or imported from correct module
# 3. If ModelRegistry should exist but is missing, this is a logic gap -- STOP and report
# 4. Check mypy error code: [attr-defined] means class missing; [import] means import path wrong
```

**Error 2: Line 80 -- params type (dict[str, object] vs expected QueryParams)**
```python
# Before (line 80):
params = {"key": value}  # type: dict[str, object]
response = await client.get(url, params=params)

# Decision: Read the mypy error message carefully -- it will tell you the exact expected type.
# The error message format is: "Argument X to Y has incompatible type Z; expected W"
# Extract "expected W" and use that as the target type.
# If the error message is unclear, check httpx source:
python -c "import httpx; print(httpx.AsyncClient.get.__annotations__)"

# After (if httpx expects QueryParams):
from httpx import QueryParams
params = QueryParams({"key": value})
response = await client.get(url, params=params)

# OR (if type checker expects dict[str, str]):
params: dict[str, str] = {"key": str(value)}
response = await client.get(url, params=params)
```

**Error 3: Line 616 -- float vs int**
```python
# Before (line 616):
progress: int = 0.75  # Incompatible types: float vs int

# After (if progress should be float):
progress: float = 0.75

# OR (if progress must be int):
progress: int = int(0.75)  # or round(0.75 * 100) for percentage

# Decision: check how progress is used downstream -- if divided by 100, keep float; if displayed as integer percentage, use int
```

**Error 4: Line 833 -- None vs ResourceManager**
```python
# Before (line 833):
result = check_fit(model, data, None)  # Expected ResourceManager, got None

# After (if ResourceManager is optional):
# Update function signature: def check_fit(..., manager: ResourceManager | None = None) -> bool
# Requires: from __future__ import annotations (verified in pre-step)

# OR (if ResourceManager is required):
from system.resource_manager import ResourceManager
manager = ResourceManager()  # or get from dependency injection
result = check_fit(model, data, manager)

# Decision: check if ResourceManager has a default/null state; if yes, make parameter optional
```

### S3 -- Fix Cross-File Mypy Errors

**Detection method**:
```powershell
mypy core/ system/ --ignore-missing-imports > plan-66-post-system-fix.log 2>&1
# Compare to baseline
diff plan-66-baseline.log plan-66-post-system-fix.log
```

If `system/model_acquisition.py` is now clean but new errors appear in `core/` files, these are cross-file errors.

**Causality check**:
- **Pre-existing**: Error appears in `plan-66-baseline.log` -- skip it (out of scope for Plan 66)
- **Introduced during Plan 66**: Error does NOT appear in `plan-66-baseline.log` but appears after S2 fixes -- fix it in S3
- **Rule of thumb**: If the error message references a type, enum, or function signature changed in Plan 65 or S2, it was likely introduced during Plan 66; fix it
- **Unrelated new errors**: If error references types not touched in Plans 64-66, STOP and report (unexpected drift)

**Fix approach** (same patterns as Plans 64-65):
1. Enum string literal -> replace with enum value (TaskPriority.NORMAL, etc.)
2. UUID string -> wrap with UUID()
3. Type mismatch -> cast or update annotation

**Per OR27**: Use compatibility shims if tests would break.

**STOP thresholds**:
- If >3 cross-file errors in core/, STOP and report. Plan 65 should not have introduced that many.
- **Cumulative STOP**: If fixing cross-file errors brings total error count across all files to >15, STOP and report. This mirrors S1.5 and prevents scope creep during remediation.

### S4 -- Enum Consistency Verification (Conditional)

**Pre-flight check before running S4**:
```powershell
# Check if enum errors exist in baseline or current scan
grep -E "str is not assignable to Enum|has incompatible type.*Enum|expected.*Enum" plan-66-baseline.log plan-66-post-system-fix.log 2>/dev/null
```
- If **0 matches**: Skip S4 entirely. No enum errors detected.
- If **matches found**: Run S4 enum grep below.

**Rationale**: If mypy didn't flag enum issues yet, grep-based search may find latent ones. If no enum errors surfaced, skip.

If run, use string-literal-specific patterns:
```powershell
grep -rE 'priority\s*=\s*["']' core/ --include="*.py" | grep -v "TaskPriority"
grep -rE 'current_state\s*=\s*["']' core/ --include="*.py" | grep -v "TaskStatus"
grep -rE 'action_type\s*=\s*["']' core/ --include="*.py" | grep -v "ApprovalActionType"
```

Fix any matches (replace string with enum value).

### S5 -- File-Scoped Verification

After each file edit, run `/jarvis-verify`. Then:

1. Syntax check: `python -c "import ast; ast.parse(open('<file>').read())"`
2. Ruff: `ruff check <edited_file>`
3. Mypy: `mypy <edited_file> --ignore-missing-imports`
4. If mypy shows >0 errors on the edited file, fix before proceeding to next file.

After ALL files edited, run:
5. Full ruff: `ruff check core/ system/`
6. Full mypy: `mypy core/ system/ --ignore-missing-imports > plan-66-final.log 2>&1`
7. Compare to S1 baseline:
   - **Net reduction**: Error count < S1 count -- pass
   - **Stable baseline**: Error count == S1 count -- check `diff plan-66-baseline.log plan-66-final.log`. If all errors are from S1 baseline (no new errors introduced), acceptable. If new errors appeared, investigate.
   - **Regression**: Error count > S1 count -- STOP and report which files introduced new errors

### S6 -- Baseline Reconciliation

Run full test suite: `python -m pytest tests/ -q --tb=short`

**Expected**: 1232 passed, 67 skipped

**Tolerance rules**:
- 1231-1233 passed: acceptable (±1 from baseline, accounts for flaky tests)
- 1230 or fewer: STOP and report
- 1234 or more: STOP and report

**Why ±1**: Plan 65 established 1232 as stable baseline. ±1 accounts for test order randomization or platform-specific skips without hiding real regressions.

**Windows CI variance**: If running on Windows CI and consistently seeing 1230 or 1234 without code changes, this is a known platform variance. Do NOT fail Plan 66 or broaden tolerance. Report to CI maintainer with the exact test count and environment details.

If ruff/mypy errors appear outside edited files, STOP and report -- do not fix unilaterally (OR16).

## Abort & Rollback

If S5 or S6 fails and cannot be fixed within scope:
1. `git checkout -- <file>` to revert individual file
2. If multiple files affected: `git reset --hard HEAD` to last known good state
3. Report which file failed and the error message
4. Do NOT proceed to closing

## Closing

**Run `/jarvis-close`** -- handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md, rule proposal, docs commit, push, post-push verification. If workflow missing or fails, STOP and report.

**Closing checklist**:
- [ ] S6 baseline reconciliation passed (1231-1233 passed, 67 skipped)
- [ ] Ruff: 0 errors on all edited files AND no new errors outside scope
- [ ] Mypy: net reduction OR stable baseline with no new errors (see S5 verification rules)
- [ ] `/jarvis-close` executed successfully:
      - [ ] Tag `prompt-66` created and pushed
      - [ ] CHANGELOG entry appended
      - [ ] PLANS.md updated (Plan 66 -> completed, Plan 67 -> ACTIVE)
      - [ ] C9 rule proposal: Option B (none) unless new pattern found
      - [ ] No new mypy/ruff errors introduced in files outside core/ and system/

**If any checklist item fails, mark Plan 66 as BLOCKED and report the failure.**
