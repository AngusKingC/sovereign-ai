# Prompt-41 Fix-up: Correct test baseline + investigate warning

> **Executor instructions**: Small docs + investigation fix-up for prompt-41. No new tag. The prompt-41 CHANGELOG entry and handoff claim "~1124 passed, 0 warnings" but actual measurement is "1118 passed, 1 warning." This is a Rule 19 violation (gate marked PASSED without literal evidence) that needs correction.
>
> **Do NOT use `--ignore=tests/test_llama_cpp_adapter.py`** in any commands. The test file has `pytest.importorskip("llama_cpp")` which handles the missing dependency cleanly. If collection fails without `--ignore`, that's a separate bug to investigate — not a reason to keep `--ignore`.

## Status

- **Priority**: P0 (Rule 19 violation — evidence gap in authoritative records)
- **Effort**: S (2 commands + docs update)
- **Risk**: LOW (docs-only commit, no code changes unless warning investigation reveals an issue)
- **Depends on**: prompt-41 (commit `18ce278`, tag `prompt-41`)
- **In scope**: `CHANGELOG.md` (correct prompt-41 test results), `SOVEREIGN_AI_HANDOFF.md` (correct test baseline), possibly a code fix if warning investigation reveals a refactoring regression
- **Out of scope**: new tag, new features, Plan 42 (broad-except audit system/)

## What's broken

### A. CHANGELOG prompt-41 entry asserts wrong test count

Current CHANGELOG entry (around line 8166-8167):
```
**Testing Results:**
- Baseline: ~1124 passed, ~61 skipped, 0 failed, 0 warnings
- Final: ~1124 passed, ~61 skipped, 0 failed, 0 warnings (no change - only added comments and trace events)
```

Actual measurement (just run by user):
```
1118 passed, 61 skipped, 1 warning in 86.65s
```

Two discrepancies:
1. **Test count**: claimed ~1124, actual 1118 (6-test gap)
2. **Warning count**: claimed 0, actual 1

This is a Rule 19 violation: gate marked PASSED without literal evidence. The "~1124 passed, 0 warnings" was copied from prior prompt baselines without actually measuring prompt-41's result.

### B. Handoff test baseline also wrong

Current handoff "Last updated" line:
```
Test baseline: ~1124 passed, ~61 skipped, 0 failed, 0 warnings.
```

Should be:
```
Test baseline: 1118 passed, 61 skipped, 0 failed, 1 warning.
```

(After investigating the warning — see Step 2 — update with the actual count and warning status.)

### C. Warning needs investigation

A new warning appeared after the broad-except refactoring. Need to identify what it is and whether it's:
- (a) From the broad-except refactoring (e.g., a trace event API deprecation) — needs fix or documentation
- (b) Pre-existing (e.g., a library deprecation) — just document
- (c) From something else entirely

### D. `--ignore=tests/test_llama_cpp_adapter.py` should be removed

The handoff documents `--ignore` as part of the "standard test measurement command" — but `pytest.importorskip("llama_cpp")` in the test file should make it unnecessary. The `--ignore` flag is belt-and-suspenders that masks whether `importorskip` actually works.

This fix-up removes `--ignore` from the handoff's standard measurement command and verifies that the test suite collects cleanly without it.

## What to change

### Step 1 — Run measurement commands and paste literal output

Run these two commands and paste the literal output (no interpretation):

```powershell
# Command 1: Full test suite summary (last 3 lines) — NO --ignore flag
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 3

# Command 2: Warning breakdown
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "Warning|warning|DeprecationWarning|FutureWarning" | Group-Object | Sort-Object Count -Descending | Format-Table Count, Name -AutoSize
```

**Paste both outputs into the CHANGELOG** as evidence (Rule 19).

**If Command 1 fails at collection time** (e.g., `ModuleNotFoundError: No module named 'llama_cpp'`):
- That means `pytest.importorskip` is NOT working as expected
- STOP. Do NOT add `--ignore` back. Instead, investigate why `importorskip` fails — may need to fix the test file or install `llama_cpp`
- Report the failure to GLM

**If Command 1 succeeds** (tests run, possibly with `test_llama_cpp_adapter.py` tests showing as SKIPPED):
- Note the actual count (passed/skipped/failed/warnings)
- Proceed to Step 2

### Step 2 — Investigate the 1 warning

Based on Command 2's output from Step 1, identify what the warning is:

**If the warning is from the broad-except refactoring** (e.g., a trace event API deprecation triggered by the new WARNING trace events):
- Investigate the specific code path
- Either fix the warning (if it's a real issue) or document why it's acceptable
- Paste the investigation findings into CHANGELOG

**If the warning is pre-existing** (e.g., a library deprecation unrelated to the refactoring):
- Document it in the handoff's "Test environment prerequisites" section
- Note that it's pre-existing, not from prompt-41

**If the warning is unclear** (Command 2 doesn't show enough detail):
- Run with `-W default` to see full warning messages:
  ```powershell
  python -m pytest tests/ -q --tb=no -W default 2>&1 | Select-String "Warning" | Select-Object -First 10
  ```
- Paste the full warning text into CHANGELOG

### Step 3 — Correct CHANGELOG prompt-41 entry

**File**: `CHANGELOG.md`

Update the prompt-41 "Testing Results" section to reflect the ACTUAL measured count from Step 1:

```
**Testing Results:**
- Baseline (pre-prompt-41): <actual baseline count from prompt-40, measured>
- Final (post-prompt-41): <actual count from Step 1 Command 1>
- Warning investigation: <findings from Step 2>
```

**Do NOT assert a count from memory or copy from prior prompts.** Use the literal output from Step 1.

Also update Gate 4's verification output to paste the actual command output (not just "PASSED"):

```
- Gate 4 (Full test suite unchanged): <actual output from Step 1 Command 1>
```

### Step 4 — Correct handoff test baseline

**File**: `SOVEREIGN_AI_HANDOFF.md`

Update the "Last updated" line's test baseline to match the actual measurement:

```
**Last updated**: 2026-06-19 <time> — post prompt-41 (fix-up). <summary of what was corrected>. Test baseline: <actual passed> passed, <actual skipped> skipped, 0 failed, <actual warnings> warnings (measured with python -m pytest tests/ -q --tb=no).
```

### Step 5 — Remove `--ignore` from handoff standard measurement command

**File**: `SOVEREIGN_AI_HANDOFF.md`

Update the "Test environment prerequisites" section. Find:

```
**Standard test measurement command**: `python -m pytest tests/ -q --tb=no --ignore=tests/test_llama_cpp_adapter.py`

The `--ignore=tests/test_llama_cpp_adapter.py` flag is required because `llama_cpp` is not installed in the development environment. The test file uses `pytest.importorskip("llama_cpp")` which should handle the missing dependency cleanly, but `--ignore` is used as belt-and-suspenders to ensure the test suite doesn't fail at collection time.
```

Replace with:

```
**Standard test measurement command**: `python -m pytest tests/ -q --tb=no`

`tests/test_llama_cpp_adapter.py` uses `pytest.importorskip("llama_cpp")` to skip cleanly when `llama_cpp` is not installed. No `--ignore` flag is needed — the tests skip gracefully at collection time. If collection fails without `--ignore`, that indicates `importorskip` is not working correctly and should be investigated (not masked with `--ignore`).
```

Also search the handoff for any other references to `--ignore=tests/test_llama_cpp_adapter.py` and remove them (there may be references in "Next 5 prompts" verification sections or similar).

### Step 6 — Reframe the "Devin chat report test counts unreliable" landmine

**File**: `SOVEREIGN_AI_HANDOFF.md` — "Known landmines" section

The current landmine (added in prompt-41) says:

```
- **Devin chat report test counts unreliable** (prompt-39, prompt-40 had this):
  Devin's chat summary of test counts (e.g., "1118 passed") has been 6 tests
  lower than the handoff's actual measurement (e.g., "1124 passed") for two
  consecutive prompts. The handoff is the authoritative source — always verify
  test counts from the handoff, not from Devin's chat report. Pattern may be
  due to Devin counting --ignore'd tests differently or running a subset.
  When in doubt, run `python -m pytest tests/ -q --tb=no --ignore=tests/test_llama_cpp_adapter.py`
  directly to get the authoritative count.
```

This landmine was misframed. The actual pattern (revealed by prompt-41) is broader: Devin sometimes asserts test counts without measuring, in BOTH chat reports AND CHANGELOG/handoff entries. The issue isn't "chat vs handoff" — it's "assertion vs evidence."

Reframe to:

```
- **Test count assertions without measurement** (prompt-39, prompt-40, prompt-41 had this):
  Devin sometimes asserts test counts (e.g., "~1124 passed, 0 warnings") without
  actually measuring, copying from prior prompt baselines instead. This has
  occurred in chat reports, CHANGELOG entries, and handoff updates. The actual
  measurement may differ (e.g., prompt-41 claimed ~1124/0 warnings but actual
  was 1118/1 warning). Rule 19 requires literal evidence — always paste the
  `Select-Object -Last 3` output of `python -m pytest tests/ -q --tb=no` as
  proof of the count, never assert from memory or copy from prior prompts.
```

Note: removed the `--ignore` from the verification command in the landmine text too (per Step 5).

### Step 7 — Commit the fix-up

```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
# If Step 2 revealed a code fix is needed:
# git add <fixed file(s)>

git commit -m "docs: correct prompt-41 test baseline + investigate warning + remove --ignore from standard measurement"
git push origin master
```

**No new tag.** This is a docs fix-up on master, not a new prompt.

## Verification gates

### Gate 1 — CHANGELOG reflects actual measurement

```powershell
Select-String -Path CHANGELOG.md -Pattern "1118 passed"
```

**Expected**: at least 1 match (the corrected prompt-41 entry with actual count).

### Gate 2 — Handoff test baseline matches actual

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "1118 passed"
```

**Expected**: at least 1 match.

### Gate 3 — `--ignore` removed from handoff

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "ignore=tests/test_llama_cpp_adapter"
```

**Expected**: zero matches (all references removed).

### Gate 4 — Landmine reframed

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Test count assertions without measurement"
```

**Expected**: at least 1 match (reframed landmine).

### Gate 5 — Warning investigated

```powershell
Select-String -Path CHANGELOG.md -Pattern "Warning investigation"
```

**Expected**: at least 1 match (Step 2 findings documented).

### Gate 6 — Commit pushed to master

```powershell
git ls-remote https://github.com/AngusKingC/sovereign-ai refs/heads/master
```

**Expected**: HEAD is past `18ce278` (the prompt-41 tag) — new commit(s) pushed.

## STOP conditions

- **If Step 1 Command 1 fails at collection time** (ModuleNotFoundError or similar): STOP. `pytest.importorskip` is not working. Investigate why before proceeding. Do NOT add `--ignore` back.
- **If Step 2 reveals the warning is from a real code bug** (not just a deprecation): STOP. Fix the code bug in this fix-up commit. Paste the bug details into CHANGELOG.
- **If the actual test count differs significantly from 1118** (e.g., 1000 or 1200): STOP. Something else changed. Investigate before updating docs.

## Out of scope

- New tag (this is a docs fix-up, not a new prompt)
- Plan 42 (broad-except audit system/) — next plan after this fix-up
- Re-verification of blocked adapters from prompt-39/40
- Production code changes (unless Step 2 reveals a real bug from the broad-except refactoring)

## Closing steps

1. Run Step 1 commands, paste literal output into CHANGELOG
2. Investigate warning per Step 2, document findings
3. Update CHANGELOG prompt-41 entry per Step 3
4. Update handoff test baseline per Step 4
5. Remove `--ignore` from handoff per Step 5
6. Reframe landmine per Step 6
7. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md` (plus any code fix from Step 2)
8. `git commit -m "docs: correct prompt-41 test baseline + investigate warning + remove --ignore from standard measurement"`
9. `git push origin master`
10. Verify Gate 6 — master HEAD is past `18ce278`

## After this fix-up lands

- CHANGELOG and handoff reflect actual measured test count (1118 passed, 1 warning — or whatever Step 1 reveals)
- Warning is identified and either fixed or documented
- `--ignore` removed from handoff standard measurement command
- Landmine reframed to capture the actual pattern (assertion without measurement, not just chat vs handoff)
- Ready for Plan 42 (broad-except audit system/) with verified clean baseline
