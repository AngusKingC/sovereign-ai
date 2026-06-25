# Plan 78 Rev5 Context Brief — Circuit Breaker at Orchestrator Level

**Note**: This is the context brief for Rev5, which incorporates Claude's Rev4 review findings (3 issues + 2 other concerns). Rev4's context brief is superseded. Rev5 is the version Devin will execute unless Claude's Rev5 review surfaces new CRITICAL issues.

## Part 1: Roles/Rules

Your job is to find issues in this plan, not rewrite it. Assume this plan will fail — identify how.

Each issue you report must include:
- A concrete failure scenario (what breaks, when, why)
- Evidence from the codebase or governance documents
- The impact if the issue is not addressed

You may report "No issues found" if the plan is sound. Do not invent problems.

Ban: style comments, formatting suggestions, speculative future features, "nice to have" items. Substance only.

---

## Part 2: Context

### Plan Scope

Extend the existing adapter-level circuit breaker (`core/adapter_fallback.py:AdapterFallbackChain`) to:
1. **Worker level** — new `WorkerCircuitBreaker` class in `core/worker_circuit_breaker.py`, keyed by `worker_id`. Includes `register_worker()` method and `_registered_workers: set[str]` field (Issue #4 fix).
2. **Orchestrator level** — aggregate check: when `degraded_worker_ratio >= degraded_mode_threshold`, orchestrator enters degraded mode. Default 0.5; CLI sets 0.2 for PEMADS Phase 2 (Issue #6).
3. **Degraded mode** — new `TaskStatus.QUEUED` value; tasks transition to QUEUED instead of FAILED. Queue stores `(task, worker_id, queued_at)` tuples (Issue #5 — timeout tracking). Type annotation `list[tuple[Task, str, datetime]]` (Rev5 Issue #2 fix).
4. **Resume path** — `_execute_task()` helper (Issue #2 recursion fix) + `_maybe_resume_queued_tasks()` method. Called ONLY from `process_task` (at start). On `_execute_task` failure during resume → transition to FAILED (Rev5 Issue #1 fix — NOT re-queue). Re-queue ONLY when worker is circuit-open. `MAX_RESUME_ITERATIONS=3` + `QUEUED_TASK_TIMEOUT_SECONDS=300`.

**Scope boundary**: Plan 78 = cascade failure prevention, NOT orchestrator-crash recovery. In-memory queue; crash loses queued tasks. Crash recovery is a separate plan.

### What Rev5 Fixed from Rev4 (Claude Review)

| Issue | Severity | Rev5 Fix |
|---|---|---|
| #1 `_execute_task` double-transitions; re-queue leaves task in EXECUTING, breaking timeout | HIGH | Removed pre-transition from `_maybe_resume_queued_tasks`. `_execute_task` handles QUEUED → EXECUTING internally. On `_execute_task` failure during resume → transition to FAILED (NOT re-queue). Invariant: `_queued_tasks` only contains QUEUED-state tasks. 3 new regression tests. |
| #2 `list[Task]` vs `list[tuple[...]]` mypy mismatch | MEDIUM | S2.1 annotation changed to `list[tuple[Task, str, datetime]]`. |
| #3 Inline `from datetime import` triggers Ruff | LOW | Moved to top of `core/orchestrator.py`. |
| Other — caller doesn't know task was queued | Design gap | "Caller Contract" note in S4.3: caller MUST inspect `metadata={"status": "queued"}`. Plan 81 implements callback/retry. |
| Other — resume caller latency | Design tradeoff | "Latency Tradeoff" note in S4.4: worst case ~2N seconds for N queued tasks. PEMADS Phase 2 max ~5 tasks → ~10s. Acceptable for turn-based debates. |

### Key Design Invariants (Rev5)

1. **`_queued_tasks` only contains QUEUED-state tasks.** Maintained by:
   - Timeout path: QUEUED → FAILED (no re-queue)
   - Circuit-open path: re-queue without state change (stays QUEUED)
   - Execution-failure path: EXECUTING → FAILED (no re-queue)
   - Execution-success path: task completes (no re-queue)

2. **No recursion.** `_maybe_resume_queued_tasks` calls `_execute_task` (NOT `process_task`). `record_success` does NOT trigger resume. Resume happens ONLY at `process_task` entry.

3. **Timeout clock never resets.** Re-queued tasks preserve original `queued_at`. A task stuck behind a perpetually-down worker will eventually time out (300s) → FAILED.

4. **Execution failures during resume are terminal.** If `_execute_task` raises, the task goes to FAILED — it does NOT go back to the queue. This mirrors normal `process_task` behavior (EXECUTING → FAILED on worker failure).

### What Was Verified by GLM AST Walk (2026-06-26)

- `AdapterFallbackChain` exists at `core/adapter_fallback.py:24` with circuit breaker logic
- `AdapterFallbackChain._failure_counts: dict` and `_circuit_open_since: dict` (lines 59-60) — precedent for in-memory state NOT being AR10 violation
- `Orchestrator.__init__` accepts `fallback_chain` via DI (line 51)
- `Orchestrator.register_worker` exists at line 102
- `Orchestrator.process_task` transitions to FAILED at line 457 on worker failure (EXECUTING → FAILED is valid in existing state machine — confirms Rev5 Issue #1 fix is safe)
- `TaskStatus` enum has 9 values (no `QUEUED`)
- `TraceComponent` has `WORKER` and `ORCHESTRATOR`
- `TraceEventType` has `CIRCUIT_BREAKER_OPEN`, `CIRCUIT_BREAKER_RESET`, `OPERATION_ERROR`
- `tests/test_adapter_fallback.py` has 14 tests

### Author's Reasoning (Attack This)

1. **Extend, don't generalize.** Separate `WorkerCircuitBreaker` class, not generic `CircuitBreaker[T]`. Avoids touching tested code.

2. **`_execute_task` helper eliminates recursion.** `process_task` = entry point. `_execute_task` = pure execution. `_maybe_resume_queued_tasks` calls `_execute_task` directly.

3. **Execution failures during resume are terminal (Rev5 Issue #1 fix).** If `_execute_task` raises, transition to FAILED — NOT re-queue. This maintains the invariant that `_queued_tasks` only contains QUEUED-state tasks. Re-queueing an EXECUTING-state task would break the timeout path (QUEUED → FAILED wouldn't apply). The existing state machine permits EXECUTING → FAILED (confirmed at orchestrator.py:457).

4. **Timeout-based orphaned task cleanup.** 300s timeout. Re-queued tasks preserve original `queued_at`.

5. **Rerouting deferred to Plan 81.** QUEUED tasks resume to the SAME `worker_id`.

6. **Persistence NOT in scope.** Plan 78 = cascade prevention, NOT crash recovery.

7. **Threshold 0.2 for PEMADS Phase 2.** Any single expert failure triggers degraded mode.

**Attack this reasoning**: Is the "execution failures are terminal" decision correct, or should there be a retry mechanism for transient failures during resume? Is the invariant (`_queued_tasks` only contains QUEUED-state tasks) actually necessary, or is it over-engineering? Is 300s timeout appropriate for PEMADS Phase 2 debates? Is the caller contract (metadata `status: "queued"`) sufficient signal, or does Plan 81 need a stronger mechanism (exception, Future, callback)?

### Open Questions (Post-Rev5)

1. **Generalize vs duplicate** (unchanged): Should `AdapterFallbackChain` and `WorkerCircuitBreaker` share a base class? GLM judges duplication acceptable for now.

2. **Timeout value**: Is 300s right for PEMADS Phase 2? Debates may have turns that take longer. (GLM judges 300s reasonable; tunable via constant.)

3. **AR10 interpretation**: Is `_queued_tasks` an AR10 violation? GLM judges NO (in-process operational state). If user/Claude judges YES, escalate to Tier 2.

4. **Caller contract sufficiency**: Is `metadata={"status": "queued"}` enough signal for Plan 81, or does it need an exception/Future/callback? (GLM judges metadata is sufficient for Plan 78; Plan 81 can add stronger mechanism if needed.)

5. **Execution failure retry**: Should transient failures during resume (e.g., network blip) be retried, or is terminal FAILED correct? (GLM judges terminal is correct — mirrors normal `process_task` behavior. Retry logic would add complexity and risk infinite loops.)

### Confidence Levels

- WorkerCircuitBreaker implementation: 92% (unchanged)
- Orchestrator wiring + `_execute_task` extraction (S2): 90% (up from 88% — type annotation fixed)
- Aggregate degraded mode (S3): 85% (unchanged)
- QUEUED + transitions + resume + timeout + execution-failure handling (S4): 85% (up from 80% — Issue #1 state invariant fixed, invariant test added)
- CLI wiring (S5): 92% (unchanged)

**Overall**: 88% (up from 85%). All 3 Rev4 issues + 2 other concerns resolved. Remaining risks are scope-boundary judgments (AR10 interpretation, rerouting deferral, in-memory queue, caller contract) that are defensible for Plan 78's stated purpose.

---

## Part 3: Answer Format

Respond with:

1. **Pre-mortem** (1-2 sentences): "If this plan failed in 6 months, the most plausible reason would be..."

2. **Issues** (0-N, each with):
   - Issue title
   - Severity: CRITICAL / HIGH / MEDIUM / LOW
   - Concrete failure scenario
   - Evidence from codebase or docs
   - Suggested fix (optional — GLM decides whether to adopt)

3. **Other concerns** (open field — anything unexpected)

4. **Overall verdict**: PROCEED / REVISE / REJECT

If no issues: "No issues found. PROCEED."

---

## Tier Disclosure

This plan is classified **Tier 1** (Claude only) per GR4. Justification:
- Single architectural subsystem (core/) — extends existing pattern
- GLM confidence 88% overall (above 70% threshold)
- All Rev2/Rev3/Rev4 issues resolved with targeted fixes — no architectural disagreements

Rev4 was also Tier 1. Claude's Rev4 review found 3 implementation bugs (logic error + type annotation + import placement) — all fixable with targeted edits, no architectural disagreement. If Claude's Rev5 review surfaces new architectural disagreements GLM can't resolve, GLM will escalate to Tier 2.

**Outstanding Tier 2 candidate**: Issue #3 from Rev3 (AR10 interpretation of `_queued_tasks`). GLM judges it's NOT an AR10 violation (in-process operational state, `AdapterFallbackChain._failure_counts` is precedent). If the user or Claude judges YES, that IS an architectural disagreement requiring 5-AI panel input. This is the one Rev5 decision that could legitimately trigger Tier 2.
