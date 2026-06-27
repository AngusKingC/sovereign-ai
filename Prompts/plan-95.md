# Plan 95 — 5-Plan Milestone Scan + Bug Fixes

**Tag**: `prompt-95` | **Depends on**: `prompt-94`

---

## Scope

Whole-repo scan after Batch 3 (Plans 91–94 — UI Remediation Phases 1–3). No new features. Fixes only. This plan:
1. Runs ALL scan tools (no skipping)
2. Fixes bugs found in Plans 91–94 execution logs
3. Reconciles baselines
4. Verifies UI Gap Analysis gaps are closed

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-94` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

---

## S1. Fix Plan 93 skipped test — `test_list_workers` KeyError (HIGH — execution bug)

**Problem**: Plan 93 skipped `test_list_workers` with `@pytest.mark.skip(reason="KeyError: 0 - response model serialization issue")`. This is a Pydantic response model serialization bug in `api/workers.py` — the `WorkerProfileResponse` model fails when converting `WorkerFactory.list_workers()` results.

**Evidence**: Plan 93 execution log line 3208: `@pytest.mark.skip(reason="KeyError: 0 - response model serialization issue")`

**Step 1**: Read `api/workers.py` and find the `_profile_to_response()` function.

**Step 2**: Read `tests/test_worker_api.py` and find the `test_list_workers` test.

**Step 3**: Debug the KeyError. The error "KeyError: 0" typically means Pydantic is trying to access index 0 of a field that's a scalar, or a list is being treated as a dict. Common causes:
- `WorkerProfileResponse` has a field that's `list[str]` but the source `WorkerProfile` has a `str` (or vice versa)
- `capabilities` field mismatch — source is `list`, response model expects `dict`
- Pydantic v2 `model_dump()` producing a dict that's then passed to `WorkerProfileResponse(**dict)` where a list field is accessed by index

**Step 4**: Fix the serialization issue. Remove the `@pytest.mark.skip` decorator.

**Step 5**: Verify:
```bash
python -m pytest tests/test_worker_api.py::test_list_workers -vvv
```
Expected: test PASSES (not skipped).

---

## S2. Fix skipped test count — 67 → 71 jump (MEDIUM — verify no tests silently dropped)

**Problem**: Skipped count jumped from 67 to 71 between Plan 92 and Plan 93. This is a +4 delta in skipped tests. Plan 93's reconciliation note says "3 tests skipped in test_api_stubs.py (stub tests now implemented)" but that accounts for only 3, not 4.

**Step 1**: Run pytest with skip reasons:
```bash
python -m pytest tests/ -vvv --tb=no -q | grep "SKIPPED"
```

**Step 2**: Compare the skip list against the previous scan (Plan 90). Identify which 4 tests are newly skipped.

**Step 3**: For each newly skipped test:
- If the skip reason is a known issue (like the KeyError in S1), verify it's tracked
- If the skip was added without justification, remove the skip decorator and fix the test or the code it tests
- If the skip is intentional (e.g., requires external service), document why in a comment

**Step 4**: After S1 fix (un-skipping `test_list_workers`), verify skip count returns to 70 or lower.

---

## S3. Run full-repo mypy (HIGH — was NOT run in Plans 91–93)

**Problem**: Plans 91–93 only ran file-scoped mypy (e.g., `mypy api/models.py web/server.py`). Full-repo mypy (`mypy core/ system/`) was NOT run. The PLANS.md baseline says "Mypy (core/system) 0 errors" but this hasn't been verified since Plan 90.

**Step 1**: Run full-repo mypy:
```bash
mypy core/ system/ --ignore-missing-imports
```

**Step 2**: If errors are found:
- Fix each error (do NOT suppress with `# type: ignore` unless documented)
- Common issues from Plans 91–94: new `Optional` injections in `orchestrator.py` may have missing type annotations, `api/models.py` and `api/workers.py` may have untyped `Depends()` calls

**Step 3**: Verify:
```bash
mypy core/ system/ --ignore-missing-imports
```
Expected: `Success: no issues found in N source files`

---

## S4. Run full-repo ruff (HIGH — verify no drift)

```bash
ruff check .
```
Expected: `All checks passed!`

If errors found, fix them.

---

## S5. Run bandit (MEDIUM — was NOT run in Plans 91–93)

```bash
bandit -r . -x .venv,venv,node_modules,.git -ll 2>&1 | tail -n 10
```
Expected: baseline count from PLANS.md (check current baseline). If new findings:
- B608 (SQL injection false positive in asyncpg parameterized queries) — known, accepted
- Any NEW findings in `api/models.py`, `api/workers.py`, `api/adapters.py`, `api/memory.py` — investigate and fix

Document delta in PLANS.md reconciliation notes.

---

## S6. Run pip-audit (MEDIUM — verify no new CVEs)

```bash
pip-audit 2>&1 | tail -n 10
```
Expected: baseline CVE count from PLANS.md. If new CVEs:
- Check if caused by `kuzu` dependency (if Plan 96 already ran) or other new deps
- Document in PLANS.md if upstream-only (no actionable fix)

---

## S7. Run vulture (MEDIUM — verify whitelist still valid)

```bash
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
    sys.exit(1)
print(f'All {len(findings)} findings are whitelisted.')
"
```
Expected: 40 findings (baseline), all whitelisted. If new findings:
- Fix dead code (preferred) OR add to `vulture-whitelist.txt` with justification

---

## S8. Run detect-secrets (MEDIUM)

```bash
detect-secrets scan --baseline .secrets.baseline
```
Expected: exit code 0 (no new secrets). If new findings, investigate.

---

## S9. Run full Python test suite

```bash
python -m pytest tests/ -vvv
```
Expected: 1477+ passed, ≤71 skipped (after S1 fix, should be ≤70 skipped).

**STOP condition**: If any test FAILS (not skips), STOP and fix before proceeding. Do not skip tests to get green — fix the underlying issue.

---

## S10. Run Vitest

```bash
cd src && npm test
```
Expected: 50 tests passed (baseline from Plan 94).

If failures:
- Check for TypeScript strict mode issues in new components (ModelsPanel, ModelDownloader, WorkerCreator, WorkerEditor, ResourceMonitorPanel, CostPolicyTab)
- Fix all failures

---

## S11. Run Playwright E2E

```bash
cd src && npx playwright test
```
Expected: 8 tests passed (baseline from Plan 85).

If failures:
- Check if new API endpoints (`/api/models`, `/api/workers`, `/api/adapters`, `/api/costs/policy`, `/api/resources/monitor`) are reachable
- Check if CORS/proxy still works
- Fix all failures

**Note**: Do NOT skip Playwright. It was properly run in Plan 91 (56 references in log) but NOT in Plan 93 (0 references). The scan must verify all E2E tests pass.

---

## S12. Run TypeScript build

```bash
cd src && npx tsc --noEmit && npm run build
```
Expected: 0 TypeScript errors, build succeeds.

If errors:
- Check new TypeScript files from Plans 91–94 for strict mode violations
- Fix all errors

---

## S13. Run coverage

```bash
python -m pytest tests/ --cov=. --cov-report=term-missing
```
Expected: ≥77% (82% baseline -5% tolerance). If coverage dropped:
- Identify which new files have low coverage
- Document in PLANS.md reconciliation notes
- Do NOT write new tests just to boost coverage — only if existing tests are genuinely missing

---

## S14. Scan LANDMINES.md for missing rules

**Step 1**: Read LANDMINES.md in full.

**Step 2**: For each landmine, check if a corresponding AR/OR rule exists in AGENTS.md.

**Step 3**: If any landmine has no corresponding rule, propose via C9 with "Source: landmine L{n}".

**Step 4**: If no new landmine patterns were found during Plans 91–94 or this scan, output C9 Option B (explicit none with justification).

---

## S15. Scan CHANGELOG.md

**Step 1**: Verify Plans 91, 92, 93, 94 all have CHANGELOG entries:
```bash
grep -c "prompt-9[1-4]" CHANGELOG.md
```
Expected: at least 4 matches.

**Step 2**: If any plan is missing a CHANGELOG entry, add it retroactively.

---

## S16. Scan PLANS.md for consistency

**Step 1**: Verify completed prompts table has rows for Plans 91, 92, 93, 94, and 95 (this scan).

**Step 2**: Verify test baseline reflects actual counts from S9:
- Python: 1477+ passed (after S1 fix, may be 1478 if un-skipped test passes)
- Skipped: ≤70 (should decrease by 1 from S1 fix)
- Vitest: 50
- Playwright: 8

**Step 3**: Verify static analysis baselines reflect actual counts from S3–S8.

**Step 4**: Verify Next 5 Prompts Queue is correct:
- Plan 96: Memory Backend + UI Integration
- Plan 97: Debate & Expert Panel UI
- Plan 98: Security & Sandbox Visibility
- Plan 99: Observability & Trace Viewer
- Plan 100: Scan prompt

**Step 5**: Update PLANS.md "Last updated" line to reference this scan.

**Step 6**: Verify the skipped test count in PLANS.md matches actual. If S1 fix un-skipped `test_list_workers`, the skipped count should decrease from 71 to 70 (or lower if S2 found more un-skippable tests).

---

## S17. Scan docstrings for stale references

**Step 1**: Search for references to removed/renamed modules:
```bash
# Check for stale stub references (stubs were wired in Plans 91/93)
grep -rn "stub\|501\|not yet implemented" api/ --include="*.py" | head -10

# Check for references to TerminalPlaceholder (deleted in Plan 86)
grep -rn "TerminalPlaceholder" src/ --include="*.tsx" | head -5

# Check for stale "Coming in Plan" tooltips
grep -rn "Coming in Plan" src/ --include="*.tsx" | head -10
```

**Step 2**: Fix any stale references found.

---

## S18. Verify UI Gap Analysis gaps closed

**Step 1**: Read `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §3 (Critical UI Gaps).

**Step 2**: Verify each gap has UI implementation:

| Gap | Plan | UI Component | Verify |
|-----|------|-------------|--------|
| #1 Model & Adapter Selection | 91 | `ModelsPanel.tsx`, StatusBar model click | `grep -l "ModelsPanel" src/components/panels/` |
| #1 Model Downloader | 92 | `ModelDownloader.tsx`, Fallback Chain Editor | `grep -l "ModelDownloader" src/components/panels/` |
| #2 Worker Creation | 93 | `WorkerCreator.tsx`, `WorkerEditor.tsx` | `grep -l "WorkerCreator" src/components/panels/` |
| #4 Cost & Resource Controls | 94 | `ResourceMonitorPanel.tsx`, un-mocked SettingsDrawer | `grep -l "ResourceMonitorPanel" src/components/panels/` |

**Step 3**: For each gap, verify the component exists and is wired to the API:
```bash
# Verify ModelsPanel exists and imports from api.ts
grep -l "getModels\|searchModels" src/components/panels/ModelsPanel.tsx

# Verify ModelDownloader exists and imports download functions
grep -l "downloadModel\|getDownloadStatus" src/components/panels/ModelDownloader.tsx

# Verify WorkerCreator exists and imports createWorker
grep -l "createWorker" src/components/panels/WorkerCreator.tsx

# Verify ResourceMonitorPanel exists and imports getResourceMonitor
grep -l "getResourceMonitor" src/components/panels/ResourceMonitorPanel.tsx
```

**Step 4**: If any gap is NOT closed (component missing or not wired), document in PLANS.md as a known gap for future plans.

---

## S19. Verify Git Bash migration complete

**Step 1**: Check for any remaining PowerShell references in workflow files:
```bash
grep -rn "powershell\|Select-String\|Get-Content\|Set-Content\|Add-Content\|ForEach-Object\|Select-Object" .windsurf/workflows/ | grep -v "Avoid\|NEVER\|do NOT"
```
Expected: 0 results (only acceptable matches are in AGENTS.md telling Devin NOT to use PowerShell).

**Step 2**: Check for remaining `Test-Path` in jarvis-open.md note (stale from Plan 85):
```bash
grep -n "Test-Path" .windsurf/workflows/jarvis-open.md
```
If found, update to `test -f`.

**Step 3**: Check AI_HANDOFF.md line 34:
```bash
grep -n "PowerShell" AI_HANDOFF.md
```
If still says "PowerShell on Windows", fix to "Git Bash on Windows".

---

## S20. Check for test-results/ in git tracking

**Step 1**: Verify `test-results/` is in `.gitignore`:
```bash
grep "test-results" src/.gitignore .gitignore 2>/dev/null
```

**Step 2**: If `test-results/` files are still tracked, untrack them:
```bash
git rm -r --cached src/test-results/ 2>/dev/null || true
```

**Step 3**: Add to `.gitignore` if not present:
```bash
echo "test-results/" >> .gitignore
```

---

## What NOT to do

- Do NOT add new features (that's Plans 96+).
- Do NOT skip any scan tool — ALL tools must run (ruff, mypy full-repo, bandit, pip-audit, vulture, detect-secrets, pytest, Vitest, Playwright, tsc, npm build, coverage).
- Do NOT suppress mypy errors with `# type: ignore` unless documented.
- Do NOT skip Playwright E2E tests.
- Do NOT skip Vitest.
- Do NOT leave tests in skipped state without justification.
- Do NOT refactor working code unless it violates an existing AR/OR rule.

---

## STOP condition

If any scan reveals a structural problem requiring design decisions (not mechanical fixes), STOP and report. Do not guess. Examples:
- `test_list_workers` KeyError requires redesigning the response model architecture
- Full-repo mypy reveals 50+ errors (too many for a scan prompt)
- Playwright E2E tests fail due to fundamental architecture issue
- Coverage drops >5% from baseline without clear cause

---

## Files WILL create
- None (scan-only, no new files unless fixing bugs)

## Files WILL edit (potential)
- `api/workers.py` (fix KeyError serialization bug — S1)
- `tests/test_worker_api.py` (remove `@pytest.mark.skip` — S1)
- `core/` files (fix full-repo mypy errors — S3)
- `PLANS.md` (update baselines, reconcile skipped count — S16)
- `CHANGELOG.md` (add Plan 95 entry at closing)
- `.gitignore` (add test-results/ — S20)
- `.windsurf/workflows/jarvis-open.md` (fix stale Test-Path reference — S19)
- `AI_HANDOFF.md` (fix PowerShell → Git Bash — S19)
- `vulture-whitelist.txt` (update if new findings — S7)
- `src/` TypeScript files (fix tsc errors if any — S12)

## Files will NOT edit
- `src/` frontend components (no new UI features)
- `memory/` (Plan 96 scope)
- `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` (reference doc, not edited)

---

## Closing

Run `/jarvis-close`. Tag `prompt-95`. CHANGELOG entry for Plan 95. Update PLANS.md (completed row, baseline reconciliation, queue shift to Plans 96–100).
