---
name: jarvis-verify
description: "Run Sovereign AI verification after editing files. Checks syntax, diff scope, and runs targeted tests. Use after every file edit or batch of edits, before the full closing sequence."
---

# Jarvis Verify — Post-Edit Verification

Run this after editing files, before proceeding to the next step or the closing sequence.

## Step 1: Syntax check all edited .py files

For each .py file you edited, run:
```bash
python -c "import ast; ast.parse(open('<file>.py').read())"
```

If ANY file has a syntax error, STOP — fix before proceeding. Do not wait for tests to catch it.

## Step 2: Diff check — confirm only intended files changed

```bash
git diff --stat
```

Review the output. If unexpected files appear in the diff, STOP and investigate. Only files you intentionally edited should appear.

## Step 3: Run targeted test file(s)

For each production file you edited, run its corresponding test file:
```bash
python -m pytest tests/test_<name>.py -vvv
```

**Note**: Do NOT use `-q --tb=short` or pipe to `tail -n 5`. Run with full verbose output (`-vvv`) so hangs, stuck tests, and failure details are all visible.

If tests fail:
1. Do NOT revert yet — read the failure output
2. Determine if the failure is from your edit or pre-existing
3. If from your edit: fix the edit or stash with git stash (recoverable) or revert with git checkout -- <file> (destructive — only if you're sure)
4. If pre-existing: note in CHANGELOG, continue

## Step 4: Ruff check on touched files

```bash
ruff check <files_touched> 2>&1 | tail -n 3
```

If ruff finds new errors introduced by your edits, fix them before proceeding.

## Step 5: detect-secrets scan on touched files (NEW — Plan 72)
```bash
detect-secrets scan --baseline .secrets.baseline
```
If exit code != 0, a new secret-like string was introduced. Either:
- If false positive (e.g., test fixture with dummy API key string): update baseline with `detect-secrets scan > .secrets.baseline` and commit the change.
- If real secret: REMOVE from source immediately. Consider rotating the secret if it was committed.

## Step 6: Vulture check on touched files with whitelist (FIXED — Plan 75)
```bash
# Run vulture on touched files and check for new findings vs whitelist
python -c "
import subprocess, sys
files = sys.argv[1:]
if not files:
    print('No files to check')
    sys.exit(0)
result = subprocess.run(['vulture'] + files + ['--min-confidence', '80'], capture_output=True, text=True)
findings = [l for l in result.stdout.splitlines() if 'confidence' in l]
if not findings:
    print('No vulture findings.')
    sys.exit(0)
with open('txt/vulture-whitelist.txt', encoding='utf-8') as f:
    whitelist = set(l.strip() for l in f if l.strip())
new_findings = [f for f in findings if f not in whitelist]
if new_findings:
    print('NEW vulture findings (not in whitelist):')
    for f in new_findings:
        print(f'  {f}')
    sys.exit(1)
print(f'All {len(findings)} findings are whitelisted.')
" <files_touched>
```
If new findings appear (not in whitelist), either:
- Fix the dead code (preferred), OR
- Add to `txt/vulture-whitelist.txt` (UTF-8 encoded) with an inline comment in the source file explaining why it's whitelisted (e.g., `# vulture-whitelist: required by ABC interface`).

## Expected result

All syntax checks pass, diff shows only intended files, targeted tests pass (check PLANS.md for current baseline). detect-secrets baseline check passes. Vulture whitelist check passes (no new dead code). If any step fails, STOP and fix before moving to the next file or the closing sequence.
