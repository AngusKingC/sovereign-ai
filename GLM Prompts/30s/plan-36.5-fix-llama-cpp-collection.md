# Plan 36.5 — Fix llama_cpp test collection

> **Executor instructions**: This is a one-line fix. Follow the steps in order. Run the verification gates. If any gate doesn't pass, stop and report. No improvisation.
>
> **Drift check (run first)**: `git diff --stat 274fe06..HEAD -- tests/test_llama_cpp_adapter.py`
> If this file changed since prompt-36, compare the "Current state" excerpt against the live code before proceeding; on a mismatch, STOP.

## Status

- **Priority**: P1 (blocks every subsequent plan's baseline stability)
- **Effort**: S (5 minutes)
- **Risk**: LOW
- **Depends on**: prompt-36 (already landed, commit 274fe06)
- **Planned at**: commit `274fe06`, 2026-06-18
- **In scope**: `tests/test_llama_cpp_adapter.py` (one line added near top)
- **Out of scope**: everything else. Do not touch the adapter, other test files, CI workflow, or handoff beyond what's specified in Closing Steps below.

## Why this matters

`tests/test_llama_cpp_adapter.py:13` does `from adapters.llama_cpp import LlamaCppAdapter`, which transitively imports `llama_cpp` at module level. `llama_cpp` is not installed (per CHANGELOG Phase 4, 2026-06-06: "Installation failure due to missing Windows build tools"). Result: pytest aborts at collection with `ModuleNotFoundError: No module named 'llama_cpp'` and runs zero tests.

This forces every test command to use `--ignore=tests/test_llama_cpp_adapter.py`, which causes the baseline-count confusion that's been recurring since 35.6c — three consecutive CHANGELOGs (35.6c, 35.6f, 36) with wrong test-count math because the baseline command and the verification command used different `--ignore` flags.

It also breaks CI. `.github/workflows/ci.yml` runs `python -m pytest tests/ -v` without `--ignore`. On first CI run, collection will abort with `ModuleNotFoundError` and CI goes red on a collection error, hiding every real regression in the noise.

The fix is `pytest.importorskip("llama_cpp")` at the top of the test file. The file collects, the 9 tests skip cleanly when `llama_cpp` is missing, the tests run when `llama_cpp` is present. No `--ignore` needed anywhere. Baseline becomes stable across local and CI.

## Current state

`tests/test_llama_cpp_adapter.py` lines 1-13:

```python
"""
llama.cpp adapter tests.

Single responsibility: Test llama.cpp adapter functionality,
hardware configuration, and LLM generation.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from adapters.llama_cpp import LlamaCppAdapter
```

The `from adapters.llama_cpp import LlamaCppAdapter` line at module-import time triggers `import llama_cpp` inside `adapters/llama_cpp.py:12`, which fails at collection time before any test runs.

Verify this is still the current state before editing (PowerShell):

```powershell
Get-Content tests\test_llama_cpp_adapter.py | Select-Object -First 15
```

If the first 15 lines don't match the excerpt above, STOP — the file has drifted since this plan was written.

## What to change

### Step 1 — Add `importorskip` at the top of the test file

**File**: `tests/test_llama_cpp_adapter.py`

Replace the first 13 lines:

```python
"""
llama.cpp adapter tests.

Single responsibility: Test llama.cpp adapter functionality,
hardware configuration, and LLM generation.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from adapters.llama_cpp import LlamaCppAdapter
```

With:

```python
"""
llama.cpp adapter tests.

Single responsibility: Test llama.cpp adapter functionality,
hardware configuration, and LLM generation.
"""

import pytest

# Skip all tests in this file if llama_cpp is not installed.
# Without this, pytest aborts at collection with ModuleNotFoundError,
# which forces every test command to use --ignore=tests/test_llama_cpp_adapter.py
# and breaks CI (which runs pytest without --ignore).
pytest.importorskip("llama_cpp")

from datetime import datetime
from uuid import uuid4

from adapters.llama_cpp import LlamaCppAdapter
```

**Why this placement**: `pytest.importorskip("llama_cpp")` must run BEFORE `from adapters.llama_cpp import LlamaCppAdapter` (which transitively imports `llama_cpp`). If `llama_cpp` is not installed, `importorskip` raises `pytest.skip()` at module level, the file is collected but all tests are marked skipped, and pytest continues with the rest of the suite. If `llama_cpp` is installed, `importorskip` is a no-op and the tests run normally.

**Why `importorskip` and not deleting the test file**: The `LlamaCppAdapter` is dead code (llama_cpp never installed successfully, LM Studio is the documented fallback). Deleting the test file would be cleaner. But deleting tests without confirming the adapter is truly dead is riskier than `importorskip` — if someone ever gets llama_cpp working on Windows, the tests are still there. `importorskip` is the reversible choice; deletion is not. If you want to delete the adapter entirely, that's a separate plan.

**Why `importorskip` and not `pytestmark = pytest.mark.skipif(...)`**: `importorskip` is the standard pytest pattern for optional dependencies. It's a one-liner, doesn't require importing the module to check, and produces cleaner skip reasons in the test output. `skipif` requires a manual `import` check that itself can fail at collection.

### Step 2 — Do not modify any other file

That's it. One file, one line added (plus a comment). Do not:
- Modify `adapters/llama_cpp.py`
- Modify `.github/workflows/ci.yml` (it already runs `pytest tests/ -v` without `--ignore`, which is what we want)
- Modify `SOVEREIGN_AI_HANDOFF.md` beyond what's specified in Closing Steps below
- Modify any other test file
- Add `llama_cpp` to `requirements.txt`

## Verification gates

Run all gates in order. All must pass. If any fails, STOP and report.

**Note on commands**: All commands below are PowerShell. `Select-Object -First N` and `Select-Object -Last N` are the PowerShell equivalents of Unix `head -N` and `tail -N`.

### Gate 1 — Drift check

```powershell
git diff --stat 274fe06..HEAD -- tests/test_llama_cpp_adapter.py
```

**Expected**: empty output (no changes to this file since prompt-36).

If output is non-empty, the file has drifted since this plan was written. Compare the "Current state" excerpt in this plan against the live code. On mismatch, STOP and report — do not proceed.

### Gate 2 — File collects without `--ignore`

```powershell
python -m pytest tests/test_llama_cpp_adapter.py --collect-only -q
```

**Expected output** (when `llama_cpp` is not installed):
```
9 tests skipped in 0.XXs
```
Or:
```
tests/test_llama_cpp_adapter.py::TestLlamaCppAdapter::test_...
  ...
9 tests collected in 0.XXs
```
Either is acceptable. The key signal: no `ModuleNotFoundError`, no `Interrupted: 1 error during collection`.

**Failure mode**: If you see `ModuleNotFoundError: No module named 'llama_cpp'` followed by `Interrupted: 1 error during collection`, the `importorskip` line is in the wrong place, missing, or the import order is wrong. STOP and report.

### Gate 3 — Full suite runs without `--ignore`

```powershell
python -m pytest tests/ -q --tb=no
```

**Expected**: The suite runs to completion. The `test_llama_cpp_adapter.py` tests are reported as `SKIPPED` (9 skips expected on a machine without `llama_cpp` installed). No `Interrupted: 1 error during collection`. All other tests run as before.

**Specifically check the final summary line**. Before this fix, running without `--ignore` aborts with something like `1 error in X.XXs`. After this fix, the summary should be `N passed, 9 skipped, X failed, W warnings in XX.XXs` (numbers vary by environment). The key signal is the absence of `Interrupted` and the presence of `9 skipped`.

**Note on environment-specific failures**: If your environment is missing other optional deps (`pynvml`, `icalendar`, `faster_whisper`, `asyncpg`, `qdrant-client`), some of those tests will fail with `ModuleNotFoundError`. Those are pre-existing failures unrelated to this plan. The plan passes if:
1. No `Interrupted: N errors during collection` (collection succeeds)
2. The `test_llama_cpp_adapter.py` tests are SKIPPED (not errored)
3. The test count for non-llama_cpp tests is the same as before this plan (within ±0)

### Gate 4 — Test count is now stable without `--ignore`

Run this command and record the exact output:

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 1
```

**Expected**: A line like `N passed, 9 skipped, X failed, W warnings in XX.XXs`. Record N, X, and W exactly — these become the new baseline for Plan 37 onwards.

**This is the new baseline.** Every subsequent plan (37, 38, 39, 40) will use `python -m pytest tests/ -q` (no `--ignore`) and compare against this baseline. The baseline confusion that's been recurring since 35.6c ends here.

### Gate 5 — The 9 llama_cpp tests are skipped, not failed

```powershell
python -m pytest tests/test_llama_cpp_adapter.py -v --tb=no 2>&1 | Select-Object -Last 15
```

**Expected**: 9 lines like `SKIPPED [1] tests/test_llama_cpp_adapter.py:11: ModuleNotFoundError: No module named 'llama_cpp'` (or similar). The skip reason should mention `llama_cpp`.

**Failure mode**: If the tests show as `FAILED` or `ERROR` instead of `SKIPPED`, the `importorskip` didn't trigger. STOP and report.

### Gate 6 — Lint check on the modified file

```powershell
ruff check tests/test_llama_cpp_adapter.py
```

**Expected**: 0 errors. If ruff flags the new comment or the `importorskip` placement, fix it. If ruff is not installed, skip this gate and note it in the CHANGELOG.

## STOP conditions

- **If Gate 1 shows the file has drifted since prompt-36**, stop. Compare live code against the plan's "Current state" excerpt and report the mismatch.
- **If Gate 2 or Gate 3 shows `Interrupted: N errors during collection`**, stop. The `importorskip` line is in the wrong place. Report the exact error.
- **If any file outside `tests/test_llama_cpp_adapter.py` needs editing**, stop. This plan is one file, one line. Anything else is out of scope.
- **If the 9 llama_cpp tests show as FAILED or ERROR instead of SKIPPED**, stop. The `importorskip` didn't trigger correctly. Report the actual test status.

## Out of scope

- Deleting the `LlamaCppAdapter` entirely (it's dead code, but that's a separate decision)
- Adding `llama_cpp` to `requirements.txt` (it doesn't install on Windows per Phase 4 CHANGELOG; Linux CI might install it but it's a 5-10 min compile)
- Modifying `.github/workflows/ci.yml` (it already runs `pytest tests/ -v` without `--ignore`, which is what we want after this fix)
- Modifying any other test file that may have similar `ModuleNotFoundError` issues (`test_anthropic_adapter.py`, `test_gemini_adapter.py`, `test_postgres_backend.py`, `test_qdrant_backend.py` — these need their own `importorskip` or `pytest.importorskip` treatment, but that's Plan 38.5 territory)
- Fixing the test-count math in the prompt-36 CHANGELOG (that's historical; can't be fixed retroactively without rewriting history)

## Closing steps (after all gates pass)

1. `git add tests/test_llama_cpp_adapter.py`
2. `git commit -m "fix: importorskip llama_cpp in test file — collection no longer aborts"`
3. `git tag prompt-36.5`
4. `git show prompt-36.5 --stat` — verify the file list contains ONLY `tests/test_llama_cpp_adapter.py`. If any other file appears, `git tag -d prompt-36.5`, clean, re-tag.
5. Update `CHANGELOG.md` (append-only, using `Add-Content` per the handoff's PowerShell procedure) with:

```markdown
## 2026-06-18 HH:MM - Prompt 36.5: Fix llama_cpp test collection

### Files Modified
- tests/test_llama_cpp_adapter.py
  - Added `pytest.importorskip("llama_cpp")` after the module docstring and `import pytest` line, before `from adapters.llama_cpp import LlamaCppAdapter`
  - Added explanatory comment documenting why importorskip is needed
  - No other changes

### Implementation Notes
- No mid-prompt failures encountered
- Drift check passed: no changes to tests/test_llama_cpp_adapter.py since prompt-36
- All gates passed on first run

### Testing Results
- **Baseline**: N passed, X failed, W warnings (with --ignore=tests/test_llama_cpp_adapter.py)
- **Final**: N passed, 9 skipped, X failed, W warnings (WITHOUT --ignore)
- **Test Command**: `python -m pytest tests/ -q --tb=no`
- **Key change**: --ignore flag no longer needed; test_llama_cpp_adapter.py tests now SKIP cleanly instead of aborting collection
- **New baseline for Plan 37 onwards**: N passed, 9 skipped (record exact N here from Gate 4 output)

### Verification Gate Output
- **Gate 1 (Drift)**: empty output (no drift)
- **Gate 2 (Collection)**: 9 tests skipped in 0.XXs (or 9 tests collected)
- **Gate 3 (Full suite)**: N passed, 9 skipped, X failed (NO `Interrupted: N errors during collection`)
- **Gate 4 (Baseline)**: [paste exact Select-Object -Last 1 output here]
- **Gate 5 (Skip status)**: 9 SKIPPED lines mentioning llama_cpp
- **Gate 6 (Lint)**: 0 errors (or "ruff not installed, skipped")

### Checkpoint Commit
[commit hash]
```

6. Update `SOVEREIGN_AI_HANDOFF.md` (the GLM-format handoff — no Technical Debt table exists in this format; update the sections that do exist):
   - Update the "Last updated" line at the top to: `2026-06-18 — post prompt-36.5. llama_cpp test collection fixed; --ignore flag no longer needed.`
   - Update the "Test baseline" line to the new baseline from Gate 4: `N passed, 9 skipped, X failed, W warnings (measured with python -m pytest tests/ -q, no --ignore flag needed)`
   - In the "What works right now" section, no changes needed (the llama_cpp tests still don't run, they just skip cleanly now)
   - In the "What's broken right now" section, no changes needed (this plan doesn't fix any F-bugs)
   - In the "Built but not reachable" table — there is no row for the llama_cpp adapter or its tests in this table (the adapter is dead code, not an unreachable subsystem; the tests are now cleanly skipped). Do not add a row for it.
   - Update the canonical test command wherever it appears in the handoff. Search for `--ignore=tests/test_llama_cpp_adapter.py` and remove that flag from every command that contains it. After this update, the canonical test command is `python -m pytest tests/ -v` (no `--ignore`).

7. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
8. `git commit -m "docs: prompt-36.5 changelog and handoff update"`
9. `git push origin master && git push origin prompt-36.5`

## After Plan 36.5 lands

The foundation is now solid:
- F1, F2, F3, F5 fixed (prompt-36)
- F4 fixed (prompt-35.6f)
- llama_cpp collection fixed (prompt-36.5)
- Test baseline stable and comparable across local and CI
- `python -m pytest tests/ -q` (no flags) is the canonical test command

Plan 37 (Fix F6 — MemoryRouter call-signature mismatch across 15+ files) can now use the stable baseline. Plan 37's gates will use `python -m pytest tests/ -q` and the counts will be directly comparable to prompt-36.5's baseline. The test-count confusion that's been recurring since 35.6c ends here.
