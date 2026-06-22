---
name: jarvis-close
description: "Sovereign AI closing sequence — C1 through C13. Run this after all plan work is complete. Includes test suite, lint, commit, tag, changelog, handoff update, push, and verification."
---

# Jarvis Close — Plan Closing Sequence

Execute each step in order. Paste output for each. Do NOT skip steps.

## Step 1: Full test suite
```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```
Expected: `1167 passed, 55 skipped`. If tests fail, STOP.

## Step 2: Ruff check on touched files
```powershell
ruff check <files_touched> 2>&1 | Select-Object -Last 3
```
Expected: zero errors.

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
    "## 2026-06-21 HH:MM — prompt-{N}",
    "",
    "**Plan**: <one-line plan title>",
    "",
    "**Changed**:",
    "- <file>: <what changed (1 line per file)>",
    "",
    "**Results**:",
    "- Tests: <count> passed, <count> skipped",
    "- Ruff: <before> → <after>",
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

## Step 9: Rule proposal (L20 — MANDATORY)

Include either Option A (propose a new rule) or Option B (explicit none with justification listing patterns considered). Silence is NOT acceptable.

## Step 10: Update SOVEREIGN_AI_HANDOFF.md
- Update "Last updated" line
- Update test baseline + static analysis baseline
- Add row to Completed prompts table
- Update Next 5 prompts (remove completed plan, shift up)

## Step 11: Commit docs
```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-{N} changelog and handoff update"
```

## Step 12: Push
```powershell
git push origin master
git push origin prompt-{N}
```

## Step 13: Post-push verification (MANDATORY)
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
7. C10 handoff updates
8. C11 docs commit output
9. C12 push output
10. C13 tag on origin (git ls-remote output)

If ANY check fails or output is missing, the plan is NOT complete.
