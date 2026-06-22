# Plan 50 Context Brief (for Claude review)

**Current revision**: REV2 (2026-06-20)

---

## Reviewer instructions — 7-point check

For each finding, cite which of the 7 points it violates:
1. **Factual accuracy** — file paths, line numbers, function names must match the repo today.
2. **Numbering collisions** — step/gate/STOP numbers unique; cross-references resolve.
3. **Grep strings** — patterns broad enough to catch edge cases.
4. **Internal consistency** — "Current state" agrees with "What to change".
5. **STOP conditions** — testable, specific, catches real failure modes.
6. **Builds on prior findings** — no re-guessing disproved hypotheses.
7. **Known landmines** — see below.

**Output format**: Verdict (PLACE / PLACE-WITH-FINDINGS / DO-NOT-PLACE), then numbered findings.

---

## Known landmines relevant to Plan 50

- **L1**: `global_rules.md` is Devin-local. C8 targets `SOVEREIGN_AI_HANDOFF.md`.
- **L2**: Gates require literal pasted output (Rule 19).
- **L3**: `@pytest.mark.skip` forbidden — fix mocks, don't skip.
- **L4**: Tagging with red test suite forbidden.
- **L5**: Tag-push gate mandatory (C10/C11).
- **L9**: No Devin memory citations.
- **L10**: Test count assertions require measurement.
- **L11**: "No interactive shell" not a valid skip reason.
- **L12**: Scope creep — 8 in-scope test files only (STOP S6).
- **L13**: Capture actual counts at plan-start, don't predict.
- **L15**: CHANGELOG entries >20 lines use temp-file pattern.
- **L16**: Pydantic v2 + mypy requires `Field(default=None, ...)`.
- **L17**: Closing steps MANDATORY — tag-push gate verification required (Rule 21).

---

## Prior prompt state

- **Test baseline (prompt-49b)**: 1167 passed, 55 skipped, 0 failed, 0 warnings (Windows). Linux subset: ~1087 passed, 1 skipped, 2 pre-existing failures (calendar + pdf — unrelated to Plan 50).
- **Static analysis baseline (post-prompt-49b)**:
  - Ruff: 358 errors (unchanged — Plan 49b was test-only)
  - Mypy: 435 errors (Plan 49 eliminated ~108, Plan 49b eliminated ~32)
  - Bandit: 22 medium+ (unchanged)
- **Code commit SHA at prompt-49b**: `2db2cc7`. Step 0.1 verifies.
- **Tag status**: prompt-49b tag on origin at `2db2cc7` (verified post-push).
- **Plan 49b old-API migration intact**: 0 `request_approval(action=, context=)` errors remaining.

---

## Prior findings this plan must build on

- **Scan report "567 mypy errors"**: post-Plan 49/49b, 435 remain. Plan 50 targets 122 of these (MockMemoryRouter/MockStateMachine inheritance).
- **Scan report mypy per-category breakdown**: "MockMemoryRouter" and "MockStateMachine" errors are the largest single category (122 of 435 = 28% of remaining errors).
- **L17/Rule 21 (just added)**: prompt-49b tag-push was missed. Plan 50's C10/C11 explicitly enforce the tag-push gate. Every closing step section now references Rule 21.
- **Plan 49 L16**: pydantic `Field(default=None, ...)` pattern — not directly relevant to Plan 50 (test-only), but the same "mypy plugin requires explicit syntax" pattern applies.

---

## Files in scope

**In-scope (Plan 50 may edit only these — 8 test files):**
- `tests/test_approval_gate.py` (Step 1 — 32 errors, has MockMemoryRouter + MockStateMachine)
- `tests/test_resource_manager.py` (Step 2 — 19 errors)
- `tests/test_task_state_machine.py` (Step 3 — 17 errors)
- `tests/test_model_acquisition.py` (Step 4 — 13 errors)
- `tests/test_ollama_worker.py` (Step 5 — 12 errors)
- `tests/test_model_registry.py` (Step 6 — 11 errors)
- `tests/test_scratchpad.py` (Step 6 — 10 errors)
- `tests/test_system_profiler.py` (Step 6 — 8 errors)

**NOT in scope** (3 additional files with MockMemoryRouter but 0 mypy errors — leave alone):
- `tests/test_approval_trust.py`, `tests/test_model_evaluator.py`, `tests/test_worker_factory.py`

**Out-of-scope**: production code (any non-test `.py` file), adapter fixes (Plan 51), F4 wiring (Plan 52), test suite health (Plan 53), F401 bulk (Plan 54), marine stack (Plan 55), deps (Plan 56), dead code (Plan 57).

---

## Review focus for current REV (REV2)

**What changed in REV2** (2 edits, both from Claude round-1 review):
1. S4: added "This STOP applies to ALL 8 in-scope files — if MemoryRouter.__init__ does real I/O, the inheritance approach fails for the entire plan, not just Step 1. Stop after Step 1.6's check; do not proceed to Steps 2-6." Prevents Devin from partially completing Steps 2-5 before realizing S4 applies to them too.
2. S10: added "Step 6 covers 3 files × ~10 lines = ~30 lines total — still under the 50-line limit. S10 does not apply to Step 6." Eliminates ambiguity about whether multi-file combined steps trigger the 50-line limit.

**Claude should verify**:
1. S4's "all 8 files" clarification is clear and prevents partial execution.
2. S10's Step 6 note is consistent with the actual line count (~30 lines for 3 files × ~10 lines each).
3. No other changes introduced.

**Prior revision history**:
- REV1: initial draft (2026-06-20) — mock inheritance fix across 8 test files

**Open design questions** (all RESOLVED per round-1 review):
- Q1 (Inheritance vs Protocol): RESOLVED — inheritance is the right primary approach.
- Q2 (S4 fallback clarity): RESOLVED — S4 now covers all 8 files.
- Q3 (3 excluded files): RESOLVED — correct to exclude (0 errors).
- Q4 (other state machine mocks): RESOLVED — Step 0.3/0.4 coverage is sufficient.
- Q5 (Rule 21 enforcement): RESOLVED — C10/C11 are strong.

All design questions are resolved. Review should focus on the 2 REV2 edits only.

---

## Revision history

- REV1: initial draft (2026-06-20) — mock inheritance fix across 8 test files
