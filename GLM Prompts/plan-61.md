# Plan 61 — Trace Store Implementation (Postgres Backend)

**Priority**: 2 (measurement layer foundation)
**Scope**: Implement persistent trace event storage in Postgres for the observability measurement layer.

---

## S0 — Opening Sequence

### S0.1: Run `/jarvis-open`

Per AI_HANDOFF.md's Devin Plan Template, run the workflow — do not hand-roll the equivalent commands. The workflow verifies the previous prompt's tag on origin and confirms the working copy is clean and on `master`. If the workflow is missing or fails, STOP and report.

### S0.2: AGENTS.md Rules Check

Read `AGENTS.md` in full. No new AGENTS.md rules for this plan.

All file edits in this plan MUST comply with:
- **AR1-AR4**: Architecture rules (core/memory separation)
- **AR9**: No raw LLM calls outside adapters/
- **AR10**: Memory access via MemoryRouter only
- **AR11**: `TraceEmitter` via constructor injection only — **never the global `emit_trace()` function.** This plan only ever touches the constructor-injected `TraceEmitter` instance method. Anywhere this plan says "emit_trace()", it means `TraceEmitter.emit_trace()` on the injected instance, not the deprecated global function. If the existing code in `core/observability.py` currently calls the global function, that is the known AR13 deferred violation — do not extend it; route new trace-store wiring only through the instance method.
- **AR12**: All I/O async
- **AR14**: Return type annotations
- **AR18**: No broad `except Exception: pass` without inline comment + WARNING trace. Applies directly to the fire-and-forget store call in S1.3/S2.2 below.
- **OR5**: Edit each file occurrence individually (never replace_all)
- **OR6**: Syntax check after every edit
- **OR7**: Structured markdown edits use Edit tool only
- **OR15-OR17**: Scope discipline (no unplanned changes)
- **OR20**: Never mix naive/aware datetime (use `datetime.now(timezone.utc)`)
- **OR22**: Re-read AGENTS.md before file edits

**If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context.**

### S0.3: Scope Declaration (OR15)

**Will edit** (6 files, see Expected Outcomes for line estimates):
- `memory/postgres_trace_store.py` (new)
- `tests/test_postgres_trace_store.py` (new)
- `tests/test_postgres_trace_store_integration.py` (new)
- `memory/__init__.py`
- `memory/router.py`
- `core/observability.py`

**Will NOT edit**: anything in `core/` other than `observability.py`. No changes to `cli/`, `web/`, `system/`, `skills/`, `adapters/`, or any other file in `memory/`. If wiring the new backend requires touching a file outside this list, STOP and report per OR16 — do not fix it unilaterally.

---

## S1 — Implement Postgres Trace Store Backend

### S1.1: Create `memory/postgres_trace_store.py`

**Purpose**: Persistent trace storage backend using Postgres.

**Scope**: New file only (no existing code to modify yet). ~200 lines.

**Library**: Use **`asyncpg`** for connection pooling and queries. (Do not use `psycopg`/`psycopg_pool` — `asyncpg` is the library used throughout this plan's code skeleton, tests, and `requirements.txt` entry; mixing the two is not permitted.)

**Design**:
- Class: `PostgresTraceStore` (implements trace storage interface)
- Async methods: `store_trace()`, `query_traces()`, `get_trace_by_id()`, `close()`
- Postgres connection pooling via `asyncpg.create_pool()`
- Schema: trace table with columns: id, timestamp, event_type, metadata (jsonb), source, status
- Timestamps: **Use `datetime.now(timezone.utc)` — never bare `datetime.now()` or `datetime.utcnow()` (OR20)**

**Steps**:
1. Create file with class skeleton
2. Add constructor with connection pool initialization
3. Implement `store_trace(event: TraceEvent) → str` (returns trace ID)
4. Implement `query_traces(filters: dict) → list[TraceEvent]`
5. Implement `get_trace_by_id(trace_id: str) → TraceEvent | None`
6. Implement `close() -> None` — closes the pool cleanly (`await self.pool.close()`). Required so tests and any future shutdown path don't leak connections.

**Key requirements**:
- ✅ All methods async (AR12)
- ✅ Return type annotations on all public methods (AR14)
- ✅ No direct imports of LLM adapters (AR9)
- ✅ Connection pooling for production use (5-10 pool size)
- ✅ Jsonb column for flexible metadata storage
- ✅ `close()` available for clean teardown (no leaked connections in tests or app shutdown)

**File structure**:
```python
from datetime import datetime, timezone
from typing import Optional
import asyncpg

class PostgresTraceStore:
    def __init__(self, dsn: str, pool_size: int = 10):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
        self.pool_size = pool_size

    async def initialize(self) -> None:
        """Set up connection pool and schema."""
        # Create pool via asyncpg.create_pool(dsn=self.dsn, max_size=self.pool_size)
        # Create table if not exists

    async def close(self) -> None:
        """Close the connection pool cleanly."""
        # await self.pool.close() if self.pool is not None

    async def store_trace(self, event: dict) -> str:
        """Store trace event, return trace ID."""
        # Insert into trace table
        # Return id

    async def query_traces(self, filters: dict) -> list:
        """Query traces by filters."""
        # Build WHERE clause from filters
        # Execute query
        # Return results

    async def get_trace_by_id(self, trace_id: str) -> Optional[dict]:
        """Get trace by ID."""
        # Query by id
        # Return result or None
```

After creating, run:
```powershell
python -c "import ast; ast.parse(open('memory/postgres_trace_store.py').read())"
git diff --stat memory/postgres_trace_store.py
```

Verify: syntax clean, file is new, ~200 lines.

---

### S1.2: Update `memory/__init__.py` to export PostgresTraceStore

**Purpose**: Make trace store available to core.observability.

**Steps**:
1. Add import: `from .postgres_trace_store import PostgresTraceStore`
2. Add to `__all__` list

**After edit**:
```powershell
python -c "import ast; ast.parse(open('memory/__init__.py').read())"
git diff memory/__init__.py
```

Verify: syntax clean, only 2-3 lines changed.

---

### S1.3: Update `core/observability.py` — Trace Routing

**Purpose**: Route trace emissions to Postgres backend when available, without blocking the caller.

**Current state**: `TraceEmitter` exists; needs backend integration. Per AR11, all wiring below applies to the **constructor-injected `TraceEmitter` instance method** — never the deprecated global `emit_trace()` function (AR13's known violation lives elsewhere; do not extend it here).

**Steps**:
1. Add optional parameter to `TraceEmitter.__init__`: `trace_store: PostgresTraceStore | None = None`. Type annotation: `trace_store: Optional[PostgresTraceStore] = None`.
2. In `TraceEmitter.emit_trace()`, if `self.trace_store` exists, schedule the store call as a **fire-and-forget background task** — do not `await` it directly in the emission path, since that would block the caller on Postgres I/O:
   ```python
   if self.trace_store is not None:
       asyncio.create_task(self._safe_store_trace(trace_event))
   ```
3. Implement a small wrapper that applies AR18 (no bare `except Exception: pass`):
   ```python
   async def _safe_store_trace(self, trace_event: dict) -> None:
       """Best-effort trace persistence. Failures here must never affect
       the emission path — trace storage is an optional backend."""
       try:
           await self.trace_store.store_trace(trace_event)
       except Exception as exc:  # noqa: BLE001 — optional backend, swallow by design
           logger.warning("Trace store write failed; continuing without persistence: %s", exc)
   ```
4. This requires `import asyncio` at the top of `core/observability.py` if not already present. Confirm a module-level `logger` already exists (e.g. `logger = logging.getLogger(__name__)`) before using `logger.warning(...)` above — if it doesn't, adding it is in-scope for this file since `core/observability.py` is already on the declared edit list.
5. For testability, store the created task on the emitter (e.g. `self._last_trace_task = asyncio.create_task(...)`) rather than discarding the reference. This gives tests in S1.4/S4.1 something deterministic to `await` instead of guessing how long the background write takes.
6. This resolves the apparent tension between "call it" and "don't block the critical path": the `await` happens inside the background task, not inline in `emit_trace()`.

**Key point**: Trace storage is **optional** (graceful degradation if Postgres unavailable or if a write fails mid-session).

**After each edit**:
```powershell
python -c "import ast; ast.parse(open('core/observability.py').read())"
git diff core/observability.py | head -40
```

Verify: syntax clean, only trace_store wiring added.

---

### S1.4: Create `tests/test_postgres_trace_store.py`

**Purpose**: Unit tests for PostgresTraceStore.

**Scope**: ~160 lines, 13 test cases.

**Test scenarios**:
1. `test_initialize_creates_pool()` — pool initializes without error
2. `test_store_trace_returns_id()` — store_trace returns a UUID/string
3. `test_store_trace_inserts_data()` — verify data in DB after store
4. `test_query_traces_empty()` — query on empty table returns []
5. `test_query_traces_with_filters()` — query filters work (timestamp range, source)
6. `test_get_trace_by_id_found()` — get existing trace
7. `test_get_trace_by_id_not_found()` — get non-existent trace returns None
8. `test_async_concurrent_stores()` — concurrent store calls don't corrupt data
9. `test_jsonb_metadata_round_trip()` — metadata survives serialization
10. `test_connection_pool_exhaustion()` — graceful handling of pool limits
11. `test_close_closes_pool()` — `close()` releases the pool without error and a subsequent `store_trace()` call fails cleanly rather than hanging
12. `test_emit_trace_with_no_trace_store()` — `TraceEmitter` with `trace_store=None` emits normally with no error (the actual graceful-degradation path)
13. `test_emit_trace_swallows_store_failure()` — if `store_trace()` raises, `emit_trace()` still returns/completes normally and a WARNING is logged (AR18 compliance), not raised to the caller

**Environment note**: Tests 1-11 require a real Postgres instance or a Postgres test fixture (e.g. `testcontainers`, a docker-compose service, or an equivalent). **Before this plan is executed, confirm which option exists in the test environment.** If no live Postgres is available in CI/test, these tests must be marked `@pytest.mark.skipif(<no postgres>, reason="...")` rather than silently failing or hanging — and the S5.1 baseline math below must be adjusted to expect skips, not passes, for that subset (see S5.1 note).

**Fixtures**:
- `postgres_dsn` — test DB connection string (or mock)
- `trace_store` — `PostgresTraceStore` instance for tests, with teardown via `close()` in a fixture finalizer/`yield`
- `sample_trace_event` — dict with test event data

**Important**: Use pytest-asyncio for async tests. Mark tests `@pytest.mark.asyncio`.

After creating:
```powershell
python -m pytest tests/test_postgres_trace_store.py -v
```

Expected: all tests pass, or skip cleanly with a clear reason if Postgres is unavailable.

---

## S2 — Integration with Memory Router

### S2.1: Update `memory/router.py` — Backend Registration

**Purpose**: Register PostgresTraceStore as optional backend in MemoryRouter.

**Steps**:
1. Add parameter to MemoryRouter constructor: `trace_store: PostgresTraceStore | None = None`
2. Store as instance variable: `self.trace_store = trace_store`
3. Add method: `get_trace_store() -> Optional[PostgresTraceStore]`

**Before editing**: confirm `MemoryRouter.__init__`'s current call sites (`grep`/`Select-String` for `MemoryRouter(`) to confirm adding this parameter doesn't collide with positional-argument call sites elsewhere in the repo. This is outside the file-edit list but is a read-only check, not a scope expansion.

**After edit**:
```powershell
python -c "import ast; ast.parse(open('memory/router.py').read())"
git diff memory/router.py | head -30
```

Verify: syntax clean, only backend registration added.

---

### S2.2: Update `core/observability.py` — Route through MemoryRouter

**Purpose**: Get trace_store from MemoryRouter instead of direct injection (AR10).

**Current pattern**: Other memory access routes through MemoryRouter (AR10).

**Steps**:
1. In `TraceEmitter.__init__`, accept `memory_router` and, if provided, set `self.trace_store = memory_router.get_trace_store()` (falling back to a directly-injected `trace_store` argument if `memory_router` is not provided — keep both paths working per AR10 + the existing optional-injection pattern from S1.3).
2. The fire-and-forget pattern from S1.3 (`asyncio.create_task(self._safe_store_trace(...))` + `_safe_store_trace`'s try/except + WARNING log) is unchanged — this step only changes *where* `self.trace_store` is sourced from, not the non-blocking/error-handling behavior.
3. Confirm there is exactly one non-blocking path into trace storage, not two divergent ones — S1.3 and this step must describe the same mechanism, not a second one.

**After edit**:
```powershell
python -c "import ast; ast.parse(open('core/observability.py').read())"
git diff core/observability.py | head -40
```

Verify: syntax clean, trace storage routed through MemoryRouter, no duplicate/conflicting non-blocking logic.

---

## S3 — Verification and Testing

### S3.1: Run Targeted Tests

```powershell
python -m pytest tests/test_postgres_trace_store.py tests/test_memory_router.py -v --tb=short
```

Expected: all targeted tests pass (or skip cleanly per the S1.4 environment note).

**If tests fail**:
- Check: Postgres connection string correct?
- Check: Pool initialization working?
- Check: Async fixtures set up correctly?
- Check: is `close()` being called in fixture teardown (leaked connections can cause flaky failures in later tests)?

If pre-existing failures (unrelated to this plan), note in CHANGELOG, continue.

---

### S3.2: File-Scoped Mypy

```powershell
mypy memory/postgres_trace_store.py memory/router.py core/observability.py --ignore-missing-imports 2>&1 | Select-Object -Last 5
```

Expected: error count ≤ baseline (+5-10 acceptable for Postgres typing).

If errors: fix type annotations, re-run.

---

### S3.3: Ruff on Touched Files

```powershell
ruff check memory/postgres_trace_store.py memory/__init__.py memory/router.py core/observability.py tests/test_postgres_trace_store.py 2>&1 | Select-Object -Last 3
```

Expected: 0 errors (file-scoped cleanup as you go).

If errors: fix before moving to closing.

---

## S4 — Integration Smoke Test

### S4.1: Create Integration Test Sketch

**File**: `tests/test_postgres_trace_store_integration.py`

**Purpose**: End-to-end trace: emit → store → query.

**Test**:
1. Initialize MemoryRouter with PostgresTraceStore
2. Create TraceEmitter with memory_router
3. Emit a trace event
4. Await the background task directly rather than guessing with a sleep — use the `self._last_trace_task` handle introduced in S1.3 (`await emitter._last_trace_task`) so the test deterministically waits for the real Postgres round-trip to finish before querying
5. Query stored traces
6. Verify event matches
7. Call `trace_store.close()` at the end of the test

**Scope**: ~55 lines, 1-2 integration tests.

```python
@pytest.mark.asyncio
async def test_trace_emit_to_store_e2e():
    # Setup
    trace_store = PostgresTraceStore(dsn="...")
    await trace_store.initialize()

    router = MemoryRouter(trace_store=trace_store)
    emitter = TraceEmitter(memory_router=router)

    # Emit (fire-and-forget; await the stored task handle deterministically
    # rather than guessing with a sleep)
    await emitter.emit_trace({"event_type": "test", "data": {"key": "value"}})
    await emitter._last_trace_task

    # Query
    traces = await trace_store.query_traces({"event_type": "test"})

    # Verify
    assert len(traces) == 1
    assert traces[0]["data"]["key"] == "value"

    # Teardown
    await trace_store.close()
```

After creating:
```powershell
python -m pytest tests/test_postgres_trace_store_integration.py -v
```

Expected: passes (if Postgres available), skips cleanly otherwise.

---

## S5 — Baseline Reconciliation

### S5.1: Run Full Test Suite

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Expected: ~1181 passed, 56 skipped (+15 from new trace store tests: 13 unit + 2 integration), **assuming a live Postgres test fixture is available**.

**If no Postgres fixture is available in the test environment**: expect the Postgres-dependent subset (11 of the 13 unit tests, plus both integration tests — 13 tests total) to **skip**, not pass. Only the 2 backend-independent unit tests (`test_emit_trace_with_no_trace_store`, `test_emit_trace_swallows_store_failure`) will pass without Postgres. In that case the realistic expectation is **1168 passed, 69 skipped** (56 existing + 13 new skips). Confirm which scenario applies *before* running S5.1, and use the matching numbers above so a skip-driven count doesn't get misread as a regression.

**Baseline check**: PLANS.md expects 1166 baseline + 15 new = **1181 total** (live-Postgres scenario) or **1166 + 2 = 1168 passed / +13 skipped** (no-Postgres scenario). If only 1 (not 2) integration test ends up written, both totals shift down by 1 per OR17 baseline reconciliation.

If count differs from whichever scenario applies:
- ✅ Within ±5: acceptable, note delta in CHANGELOG
- ❌ Outside ±5: investigate pre-existing changes, STOP if unclear

---

## Closing — Run `/jarvis-close`

Per AI_HANDOFF.md's Devin Plan Template, run the workflow — it handles the test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md (if a new pattern was captured), rule proposal (C9), docs commit, push, and post-push verification (OR9-OR11). Do not hand-roll the equivalent git/test/push sequence inline — `.windsurf/workflows/jarvis-close.md` is the single source of truth for this sequence. If the workflow is missing or fails, STOP and report.

Files expected to be staged by the workflow: `memory/postgres_trace_store.py`, `memory/__init__.py`, `memory/router.py`, `core/observability.py`, `tests/test_postgres_trace_store.py`, `tests/test_postgres_trace_store_integration.py`.

---

## Expected Outcomes

### Code Changes
- **New**: `memory/postgres_trace_store.py` (~200 lines)
- **New**: `tests/test_postgres_trace_store.py` (~160 lines)
- **New**: `tests/test_postgres_trace_store_integration.py` (~55 lines)
- **Modified**: `memory/__init__.py` (+2 lines)
- **Modified**: `memory/router.py` (+8 lines)
- **Modified**: `core/observability.py` (+20 lines — includes fire-and-forget wrapper + WARNING log per AR18)

### Test Changes
- **Tests**: +15 (13 unit + 2 integration), of which 13 are Postgres-dependent and may report as skipped rather than passed depending on test-fixture availability (see S5.1)
- **Baseline**: 1166 → 1181 passed (live-Postgres scenario) or 1166 → 1168 passed / +13 skipped (no-Postgres scenario)
- **Status**: see S5.1 for the scenario-dependent expected split

### Static Analysis
- **Ruff**: 0 errors (file-scoped cleanup)
- **Mypy**: 277 → 282-287 errors (+5-10 acceptable for Postgres typing)
- **Bandit**: 3179 low (no new security issues)
- **pip-audit**: 19 CVEs (no new dependencies expected beyond `asyncpg`, which should already be in `requirements.txt` — verify)

### Architectural Impact
- ✅ MemoryRouter extended with optional trace_store backend
- ✅ TraceEmitter routes to Postgres when available (graceful degradation), via the constructor-injected instance method only (AR11)
- ✅ All trace storage async; the persistence call itself is fire-and-forget so it never blocks the emission path (AR12)
- ✅ Store-call failures are caught and logged at WARNING, never silently swallowed bare (AR18)
- ✅ AR1-AR4 compliant (core/memory separation maintained)
- ✅ AR10 compliant (memory access via MemoryRouter)

---

## Success Criteria

✅ Plan 61 is complete when:
1. All file edits finish syntax-clean (S1-S5)
2. All ruff/mypy errors fixed (or acceptable within baseline)
3. Full test suite passes per whichever S5.1 scenario applies (live-Postgres or no-Postgres), with the actual numbers reconciled against PLANS.md per OR17
4. Integration test passes (or skips cleanly, per S4.1): trace emit → store → query works end-to-end
5. Git tag `prompt-61` created and pushed to origin
6. CHANGELOG updated with Plan 61 entry, including which S5.1 scenario applied
7. PLANS.md updated: completed prompts row, baseline, queue shift

**Gate**: Full test suite passes (accounting for the Postgres-availability scenario). Postgres connection pooling and teardown verified. Trace store receives events from measurement layer without blocking emission, and degrades gracefully on backend absence or failure.

---

## Notes

- **Postgres dependency**: Requires `asyncpg` in `requirements.txt` (likely already there; verify). Do not introduce `psycopg`/`psycopg_pool` — this plan standardizes on `asyncpg` throughout.
- **Connection string**: Use environment variable or config file (not hardcoded)
- **Pool size**: Default 10; adjust if needed per deployment context
- **Graceful degradation**: Trace storage optional; system works without Postgres, and continues working if Postgres is present but a write fails mid-session (AR18-compliant catch + WARNING log)
- **Non-blocking storage**: The store call runs as a background task (`asyncio.create_task`), not an inline `await` in the emission path
- **Datetime**: All timestamps use `datetime.now(timezone.utc)` (OR20)
- **AR11**: All `TraceEmitter` wiring in this plan uses the constructor-injected instance, never the deprecated global `emit_trace()` function

---

**Plan created**: 2026-06-23
**Target execution**: Next available Devin session
**Estimated duration**: 2-3 hours (including tests)
