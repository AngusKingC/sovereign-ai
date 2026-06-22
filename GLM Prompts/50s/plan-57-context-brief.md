# Plan 57 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-21
**Plan**: 57 — Vulture cleanup (32 high-confidence findings)

---

## What this plan does

Removes 32 high-confidence vulture findings (dead code) across 4 directories:
- **adapters** (13): all `structured_output` unused variable across 12 adapter files
- **core** (7): `last_check_time`, `record_type`, `cls` x4 (pydantic validators), `structured_output` x2
- **tests** (10): unused mock clients, `req`, `raw_output`, `auth`
- **workers** (1): `structured_output`

Uses a 3-category triage:
- **Category A**: Safe to remove (delete the line)
- **Category B**: Remove variable, keep the call (side effects matter — e.g. `result = await handler.execute()` where `execute()` emits traces)
- **Category C**: Defer (e.g. `cls` parameters required by pydantic protocol — vulture false positive)

## Baselines (from Plan 55 scan, verified in Plan 56)

- **Tests**: 1167 passed, 55 skipped, 0 failed
- **Vulture**: 32 high-confidence findings
- **prompt-56 tag on origin**: `b2f8682` ✅ verified (retroactively tagged after Plan 56 — see L18 note in Section 0)
- **master HEAD**: `b2f8682` ✅ verified

## Section 0: Rules (v2.3 — includes new L24)

Inline approach (same as Plans 55, 56). 24 rules (L1-L24). **New this plan: L24 (sequential scan execution)** — proposed by GLM after the parallel-scan corruption pattern recurred across Plans 55-56. Plan 55's parallel scan produced contaminated output and an inaccurate CVE count (reported 37, actual 55) that propagated to the handoff. Devin declined to propose a rule via C9 in both plans, so GLM proposed it.

**L18 note added**: even docs-only plans must create a tag. Plan 56 skipped the tag because there were no code changes — this was incorrect. The tag marks prompt completion, not just code commits. Plan 56's tag was retroactively created on the docs commit.

## Landmines relevant to this plan

- **L5**: don't expand scope — vulture findings only, don't fix other issues
- **L9**: fix test file in same step as production file
- **L10**: do not remove working implementation to make a test pass — if a "dead code" removal breaks tests, it's NOT dead code. Revert and defer.
- **L17**: closing steps C1-C13 mandatory
- **L20**: C9 rule-proposal MANDATORY
- **L21**: CHANGELOG append to END, temp-file pattern
- **L22**: PowerShell commands only
- **L23**: verification gates scoped to actual prior plan scope
- **L24** (NEW): run scan tools sequentially, never in parallel

## Review focus for Claude

1. **Is the Category A/B/C triage sound?**
   - A: delete line (unused local var, no side effects)
   - B: remove `var = `, keep RHS (side effects matter — e.g. `result = await handler.execute()` where execute emits traces)
   - C: defer (pydantic `cls` parameters, subtle behavior changes)

2. **Is the `core/schemas.py` cls caution adequate?** Vulture flags `cls` in 4 class methods as unused. These are likely pydantic validators (`@validator` decorator) where `cls` is required by the protocol even if not referenced in the body. The plan says "Category C — do NOT remove." Should it also say "verify each `cls` method has a `@validator` or `@root_validator` decorator before deferring"?

3. **Is the S3.1-S3.4 sequential file-processing approach correct?** Per L9, fix test file in same step as production file. But vulture findings in adapters (production) and tests are independent — the adapter `structured_output` and the test `mock_client` are different findings. Should the plan group by finding instead of by directory?

4. **Is the L24 STOP condition in S1.2 adequate?** "If vulture output looks contaminated, STOP and re-run." How does Devin recognize contamination? Suggested check: vulture output should be lines of form `file:line: unused variable 'name' (100% confidence)`. If any line doesn't match this pattern, it's contaminated.

5. **Is the L18 note about docs-only tag creation clear?** Plan 56 missed this — Devin skipped the tag because there were no code changes. The note now says "even if no code changes, you MUST still create the tag. Tag the docs commit if no code commit exists." Is this clear enough?

6. **Should the plan batch-remove the 13 adapter `structured_output` findings or process them one at a time?** The findings are identical across 12 adapter files (all `structured_output` unused variable). Batching would be faster but risks scope creep if one adapter's `structured_output` is actually used. The plan currently says "for each adapter file" — one at a time. Is this the right tradeoff?

## Files this plan touches

- **~15-20 .py files** across adapters/, core/, tests/, workers/ (exact list from S1.2 vulture output)
- **`CHANGELOG.md`** — append prompt-57 entry
- **`SOVEREIGN_AI_HANDOFF.md`** — update vulture baseline + Completed row 57 + Next-5 shift

## Expected outcome

- Tests: 1167 passed (unchanged — dead code removal shouldn't affect tests)
- Vulture: 32 → ~7 findings (25 removed, 7 deferred as Category C — mostly `cls` in core/schemas.py)
- Ruff: may drop slightly (some F841 "unused variable" findings overlap with vulture)
- Mypy: unchanged (dead code removal doesn't affect type checking)
