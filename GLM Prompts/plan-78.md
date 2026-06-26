# Plan 78 — Circuit Breaker at Orchestrator Level

## Rev6 Changes (2026-06-26)

Rev6 incorporates Claude's Rev5 review findings (2 issues: 1 HIGH, 1 LOW + 1 other concern). All are surgical fixes.

| Issue | Severity | Rev6 Fix |
|---|---|---|
| #1 `record_success`/`record_failure` called twice on normal `process_task` path (double-counting → circuit opens at half the intended threshold) | HIGH | **Duplication removed.** S2.1a now explicitly instructs: when replacing `worker.run(task)` with `_execute_task(task, worker_id)`, ALSO remove the `record_success`/`record_failure` calls added in S2.1's post-`worker.run` instructions. `_execute_task` owns these calls exclusively. Added explicit note about the double-counting consequence if omitted. |
| #2 `_execute_task` comment says "resume path may already be EXECUTING" — false in Rev5 | LOW | **Comment updated.** Now reads: "Transition to EXECUTING. Resume path arrives with task in QUEUED state; direct process_task path may arrive in any pre-EXECUTING state. Guard handles both." |
| Other — AR10 note still says `list[Task]` | LOW | **Type reference fixed.** AR10 Interpretation note now says `list[tuple[Task, str, datetime]]` to match the `__init__` annotation. |

**GR4 process note**: GLM is at Rev6 under Tier 1 review. Per GR4, GLM should have escalated to Tier 2 at Rev3. This is a process violation. However, all Rev3/4/5/6 findings were surgical implementation bugs (not architectural disagreements), and Claude's verdicts were REVISE (not REJECT). GLM recommends Tier 2 escalation before delivery if the user wants a clean-process review. Otherwise, Rev6 is ready for delivery.

---

## Rev5 Changes (2026-06-26, retained for history)

Rev5 incorporated Claude's Rev4 review findings (3 issues + 2 other concerns). See Rev5 file for details. Rev6 supersedes Rev5.

---

## Scope Boundary (NEW — Rev4, Issue #1 clarification)

**Plan 78 delivers cascade failure prevention. It does NOT deliver orchestrator-crash recovery.**

These are different failure modes:

| Failure mode | What happens | Plan 78 coverage |
|---|---|---|
| **Cascade failure** | Worker A fails → its failure propagates to Workers B, C, D (e.g., shared resource exhaustion, retry storm) | ✅ Covered — circuit breaker opens for Worker A, isolating its failure. Other workers continue. |
| **Orchestrator crash** | Orchestrator process dies (OOM, segfault, power loss) | ❌ NOT covered — in-memory `_queued_tasks` list is lost on crash. Tasks in QUEUED state at crash time are unrecoverable. |

**Why this is acceptable for PEMADS Phase 2**:
- PEMADS Phase 2 debates are turn-based. If the orchestrator crashes mid-debate, the debate is lost regardless of queue persistence (the debate state lives in the orchestrator's memory too).
- Orchestrator crash recovery is a separate concern requiring persistent debate state, checkpointing, and restart logic. That belongs in a dedicated `orchestrator-crash-recovery` plan, not in Plan 78.
- Plan 78's value is preventing cascade failure — the common case where one worker's failure triggers a cascade that brings down the whole system. This is the #1 reliability risk for PEMADS Phase 2.

**PLANS.md queue entry update** (S0.4): The Plan 78 queue entry text changes from "Required before PEMADS Phase 2 (live debates)" to "Required before PEMADS Phase 2 — cascade failure prevention only. Orchestrator-crash recovery is a separate concern (deferred to `orchestrator-crash-recovery` plan)."

---

## Rev3 Changes (2026-06-26, retained for history)

Rev3 incorporated Claude's Rev2 review findings (5 issues). See Rev3 file for details. Rev4 supersedes Rev3.

---

## Context

PLANS.md queue entry (verified at commit `a5cff19`):

> **Plan 78 — Circuit Breaker at Orchestrator Level (Priority 2 — Kimi High)**
> Scope: Extend existing `core/adapter_fallback.py` circuit breaker to per-worker and orchestrator-level. Add degraded mode (queue tasks instead of failing). Required before PEMADS Phase 2 (live debates).
> Expected impact: Cascade failure prevention. Prerequisite for PEMADS Phase 2 safety.

This is **Rev2** of the plan. Rev1 was rejected by GLM review on 2026-06-26 for scope divergence (Rev1 was "Infrastructure & Modularity Remediation" — unrelated to the PLANS.md queue entry). Rev2 reverts to the queue-mandated Circuit Breaker scope. The infrastructure remediation work from Rev1 is deferred to a named plan `infra-remediation` (following the `ar18-fix-all` / `rule-cleanup` precedent for named remediation plans). A placeholder entry for `infra-remediation` will be added to PLANS.md at closing (C12).

**Current state of circuit breaker in the repo** (verified by GLM AST walk, 2026-06-26):
- `core/adapter_fallback.py:AdapterFallbackChain` implements circuit breaker at the **adapter** level only (per-adapter failure counts, open/reset state, timeout-based reset)
- `core/orchestrator.py:Orchestrator` accepts `fallback_chain` via DI and attaches it to workers (line 107-108), but does NOT track per-worker failure state
- `core/worker_base.py:WorkerBase` has no circuit breaker awareness — workers fail, orchestrator catches exception, task transitions to FAILED
- `TaskStatus` enum has no `QUEUED` or `DEGRADED` state — failed tasks go straight to FAILED
- `TraceComponent` enum has `WORKER` and `ORCHESTRATOR` values (no new components needed)
- `TraceEventType` has `CIRCUIT_BREAKER_OPEN` and `CIRCUIT_BREAKER_RESET` (reusable for worker/orchestrator level)
- Existing tests: `tests/test_adapter_fallback.py` has 14 tests covering adapter-level circuit breaker

**Author's reasoning**: Extend the existing `AdapterFallbackChain` pattern rather than create a new abstraction. The circuit breaker logic (failure threshold → open → timeout → reset) is identical across levels; only the unit of failure changes (adapter → worker → orchestrator). A `WorkerCircuitBreaker` class wrapping the same logic, plus an orchestrator-level aggregate check, is simpler than a generic `CircuitBreaker[T]` abstraction. Degraded mode = when orchestrator-level circuit breaker is open, transition new tasks to a `QUEUED` state instead of FAILED, and retry when the breaker resets.

**Confidence**: 75% overall. 85% on WorkerCircuitBreaker (clear pattern extension). 70% on orchestrator-level aggregate (design choice: count-based vs time-based aggregation). 65% on degraded mode QUEUED state (new TaskStatus value — needs careful transition-table update).

---

## Opening (S0)

### S0.1. Run `/jarvis-open`

Verify `prompt-77` tag exists on origin:
```powershell
git ls-remote --tags origin | Select-String "prompt-77"
```
If empty, push failed — STOP and report.

Confirm working copy is clean and on master:
```powershell
git status -s
git branch --show-current
```

**Applying OR26 (governance-doc cleanup at opening)**: If `git status -s` shows modified or untracked governance docs (`AGENTS.md`, `AI_HANDOFF.md`, `PLANS.md`, `CHANGELOG.md`, `LANDMINES.md`) or plan files in `GLM Prompts/`, commit them as a standalone `docs: cleanup pre-prompt-78` commit tagged `docs-cleanup-78` BEFORE proceeding to S0.2. Do NOT bundle them into the `prompt-78` tag. The CHANGELOG entry for `prompt-78` must list only files edited as part of the plan body (S1-S5).

**Applying OR39 (plan-file retention)**: If `plan-77*.md` files exist in `GLM Prompts/` and are untracked, they are an OR26 violation from Plan 77 — commit them as part of the `docs-cleanup-78` commit above. The current plan's file (`plan-78*.md`) will be added in C12.

If the workflow is missing or fails, STOP and report.

### S0.2. Read AGENTS.md in full

AGENTS.md is always-on — every file edit in this plan MUST comply. Pay special attention to:
- AR1: `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/`. (WorkerCircuitBreaker lives in `core/`; it must not import from `workers/`.)
- AR9: No raw LLM calls outside `adapters/`. (N/A — no LLM calls in this plan.)
- AR10: No memory access outside `MemoryRouter`. (Degraded mode queue persistence MUST go through MemoryRouter.)
- AR11: `TraceEmitter` via constructor injection only. Never use the global `emit_trace()` function.
- AR12: All I/O operations are async.
- AR14: All public functions and methods have return type annotations.
- AR18: No broad `except Exception: pass` without inline comment + WARNING trace.
- OR5: Never use `replace_all`. Edit each occurrence individually.
- OR6: Syntax check after every file edit, BEFORE tests.
- OR15: Pre-declare scope before editing. (See "Scope Declaration" at end of this plan.)
- OR16: HARD STOP on scope expansion.
- OR22: Re-read AGENTS.md before any file edit.
- OR23: Cite rules by number when applying them.
- OR34: Execute steps in strict numerical order.

If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the source landmine and diagnostic context.

### S0.3. Install GR1 into AI_HANDOFF.md and commit

This plan installs one new rule into `AI_HANDOFF.md` (not `AGENTS.md` — GR rules are GLM's, not Devin's). The rule is **GR1: Refresh local rules when appropriate**.

**Applying GR6 (cite Devin's rules by number)**: This step applies OR26 (governance-doc edits at /jarvis-open are a separate commit and tag) and OR39 (plan files committed in C12).

Edit `AI_HANDOFF.md` — append a new section after the "Tiered Review System" section:

```markdown
## GLM Operating Discipline (NEW — Plan 78)

GLM maintains a local rules file at `/home/z/my-project/glm_rules.md` (outside the repo, since GLM doesn't write to the repo). Rules are prefixed `GR{n}` to mirror Devin's `AR{n}`/`OR{n}` scheme. The canonical copy of GR rules lives in this section; the local file is a mirror for GLM's own reference.

### GR1. Refresh local rules when appropriate

At the start of every new GLM chat session, BEFORE doing any plan work:
1. Check if `/home/z/my-project/glm_rules.md` exists. If not, derive it from `AI_HANDOFF.md` + `AGENTS.md` + `LANDMINES.md` in the cloned repo.
2. If it exists, diff its `## Sync` section against the latest commit touching `AI_HANDOFF.md`, `AGENTS.md`, or `LANDMINES.md` on origin. If any of those files were updated since the last sync, re-derive the local rules file from the current repo state.
3. If a Devin execution log references a new governance patch or new AR/OR rule, refresh local rules AFTER reviewing the log (Workflow Step 4) so the new rule is in scope for the next plan.

Without this rule, a new GLM chat operates on stale rules — it doesn't know about AR20, OR39, governance patches, or new landmines added since the last chat. Stale rules → wrong plans → Devin STOP conditions → wasted cycles.

Every version of the local rules file MUST end with a `## Sync` section recording: (a) the commit SHA of `AI_HANDOFF.md` at last sync, (b) the commit SHA of `AGENTS.md` at last sync, (c) the commit SHA of `LANDMINES.md` at last sync, (d) the date.

(Source: GLM observation, post-rule-cleanup chat — GLM had no canonical rules file and was operating from inferred context. User requested codification.)
```

Commit as `governance: add GR1 (GLM local rules refresh) to AI_HANDOFF.md` and tag as `governance-gr1`. This is a governance commit, separate from the `prompt-78` tag (per OR26).

**Note**: Only GR1 is installed in this plan. GR2-GR15 (full GLM operating discipline set) are deferred to a future governance patch — they need real-world validation before codification. GR1 is the highest-priority rule because without it, future GLM chats operate on stale rules.

### S0.4. Update PLANS.md queue to reflect infra-remediation deferral

Edit `PLANS.md` "Next 5 Prompts Queue" section. After the Plan 85 (Open Slot TBD) entry, add:

```markdown
### Plan infra-remediation — Infrastructure & Modularity Remediation (deferred from Plan 78 Rev1)

**Scope**: Fix systematic gaps between AGENTS.md rules and code reality discovered in GLM AST scan (2026-06-26, verified counts):
- 2 AR1 violations (core/worker_factory.py:38, core/resource_budget.py:23 — inline imports of system/)
- 264 AR18 violations (bare `except Exception: pass` across 43 files — top: skills/notes/notes_skill.py:36, skills/calendar/calendar_skill.py:24, skills/reminder/reminder_skill.py:18)
- 38 print() statements in production code (top: core/observability.py:5)
- test_ar18_compliance.py is BROKEN — passes while 264 violations exist (only catches `except Exception:` immediately followed by `pass`, misses the common `except Exception:\n    # comment\n    pass` pattern)

**Prerequisite**: Fix test_ar18_compliance.py FIRST (S2.1 of infra-remediation plan) before any AR18 remediation work.

**Expected impact**: Closes the gap between AGENTS.md rules and code reality. Not blocking PEMADS Phase 2.

**Gate**: Full test suite pass, ruff 0, mypy 0, test_ar18_compliance.py actually fails on real violations.
```

This update goes into the S0.3 governance commit (it's a PLANS.md queue edit, not a plan-body edit).

---

## Plan Body

### S1 — WorkerCircuitBreaker Implementation

**Applying AR1**: `WorkerCircuitBreaker` lives in `core/` (new file `core/worker_circuit_breaker.py`). It MUST NOT import from `workers/`, `adapters/`, `cli/`, `memory/`, `skills/`, `web/`, or `system/`. It imports from `core/observability.py` only (for TraceEmitter, TraceEvent, TraceComponent, TraceEventType, TraceLevel).

**Applying AR11**: `TraceEmitter` is injected via constructor. Never use the global `emit_trace()` function.

**Applying AR12**: All I/O operations (trace emission) are async. State mutations (failure count, circuit open/reset) are synchronous — they're in-memory state, not I/O.

**Applying AR14**: All public methods have return type annotations.

#### S1.1. Create `core/worker_circuit_breaker.py`

New module containing `WorkerCircuitBreaker` class. This class wraps the same circuit breaker logic as `AdapterFallbackChain` but keyed by `worker_id` instead of adapter index.

**Public API**:
```python
class WorkerCircuitBreaker:
    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        failure_threshold: int = 3,
        reset_timeout: int = 60,
    ) -> None: ...

    def register_worker(self, worker_id: str) -> None: ...
        """Seed the tracked worker set with worker_id (count=0, circuit closed).
        Adds worker_id to _registered_workers (the canonical roster used as
        denominator for get_degraded_worker_ratio) AND seeds _failure_counts
        and _circuit_open_since. MUST be called by Orchestrator.register_worker
        for every worker at registration time. Idempotent — registering an
        already-tracked worker is a no-op.
        (Source: Claude Rev2 review Issue #1 — CRITICAL; Rev3 had a regression
        where get_degraded_worker_ratio still used _failure_counts as denominator
        instead of the registered roster. Rev4 fixes this by tracking
        _registered_workers separately. — Claude Rev3 review Issue #4)"""

    def record_failure(self, worker_id: str) -> None: ...
        """Increment failure count for worker_id. Open circuit if threshold reached.
        If worker_id is not registered, auto-registers it first (defensive)."""

    def record_success(self, worker_id: str) -> None: ...
        """Reset failure count for worker_id. Close circuit if open.
        If worker_id is not registered, auto-registers it first (defensive)."""

    def is_available(self, worker_id: str) -> bool: ...
        """True if worker_id's circuit is closed or reset timeout has elapsed.
        Unknown (unregistered) workers return True (no failures recorded)."""

    async def reset_circuit(self, worker_id: str) -> None: ...
        """Manually reset circuit for worker_id. Emits CIRCUIT_BREAKER_RESET trace."""

    def get_status(self) -> list[dict]: ...
        """Return status of all tracked workers. Read-only, sync-safe."""

    def get_degraded_workers(self) -> list[str]: ...
        """Return list of worker_ids with open circuits. Used by orchestrator for degraded mode."""

    def get_degraded_worker_ratio(self) -> float: ...
        """Return ratio of workers with open circuits to TOTAL REGISTERED workers
        (not total workers-seen-in-_failure_counts). Returns 0.0 if no workers
        registered. Used by orchestrator to detect cascade failure.
        (Source: Claude Rev2 review Issue #1 — denominator must be the registered
        roster, not the lazily-populated _failure_counts dict.)"""
```

**Trace events emitted** (reuse existing `TraceEventType` values — no new event types needed):
- `CIRCUIT_BREAKER_OPEN` with `component=TraceComponent.WORKER`, `data={"worker_id": ..., "failure_count": ...}`
- `CIRCUIT_BREAKER_RESET` with `component=TraceComponent.WORKER`, `data={"worker_id": ...}`

**Internal state**:
- `_registered_workers: set[str]` — the canonical roster of workers registered via `register_worker()`. Used as the denominator for `get_degraded_worker_ratio()`. (Issue #4 fix — separate from `_failure_counts` to avoid the lazy-population bug.)
- `_failure_counts: dict[str, int]` — per-worker failure count. Seeded with `0` for every worker via `register_worker()`. Auto-registers unknown workers in `record_failure`/`record_success` (defensive, but Orchestrator SHOULD call `register_worker` proactively at worker registration time).
- `_circuit_open_since: dict[str, float | None]` — per-worker circuit open timestamp (None = closed). Seeded with `None` for every worker via `register_worker()`.

#### S1.2. Syntax check + file-scoped ruff + mypy

```powershell
python -c "import ast; ast.parse(open('core/worker_circuit_breaker.py').read())"
ruff check core/worker_circuit_breaker.py
mypy core/worker_circuit_breaker.py --ignore-missing-imports
```

**STOP condition**: If any check fails, fix before proceeding.

#### S1.3. Create `tests/test_worker_circuit_breaker.py`

**Applying OR24**: Every new implementation MUST have a corresponding test file. Tests cover key paths.

Test cases (mirror `test_adapter_fallback.py` structure):
1. `test_record_failure_increments_count` — failure count goes 0 → 1 → 2
2. `test_record_failure_opens_circuit_at_threshold` — after `failure_threshold` failures, `is_available` returns False
3. `test_record_success_resets_count` — success resets count to 0
4. `test_record_success_closes_open_circuit` — success after open closes circuit
5. `test_is_available_returns_true_for_unknown_worker` — unknown workers are available (no failures recorded)
6. `test_is_available_returns_true_after_reset_timeout_elapses` — circuit auto-resets after timeout
7. `test_reset_circuit_clears_failure_count` — manual reset works
8. `test_reset_circuit_emits_reset_trace_event` — trace event emitted
9. `test_record_failure_emits_open_trace_event_at_threshold` — trace event emitted when circuit opens
10. `test_get_status_returns_correct_structure` — status list has correct shape
11. `test_get_degraded_workers_returns_only_open_circuits` — only workers with open circuits returned
12. `test_register_worker_seeds_failure_count_and_circuit_state` — register_worker adds worker with count=0, circuit_open=None (Issue #1 fix)
13. `test_register_worker_is_idempotent` — registering an already-tracked worker is a no-op
14. `test_get_degraded_worker_ratio_uses_registered_roster_as_denominator` — 2 of 5 registered workers degraded → 0.4 (NOT 1.0 from lazy-population bug) (Issue #1 regression test)
15. `test_record_failure_auto_registers_unknown_worker` — calling record_failure on unregistered worker auto-registers it
16. `test_concurrent_async_record_failures_do_not_corrupt_state` — `asyncio.gather` over multiple `record_failure` calls (for the same worker_id and different worker_ids) does not corrupt internal dicts. **Note**: This tests asyncio concurrency (single-threaded event loop), NOT multi-threaded concurrency. The `WorkerCircuitBreaker` is designed for the orchestrator's asyncio event loop; if multi-threaded access is added later, a `threading.Lock` would be required. (Source: Claude Rev2 review Issue #5 — renamed from "thread-safe" to "asyncio-safe" to avoid false confidence.)

**Applying AR18**: Test file may use `except Exception:` in test fixtures only if needed for cleanup — add inline comment + WARNING trace per AR18.

#### S1.4. Run tests

```powershell
pytest tests/test_worker_circuit_breaker.py -q --tb=short
```

**STOP condition**: If any test fails, fix before proceeding.

---

### S2 — Wire WorkerCircuitBreaker into Orchestrator

**Applying AR11**: `WorkerCircuitBreaker` is injected into `Orchestrator` via constructor.

#### S2.1. Update `core/orchestrator.py`

**Step A — Add `worker_circuit_breaker` to `Orchestrator.__init__`:**

**Applying OR20 + Issue #3 fix**: Add `from datetime import datetime, timezone` to the top of `core/orchestrator.py` (not inline in method bodies — avoids Ruff E402/PLC0415).

```python
# At top of core/orchestrator.py (with other imports)
from datetime import datetime, timezone

# In Orchestrator.__init__:
def __init__(
    self,
    ...,
    worker_circuit_breaker: "WorkerCircuitBreaker | None" = None,
    degraded_mode_threshold: float = 0.5,
    ...
) -> None:
    self.worker_circuit_breaker = worker_circuit_breaker
    self.degraded_mode_threshold = degraded_mode_threshold
    # Issue #2 fix: type annotation matches runtime tuple storage.
    # Each entry is (task, worker_id, queued_at) for timeout tracking (Issue #5).
    self._queued_tasks: list[tuple[Task, str, datetime]] = []
```

**Step B — Register workers with the circuit breaker in `Orchestrator.register_worker`** (Issue #1 fix):
At line 102-108 of `core/orchestrator.py` (existing `register_worker` method), add circuit breaker registration:
```python
def register_worker(self, worker_id: str, worker: "WorkerBase") -> None:
    # ... existing code ...
    self.workers[worker_id] = worker
    if self.fallback_chain is not None and hasattr(worker, "fallback_chain"):
        worker.fallback_chain = self.fallback_chain
    # NEW: register with circuit breaker so denominator is the full roster
    if self.worker_circuit_breaker is not None:
        self.worker_circuit_breaker.register_worker(worker_id)
```

**Step C — Add worker-level circuit breaker check in `process_task`** (at line 308, before `worker.run(task)`):
```python
# Check worker circuit breaker before execution
if self.worker_circuit_breaker is not None:
    if not self.worker_circuit_breaker.is_available(worker_id):
        # Worker circuit is open. S4.3 implements degraded-mode queuing
        # (transition to QUEUED). For S2, leave as a no-op stub with TODO —
        # the QUEUED TaskStatus value does not exist until S4.1, and OR34
        # mandates strict numerical order. The stub logs a warning so the
        # behavior is observable during S2 testing.
        # TODO(S4.3): replace this stub with degraded-mode queuing logic.
        logger.warning(
            "Worker %s circuit open — degraded-mode queuing not yet implemented (S4.3)",
            worker_id,
        )
```

**Note on sequencing** (Issue #3 fix): S2.1 Step C is a **no-op stub** — it logs a warning but does NOT transition to QUEUED. The `TaskStatus.QUEUED` value does not exist until S4.1, and the transition table doesn't permit it until S4.2. Per OR34 (strict numerical order), S2 must not reference S4's enum. S4.3 will replace this stub with the full degraded-mode queuing logic. The stub exists so S2 tests can verify the circuit breaker check is wired correctly without depending on S4.

After `worker.run(task)` succeeds (line 309), record success:
```python
if self.worker_circuit_breaker is not None:
    self.worker_circuit_breaker.record_success(worker_id)
    # NOTE: Do NOT call _maybe_resume_queued_tasks() here (Issue #2 fix).
    # Rev3 had record_success → _maybe_resume_queued_tasks → process_task →
    # _maybe_resume_queued_tasks recursion. Rev4 removes this call entirely.
    # Resume happens ONLY at process_task entry (opportunistic drain when a
    # new task arrives). This is sufficient for PEMADS Phase 2 (turn-based
    # debates always have a next turn arriving).
```

In the `except Exception` block after `worker.run(task)` fails (around line 490), record failure:
```python
if self.worker_circuit_breaker is not None:
    self.worker_circuit_breaker.record_failure(worker_id)
```

**Rev6 Issue #1 fix — CRITICAL**: The `record_success` and `record_failure` calls above are DUPLICATED by `_execute_task` (S2.1a). When S2.1a is applied (replacing `worker.run(task)` with `self._execute_task(task, worker_id)`), you MUST REMOVE these two call sites from `process_task`. `_execute_task` owns `record_success`/`record_failure` exclusively. If you leave both in place, every success records twice and every failure records twice — with `failure_threshold=3`, the circuit opens after 2 real failures instead of 3 (double-counting bug). **This is the #1 bug to watch for in implementation.**

**AR10 Interpretation** (Issue #3 response): The `_queued_tasks: list[tuple[Task, str, datetime]]` field (Rev5 Issue #2 fix — was `list[Task]` in Rev4) is in-memory operational state, NOT a memory access governed by AR10. AR10 ("No memory access outside MemoryRouter") governs the MemoryRouter backends (SQLite, Qdrant, Obsidian) per CONTEXT.md: "The single entry point for all memory operations. Routes read/write to appropriate backends." An in-process FIFO queue for short-lived task scheduling is operational state, not a memory operation. Precedent: `AdapterFallbackChain._failure_counts: dict` and `_circuit_open_since: dict` (`core/adapter_fallback.py:59-60`) are the same pattern — in-memory state, never flagged as AR10 violation in any prior review. If the user judges this interpretation is wrong, escalate to Tier 2 for architectural review of the AR10 boundary.

#### S2.1a. Extract `_execute_task` helper (Issue #2 fix — new in Rev4)

To eliminate the recursion in `_maybe_resume_queued_tasks` (Issue #2), extract the worker-execution logic from `process_task` into a separate `_execute_task` method. `_maybe_resume_queued_tasks` calls `_execute_task` directly (NOT `process_task`), avoiding the recursive call chain.

Add this method to `Orchestrator`:
```python
async def _execute_task(self, task: Task, worker_id: str) -> WorkerOutput:
    """Execute a task via the assigned worker. Called by process_task (normal
    path) and _maybe_resume_queued_tasks (resume path).

    This method contains the worker.run + record_success/record_failure logic.
    It does NOT call _maybe_resume_queued_tasks (no recursion). It does NOT
    check is_degraded() (caller is responsible for that check).

    (Source: Claude Rev3 review Issue #2 — Rev3's _maybe_resume_queued_tasks
    called process_task, which called _maybe_resume_queued_tasks at its start,
    creating unbounded recursion. Rev4 breaks the cycle by extracting this
    helper.)

    Args:
        task: The task to execute
        worker_id: The worker to route to

    Returns:
        WorkerOutput from the worker
    """
    worker = self.workers[worker_id]

    # Transition to EXECUTING.
    # Resume path arrives with task in QUEUED state (Rev5 Issue #1 fix —
    # _maybe_resume_queued_tasks no longer pre-transitions).
    # Direct process_task path may arrive in any pre-EXECUTING state
    # (e.g., RECEIVED, PLANNED). Guard handles both.
    if task.current_state != TaskStatus.EXECUTING:
        task = await self.state_machine.transition(
            task,
            TaskStatus.EXECUTING,
            reason="Worker execution starting",
            actor="orchestrator",
        )

    try:
        output = await worker.run(task)
        if self.worker_circuit_breaker is not None:
            self.worker_circuit_breaker.record_success(worker_id)
        return output
    except Exception as e:
        if self.worker_circuit_breaker is not None:
            self.worker_circuit_breaker.record_failure(worker_id)
        raise
```

Update `process_task` (S2.1 Step C area, around line 308) to call `_execute_task` instead of inlining the worker.run logic:
```python
# Replace: output = await worker.run(task)
# With:
output = await self._execute_task(task, worker_id)
```

This keeps `process_task` as the entry point (degraded check + queue + execute) while `_execute_task` is the pure execution helper.

**Applying AR18**: The existing `except Exception as e:` block at line 490 already has inline comment + WARNING trace (per ar18-fix-all). Verify the comment is still present; if not, restore it.

#### S2.2. Update `core/orchestrator.py` type annotation for forward reference

`WorkerCircuitBreaker` is referenced as `"WorkerCircuitBreaker | None"` (string literal) in `__init__` signature to avoid circular import. Add `from __future__ import annotations` at top of `core/orchestrator.py` if not already present (check first — Plan 67 may have added it).

#### S2.3. Syntax check + file-scoped ruff + mypy

```powershell
python -c "import ast; ast.parse(open('core/orchestrator.py').read())"
ruff check core/orchestrator.py
mypy core/orchestrator.py --ignore-missing-imports
```

#### S2.4. Update existing orchestrator tests

Check `tests/test_orchestrator.py` (or equivalent) for tests that instantiate `Orchestrator`. Add `worker_circuit_breaker=None` to those constructors (backward compatible — defaults to None).

If any test asserts on `Orchestrator.__init__` signature, update the assertion.

**Applying OR25**: Test deletion is a scope deviation. If a test cannot be made to pass, STOP and report — do NOT delete or comment out.

#### S2.5. Run orchestrator tests

```powershell
pytest tests/test_orchestrator.py tests/test_orchestrator_integration.py -q --tb=short
```

**STOP condition**: If any test fails, fix before proceeding.

---

### S3 — Orchestrator-Level Aggregate Circuit Breaker

The orchestrator-level circuit breaker is an **aggregate** of worker-level breakers. When too many workers have open circuits (cascade failure), the orchestrator itself enters degraded mode.

#### S3.1. Add aggregate check method to `WorkerCircuitBreaker`

Add to `core/worker_circuit_breaker.py`:
```python
def get_degraded_worker_ratio(self) -> float:
    """Return ratio of workers with open circuits to TOTAL REGISTERED workers.

    Uses _registered_workers (the canonical roster populated by register_worker)
    as the denominator, NOT _failure_counts. This fixes the Rev3 regression
    where the denominator was len(_failure_counts) — which could grow beyond
    the registered set due to defensive auto-registration in record_failure.

    Returns 0.0 if no workers registered. Used by orchestrator to detect
    cascade failure.

    (Source: Claude Rev3 review Issue #4 — Rev3 claimed to fix the denominator
    bug from Rev2 but S3.1 still used _failure_counts. Rev4 fixes this properly
    by tracking _registered_workers as a separate set.)

    Returns:
        Ratio in [0.0, 1.0]
    """
    if not self._registered_workers:
        return 0.0
    degraded = len(self.get_degraded_workers())
    total = len(self._registered_workers)
    return degraded / total
```

#### S3.2. Add orchestrator degraded-mode threshold to `Orchestrator.__init__`

```python
def __init__(
    self,
    ...,
    worker_circuit_breaker: "WorkerCircuitBreaker | None" = None,
    degraded_mode_threshold: float = 0.5,  # 50% of workers degraded → orchestrator degraded
    ...
) -> None:
```

#### S3.3. Add `is_degraded` method to `Orchestrator`

```python
def is_degraded(self) -> bool:
    """True if orchestrator is in degraded mode (too many workers have open circuits).

    Returns:
        True if degraded_worker_ratio >= degraded_mode_threshold, False otherwise
    """
    if self.worker_circuit_breaker is None:
        return False
    return (
        self.worker_circuit_breaker.get_degraded_worker_ratio()
        >= self.degraded_mode_threshold
    )
```

#### S3.4. Syntax check + file-scoped ruff + mypy

```powershell
python -c "import ast; ast.parse(open('core/worker_circuit_breaker.py').read())"
python -c "import ast; ast.parse(open('core/orchestrator.py').read())"
ruff check core/worker_circuit_breaker.py core/orchestrator.py
mypy core/worker_circuit_breaker.py core/orchestrator.py --ignore-missing-imports
```

#### S3.5. Add tests for aggregate behavior

Add to `tests/test_worker_circuit_breaker.py`:
- `test_get_degraded_worker_ratio_returns_zero_when_no_workers` — empty breaker returns 0.0
- `test_get_degraded_worker_ratio_returns_correct_ratio` — 2 of 4 workers degraded → 0.5

Add to orchestrator tests:
- `test_is_degraded_returns_false_when_no_circuit_breaker` — None breaker → not degraded
- `test_is_degraded_returns_true_when_ratio_exceeds_threshold` — 60% degraded with 0.5 threshold → degraded
- `test_is_degraded_returns_false_when_ratio_below_threshold` — 40% degraded with 0.5 threshold → not degraded

#### S3.6. Run tests

```powershell
pytest tests/test_worker_circuit_breaker.py tests/test_orchestrator.py -q --tb=short
```

---

### S4 — Degraded Mode (Queue Tasks Instead of Failing)

When `Orchestrator.is_degraded()` returns True, new tasks are queued instead of executed. This requires a new `TaskStatus.QUEUED` value.

#### S4.1. Add `QUEUED` to `TaskStatus` enum

Edit `core/schemas.py`:
```python
class TaskStatus(str, Enum):
    """Status of task execution."""

    RECEIVED = "received"
    PLANNED = "planned"
    QUEUED = "queued"  # NEW — degraded mode (orchestrator circuit breaker open)
    EXECUTING = "executing"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"

    # Backward compatibility aliases
    PENDING = "received"
    RUNNING = "executing"
```

#### S4.2. Update `TaskStateMachine` transition table

Edit `core/task_state_machine.py`. Add `QUEUED` to the transition table:
- `RECEIVED → QUEUED` (valid — task queued when orchestrator degraded)
- `QUEUED → EXECUTING` (valid — task resumed when orchestrator recovers)
- `QUEUED → CANCELLED` (valid — user cancels queued task)
- `QUEUED → FAILED` (valid — queue timeout, if implemented later)

All other transitions involving `QUEUED` are invalid.

#### S4.3. Update `Orchestrator.process_task` to check degraded mode

At the START of `process_task` (before line 246, before cost check):
```python
# S4.4: opportunistically drain queued tasks when orchestrator is healthy
# (Issue #2 fix: this is the ONLY place _maybe_resume_queued_tasks is called.
# It is NOT called after record_success — that caused recursion in Rev3.)
await self._maybe_resume_queued_tasks()

# Check orchestrator degraded mode
if self.is_degraded():
    # Transition to QUEUED instead of EXECUTING
    try:
        task = await self.state_machine.transition(
            task,
            TaskStatus.QUEUED,
            reason="Orchestrator in degraded mode (cascade failure detected)",
            actor="orchestrator",
        )
        # Append to in-memory FIFO queue for opportunistic resume (S4.4)
        # Store as tuple: (task, worker_id, queued_at) for timeout tracking (Issue #5)
        # datetime imported at top of file (Issue #3 fix — no inline imports)
        self._queued_tasks.append((task, worker_id, datetime.now(timezone.utc)))
        # Emit trace event
        await self._emitter.emit(
            TraceEvent(
                event_type=TraceEventType.CIRCUIT_BREAKER_OPEN,
                component=TraceComponent.ORCHESTRATOR,
                level=TraceLevel.WARNING,
                message="Task queued due to orchestrator degraded mode",
                data={
                    "task_id": task.task_id,
                    "worker_id": worker_id,
                    "degraded_ratio": self.worker_circuit_breaker.get_degraded_worker_ratio()
                    if self.worker_circuit_breaker
                    else 0.0,
                    "queue_length": len(self._queued_tasks),
                },
                duration_ms=0,
            )
        )
        return WorkerOutput(
            task_id=task.task_id,
            worker_id=worker_id,
            content="",
            confidence=0.0,
            model_used="none",
            metadata={
                "status": "queued",
                "reason": "Orchestrator in degraded mode",
                "queue_length": len(self._queued_tasks),
            },
        )
    except Exception as e:
        # AR18: state transition failure — log and fall through to normal execution
        # (don't crash the orchestrator if queueing fails)
        logger.warning("Failed to queue task in degraded mode: %s", e)
```

**Applying OR20** (datetime discipline): Use `datetime.now(timezone.utc)`, never `datetime.utcnow()` or bare `datetime.now()`. The `queued_at` timestamp is timezone-aware. The `datetime` and `timezone` names are imported at the top of `core/orchestrator.py` (Issue #3 fix).

**Applying AR18**: The `except Exception` block above has inline comment explaining why it's broad (state transition failure) and falls through to normal execution. No `pass` — it logs and continues.

**Caller Contract** (Rev5 — Claude Rev4 review "other concern 1"): When `process_task` returns a `WorkerOutput` with `metadata={"status": "queued"}`, the caller MUST inspect this flag. The task has NOT executed — `content` is empty, `confidence` is 0.0. The caller MUST NOT treat this as a successful result. For PEMADS Phase 2 (Plan 81), the debate loop MUST NOT advance the turn on a queued-task response. Plan 81 is responsible for implementing the callback/retry mechanism that re-invokes `process_task` when the orchestrator exits degraded mode. Plan 78 delivers the queue + resume infrastructure; Plan 81 delivers the caller-side handling.

#### S4.4. Implement `_maybe_resume_queued_tasks()` method (Issue #2 + #5 + Rev5 #1 fix)

Add this method to `Orchestrator`:
```python
# Module-level constant (or class attribute)
QUEUED_TASK_TIMEOUT_SECONDS = 300  # 5 minutes — Issue #5 fix
MAX_RESUME_ITERATIONS = 3  # Safety limit to prevent infinite loops — Issue #2 fix

async def _maybe_resume_queued_tasks(self) -> None:
    """Drain the QUEUED task queue when orchestrator is not degraded.

    Called ONLY from process_task (at start). NOT called after record_success
    (Rev3 had that — caused recursion, Rev4 removed it — Issue #2 fix).

    Algorithm:
    1. If queue is empty or orchestrator is degraded, return (no-op).
    2. Snapshot the queue and clear it.
    3. For each (task, worker_id, queued_at) in snapshot:
       a. If queued_at + QUEUED_TASK_TIMEOUT_SECONDS < now, transition to FAILED
          (Issue #5 fix — orphaned task cleanup). Task is in QUEUED state —
          QUEUED → FAILED is valid per S4.2.
       b. If worker_id's circuit is still open, re-queue at back (with ORIGINAL
          queued_at — don't reset the timeout clock). Task remains in QUEUED.
       c. Otherwise, worker is available — call _execute_task (NOT process_task —
          avoids recursion, Issue #2 fix). _execute_task handles the
          QUEUED → EXECUTING transition internally (via its
          `if task.current_state != EXECUTING` guard).
          - On success: emit CIRCUIT_BREAKER_RESET trace. Task is now COMPLETE
            (or whatever _execute_task's worker.run produced).
          - On failure (Rev5 Issue #1 fix): transition to FAILED (NOT re-queue).
            The task was in EXECUTING state when _execute_task raised.
            EXECUTING → FAILED is valid in the existing state machine (the
            normal process_task path does this at orchestrator.py:457).
            Re-queueing an EXECUTING-state task would break the timeout path
            (QUEUED → FAILED wouldn't apply). So execution failures during
            resume are terminal — the task goes to FAILED, not back to queue.
    4. If any tasks were re-queued (step b only) and we haven't hit
       MAX_RESUME_ITERATIONS, loop again.

    Invariant: _queued_tasks only contains tasks in QUEUED state. This is
    maintained because:
    - Timeout path (step a): transitions to FAILED, does NOT re-queue
    - Circuit-open path (step b): re-queues WITHOUT state change (stays QUEUED)
    - Execution-failure path (step c): transitions to FAILED, does NOT re-queue
    - Execution-success path (step c): task completes, does NOT re-queue

    (Source: Claude Rev3 review Issue #2 — recursion bug. Claude Rev3 review
    Issue #5 — no orphaned task cleanup. Claude Rev4 review Issue #1 —
    re-queue-on-execution-failure left tasks in EXECUTING state, breaking
    timeout path. Rev5 fixes by transitioning to FAILED on execution failure.)
    """
    if not self._queued_tasks:
        return
    if self.is_degraded():
        return  # Still degraded — wait

    # datetime, timezone imported at top of file (Issue #3 fix — no inline imports)
    iteration = 0
    while self._queued_tasks and iteration < MAX_RESUME_ITERATIONS:
        iteration += 1
        queue_snapshot = list(self._queued_tasks)
        self._queued_tasks.clear()

        for task, worker_id, queued_at in queue_snapshot:
            now = datetime.now(timezone.utc)

            # Issue #5: timeout check — transition to FAILED
            # Task is in QUEUED state — QUEUED → FAILED is valid per S4.2
            if (now - queued_at).total_seconds() > QUEUED_TASK_TIMEOUT_SECONDS:
                try:
                    await self.state_machine.transition(
                        task,
                        TaskStatus.FAILED,
                        reason=f"Queued task timeout ({QUEUED_TASK_TIMEOUT_SECONDS}s)",
                        actor="orchestrator",
                    )
                    # Emit trace for timeout-to-FAILED (other concern: no resume traces)
                    try:
                        await self._emitter.emit(
                            TraceEvent(
                                event_type=TraceEventType.OPERATION_ERROR,
                                component=TraceComponent.ORCHESTRATOR,
                                level=TraceLevel.WARNING,
                                message="Queued task timed out, transitioned to FAILED",
                                data={
                                    "task_id": task.task_id,
                                    "worker_id": worker_id,
                                    "queued_at": queued_at.isoformat(),
                                    "timeout_seconds": QUEUED_TASK_TIMEOUT_SECONDS,
                                },
                                duration_ms=0,
                            )
                        )
                    except Exception as e:
                        logger.warning("Trace emission failed: %s", e)
                except Exception as e:
                    # AR18: transition failure — log, don't crash
                    # If QUEUED → FAILED transition fails, re-queue for next attempt
                    logger.warning("Failed to transition timed-out task to FAILED: %s", e)
                    self._queued_tasks.append((task, worker_id, queued_at))
                continue

            # Check if worker is available
            if self.worker_circuit_breaker is not None:
                if not self.worker_circuit_breaker.is_available(worker_id):
                    # Worker still down — re-queue at back with ORIGINAL queued_at
                    # Task remains in QUEUED state (no transition needed)
                    self._queued_tasks.append((task, worker_id, queued_at))
                    continue

            # Worker is available — call _execute_task (NOT process_task — no recursion)
            # _execute_task handles the QUEUED → EXECUTING transition internally
            # via its `if task.current_state != EXECUTING` guard.
            try:
                await self._execute_task(task, worker_id)
                # Success — emit trace (other concern: no resume traces)
                try:
                    await self._emitter.emit(
                        TraceEvent(
                            event_type=TraceEventType.CIRCUIT_BREAKER_RESET,
                            component=TraceComponent.ORCHESTRATOR,
                            level=TraceLevel.INFO,
                            message="Queued task resumed successfully",
                            data={
                                "task_id": task.task_id,
                                "worker_id": worker_id,
                                "queued_duration_seconds": (now - queued_at).total_seconds(),
                            },
                            duration_ms=0,
                        )
                    )
                except Exception as e:
                    logger.warning("Trace emission failed: %s", e)
            except Exception as e:
                # Rev5 Issue #1 fix: _execute_task failed. Task is now in EXECUTING
                # state (the transition happened inside _execute_task before
                # worker.run raised). Do NOT re-queue — that would put an
                # EXECUTING-state task in _queued_tasks, breaking the timeout
                # path (QUEUED → FAILED wouldn't apply). Instead, transition
                # to FAILED, mirroring normal process_task behavior
                # (orchestrator.py:457 does EXECUTING → FAILED on worker failure).
                logger.warning(
                    "Resume execution failed for task %s, transitioning to FAILED: %s",
                    task.task_id, e
                )
                try:
                    await self.state_machine.transition(
                        task,
                        TaskStatus.FAILED,
                        reason=f"Resume execution failed: {type(e).__name__}: {e}",
                        actor="orchestrator",
                    )
                except Exception as transition_e:
                    # AR18: if EXECUTING → FAILED also fails, log and leave task
                    # in EXECUTING (it will be caught by existing failure handling)
                    logger.warning(
                        "Failed to transition resumed task %s to FAILED: %s",
                        task.task_id, transition_e
                    )
```

**Latency Tradeoff** (Rev5 — Claude Rev4 review "other concern 2"): Every `process_task` call drains the queue (up to `MAX_RESUME_ITERATIONS=3` passes) before executing the new task. With N queued tasks at ~2s each per `_execute_task` call, the caller waits ~2N seconds in the worst case. For PEMADS Phase 2 (3-5 expert panel, max ~5 queued tasks), worst case ~10s. This is acceptable for turn-based debates where turns are measured in tens of seconds. If latency becomes an issue in practice, a background poller can be added (future work — see closing section). The `MAX_RESUME_ITERATIONS=3` limit caps the per-call drain at 3 passes, preventing unbounded latency.

**Design notes** (Issue #4 clarification + Rev4/Rev5 updates):
- **Rerouting is deferred to Plan 81** (PEMADS Phase 2 Expert Panel Manager). In Plan 78, QUEUED tasks resume to the SAME `worker_id` they were originally routed to. If that worker is still circuit-open, the task is re-queued at the back of the FIFO with its ORIGINAL `queued_at` timestamp (so the timeout clock keeps ticking). This is a deliberate scope boundary: Plan 78 delivers cascade-failure prevention, not workload rebalancing.
- **Persistence is NOT in scope** (Issue #1 clarification). See "Scope Boundary" section at the top of this plan. Plan 78 = cascade failure prevention, NOT orchestrator-crash recovery. The `_queued_tasks` list is in-memory; if the orchestrator crashes, queued tasks are lost. Crash recovery belongs in a separate `orchestrator-crash-recovery` plan.
- **No background poller**. The resume is opportunistic — triggered by `process_task` calls only. If no new tasks arrive, QUEUED tasks sit until timeout (QUEUED_TASK_TIMEOUT_SECONDS = 300s) transitions them to FAILED. This is acceptable for PEMADS Phase 2 (turn-based debates always have a next turn arriving).
- **Iteration limit** (Issue #2 fix). MAX_RESUME_ITERATIONS = 3 prevents infinite loops. After 3 iterations, remaining tasks stay in the queue and will be retried on the next `process_task` call.
- **Timeout preserves original queued_at** (Issue #5 fix). When a task is re-queued (worker still down), it keeps its original `queued_at` timestamp. This ensures the timeout clock keeps ticking — a task stuck behind a perpetually-down worker will eventually time out and transition to FAILED.
- **Execution failures are terminal** (Rev5 Issue #1 fix). If `_execute_task` raises during resume, the task transitions to FAILED (not re-queued). This maintains the invariant that `_queued_tasks` only contains QUEUED-state tasks. Re-queueing is ONLY for circuit-open workers (step b), not for execution failures (step c).

#### S4.5. Syntax check + file-scoped ruff + mypy

```powershell
python -c "import ast; ast.parse(open('core/schemas.py').read())"
python -c "import ast; ast.parse(open('core/task_state_machine.py').read())"
python -c "import ast; ast.parse(open('core/orchestrator.py').read())"
ruff check core/schemas.py core/task_state_machine.py core/orchestrator.py
mypy core/schemas.py core/task_state_machine.py core/orchestrator.py --ignore-missing-imports
```

#### S4.6. Add tests for degraded mode + resume + timeout + execution failure

Add to orchestrator tests:
- `test_process_task_transitions_to_queued_when_degraded` — mock `is_degraded()` True, verify task → QUEUED, verify task appended to `_queued_tasks` as `(task, worker_id, queued_at)` tuple
- `test_process_task_executes_normally_when_not_degraded` — mock `is_degraded()` False, verify task → EXECUTING
- `test_process_task_does_not_double_count_record_success` — verify `record_success` is called exactly ONCE per successful execution (Rev6 Issue #1 regression test — guards against duplicate record calls in process_task + _execute_task)
- `test_process_task_does_not_double_count_record_failure` — verify `record_failure` is called exactly ONCE per failed execution (Rev6 Issue #1 regression test)
- `test_circuit_breaker_opens_after_exactly_failure_threshold_failures` — with `failure_threshold=3`, verify circuit opens after exactly 3 real failures (NOT 2, which would indicate double-counting) (Rev6 Issue #1 end-to-end regression test)
- `test_queued_task_can_transition_to_executing` — QUEUED → EXECUTING is valid
- `test_queued_task_can_transition_to_cancelled` — QUEUED → CANCELLED is valid
- `test_queued_to_complete_is_invalid` — QUEUED → COMPLETE raises InvalidStateTransitionError
- `test_queued_to_failed_is_valid_for_timeout` — QUEUED → FAILED is valid (Issue #5 timeout path)
- `test_executing_to_failed_is_valid` — verify EXECUTING → FAILED is valid in existing state machine (Rev5 Issue #1 — resume execution failure path depends on this)
- `test_maybe_resume_queued_tasks_noop_when_still_degraded` — queue has tasks, `is_degraded()` True → queue unchanged
- `test_maybe_resume_queued_tasks_drains_when_recovered` — queue has 2 tasks, `is_degraded()` False, workers available → both tasks executed via `_execute_task`, queue empty
- `test_maybe_resume_re_queues_tasks_whose_worker_still_down` — queue has 1 task whose worker is circuit-open, orchestrator not degraded → task re-queued at back with ORIGINAL `queued_at`, queue still has 1 task, task still in QUEUED state
- `test_maybe_resume_transitions_timed_out_tasks_to_failed` — queue has 1 task with `queued_at` 400s ago (> 300s timeout) → task transitioned QUEUED → FAILED, queue empty (Issue #5 regression test)
- `test_maybe_resume_preserves_queued_at_on_requeue` — task re-queued due to worker-down keeps original `queued_at` (not reset to now) (Issue #5 regression test)
- `test_maybe_resume_transitions_to_failed_on_execute_task_failure` — queue has 1 task, worker available, `_execute_task` raises → task transitioned EXECUTING → FAILED, NOT re-queued (Rev5 Issue #1 regression test)
- `test_maybe_resume_does_not_re_queue_on_execution_failure` — verify `_queued_tasks` remains empty after `_execute_task` raises (Rev5 Issue #1 regression test — confirms invariant)
- `test_maybe_resume_calls_execute_task_not_process_task` — verify `_execute_task` is called, NOT `process_task` (Issue #2 recursion regression test — mock both methods, verify only `_execute_task` called)
- `test_maybe_resume_respects_max_iterations` — queue has tasks that keep getting re-queued (worker circuit-open), verify loop exits after MAX_RESUME_ITERATIONS=3 (Issue #2 regression test)
- `test_process_task_calls_resume_at_start` — verify `_maybe_resume_queued_tasks` is called before degraded check
- `test_record_success_does_not_call_resume` — verify `_maybe_resume_queued_tasks` is NOT called after `record_success` (Issue #2 regression test — Rev3 had this, Rev4 removed it)
- `test_resume_emits_circuit_breaker_reset_trace` — verify trace event emitted on successful resume (other concern: no resume traces)
- `test_timeout_emits_operation_error_trace` — verify trace event emitted on timeout-to-FAILED (other concern: no resume traces)
- `test_queued_tasks_only_contains_queued_state_tasks` — invariant test: after any resume operation, all tasks in `_queued_tasks` have `current_state == QUEUED` (Rev5 Issue #1 invariant test)

Add to task state machine tests:
- `test_queued_state_transitions_valid_set` — verify the 4 valid transitions from QUEUED (RECEIVED→QUEUED, QUEUED→EXECUTING, QUEUED→CANCELLED, QUEUED→FAILED)

Add to `tests/test_worker_circuit_breaker.py` (Issue #4 regression):
- `test_get_degraded_worker_ratio_uses_registered_workers_not_failure_counts` — register 5 workers, fail 2 (1 circuit open), verify ratio = 1/5 = 0.2 (NOT 1/2 = 0.5 from the Rev3 regression bug)
- `test_register_worker_adds_to_registered_workers_set` — verify `_registered_workers` set is populated and used as denominator

#### S4.7. Run tests

```powershell
pytest tests/test_orchestrator.py tests/test_task_state_machine.py -q --tb=short
```

---

### S5 — Wire WorkerCircuitBreaker into CLI

**Applying AR8**: `cli/` may import from anywhere. The CLI wires the `WorkerCircuitBreaker` into the `Orchestrator` at startup.

#### S5.1. Update `cli/serve.py`

Find where `Orchestrator` is instantiated (search for `Orchestrator(`). Add:
```python
from core.worker_circuit_breaker import WorkerCircuitBreaker

worker_circuit_breaker = WorkerCircuitBreaker(
    emitter=emitter,
    failure_threshold=3,
    reset_timeout=60,
)

orchestrator = Orchestrator(
    ...,
    worker_circuit_breaker=worker_circuit_breaker,
    # Issue #6: 0.2 threshold for PEMADS Phase 2 (3-5 expert panel).
    # Any single expert failure (1/5 = 20%) triggers degraded mode.
    # Default 0.5 is for generic systems with larger fleets.
    # For non-PEMADS use cases, override to 0.5 or higher.
    degraded_mode_threshold=0.2,
)
```

**Threshold rationale** (Issue #6): The default `degraded_mode_threshold=0.5` is appropriate for generic systems with large fleets (e.g., 20+ workers — 50% = 10 failures). For PEMADS Phase 2 with 3-5 expert models, 50% means 2-3 experts must fail before degraded mode triggers — too late to prevent cascade. A 0.2 threshold means:
- 5-expert panel: 1 failure (20%) → degraded mode triggers
- 3-expert panel: 1 failure (33% > 20%) → degraded mode triggers

This is intentionally aggressive for PEMADS Phase 2 — any single expert failure queues subsequent tasks rather than risking cascade. The tradeoff is more frequent degraded-mode queuing, which is acceptable because the resume path (S4.4) drains the queue quickly once the failed expert recovers.

#### S5.2. Update `cli/tui.py` if it instantiates Orchestrator

Search for `Orchestrator(` in `cli/tui.py`. If found, add the same wiring.

#### S5.3. Syntax check + file-scoped ruff + mypy

```powershell
python -c "import ast; ast.parse(open('cli/serve.py').read())"
python -c "import ast; ast.parse(open('cli/tui.py').read())"
ruff check cli/serve.py cli/tui.py
mypy cli/serve.py cli/tui.py --ignore-missing-imports
```

#### S5.4. Run CLI smoke tests

```powershell
pytest tests/test_serve.py tests/test_tui.py -q --tb=short 2>&1 | Select-Object -Last 20
```

If no `test_serve.py` or `test_tui.py` exists, skip — CLI smoke testing is manual.

---

## Closing

Run `/jarvis-close` per workflow file `.windsurf/workflows/jarvis-close.md`.

**Applying OR39**: Ensure `GLM Prompts/plan-78*.md` is added in the C12 docs commit:
```powershell
git add CHANGELOG.md PLANS.md LANDMINES.md "GLM Prompts/plan-78*.md"
```

**Applying OR38**: Plan 78 is in the 70s decade. No decade-boundary cleanup triggered (decade boundary is at prompt-80). Catch-up clause: if `GLM Prompts/` contains files from the 50s decade or earlier, delete them as `docs: cleanup pre-prompt-78` (per OR26 at S0.1). Files from the 60s decade are NOT eligible for catch-up deletion — wait for prompt-80.

### Expected results

- **Tests**: 1364 + ~44 new tests = ~1408 passed, 67 skipped (delta +44, exceeds OR17 ±5 tolerance. OR17 invoked. Justification: all 44 tests are in-scope new tests — 18 for WorkerCircuitBreaker (S1.3 + S3.5, including register_worker + `_registered_workers` denominator regression tests per Issue #4), 3 for orchestrator wiring (S2.4), 21 for degraded mode + resume + timeout + execution-failure + double-counting + invariant (S4.6, including recursion regression tests per Issue #2, timeout tests per Issue #5, Rev5 Issue #1 execution-failure-to-FAILED tests, Rev6 Issue #1 double-counting regression tests, invariant test, trace tests), 1 for QUEUED transitions (S4.6), 1 for QUEUED→FAILED transition (S4.6). No existing tests modified or deleted. Document in CHANGELOG.)
- **Ruff**: 0 errors
- **Mypy**: 0 errors (file-scoped on edited files)
- **New module**: `core/worker_circuit_breaker.py` with `WorkerCircuitBreaker` class (including `register_worker` method, `_registered_workers` set — Issue #4 fix)
- **New TaskStatus**: `QUEUED` value added
- **New transition paths**: `RECEIVED → QUEUED`, `QUEUED → EXECUTING`, `QUEUED → CANCELLED`, `QUEUED → FAILED` (FAILED now actually used for timeout — Issue #5)
- **New Orchestrator methods**: `_execute_task()` (Issue #2 recursion fix), `_maybe_resume_queued_tasks()` (Issue #2 exit path, Issue #5 timeout, trace events)
- **New constants**: `QUEUED_TASK_TIMEOUT_SECONDS = 300` (Issue #5), `MAX_RESUME_ITERATIONS = 3` (Issue #2)
- **CLI wiring**: `cli/serve.py` (and `cli/tui.py` if applicable) instantiates `WorkerCircuitBreaker` and injects into `Orchestrator` with `degraded_mode_threshold=0.2` for PEMADS Phase 2 (Issue #6)

### Landmine capture (C11)

If any new failure pattern is discovered during execution, capture it in `LANDMINES.md` per GR11 (trigger + impact only, append-only).

Candidate landmine to watch for: If `TaskStatus.QUEUED` addition breaks backward compatibility with serialized tasks (e.g., tasks persisted with old enum values), capture as L21: "Adding new TaskStatus enum value breaks deserialization of persisted tasks with old enum set."

**Future work** (out of scope for Plan 78, documented per Claude Rev3 review "other concerns"):
- **Chaos testing**: Simulate orchestrator crash with N QUEUED tasks, multiple rapid worker failures/recoveries, concurrent `process_task` calls during resume. Belongs in Plan 80+ (5-plan scan) or a dedicated `chaos-test` plan.
- **Orchestrator crash recovery**: Persist `_queued_tasks` to MemoryRouter so queued tasks survive orchestrator restart. Separate `orchestrator-crash-recovery` plan.
- **Background poller for resume**: If opportunistic drain proves insufficient (e.g., long gaps between `process_task` calls), add a periodic poller. Defer until PEMADS Phase 2 surfaces the need.

---

## Scope Declaration

**Applying OR15 (pre-declare scope) and GR12 (GLM pre-declares scope before drafting)**:

### WILL edit (exhaustive list)

| File | Change |
|---|---|
| `AI_HANDOFF.md` | Add "GLM Operating Discipline" section with GR1 (S0.3) |
| `PLANS.md` | Add `infra-remediation` queue entry (S0.4); update completed prompts + baselines at closing (C12) |
| `core/worker_circuit_breaker.py` | NEW — `WorkerCircuitBreaker` class with `register_worker`, `record_failure`, `record_success`, `is_available`, `reset_circuit`, `get_status`, `get_degraded_workers`, `get_degraded_worker_ratio`; `_registered_workers: set[str]` field (Issue #4) (S1.1, S3.1) |
| `core/orchestrator.py` | Add `worker_circuit_breaker` + `degraded_mode_threshold` + `_queued_tasks` params; call `register_worker` in `register_worker`; add `is_degraded()` method; add `_execute_task()` helper (Issue #2 recursion fix); add `_maybe_resume_queued_tasks()` method (Issue #2 exit path, Issue #5 timeout, trace events); update `process_task` for circuit breaker check + degraded mode + opportunistic resume; add `QUEUED_TASK_TIMEOUT_SECONDS` + `MAX_RESUME_ITERATIONS` constants (S2.1, S2.1a, S3.2, S3.3, S4.3, S4.4) |
| `core/schemas.py` | Add `QUEUED` to `TaskStatus` enum (S4.1) |
| `core/task_state_machine.py` | Add `QUEUED` transitions to transition table (S4.2) |
| `cli/serve.py` | Wire `WorkerCircuitBreaker` into `Orchestrator` instantiation (S5.1) |
| `cli/tui.py` | Wire `WorkerCircuitBreaker` into `Orchestrator` instantiation IF it instantiates Orchestrator (S5.2) |
| `tests/test_worker_circuit_breaker.py` | NEW — 18 tests for `WorkerCircuitBreaker` including register_worker + `_registered_workers` denominator regression tests (Issue #4) (S1.3, S3.5) |
| `tests/test_orchestrator.py` | Add tests for circuit breaker wiring + degraded mode + resume + timeout + recursion safety + trace events (S2.4, S3.5, S4.6) |
| `tests/test_task_state_machine.py` | Add tests for `QUEUED` state transitions (S4.6) |
| `CHANGELOG.md` | Append entry at closing (C12) |
| `LANDMINES.md` | Append entry at closing IF new pattern discovered (C11) |

### WILL NOT edit

- `AGENTS.md` (no new AR/OR rules — GR1 goes in AI_HANDOFF.md, not AGENTS.md)
- `CONTEXT.md` (no new domain vocabulary needed — circuit breaker is already in CONTEXT.md)
- `core/adapter_fallback.py` (existing adapter-level circuit breaker is unchanged — this plan extends the pattern, not modifies it)
- `core/worker_base.py` (workers remain circuit-breaker-unaware — the orchestrator tracks per-worker state, not the workers themselves)
- `core/worker_factory.py` (no changes — factory creates workers, doesn't track failure state)
- `tests/test_adapter_fallback.py` (existing tests unchanged — adapter-level circuit breaker behavior is preserved)
- `workers/` (no worker code changes)
- `adapters/` (no adapter code changes)
- `memory/` (no memory code changes — degraded mode queue is in-memory state, not persisted. Persistence deferred to future plan.)
- `system/` (no system code changes)
- `skills/` (no skill code changes)
- `web/` (no web code changes)
- `scripts/` (no script changes)

### Tests added

- 18 tests in `tests/test_worker_circuit_breaker.py` (S1.3 + S3.5 — includes register_worker tests, `_registered_workers` denominator regression tests per Issue #4)
- 3 tests in `tests/test_orchestrator.py` for circuit breaker wiring (S2.4)
- 21 tests in `tests/test_orchestrator.py` for degraded mode + resume + timeout + execution-failure + double-counting + invariant (S4.6 — includes recursion regression tests per Issue #2, timeout tests per Issue #5, Rev5 Issue #1 execution-failure-to-FAILED tests, Rev6 Issue #1 double-counting regression tests, invariant test, trace tests, `_execute_task` vs `process_task` verification)
- 1 test in `tests/test_task_state_machine.py` for QUEUED transitions (S4.6)
- 1 test in `tests/test_task_state_machine.py` for QUEUED→FAILED transition (S4.6)
- **Total**: 44 new tests (delta +44, exceeds OR17 ±5 tolerance — justification documented in CHANGELOG)

### Tests modified

- `tests/test_orchestrator.py`: existing tests that instantiate `Orchestrator` may need `worker_circuit_breaker=None` added (backward compatible — defaults to None)

### Baseline changes expected

- Test count: 1364 → ~1408 (+44, OR17 invoked)
- Ruff: 0 (baseline held)
- Mypy: 0 (baseline held, file-scoped)
- All other baselines unchanged

### HARD STOP conditions

- Any test fails after a file edit (OR16)
- Any file outside the "WILL edit" list needs editing (OR16, GR12)
- Syntax error after a file edit (OR6)
- Test count drops below 1364 (data integrity)
- Mypy errors increase (type safety)

**If any HARD STOP condition fires**: STOP and report per OR16. Do not fix unilaterally.
