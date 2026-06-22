# Plan 37.6: TUI memory + cognition stack wiring (mirror of 35.6f for `cli/tui.py`)

> **Executor instructions**: This plan wires the cognition stack into `cli/tui.py` — the path users actually use when they run `jarvis` (no args) or `jarvis --rich`. Today the TUI constructs `Orchestrator(memory_router=None)` and `create_worker(..., memory_router=None)`, so every memory call throws AttributeError and gets silently swallowed by broad excepts. The user sees responses that look fine but has no idea memory is dead. This plan mirrors what prompt-35.6f did for `cli/serve.py`: construct the full cognition stack and pass a real `memory_router` to the orchestrator and worker. Plus 4 small hygiene fixes from prompt-37.5 that were skipped.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-37.5..HEAD -- cli/tui.py cli/main.py cli/rich_cli.py tests/test_main.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> If any of these files changed since prompt-37.5, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P1 (the path users actually use — without this, F6 fixes only help `jarvis serve`)
- **Effort**: M
- **Risk**: MED (touches the primary user entry point; if TUI breaks, users can't use Sovereign at all)
- **Depends on**: prompt-37.5 (commit `e02cb2a`, tag `prompt-37.5`)
- **Planned at**: commit `f9829db`, 2026-06-18
- **In scope**: 1 production file (`cli/tui.py`) + 1 new test file (`tests/test_tui.py`) + 2 documentation files (handoff + CHANGELOG)
- **Out of scope**: `cli/rich_cli.py` (separate path, separate plan if needed), `cli/main.py` (thin dispatcher), broad-except audit (Plan 38+), InputSanitiser wiring (Plan 41+)

## Why this matters

The handoff's "What works right now" section says `jarvis` (no args) "starts Textual TUI with one OllamaWorker registered. User can type queries, get responses from local Ollama." This is technically true but deeply misleading. Here's what actually happens when a user types a query in the TUI:

1. Textual UI dispatches command → `QueryHandler.execute()` at `core/handlers.py:439` constructs a Task
2. `QueryHandler` calls `self.orchestrator.route_task(task)` (line 504)
3. Orchestrator calls `memory_router.get_global_context(...)` → `AttributeError: 'NoneType' object has no attribute 'get_global_context'` → swallowed by `except Exception: pass` at orchestrator.py:401-402
4. Orchestrator routes to OllamaWorker
5. `WorkerBase.run()` calls `self.memory_router.fetch(task)` → `AttributeError: 'NoneType'...` → swallowed
6. Worker calls Ollama adapter, gets response
7. Response returned to user — looks fine, zero indication that memory is dead

Every query is stateless. No context is fetched before the call. No outcome is written after. The next query starts from a blank slate, every time, forever. This is the opposite of what the project's diagrams require (MEMORY lives outside the conversation, DISCOVERY reads from it, VERIFICATION writes to it, ITERATION reads from it again).

Meanwhile, `cli/serve.py` (the `jarvis serve` path) has had the full cognition stack wired since prompt-35.6f: RatingSystem, InstructionGenerator, InstructionVersionManager, OutputEvaluator, TraceOptimiser, OrchestratorImprovementLoop, WorkerFactory, ApprovalGate, EscalationEngine, AdapterFallbackChain, ApprovalTrustRegistry — all constructed, all passed real `memory_router`, all registered with each other. **The TUI has none of this.** It's a stripped-down shell that calls Ollama directly.

This plan mirrors 35.6f for the TUI. After it lands, `jarvis` (no args) and `jarvis serve` will have parity at the cognition-stack level.

## What's broken (verified against live repo at commit f9829db)

### A. `cli/tui.py` constructs orchestrator + worker with `memory_router=None`

**Current state** (verified at lines 276, 279, 375):
```python
# Line 276
self.orchestrator = Orchestrator(memory_router=None)

# Line 279
self.worker = create_worker("ollama", "llama3", memory_router=None)

# Line 375 (on adapter swap)
self.worker = create_worker(adapter_name, "llama3", memory_router=None)
```

A `memory_router` IS constructed at line 266, but only for `WorkerPersistence` — it's never passed to the orchestrator or worker. The orchestrator and worker get `None`.

### B. `cli/tui.py` constructs zero cognition components

Verified by grep — `cli/tui.py` does NOT construct: `ApprovalGate`, `EscalationEngine`, `AdapterFallbackChain`, `WorkerFactory`, `RatingSystem`, `InstructionGenerator`, `InstructionVersionManager`, `OutputEvaluator`, `TraceOptimiser`, `OrchestratorImprovementLoop`, `ApprovalTrustRegistry`, `InputSanitiser`, `TaskStateMachine`.

Compare to `cli/serve.py:38-164` which constructs all of these. The TUI has none of them. The orchestrator in the TUI has no approval gate, no escalation engine, no fallback chain, no improvement loop — nothing.

### C. No `tests/test_tui.py` exists

Verified: `ls tests/test_tui*` returns nothing. The TUI is completely untested. `tests/test_main.py` only tests the `serve` subcommand (2 tests). The TUI path has zero test coverage.

### D. 37.5 hygiene gaps (rolled in from verification)

Four small documentation/hygiene gaps from prompt-37.5 that should have been done but weren't:

**D1. Handoff F6 status is inconsistent.**
- Line 3 ("Last updated"): "Finished F6..."
- Line 58: "F6 — MemoryRouter call-signature mismatch (PARTIALLY FIXED)"
- Line 60: "However, `system/trajectory_exporter.py`... still has mypy errors"
- Line 62: "Remaining work: Fix trajectory_exporter.py pattern... Also 69 test failures due to mock implementation details"

The "Remaining work" line references the 69 test failures (fixed in 37.1) and trajectory_exporter (now stubbed with Plan 45 deferral). F6 should move from "PARTIALLY FIXED" to "Recently fixed (prompt-37.5)".

**D2. "Built but not reachable" table not updated for 37.5.**
The plan's closing step 7 said: "Update 'Built but not reachable' table: ApprovalTrustRegistry, notes skill, reminder skill now functionally correct (still not wired end-to-end via TUI)." This wasn't done. The table still lists them as plain "Built but not reachable" with no note about 37.5 making them functionally correct.

**D3. CHANGELOG Gate 14 verifies the wrong tag.**
Prompt-37.5's CHANGELOG entry says: "Gate 14: Tag verification — PASSED - prompt-37.1 tag exists on remote with correct hash (41cb13b...)." This is verifying `prompt-37.1` (the previous prompt), not `prompt-37.5` (the current one). The tag IS on origin (verified), but the CHANGELOG gate output references the wrong tag.

**D4. F6 "Remaining work" line is stale.**
Line 62: "Also 69 test failures due to mock implementation details not matching expected behavior." These were fixed in prompt-37.1. The line should be removed or updated to reflect that the only remaining F6 work is trajectory_exporter (Plan 45).

## What to change

### Step 0 — Handoff hygiene from 37.5 (do this FIRST, before any code changes)

**File**: `SOVEREIGN_AI_HANDOFF.md`

**0a.** Move F6 from "PARTIALLY FIXED" to "Recently fixed (prompt-37.5)". Find the `### F6 — MemoryRouter call-signature mismatch (PARTIALLY FIXED)` section and:
- Change the heading to `### F6 — MemoryRouter call-signature mismatch (FIXED in prompt-37.5)`
- Update the "Status" line to: "Fully closed. 4 new MemoryRouter methods added (`fetch_by_filter`, `write_to_collection`, `get_global_context`, `set_global_context`) and 33 call sites updated in prompt-37. Plus `scoped_read`/`scoped_write` added in prompt-37.5 (13 call sites in 3 files). `trajectory_exporter.py` uses a different pattern (`fetch(Type, filter_func=...)`) and is stubbed with a Plan 45 deferral."
- Remove the "Remaining work" line (it references 37.1's 69 test failures, which are fixed)
- Update the "Verification" line to: `mypy core/ system/ --ignore-missing-imports | grep "Unexpected keyword argument"` returns zero hits (excluding `trajectory_exporter.py` which is Plan 45)

**0b.** Add a "Recently fixed (prompt-37.5)" section after the existing "Recently fixed (prompt-37)" section:
```
## Recently fixed (prompt-37.5)

Fixed in prompt-37.5. These entries will be removed in the next prompt.

- **F6 (fully closed)** — Added `scoped_read`/`scoped_write` to MemoryRouter (13 call sites in 3 files: approval_trust, notes_skill, reminder_skill). Fixed `escalation.py:146` phantom `request` call → `request_approval`. Fixed `trajectory_exporter.py` with Option 2 stub (Plan 45 deferral). Added TYPE_CHECKING import for StrategicContext (rolled in from 37.1 gap).
```

**0c.** Update the "Built but not reachable" table. For each of these rows, update the "Status" column to note they're now functionally correct (but still not wired end-to-end via TUI — that's what 37.6 is for):
- `ApprovalTrustRegistry` → "Functionally correct (prompt-37.5 added scoped_read/write). Wired in `cli/serve.py` only; not in `cli/tui.py` (Plan 37.6)."
- `TrajectoryExporter` → "Stubbed with Plan 45 deferral (prompt-37.5). Backend doesn't support `fetch(Type, filter_func=...)` pattern."
- `notes_skill` and `reminder_skill` (if listed) → "Functionally correct (prompt-37.5 added scoped_read/write). Not wired into runtime entry points."

**0d.** Update the "Last updated" line to reference prompt-37.6 once 37.6 lands (do this in 37.6's closing steps, not now).

### Step 1 — Construct the full cognition stack in `cli/tui.py`

**File**: `cli/tui.py`
**Location**: The `__init__` method of the TUI app class, around lines 260-285 (where `memory_router` is currently constructed for `WorkerPersistence` only).

**Approach**: Mirror what `cli/serve.py:38-164` does. Construct every component in the same order, with the same dependencies, passing the same `memory_router`. The only differences:
- TUI uses `TextualTraceEmitter` (or similar) instead of `MemoryTraceEmitter` — check what `cli/tui.py` already uses for `self.emitter` and pass that
- TUI's `memory_router` is conditionally constructed (only if `db_dsn` is set); for the no-DSN case, construct `MemoryRouter(backends={})` like `serve.py` does

**Required components** (mirror `cli/serve.py:55-180`):

```python
# 1. Memory router (use existing one if db_dsn, else empty backends)
if db_dsn:
    from memory.postgres import PostgresBackend
    memory_router = MemoryRouter(postgres_backend=PostgresBackend(dsn=db_dsn, table_name="workers"))
else:
    memory_router = MemoryRouter(backends={}, emitter=self.emitter)

# 2. SkillRegistry
skill_registry = SkillRegistry(emitter=self.emitter)

# 3. ApprovalTrustRegistry
approval_trust = ApprovalTrustRegistry(memory_router=memory_router, emitter=self.emitter)

# 4. TaskStateMachine
state_machine = TaskStateMachine(memory_router=memory_router)

# 5. ApprovalGate (with trust_registry)
approval_gate = ApprovalGate(
    state_machine=state_machine,
    memory_router=memory_router,
    emitter=self.emitter,
    trust_registry=approval_trust,
)

# 6. EscalationEngine
escalation_engine = EscalationEngine(
    approval_gate=approval_gate,
    memory_router=memory_router,
    emitter=self.emitter,
)

# 7. AdapterFallbackChain (use current adapter, not just Ollama)
# IMPORTANT: Read create_worker's implementation in cli/adapter_factory.py to find
# how to get a reference to the adapter it creates. Check whether the returned
# worker exposes it via worker.adapter or similar. If create_worker doesn't
# expose the adapter, construct the adapter explicitly here (matching how
# cli/serve.py:81 constructs OllamaAdapter directly) and pass it to both
# create_worker and AdapterFallbackChain.
current_adapter = ...  # see note above — resolve by reading create_worker source
current_adapter_name = ...  # e.g. "qwen2.5-coder:7b" or whatever the user configured
fallback_chain = AdapterFallbackChain(
    adapters=[(current_adapter, current_adapter_name)],
    resource_manager=None,  # knowingly None — see note below
    approval_gate=approval_gate,
    emitter=self.emitter,
)
# NOTE: resource_manager=None mirrors cli/serve.py. If AdapterFallbackChain
# calls resource_manager methods at runtime, it will raise AttributeError
# swallowed by broad except (Plan 38+ will audit). Not a new problem — same
# gap exists in serve.py today.

# 8. RatingSystem
rating_system = RatingSystem(memory_router=memory_router, emitter=self.emitter)

# 9. InstructionGenerator
instruction_generator = InstructionGenerator(
    adapter=current_adapter,
    rating_system=rating_system,
    memory_router=memory_router,
    obsidian_vault_path=os.getenv("OBSIDIAN_VAULT_PATH"),
    emitter=self.emitter,
)

# 10. InstructionVersionManager
instruction_versioning = InstructionVersionManager(
    instruction_generator=instruction_generator,
    rating_system=rating_system,
    approval_gate=approval_gate,
    memory_router=memory_router,
    emitter=self.emitter,
)

# 11. OutputEvaluator
output_evaluator = OutputEvaluator(
    llm_adapter=current_adapter,
    memory_router=memory_router,
    evaluator_model="default",
    emitter=self.emitter,
)

# 12. TraceOptimiser
trace_optimiser = TraceOptimiser(
    memory_router=memory_router,
    instruction_version_manager=instruction_versioning,
    emitter=self.emitter,
)

# 13. Orchestrator (with all dependencies)
self.orchestrator = Orchestrator(
    memory_router=memory_router,  # ← was None
    improvement_loop=None,  # set after creating it
    cloud_fallback_model="gpt-4o",
    approval_gate=approval_gate,
    escalation_engine=escalation_engine,
    fallback_chain=fallback_chain,
    a2a_router=None,
    emitter=self.emitter,
)

# 14. WorkerFactory
worker_factory = WorkerFactory(
    skill_registry=skill_registry,
    orchestrator=self.orchestrator,
    memory_router=memory_router,
    emitter=self.emitter,
    persistence=self.worker_persistence,  # may be None
    instruction_generator=instruction_generator,
)

# 15. OrchestratorImprovementLoop
improvement_loop = OrchestratorImprovementLoop(
    orchestrator=self.orchestrator,
    instruction_version_manager=instruction_versioning,
    memory_router=memory_router,
    emitter=self.emitter,
)
self.orchestrator.improvement_loop = improvement_loop

# 16. Create worker with REAL memory_router (not None)
self.worker = create_worker("ollama", "llama3", memory_router=memory_router)
self.orchestrator.register_worker("ollama_worker", self.worker)
```

**Verify after this step**: `python -c "from cli.tui import <TUIAppClass>; print('imports OK')"` (replace `<TUIAppClass>` with the actual class name — read the file first).

### Step 2 — Fix the adapter-swap path (line 375)

**File**: `cli/tui.py`
**Line**: 375

When the user swaps adapters via `/adapter <name>`, the TUI creates a new worker. Currently:
```python
self.worker = create_worker(adapter_name, "llama3", memory_router=None)
```

Change to use the same `memory_router` constructed in Step 1:
```python
self.worker = create_worker(adapter_name, "llama3", memory_router=memory_router)
```

**Problem**: `memory_router` is currently a local variable in `__init__`. It needs to become `self.memory_router` so the adapter-swap path can access it. Update Step 1 to store as `self.memory_router` and use it in both the initial construction and the adapter swap.

### Step 3 — Handle the no-DSN case for `WorkerPersistence`

**File**: `cli/tui.py`

Currently, `WorkerPersistence` is only constructed if `db_dsn` is set (line 254-271). The `memory_router` is also only constructed in that branch. Step 1 changes this so `memory_router` is always constructed (empty backends if no DSN).

**Verify**: After Step 1, the no-DSN path should still work — `WorkerPersistence` gets `None` (or skip its construction), `memory_router` gets `MemoryRouter(backends={})`, orchestrator and worker get the real (if empty) `memory_router`. Memory calls will return empty results, not AttributeError. That's correct behavior for a no-DSN setup.

### Step 4 — Create `tests/test_tui.py`

**File**: `tests/test_tui.py` (NEW)

The TUI has zero test coverage today. This plan adds a minimal test file that verifies the cognition stack is constructed and wired. **Do NOT write smoke tests with `assert True`** (recurring mistake #2). Each test must verify behavior.

**Required tests**:

```python
"""Tests for TUI cognition stack wiring (Plan 37.6)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from cli.tui import <TUIAppClass>  # replace with actual class name

# NOTE: Do NOT add @pytest.mark.asyncio at class level. The TUI __init__ is
# synchronous, so all tests below are plain def (not async def). Adding
# @pytest.mark.asyncio on the class would be ignored for sync methods but
# is misleading — leave it off.

class TestTUICognitionWiring:
    """Verify the TUI constructs and wires the full cognition stack."""
    
    def test_tui_constructs_memory_router(self):
        """TUI must construct a real MemoryRouter, not pass None."""
        # ... capture the orchestrator and assert memory_router is not None
        # ... assert memory_router has fetch_by_filter method (the new interface)
    
    def test_tui_passes_memory_router_to_orchestrator(self):
        """Orchestrator must receive the real memory_router, not None."""
        # ... assert orchestrator.memory_router is the same object as the one constructed
    
    def test_tui_passes_memory_router_to_worker(self):
        """OllamaWorker must receive the real memory_router, not None."""
        # ... assert worker.memory_router is the same object
    
    def test_tui_constructs_approval_gate(self):
        """TUI must construct ApprovalGate with trust_registry."""
        # ... assert orchestrator has approval_gate
        # ... assert approval_gate has trust_registry (not None)
    
    def test_tui_constructs_rating_system(self):
        """TUI must construct RatingSystem."""
        # ... assert rating_system is constructed and wired
    
    def test_tui_constructs_instruction_generator(self):
        """TUI must construct InstructionGenerator."""
        # ... assert instruction_generator is constructed
    
    def test_tui_constructs_orchestrator_improvement_loop(self):
        """TUI must construct OrchestratorImprovementLoop and set it on orchestrator."""
        # ... assert orchestrator.improvement_loop is not None
    
    def test_tui_adapter_swap_preserves_memory_router(self):
        """When user swaps adapter, the new worker must get the same memory_router."""
        # ... simulate adapter swap, assert new worker has memory_router (not None)
        # ... assert it's the SAME object as the original (not a new one)
```

**STOP condition for Step 4**: If the TUI class can't be constructed in a test (e.g., requires a running Textual app, Ollama server, or Postgres connection), STOP. Document the blocker in the CHANGELOG and write the tests as `@pytest.mark.skip(reason="...")` with the blocker explained. Do NOT delete the tests.

### Step 5 — Run the TUI manually to verify it still starts

**Command**: `python -m cli.tui` (or whatever the TUI entry point is — check `cli/main.py`)

**Expected**: TUI starts, user can type a query, get a response from Ollama. No trace spam (F7 is still open — Plan 38). No crashes.

**If TUI crashes**: STOP. The wiring is wrong. Common causes:
- Circular import (cognition stack imports something that imports TUI)
- Missing required argument to a component (read the component's `__init__` signature)
- `emitter` mismatch (TUI's emitter vs cognition stack's expected emitter type)

**Verify**: Type a query like "hello" and confirm you get a response. Then type another query and confirm the memory_router is actually being called (check trace events if emitter is MemoryTraceEmitter).

### Step 6 — Update handoff "What works right now" section

**File**: `SOVEREIGN_AI_HANDOFF.md`

Find the "What works right now" section. Update the `jarvis` (no args) entry:

**Before**:
```
- **`jarvis`** (no args) — starts Textual TUI with one OllamaWorker registered. User can type queries, get responses from local Ollama.
```

**After**:
```
- **`jarvis`** (no args) — starts Textual TUI with full cognition stack wired (Orchestrator, MemoryRouter, ApprovalGate, EscalationEngine, AdapterFallbackChain, WorkerFactory, RatingSystem, InstructionGenerator, InstructionVersionManager, OutputEvaluator, TraceOptimiser, OrchestratorImprovementLoop). User can type queries, get responses from local Ollama. Memory is now stateful across queries (prompt-37.6).
```

### Step 7 — Update handoff "Built but not reachable" table

**File**: `SOVEREIGN_AI_HANDOFF.md`

The handoff's table has 3 columns: `Subsystem | File | Why it's dormant`. There is NO "Status" column. Per the handoff's own maintenance rules: "The 'Built but not reachable' table shrinks as subsystems are wired. It never grows."

**Action**: Remove these rows from the table entirely (they are no longer dormant — they're now wired in both `cli/serve.py` and `cli/tui.py`):
- `WorkerFactory`
- `RatingSystem`
- `InstructionGenerator`
- `InstructionVersionManager`
- `OutputEvaluator`
- `TraceOptimiser`
- `OrchestratorImprovementLoop`
- `EscalationEngine`
- `AdapterFallbackChain`
- `ApprovalGate` (note: was "Only constructed in `screenshot` and `home_assistant` skills as throwaway instances" — now also wired in both CLI entry points)
- `ApprovalTrustRegistry`
- `WorkerPersistence` (was "Constructed in `tui.py:267` and `rich_cli.py:84` but never passed to WorkerFactory" — now passed)

**Do NOT add a Status column**. The table shrinks by removing rows, not by annotating them. If a row needs to remain (e.g. MultiWorkerDispatcher, A2ARouter — still not wired), leave it as-is.

After Step 7, the table should have ~12 fewer rows (the 12 subsystems listed above). Remaining rows: MultiWorkerDispatcher, A2ARouter, MonitorDaemon, VoiceDaemon, TelegramGateway, RetentionDaemon, RetentionManager, TriggerEngine, NotificationSystem, ResourceBudget, VerbosityManager, TrajectoryExporter (stubbed, Plan 45), MemoryCompactor, InputSanitiser (Rule 13 violation), MCPServer, MCPAdapter.

### Step 8 — Fix 37.5 CHANGELOG Gate 14 reference

**File**: `CHANGELOG.md`

**First**: Verify the prompt-37.5 hash before writing it. Run `git rev-parse prompt-37.5` and confirm it matches `e02cb2a80d71803975ef95424d5abd278855439d`. If it doesn't match (e.g. tag was moved, repo was rewritten), use the actual output of `git rev-parse prompt-37.5` instead. Do NOT trust the hash hardcoded in this plan blindly — verify against the live repo.

Find prompt-37.5's Gate 14 entry:
```
#### Gate 14: Tag verification
PASSED - prompt-37.1 tag exists on remote with correct hash (41cb13b88adaa293da830d4eca6f2b1a796c92f6).
```

Append a correction (do not edit history — append-only per global_rules.md Rule 16):
```
#### Gate 14: Tag verification (CORRECTION — added in Plan 37.6)
- Original entry above incorrectly referenced prompt-37.1 tag (hash 41cb13b...).
- Actual prompt-37.5 tag: e02cb2a80d71803975ef95424d5abd278855439d (verified via `git rev-parse prompt-37.5`)
- Verified via `git ls-remote --tags origin | grep prompt-37.5` → e02cb2a80d71803975ef95424d5abd278855439d refs/tags/prompt-37.5
- The tag was on origin the whole time; the CHANGELOG gate output referenced the wrong prompt number.
```

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-37.5..HEAD -- cli/tui.py cli/main.py cli/rich_cli.py tests/test_main.py tests/test_tui.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
```

**Expected**: empty output (no drift since prompt-37.5).

### Gate 2 — TUI imports cleanly

```
python -c "from cli.tui import <TUIAppClass>; print('imports OK')"
```

**Expected**: `imports OK` (no ImportError, no circular import).

### Gate 3 — TUI constructs memory_router (not None)

```
python -c "import asyncio; from cli.tui import <TUIAppClass>; from unittest.mock import patch; app = <TUIAppClass>(); print('memory_router:', app.orchestrator.memory_router)"
```

**Expected**: `memory_router: <MemoryRouter object at 0x...>` — NOT `None`.

**Warning — potential hangs/connection errors**: The existing `cli/tui.py:279` constructs an OllamaWorker that contacts Ollama at construction time. If Gate 3 hangs or throws a connection error (e.g. `httpx.ConnectError` to localhost:11434), **mock the Ollama/Postgres calls before constructing the app**. Example:
```python
python -c "
from unittest.mock import patch, AsyncMock
with patch('adapters.ollama.OllamaAdapter.generate', new_callable=AsyncMock), \
     patch('memory.postgres.PostgresBackend.__init__', return_value=None):
    from cli.tui import <TUIAppClass>
    app = <TUIAppClass>()
    print('memory_router:', app.orchestrator.memory_router)
"
```
If mocking is required, document this in the CHANGELOG and update Gate 3's command accordingly. Do NOT spend time debugging a test environment issue — it's a wiring test, not an integration test.

### Gate 4 — TUI constructs full cognition stack

```
python -m pytest tests/test_tui.py -v --tb=short
```

**Expected**: all 8 tests pass. If any test is `@pytest.mark.skip`, the CHANGELOG must explain why.

### Gate 5 — TUI starts and accepts a query

```
python -m cli.tui
# Type "hello", press Enter, verify response
# Type "what did I just say?", verify it remembers (memory_router working)
```

**Expected**: TUI starts, accepts query, returns response. Second query shows memory of first (if memory_router is working). No crashes, no trace spam (F7 is Plan 38).

**If TUI cannot be tested interactively in CI**: document this in CHANGELOG and rely on Gates 3-4 for verification.

### Gate 6 — Adapter swap preserves memory_router

```
# In TUI, type /adapter lm_studio
# Then type a query
# Verify the worker still has memory_router (not None)
```

**Expected**: adapter swap works, new worker has `memory_router` set, queries still work.

### Gate 7 — Full test suite

```
python -m pytest tests/ -q --tb=short
```

**Expected**:
- Baseline (post prompt-37.5): **1072 passed, 29 skipped, 1 failed (flaky), 63 warnings**
  - Note: prompt-37.5 did not add new tests, but it converted 6 trajectory_exporter tests from passing to `pytest.skip(...)` (Plan 45 deferral). So the baseline went from 1078/23 (post-37.1) to 1072/29 (post-37.5). The 6-test delta is skipped-count, not lost tests.
- After prompt-37.6: **1080 passed** (1072 + 8 new tests in test_tui.py), 29 skipped, 1 failed (flaky), ~63 warnings
- Acceptable range: **{1079, 1080, 1081}**. Anything outside is a regression. STOP.
- If Gate 7 shows 1086 passed (Claude's first-round review suggested this — it was wrong; the math is 1072+8=1080, not 1078+8=1086, because 37.5's 6 trajectory_exporter tests moved from passed to skipped)

### Gate 8 — Handoff "What works right now" updated

```
grep "full cognition stack wired" SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 1 match (the updated `jarvis` entry).

### Gate 9 — Handoff "Built but not reachable" table updated

```
grep -c "^\| [A-Z]" SOVEREIGN_AI_HANDOFF.md
```

**Expected**: count of data rows in the table. Record the count BEFORE Step 7 (should be ~24) and AFTER Step 7 (should be ~12). The drop should be ~12 rows (the 12 subsystems wired by this plan).

**Also verify**: no "Status" column was added to the table. The grep for status annotation should return 0:
```
grep -c "Wired in \`cli/serve.py\` (35.6f) and \`cli/tui.py\` (37.6)" SOVEREIGN_AI_HANDOFF.md
```
**Expected**: 0 matches. (The rows are REMOVED, not annotated. See Step 7 — the table shrinks, it doesn't grow a Status column.)

### Gate 10 — F6 fully closed in handoff (from Step 0a)

```
grep "PARTIALLY FIXED" SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 0 matches (F6 should now say "FIXED in prompt-37.5").

### Gate 11 — Rule 18 honored (no red test suite)

Implicit in Gate 7. If Gate 7 passes, Rule 18 is honored.

## STOP conditions

- **If Step 1 reveals a circular import** (e.g., cognition stack imports something that imports TUI), STOP. Document the circular dependency. May need to refactor before this plan can land.
- **If Step 4 (TUI tests) cannot construct the TUI app** (e.g., requires running Textual event loop), STOP. Write tests as `@pytest.mark.skip` with the blocker explained. Do NOT delete tests.
- **If Step 5 (manual TUI test) crashes**, STOP. The wiring is wrong. Investigate before proceeding.
- **If Gate 7 shows fewer than 1079 passed tests**, STOP. Regression introduced.
- **If any file outside the in-scope list needs editing**, STOP. Report which file and why.
- **If total production code changes exceed 200 lines** (excluding tests), STOP. Split into 37.6a/37.6b.

## Out of scope

- **`cli/rich_cli.py`** — separate interactive path (`jarvis --rich`). May need same treatment. Separate plan.
- **F7 (trace spam)** — Plan 38. The TUI will still show trace spam until 38 lands.
- **Broad-except audit** — Plan 38+. The TUI's `except Exception: pass` blocks still swallow errors silently.
- **InputSanitiser wiring** — Plan 41+. TUI user input still flows directly to LLM without sanitisation.
- **`cli/main.py`** — thin dispatcher, no changes needed.
- **Interactive TUI testing in CI** — manual verification only (Gate 5). Automated TUI testing is a separate concern.

## Closing steps

1. `git add` the in-scope files: `cli/tui.py`, `tests/test_tui.py`, `SOVEREIGN_AI_HANDOFF.md`, `CHANGELOG.md`
2. `git commit -m "fix: prompt-37.6 — wire cognition stack into cli/tui.py (mirror of 35.6f for TUI)"`
3. `git tag prompt-37.6`
4. `git show prompt-37.6 --stat` — verify file list. If unexpected file appears, `git tag -d prompt-37.6`, clean, re-tag.
5. **Post-tag verification (global_rules.md Rule 20)**: `git rev-parse prompt-37.6` — confirm hash matches the commit
6. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail
   - **Implementation Notes**: any components that needed different wiring than `cli/serve.py`, any circular import issues, any tests that needed `@pytest.mark.skip`
   - **Testing Results**: baseline (1072 passed from prompt-37.5) → final (expected 1080)
   - **Verification Gate Output**: literal output of each gate
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-37.6
   - Update "What works right now" section (Step 6)
   - Update "Built but not reachable" table (Step 7)
   - Confirm Step 0 hygiene fixes are in place
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-37.6 changelog and handoff update"`
10. `git push origin master && git push origin prompt-37.6`
11. **Post-push verification (global_rules.md Rule 20)**: `git ls-remote --tags origin | grep prompt-37.6` — verify the tag exists on the remote. **Do not skip this step.**
12. **Reconcile test count**: Paste the literal `python -m pytest tests/ -q --tb=short` output into the CHANGELOG. If the count differs from 1080, explain why.

## After Plan 37.6 lands

The TUI path now has parity with `jarvis serve` at the cognition-stack level. The foundation is solid. The queue can now proceed to horizontal cleanup:

- **Plan 38** — F7 trace spam + `cli/__init__.py` (was Plan 38 before resequencing)
- **Plan 38.5** — Broad-except audit, part 1 (core/)
- **Plan 39** — Broad-except audit, part 2 (system/)
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45+** — graphify integration cluster, proper MemoryBackend.delete(), trajectory_exporter functional redesign

Plans 38+ can land in any order. The foundation is done. Horizontal cleanup work won't be blocked by functional bugs.
