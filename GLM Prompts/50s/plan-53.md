# Plan 53: Fix calendar test + B108 hardcoded temp files + datetime.utcnow deprecation

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result. If STOP fires, stop and report.
>
> **Mypy**: FILE-SCOPED only (L18). NEVER `mypy .`.
> **Commands**: PowerShell only (L21).

## Opening steps (run BEFORE Step 0)

1. **Verify previous prompt completed**:
   ```powershell
   git ls-remote --tags origin | findstr prompt-52
   ```
   If empty, STOP.

2. **Pull latest**:
   ```powershell
   git pull origin master
   ```

## Status
- Priority: P2
- Effort: M
- Risk: LOW (test-only changes)
- Depends on: prompt-52
- Planned at: commit prompt-52 (58f06c6), 2026-06-20
- Revision: REV1 (2026-06-20)
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 findings 1-2 (Step 3 pre-split into 3a/3b/3c/3d; bandit commands add --exclude __pycache__,.pytest_cache).
- Revision: REV3 (2026-06-20) — incorporates Claude round-2 finding 1 (Step 3d "7 files" corrected to "9 files"; total occurrences corrected from 109 to 81 based on per-file sum; Step 4.3 expected count updated).
- **Line numbers verified at clone SHA `81dd2d4`** (L20).

## Why this matters

3 test-suite issues block clean CI:
1. **Calendar test failure** — `tests/skills/test_calendar_skill.py:56` uses hardcoded date `20260620T140000Z` which is now in the past. `get_upcoming(days=7)` returns 0 events → `assert len(result) == 1` fails. This is the only failing test.
2. **22 B108 bandit findings** — tests create temp files like `"test.ics"` in the working directory instead of using `tempfile.mkdtemp()`. Risk of test pollution + bandit CI failure.
3. **81 `datetime.utcnow()` deprecation warnings** — Python 3.12+ deprecated `datetime.utcnow()`. Should use `datetime.now(timezone.utc)`. These warnings clutter test output. (Count corrected from 109 to 81 in REV3 — per-file breakdown sums to 81, not 109.)

## Current state

**Files in scope** (verified at SHA `81dd2d4`):

*Calendar test (1 file):*
- `tests/skills/test_calendar_skill.py:56` — `DTSTART:20260620T140000Z` (hardcoded, now in past)

*B108 hardcoded temp files (1 file, 22 occurrences):*
- `tests/skills/test_calendar_skill.py` — all tests use `"test.ics"` in working directory (lines 64, 78-79, 105, 115-116, 142, 153-154, 193, 206-207, 230, 246)

*datetime.utcnow (15 files, 81 occurrences):*
- `tests/test_approval_gate.py` (16), `tests/test_adapter_fallback.py` (15), `tests/skills/test_calendar_skill.py` (11), `tests/skills/test_reminder_skill.py` (9), `tests/skills/test_notes_skill.py` (7), `tests/skills/test_email_skill.py` (5), `tests/test_model_evaluator.py` (4), `tests/test_worker_persistence.py` (3), `tests/test_memory_scoping.py` (3), `tests/test_worker_factory.py` (2), `tests/test_escalation.py` (2), `tests/test_integration.py` (1), `tests/test_monitor_daemon.py` (1), `tests/test_web_server.py` (1), `tests/test_evaluator.py` (1)

**Step 0 — verify:**

0.1. `git rev-parse HEAD` — expected: descendant of prompt-52.
0.2. `git ls-remote --tags origin | findstr prompt-52` — confirm tag on origin.
0.3. `python -m pytest tests/ -q --tb=short | Select-Object -Last 3` — baseline: 1166 passed, 55 skipped, 1 failed (calendar). If different, STOP.
0.4. `Select-String -Path tests/skills/test_calendar_skill.py -Pattern "20260620" | Measure-Object -Line` — confirm hardcoded date exists. If 0, STOP.

## What to change

### Step 1 — Fix calendar test (1 file, fixes the failing test)

1.1. In `tests/skills/test_calendar_skill.py`, replace the hardcoded date `20260620T140000Z` with a dynamically generated future date. At line 56, change:
```python
DTSTART:20260620T140000Z
DTEND:20260620T150000Z
```
to:
```python
DTSTART:{future_date.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{future_date.strftime("%Y%m%dT%H%M%SZ")}
```
Where `future_date` is defined before the ICS content:
```python
from datetime import datetime, timedelta, timezone
future_date = datetime.now(timezone.utc) + timedelta(days=1)
```

**Note**: other tests in the same file (lines 93, 99, 130, 136) already use dynamic dates with `strftime` — follow the same pattern.

1.2. **Verification**:
```powershell
python -m pytest tests/skills/test_calendar_skill.py::TestCalendarSkill::test_get_upcoming_returns_correctly_parsed_events_from_test_ics_string -v
```
Expected: PASSED (was FAILED).

### Step 2 — Fix B108 hardcoded temp files (1 file, 22 occurrences)

2.1. In `tests/skills/test_calendar_skill.py`, replace all `"test.ics"` hardcoded paths with `tempfile.mkdtemp()` + `os.path.join()`. At the top of the file, add:
```python
import tempfile
```

2.2. In each test method, replace:
```python
# Before:
with open("test.ics", "wb") as f:
    ...
if os.path.exists("test.ics"):
    os.remove("test.ics")

# After:
test_dir = tempfile.mkdtemp()
test_file = os.path.join(test_dir, "test.ics")
with open(test_file, "wb") as f:
    ...
import shutil
shutil.rmtree(test_dir, ignore_errors=True)
```

**Note**: the `calendar_path` parameter in the skill constructor (line 25) also uses `"test.ics"` — update it to use the temp file path.

2.3. **Verification**:
```powershell
python -m pytest tests/skills/test_calendar_skill.py -v
```
Expected: all tests pass, 0 failed.
```powershell
bandit tests/skills/test_calendar_skill.py -ll
```
Expected: 0 B108 findings (was 22).

### Step 3 — Fix datetime.utcnow() deprecation (15 files, 81 occurrences)

3.1. For each file, replace `datetime.utcnow()` with `datetime.now(timezone.utc)`. Use `timezone.utc` (not `datetime.UTC`) for compatibility with all Python 3.x versions.

**Pattern**:
```python
# Before:
from datetime import datetime
...
timestamp = datetime.utcnow()

# After:
from datetime import datetime, timezone
...
timestamp = datetime.now(timezone.utc)
```

3a. **Top file: `tests/test_approval_gate.py`** (16 occurrences, ~32 lines). Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)`. Add `timezone` to import.

**Verification (3a)**:
```powershell
Select-String -Path tests/test_approval_gate.py -Pattern "utcnow" | Measure-Object -Line
```
Expected: 0 (was 16).

3b. **`tests/test_adapter_fallback.py` (15) + `tests/skills/test_calendar_skill.py` (11)** = 26 occurrences, ~52 lines. Same replacement pattern.

**Verification (3b)**:
```powershell
Select-String -Path tests/test_adapter_fallback.py -Pattern "utcnow" | Measure-Object -Line
Select-String -Path tests/skills/test_calendar_skill.py -Pattern "utcnow" | Measure-Object -Line
```
Expected: 0 for both.

3c. **`tests/skills/test_reminder_skill.py` (9) + `tests/skills/test_notes_skill.py` (7) + `tests/skills/test_email_skill.py` (5)** = 21 occurrences, ~42 lines. Same pattern.

**Verification (3c)**:
```powershell
Select-String -Path tests/skills/test_reminder_skill.py -Pattern "utcnow" | Measure-Object -Line
Select-String -Path tests/skills/test_notes_skill.py -Pattern "utcnow" | Measure-Object -Line
Select-String -Path tests/skills/test_email_skill.py -Pattern "utcnow" | Measure-Object -Line
```
Expected: 0 for all three.

3d. **Remaining 9 files: `tests/test_model_evaluator.py` (4), `tests/test_worker_persistence.py` (3), `tests/test_memory_scoping.py` (3), `tests/test_worker_factory.py` (2), `tests/test_escalation.py` (2), `tests/test_integration.py` (1), `tests/test_monitor_daemon.py` (1), `tests/test_web_server.py` (1), `tests/test_evaluator.py` (1)** = 18 occurrences, ~36 lines. Same pattern.

**Verification (3d)**:
```powershell
Select-String -Path tests/test_model_evaluator.py tests/test_worker_persistence.py tests/test_memory_scoping.py tests/test_worker_factory.py tests/test_escalation.py tests/test_integration.py tests/test_monitor_daemon.py tests/test_web_server.py tests/test_evaluator.py -Pattern "utcnow" | Measure-Object -Line
```
Expected: 0.

3.2. **Full verification** (file-scoped — pick 3 representative files):
```powershell
python -m pytest tests/test_approval_gate.py tests/test_adapter_fallback.py tests/skills/test_calendar_skill.py -q --tb=short | Select-Object -Last 3
```
Expected: all pass, 0 failed.

### Step 4 — Verify no regressions

4.1. `python -m pytest tests/ -q --tb=short | Select-Object -Last 3` — expected: 1167 passed (calendar now passes!), 55 skipped, 0 failed. If still 1 failed, STOP.

4.2. `bandit tests/ -ll --exclude __pycache__,.pytest_cache | Select-String "B108" | Measure-Object -Line` — expected: 0 (was 22). If >0, run `bandit tests/skills/test_calendar_skill.py -ll` to confirm the target file is fixed, then investigate remaining findings.

4.3. `python -m pytest tests/ -q --tb=short 2>&1 | Select-String "utcnow" | Measure-Object -Line` — expected: 0 (was 81). Note: this checks warnings output.

## Verification gates

1. `python -m pytest tests/skills/test_calendar_skill.py -v` — expected: all pass, 0 failed (was 1 failed).
2. `bandit tests/skills/test_calendar_skill.py -ll --exclude __pycache__,.pytest_cache` — expected: 0 B108 (was 22).
3. `Select-String -Path tests/test_approval_gate.py -Pattern "utcnow" | Measure-Object -Line` — expected: 0 (was 16).
4. `python -m pytest tests/ -q --tb=short | Select-Object -Last 3` — expected: 1167 passed, 55 skipped, 0 failed.
5. `bandit tests/ -ll --exclude __pycache__,.pytest_cache | Select-String "B108" | Measure-Object -Line` — expected: 0 (was 22).
6. `ruff check tests/skills/test_calendar_skill.py tests/test_approval_gate.py tests/test_adapter_fallback.py` — expected: 0 errors.

## STOP conditions

- **S0**: HEAD not descendant of prompt-52. STOP.
- **S1**: prompt-52 tag absent from origin. STOP.
- **S2**: Calendar test already passing (hardcoded date already fixed). STOP.
- **S3**: Test baseline not 1166/55/1 (calendar). STOP.
- **S4**: File outside in-scope list. STOP.
- **S5**: New test failure. STOP.
- **S6**: >50 lines per step. STOP. **Step 3 is pre-split into 3a/3b/3c/3d (REV2), each under 50 lines — S6 does not apply to Step 3.**
- **S7**: Gate without evidence. STOP (Rule 19).
- **S8**: Closing step without evidence. STOP (Rule 21/L17).
- **S9**: C5 reveals out-of-scope file. STOP.
- **S10**: C11 tag-push fails. STOP.

## Closing steps (mandatory — Rule 21)

[Standard C1-C11 from handoff template]

**C6 CHANGELOG**:
```
## 2026-06-21 HH:MM — prompt-53

**Plan**: Test suite health — calendar test fix + B108 + datetime.utcnow deprecation

**Changed**:
- tests/skills/test_calendar_skill.py: fixed hardcoded date → dynamic future date; replaced "test.ics" with tempfile.mkdtemp() (22 B108 fixed)
- 15 test files: datetime.utcnow() → datetime.now(timezone.utc) (81 occurrences)

**Results**:
- Tests: 1167 passed (was 1166), 55 skipped, 0 failed (calendar fixed!)
- Bandit B108: 0 (was 22)
- utcnow warnings: 0 (was 81)
- Tag: prompt-53 verified on origin
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

- Production code changes (only test files).
- F401 bulk cleanup (Plan 54).
- Marine stack (Plan 55).
- Dependency updates (Plan 56).
- Dead code cleanup (Plan 57).
- The `datetime.utcnow()` calls in PRODUCTION code (not tests) — those are a separate plan.

## For Claude review

1. The calendar test fix uses `datetime.now(timezone.utc) + timedelta(days=1)` for the future date. Is `timezone.utc` correct, or should it be `datetime.UTC` (Python 3.11+)? Check the project's Python version requirement.

2. Step 2 (B108 fix) touches the same file as Step 1 (calendar test). Should these be combined into one step, or is keeping them separate (Step 1 = date fix, Step 2 = temp file fix) clearer for verification?

3. Step 3 has 81 occurrences across 15 files. S6 says >50 lines per step triggers STOP. Each `utcnow()` replacement is 1 line (the call) + possibly 1 line (the import). 81 occurrences × 2 lines = 162 lines total. This MUST be split into sub-steps. The plan notes this in S6 but doesn't pre-split. Should it pre-split into 3a/3b/3c?

4. `bandit tests/ -ll` in Gate 5 — does this need `--exclude` flags? The tests/ directory shouldn't have a venv, but worth confirming.

5. Gate 3 checks only `test_approval_gate.py` for utcnow. Should it check all 15 files, or is 1 representative file sufficient?
