# Plan 58.5 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-21
**Plan**: 58.5 — Bare datetime.now() cleanup (231 calls across 28 files)

---

## What this plan does

Completes L19 compliance by replacing bare `datetime.now()` (without timezone) calls with `datetime.now(timezone.utc)`. Plan 58 fixed `datetime.utcnow()` calls; this plan fixes the remaining bare `datetime.now()` calls that were deferred.

**Critical scope correction**: Plan 58's S4.3 HARD STOP reported "46+ calls across 9 files" — but that was an INCOMPLETE scan. GLM verified the actual count via clone grep: **231 calls across 28 files** (7 production + 21 test). This plan uses the verified count.

## Baselines (from Plan 58 closing + clone verification)

- **Tests**: 1167 passed, 55 skipped, 0 failed
- **Bare datetime.now()**: 231 across 28 files (26 production + 205 test)
- **prompt-58 tag on origin**: `51b4a3f` ✅ verified
- **master HEAD**: `d1907f1` ✅ verified

**Production breakdown** (7 files, 26 total):
- core/session.py: 9
- core/instruction_generator.py: 6
- core/instruction_versioning.py: 5
- core/rating_system.py: 3
- core/handlers.py: 1
- core/scratchpad.py: 1
- core/task_state_machine.py: 1

**Test breakdown** (21 files, 205 total):
- tests/test_instruction_versioning.py: 32
- tests/test_schemas.py: 31
- tests/test_task_state_machine.py: 18
- tests/test_instruction_generator.py: 12
- tests/test_anthropic_adapter.py: 10
- (and 16 more files with 1-7 each)

## Section 0: Rules (v2.4 — same as Plan 58)

Inline approach (same as Plans 55-58). 25 rules (L1-L25). No new rules added since Plan 58.

## Landmines relevant to this plan

- **L5**: don't expand scope — bare datetime.now() only
- **L9**: fix test file in same step as production file — CRITICAL for this plan (L19 coupling)
- **L17**: closing steps C1-C13 mandatory
- **L19**: datetime consistency — THIS IS THE RULE THIS PLAN ENFORCES (completing Plan 58's work)
- **L20**: C9 rule-proposal MANDATORY
- **L21**: CHANGELOG append to END, temp-file pattern
- **L22**: PowerShell commands only
- **L23**: verification gates scoped to actual prior plan scope
- **L24**: run scan tools sequentially, use -AllMatches
- **L25**: test fixture parameter removal (relevant if any test fixtures have datetime parameters)

## Review focus for Claude

1. **Is the scope correction (231 vs 46+) adequately documented?** Plan 58's HARD STOP report was incomplete — Devin only found 46+ calls during a partial scan. GLM verified the actual count is 231 across 28 files. The plan explains this in "Why this plan exists" and S1.2. Is the explanation clear enough that Devin won't be confused by the discrepancy?

2. **Is the 3-category triage (A/B/C) sound for bare datetime.now()?**
   - A: test fixtures (always safe — tests don't display time to users)
   - B: production internal timestamps (convert to UTC)
   - C: production user-facing local time (defer with noqa comment)
   
   Should there be a Category D for "production code that writes to external systems expecting local time" (e.g., Obsidian notes with local timestamps)?

3. **Is the S3.1 test-production pairing correct?** The plan lists 7 production files with their test counterparts. But some test files (test_schemas.py with 31 calls) don't have a direct production counterpart — schemas.py is a data model, not a logic module. Should S3.2 handle these separately?

4. **Is the replace_all caution adequate?** Plan 58's `replace_all` corrupted a2a_protocol.py and escalation.py. S3.2 says "use targeted replacements, NOT replace_all" and "Edit each occurrence individually or use careful regex." Should the plan specify the exact PowerShell command to use (e.g., `(Get-Content file) -replace 'datetime\.now\(\)', 'datetime.now(timezone.utc)' | Set-Content file`)?

5. **Should the plan batch the 21 test files or process one at a time?** 205 test-file calls is a lot. Batching by file (edit all occurrences in one file, test, move on) is faster than one-at-a-time. But if a batch breaks tests, bisection is harder. The plan currently says "process by file" — is this the right granularity?

6. **Is the Category C noqa comment format correct?** The plan suggests `# noqa: L19 — intentional local time display`. But L19 is a Section 0 rule, not a ruff/pylint rule. Ruff doesn't know about L19. Should the comment be `# noqa — intentional local time display (L19 exception)` instead?

## Files this plan touches

- **7 production files** (core/): session.py, instruction_generator.py, instruction_versioning.py, rating_system.py, handlers.py, scratchpad.py, task_state_machine.py
- **21 test files** (tests/): test_schemas.py, test_task_state_machine.py, test_instruction_versioning.py, test_anthropic_adapter.py, test_instruction_generator.py, test_orchestrator.py, test_together_adapter.py, and 14 more
- **CHANGELOG.md** — append prompt-58.5 entry
- **SOVEREIGN_AI_HANDOFF.md** — update Completed row 58.5 + Next-5 shift

## Expected outcome

- Tests: 1167 passed (unchanged — datetime fix shouldn't change test count)
- Bare datetime.now() count: 231 → ~5-10 (Category C deferrals only)
- L19 compliance: COMPLETE — all datetime calls now use `datetime.now(timezone.utc)` except documented Category C exceptions
- Mypy: may drop slightly (some bare datetime.now() calls had implicit type issues)
