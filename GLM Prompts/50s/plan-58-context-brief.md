# Plan 58 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-21
**Plan**: 58 — datetime.utcnow() cleanup (28 test + 90 production = 118 replacements)

---

## What this plan does

Completes the datetime cleanup started in Plan 53. Replaces all remaining `datetime.utcnow()` (naive) with `datetime.now(timezone.utc)` (aware) to achieve L19 compliance. Plan 53 fixed 81 test occurrences + 2 production occurrences (scope-expanded for test compatibility); this plan fixes the remaining 28 test + 90 production = 118 total.

**Critical per L19**: test and production files that share datetime values MUST be fixed together. Plan 53's approval_gate issue showed what happens when only one side is fixed — `TypeError: can't compare offset-naive and offset-aware datetimes`.

## Baselines (from Plan 57 closing + handoff)

- **Tests**: 1167 passed, 55 skipped, 0 failed
- **utcnow**: 28 in tests (4 files) + 90 in production (17 core/ files) = 118 total
- **prompt-57 tag on origin**: `e874f2b` ✅ verified
- **master HEAD**: `06ff457` ✅ verified

## Section 0: Rules (v2.4 — includes new L25)

Inline approach (same as Plans 55-57). 25 rules (L1-L25). **New this plan: L25 (test fixture parameter removal)** — proposed by Devin during Plan 57's C9 rule-proposal step. Captures the pattern where vulture correctly identifies test parameters as unused but they're load-bearing (pytest fixture deps, framework protocols like middleware call_next signatures).

## Landmines relevant to this plan

- **L5**: don't expand scope — utcnow only, don't fix other issues
- **L9**: fix test file in same step as production file — CRITICAL for this plan (L19 coupling)
- **L17**: closing steps C1-C13 mandatory
- **L19**: datetime consistency — THIS IS THE RULE THIS PLAN ENFORCES
- **L20**: C9 rule-proposal MANDATORY
- **L21**: CHANGELOG append to END, temp-file pattern
- **L22**: PowerShell commands only
- **L23**: verification gates scoped to actual prior plan scope
- **L24**: run scan tools sequentially
- **L25**: test fixture parameter removal (new — relevant if any test fixtures have datetime parameters)

## Review focus for Claude

1. **Is the test-production coupling identification in S2 adequate?** S2.1 maps each of the 4 test files to its production counterpart. But datetime values can flow to MULTIPLE production files (e.g., test_retention.py might pass datetimes to core/retention.py AND core/memory_router.py). Should S2 require a broader grep to find all production files that receive datetimes from each test file?

2. **Is the S3.1 pattern (edit both, test, move on) sound for L19 compliance?** The plan says "edit both files, run test, if TypeError then missed a coupled file." But this reactive approach means Devin might fix test+production pair A, then later fix pair B which also couples to A's production file — causing a regression. Should the plan require fixing ALL coupled files in one atomic step before testing?

3. **Is the S4.3 check for bare `datetime.now()` (without timezone) in scope?** These are also L19 violations but weren't in the original handoff scope. The plan says "fix them in this plan if in scope, or defer." Is this too vague? Should it be a hard STOP if bare `datetime.now()` is found, requiring explicit GLM authorization to expand scope?

4. **Is the 13 remaining production files list accurate?** The handoff says "17 production files" but Plan 53 already fixed 2 in approval_gate.py. So this plan should touch 15-17 files (depending on whether approval_gate still has utcnow). S3.3 lists 13 files. Should the plan verify the exact count via S1.2 before listing?

5. **Should the plan batch the 4 test-production pairs or process one at a time?** S3.2 processes them sequentially (pair 1, test, pair 2, test, etc.). Given L19 coupling risk, is one-at-a-time safer, or should all 4 pairs be edited before any testing?

6. **Is the bisection fallback from Plan 57 referenced?** S5 mentions "use the S5 bisection fallback from Plan 57 if needed" but doesn't repeat the procedure. Should it be repeated here for self-containedness, or is the reference sufficient?

## Files this plan touches

- **4 test files**: test_retention.py, test_memory_compactor.py, test_event_trigger.py, test_memory_router.py
- **17 production files** (core/): orchestrator, escalation, approval_gate, task_state_machine, multi_worker, retention, memory_compactor, voice_interface, auth, notification, a2a_protocol, schemas, memory_router, evaluator, event_trigger, orchestrator_improvement, worker_factory
- **CHANGELOG.md** — append prompt-58 entry
- **SOVEREIGN_AI_HANDOFF.md** — update Completed row 58 + Next-5 shift

## Expected outcome

- Tests: 1167 passed (unchanged — datetime fix shouldn't change test count)
- utcnow remaining: 0 (was 118)
- L19 compliance: achieved — all datetime calls use `datetime.now(timezone.utc)`
- Mypy: may drop slightly (some utcnow calls had implicit type issues)
- Vulture: unchanged (datetime calls aren't dead code)
