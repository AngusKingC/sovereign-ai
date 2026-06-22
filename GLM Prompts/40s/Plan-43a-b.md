# Plan 43: Broad-except audit, part 3 (skills/)

> **Executor instructions**: This plan addresses the broad-except pattern in `skills/` files — the third layer of the audit started in Plan 41 (core/) and continued in Plan 42 (system/). Verified scope: ~183 `pass` patterns per session 2 handoff. Same three-option classification approach as Plans 41 and 42: (a) cleanup path with WARNING trace, (b) specific exception type, (c) remove try/except.
>
> **Critical**: This is a refactoring plan, not a feature plan. Do NOT change behavior — only change how exceptions are handled. If removing a try/except would change behavior, STOP and apply behavior-preserving fix instead.
>
> **No `--ignore` flag** in any commands. Standard measurement command is `python -m pytest tests/ -q --tb=no`.
>
> **Grep methodology**: Use `-match "pass"` (not `pass$`) per the prompt-42 fix — the `pass$` pattern misses `except Exception: pass  # comment` variants with inline comments.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-42..HEAD -- skills/ SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `skills/`: expected empty. For handoff/CHANGELOG: review per known-landmine procedure.

## Status

- **Priority**: P1 (systemic code quality — continues Plan 42's broad-except audit)
- **Effort**: L (183 sites — ~3x larger than Plan 42's 87 patterns; may be split into Plan 43a/43b)
- **Risk**: MEDIUM (exception handling changes can subtly alter behavior — must verify no test regressions)
- **Depends on**: prompt-42 (tag `prompt-42`)
- **Planned at**: master HEAD post-prompt-42
- **In scope**:
  - All `skills/*.py` files with `except Exception: pass` patterns (~183 sites — exact per-file breakdown to be determined in Step 0)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (update Rule 17 compliance status for skills/, update "Recently fixed" section)
  - Changelog: `CHANGELOG.md` (per-step literal evidence)
- **Out of scope**: broad-except audit for web/, adapters/, gateways/ (separate plans), ruff/mypy triage, marine stack

## Why this matters

Plans 41 and 42 made `core/` and `system/` Rule 17 compliant. This plan extends the audit to `skills/` — the next layer in the dependency hierarchy.

~183 `pass` patterns silently swallow exceptions, hiding potential bugs (recurring mistake #4). The `-match "pass"` grep (rather than `pass$`) is required here — the prompt-42 verification revealed the narrower pattern misses blocks with trailing inline comments.

**Expected outcome**: 0 broad-except violations of Rule 17 in skills/ (all ~183 `pass` patterns addressed). Test suite stays at current baseline (paste literal count from Gate 4 — do NOT assert from memory).

## Pre-flight check (run before Step 0)

**Confirm prompt-42 Gate 4 output exists in CHANGELOG before proceeding.** The Gate 4 baseline for this plan is carried forward from prompt-42's literal test count output — not from memory and not assumed to be 1127.

```powershell
Select-String -Path CHANGELOG.md -Pattern "\d+ passed"
```

**Expected**: at least one match showing literal pytest output from prompt-42's Gate 4. If this match is missing — STOP. Retrieve the actual count from `git show prompt-42` or re-run the full suite at prompt-42 before proceeding. Do not continue without a confirmed baseline.

## Step 0 — Per-file breakdown (run before any fixes)

Before touching any file, get the exact per-file counts:

```powershell
Get-ChildItem -Path skills\ -Filter "*.py" | ForEach-Object {
    $matches = Select-String -Path $_.FullName -Pattern "except Exception" -Context 0,1 |
        Where-Object { $_.Context.PostContext -match "pass" }
    if ($matches.Count -gt 0) {
        Write-Host "$($_.Name): $($matches.Count) violations"
    }
}
```

Paste literal output to CHANGELOG. Use this to decide whether to split into Plan 43a/43b:

- **If any single file has 40+ patterns**: consider batching within that file (same recommendation as `resource_manager.py` in Plan 42)
- **If total confirmed count exceeds 200**: STOP and split into Plan 43a/43b before proceeding — see split boundary below

**Split boundary (if triggered)**: 43a = all files with 20+ violations (largest files first); 43b = all files with fewer than 20 violations (remainder). Apply this boundary mechanically — do not make a judgment call on where to split.

## What's broken

### A. ~183 `except Exception: pass` patterns across skills/ files

Same pattern as Plans 41 and 42:

```python
# Silent swallow — no comment, no trace, no re-raise
except Exception:
    pass

# Also caught by -match "pass" (missed by pass$):
except Exception:
    pass  # intentional
```

Each pattern needs classification:
- **Cleanup path** → add inline comment + WARNING trace event per Rule 17
- **Expected exception** → replace with specific exception type
- **Shouldn't be caught** → remove try/except (FLAG — may be behavior change)

### B. Grep methodology correction

Plans 41 and 42 used `pass$`. This plan uses `-match "pass"` throughout, per the prompt-42 fix-up finding. All verification commands below reflect this.

## Steps 1–N — Per-file audit

*(Exact file list and step count populated after Step 0 output. Template for each file:)*

**File**: `skills/<filename>.py`

1. Read each `except Exception: pass` block in context (surrounding 10 lines)
2. Classify and fix per three-option approach
3. Paste before/after diff to CHANGELOG as evidence

**Verify after each file**:
```powershell
Select-String -Path skills\<filename>.py -Pattern "except Exception" -Context 0,1 |
    Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0
```

Run per-file tests if a test file exists:
```powershell
python -m pytest tests/test_<filename>.py -v --tb=short
```

## Completion gates

### Gate 1 — Drift check clean

```powershell
git diff --stat prompt-42..HEAD -- skills/
```

**Expected**: empty output.

### Gate 2 — Zero `except Exception: pass` in skills/

```powershell
Get-ChildItem -Path skills\ -Filter "*.py" | ForEach-Object {
    $matches = Select-String -Path $_.FullName -Pattern "except Exception" -Context 0,1 |
        Where-Object { $_.Context.PostContext -match "pass" }
    if ($matches.Count -gt 0) {
        Write-Host "$($_.Name): $($matches.Count) violations"
    }
}
```

**Expected**: no output.

### Gate 3 — Per-file tests pass

```powershell
python -m pytest tests/test_<file1>.py tests/test_<file2>.py ... -v --tb=short
```

*(File list populated after Step 0.)*

### Gate 4 — Full test suite unchanged

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 3
```

**Paste literal output to CHANGELOG** — do NOT assert count from memory. Compare against prompt-42's literal Gate 4 output confirmed in the pre-flight check.

### Gate 5 — Handoff updated

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "prompt-43"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "skills/.*Rule 17 compliant\|skills/ is now compliant"
```

**Expected**: at least 1 match each.

### Gate 6 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-43
```

**Expected**: 1 match. **Do not skip this step.**

## STOP conditions

- **If pre-flight check finds no prompt-42 Gate 4 output in CHANGELOG**: STOP. Retrieve the baseline before proceeding.
- **If Step 0 count exceeds 200**: STOP. Split into Plan 43a/43b using the defined split boundary (20+ violations → 43a; remainder → 43b) before proceeding.
- **If removing a try/except would change behavior**: STOP. Document. Apply behavior-preserving fix instead.
- **If any test fails after refactoring**: STOP. The refactoring introduced a behavior change. Investigate.
- **If Gate 4 shows test count change or new warnings**: STOP. Investigate before continuing.
- **If Gate 6 shows no match**: push the tag, re-verify.
- **If you find yourself about to assert a test count without measuring**: STOP. Always paste literal `Select-Object -Last 3` output.
- **If you find yourself about to defer any step citing "per memory"**: STOP. Devin memories are not authoritative.

## Out of scope

- Broad-except audit for web/, adapters/, gateways/ (separate plans)
- ruff/mypy triage (Plan 46/47)
- marine stack
- Production adapter code changes (scope-creep landmine — STOP and report)

## Closing steps

1. `git add skills/ SOVEREIGN_AI_HANDOFF.md CHANGELOG.md`
   *(Directory-level add is safe here — Gate 1 drift check already confirmed no unintended changes exist in skills/)*
2. `git commit -m "fix: prompt-43 — broad-except audit (skills/) per Rule 17"`
3. `git tag prompt-43`
4. `git show prompt-43 --stat` — verify file list
5. `git rev-parse prompt-43` — confirm hash
6. Update `CHANGELOG.md` with all step evidence including literal test count output
7. Update `SOVEREIGN_AI_HANDOFF.md` per handoff conventions
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-43 changelog and handoff update"`
10. `git push origin master && git push origin prompt-43`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-43` — **do not skip**.

## After Plan 43 lands

**skills/ is Rule 17 compliant** — zero `except Exception: pass` patterns without inline comment + WARNING trace.

**Remaining broad-except audit work**:
- Separate plans: web/, adapters/, gateways/

**Then horizontal cleanup queue**:
- Plan 44: InputSanitiser wiring
- Plan 45: InputSanitiser redesign + trajectory_exporter functional redesign
- Plan 46: ruff triage
- Plan 47: mypy triage
