# Plan 64 — Core Mypy Remediation

## Context Brief

The mypy error count has been outside tolerance since Plan 60 (283 → 294, +11). This plan remediates the 33 type errors in `core/` files, which constitute the architectural foundation. Fixing these alone brings the full-repo count below the 283 baseline, resolving the 4-plan tolerance breach.

All errors are Tier 1 (safe, no runtime behavior change) or Tier 2 (localized interface alignment). No Tier 3 (architectural redesign) errors exist.

**Scope**: Fix 33 mypy errors across 11 files in `core/`. No new features. No new horizontal capability.

**Conventions**: "Apply OR6" means run syntax/import check after editing: `python -c "import ast; ast.parse(open('<file>.py').read())"`. OR6 is defined in AGENTS.md — read at S0.2.

---

## S0 — Opening

S0.1. Run `/jarvis-open` — verifies `prompt-63b` tag on origin, confirms working copy is clean and on master. If the workflow is missing or fails, STOP and report.

S0.2. Read `AGENTS.md` in full. AGENTS.md is always-on — every file edit in this plan MUST comply with its rules. If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context behind the rule.

S0.3. No new AGENTS.md rules this prompt. Proceed to S1.

---

## S1 — Investigate interfaces (READ-ONLY, STOP gate before S2)

Before fixing any Tier 2 errors, understand the actual interfaces these files depend on. This step is read-only — no edits.

S1.1. Read `core/multi_worker.py` end-to-end. Identify:
- What `WorkerBase.execute()` was supposed to be vs. what actually exists (`run()`, `build_prompt()` + `generate()` + `parse_output()`)
- What `orchestrator.adapter` was supposed to be vs. what actually exists (`fallback_chain`, worker-level `llm`)
- What `ResourceBudget.check_all_budgets()` was supposed to be vs. what actually exists (`check_vram_budget()`, `check_token_budget()`, `check_concurrent_budget()`)

S1.2. Read `core/rating_system.py` `record_rating()` method. Note all positional and keyword arguments, their types, and their order. This informs the S4.5 fix — do not attempt the fix until the actual signature is confirmed.

S1.3. Read `core/event_trigger.py` lines 200-230. Identify:
- What `process_task()` requires (it now takes `worker_id`)
- How triggers should route to workers — through `route_task()` or directly

S1.4. Read `core/worker_base.py` to confirm:
- The `WorkerBase` public interface (methods, attributes)
- Whether `llm` is the correct attribute name for the adapter
- The `run()` method signature

S1.5. Read `core/orchestrator.py` `__init__` and relevant methods to confirm:
- Whether `adapter` exists or should be accessed via `fallback_chain`
- The `process_task()` signature

**STOP gate**: After S1, report findings to the user before proceeding to S2. For each interface mismatch, classify using this decision tree:

**For `WorkerBase.execute()` vs. actual interface:**
- If `execute()` exists but is unused elsewhere → replace call with `run()`
- If `execute()` doesn't exist AND `run()` encapsulates the full execution pipeline → replace `execute` with `run`
- If `execute()` doesn't exist AND `run()` is only a partial pipeline (missing steps that `execute()` was supposed to perform) → STOP and report (needs design meeting)

**For `orchestrator.adapter` vs. actual interface:**
- If `fallback_chain` provides adapter access → use `self.orchestrator.fallback_chain` or equivalent
- If no single adapter property exists → refactor call site to pass adapter explicitly from worker context
- If adding an `adapter` property to Orchestrator would be clean and safe → report to user for approval before adding

**For `ResourceBudget.check_all_budgets()` vs. actual interface:**
- If the method can be a composite of existing checks → add it (real semantics)
- If the call site should use individual checks → refactor the call
- If neither is clean → STOP and report

**For `record_rating()` signature mismatch:**
- If the call site args can be mapped 1:1 to the actual signature → apply the fix
- If required args are unavailable at the call site (no task_id, no model_used) → STOP and report

Do NOT proceed with edits until the user confirms the S1 findings and approves the approach.

---

## S2 — Tier 1 fixes (15 errors, zero runtime behavior change)

Fix all safe type errors that require only type assertions, None guards, annotations, or `cast()`. Each fix is numbered to match the Tier 1 error count.

| # | File | Line ~ | Error | Fix |
|---|---|---|---|---|
| 1 | core/auth.py | 114 | `compare_digest` cannot accept `str\|None` | Add `assert self._token is not None` before call |
| 2 | core/a2a_protocol.py | 89 | `UUID\|None` not `UUID` for arg 2 | Add `assert request.parent_task_id is not None` before raise |
| 3 | core/rating_system.py | 325 | Overloaded `.get` confuses mypy | Replace `.get` with lambda in `max()` |
| 4 | core/evaluator.py | 81 | dict not accepted where `Message` expected | Wrap as `Message(role="user", content=prompt)` |
| 5 | core/instruction_generator.py | 64 | dict not `Message` | Wrap as `Message(...)` |
| 6 | core/instruction_generator.py | 177 | dict not `Message` | Wrap as `Message(...)` |
| 7 | core/instruction_generator.py | 187 | dict not `Message` | Wrap as `Message(...)` |
| 8 | core/orchestrator.py | 877 | `list[Any]` not `str` in `dict[str, str]` | Annotate result dict as `dict[str, Any]` |
| 9 | core/orchestrator.py | 878 | `Any\|None` not `str` in dict | Same fix as #8 |
| 10 | core/orchestrator.py | 879 | `getattr` 3rd arg type mismatch | Same fix as #8 |
| 11 | core/orchestrator.py | 880 | `getattr` 3rd arg type mismatch | Same fix as #8 |
| 12 | core/orchestrator.py | 881 | `getattr` 3rd arg type mismatch | Same fix as #8 |
| 13 | core/multi_worker.py | 272 | `WorkerResponse\|BaseException` not `WorkerResponse` | Add `assert isinstance(result, WorkerResponse)` in else branch |
| 14 | core/handlers.py | 153 | `str\|None` not assignable to `Sequence[str]` | Annotate `status_info: dict[str, Any]` |
| 15 | core/handlers.py | 154 | Same root cause as #14 | Same fix as #14 |

S2.1. Fix #1: `core/auth.py` ~line 114 — Add `assert self._token is not None` before `compare_digest(self._token, token)`. The preceding `if` block already guards this at runtime; the assert is for mypy only. Apply OR6.

S2.2. Fix #2: `core/a2a_protocol.py` ~line 89 — Add `assert request.parent_task_id is not None` before `CircularDependencyError(...)`. The `_check_circular` guard ensures non-None. Apply OR6.

S2.3. Fix #3: `core/rating_system.py` ~line 325 — Replace `max(model_averages, key=model_averages.get)` with `max(model_averages, key=lambda k: model_averages[k])`. Identical runtime behavior; avoids overloaded `.get` confusion. Apply OR6.

S2.4. Fix #4: `core/evaluator.py` ~line 81 — Replace `messages=[{"role": "user", "content": prompt}]` with `messages=[Message(role="user", content=prompt)]`. Import `Message` if not already imported. Apply OR6.

S2.5. Fixes #5-7: `core/instruction_generator.py` ~lines 64, 177, 187 — Replace all 3 dict literals with `Message(role="user", content=prompt)` or the appropriate role. Import `Message` if not already imported. Apply OR6.

S2.6. Fixes #8-12: `core/orchestrator.py` method `_get_worker_profiles` ~lines 877-881 — Find the `result = {}` line at the beginning of the method and change it to `result: dict[str, Any] = {}` (import `Any` from `typing` if not already). This annotation must go on the initial assignment, before any dict entries are added — that's where mypy infers the value type. This resolves all 5 errors — the dict was incorrectly inferred as `dict[str, str]` because early entries are string-valued. Apply OR6.

S2.7. Fix #13: `core/multi_worker.py` ~line 272 — Add type narrowing after the `isinstance(result, Exception)` check. In the `else` branch, add `assert isinstance(result, WorkerResponse)` before `responses.append(result)`. Apply OR6.

S2.8. Fixes #14-15: `core/handlers.py` ~line 153 — Annotate `status_info: dict[str, Any] = {...}` to widen the dict value type from the overly-narrow `Sequence[str]`. Import `Any` from `typing` if not already. Apply OR6.

S2.9. Run `ruff check` on all 7 files touched in S2. Fix any lint issues.

S2.10. Run file-scoped mypy on all 7 S2 files only (S3, S4, S5 have their own mypy runs; S6 re-verifies everything together): `mypy core/auth.py core/a2a_protocol.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/orchestrator.py core/multi_worker.py core/handlers.py --ignore-missing-imports`. Verify: all 15 Tier 1 errors resolved, no new errors introduced.

S2.11. Run `python -m pytest tests/ -q --tb=short`. Verify: same test count as baseline (1232 passed, 67 skipped). No regressions.

---

## S3 — Tier 2 easy fixes (6 errors, low-risk interface alignment)

S3.1. `core/notification.py` ~line 54: Add `if TYPE_CHECKING: from gateways.telegram.gateway import TelegramGateway` at the top. Remove any `noqa: F821` comment if present. This resolves the "Name not defined" error without creating a runtime import cycle. Apply OR6.

S3.2. `core/worker_factory.py` ~line 31: **Before editing**: Read `core/worker_base.py` and confirm `LLMResponse` is exported. If `LLMResponse` is not found in `worker_base.py`, STOP and report — do not guess the import source. If confirmed: change the import of `LLMResponse` from `core.schemas` to `core.worker_base`. Apply OR6.

S3.3. `core/instruction_versioning.py` ~line 147 — The call to `submit_for_approval()` uses a different signature than `request_approval()`. Add a `submit_for_approval()` compatibility shim to `core/approval_gate.py` that constructs an `ApprovalRequest` from the keyword args and delegates to `request_approval()`. This resolves the mypy error without breaking test mocks that assert on `submit_for_approval` calls. Apply OR6 to both files.

S3.4. `core/handlers.py` ~lines 498, 501, 533, 536: Add `command.context is not None` guard before accessing `.session_id`. Change `if self.session_manager and command.context.session_id:` to `if self.session_manager and command.context is not None and command.context.session_id:`. This adds a missing runtime None guard — the current code would crash if `context` were None. Apply OR6.

S3.5. Run `ruff check` on all 4 files touched in S3.

S3.6. Run file-scoped mypy on all 4 files: `mypy core/notification.py core/worker_factory.py core/instruction_versioning.py core/handlers.py --ignore-missing-imports`. Verify: all Tier 2 easy errors resolved.

S3.7. Run `python -m pytest tests/ -q --tb=short`. Verify: same test count. No regressions.

---

## S4 — Tier 2 multi_worker.py fixes (9 errors, medium-risk interface alignment)

**Precondition**: S1 findings confirmed by user. If S1 findings deviate from the expected approaches below, STOP before S4 and report to the user. Otherwise, apply the fixes below as written.

S4.1. `ResourceBudget.check_all_budgets` (~line 122): Based on S1 findings:
- If `check_all_budgets` can be implemented as a composite of existing budget checks (`check_vram_budget` + `check_token_budget` + `check_concurrent_budget`), add the method to `core/resource_budget.py`.
- If the call site should use individual checks instead, refactor the call.
- **Do NOT add a method that just passes or returns a constant** — the method must have real budget-checking semantics.

S4.2. `Orchestrator.adapter` (~line 149): Based on S1 findings:
- If the orchestrator's adapter is accessible via `self.fallback_chain`, replace `self.orchestrator.adapter` with the appropriate accessor.
- If no single adapter exists (orchestrator uses fallback chain), refactor the call site to pass the adapter explicitly from the worker or the caller context.

S4.3. `WorkerBase.execute` (~lines 227, 317): Based on S1 findings:
- If `WorkerBase.run()` encapsulates the full execution pipeline, replace `worker.execute(...)` with `worker.run(...)`.
- If `execute()` was intended as a distinct method, add it to `WorkerBase` as an alias or a new method that calls the pipeline.
- **Do NOT add a stub method** — the method must have real execution semantics.

S4.4. `WorkerBase.adapter` (~lines 302, 348): Replace `worker.adapter` with `worker.llm` (or whatever the actual attribute name is, per S1 findings). Verify this is correct by reading `WorkerBase.__init__`.

S4.5. `record_rating` signature mismatch (~lines 379, 384): Use the signature confirmed at S1.2. Fix the call sites to pass all required positional arguments in the correct order. If required args (task_id, model_used, etc.) are unavailable at the call site, STOP and report — do not invent placeholder values.

S4.6. Run `ruff check core/multi_worker.py`.

S4.7. Run file-scoped mypy: `mypy core/multi_worker.py --ignore-missing-imports`. Verify: all 9 multi_worker errors resolved.

S4.8. Run `python -m pytest tests/ -q --tb=short`. Verify: same test count. No regressions. If any test breaks, the interface change was not backward-compatible — STOP and report.

---

## S5 — Tier 2 event_trigger.py fix (1 error, design decision)

S5.1. Based on S1 findings for `core/event_trigger.py` ~line 214 (`process_task` missing `worker_id`):
- If the trigger should route through `route_task()` (which selects a worker automatically), replace `process_task()` call with `route_task()`.
- If the trigger config includes a worker ID, pass it to `process_task()`.
- If neither applies, add a `worker_id` parameter to the trigger config and pass it through.
- **Do NOT pass a hardcoded or dummy worker_id** — the fix must have real routing semantics.

S5.2. Run `ruff check core/event_trigger.py`.

S5.3. Run file-scoped mypy: `mypy core/event_trigger.py --ignore-missing-imports`. Verify: error resolved.

S5.4. Run `python -m pytest tests/ -q --tb=short`. Verify: same test count. No regressions.

---

## S6 — Verification

S6.1. Full test suite: `python -m pytest tests/ -q --tb=short`. Expected: 1232 passed, 67 skipped (±5 tolerance). If test count drops, investigate before proceeding.

S6.2. Ruff check on ALL touched files (comprehensive re-verification; each section also verified in isolation):
```
ruff check core/auth.py core/a2a_protocol.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/orchestrator.py core/multi_worker.py core/handlers.py core/notification.py core/worker_factory.py core/instruction_versioning.py core/event_trigger.py
```
Add `core/resource_budget.py` if S4.1 added `check_all_budgets`. Expected: 0 errors.

S6.3. File-scoped mypy on ALL touched files (comprehensive re-verification):
```
mypy core/auth.py core/a2a_protocol.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/orchestrator.py core/multi_worker.py core/handlers.py core/notification.py core/worker_factory.py core/instruction_versioning.py core/event_trigger.py --ignore-missing-imports
```
Add `core/resource_budget.py` if S4.1 added `check_all_budgets`. Expected: 0 errors on all touched files (pre-existing errors in untouched files may still exist).

S6.4. Full-repo mypy count (soft gate): `mypy . --ignore-missing-imports 2>&1 | Select-String "error:" | Measure-Object`. Record the count.
- **Expected**: below 283 (original baseline).
- **If ≥283**: Plan succeeded locally (file-scoped zero on touched files), but full-repo count may hide regressions in untouched files or confirm that non-core errors dominate. Report the count and investigate any unexpected additions in files not touched by this plan.
- **If <283**: Tolerance breach resolved. Update PLANS.md status sections accordingly.

---

## S7 — Closing

Run `/jarvis-close` — handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md, rule proposal, docs commit, push, and post-push verification.

**Expected CHANGELOG entry**:
```
## <date> HH:MM — prompt-64

**Plan**: Core Mypy Remediation

**Changed**:
- core/auth.py: Added None guard before compare_digest (mypy)
- core/a2a_protocol.py: Added assert for parent_task_id non-None (mypy)
- core/rating_system.py: Replaced .get with lambda in max() (mypy)
- core/evaluator.py: Wrapped dict literal as Message object (mypy)
- core/instruction_generator.py: Wrapped 3 dict literals as Message objects (mypy)
- core/orchestrator.py: Annotated _get_worker_profiles result dict as dict[str, Any] (mypy)
- core/multi_worker.py: Fixed WorkerBase interface calls, record_rating signatures, type narrowing (mypy)
- core/handlers.py: Widened status_info dict type, added command.context None guards (mypy)
- core/notification.py: Added TYPE_CHECKING import for TelegramGateway (mypy)
- core/worker_factory.py: Fixed LLMResponse import source (mypy)
- core/instruction_versioning.py: Renamed submit_for_approval to request_approval (mypy)
- core/event_trigger.py: Fixed process_task worker_id routing (mypy)
- core/resource_budget.py: Added check_all_budgets composite method (only if S4.1 chose this path; omit this line from CHANGELOG if S4.1 refactored the call site instead)

**Results**:
- Tests: <count> passed, <count> skipped
- Ruff: 0 errors
- Mypy (file-scoped on touched files): 0 errors
- Mypy (full-repo): <count> errors (was 294)
- Tag: prompt-64 verified on origin
```

**Expected PLANS.md updates**:
- Test baseline: unchanged (1232 passed, 67 skipped) unless tests added/removed
- Static analysis baseline: update mypy full-repo count per S6.4 result
- Completed prompts: add Plan 64 row
- Queue: shift 64→completed, 65→active, add new open slot
- Status sections: if mypy <283, move "Mypy error count exceeded tolerance" from "What's Broken" to resolved
- Baseline reconciliation: note mypy delta

**C9 rule proposal**: Assess whether any recurring pattern emerged during the type-fix work that a rule could prevent. If none, state: "No new rule proposals this plan. The errors fixed were pre-existing type annotations and interface drift — no systematic failure pattern observed."

---

## Scope Declaration

**WILL edit**:
- core/auth.py
- core/a2a_protocol.py
- core/rating_system.py
- core/evaluator.py
- core/instruction_generator.py
- core/orchestrator.py
- core/multi_worker.py
- core/handlers.py
- core/notification.py
- core/worker_factory.py
- core/instruction_versioning.py
- core/approval_gate.py
- core/event_trigger.py
- core/resource_budget.py

**Will NOT edit**:
- Any file outside `core/`
- Any test file (tests are read-only in this plan)
- AGENTS.md, PLANS.md, CHANGELOG.md, LANDMINES.md (closing handles these)
- Any skills/, system/, memory/, adapters/, cli/, web/, workers/ file

**Hard scope boundary** (OR15, OR16): If any fix requires editing a file outside the "WILL edit" list, STOP and report. Do NOT expand scope unilaterally.
