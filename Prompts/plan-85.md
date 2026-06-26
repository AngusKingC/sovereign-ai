# Plan 85 — 5-Plan Milestone Scan and Fix

**Tag**: `prompt-85` | **Depends on**: `prompt-84`

---

## Scope

Whole-repo scan after Batch 1 (Plans 81–84). No new features. No new architecture. Fixes only. This plan verifies baselines, fixes accumulated issues from the batch, runs all test suites (including Playwright E2E which was deferred from Plan 84), and reconciles PLANS.md state.

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-84` tag on origin, working copy clean on master. If the workflow is missing or fails, STOP and report.

S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.

S0.3. No new AGENTS.md rules this prompt. (Scan prompts propose rules via C9 only if new landmine patterns are found during the scan.)

---

## S1. Fix mypy baseline violation (HIGH — Issue #1)

**Problem**: PLANS.md baseline says "Mypy (core/system) 0 errors" but `mypy core/ system/` returns 8 errors in 7 files. These errors accumulated during Plans 81–84 but were not caught because Plans 81–84 used file-scoped mypy only.

**Step 1**: Run full mypy and capture ALL errors:
```powershell
mypy core/ system/ --ignore-missing-imports 2>&1 | Tee-Object -FilePath "scan/logs/mypy-scan-prompt-85.txt"
```

**Step 2**: Fix each error. Known errors from Plan 84 log:
- `system/profiler.py:114` — Library stubs not installed for "psutil". Fix: Add `types-psutil` to `requirements-dev.txt` and run `pip install types-psutil`.
- `core/multi_worker.py:28` — Cannot find module `core.resource_manager`. Fix: Either create the missing module, fix the import path, or remove the import if the module was renamed/deleted. Investigate git history: `git log --all --oneline -- "core/resource_manager*"`.
- Remaining 6 errors: Fix each individually. Do NOT suppress with `# type: ignore` unless the error is a known false positive (document the reason).

**Step 3**: Re-run mypy and verify 0 errors:
```powershell
mypy core/ system/ --ignore-missing-imports 2>&1 | Select-Object -Last 5
```
Expected: `Success: no issues found in N source files`.

**STOP condition**: If any mypy error requires a design decision (not a mechanical fix), STOP and report. Do not guess.

---

## S2. Reconcile vulture baseline (HIGH — Issue #2)

**Problem**: PLANS.md static analysis table says Vulture = 41 findings (Plan 79 source), but Plans 82/83/84 reconciliation notes say "40 findings". Actual count unknown.

**Step 1**: Run vulture and count findings:
```powershell
python -c "
import subprocess, sys
result = subprocess.run(['vulture', '.', '--min-confidence', '80', '--exclude', '.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache'], capture_output=True, text=True)
findings = [l for l in result.stdout.splitlines() if 'confidence' in l]
print(f'Total findings: {len(findings)}')
with open('vulture-whitelist.txt', encoding='utf-8') as f:
    whitelist = set(l.strip() for l in f if l.strip())
new_findings = [f for f in findings if f not in whitelist]
if new_findings:
    print(f'NEW findings (not in whitelist): {len(new_findings)}')
    for f in new_findings:
        print(f'  {f}')
else:
    print(f'All {len(findings)} findings are whitelisted.')
"
```

**Step 2**: Reconcile the count:
- If actual count = 41: Update Plans 82/83/84 reconciliation notes from "40" to "41". Update PLANS.md static analysis table to confirm 41.
- If actual count = 40: Update PLANS.md static analysis table from "41" to "40" with justification note.
- If actual count = anything else: Document the actual count and investigate the delta.

**Step 3**: If new findings appear (not in whitelist), either fix the dead code or add to `vulture-whitelist.txt` (UTF-8 encoded) per OR19.

---

## S3. Fix Plan 81 test count inconsistency (HIGH — Issue #3)

**Problem**: PLANS.md completed prompts table row for Plan 81 says "9 new backend tests" but reconciliation note says "7 new backend tests" (delta +7). The table row is wrong.

**Step 1**: Read current PLANS.md Plan 81 row:
```powershell
Select-String -Path PLANS.md -Pattern "^\| 81 \|" | Select-Object -First 1
```

**Step 2**: Fix the table row using the Edit tool (OR7 — exact `old_str`/`new_str`). Change "9 new backend tests" to "7 new backend tests" in the Plan 81 completed prompts table row.

**Step 3**: Verify the fix:
```powershell
Select-String -Path PLANS.md -Pattern "^\| 81 \|" | Select-Object -First 1
```
Expected: Row now says "7 new backend tests".

---

## S4. Run Playwright E2E tests (HIGH — Issue #4)

**Problem**: Plan 84 created 8 Playwright E2E tests but deferred execution ("requires running servers"). Plan 84 S8 explicitly required running Playwright. These tests have never been executed.

**Step 1**: Verify Playwright dependencies are installed:
```powershell
cd src; npm install 2>&1 | Select-Object -Last 10
```

**Step 2**: Verify TypeScript compiles (fix e2e type errors if present — Issue #5):
```powershell
cd src; npx tsc --noEmit 2>&1 | Select-Object -Last 20
```
If errors in `e2e/*.spec.ts` (implicit `any`, missing `@playwright/test`):
- Ensure `@playwright/test` is in `package.json` devDependencies
- Add explicit type annotations to E2E test parameters: `({ page }: { page: Page })` instead of bare `({ page })`
- Re-run tsc until 0 errors

**Step 3**: Install Playwright browsers:
```powershell
cd src; npx playwright install chromium 2>&1 | Select-Object -Last 10
```

**Step 4**: Run Playwright E2E tests:
```powershell
cd src; npx playwright test 2>&1 | Tee-Object -FilePath "../scan/logs/playwright-results-prompt-85.txt"
```

**Step 5**: Fix any failing E2E tests. Common issues:
- webServer startup failure: Verify `npm run e2e:serve` works (concurrently starts backend + frontend)
- Port conflicts: Ensure :3000 and :8000 are free
- SSE connection failures: Verify backend SSE endpoints are accessible

**STOP condition**: If E2E tests fail due to a structural issue (not a mechanical fix), STOP and report. Do not suppress test failures.

---

## S5. Fix PLANS.md queue duplication (MEDIUM — Issue #8)

**Problem**: PLANS.md lists "Terminal xterm.js + System Panels + Subagent UI" at both Plan 85 AND Plan 90. Terminal is duplicated.

**Step 1**: Read the current Next 5 Prompts Queue section:
```powershell
Select-String -Path PLANS.md -Pattern "Plan 8[5-9]|Plan 9[0-1]|Terminal|Scan Prompt|Batch 2" | Select-Object -First 20
```

**Step 2**: Fix the queue using Edit tool (OR7). The correct queue after this scan should be:
- Plan 85: THIS SCAN (already executing — will be in completed prompts after closing)
- Plan 86: JArvis UI: Terminal xterm.js + System Panels + Subagent UI (was Plan 85)
- Plan 87: PEMADS Phase 2: Expert Panel Manager + VRAM Hot-Swap (was Plan 87)
- Plan 88: PEMADS Phase 3: Judge + Implementation Gate (was Plan 88)
- Plan 89: Multi-Channel Approvals + Approval UI Enhancements (was Plan 89)
- Plan 90: 5-Plan Milestone Scan (was Plan 86 — scan moves to every 5 plans per AI_HANDOFF.md)

**Remove the duplicate Terminal entry at Plan 90.** Terminal now lives at Plan 86 only.

**Step 3**: Verify the queue is consistent:
```powershell
Select-String -Path PLANS.md -Pattern "Terminal" | Select-Object -First 10
```
Expected: Terminal appears only once (at Plan 86).

---

## S6. Fix pre-commit `--check` flag error (MEDIUM — Issue #7)

**Problem**: `pre-commit install --check` failed in Plan 84 with "unrecognized arguments: --check". This is a pre-commit version issue or wrong command in jarvis-open workflow.

**Step 1**: Check pre-commit version:
```powershell
pre-commit --version
```

**Step 2**: Check if `--check` is a valid flag for `pre-commit install`:
```powershell
pre-commit install --help
```

**Step 3**: If `--check` is not valid, update `.windsurf/workflows/jarvis-open.md` to use the correct command. The correct way to check if pre-commit hooks are installed is:
```powershell
Test-Path .git/hooks/pre-commit
```
(PowerShell-native check, already used in Plan 84 log as a workaround.)

**Step 4**: Verify the fix by running jarvis-open's pre-commit check step.

---

## S7. Full static analysis scan

Run all 6 static analysis tools and verify against PLANS.md baselines:

```powershell
# Ruff (full repo)
ruff check . 2>&1 | Select-Object -Last 5
# Expected: 0 errors

# Mypy (full repo — was file-scoped in Plans 81-84)
mypy core/ system/ --ignore-missing-imports 2>&1 | Select-Object -Last 5
# Expected: 0 errors (after S1 fixes)

# Bandit
bandit -r . -x .venv,venv,node_modules,.git 2>&1 | Select-Object -Last 10
# Expected: 3,384 low, 1 medium, 0 high (baseline)

# pip-audit
pip-audit 2>&1 | Select-Object -Last 10
# Expected: 19 CVEs (baseline, upstream only)

# Vulture (already run in S2, verify count here)

# detect-secrets
detect-secrets scan --baseline .secrets.baseline 2>&1 | Select-Object -Last 5
# Expected: exit code 0 (no new secrets)
```

**For each tool**: If count differs from PLANS.md baseline, document the delta in PLANS.md reconciliation notes with cause and justification. Fix any new findings that are not already documented as accepted suppressions.

---

## S8. Full test suite

Run all test suites:

```powershell
# Python tests
python -m pytest tests/ -q --tb=short 2>&1 | Select-Object -Last 5
# Expected: 1418 passed, 67 skipped (baseline)

# Vitest
cd src; npm test 2>&1 | Select-Object -Last 10
# Expected: 46 tests passed (18 stores + 7 hooks + 6 components + 5 shell + 10 existing)

# Playwright E2E (already run in S4, verify all pass)
cd src; npx playwright test 2>&1 | Select-Object -Last 10
# Expected: 8 tests passed (4 shell + 2 SSE + 2 CORS)

# TypeScript build
cd src; npx tsc --noEmit 2>&1 | Select-Object -Last 5
# Expected: 0 errors (after S4 fixes)

# Coverage
python -m pytest tests/ --cov=. --cov-report=term-missing 2>&1 | Select-Object -Last 5
# Expected: 83% (baseline, -5% tolerance = 78% minimum)
```

**STOP condition**: If any test fails non-trivially, STOP and report. Do not suppress test failures.

---

## S9. Scan LANDMINES.md for missing rules

**Step 1**: Read LANDMINES.md in full.

**Step 2**: For each landmine (L1 through L{n}), check if a corresponding AR/OR rule exists in AGENTS.md. The landmine should reference its source rule (or vice versa).

**Step 3**: If any landmine has no corresponding rule, propose the missing rule via C9 (Step 9 of jarvis-close) with "Source: landmine L{n}" reference.

**Step 4**: If no new landmine patterns were found during Plans 81–84 or this scan, note "No new landmine patterns" in C9.

---

## S10. Scan CHANGELOG.md

**Step 1**: Verify Plans 81, 82, 83, 84 all have CHANGELOG entries:
```powershell
Select-String -Path CHANGELOG.md -Pattern "prompt-8[1-4]"
```
Expected: 4 matches (one per plan).

**Step 2**: If any plan is missing a CHANGELOG entry, add it retroactively using the execution logs in `logs/` as the source.

---

## S11. Scan PLANS.md for consistency

**Step 1**: Verify completed prompts table has rows for Plans 81, 82, 83, 84, and 85 (this scan).

**Step 2**: Verify test baseline reflects actual counts from S8.

**Step 3**: Verify static analysis baselines reflect actual counts from S7.

**Step 4**: Verify Next 5 Prompts Queue is correct (after S5 fix).

**Step 5**: Verify Baseline Reconciliation Notes have entries for all plans in this batch (81–85).

**Step 6**: Update PLANS.md "Last updated" line to reference this scan.

---

## S12. Scan docstrings for stale references

**Step 1**: Search for references to removed/renamed modules:
```powershell
# backend/ was deleted in Plan 81 — search for stale references
Select-String -Path *.py -Pattern "from backend|import backend|backend\.main" -Recurse | Select-Object -First 20

# Check for references to modules that may not exist
Select-String -Path core/*.py -Pattern "core\.resource_manager" | Select-Object -First 10
```

**Step 2**: Fix any stale references found. If a module was renamed, update imports. If deleted, remove the reference.

---

## What NOT to do

- Do not add new capabilities.
- Do not refactor working code unless it violates an existing AR/OR rule.
- Do not touch test fixtures beyond fixing failures caused by the above.
- Do not suppress mypy errors with `# type: ignore` unless the error is a known false positive (document the reason).
- Do not skip Playwright E2E tests — they must be run and pass (or fail with STOP).
- Do not rename existing log files in `logs/` (naming inconsistency is noted but out of scope for this scan).

---

## STOP condition

If any scan reveals a structural problem requiring design decisions (not mechanical fixes), STOP and report to the user. Do not guess. Examples:
- `core/resource_manager` module is genuinely missing and its absence indicates an architectural gap
- Playwright E2E tests fail due to a fundamental architecture issue (not a config fix)
- Coverage drops >5% from baseline without clear cause

---

## Files WILL create
- `scan/logs/mypy-scan-prompt-85.txt` (mypy scan output)
- `scan/logs/playwright-results-prompt-85.txt` (Playwright test results)
- `scan/logs/` directory (if it doesn't exist — create it)

## Files WILL edit
- `PLANS.md` (fix Plan 81 test count, fix queue duplication, update baselines, add reconciliation notes)
- `CHANGELOG.md` (add Plan 85 entry at closing)
- `requirements-dev.txt` (add `types-psutil` if missing)
- `core/multi_worker.py` (fix resource_manager import — if mechanical)
- `system/profiler.py` (verify psutil import — if needed)
- `src/e2e/*.spec.ts` (fix TypeScript type errors — if present)
- `src/package.json` (verify @playwright/test + concurrently in devDependencies)
- `vulture-whitelist.txt` (update if new findings)
- `.windsurf/workflows/jarvis-open.md` (fix pre-commit --check command)
- Up to 6 additional Python files (mypy fixes from S1)

## Files will NOT edit
- `core/` logic modules (except mechanical mypy fixes in S1)
- `cli/`
- `skills/` logic
- `adapters/`
- `workers/`
- `memory/` internals
- `system/` internals (except mechanical mypy fixes in S1)
- `logs/` existing files (naming inconsistency noted, not fixed in this scan)
- `Prompts/` plan files (already committed)

---

## Closing

Run `/jarvis-close`. Tag `prompt-85`. CHANGELOG entry for Plan 85. Update PLANS.md (completed row, baseline reconciliation, queue shift — Terminal moves to Plan 86, scan moves to Plan 90, duplicate Terminal at Plan 90 removed).
