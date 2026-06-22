# Plan 54 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-21
**Plan**: 54 — F401 bulk cleanup + ship global_rules_v2.md + fix stale handoff
**Pointer-based**: references handoff sections by pointer, doesn't copy content.

---

## What this plan does (3 things, folded into one prompt)

1. **F401 cleanup**: `ruff check . --select F401 --fix` to remove 243 unused imports across 118 files. All auto-fixable. 0 F401 are in `__init__.py` (verified via clone — no re-export concerns).

2. **Ship global_rules_v2.1**: replace Devin's local `global_rules.md` (24-rule v1) with v2.1 (22 rules: L1-L18 renumbered from old 1-20, + L19 datetime, + L20 self-evolution, + L21 CHANGELOG append position, + L22 environment). Devin's self-added Rule 25 from Plan 53 is preserved as L21. Backup v1 before overwriting.

3. **Fix stale handoff**: handoff on master is stale by 3 plans (51, 52, 53 not in Completed table; baselines still say "1166 passed, 1 failure, 22 B108"). Devin's local handoff edits (Plan 58 addition) were never committed. C10 catches up: adds Plans 51-54 to Completed table, updates test baseline to 1167/0 failures, updates ruff baseline to ~115, updates bandit to 0 B108, adds Plan 58 with EXPANDED scope (28 test + 90 production utcnow).

## Why folded into one plan

Splitting into 3 tiny plans = 3 tag-push cycles (~30 min overhead). Folding = 1 cycle. The 3 concerns are independent but all small. F401 is the main work (~10 min); rules ship is ~2 min; handoff fix is ~5 min.

## Baselines (verified via clone at commit 642f406, NOT from my clone running tools — L19)

- **Tests**: 1167 passed, 55 skipped, 0 failed (post-prompt-53)
- **Ruff F401**: 243 errors across 118 files (all auto-fixable)
- **Ruff total**: ~358 errors
- **Mypy**: 282 errors (file-scoped only per L18 — this plan touches top 10 offenders)
- **Bandit B108**: 0 (fixed in Plan 53) — but Plan 53's verification was broken (`bandit tests/ -ll` without `-r` skipped directory scan). C6 re-verifies with correct command.
- **prompt-53 tag on origin**: `91720ca` ✅ verified
- **master HEAD**: `642f406` (user's CHANGELOG rebuild) ✅ verified, has prompt-53 as ancestor

## Landmines relevant to this plan (reference handoff §Known landmines)

- **L5**: don't expand scope — F401 only, no other ruff rules
- **L9**: fix test file in same step as production file — F401 --fix handles both automatically
- **L17**: closing steps C1-C13 mandatory, paste evidence
- **L18**: file-scoped mypy only, NEVER `mypy .`
- **L19** (NEW v2.1): datetime consistency — not directly relevant to F401, but L19 is being shipped this plan
- **L20** (NEW v2.1): self-evolution — C9 rule-proposal step is FIRST use
- **L21** (NEW v2.1, from Devin's Rule 25): CHANGELOG append to END, never insert at top
- **L22**: PowerShell commands only

## Plan 53 issues found during verification (context for C10 handoff fix)

1. **Handoff stale by 3 plans** — Plans 51, 52, 53 not in Completed table on master. Devin's C8 step was incomplete.
2. **Devin's Plan 58 addition lost** — edited locally, never `git add`ed. Master handoff only has Plans 53-57.
3. **Bandit verification broken** — `bandit tests/ -ll` without `-r` skipped directory scan. "0 B108" claim was unverified for full suite. Per-file check on test_calendar_skill.py was correct.
4. **Missing C5/C11/C13 evidence** — Devin did not paste `git show prompt-53 --stat`, `git ls-remote --tags origin | findstr prompt-53`. I verified via clone — tag and commit are correctly on origin.
5. **CHANGELOG format** — Devin's initial entry was 39 lines, inserted at TOP. User manually rebuilt (commit `642f406`, deleted 1924 lines, added 70). Devin self-added Rule 25 to prevent recurrence — preserved as L21 in v2.1.
6. **90 production utcnow remain** — Devin correctly deferred per L5 (plan scope was tests). But L19 (new) makes this a rule violation going forward. Plan 58 scope expanded to include production.
7. **Test count math**: 1166 + 1 (calendar test fixed) = 1167. ✅ Correct.

## Review focus for Claude

1. **Is folding 3 concerns into 1 plan acceptable?** Or should rules-ship be a separate Plan 53.5? My judgment: folding is fine because all 3 are small and independent.
2. **Is the C10 handoff fix scope correct?** It adds 4 rows to Completed table (51, 52, 53, 54), updates 3 baselines, restructures Next-5-Prompts (removes 54, adds 58 with expanded scope). This is a one-time catch-up.
3. **Is Plan 58's expanded scope (28 test + 90 production utcnow) correct?** Devin's original Plan 58 only covered 28 test files. I expanded to 90 production files because L19 makes naive/aware mixing a rule violation. Production code still using `utcnow()` will cause comparison failures whenever tests pass aware datetimes.
4. **Is the C9 rule-proposal step correctly structured?** This is the first use of L20. Format: Option A (propose) or Option B (explicit none). Silence forbidden.
5. **Are the STOP conditions adequate?** 11 STOP conditions covering: tag verification, HEAD drift, v2.1 replacement failure, baseline drift, ruff fix introducing non-F401 errors, test count decrease, mypy increase, import breakage, B108 regression, unexpected files in tag, push failure.
6. **Is `git add core/ adapters/ cli/ system/ skills/ tests/ workers/ memory/ web/ gateways/` in C5 correct?** This adds all .py files in these dirs. Alternative: `git add -A` then `git reset CHANGELOG.md SOVEREIGN_AI_HANDOFF.md global_rules.md`. The directory-listing approach is more explicit but may miss newly-created files. Recommend the explicit directory list since F401 --fix only modifies existing files (doesn't create new ones).

## Files this plan touches

- **~118 .py files** (F401 fixes via ruff --fix) — exact list in S2.1 output
- **`global_rules.md`** — replaced with v2.1 content (provided in full below)
- **`global_rules_v1_backup.md`** — created as backup (S0.4 step 2)
- **`CHANGELOG.md`** — append prompt-54 entry (~12 lines, per L21)
- **`SOVEREIGN_AI_HANDOFF.md`** — substantial C10 update (baselines + Completed table + Next-5-Prompts)

## v2.1 rules file delivery mechanism (REV2 — Finding 2 fix)

**Problem identified by Claude**: original S0.4 said "GLM will provide v2.1 content via context brief" but neither the plan nor the brief actually contained the content inline. Devin would have nothing to write.

**Fix (REV2)**: the user (human relay) saves the v2.1 content to `C:\Jarvis\global_rules_v2_source.md` on Devin's machine BEFORE handing Plan 54 to Devin. GLM pastes the full v2.1 content (from `/home/z/my-project/download/global_rules_v2.md`, ~180 lines) into the prompt to Devin. The FIRST action Devin takes is verifying that file exists; if not, STOP and report.

S0.4 then uses `Copy-Item` (file-to-file) instead of here-string assignment — avoids the Plan 48.1 / Plan 53 here-string hang issue (Finding 1 fix).

## Key changes from v1 → v2.1 (for reviewer reference)

- 24 rules → 22 rules (L1-L22)
- Merged: old 1+24→L1, old 4+23→L4, old 16+17→L16+L17 (rewritten for simplified CHANGELOG)
- Added: L19 (datetime consistency), L20 (self-evolution), L21 (CHANGELOG append position — from Devin's Rule 25)
- Moved to appendices: PowerShell cheatsheet (A1), CHANGELOG append procedure (A2)
- Fixed: Select-String syntax in L11/L12 (added `-Path`/`-Include *.py`)
- Revision history arithmetic corrected (Finding 4 fix): "L1-L22 (22 rules total)" — L19/L20/L21 are within L1-L22, not additional

## Expected outcome

- Ruff F401: 243 → 0
- Ruff total: 358 → ~115
- Tests: 1167 passed (unchanged — F401 cleanup doesn't change test count)
- Mypy (file-scoped): ≤ baseline (F401 fixes sometimes reduce mypy errors)
- Bandit B108: 0 (re-verified with correct command)
- global_rules.md: v1 → v2.1 (22 rules, L20 active)
- Handoff: stale → current (Plans 51-54 in Completed table, baselines updated, Plan 58 queued with expanded scope)
- L20 self-evolution: ACTIVE for first time — Devin's closing report MUST include C9 rule-proposal section
