# Plan 54 — F401 Bulk Cleanup + Ship global_rules_v2.md + Fix Stale Handoff

**Prompt number**: 54
**Priority**: P3 (F401 cleanup) + P1 (rules ship + handoff fix folded in as prerequisites)
**Estimated scope**: ~118 files touched (F401), 1 file replaced (global_rules.md), 1 file updated (handoff)
**Baseline test count**: 1167 passed, 55 skipped, 0 failed (post-prompt-53)
**Baseline ruff F401 count**: 243 across 118 files (verified via clone — see S2)
**Target ruff F401 count after plan**: 0 (all 243 are auto-fixable with `--fix`)

---

## Why this plan exists

Three things need to happen, and folding them into one plan is cleaner than three sequential tiny plans:

1. **F401 bulk cleanup** — 243 unused-import errors across 118 files. All auto-fixable. This is the largest single ruff category remaining (358 total ruff errors - 243 F401 = 115 other rules after this plan).

2. **Ship `global_rules_v2.md`** — the v2 rules file (24→22 rules, with L19 datetime + L20 self-evolution + L21 CHANGELOG position) needs to replace Devin's local `global_rules.md`. This unblocks L20 (self-evolution) for all future plans. Devin's self-added Rule 25 (CHANGELOG append position) is preserved as L21 in v2.1.

3. **Fix stale handoff** — the handoff on master is stale by 3 plans (51, 52, 53 not in Completed table; baselines not updated). Devin's local handoff edits (Plan 58 addition) were never committed. This plan's C8 step will properly update the handoff as part of the normal closing sequence.

---

## Opening steps (S0)

These run BEFORE any other work. Copy verbatim into the plan execution.

### S0.1 — Verify prompt-53 completed and tag on origin

```powershell
git ls-remote --tags origin | Select-String "prompt-53"
```

**Expected**: returns `91720caab56c637c78ace3f2ae78e34eb365ac80  refs/tags/prompt-53`. If empty, STOP — prompt-53 tag wasn't pushed. Fix that first.

### S0.2 — Pull latest master

```powershell
git pull origin master
```

### S0.3 — Verify HEAD matches expected commit

```powershell
git rev-parse HEAD
```

**Expected**: `642f406844d667fb9823313d176499fbff501336` (the user's CHANGELOG rebuild commit, which has prompt-53's commit `91720ca` as ancestor). If different, STOP and report — master has moved since prompt-53.

### S0.4 — Ship global_rules_v2.md (replace Devin's local copy)

**Prerequisite (user must do this BEFORE handing plan to Devin)**: save the v2.1 file content to `C:\Jarvis\global_rules_v2_source.md` on Devin's machine. The user (human relay) will paste the v2.1 content from `/home/z/my-project/download/global_rules_v2.md` into a new file at that path. GLM must include the v2.1 content in the prompt to Devin, and the FIRST instruction Devin executes is saving that content to `C:\Jarvis\global_rules_v2_source.md`.

Devin's task:

1. **Verify the source file exists and is the v2.1 version**:
   ```powershell
   Test-Path C:\Jarvis\global_rules_v2_source.md
   Get-Content C:\Jarvis\global_rules_v2_source.md | Select-Object -First 3
   ```
   **Expected**: `True` and the first 3 lines show `# Devin Global Rules (v2)` header. If `False` or wrong content, STOP — the user has not yet placed the v2.1 source file. Report to user.

2. **Back up the existing v1 file first**:
   ```powershell
   Copy-Item C:\Jarvis\global_rules.md C:\Jarvis\global_rules_v1_backup.md
   ```

3. **Overwrite `global_rules.md` with v2.1 content from the source file** (avoids here-string fragility — use file copy, not paste-into-IDE):
   ```powershell
   Copy-Item C:\Jarvis\global_rules_v2_source.md C:\Jarvis\global_rules.md -Force
   ```

4. **Verify the replacement**:
   ```powershell
   Get-Content C:\Jarvis\global_rules.md | Select-Object -First 5
   ```
   **Expected**: shows `# Devin Global Rules (v2)` header and the opening paragraph.

5. **Verify rule count** (per Claude's review — the grep pattern `^\*\*L` matches rules starting at column 0):
   ```powershell
   Select-String "^\*\*L" -Path C:\Jarvis\global_rules.md | Measure-Object -Line
   ```
   **Expected**: returns `22` (L1 through L22, inclusive).

**STOP condition**: if the rule count is not 22, the replacement failed — restore from backup (`Copy-Item C:\Jarvis\global_rules_v1_backup.md C:\Jarvis\global_rules.md -Force`) and STOP. Report the actual count and the first/last 10 lines of the file to GLM.

**Why this step is here**: v2 rules activate L20 (self-evolution) and L19 (datetime consistency). L20 is required for the C9 rule-proposal step in this plan's closing sequence. L19 prevents the naive/aware datetime landmine from recurring. Devin's self-added Rule 25 is preserved as L21.

**Why file-copy instead of here-string**: a `@"..."@` here-string with ~180 lines of content is fragile — the closing `"@` must be at column 0, and any auto-indentation (as happened in Plan 48.1 and Plan 53's CHANGELOG entry) causes the terminal to hang. File-copy from a pre-placed source file avoids this entirely.

---

## Step 1 (S1) — Capture baseline counts

Run these and paste output into the execution log. These are the BEFORE numbers.

### S1.1 — Test count baseline

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 3
```

**Expected**: `1167 passed, 55 skipped in <time>`. If different, STOP — baseline has shifted.

### S1.2 — Ruff F401 count baseline

```powershell
ruff check . --select F401 2>&1 | Select-Object -Last 3
```

**Expected**: `Found 243 errors.` and `[*] 243 fixable with the --fix option.`. If different (more or fewer), note the actual count — it becomes the baseline for this plan.

### S1.3 — Ruff total count baseline

```powershell
ruff check . 2>&1 | Select-Object -Last 3
```

**Expected**: ~358 errors total. Record the actual number. After this plan, the new total should be `baseline - 243` (or whatever S1.2 reported).

### S1.4 — File-scoped mypy baseline (NOT `mypy .`)

For the files this plan will touch, capture per-file mypy counts. Since F401 cleanup touches ~118 files, capture mypy on the top 10 offenders only (the rest will be verified post-fix):

```powershell
mypy core/orchestrator.py core/worker_factory.py core/event_trigger.py core/handlers.py system/monitor_daemon.py system/resource_manager.py adapters/base.py cli/tui.py cli/command_history.py skills/file_writer/skill.py --ignore-missing-imports 2>&1 | Select-Object -Last 3
```

Record the error count. After F401 cleanup, this count should be ≤ baseline (F401 fixes sometimes also fix mypy "unused import" errors; they should never INCREASE mypy errors).

---

## Step 2 (S2) — Run F401 auto-fix

### S2.1 — Run the fix

```powershell
ruff check . --select F401 --fix
```

**Expected output**: ruff reports applying fixes to ~118 files. Record the actual output.

**STOP condition**: if ruff reports any errors that are NOT F401 (e.g. syntax errors preventing the fix), STOP and report. F401 --fix should never introduce syntax errors.

### S2.2 — Verify F401 count is now 0

```powershell
ruff check . --select F401 2>&1 | Select-Object -Last 3
```

**Expected**: `Found 0 errors.` If any remain, they are F401 instances ruff considers unsafe to auto-fix. Triage each remaining one manually:
- If the import is in `if TYPE_CHECKING:` block and used only for type hints → keep it, add `# noqa: F401` comment with reason
- If the import is in `__init__.py` and is a re-export → add it to `__all__` or add `# noqa: F401` with "re-export" reason
- If genuinely unused → remove manually

**Note**: Per S5 check below, 0 F401 are in `__init__.py` files (verified via clone), so re-export issues are unlikely. But verify.

---

## Step 3 (S3) — Run full test suite to catch any breakage

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Expected**: `1167 passed, 55 skipped in <time>` — SAME as baseline. F401 cleanup removes unused imports; it should NOT change test count.

**STOP conditions**:
- If FEWER tests passed → an import was load-bearing (e.g. a module that registered something on import). STOP, investigate, restore the import with a `# noqa: F401` comment explaining why.
- If MORE tests passed → unlikely, but investigate. Possibly a previously-skipped test now collects.
- If any test FAILS that passed before → an import was used in a way ruff didn't detect (e.g. via `getattr(module, "ClassName")`). STOP, restore the import with `# noqa: F401`.

**Per L9**: if a production file's import removal broke its test file, fix the test file in the same step. But for F401, the test file's imports were also cleaned — so this should be self-consistent.

---

## Step 4 (S4) — File-scoped mypy on changed files

```powershell
mypy core/orchestrator.py core/worker_factory.py core/event_trigger.py core/handlers.py system/monitor_daemon.py system/resource_manager.py adapters/base.py cli/tui.py cli/command_history.py skills/file_writer/skill.py --ignore-missing-imports 2>&1 | Select-Object -Last 3
```

**Expected**: error count ≤ S1.4 baseline. F401 fixes sometimes also resolve mypy "unused import" warnings; they should never INCREASE errors.

**STOP condition**: if mypy error count INCREASED, an import was load-bearing for type checking. STOP, restore the import with `# noqa: F401` comment.

**Per L18**: NEVER run `mypy .` (full-repo). File-scoped only. Full-repo mypy only at 5-plan checkpoints (Plan 55).

---

## Step 5 (S5) — Verify no `__init__.py` re-exports were broken

```powershell
Select-String "__all__" -Path . -Recurse -Include "__init__.py" | Measure-Object -Line
```

Record the count. Then for each `__init__.py` that has `__all__`, verify the listed names still resolve:

```powershell
Get-ChildItem -Recurse -Filter "__init__.py" | ForEach-Object { python -c "import $($_.Directory.Name -replace '\\','.'); print('OK')" 2>&1 }
```

**STOP condition**: if any package fails to import, an F401 fix removed a re-export. Restore the import with `# noqa: F401` and add to `__all__` if not already there.

**Note**: Per clone verification, 0 F401 are currently in `__init__.py` files, so this step should pass cleanly. But verify — the project may have implicit re-exports.

---

## Step 6 (S6) — Bandit verification (correct command this time)

Plan 53's bandit verification was broken — `bandit tests/ -ll` without `-r` skipped the directory scan. This plan uses the correct command.

```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108|Total issues|No issues" | Select-Object -First 5
```

**Expected**: `No issues identified.` OR `Total issues: ... 0 medium, 0 high` with B108 count = 0.

Per L14: the `--exclude` list is mandatory. Per the bandit docs: `-r` is required to scan directories recursively.

**STOP condition**: if B108 > 0, Plan 53's B108 fix was incomplete. STOP and report — do NOT fix in this plan (L5: don't expand scope). Log for a follow-up plan.

---

## Closing steps (C1-C12) — MANDATORY

Copy verbatim. Paste output for each step.

### C1 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

**Paste**: last 5 lines. **Expected**: `1167 passed, 55 skipped` (same as S1.1 baseline — F401 cleanup doesn't change test count).

### C2 — Ruff check on touched files

```powershell
ruff check . --select F401 2>&1 | Select-Object -Last 3
```

**Paste**: last 3 lines. **Expected**: `Found 0 errors.`

### C3 — Ruff total count (post-fix)

```powershell
ruff check . 2>&1 | Select-Object -Last 3
```

**Paste**: last 3 lines. **Expected**: `Found <N> errors.` where N = S1.3 baseline - 243 (or whatever S1.2 reported as fixed).

### C4 — File-scoped mypy on touched files

```powershell
mypy core/orchestrator.py core/worker_factory.py core/event_trigger.py core/handlers.py system/monitor_daemon.py system/resource_manager.py adapters/base.py cli/tui.py cli/command_history.py skills/file_writer/skill.py --ignore-missing-imports 2>&1 | Select-Object -Last 3
```

**Paste**: last 3 lines. **Expected**: error count ≤ S1.4 baseline.

### C5 — Commit (code only, NO docs yet)

```powershell
git add core/ adapters/ cli/ system/ skills/ tests/ workers/ memory/ web/ gateways/
git commit -m "refactor: remove 243 unused imports (F401) across 118 files"
```

**Note**: do NOT `git add .` — only add the directories where F401 fixes applied. Do NOT add CHANGELOG.md, SOVEREIGN_AI_HANDOFF.md, or global_rules.md in this commit (those go in C10).

### C6 — Tag

```powershell
git tag prompt-54
```

### C7 — Tag verification (mandatory per L17)

```powershell
git show prompt-54 --stat | Select-Object -First 30
```

**Paste**: first 30 lines. **Verify**: file list contains ONLY `.py` files (no CHANGELOG.md, no handoff, no global_rules.md in this commit). If any unexpected file appears:

```powershell
git tag -d prompt-54
```

Then clean the working tree (unstage the unexpected file), re-commit, re-tag.

### C8 — Update CHANGELOG.md (SIMPLIFIED, ~10 lines, APPEND to END per L21)

Use the **temp-file pattern** (per L15 and Appendix A2 — here-strings with `@"..."@` are fragile and have caused Plan 48.1 and Plan 53 hangs when the closing `"@` gets auto-indented). NEVER insert at top. Oldest entry at top, newest at bottom.

**Step 1 — Write the entry to a temp file** (NOT a here-string — use `Set-Content` with an array of lines):
```powershell
$lines = @(
    "",
    "## 2026-06-21 HH:MM — prompt-54",
    "",
    "**Plan**: F401 bulk cleanup + ship global_rules_v2.md + fix stale handoff",
    "",
    "**Changed**:",
    "- 118 .py files: removed 243 unused imports (ruff F401 --fix)",
    "- global_rules.md: replaced with v2.1 (22 rules: L19 datetime + L20 self-evolution + L21 CHANGELOG position)",
    "- SOVEREIGN_AI_HANDOFF.md: added Plans 51-54 to Completed table, updated baselines, queued Plan 58",
    "",
    "**Results**:",
    "- Ruff F401: 243 → 0",
    "- Ruff total: <S1.3 baseline> → <C3 result>",
    "- Mypy (file-scoped): <S1.4 baseline> → <C4 result>",
    "- Tests: 1167 passed, 55 skipped (unchanged)",
    "- Tag: prompt-54 verified on origin"
)
Set-Content -Path "C:\Jarvis\scan\logs\changelog-entry-prompt-54.md" -Value $lines -Encoding utf8
```

If `C:\Jarvis\scan\logs\` doesn't exist, create it first: `New-Item -Path C:\Jarvis\scan\logs -ItemType Directory -Force`.

**Step 2 — Record current CHANGELOG line count** (per L21 / Appendix A2):
```powershell
$oldCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
```

**Step 3 — Append temp file to CHANGELOG**:
```powershell
Get-Content C:\Jarvis\scan\logs\changelog-entry-prompt-54.md | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
```

**Step 4 — Verify** (per L21):
```powershell
$newCount = [System.IO.File]::ReadAllLines("C:\Jarvis\CHANGELOG.md").Count
Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12
```

**Verify**:
- `$newCount` > `$oldCount` (specifically: should be `$oldCount + 17`, the entry's line count)
- The last 12 lines show the prompt-54 entry with correct format (header → Plan → Changed → Results)
- The entry appears AFTER all previous entries (no insertion at top)

**STOP condition**: if `$newCount` ≤ `$oldCount`, the append failed. Restore from `git checkout CHANGELOG.md` and STOP.

### C9 — Rule proposal (per L20 in global_rules_v2.md — FIRST PLAN WITH THIS ACTIVE)

This is the first plan where L20 (self-evolution) is active. Your closing report MUST include one of:

**Option A — propose a new rule** (if you hit a failure pattern not covered by the rules):
```
## Rule proposal for global_rules.md

Trigger: <what happened this prompt — concrete, with file + line>
Recurrence: <prompt numbers where this pattern bit, or "first occurrence">
Proposed rule: L{n+1}. <one-line rule statement>
Anchor: <prompt number + file + line>
Why existing rules didn't catch it: <one line>
```

**Option B — explicit none** (if everything went smoothly):
```
## Rule proposal — none (no new failure patterns this prompt)
```

**Silence is NOT acceptable.** If your closing report omits this section, GLM will hold the next plan until you confirm you reflected.

### C10 — Update SOVEREIGN_AI_HANDOFF.md

This is critical — the handoff on master is stale by 3+ plans. Update ALL of:

1. **Test baseline** (line ~5): change from `1166 passed, 55 skipped, 1 pre-existing failure (calendar_skill — hardcoded test date, fix in Plan 53), 0 warnings` to `1167 passed, 55 skipped, 0 failures, 0 warnings`

2. **Static analysis baseline** (lines ~7-12):
   - Ruff: change from `358 errors` to `<C3 result>` (should be ~115)
   - Mypy: keep at `282 errors` (this plan doesn't touch mypy errors significantly)
   - Bandit: change from `22 medium+ (B108 in tests, deferred to Plan 53)` to `0 B108 (fixed in Plan 53); other medium+ unchanged`

3. **Completed prompts table** (line ~191): add rows for Plans 51, 52, 53, 54:
   ```
   | 51 | Exception shadowing + float→int + DI fixes | 1166 | 27 mypy eliminated. e→inner_e, float→int casts. |
   | 52 | F4 wiring — cognition-loop into serve.py | 1166 | worker_factory etc. wired into request path. |
   | 53 | Test suite health — calendar + B108 + datetime | 1167 | Calendar test fixed. 22 B108 fixed. 81 utcnow fixed in 15 test files. 28 test utcnow + 90 production utcnow deferred to Plan 58. |
   | 54 | F401 bulk cleanup + global_rules v2.1 ship + handoff fix | 1167 | 243 F401 fixed across 118 files. v2.1 rules shipped (L19/L20/L21). Handoff baselines updated. |
   ```

4. **Next 5 prompts** (line ~256): remove Plan 54 (now completed), shift up, add Plan 58:
   ```
   ### Plan 55 — Full checkpoint scan + Marine stack start (P2)
   - 5-plan milestone: full scan (ruff + mypy . + bandit + pip-audit + vulture + pytest). Then start marine stack as SKILL.md files.

   ### Plan 56 — Dependency updates (P2)
   - Fix 55 CVEs across 14 packages. Upgrade or pin vulnerable dependencies.

   ### Plan 57 — Vulture cleanup (P3)
   - Fix 47 high-confidence dead code findings.

   ### Plan 58 — Remaining datetime.utcnow() cleanup (P3)
   - Fix 28 remaining utcnow in 4 test files: test_retention.py (12), test_memory_compactor.py (8), test_event_trigger.py (7), test_memory_router.py (1).
   - Fix 90 remaining utcnow in 17 production files (core/*): orchestrator, escalation, approval_gate (remaining), task_state_machine, multi_worker, retention, memory_compactor, voice_interface, auth, notification, a2a_protocol, schemas, memory_router, evaluator, event_trigger, orchestrator_improvement, worker_factory.
   - Per L19 (new in v2.1 rules): both test and production must use datetime.now(timezone.utc). No mixing naive/aware.

   ### Plan 59 — (open slot for next GLM scoping)
   ```

5. **Devin rules file note** (line ~14): update from v2 mention to: `**Devin rules file**: global_rules.md v2.1 (22 rules). L19 (datetime consistency), L20 (self-evolution meta-rule — every plan's closing report MUST include a rule-proposal section), L21 (CHANGELOG append position). Shipped in Plan 54.`

6. **L23 / L24 cross-references**: ensure L23 still references "Captured as global_rules_v2.md L19" and L24 still references "First active prompt: Plan 54" — both should now be accurate.

### C11 — Commit docs

```powershell
git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md global_rules.md global_rules_v1_backup.md
git commit -m "docs: prompt-54 changelog, handoff update, global_rules v2.1 ship"
```

**Note**: `global_rules_v1_backup.md` is included so the backup is in the repo (per S0.4 step 2). If you'd rather not commit the backup, delete it before this commit: `Remove-Item C:\Jarvis\global_rules_v1_backup.md` — then remove it from the `git add` line.

### C12 — Push

```powershell
git push origin master
git push origin prompt-54
```

### C13 — Post-push verification (MANDATORY per L17)

```powershell
git ls-remote --tags origin | Select-String "prompt-54"
```

**Paste**: the output. **Expected**: returns `<commit-sha>\trefs/tags/prompt-54`. If empty, the push failed — fix before reporting completion.

---

## Plan completion checklist (Devin must paste ALL before reporting done)

```
1. C1 test suite: <paste last 5 lines of pytest — must show 1167 passed, 55 skipped>
2. C2 ruff F401: <paste last 3 lines — must show "Found 0 errors.">
3. C3 ruff total: <paste last 3 lines — must show reduced count>
4. C4 mypy (file-scoped): <paste last 3 lines — must show ≤ baseline>
5. C5 commit: <paste git commit output>
6. C6 tag: <paste git tag --list prompt-54>
7. C7 file list: <paste git show prompt-54 --stat — must be .py files only>
8. C8 CHANGELOG: <paste Get-Content C:\Jarvis\CHANGELOG.md | Select-Object -Last 12>
9. C9 rule proposal: <paste either the proposal block OR "none — no new failure patterns this prompt">
10. C10 handoff: <paste the new Completed-prompts rows AND the new Next-5-prompts section>
11. C11 docs commit: <paste git commit output>
12. C12 push: <paste git push output for both master and prompt-54>
13. C13 tag on origin: <paste git ls-remote --tags origin | Select-String "prompt-54">
```

If ANY check fails or output is missing, the plan is NOT complete (Rule 21, L17, L24).

---

## STOP conditions summary

STOP and report (do NOT improvise) if:

1. **S0.1**: prompt-53 tag not on origin
2. **S0.3**: master HEAD doesn't match expected commit
3. **S0.4**: v2.1 replacement verification fails (rule count ≠ 22)
4. **S1.1**: test count baseline ≠ 1167 passed
5. **S2.1**: ruff --fix reports non-F401 errors
6. **S3**: test count DECREASES or new failures appear after F401 fix
7. **S4**: mypy error count INCREASES after F401 fix
8. **S5**: any package fails to import after F401 fix
9. **S6**: B108 > 0 (Plan 53's B108 fix was incomplete — log for follow-up, don't fix here)
10. **C7**: unexpected files in prompt-54 tag
11. **C13**: prompt-54 tag not on origin after push

When in doubt, STOP and report. Do not improvise. Do not expand scope. (L4)

---

## Out of scope (deferred)

- **28 remaining test utcnow** → Plan 58
- **90 remaining production utcnow** → Plan 58 (scope expanded from Devin's original Plan 58 which only covered tests)
- **115 other ruff errors** (non-F401) → future plan
- **282 mypy errors** → future plans (55+)
- **55 pip-audit CVEs** → Plan 56
- **47 vulture findings** → Plan 57

---

## Notes for GLM (not for Devin)

- This plan folds in 3 concerns (F401 + rules ship + handoff fix) because all 3 are prerequisites for clean future plans. Splitting into 3 tiny plans would add 3 tag-push cycles for ~10 minutes of work each.
- The handoff fix in C10 is substantial because the handoff has been stale since Plan 51. This is a one-time catch-up; future plans only add 1 row.
- Plan 58 scope is expanded to include production utcnow (90 occurrences), not just test utcnow (28). Devin's original Plan 58 only covered tests. L19 (new in v2.1) makes mixing naive/aware a rule violation, so all 118 must be fixed.
- The C9 rule-proposal step is the FIRST use of L20. If Devin's proposal is good, GLM accepts it and adds to v2.2. If Devin submits "none", that's fine — but GLM should ask Devin to confirm reflection before placing Plan 55.
