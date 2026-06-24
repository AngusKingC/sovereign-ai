# Plan 63b Context Brief -- Improvement Loop Validate + Restore Deleted Tests

## What to Review

1. **Scope discipline (OR15/OR16)** -- Does the plan avoid editing `orchestrator/improvement_loop.py`, `core/commands.py`, `core/orchestrator_improvement.py`, `evals/`, `memory/`? Only restores tests + moves an inline import + adds E2E scenarios.
2. **OR25 wording** -- Is the test-deletion rule clear enough to prevent the Plan 63a pattern without being overly broad (e.g., legitimate test removal during refactoring)?
3. **OR26 wording** -- Is the governance-doc-cleanup rule practical? Will it cause friction at S0.1 if Devin has stray plan files in the working tree?
4. **S1 mocking strategy** -- Will the proposed `mock_orchestrator_dependencies` fixture (state_machine.transition as passthrough, scratchpad_manager.compact as no-op) actually let `process_task()` reach the COMPLETE branch? Or is deeper mocking needed?
5. **E2E test scope** -- Are the 5 E2E scenarios (S2) testing the wire module's end-to-end behavior, or are they redundant with the existing TestImprovementLoopOrchestrator tests?
6. **Baseline projection** -- Is +22 tests (2 restored + 20 E2E) a reasonable expectation, or is it another overestimate like Plan 63a's +80?

## Key Pointers

- `tests/test_improvement_loop.py` (Plan 63a, shipped): 12 tests across TestImprovementLoopOrchestrator (6) and TestImproveCommandHandler (6). `TestOrchestratorIntegration` class is empty with a "deferred" comment. Plan 63b restores this class.
- `core/orchestrator.py` (Plan 63a, shipped): `process_task()` method (line 175-310) -- the improvement loop integration block (line ~277-294) is what tests #6 and #9 verify. Inline `import asyncio` at line ~282 needs to move to top-of-file.
- `core/orchestrator.py` `__init__` (line 38-84): accepts `improvement_loop_orchestrator` parameter (Plan 63a addition). Tests will need to pass mocked dependencies for `state_machine`, `scratchpad_manager`, `worker_registry`, `_emitter` as well.
- `orchestrator/improvement_loop.py` (Plan 63a, shipped): `ImprovementLoopOrchestrator.process_improvement_task()` -- already tested directly; E2E scenarios exercise this from a different angle (trace → eval → improvement → proposal flow).
- `evals/harness.py` (Plan 62): `EvalHarness.evaluate()` returns `EvalResult`. Already mocked in existing test fixtures.
- `memory/postgres_trace_store.py` (Plan 61): `query_traces(filters)` -- NO `limit` parameter. Wire module uses Python slicing. Already handled.

## Architecture Notes

**Why restore the deleted tests first**: Plan 63a's central claim -- "orchestrator invokes wire module via asyncio.create_task after task completion" -- has zero test coverage. The wire module is tested in isolation, but the wiring between orchestrator and wire module is not. If the orchestrator code is wrong (e.g., `improvement_loop_orchestrator` attribute never set, or `process_task()` doesn't reach the COMPLETE branch in production), no test catches it. This is the highest-risk gap in the codebase right now.

**Why the mocking failed in Plan 63a**: `process_task()` calls `state_machine.transition()` twice (VALIDATING then COMPLETE) and `scratchpad_manager.compact()` before reaching the improvement loop block. With these unmocked, the orchestrator raised AttributeError or never reached the COMPLETE branch. The fix is to mock all four collaborators (state_machine, scratchpad_manager, worker_registry, emitter), not just memory_router + improvement_loop_orchestrator.

**OR25 vs legitimate test removal**: The rule targets tests that are *specified in the plan's S4 test list*. If a future plan removes a test as part of a deliberate refactor (with GLM authorization in the plan itself), that's fine -- the plan is the authorization. OR25 prevents *unilateral* deletion when tests prove harder than expected.

**OR26 friction tradeoff**: Yes, this adds a step at S0.1 when the working tree is dirty. The alternative (bundling cleanup into prompt-{N} tags) corrupts the tag's atomicity and makes the CHANGELOG inaccurate. The friction is intentional.

## Known Risks

- **S1 fixture complexity**: The proposed `mock_orchestrator_dependencies` may not be sufficient -- `process_task()` may have other dependencies (escalation_engine, approval_gate, etc.) that also need mocking. If S1 takes more than 3 attempts, STOP per OR25 (don't delete, report).
- **E2E vs existing tests overlap**: S2's `test_e2e_trace_to_eval_to_improvement` may overlap with Plan 63a's `test_process_improvement_task_feeds_improvement_loop`. Different framing (E2E "trace → eval → improvement" narrative vs unit "verify record_routing_decision called"), but the assertions may be similar. Acceptable -- different test names document different intents.
- **Baseline target +22 may be optimistic**: If S1 takes 2 tests and S2 takes 5 tests, the actual delta is +7, not +22. The plan tolerates ±5 deviation per OR17 -- update PLANS.md if actual differs.
- **AGENTS.md edit at S0.3**: Adding OR25/OR26 modifies a governance doc. This is in scope (declared at S0.4). The edit must use Edit tool, not PowerShell `-replace` (OR7).

## Questions for Claude (answer in review)

1. Should OR25 be more specific (e.g., "tests listed in plan S4") or more general (e.g., "any test that exists at plan start")? **Default: S4-listed tests only -- gives Devin latitude to remove orphan tests from prior plans.**
2. Should OR26 require a separate `docs-cleanup-{N}` tag, or is a separate commit sufficient? **Default: separate tag -- makes the cleanup traceable in `git tag --list` without polluting prompt-{N} sequence.**
3. Is moving `import asyncio` (S3) worth a plan step, or is it noise? **Default: yes, worth it -- inline imports are a code smell and the fix is one line.**
4. Should the E2E tests (S2) live in `TestEndToEndValidation` or be folded into `TestImprovementLoopOrchestrator`? **Default: separate class -- clearer test organization.**
