# Plan 70 — 5-Plan Milestone Full Scan (Priority 1)

## Scope

Full 6-tool checkpoint scan to capture fresh baselines after Plans 66–69 (mypy remediation, system cleanup, skill taxonomy, repo hygiene). This is a scan-only plan — no code changes, no doc edits beyond PLANS.md baseline updates at closing.

## Pre-scan Context

Since the last full scan (Plan 60, 2026-06-23), the following significant changes occurred:
- **Plan 66**: Fixed 23 mypy errors across 7 system files. Core mypy clean (0 errors).
- **Plan 67**: Fixed 172 mypy errors across 45 files. Full-repo mypy clean (0 errors, 181 source files).
- **Plan 68**: Added SkillTier enum, SkillClassification dataclass, SkillTaxonomyRegistry, CONTEXT.md. 20 new tests. Baseline: 1253 passed, 67 skipped.
- **Plan 69**: Docs/cleanup only. Baselines held.

## S0 — Opening

S0.1. **Run `/jarvis-open`** — verifies prompt-69 tag on origin and confirms working copy is clean and on master. If the workflow is missing or fails, STOP and report.

S0.2. **Read AGENTS.md in full.** AGENTS.md is always-on — every file edit in this plan MUST comply with its rules. If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context behind the rule.

S0.3. **No new AGENTS.md rules this prompt.** Proceed directly to the plan body.

## S1 — Tool 1: pytest (full suite)

Run the full test suite:
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Wait for completion. Record: `<N> passed, <M> skipped, <P> failed`.
Expected: 1253 passed, 67 skipped (±5 per PLANS.md tolerance).
If outside tolerance, note the delta for PLANS.md reconciliation.

## S2 — Tool 2: ruff (full-repo)

```powershell
ruff check . 2>&1 | Select-Object -Last 5
```

Wait for completion. Record: `Found <N> errors.`
If errors found, get breakdown:
```powershell
ruff check . --statistics 2>&1
```
Expected: 0 errors.

## S3 — Tool 3: mypy (full-repo — ONLY at 5-plan checkpoints)

```powershell
mypy . --ignore-missing-imports 2>&1 | Select-Object -Last 5
```

**This is the ONLY time `mypy .` is allowed** (per OR2). This will take 2–5 minutes. Wait for completion.
Record: `Found <N> errors in <M> files.`
Expected: 0 errors (Plan 67 achieved full-repo mypy clean on 181 source files; Plans 68–69 were docs-only or added init files).

## S4 — Tool 4: bandit (full-repo)

```powershell
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache,globalrules 2>&1 | Select-Object -Last 10
```

Wait for completion. Record severity breakdown (low / medium / high). B108 should be 0 (suppressed per Plan 59).
Expected: ~3,179 low, 0 medium, 0 high (Plan 60 baseline).

## S5 — Tool 5: pip-audit

```powershell
pip-audit 2>&1 | Select-Object -Last 10
```

Wait for completion. Record: `Found <N> known vulnerabilities in <M> packages.`
No tolerance gate — pip-audit is informational (project does not control upstream CVEs). Record the actual count as the new baseline regardless of delta from Plan 60.

## S6 — Tool 6: vulture

```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-Object -Last 10
```

Wait for completion. Record: `<N> high-confidence findings.`
No tolerance gate — this scan captures the actual baseline. Plans 68–69 added new modules (skill_taxonomy.py, classifications.py, 5 __init__.py files) which may shift the count from the Plan 60 baseline of 23. Record the actual count regardless of delta.

## S7 — Compile Scan Summary

After ALL 6 tools complete (do NOT compile mid-scan), write the summary to scan/logs:

```powershell
$summary = @(
    "## Full Checkpoint Scan Results",
    "",
    "**Date**: 2026-06-24",
    "**Plan**: 70 (5-plan milestone)",
    "**Tests**: <tool 1 result>",
    "**Ruff**: <tool 2 result> errors",
    "**Mypy (full-repo)**: <tool 3 result> errors",
    "**Bandit**: <tool 4 result>",
    "**pip-audit**: <tool 5 result> CVEs",
    "**Vulture**: <tool 6 result> findings"
)
Set-Content -Path "C:\Jarvis\scan\logs\checkpoint-scan-prompt-70.md" -Value $summary -Encoding utf8
Get-Content C:\Jarvis\scan\logs\checkpoint-scan-prompt-70.md
```

## Closing

**Run `/jarvis-close`** — handles test suite (already captured in S1), ruff (already captured in S2), commit, tag, CHANGELOG, PLANS.md (with fresh baselines from this scan), LANDMINES.md (if new pattern), rule proposal (C9), docs commit, push, and post-push verification. If the workflow is missing or fails, STOP and report.

**PLANS.md baseline updates at C10**: Update the Static Analysis Baseline table with actual counts from this scan. Update the "Captured" line to reference Plan 70. Update the Test Baseline verified step to Plan 70, S1. Update the per-plan verification cadence next milestone to 75.

**Queue shift at C10**: This plan is a scan — no queue promotion happens. Plan 70 stays in the queue as completed. Specific queue edits:
- Plan 71: Remains as-is (open slot).
- Plan 72: Currently a tentative scan entry — replace with a generic open slot since Plan 70 now covers the 5-plan scan. Copy the current Plan 72 scope text into the reconciliation notes for reference, then clear it to TBD.
- Plan 73: Remains as-is (open slot). Update its "post-Plan" reference from 71 to 72.
- Plan 74: Remains as-is (open slot). Update its "post-Plan" reference from 73 to 73 (no change needed — already correct).
- Add new Plan 75 at bottom as **5-Plan Milestone Full Scan (Priority 1 — tentative)** with scope: "Post-Plans 71–74 full-repo scan and baseline refresh." This preserves the OR2 cadence (55, 60, 65, 70, 75, 80).

**Reconciliation notes at C10**: Record all deltas from Plan 60 baselines.
