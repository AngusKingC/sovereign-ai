---
name: jarvis-verify
description: "Run Sovereign AI verification after editing files. Checks syntax, diff scope, and runs targeted tests. Use after every file edit or batch of edits, before the full closing sequence."
---

# Jarvis Verify — Post-Edit Verification

Run this after editing files, before proceeding to the next step or the closing sequence.

## Step 1: Syntax check all edited .py files

For each .py file you edited, run:
```powershell
python -c "import ast; ast.parse(open('<file>.py').read())"
```

If ANY file has a syntax error, STOP — fix before proceeding. Do not wait for tests to catch it.

## Step 2: Diff check — confirm only intended files changed

```powershell
git diff --stat
```

Review the output. If unexpected files appear in the diff, STOP and investigate. Only files you intentionally edited should appear.

## Step 3: Run targeted test file(s)

For each production file you edited, run its corresponding test file:
```powershell
python -m pytest tests/test_<name>.py -v | Select-Object -Last 5
```

If tests fail:
1. Do NOT revert yet — read the failure output
2. Determine if the failure is from your edit or pre-existing
3. If from your edit: fix the edit or stash with git stash (recoverable) or revert with git checkout -- <file> (destructive — only if you're sure)
4. If pre-existing: note in CHANGELOG, continue

## Step 4: Ruff check on touched files

```powershell
ruff check <files_touched> 2>&1 | Select-Object -Last 3
```

If ruff finds new errors introduced by your edits, fix them before proceeding.

## Expected result

All syntax checks pass, diff shows only intended files, targeted tests pass (check SOVEREIGN_AI_HANDOFF.md for current baseline). If any step fails, STOP and fix before moving to the next file or the closing sequence.
