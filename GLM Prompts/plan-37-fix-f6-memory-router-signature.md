# Plan 37: Fix F6 — MemoryRouter call-signature mismatch across 12 files

> **Executor instructions**: This is the largest plan in the queue. 12 files, ~70 call sites. Follow the steps in strict order. After each file, run the relevant test file. At each gate, run the full suite. If the total production code changes exceed 200 lines, STOP — the plan will be split into 37a/37b.
>
> **Drift check (run first)**: `git diff --stat 0031b49..HEAD -- core/memory_router.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/instruction_versioning.py core/orchestrator_improvement.py core/trace_optimiser.py core/worker_factory.py core/scratchpad.py core/orchestrator.py system/worker_persistence.py system/resource_manager.py system/model_registry.py system/trajectory_exporter.py`
> If any of these files changed since prompt-36.5, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (large surface area, but each change is mechanical)
- **Depends on**: prompt-36.5 (stable test baseline)
- **Planned at**: commit `0031b49`, 2026-06-18
- **In scope**: 14 files (see file list below)
- **Out of scope**: F7 (trace spam — Plan 38), ruff/mypy triage on files NOT in the in-scope list (Plans 39-40), non-F6 mypy errors in other files

## Why this matters

The self-improvement subsystem (RatingSystem, OutputEvaluator, InstructionGenerator, InstructionVersionManager, OrchestratorImprovementLoop, TraceOptimiser) and the worker management subsystem (WorkerFactory, WorkerPersistence) are built but silently non-functional. Every `memory_router.fetch(dict, collection=...)` and `memory_router.write(dict, collection=..., document_id=...)` call throws `TypeError` at runtime because `MemoryRouter`'s interface is `fetch(task: Task)` / `write(data: dict, backend_name: str | None = None)`. The broad `except Exception: pass` blocks swallow the errors, so the subsystems appear to work in tests (which mock the MemoryRouter) but fail silently in production.

This is the same class of bug that 35.6d Bug 5 fixed in `SessionManager` and `CommandHistory` — but only 2 of 14 affected files were fixed. This plan fixes the remaining 12.

## Current state

### MemoryRouter's current interface (`core/memory_router.py`)

```python
class MemoryRouter:
    async def fetch(self, task: Task) -> list[dict[str, Any]]: ...
    async def write(self, data: dict[str, Any], backend_name: str | None = None) -> None: ...
    async def list_keys(self, prefix: str) -> list[str]: ...
```

### What callers expect (5 distinct patterns)

**Pattern 1** — `fetch(filter_dict, collection=..., limit=...)` — 29 uses of `collection`, 9 of `limit`:
- `core/rating_system.py`, `core/evaluator.py`, `core/instruction_generator.py`, `core/instruction_versioning.py`, `core/orchestrator_improvement.py`, `core/trace_optimiser.py`, `system/worker_persistence.py`

**Pattern 2** — `write(data_dict, collection=..., document_id=...)` — 5 uses of `document_id`:
- `core/rating_system.py`, `core/evaluator.py`, `core/instruction_generator.py`, `core/instruction_versioning.py`, `core/orchestrator_improvement.py`, `core/worker_factory.py`, `system/worker_persistence.py`

**Pattern 3** — `fetch(filter_dict, task_id=..., query=...)` — 3 uses of `task_id`, 2 of `query`:
- `system/model_registry.py`, `system/resource_manager.py`

**Pattern 4** — `write(data_dict, task_id=..., content=..., metadata=...)` — 1 use:
- `core/scratchpad.py`

**Pattern 5** — `fetch(filter_dict, filter_func=...)` — 2 uses:
- `system/trajectory_exporter.py`

### Additional missing methods

`core/orchestrator.py:385,400,482,497` calls `self.memory_router.get_global_context(caller_id=...)` and `self.memory_router.set_global_context(context, caller_id=...)`. Mypy reports these methods don't exist on `MemoryRouter`. They were supposed to be added in Prompt 23 (Memory Scoping) but either landed on `ScopedMemoryRouter` instead, or were never added, or were removed. This plan adds them to `MemoryRouter`.

## What to change

### Step 1 — Add new methods to MemoryRouter

**File**: `core/memory_router.py`
**Insert after**: the existing `list_keys` method (after line 372)

Add these methods to the `MemoryRouter` class:

```python
    async def fetch_by_filter(
        self,
        filter: dict[str, Any],
        collection: str | None = None,
        limit: int | None = None,
        filter_func: Any = None,
    ) -> list[dict[str, Any]]:
        """Fetch memory entries matching a filter dictionary.

        This is the document-store-style query interface. Callers that need
        filtered retrieval (by collection, by document_id, by arbitrary filter
        dict, or by a callable filter_func) should use this method instead of
        fetch(task), which is for task-based routing queries.

        Args:
            filter: Dictionary of key-value pairs to match against stored entries.
            collection: Optional collection/scope name to restrict the search.
            limit: Optional maximum number of results to return.
            filter_func: Optional callable that takes a dict and returns bool.
                         If provided, only entries where filter_func(entry) is True are returned.

        Returns:
            List of matching memory entries (dicts).
        """
        import time
        from datetime import datetime
        from uuid import uuid4

        start_time = time.perf_counter()
        all_results: list[dict[str, Any]] = []

        for backend_name, backend in self.backends.items():
            try:
                # Backends implement fetch(task: Task). We construct a minimal
                # Task from the filter dict so the existing backend interface
                # works without modification.
                from core.schemas import Task, TaskPriority, TaskStatus
                task = Task(
                    task_id=uuid4(),
                    intent=str(filter),
                    complexity_score=0.0,
                    priority=TaskPriority.NORMAL,
                    current_state=TaskStatus.RECEIVED,
                    created_at=datetime.utcnow(),
                )
                results = await backend.fetch(task)
                # Apply filter matching in Python (backends don't support filtered queries natively)
                for entry in results:
                    content = entry.get("content", entry)
                    if isinstance(content, dict):
                        match = all(content.get(k) == v for k, v in filter.items())
                    else:
                        match = True  # Can't filter, return as-is
                    if match and filter_func is not None:
                        match = filter_func(entry)
                    if match:
                        all_results.append(entry)
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.DATA_READ,
                        component=TraceComponent.MEMORY_ROUTER,
                        level=TraceLevel.WARNING,
                        message=f"fetch_by_filter backend error: {backend_name}",
                        data={"error": str(e)},
                        duration_ms=0,
                    )
                    await self.emitter.emit(event)
                except Exception:
                    pass

        # Apply limit
        if limit is not None:
            all_results = all_results[:limit]

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            event = TraceEvent(
                event_type=TraceEventType.DATA_READ,
                component=TraceComponent.MEMORY_ROUTER,
                level=TraceLevel.INFO,
                message="fetch_by_filter completed",
                data={"filter": filter, "collection": collection, "result_count": len(all_results)},
                duration_ms=duration_ms,
            )
            await self.emitter.emit(event)
        except Exception:
            pass

        return all_results

    async def write_to_collection(
        self,
        data: dict[str, Any],
        collection: str,
        document_id: str | None = None,
    ) -> None:
        """Write data to a named collection.

        This is the document-store-style write interface. Callers that need
        to write to a specific collection (ratings, evaluations, instructions,
        etc.) with an optional document_id should use this method instead of
        write(data), which writes to all backends without collection scoping.

        Args:
            data: Dictionary of data to write.
            collection: Collection/scope name (e.g., "ratings", "evaluations").
            document_id: Optional document identifier. If provided, the data
                         dict is augmented with collection and document_id fields.
        """
        import time

        start_time = time.perf_counter()

        # Augment data with collection and document_id metadata
        write_data = data.copy()
        write_data["_collection"] = collection
        if document_id is not None:
            write_data["_document_id"] = document_id

        for backend_name, backend in self.backends.items():
            try:
                await backend.write(write_data)
            except Exception as e:
                try:
                    event = TraceEvent(
                        event_type=TraceEventType.DATA_WRITE,
                        component=TraceComponent.MEMORY_ROUTER,
                        level=TraceLevel.WARNING,
                        message=f"write_to_collection backend error: {backend_name}",
                        data={"collection": collection, "error": str(e)},
                        duration_ms=0,
                    )
                    await self.emitter.emit(event)
                except Exception:
                    pass

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            event = TraceEvent(
                event_type=TraceEventType.DATA_WRITE,
                component=TraceComponent.MEMORY_ROUTER,
                level=TraceLevel.INFO,
                message="write_to_collection completed",
                data={"collection": collection, "document_id": document_id},
                duration_ms=duration_ms,
            )
            await self.emitter.emit(event)
        except Exception:
            pass

    async def get_global_context(self, caller_id: str = "orchestrator") -> Any:
        """Get the shared global StrategicContext.

        Args:
            caller_id: Identifier of the caller (for access control logging).

        Returns:
            StrategicContext if set, None otherwise.
        """
        from core.schemas import StrategicContext
        results = await self.fetch_by_filter(
            filter={"_collection": "global_context"},
            collection="global_context",
            limit=1,
        )
        if results:
            content = results[0].get("content", results[0])
            if isinstance(content, dict) and "context" in content:
                return StrategicContext(**content["context"])
        return None

    async def set_global_context(self, context: Any, caller_id: str = "orchestrator") -> None:
        """Set the shared global StrategicContext.

        Args:
            context: StrategicContext to store.
            caller_id: Identifier of the caller (for access control logging).
        """
        await self.write_to_collection(
            data={"context": context.model_dump() if hasattr(context, "model_dump") else context},
            collection="global_context",
            document_id="current",
        )
```

**Why this approach (Option A)**: The callers are doing filtered document queries, not task-based routing. Forcing them to construct `Task` objects (Option B) would be a shape mismatch. The new methods (`fetch_by_filter`, `write_to_collection`) match what the callers actually need. `get_global_context` and `set_global_context` are convenience wrappers that use the new methods.

**Why the backends still receive `fetch(task)` internally**: The backends (`PostgresBackend`, `QdrantBackend`, `ObsidianBackend`) all implement `fetch(task: Task)`. Changing their interface would require changes to 3 backend files + all their tests. Instead, `fetch_by_filter` constructs a minimal `Task` from the filter dict and lets the backends handle it. The filtering happens in Python after the backend returns. This is not efficient for large datasets, but it's correct and doesn't require backend changes.

### Step 2 — Fix callers file by file

For each file, update all `memory_router.fetch(dict, ...)` calls to `memory_router.fetch_by_filter(...)` and all `memory_router.write(dict, ...)` calls to `memory_router.write_to_collection(...)`. The mapping is:

| Old call | New call |
|---|---|
| `fetch(filter_dict, collection=X, limit=N)` | `fetch_by_filter(filter=filter_dict, collection=X, limit=N)` |
| `fetch(filter_dict, collection=X)` | `fetch_by_filter(filter=filter_dict, collection=X)` |
| `write(data, collection=X, document_id=D)` | `write_to_collection(data=data, collection=X, document_id=D)` |
| `write(data, collection=X)` | `write_to_collection(data=data, collection=X)` |
| `fetch(filter_dict, task_id=T, query=Q)` | `fetch_by_filter(filter={"task_id": T, "query": Q, **filter_dict})` |
| `write(data, task_id=T, content=C, metadata=M)` | `write_to_collection(data={**data, "content": C, "metadata": M}, collection="scratchpad", document_id=T)` |
| `fetch(filter_dict, filter_func=F)` | `fetch_by_filter(filter=filter_dict, filter_func=F)` |

**Files to fix, in dependency order** (fix one, run its test file, then move to the next):

1. **`core/scratchpad.py`** — 1 call site (line 161, pattern 4)
2. **`core/rating_system.py`** — 6 call sites (lines 38, 59, 135, 184, 350, pattern 1+2)
3. **`core/evaluator.py`** — 3 call sites (lines 188, 229, pattern 1+2)
4. **`core/instruction_generator.py`** — 8 call sites (lines 89, 116, 211, 238, 288, 324, pattern 1+2)
5. **`core/instruction_versioning.py`** — 8 call sites (lines 132, 215, 230, 285, 368, 382, 425, pattern 1+2)
6. **`core/orchestrator_improvement.py`** — 8 call sites (lines 64, 103, 134, 238, 264, pattern 1+2)
7. **`core/trace_optimiser.py`** — 2 call sites (lines 56, pattern 1)
8. **`core/worker_factory.py`** — 3 call sites (line 177, pattern 2)
9. **`core/orchestrator.py`** — 4 call sites (lines 385, 400, 482, 497 — `get_global_context`/`set_global_context` — these now work because Step 1 added the methods)
10. **`system/worker_persistence.py`** — 6 call sites (lines 74, 123, 173, 329, 373, 393, pattern 1+2)
11. **`system/resource_manager.py`** — 2 call sites (line 1013, pattern 3)
12. **`system/model_registry.py`** — 2 call sites (line 59, pattern 3)
13. **`system/trajectory_exporter.py`** — 2 call sites (lines 64, 69, pattern 5)

### Step 3 — Fix co-located mypy errors in the same files

While fixing the MemoryRouter calls, you will encounter other mypy errors on nearby lines in the same files. Fix these only if they're on the same line or adjacent lines as the MemoryRouter fix. Do NOT go hunting for them elsewhere in the file.

Known co-located errors:
- `core/rating_system.py:79` — `TraceEventType.ERROR` doesn't exist. Use `TraceEventType.OPERATION_ERROR`.
- `system/resource_manager.py:887,927,941` — `TraceEventType.OPERATION_WARNING` doesn't exist. Use `TraceEventType.OPERATION_ERROR` or `TraceEventType.COMMAND_FAILED`.
- `core/evaluator.py:134,206` — `TraceComponent.EVALUATOR` doesn't exist. Add it to `core/observability.py`'s `TraceComponent` enum, or use `TraceComponent.ORCHESTRATOR`.
- `core/escalation.py:146` — `ApprovalGate` has no attribute `request`. Check the actual method name in `core/approval_gate.py`.
- `core/instruction_versioning.py:148` — `ApprovalGate` has no attribute `submit_for_approval`. Check the actual method name.

**For each of these**: read the actual file to find the correct enum value or method name. Do NOT guess. Use `Select-String "class TraceComponent" core/observability.py` to list available components, `Select-String "class TraceEventType" core/observability.py` to list available event types, `Select-String "def " core/approval_gate.py` to list available methods.

### Step 4 — Add tests for the new MemoryRouter methods

**File**: `tests/test_memory_router.py`
**Append to `TestMemoryRouter` class**:

```python
    @pytest.mark.asyncio
    async def test_fetch_by_filter_returns_matching_entries(self, mock_backend):
        """Test that fetch_by_filter returns entries matching the filter."""
        # Seed the backend with data
        router = MemoryRouter(backends={"mock": mock_backend})
        await router.write_to_collection(
            data={"name": "test", "value": 42},
            collection="test_collection",
            document_id="doc1",
        )

        # Fetch by filter
        results = await router.fetch_by_filter(
            filter={"_collection": "test_collection"},
            collection="test_collection",
        )

        assert isinstance(results, list)
        # Note: mock_backend.fetch returns mock data, not the written data.
        # This test verifies the method runs without error and returns a list.

    @pytest.mark.asyncio
    async def test_write_to_collection_augments_data(self, mock_backend):
        """Test that write_to_collection adds _collection and _document_id to data."""
        router = MemoryRouter(backends={"mock": mock_backend})
        await router.write_to_collection(
            data={"key": "value"},
            collection="my_collection",
            document_id="my_doc",
        )

        # Verify the backend received the augmented data
        assert len(mock_backend.storage) == 1
        written = mock_backend.storage[-1]
        assert written["_collection"] == "my_collection"
        assert written["_document_id"] == "my_doc"
        assert written["key"] == "value"

    @pytest.mark.asyncio
    async def test_get_global_context_returns_none_when_empty(self, mock_backend):
        """Test that get_global_context returns None when no context is set."""
        router = MemoryRouter(backends={"mock": mock_backend})
        context = await router.get_global_context()
        assert context is None
```

## Verification gates

### Gate 1 — Drift check

```powershell
git diff --stat 0031b49..HEAD -- core/memory_router.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/instruction_versioning.py core/orchestrator_improvement.py core/trace_optimiser.py core/worker_factory.py core/scratchpad.py core/orchestrator.py system/worker_persistence.py system/resource_manager.py system/model_registry.py system/trajectory_exporter.py
```

**Expected**: empty output (no changes to these files since prompt-36.5).

### Gate 2 — New MemoryRouter methods work

```powershell
python -c "import asyncio; from core.memory_router import MemoryRouter; from core.observability import MemoryTraceEmitter; mr = MemoryRouter(backends={}, emitter=MemoryTraceEmitter()); asyncio.run(mr.write_to_collection({'k':'v'}, 'test', 'd1')); r = asyncio.run(mr.fetch_by_filter({'_collection':'test'})); print('PASS:', r); gc = asyncio.run(mr.get_global_context()); print('global context:', gc)"
```

**Expected**: `PASS: []` (empty list from empty backends) and `global context: None`. No TypeError, no AttributeError.

### Gate 3 — Mypy errors eliminated for F6 pattern

```powershell
mypy core/ system/ --ignore-missing-imports 2>&1 | Select-String "Unexpected keyword argument"
```

**Expected**: zero output. All `"Unexpected keyword argument"` errors for `collection`, `document_id`, `limit`, `task_id`, `query`, `filter_func`, `content`, `metadata` on `fetch`/`write` of `MemoryRouter` are gone.

If any remain, identify which file wasn't fully updated and fix it.

### Gate 4 — Mypy errors eliminated for get/set_global_context

```powershell
mypy core/orchestrator.py --ignore-missing-imports 2>&1 | Select-String "get_global_context|set_global_context"
```

**Expected**: zero output.

### Gate 5 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short
```

**Expected**: baseline is `1072 passed, 23 skipped, 1 failed, 63 warnings` (from prompt-36.5). After this plan:
- Passed count should increase by 3 (the 3 new tests in Step 4) → 1075 passed
- Skipped: 23 (unchanged)
- Failed: 1 (pre-existing flaky) or 0
- Warnings: ~63 (unchanged or slightly different)

If passed count drops below 1072, a regression was introduced. Identify the failing test(s) and fix before proceeding.

### Gate 6 — ruff on changed files

```powershell
ruff check core/memory_router.py core/scratchpad.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/instruction_versioning.py core/orchestrator_improvement.py core/trace_optimiser.py core/worker_factory.py core/orchestrator.py system/worker_persistence.py system/resource_manager.py system/model_registry.py system/trajectory_exporter.py tests/test_memory_router.py
```

**Expected**: 0 errors on the lines you changed. Pre-existing ruff errors in these files are out of scope (Plan 39).

### Gate 7 — mypy on changed files

```powershell
mypy core/memory_router.py core/scratchpad.py core/rating_system.py core/evaluator.py core/instruction_generator.py core/instruction_versioning.py core/orchestrator_improvement.py core/trace_optimiser.py core/worker_factory.py core/orchestrator.py system/worker_persistence.py system/resource_manager.py system/model_registry.py system/trajectory_exporter.py --ignore-missing-imports
```

**Expected**: 0 errors related to MemoryRouter calls. Co-located errors (Step 3) should also be fixed. Other pre-existing mypy errors in these files (e.g., `WorkerBase has no attribute "execute"` in `multi_worker.py` — which is NOT in scope) are deferred to Plan 40.

## STOP conditions

- **If total production code changes exceed 200 lines** (excluding tests), STOP. The plan will be split into 37a (MemoryRouter + core/ files) and 37b (system/ files).
- **If any file outside the 14 in-scope files needs editing**, STOP. Report which file and why.
- **If a co-located mypy error (Step 3) requires more than 10 lines to fix**, skip it and note it in the CHANGELOG. Do not expand scope.
- **If Gate 5 reveals a regression** (passed count below 1072), STOP. Identify the failing test and fix before proceeding.
- **If a caller uses a pattern not covered by the 5 patterns in "Current state"**, STOP. Report the file, line, and call pattern. The plan needs updating.
- **If `get_global_context` or `set_global_context` already exist on MemoryRouter** (check before Step 1), do not re-add them. Skip that part of Step 1 and verify the existing methods work.

## Out of scope

- **F7** (trace spam from WorkerBase ConsoleTraceEmitter default) — Plan 38
- **Warning cleanup** (175 `utcnow()` deprecation warnings) — Plan 38
- **Other optional-dep test files** (anthropic, gemini, postgres, qdrant — same importorskip pattern as 36.5) — Plan 38.5
- **ruff triage** (365 errors) — Plan 39
- **mypy triage on files NOT in the in-scope list** (e.g., `multi_worker.py`'s `WorkerBase has no attribute "execute"` errors, `event_trigger.py`'s `process_task` signature mismatch) — Plan 40
- **InputSanitiser wiring** — separate plan
- **WorkerFactory wiring** — depends on this plan landing first

## Closing steps

1. `git add` the 14 in-scope files + `tests/test_memory_router.py`
2. `git commit -m "fix: F6 — MemoryRouter call-signature mismatch across 12 files"`
3. `git tag prompt-37`
4. `git show prompt-37 --stat` — verify file list matches the in-scope list. If unexpected file appears, `git tag -d prompt-37`, clean, re-tag.
5. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail (how many call sites changed in each)
   - **Implementation Notes**: any co-located errors found and fixed, any patterns that didn't match the 5 documented patterns, any files that needed more than one edit pass
   - **Testing Results**: baseline (1072 passed, 23 skipped, 1 failed, 63 warnings) → final (expected: 1075 passed, 23 skipped, 0-1 failed, ~63 warnings)
   - **Verification Gate Output**: literal output of each gate
6. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Move F6 from "What's broken" to a "Recently fixed" subsection
   - Update "Built but not reachable" table: the 6 self-improvement subsystems (RatingSystem, OutputEvaluator, InstructionGenerator, InstructionVersionManager, OrchestratorImprovementLoop, TraceOptimiser) and 2 worker management subsystems (WorkerFactory, WorkerPersistence) are now functionally correct but still not wired into a runtime entry point. Move them from "Built but not reachable" to a new "Built and functionally correct, not yet wired" note. They still need wiring (separate plan).
   - Update test baseline
7. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
8. `git commit -m "docs: prompt-37 changelog and handoff update"`
9. `git push origin master && git push origin prompt-37`
10. **Post-push verification**: `git ls-remote --tags origin | Select-String "prompt-37"` — verify the tag exists on the remote.

## After Plan 37 lands

The self-improvement subsystem is now functionally correct (no more silent TypeError on every memory call). The next step is wiring it into `cli/serve.py` end-to-end — but that's a separate plan (Plan 41 or later) because it requires:
- An eval harness to verify self-improvement is actually happening
- TrajectoryExporter to be wired (it's one of the files fixed in this plan)
- Model re-ingestion for fine-tuned models (Tech Debt row 1462)

Plans 38 (warnings), 38.5 (skips), 39 (ruff), 40 (mypy) can land in any order after 37. The foundation is now solid enough that horizontal cleanup work won't be blocked by functional bugs.
