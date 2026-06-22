# Plan 48.1: Fix CHANGELOG append procedure — temp-file pattern to avoid PowerShell here-string hangs

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first):
> `git diff --stat prompt-48..HEAD -- SOVEREIGN_AI_HANDOFF.md`
> (Plan 48.1 only edits the handoff — no production code changes.)
> If the handoff changed since prompt-48, compare the CHANGELOG append
> procedure section (lines 269-273) against the current state below;
> on mismatch, STOP.

## Status
- Priority: P1
- Effort: S
- Risk: LOW
- Depends on: prompt-48 (in progress — Plan 48.1 unblocks Plan 48's Step 3 CHANGELOG entry AND prevents the same hang in Plan 48's remaining closing steps)
- Planned at: commit prompt-48 (in progress), 2026-06-20
- Revision: REV1 (2026-06-20) — initial draft.
- Revision: REV2 (2026-06-20) — incorporates Claude round-1 review findings 1-3 (Step 4.1 Linux path → Windows placeholder; "Current state" 1 file → 3 files matching S5 + context brief; Gate 3 + S3 truncated-append predicate added with 60-line floor).
- Revision: REV3 (2026-06-20) — incorporates S3b false-positive fire. Devin's append was 33 lines (correct for the 37-line full entry), but S3b's 60-line threshold was based on a bad "~80 lines" estimate. Actual full entry is 37 lines (markdown table = 1 line per row, not multi-line). Threshold lowered from 60 → 30 (20% below actual 37, still catches truncation). Gate 3 updated to match. Lesson added to handoff L15: derive truncation floors from ACTUAL entry line count, not estimates.

## Why this matters

Plan 48's Step 3 hung when Devin tried to append a ~80-line CHANGELOG entry using `Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Value @" ... "@`. PowerShell here-strings require the closing `"@` at **column 1 with zero leading whitespace**; if the editor auto-indents or the paste introduces any leading space, the here-string never closes and PowerShell waits forever for more input. This is the second PowerShell file-operation failure (the first was the `Get-Content | Measure-Object` truncation landmine L7). The current CHANGELOG append procedure (handoff lines 269-273) mandates `Add-Content` with here-strings — it's the source of the hang. Plan 48.1 replaces the procedure with a temp-file-then-append pattern that's immune to here-string parsing issues, and adds L15 to the known landmines so future plans don't repeat the mistake. This is a process-discipline fix (documentation only, no production code changes) — same category as prompt-37.6.1 which added Rule 19.

## Current state

**Files in scope (Plan 48.1 may edit only these — 3 files):**
- `SOVEREIGN_AI_HANDOFF.md` — the CHANGELOG append procedure section (lines 269-273) + the known landmines list (add L15) + completed-prompts table (C8). The plan template's CHANGELOG example is embedded in the handoff (lines 199-245), so updating the procedure updates the template for all future plans.
- `plans/plan-48.md` (or the local copy at `C:\Jarvis\plans\plan-48.md`) — Step 4 updates its CHANGELOG append procedure section to match the handoff, so Plan 48's remaining closing steps (C6-C11) use the new temp-file pattern.
- `CHANGELOG.md` (at `C:\Jarvis\CHANGELOG.md`) — Step 3 appends Plan 48's stuck Step 3 entry (55-CVE table); C6 appends Plan 48.1's own entry. Both use the new temp-file pattern.

**Step 0 — verify current state (do this before any edits; paste all output to CHANGELOG entry "Step 0"):**

0.1. `git rev-parse HEAD` — capture commit SHA at plan-start. Paste to CHANGELOG.

0.2. `git ls-remote --tags origin | findstr prompt-48` — confirm prompt-48 tag is on origin (Plan 48 should have been tagged before this fix-up starts; if Plan 48 is NOT yet tagged, see STOP S2). If absent AND Plan 48 is still in progress (not tagged yet), proceed — Plan 48.1 is a mid-prompt fix-up.

0.3. `Get-Content SOVEREIGN_AI_HANDOFF.md | Select-Object -Skip 268 -First 10` — paste lines 269-278 to CHANGELOG. Confirm: the CHANGELOG append procedure currently says:
   - `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count` for line counts
   - `Add-Content` to append
   - "NEVER paste into editor, NEVER use insert operations"
   - Example session uses `Add-Content -Path ... -Value @" ... "@`

0.4. `[System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count` — capture current CHANGELOG line count. Paste to CHANGELOG. This is the baseline for Step 3 verification.

0.5. `Test-Path C:\Jarvis\scan` — confirm the `scan\` directory exists (Plan 48 created it for scan outputs). If not, create it: `mkdir C:\Jarvis\scan`. The temp file in Step 3 goes here.

0.6. `Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "L15|here-string|temp-file"` — confirm L15 does NOT already exist and the temp-file pattern is NOT already documented. If either exists, STOP — someone already did part of this fix.

If any of these do not match the description above, STOP — the plan was written against stale state.

**Repo conventions:**
- This is a documentation-only plan. No production code changes. No test changes. No architecture rule changes.
- The handoff is the source of truth for process rules. Updating it updates the plan template for all future plans.

## What to change

### Step 1 — Add L15 to the handoff's known landmines

Edit `SOVEREIGN_AI_HANDOFF.md`. Find the known landmines list (the section starting with "Known landmines — Claude checks every plan against these", around line 359). Add L15 after L14 (or after the last existing landmine):

```markdown
- **PowerShell here-strings + `Add-Content` hang on large entries (L15, prompt-48.1)**: The `@" ... "@` here-string requires the closing `"@` at column 1 with zero leading whitespace; if auto-indented by the editor or mis-pasted, PowerShell waits forever for more input (Plan 48 Step 3 hung on this). Additionally, `Add-Content` with very long `-Value` is slow + file-lock-prone on 7000+ line CHANGELOG files. **Fix**: for CHANGELOG entries >20 lines, write to a temp file first (`$entry | Out-File -FilePath C:\Jarvis\scan\entry.md -Encoding utf8`), then append with `Get-Content C:\Jarvis\scan\entry.md | Add-Content -Path C:\Jarvis\CHANGELOG.md`. Verify with `[System.IO.File]::ReadAllLines(...).Count` before and after. The temp-file pattern avoids both the here-string parsing issue and the `Add-Content` file-lock deadlock. For entries ≤20 lines, `Add-Content -Value @"..."@` is still acceptable IF the closing `"@` is at column 1 — but the temp-file pattern is always safer.
```

**Verification**:
```
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "L15"
```
Expected: ≥1 match. Paste literal output to CHANGELOG.

### Step 2 — Replace the CHANGELOG append procedure in the handoff

Edit `SOVEREIGN_AI_HANDOFF.md`. Find the "CHANGELOG append procedure (PowerShell, because file locks)" section (around line 269). Replace the ENTIRE section (from the heading through the example session) with:

```markdown
### CHANGELOG append procedure (PowerShell, because file locks)

Per handoff lines 269-273 (updated prompt-48.1). Use these exact PowerShell idioms — do not substitute.

- **Line count**: `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count`. NEVER use `Get-Content | Measure-Object` — it truncates large files.
- **Append method (L15 — temp-file pattern for entries >20 lines)**: write the entry to a temp file first, then append. This avoids PowerShell here-string parsing issues (`"@` must be at column 1 with zero leading whitespace; auto-indent hangs forever) AND `Add-Content` file-lock deadlocks on large CHANGELOG files.
- **Append method (for entries ≤20 lines)**: `Add-Content -Path r"C:\Jarvis\CHANGELOG.md" -Value @"..."@` is acceptable IF the closing `"@` is at column 1. The temp-file pattern is always safer — use it if in doubt.
- **NEVER paste into the editor** for entries >20 lines — file locks + auto-indent can corrupt the here-string. For entries ≤20 lines, pasting into the editor + verifying line count is an acceptable fallback if `Add-Content` fails.
- **Before appending**: record current line count with `[System.IO.File]::ReadAllLines(...).Count`.
- **After appending**: verify new count exceeds previous, verify last 5 lines with `Get-Content ... | Select-Object -Last 5`.
- **Close the file in the IDE before running `Add-Content`** — file locks will cause silent truncation.

**Standard temp-file append pattern (use for ALL entries >20 lines)**:
```powershell
# 1. Write the entry to a temp file (here-string is safe here — Out-File handles it)
$entry = @"
## 2026-06-20 HH:MM — Plan NN Step N

**What was done**: <concrete actions>

**Files Modified**:
- <file>: <changes>

**What failed**: <none / failures and resolution>

**Testing Results**: <baseline → final, with command>

**Verification Gate Output**:
``<literal output>``
"@

$entry | Out-File -FilePath C:\Jarvis\scan\changelog-entry.md -Encoding utf8

# 2. Close the IDE if CHANGELOG.md is open, then append
$before = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\changelog-entry.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md"
$after = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
Write-Host "Before: $before, After: $after"
Get-Content r"C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5

# 3. Clean up temp file
Remove-Item C:\Jarvis\scan\changelog-entry.md
```

**Critical**: the closing `"@` in step 1 MUST be at column 1 (no leading whitespace). If using VS Code, disable auto-indent for PowerShell files or paste with Ctrl+Shift+V (paste without formatting). If the here-string still hangs, write the entry to the temp file using the editor directly (not PowerShell) and skip step 1.
```

**Verification**:
```
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "temp-file pattern|L15|Out-File -FilePath C:.Jarvis.scan.changelog-entry"
```
Expected: ≥3 matches. Paste literal output to CHANGELOG.

### Step 3 — Apply the new procedure to Plan 48's stuck Step 3 CHANGELOG entry

Plan 48's Step 3 CHANGELOG entry (the one that hung) is the immediate test case for the new procedure. Devin already drafted the content — it's the 55-CVE table. Apply it using the temp-file pattern from Step 2:

3.1. Create the temp file `C:\Jarvis\scan\plan-48-step3-entry.md` with the content Devin already drafted (the 14-row CVE table + diskcache note + verification output). Use the editor or `Out-File` — either is fine since this is the temp file, not the CHANGELOG itself.

3.2. **Verify the temp file was created correctly**:
```
[System.IO.File]::ReadAllLines("C:\Jarvis\scan\plan-48-step3-entry.md").Count
```
Expected: ~80 lines. Paste literal output to CHANGELOG.
```
Get-Content C:\Jarvis\scan\plan-48-step3-entry.md | Select-Object -First 3
```
Expected: starts with `## 2026-06-20 11:30 — Plan 48 Step 3`. Paste literal output.

3.3. **Close the IDE if CHANGELOG.md is open**, then append:
```powershell
$before = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\plan-48-step3-entry.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md"
$after = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Write-Host "Before: $before, After: $after"
Get-Content "C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5
```
Expected: `$after` > `$before` (by ~80 lines). The last 5 lines should show the end of the Plan 48 Step 3 entry. Paste literal output to CHANGELOG. **If `$after` == `$before`**, STOP — the append failed silently; investigate (likely a file lock — close the IDE and retry).

3.4. **Clean up the temp file**:
```
Remove-Item C:\Jarvis\scan\plan-48-step3-entry.md
```

3.5. **Verification**:
```
[System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
```
Expected: (Step 0.4 baseline + ~80). Paste literal output. Confirm the count increased by approximately 80 lines.

### Step 4 — Update Plan 48's own CHANGELOG append procedure section

Plan 48 (the security plan, currently in progress) has its OWN CHANGELOG append procedure section (copied from the handoff template). Update it to match the new handoff procedure so Plan 48's remaining closing steps (C6-C11) use the temp-file pattern.

4.1. Edit the local copy of `plans/plan-48.md` (relative to the repo root — on Devin's Windows env, this is `C:\Jarvis\plans\plan-48.md`; on Linux scan env, `/home/z/my-project/download/plans/plan-48.md`). Find the "CHANGELOG append procedure (PowerShell, because file locks)" section. Replace it with the same content as Step 2 (the new temp-file pattern).

4.2. **Verification**:
```
Select-String -Path <plan-48.md> -Pattern "temp-file pattern|Out-File -FilePath"
```
Expected: ≥2 matches. Paste literal output to CHANGELOG. (Use the actual path to plan-48.md on your system — `C:\Jarvis\plans\plan-48.md` on Windows, or the Linux equivalent.)

## Verification gates (run in order, all must pass)

1. `Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "L15"` — expected: ≥1 match (L15 landmine added). Paste literal output.
2. `Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "temp-file pattern"` — expected: ≥1 match (procedure updated). Paste literal output.
3. `[System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count` — expected: count is at least (Step 0.4 baseline + 30). **REV3**: the 30-line floor (20% below the actual 37-line full entry) catches truncated appends. If the increase is less than 30, STOP — the temp file may have been truncated during write or append. The Plan 48 Step 3 entry was appended successfully only if the count increased by ≥30 lines. Paste literal output. **Note**: the original REV2 threshold was 60 (based on a bad "~80 lines" estimate); the actual full entry is 37 lines (markdown tables are 1 line per row in raw text), so 60 caused a false-positive S3b fire on Devin's correct 33-line append.
4. `Get-Content "C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5` — expected: ends with the Plan 48 Step 3 entry content. Paste literal output.
5. `Select-String -Path <plan-48.md> -Pattern "temp-file pattern"` — expected: ≥1 match (Plan 48's procedure updated). Paste literal output.
6. Manual smoke (any shell — landmine L11):
   ```
   python -c "print('CHANGELOG line count:', len(open(r'C:\Jarvis\CHANGELOG.md').readlines()))"
   ```
   Expected: line count matches Step 3. Paste literal output.

## STOP conditions

- **S0**: If Step 0.1 reveals `HEAD` is not a descendant of `prompt-48` (or the in-progress Plan 48 commit), STOP — Plan 48.1 must be applied on top of Plan 48.
- **S1**: If Step 0.2 shows `prompt-48` tag is absent from origin AND Plan 48 has been marked complete, STOP — Plan 48 was never properly tagged (landmine L5). If Plan 48 is still in progress (not yet tagged), proceed.
- **S2**: If Step 0.6 reveals L15 already exists OR the temp-file pattern is already documented, STOP — someone already did this fix; investigate before proceeding.
- **S3**: If Step 3.3's `$after` == `$before`, STOP — the append failed silently (likely a file lock). Close the IDE and retry. If retry fails, STOP and report.
- **S3b (REV2, threshold lowered REV3)**: If Step 3.3's `$after` < (`$before` + 30), STOP — partial append; the temp file may have been truncated during write or the append was interrupted. Investigate the temp file's actual line count vs the appended line count. The 30-line floor is 20% below the actual 37-line full entry; a successful append should be ≥30 lines, anything less indicates truncation. **REV3 note**: the original REV2 threshold was 60 (based on a bad "~80 lines" estimate); the actual full entry is 37 lines (markdown tables are 1 line per row in raw text), so 60 caused a false-positive S3b fire on Devin's correct 33-line append. Always derive truncation floors from the ACTUAL entry line count, not estimates.
- **S4**: If Step 3.3's last 5 lines do NOT show the Plan 48 Step 3 entry content, STOP — the wrong content was appended. Investigate.
- **S5**: If a file outside the in-scope list needs editing, STOP — out-of-scope. The 3 in-scope files are listed in "Current state" above: `SOVEREIGN_AI_HANDOFF.md`, `plans/plan-48.md`, and `CHANGELOG.md` (the append target).
- **S6**: If any verification gate is marked PASSED without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S7**: If any closing step (C1-C10 below) is marked DONE without literal output pasted to CHANGELOG, STOP (landmine L2 / Rule 19).
- **S8**: If C5 (`git show prompt-48.1 --stat`) reveals a file outside the in-scope list (other than `CHANGELOG.md` and `SOVEREIGN_AI_HANDOFF.md`), STOP — delete the tag with `git tag -d prompt-48.1`, unstage, re-tag. Do not push the bad tag.
- **S9**: If C10 (`git push origin prompt-48.1`) succeeds locally but `git ls-remote --tags origin | findstr prompt-48.1` returns empty, STOP — the tag did not reach origin (landmine L5). Retry. If retry fails, report to user.

## Closing steps (mandatory, every prompt)

These run AFTER all verification gates (Gates 1-6) pass. Each step requires literal output pasted to CHANGELOG (landmine L2 / Rule 19). Do not batch. **Use the new temp-file pattern from Step 2 for ALL CHANGELOG entries in this closing section** — Plan 48.1 is the first plan to use the new procedure dogfooding-style.

**C1** — Run full test suite:
```
python -m pytest tests/ -q --tb=no | Select-Object -Last 3
```
Expected: 1167 passed, 55 skipped, 0 failed, 0 warnings (unchanged — Plan 48.1 is docs-only). Paste literal output.

**C2** — Ruff check on touched files:
```
ruff check SOVEREIGN_AI_HANDOFF.md
```
Expected: 0 errors (ruff doesn't lint markdown, but run anyway to confirm no accidental .py changes). Paste literal output.

**C3** — Verify handoff structure:
```
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "^## |^### "
```
Expected: section headings still present and ordered. Paste literal output.

**C4** — Commit and tag:
```
git add SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
git commit -m "docs: prompt-48.1 CHANGELOG append procedure fix + L15 landmine"
git tag prompt-48.1
```
Verify:
```
git log -1 --oneline
git tag --list prompt-48.1
```
Expected: `prompt-48.1` appears in both. Paste literal output.

**C5** — Verify file list in the tag:
```
git show prompt-48.1 --stat
```
Expected: file list contains ONLY `SOVEREIGN_AI_HANDOFF.md` and `CHANGELOG.md`. If unexpected file appears, run `git tag -d prompt-48.1`, `git reset HEAD~1`, clean, re-commit, re-tag. Do NOT push the bad tag. Paste literal output.

**C6** — Update `CHANGELOG.md` with Plan 48.1's own entry (using the new temp-file pattern — dogfooding):
```powershell
$entry = @"
## 2026-06-20 HH:MM — Plan 48.1

**What was done**: Fixed CHANGELOG append procedure to use temp-file pattern (avoids PowerShell here-string hangs on large entries). Added L15 to known landmines. Applied the new procedure to unblock Plan 48's stuck Step 3 CHANGELOG entry (55-CVE table). Updated Plan 48's own CHANGELOG procedure section for remaining closing steps.

**Files Modified**:
- SOVEREIGN_AI_HANDOFF.md: added L15 landmine; replaced CHANGELOG append procedure (lines 269-273) with temp-file pattern.
- CHANGELOG.md: appended Plan 48's Step 3 entry (55-CVE table) using the new temp-file pattern.
- plans/plan-48.md: updated CHANGELOG append procedure section to match handoff.

**What failed**: Plan 48 Step 3 hung on `Add-Content -Value @"..."@` (PowerShell here-string closing `"@` not at column 1). Resolved by switching to temp-file pattern.

**Testing Results**: CHANGELOG line count: (Step 0.4 baseline) → (baseline + ~80). Test suite unchanged.

**Verification Gate Output**:
``<literal output of Gates 1-6>``
"@

$entry | Out-File -FilePath C:\Jarvis\scan\plan-48.1-entry.md -Encoding utf8
$before = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\scan\plan-48.1-entry.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md"
$after = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Write-Host "Before: $before, After: $after"
Get-Content "C:\Jarvis\CHANGELOG.md" | Select-Object -Last 5
Remove-Item C:\Jarvis\scan\plan-48.1-entry.md
```
Expected: `$after` > `$before`. Paste literal output to CHANGELOG.

**C7** — Commit CHANGELOG update:
```
git add CHANGELOG.md
git commit -m "docs: prompt-48.1 changelog entry"
```
Verify with `git log -1 --oneline`. Paste literal output.

**C8** — Update `SOVEREIGN_AI_HANDOFF.md` completed-prompts table:
- Add row: `| 48.1 | CHANGELOG append procedure fix (temp-file pattern + L15) | 1167 | Docs-only. Fixed PowerShell here-string hang. |`

**C9** — Commit handoff update:
```
git add SOVEREIGN_AI_HANDOFF.md
git commit -m "docs: prompt-48.1 handoff update"
```
Verify with `git log -1 --oneline`. Paste literal output.

**C10** — Push to origin:
```
git push origin master
git push origin prompt-48.1
```
**Tag-push gate (landmine L5)**: after pushing, verify:
```
git ls-remote --tags origin | findstr prompt-48.1
```
Expected: a line containing `prompt-48.1`. If empty, retry. If retry fails, report to user; do NOT mark Plan 48.1 complete. Paste literal output.

## Out of scope

- **Plan 48's remaining steps** (Steps 4-5, Gates 1-8, Closing C1-C11) — Plan 48.1 only unblocks Step 3's CHANGELOG entry and updates the procedure for the rest. Plan 48 resumes after Plan 48.1 completes.
- **Production code changes** — Plan 48.1 is docs-only. No `.py` files touched.
- **Test changes** — no test files touched.
- **Updating plans 45-47** — those plans are complete; their CHANGELOG procedure sections are historical and don't need updating.
- **Updating the plan template beyond the handoff** — the plan template IS in the handoff (lines 199-245), so updating the handoff updates the template.
- **Refactoring `Add-Content` usage in existing scripts** — out of scope. The new procedure applies to future CHANGELOG entries only.

## For Claude review (Devin: do not execute)

1. **Step 2 procedure text**: the new CHANGELOG append procedure uses `Get-Content <temp> | Add-Content <target>`. Is this the most reliable pattern, or should it use `[System.IO.File]::AppendAllText` instead? The latter is a single syscall (no pipe), but requires reading the temp file content into a string variable first. Tradeoff: `Get-Content | Add-Content` is simpler and more PowerShell-idiomatic; `AppendAllText` is more robust but more verbose.

2. **L15 threshold (20 lines)**: the procedure says "for entries >20 lines, use temp-file pattern; for ≤20 lines, `Add-Content -Value @"..."@` is acceptable". Is 20 the right threshold? Too low and Devin uses the temp-file pattern for trivial entries (overhead). Too high and the here-string hang risk persists for medium entries.

3. **Step 4 (update Plan 48's procedure section)**: Plan 48 is currently in progress. Should Plan 48.1 update Plan 48's plan file directly, or should it just update the handoff and tell Devin to re-read the handoff for the remaining closing steps? Direct edit is more reliable; handoff-reread is less invasive.

4. **Dogfooding in C6**: Plan 48.1's own CHANGELOG entry (C6) uses the new temp-file pattern. If the pattern has a bug, C6 will hang too. Is this a good test (catches bugs immediately) or a risk (Plan 48.1 itself gets stuck)?

5. **Temp file location (`C:\Jarvis\scan\`)**: the procedure uses `C:\Jarvis\scan\` for temp files. Is this the right location, or should it use `$env:TEMP` (the system temp dir)? `C:\Jarvis\scan\` keeps it in the repo (visible, easy to debug) but clutters the repo; `$env:TEMP` is cleaner but harder to find if something goes wrong.
