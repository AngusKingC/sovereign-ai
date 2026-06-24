# Plan 63b -- Improvement Loop Validate + Restore Deleted Integration Tests

## Opening (S0)

1. **Run `/jarvis-open`** -- verify `prompt-63a` tag on origin, confirm working copy clean and on master. If workflow missing or fails, STOP and report.

2. **Read AGENTS.md in full.** Apply all existing rules (AR1-AR18, OR1-OR24). Cite rules by number per OR23.

3. **Add new AGENTS.md rules and commit** before any coding step. Two new rules this prompt:

   **OR25. Test deletion is a scope deviation.** If a test listed in the plan's S4 test specification cannot be made to pass due to mocking complexity, fixture difficulty, or API mismatch, STOP and report to the user. Do NOT delete the test, comment it out, or replace it with a "deferred to a future plan" note. Tests specified in the plan are part of the plan's scope; removing them is a HARD STOP under OR16. (Source: GLM observation, Plan 63a execution -- two integration tests were silently deleted after failing twice, leaving the plan's central wiring claim unverified.)

   **OR26. Governance-doc edits discovered at /jarvis-open must be a separate commit and tag.** If `git status` at S0.1 shows modified/untracked governance docs (`AGENTS.md`, `AI_HANDOFF.md`, `PLANS.md`, `CHANGELOG.md`, `LANDMINES.md`) or plan files (`GLM Prompts/`), commit them as a standalone `docs: cleanup pre-prompt-{N}` commit and tag as `docs-cleanup-{N}` -- do NOT bundle them into the next `prompt-{N}` tag. The CHANGELOG entry for `prompt-{N}` must list only the files actually edited as part of the plan body. (Source: GLM observation, Plan 63a execution -- 13 files were bundled into `prompt-63a` tag; CHANGELOG only documented 5.)

   After adding OR25 and OR26 to AGENTS.md under the appropriate sections (test discipline for OR25, scope discipline for OR26), commit the change as `docs: add OR25 and OR26 rules` BEFORE any coding step.

4. **Scope declaration** -- will edit:
   - `AGENTS.md` -- add OR25 (Test discipline section) and OR26 (Scope discipline section)
   - `core/orchestrator.py` -- move `import asyncio` from inline (line ~282) to top-of-file imports block; no logic change
   - `tests/test_improvement_loop.py` -- restore `TestOrchestratorIntegration` class with the two deleted tests (#6 and #9), fix mocking strategy so they pass; add E2E validation scenarios per Plan 63b's original scope
   - Will NOT edit: `core/commands.py`, `core/orchestrator_improvement.py`, `evals/`, `memory/`, `orchestrator/improvement_loop.py`, `orchestrator/__init__.py`, `adapters/`, `skills/`, `web/`, `cli/`, `workers/`, `gateways/`, `system/`

## Plan Body (S1-S5)

### S1 -- Restore Deleted Integration Tests (Fix Plan 63a's Central Gap)

Plan 63a deleted two tests after they failed twice. The failures were caused by:
1. Tests not decorated with `@pytest.mark.asyncio` (fixed in Plan 63a after first failure)
2. `patch("asyncio.create_task")` did not patch the symbol actually used inside `core/orchestrator.py` -- needed `patch("core.orchestrator.asyncio.create_task")`. Devin tried this fix but the test still failed because `orchestrator.process_task()` never reached the COMPLETE branch (mocked worker did not return `WorkerOutput` with content). After trying twice, Devin deleted the tests.

**Root cause of remaining failure**: `orchestrator.process_task()` requires the task to flow through `state_machine.transition(task, TaskStatus.VALIDATING)` then `state_machine.transition(task, TaskStatus.COMPLETE)` to reach the branch where the improvement loop is invoked. The mocked state machine must return a task in the expected state, and the mocked scratchpad_manager.compact must not raise.

**S1.1** -- In `tests/test_improvement_loop.py`, restore the `TestOrchestratorIntegration` class. Remove the "deferred to a future plan" comment.

**S1.2** -- Add fixture `mock_orchestrator_dependencies` that returns a dict containing:
- `mock_state_machine` -- MagicMock with `transition = AsyncMock(side_effect=lambda task, status, **kw: task)` (returns task unchanged, simulating state transition)
- `mock_scratchpad_manager` -- MagicMock with `compact = AsyncMock()` (no-op)
- `mock_worker_registry` -- MagicMock with `get_worker = AsyncMock(return_value=mock_worker)`
- `mock_emitter` -- MagicMock with `emit = AsyncMock()`

**S1.3** -- Restore `test_orchestrator_invokes_wire_module_on_completion`:
- Construct `Orchestrator` with mocked dependencies (memory_router, improvement_loop_orchestrator, state_machine, scratchpad_manager, emitter)
- Register mock worker that returns `WorkerOutput(task_id=..., worker_id="worker-1", content="test output", confidence=1.0, model_used="test-model")`
- Patch `core.orchestrator.asyncio.create_task` -- return a MagicMock for the task object
- Call `await orchestrator.process_task(task, "worker-1")`
- Assert `mock_create_task.assert_called_once()` and that the first positional arg is `mock_improvement_loop_orchestrator.process_improvement_task(...)` (use `assert_called` with the coroutine, or check `mock_improvement_loop_orchestrator.process_improvement_task.assert_called_once_with(task_id=str(task.task_id))`)

**S1.4** -- Restore `test_orchestrator_done_callback_suppresses_warning`:
- Same setup as S1.3
- After calling `process_task`, assert `mock_task.add_done_callback.assert_called_once()`
- Verify the callback is a lambda that calls `.exception()` on the task (capture via `side_effect` if needed)

**S1.5** -- Verify both tests pass: `python -m pytest tests/test_improvement_loop.py::TestOrchestratorIntegration -v`

If after reasonable effort (3 attempts) the tests still cannot be made to pass due to deeper architectural coupling in `process_task()`, STOP and report. Do NOT delete the tests again (OR25).

### S2 -- Add E2E Validation Scenarios

Plan 63b's original scope: "End-to-end validation of improvement loop. Inject test failures into the system and verify the loop captures → evaluates → routes improvements."

In `tests/test_improvement_loop.py`, add a new class `TestEndToEndValidation` with the following tests:

1. `test_e2e_trace_to_eval_to_improvement` -- Given a trace store containing a trace with `predicted` and `gold` fields, calling `process_improvement_task()` produces eval results, feeds them to `improvement_loop.record_routing_decision()`, and returns a results dict with `accuracy` set from `improvement_loop.get_routing_accuracy()`.

2. `test_e2e_update_triggered_when_threshold_met` -- Given mocked `improvement_loop.check_and_trigger_update()` returns a `VersionUpdateProposal`, calling `process_improvement_task()` returns `update_triggered=True` and `proposal=<the proposal>`.

3. `test_e2e_no_update_triggered_when_threshold_not_met` -- Given mocked `improvement_loop.check_and_trigger_update()` returns `None`, calling `process_improvement_task()` returns `update_triggered=False` and `proposal=None`.

4. `test_e2e_failed_eval_does_not_break_loop` -- Given a trace with malformed data (missing `predicted` field), the loop skips that trace, processes remaining traces, and returns partial results without raising.

5. `test_e2e_specific_task_id_queries_only_that_task` -- Given `task_id="task-42"`, the wire module calls `trace_store.query_traces(filters={"task_id": "task-42"})` exactly once and does NOT query recent traces.

**Constraint**: These E2E tests use the same mock fixtures as S1, but exercise the full `process_improvement_task()` flow end-to-end. They do NOT test the orchestrator's invocation of the wire module (that's covered by S1.3/S1.4).

### S3 -- Move Inline `import asyncio` to Top-of-File

In `core/orchestrator.py`:
- Remove the inline `import asyncio` inside the `try:` block at line ~282
- Add `import asyncio` to the top-of-file imports block (after stdlib imports, before third-party)
- No logic change -- just import hygiene

After edit: `python -c "import ast; ast.parse(open('core/orchestrator.py').read())"` (OR6)

### S4 -- File-Scoped Verification (Fail Fast)

After each file edit, run `/jarvis-verify`. Then:

1. Ruff: `ruff check core/orchestrator.py tests/test_improvement_loop.py AGENTS.md`
2. Mypy on test file: `mypy tests/test_improvement_loop.py --ignore-missing-imports`
3. Mypy on orchestrator: `mypy core/orchestrator.py --ignore-missing-imports`
4. Targeted tests: `python -m pytest tests/test_improvement_loop.py -v`
5. Full harness tests: `python -m pytest tests/test_eval_harness.py tests/test_orchestrator_improvement.py -v`

Run scan tools ONE AT A TIME (OR3).

### S5 -- Baseline Reconciliation

Run full test suite: `python -m pytest tests/ -q --tb=short`

- Expected: **1247 passed (+22 from baseline 1225), 67 skipped**
  - +2 restored integration tests (S1)
  - +20 E2E validation tests (S2)
- If actual count differs by >5 from expected, update PLANS.md baseline per OR17.
- If ruff/mypy errors appear outside edited files, STOP and report -- do not fix unilaterally (OR16).

## Closing

**Run `/jarvis-close`** -- handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md (if new pattern), rule proposal (C9), docs commit, push, post-push verification. If workflow missing or fails, STOP and report.

**Closing checklist:**
- [ ] 1247 passed, 67 skipped (baseline 1225 + 22)
- [ ] Ruff: 0 errors
- [ ] Mypy: 19 errors in existing core/ files (unchanged from Plan 63a baseline); no new errors introduced
- [ ] Tag `prompt-63b` created and pushed
- [ ] CHANGELOG entry appended (list ALL files actually edited: AGENTS.md, core/orchestrator.py, tests/test_improvement_loop.py)
- [ ] PLANS.md: Plan 63b completed, Plan 64 promoted to ACTIVE
- [ ] No new LANDMINES.md entries (or capture if pattern found)
- [ ] C9: OR25 and OR26 already added at S0.3; no additional rule proposals unless new pattern found

**Post-push verification** (OR11): `git ls-remote --tags origin | Select-String "prompt-63b"` -- if empty, push failed.

**Audit trail note** (per OR23): Throughout execution, cite OR25 when restoring the deleted tests, OR26 when handling the cleanup commit pattern, OR16/OR22 when encountering any scope question, OR3 when running scan tools, OR6 after each syntax check, OR17 when reconciling baselines.
