---
name: jarvis-close
description: "Sovereign AI closing sequence — C1 through C13. Run this after all plan work is complete. Includes test suite, lint, commit, tag, changelog, plans update, landmines update, push, and verification."
---

# Jarvis Close — Plan Closing Sequence

Execute each step in order. Paste output for each. Do NOT skip steps.

## Step 1: Full test suite
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```
Expected: check `PLANS.md` for current baseline. If tests fail, STOP.

## Step 2: Ruff check on touched files
```powershell
ruff check <files_touched> 2>&1 | Select-Object -Last 3
```
Expected: zero errors.

## Step 2.5: detect-secrets baseline check (NEW — Plan 72)
```powershell
detect-secrets scan --baseline .secrets.baseline
```
If exit code != 0, STOP — a new secret was introduced. Either update baseline (if false positive) or remove the secret. Do not commit until this passes.

## Step 2.7: Vulture whitelist check (FIXED — Plan 75)
```powershell
# Run vulture and compare to whitelist (vulture doesn't accept whitelist files as args)
python -c "
import subprocess, sys
result = subprocess.run(['vulture', '.', '--min-confidence', '80', '--exclude', '.venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache'], capture_output=True, text=True)
findings = [l for l in result.stdout.splitlines() if 'confidence' in l]
with open('vulture-whitelist.txt', encoding='utf-8') as f:
    whitelist = set(l.strip() for l in f if l.strip())
new_findings = [f for f in findings if f not in whitelist]
if new_findings:
    print('NEW vulture findings (not in whitelist):')
    for f in new_findings:
        print(f'  {f}')
    sys.exit(1)
print(f'All {len(findings)} findings are whitelisted.')
"
```
If new findings appear (not in whitelist), STOP — either fix the dead code or add to `vulture-whitelist.txt` (UTF-8 encoded). Do not commit until this passes.

## Step 2.8: Pre-commit run on staged files (NEW — Plan 72)
```powershell
pre-commit run --files <staged_files>
```
If any hook fails, STOP — fix the issue before committing. Pre-commit hooks are the last gate before `git commit`. Per OR32, NEVER use `git commit --no-verify` to bypass hooks.

## Step 3: File-scoped mypy on touched files
```powershell
mypy <files_touched> --ignore-missing-imports 2>&1 | Select-Object -Last 3
```
Expected: error count ≤ baseline. NEVER `mypy .` (except 5-plan checkpoints).

## Step 4: Commit code (in-scope files only)
```powershell
git add <in-scope files only>
git commit -m "checkpoint: prompt-{N}"
```

## Step 5: Create tag
```powershell
git tag prompt-{N}
```

## Step 6: Tag existence check (MANDATORY)
```powershell
git tag --list prompt-{N}
```
If empty, tag wasn't created. Create it before proceeding.

## Step 7: Tag verification
```powershell
git show prompt-{N} --stat | Select-Object -First 30
```
Verify file list contains ONLY in-scope files. If unexpected files appear, delete tag, clean, re-commit, re-tag.

## Step 8: Update CHANGELOG.md (temp-file pattern, append to END)
Write entry to temp file:
```powershell
$lines = @(
    "",
    "## <YYYY-MM-DD> HH:MM — prompt-{N}",
    "",
    "**Plan**: <one-line plan title>",
    "",
    "**Changed**:",
    "- <file>: <what changed (1 line per file)>",
    "",
    "**Results**:",
    "- Tests: <count> passed, <count> skipped",
    "- Ruff: <before> → <after>",
    "- Coverage: core <X>%, system <Y>%, memory <Z>%, adapters <A>%, skills <B>%",
    "- Tag: prompt-{N} verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-{N}.md" -Value $lines -Encoding utf8
```
Record old count, append, verify new count:
```powershell
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-{N}.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```
Verify: `$newCount > $oldCount` and last 12 lines show the new entry.

Clean up temp file:
```powershell
Remove-Item "C:\Jarvis\scan\logs\changelog-entry-prompt-{N}.md"
```

## Step 9: Rule proposal (L20 — MANDATORY)

Include either Option A (propose a new rule) or Option B (explicit none with justification listing patterns considered). Silence is NOT acceptable.

**If proposing a rule based on a landmine captured at Step 11**, include the source reference: e.g., "Source: landmine L{n}" — so the rule's diagnostic context is traceable. The landmine itself is never edited after capture (append-only).

## Step 10: Update PLANS.md

`PLANS.md` (in repo root) is the dynamic project state.

**IMPORTANT**: Use the Edit tool (AGENTS.md OR7) with exact `old_str`/`new_str` pairs. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content`.

Update all 6 sections:

- **(a) Completed prompts table**: add new row at the bottom with #, prompt name, test count, one-line notes.
- **(b) Test baseline**: update "Current baseline:" line if test count changed. Include new count and source (Plan {N} S{step}).
- **(c) Static analysis baseline**: update the 5-tool table if any tool count changed. Include source (Plan {N} S{step}) and delta notes. Also fill in Coverage row percentages (added at Plan 72 S10) with actual values from the test run.
- **(d) Next 5 prompts queue**: shift the queue — Plan {N+1} becomes active, add a new open slot at the bottom. If the active plan changed scope, update its queue entry.
- **(e) Status sections**: if any feature moved between sections (e.g., from "Built but not reachable" to "Works right now"), update the 4 status subsections.
- **(f) Baseline reconciliation notes**: add explanation of any tool count deltas, with tolerance justification (within/outside acceptable range).

After all updates, verify with:
```powershell
git diff PLANS.md | Select-Object -First 30
```
Confirm only the 6 intended sections changed. If unexpected sections appear, revert and re-edit.

## Step 11: Update LANDMINES.md (only if new failure pattern)

If this plan hit a new failure pattern not covered by existing landmines, append a new entry to `LANDMINES.md` using the structured format:
- **L{n+1}**: one-line label
- Trigger: what happened this prompt — concrete, with file + line
- Impact: why it bites
- Mitigation: how to avoid it next time

**Landmines are append-only** — capture once, never edit after. Do NOT add "FIXED" cross-references to landmine entries when a rule is later added to AGENTS.md. The linkage goes the other way: the AGENTS.md rule references its source landmine ("Source: landmine L{n}") at the time the rule is proposed.

If no new failure patterns were encountered, skip this step. Silence is acceptable here (unlike C9 — landmines are only added when patterns actually emerge).

## Step 12: Commit docs
```powershell
git add CHANGELOG.md PLANS.md LANDMINES.md "GLM Prompts/plan-{N}*.md"
git commit -m "docs: prompt-{N} changelog, plans, and landmines update"
```
(If `LANDMINES.md` was not updated this plan, omit it from the `git add`. The `"GLM Prompts/plan-{N}*.md"` glob is REQUIRED per OR39 — plan files must be committed to git. If no plan files exist for this plan (e.g., named plans that don't follow the `plan-{N}` pattern), omit the glob. For named plans, substitute the actual plan file pattern, e.g., `"GLM Prompts/plan-rule-cleanup*.md"`. (Directory name retained for filesystem compatibility; the Prompt Creator role can be GLM or Kimi.))

**OR39 reminder**: Plan files are part of the project record. Failing to commit them creates git history gaps (see L20). If `git status` shows untracked plan files at this step, they MUST be added.

## Step 13: Push
```powershell
git push origin master
git push origin prompt-{N}
```

## Step 14: Post-push verification (MANDATORY)
```powershell
git ls-remote --tags origin | Select-String "prompt-{N}"
```
If empty, push failed. Fix before reporting completion.

## Completion checklist

Paste ALL of:
1. C1 test suite output (last 5 lines)
2. C5 commit output
3. C6 tag created (git tag --list)
4. C7 file list (git show --stat)
5. C8 CHANGELOG (last 12 lines)
6. C9 rule proposal (block or "none" with justification)
7. C10 PLANS.md updates (paste git diff showing all 6 sections: Completed Prompts, Test Baseline, Analysis Baseline, Queue Shift, Status Sections, Reconciliation Notes)
8. C11 LANDMINES.md update (paste new entry, OR "no new failure patterns this plan")
9. C12 docs commit output
10. C13 push output
11. C14 tag on origin (git ls-remote output)

If ANY check fails or output is missing, the plan is NOT complete.
