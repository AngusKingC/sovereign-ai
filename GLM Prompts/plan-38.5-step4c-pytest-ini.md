# Plan 38.5 — Step 4c: Create `pytest.ini` for subprocess transport warning suppression

> **Executor instructions**: This is the focused Step 4c sub-prompt of Plan 38.5. **Before executing this, finish any remaining Plan 38.5 steps (2, 3, 5) that haven't landed yet** — so the entire Plan 38.5 work can commit and push in one atomic unit. Then execute this Step 4c. Then do one commit, one tag, one push for all of Plan 38.5.
>
> If Plan 38.5 Steps 2, 3, 5 are already done (committed locally but not yet tagged), just do this Step 4c and fold everything into one commit.
>
> If Plan 38.5 has already been tagged and pushed, treat this as a follow-up sub-prompt with its own small tag (`prompt-38.5-step4c`).

## Status

- **Priority**: P1 (completes Plan 38.5 cat 2 warning fix)
- **Effort**: S (one new file, ~10 lines)
- **Risk**: LOW (no production code, no test code changes — just config)
- **Depends on**: Plan 38.5 Steps 1-3 attempted (Step 4b specifically — need to know if it worked)
- **In scope**: `pytest.ini` (new file) only
- **Out of scope**: `pyproject.toml` (doesn't exist — creating it would be a structural change requiring its own plan), test files, production code

## Why this matters

Plan 38.5 Step 4b tried to fix 4 remaining cat 2 warnings (PytestUnraisableException + ResourceWarning unclosed transport) via subprocess cleanup fixtures in `tests/skills/test_docker_skill.py` and `tests/skills/test_web_scraper.py`. Per prompt-38 CHANGELOG line 7124, these warnings are a pytest-asyncio/Windows interaction, not a code bug — Step 4b's fixture cleanup may not fully eliminate them.

Step 4c is the fallback: suppress with `filterwarnings` and document the root cause with a Plan-38.5 ticket reference. **Legitimate suppression (warning hidden, ticket visible, root cause documented) — not silent noise.**

## What to change

### Step 1 — Verify Step 4b's result

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "PytestUnraisableException|unclosed transport"
```

**Paste literal output into CHANGELOG** (Rule 19 evidence).

- If **zero matches**: Step 4b worked. Skip Steps 2-3 of this sub-prompt. Document in CHANGELOG: "Step 4c not needed — Step 4b fully eliminated cat 2 warnings."
- If **non-zero matches** (likely 4): proceed to Step 2.

### Step 2 — Create `pytest.ini`

**File**: `C:\Jarvis\pytest.ini` (new file)

**Exact content** (copy-paste verbatim from this plan — do not retype):

```ini
[pytest]
# Plan 38.5 Step 4c: subprocess transport cleanup warnings on Windows.
# Source: tests/skills/test_docker_skill.py and tests/skills/test_web_scraper.py
# use asyncio.create_subprocess_exec; pytest-asyncio event loop closes before
# subprocess transports clean up. Per prompt-38 CHANGELOG line 7124, this is a
# pytest-asyncio/Windows interaction, not a code bug. Suppression is the
# accepted workaround pending upstream pytest-asyncio fix.
filterwarnings =
    ignore::pytest.PytestUnraisableExceptionWarning
    ignore:unclosed transport:ResourceWarning
```

### Step 3 — Verify suppression works

```powershell
# Verify pytest picks up the new config (no syntax errors)
python -m pytest --co tests/skills/test_docker_skill.py -q

# Verify cat 2 warnings are now suppressed
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "PytestUnraisableException|unclosed transport"

# Overall warning count (should be 4 fewer than pre-Step-4c)
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 1
```

**Expected**:
- First command: runs without error, lists collected tests
- Second command: zero matches
- Third command: warning count reduced by 4 (the suppressed cat 2 warnings)

**If second command still shows matches after creating `pytest.ini`**: STOP. The `filterwarnings` syntax may not match the actual warning class. Paste literal warning output into CHANGELOG and report — do not silently broaden the suppression.

**Paste literal output of all three commands into CHANGELOG.**

## Verification gates

### Gate 1 — `pytest.ini` exists and is valid

```powershell
Test-Path C:\Jarvis\pytest.ini
python -m pytest --co tests/skills/test_docker_skill.py -q
```

**Expected**: `True` for first command. Second command runs without error.

### Gate 2 — Cat 2 warnings suppressed (or eliminated by Step 4b)

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "PytestUnraisableException|unclosed transport"
```

**Expected**: zero matches (either genuinely fixed by Step 4b, or suppressed by Step 4c's `filterwarnings`).

### Gate 3 — No new warnings introduced

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 1
```

**Expected**: warning count is 4 fewer than pre-Step-4c count (or unchanged if Step 4b already eliminated them and Step 1 above skipped the rest).

## STOP conditions

- **If Step 1 shows zero matches** (Step 4b worked): skip the rest, document in CHANGELOG.
- **If Step 3's second command still shows matches after creating `pytest.ini`**: STOP. Filterwarnings syntax may be wrong. Do not silently broaden suppression.
- **If any file other than `pytest.ini` needs editing for this sub-prompt**: STOP. This sub-prompt is one file only. (Other Plan 38.5 file edits belong to their respective steps.)

## Closing steps

**Fold into the main Plan 38.5 commit if Plan 38.5 hasn't been tagged yet.** Otherwise, separate tag.

### If folding into Plan 38.5 (preferred — one atomic commit):

1. Make sure all Plan 38.5 steps (2, 3, 4a/4b, 4c, 5) are complete with Rule 19 evidence in CHANGELOG
2. `git add` all in-scope files: modified test files, `adapters/gemini.py` (if migrated), `pytest.ini`, `SOVEREIGN_AI_HANDOFF.md`, `CHANGELOG.md`
3. `git commit -m "fix: prompt-38.5 — finish warnings cleanup (missed PytestWarning files, \J hunt, cat 2 remainder, Gemini migration)"`
   - **Conditional — Step 5 deferred?** If Gemini migration deferred to Plan 38.7, append: ` [partial: gemini-migration-pending]`
4. `git tag prompt-38.5`
5. `git show prompt-38.5 --stat` — verify file list (should include `pytest.ini`)
6. `git rev-parse prompt-38.5` — confirm hash matches the commit
7. Update `CHANGELOG.md` (append-only):
   - **Files Modified**: per-file detail including `pytest.ini` (new file, 10 lines)
   - **Implementation Notes**: Step 4b result (eliminated or not), Step 4c suppression applied with root cause citation
   - **Testing Results**: baseline (26 warnings from 38) → final (≤4 warnings)
   - **Verification Gate Output**: literal output of each gate
   - **Deferred actions** (if Step 5 deferred): Plan 38.7 queued for Gemini migration
8. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-38.5
   - Update test baseline to final count
   - If Step 5 deferred: add "Plan 38.7 — Gemini SDK migration" to deferred-actions list
9. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
10. `git commit -m "docs: prompt-38.5 changelog and handoff update"`
11. `git push origin master && git push origin prompt-38.5`
12. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-38.5` — verify the tag exists on the remote. **Do not skip this step.** (Per known landmine: prompt-38's tag-push gate was skipped — must not recur.)

### If Plan 38.5 already tagged and pushed (separate follow-up):

1. `git add pytest.ini`
2. `git commit -m "fix: prompt-38.5 Step 4c — add pytest.ini with subprocess transport warning suppression"`
3. `git tag prompt-38.5-step4c`
4. `git show prompt-38.5-step4c --stat` — verify only `pytest.ini` was added
5. Update `CHANGELOG.md` (append-only) with Step 4c evidence
6. Update `SOVEREIGN_AI_HANDOFF.md` test baseline warning count if changed
7. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
8. `git commit -m "docs: prompt-38.5 Step 4c changelog and handoff update"`
9. `git push origin master && git push origin prompt-38.5-step4c`
10. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-38.5` — verify the tag is on the remote.

## Out of scope

- `pyproject.toml` creation (defer to a future "modernize project layout" plan if needed)
- Any test file changes (Step 4b already done)
- Any production code changes
- Plan 38.5's other steps (2, 3, 5) — those are their own steps, just need to be done before the commit if not yet
- Broad-except audit, ruff triage, mypy triage — future plans

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This is a focused sub-prompt. Check that:

1. `pytest.ini` is the right choice over `pyproject.toml` (GLM chose `pytest.ini` because the project doesn't currently use `pyproject.toml`, and creating it would require structural decisions about build system and project metadata that are out of scope for a warnings cleanup).

2. The `filterwarnings` syntax is correct:
   - `ignore::pytest.PytestUnraisableExceptionWarning` — suppress all warnings of this class
   - `ignore:unclosed transport:ResourceWarning` — suppress ResourceWarning whose message matches "unclosed transport"
   
   Both are standard pytest filterwarnings syntax. Flag if either looks wrong.

3. The comment block is sufficient for audit purposes. It cites: (a) which plan added it, (b) which tests cause it, (c) why suppression is the accepted approach, (d) the CHANGELOG line that established the root cause. Anything missing?

4. The "fold into Plan 38.5 vs separate tag" logic is correct. GLM's default: fold if Plan 38.5 hasn't been tagged yet, separate tag if it has.

5. The STOP condition for "Step 3's second command still shows matches" is appropriate — does it correctly prevent silent broadening of the suppression?

6. The closing-step structure (one commit for code, one for docs, one tag, push both) is consistent with the standard prompt template.

**Output format**: Lead with verdict (ship as-is / ship with fix / send back), then list specific issues by severity. Skip praise. Cite specific line numbers when flagging factual errors.

**Known landmines to check against** (from SOVEREIGN_AI_HANDOFF.md "Claude review workflow" section):
- Tag-push gate must be verified with `git ls-remote --tags origin | findstr prompt-38.5` — closing step 12 (folded) or step 10 (separate) includes this. Verify it's not skipped.
- Rule 19 evidence requirement — Step 1 and Step 3 both require literal pytest output pasted into CHANGELOG. Verify the plan enforces this.
- No `global_rules.md` citations (file is unreachable, can't be verified).
- No re-guessing of disproved hypotheses — this plan builds on prompt-38 CHANGELOG line 7124's finding (subprocess transports, not httpx), doesn't re-litigate it.
