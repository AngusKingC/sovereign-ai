# Plan 42: Broad-except audit, part 2 (system/)

> **Executor instructions**: This plan addresses the broad-except pattern in `system/` files — the second layer of the audit started in Plan 41 (core/). Verified scope: 157 except blocks across 10 system/ files, 87 with `pass` (Rule 17 violations). Same three-option classification approach as Plan 41: (a) cleanup path with WARNING trace, (b) specific exception type, (c) remove try/except.
>
> **Critical**: This is a refactoring plan, not a feature plan. Do NOT change behavior — only change how exceptions are handled. If removing a try/except would change behavior, STOP and apply behavior-preserving fix instead.
>
> **No `--ignore` flag** in any commands. Per the post-prompt-41 fix-up, the standard measurement command is `python -m pytest tests/ -q --tb=no` (no flags). `llama_cpp` is installed in the environment, so `test_llama_cpp_adapter.py` tests are included in the count.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-41..HEAD -- system/ SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `system/`: expected empty. For handoff/CHANGELOG: review per known-landmine procedure (docs files may have drift from the prompt-41 fix-up commit `1227534`).

## Status

- **Priority**: P1 (systemic code quality — continues Plan 41's broad-except audit)
- **Effort**: M-L (10 files, 87 `pass` patterns — larger than Plan 41's 5 files / 29 patterns)
- **Risk**: MEDIUM (exception handling changes can subtly alter behavior — must verify no test regressions)
- **Depends on**: prompt-41 (commit `18ce278`, tag `prompt-41`) + prompt-41 fix-up (commit `1227534` on master)
- **Planned at**: master HEAD post-prompt-41-fixup, 2026-06-19
- **In scope**:
  - Production: `system/resource_manager.py` (57 except, 39 with pass — largest)
  - Production: `system/model_acquisition.py` (22 except, 11 with pass)
  - Production: `system/profiler.py` (20 except, 10 with pass)
  - Production: `system/model_registry.py` (18 except, 12 with pass)
  - Production: `system/monitor_daemon.py` (15 except, 9 with pass)
  - Production: `system/voice_daemon.py` (6 except, 5 with pass)
  - Production: `system/trajectory_exporter.py` (1 except, 1 with pass — minimal)
  - Production: `system/worker_persistence.py` (6 except, 0 with pass — verify only)
  - Production: `system/retention_manager.py` (10 except, 0 with pass — verify only)
  - Production: `system/retention_daemon.py` (2 except, 0 with pass — verify only)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (update Rule 17 compliance status for system/, update "Recently fixed" section)
  - Changelog: `CHANGELOG.md` (per-step literal evidence)
- **Out of scope**: broad-except audit for skills/ (Plan 43), web/ (separate plan), adapters/ (separate plan), gateways/ (separate plan), ruff/mypy triage, trajectory_exporter functional redesign (Plan 45), marine stack

## Why this matters

Plan 41 made `core/` Rule 17 compliant (zero `except Exception: pass` patterns without inline comment + WARNING trace). This plan extends the audit to `system/` — the next layer in the dependency hierarchy.

**Verified scope** (by grepping each system/ file):

| File | except blocks | with `pass` |
|---|---|---|
| `resource_manager.py` | 57 | 39 |
| `model_acquisition.py` | 22 | 11 |
| `profiler.py` | 20 | 10 |
| `model_registry.py` | 18 | 12 |
| `monitor_daemon.py` | 15 | 9 |
| `voice_daemon.py` | 6 | 5 |
| `trajectory_exporter.py` | 1 | 1 |
| `worker_persistence.py` | 6 | 0 (verify only) |
| `retention_manager.py` | 10 | 0 (verify only) |
| `retention_daemon.py` | 2 | 0 (verify only) |
| **Total** | **157** | **87** |

87 `pass` patterns are Rule 17 violations. Each silently swallows exceptions, hiding potential bugs (recurring mistake #4).

**Test coverage**: 8 of 10 system/ files have test files (only `retention_daemon.py` and `voice_daemon.py` don't). This means most refactoring can be verified via existing tests.

**Expected outcome**: 0 broad-except violations of Rule 17 in system/ (all 87 `pass` patterns addressed). Test suite stays at 1127 passed, 0 failed, 0 warnings (no behavior changes).

## What's broken

### A. 87 `except Exception: pass` patterns across 7 system/ files

Verified by grepping each file. Examples of the pattern (same as Plan 41):

```python
# Silent swallow — no comment, no trace, no re-raise
except Exception:
    pass
```

Each pattern needs to be classified:
- **Cleanup path** (in finally, or after primary operation completed) → add inline comment + WARNING trace event per Rule 17
- **Expected exception** (network, parse, etc.) → replace with specific exception type
- **Shouldn't be caught** → remove try/except, let it propagate (FLAG THIS — may be behavior change)

### B. 3 system/ files have 0 `pass` patterns but still have except blocks

`worker_persistence.py` (6 except, 0 pass), `retention_manager.py` (10 except, 0 pass), `retention_daemon.py` (2 except, 0 pass) — these files already handle exceptions properly (with logging, re-raise, or specific types). Quick verification that existing handling is Rule 17 compliant.

## What to change

### Step 1 — Audit `system/resource_manager.py` (largest: 57 except, 39 with pass)

**File**: `system/resource_manager.py`

For each of the 39 `except Exception: pass` patterns, classify and fix per the three-option approach:

1. Read each `except Exception: pass` block in context (surrounding 10 lines)
2. Classify:
   - **Cleanup path** → add inline comment + WARNING trace event
   - **Expected exception** → replace with specific exception type
   - **Shouldn't be caught** → remove try/except (FLAG for GLM review — may be behavior change)
3. For each fix, paste before/after diff to CHANGELOG as evidence

**Batching recommendation for this file specifically**: `resource_manager.py` has 39 patterns — the highest density in this plan. To make regressions easier to isolate, consider fixing in 2-3 batches (e.g., ~13 patterns per batch) and running `python -m pytest tests/test_resource_manager.py -v --tb=short` after each batch rather than all 39 at once. This is a recommendation, not a requirement — if you prefer to fix all 39 then test once, that's acceptable, but a regression will be harder to isolate to a specific change.

**Example fix for cleanup path** (same pattern as Plan 41):
```python
# Before:
except Exception:
    pass

# After (cleanup path — emit trace event per Rule 17):
except Exception as e:
    # Cleanup path — don't mask the original error, but log for debugging
    # Per Rule 17: broad except requires inline comment + WARNING trace
    await self._emitter.emit(TraceEvent(
        event_type=TraceEventType.OPERATION_ERROR,
        component=TraceComponent.SYSTEM,
        level=TraceLevel.WARNING,
        message=f"Cleanup failed: {type(e).__name__}: {e}",
        data={"exception_type": type(e).__name__, "exception_message": str(e)},
        duration_ms=0,
    ))
```

**If removing a try/except would change behavior**: STOP. Document the specific case in CHANGELOG. Apply the cleanup-path fix (with WARNING trace) instead and note "behavior-preserving — should be reviewed for whether exception should propagate."

**Verify** (paste literal output):
```powershell
# Count remaining broad-except + pass patterns
Select-String -Path system\resource_manager.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0 (all 39 pass patterns addressed)

# Run tests
python -m pytest tests/test_resource_manager.py -v --tb=short
# All tests still pass
```

### Step 2 — Audit `system/model_acquisition.py` (22 except, 11 with pass)

**File**: `system/model_acquisition.py`

Same procedure as Step 1. 11 `pass` patterns to address.

**Verify** (paste literal output):
```powershell
Select-String -Path system\model_acquisition.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_model_acquisition.py -v --tb=short
# All tests still pass
```

### Step 3 — Audit `system/profiler.py` (20 except, 10 with pass)

**File**: `system/profiler.py`

Same procedure. 10 `pass` patterns.

**Verify** (paste literal output):
```powershell
Select-String -Path system\profiler.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_profiler.py -v --tb=short
# All tests still pass
```

### Step 4 — Audit `system/model_registry.py` (18 except, 12 with pass)

**File**: `system/model_registry.py`

Same procedure. 12 `pass` patterns.

**Verify** (paste literal output):
```powershell
Select-String -Path system\model_registry.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_model_registry.py -v --tb=short
# All tests still pass
```

### Step 5 — Audit `system/monitor_daemon.py` (15 except, 9 with pass)

**File**: `system/monitor_daemon.py`

Same procedure. 9 `pass` patterns.

**Verify** (paste literal output):
```powershell
Select-String -Path system\monitor_daemon.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_monitor_daemon.py -v --tb=short
# All tests still pass
```

### Step 6 — Audit `system/voice_daemon.py` (6 except, 5 with pass)

**File**: `system/voice_daemon.py`

Same procedure. 5 `pass` patterns. Note: no test file exists for `voice_daemon.py` — verify via import and basic smoke test:

```powershell
python -c "from system.voice_daemon import VoiceDaemon; print('import OK')"
```

**Verify** (paste literal output):
```powershell
Select-String -Path system\voice_daemon.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -c "from system.voice_daemon import VoiceDaemon; print('import OK')"
# Should print "import OK" without errors
```

### Step 7 — Audit `system/trajectory_exporter.py` (1 except, 1 with pass)

**File**: `system/trajectory_exporter.py`

Minimal — only 1 `pass` pattern. Quick fix.

**Note**: `trajectory_exporter.py` has a Plan 45 deferral for functional redesign (the 6 skipped tests in `test_trajectory_exporter.py`). This broad-except fix is separate from the Plan 45 work — just address the 1 `pass` pattern, don't touch the deferred functionality.

**Verify** (paste literal output):
```powershell
Select-String -Path system\trajectory_exporter.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_trajectory_exporter.py -v --tb=short
# 6 tests still SKIPPED (Plan 45 deferral — unchanged)
```

### Step 8 — Verify 3 files with 0 `pass` patterns

**Files**: `system/worker_persistence.py` (6 except, 0 pass), `system/retention_manager.py` (10 except, 0 pass), `system/retention_daemon.py` (2 except, 0 pass)

These files already handle exceptions without bare `pass`. Quick verification that existing handling is Rule 17 compliant (each except block either has an inline comment, specific exception type, or re-raises).

**Procedure**: For each file, read each except block and confirm:
- Has inline comment explaining why the exception is caught, OR
- Uses specific exception type (not bare `Exception`), OR
- Re-raises after logging/handling

If any except block is non-compliant (bare `except Exception:` with `pass` or swallow without comment), apply the three-option fix.

**Verify** (paste literal output):
```powershell
# Confirm 0 pass patterns (should already be 0)
Select-String -Path system\worker_persistence.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
Select-String -Path system\retention_manager.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
Select-String -Path system\retention_daemon.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# All should be 0

# Run available tests
python -m pytest tests/test_worker_persistence.py tests/test_retention_manager.py -v --tb=short
# All tests still pass (retention_daemon has no test file — verify via import)
python -c "from system.retention_daemon import RetentionDaemon; print('import OK')"
```

### Step 9 — Update handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`

1. Update "Last updated" to reference prompt-42.
2. Update Rule 17 compliance status in "Architecture rules" section — note that system/ is now compliant (87 `pass` patterns addressed).
3. Update "Recently fixed" section — add prompt-42 entry.
4. Update "Next 5 prompts" to reflect Plan 43 (broad-except audit skills/) as next in queue.
5. Update test baseline if changed (should be unchanged: 1127 passed, 0 warnings).

### Step 10 — Update CHANGELOG with literal evidence

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 evidence: `resource_manager.py` before/after diff summary + test results
- Step 2 evidence: `model_acquisition.py` before/after diff summary + test results
- Step 3 evidence: `profiler.py` before/after diff summary + test results
- Step 4 evidence: `model_registry.py` before/after diff summary + test results
- Step 5 evidence: `monitor_daemon.py` before/after diff summary + test results
- Step 6 evidence: `voice_daemon.py` before/after diff summary + import verification
- Step 7 evidence: `trajectory_exporter.py` before/after diff summary + test results
- Step 8 evidence: 3 files verification output
- Final test counts: 1127 passed, 61 skipped, 0 failed, 0 warnings (unchanged — no behavior changes)
- **Paste literal `Select-Object -Last 3` output of `python -m pytest tests/ -q --tb=no`** as proof of final count (per "Test count assertions without measurement" landmine)

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-41..HEAD -- system/
```

**Expected**: empty output.

### Gate 2 — Zero `except Exception: pass` in system/

```powershell
# Count remaining broad-except + pass patterns across all system files
Get-ChildItem -Path system\ -Filter "*.py" | ForEach-Object {
    $matches = Select-String -Path $_.FullName -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" }
    if ($matches.Count -gt 0) {
        Write-Host "$($_.Name): $($matches.Count) violations"
    }
}
```

**Expected**: no output (zero violations across all system files).

**Scope note** (same as Plan 41): This grep catches bare `except Exception: pass` patterns. It does NOT catch `except Exception as e:` blocks that swallow via logging-only. Those are addressed in the Step 1-8 procedures but not verified by this gate — they will be caught in ruff triage (Plan 46).

### Gate 3 — All system tests still pass

```powershell
python -m pytest tests/test_resource_manager.py tests/test_model_acquisition.py tests/test_profiler.py tests/test_model_registry.py tests/test_monitor_daemon.py tests/test_worker_persistence.py tests/test_retention_manager.py tests/test_trajectory_exporter.py -v --tb=short
```

**Expected**: all tests pass (no behavior changes from exception handling refactoring). trajectory_exporter tests still show 6 SKIPPED (Plan 45 deferral — unchanged).

### Gate 4 — Full test suite unchanged

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 3
```

**Expected**:
- Passed: 1127 (unchanged from prompt-41 fix-up)
- Skipped: 61 (unchanged)
- Failed: 0
- Warnings: 0

**Acceptable ranges**:
- Passed: {1125, 1126, 1127, 1128, 1129} — small variations OK
- Skipped: {60, 61, 62}
- Failed: {0}
- Warnings: {0}

**Paste literal output to CHANGELOG** — do NOT assert the count from memory (per "Test count assertions without measurement" landmine).

### Gate 5 — Handoff updated

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "prompt-42"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "system/.*Rule 17 compliant\|system/ is now compliant"
```

**Expected**: at least 1 match each.

### Gate 6 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-42
```

**Expected**: 1 match. **Do not skip this step.**

## STOP conditions

- **If removing a try/except would change behavior**: STOP. Document the specific case. Apply behavior-preserving fix (cleanup path with WARNING trace) instead. Note "should be reviewed for whether exception should propagate" in CHANGELOG.
- **If any system test fails after broad-except refactoring**: STOP. The refactoring introduced a behavior change. Investigate root cause.
- **If Gate 4 shows test count change**: STOP. Investigate whether the refactoring caused test failures or new skips. Paste literal output.
- **If Gate 4 shows new warnings**: STOP. The refactoring introduced a new warning. Investigate.
- **If Step 8 verification reveals `pass` patterns in the expected-clean files** (`worker_persistence.py`, `retention_manager.py`, `retention_daemon.py`): STOP. Report to GLM — these files were listed as 0 violations based on GLM's grep. Do not fix unilaterally; the scope of this plan covers only the 7 files listed in Steps 1-7. If the grep counts were wrong, the plan scope needs re-evaluation before proceeding.
- **If Gate 6 shows no match**: push the tag, re-verify.
- **If you find yourself about to assert a test count without measuring**: STOP. Per "Test count assertions without measurement" landmine, always paste literal `Select-Object -Last 3` output.
- **If you find yourself about to defer any step citing "per memory" or "Mistake Pattern N"**: STOP. Per landmine, Devin memories are not authoritative.

## Out of scope

- Broad-except audit for skills/ (Plan 43)
- Broad-except audit for web/, adapters/, gateways/ (separate plans)
- ruff/mypy triage
- trajectory_exporter functional redesign (Plan 45 — the 6 skipped tests stay)
- marine stack
- Re-verification of blocked adapters from prompt-39/40
- Production adapter code changes (per scope-creep landmine, STOP and report)

## Closing steps

1. `git add system/resource_manager.py system/model_acquisition.py system/profiler.py system/model_registry.py system/monitor_daemon.py system/voice_daemon.py system/trajectory_exporter.py system/worker_persistence.py system/retention_manager.py system/retention_daemon.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md`
   - (Only add files that were actually modified — the 3 "verify only" files may not need changes)
2. `git commit -m "fix: prompt-42 — broad-except audit (system/) per Rule 17"`
3. `git tag prompt-42`
4. `git show prompt-42 --stat` — verify file list
5. `git rev-parse prompt-42` — confirm hash
6. Update `CHANGELOG.md` (append-only) with all step evidence per Rule 19 — **including literal test count output**
7. Update `SOVEREIGN_AI_HANDOFF.md` per Step 9
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-42 changelog and handoff update"`
10. `git push origin master && git push origin prompt-42`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-42` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 42 lands

**System/ is Rule 17 compliant** — zero `except Exception: pass` patterns without inline comment + WARNING trace.

**Test suite unchanged**: 1127 passed, 61 skipped, 0 failed, 0 warnings. Exception handling refactoring preserved all behavior.

**Remaining broad-except audit work**:
- Plan 43: skills/ (~183 sites per session 2 handoff)
- Separate plans: web/, adapters/, gateways/

**Then horizontal cleanup queue**:
- Plan 44: InputSanitiser wiring
- Plan 45: InputSanitiser redesign + trajectory_exporter functional redesign
- Plan 46: ruff triage
- Plan 47: mypy triage
- Plan 48+: graphify integration, marine stack

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This plan audits broad-except patterns in system/ — continues Plan 41's audit. Check that:

1. **Is the scope manageable for one plan?** 87 `pass` patterns across 7 files (plus 3 verify-only files). Plan 41 handled 29 patterns across 5 files. This is 3x the scope. Should it be split (e.g., one plan for the top 3 files, another for the rest)?

2. **Is the three-option classification approach consistent with Plan 41?** Same options: (a) cleanup path with WARNING trace, (b) specific exception type, (c) remove try/except. Same STOP condition for behavior changes. Is this the right approach for system/ files which may have different patterns than core/?

3. **Is the `trajectory_exporter.py` scope correct?** Step 7 addresses 1 `pass` pattern in trajectory_exporter.py but explicitly says "don't touch the deferred functionality" (Plan 45). Is this scope boundary clear?

4. **Is the Gate 4 evidence requirement strong enough?** Per the new "Test count assertions without measurement" landmine, Gate 4 requires pasting literal `Select-Object -Last 3` output. Is this sufficient to prevent the assertion-without-measurement pattern?

5. **Are the 3 verify-only files (worker_persistence, retention_manager, retention_daemon) handled correctly?** Step 8 says "quick verification" — but what if verification reveals non-compliant patterns? Should there be a STOP condition?

6. **No known landmines violated**:
   - Tag-push gate (closing step 11) ✅
   - Rule 19 evidence requirement ✅
   - No `global_rules.md` citations ✅
   - No "per memory" citations ✅
   - No re-guessing disproved hypotheses ✅
   - Drift check distinguishes code vs docs ✅
   - Test-count methodology documented (no `--ignore`, literal output required) ✅
   - "No interactive shell" landmine — N/A (no verification work) ✅
   - Scope creep landmine — N/A (no production adapter changes) ✅
   - "Test count assertions without measurement" landmine — Gate 4 requires literal output ✅
