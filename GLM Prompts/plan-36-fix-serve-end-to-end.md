# Plan 36: Fix `jarvis serve` end-to-end (F1, F2, F3, F5)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat ed288ca..HEAD -- cli/main.py core/memory_router.py cli/serve.py core/orchestrator.py`
> If any of these files changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (35.6f fixed F4; this plan fixes the remaining 4 regressions)
- **Planned at**: commit `ed288ca`, 2026-06-18
- **In scope**: `cli/main.py`, `core/memory_router.py`, `cli/serve.py`, `core/orchestrator.py`, `tests/test_orchestrator.py`, `tests/test_serve.py`
- **Out of scope**: F6 (MemoryRouter call-signature mismatch across 15+ files — Plan 37), F7 (trace spam — Plan 38), llama_cpp CI ignore (Plan 38.5), ruff/mypy triage (Plans 39-40)

## Why this matters

`jarvis serve` is non-functional. Four bugs from the 35.6b regression are still open after 35.6c, 35.6d, and 35.6f:

- **F1**: `jarvis serve` crashes with "Got unexpected extra argument (serve)" because `typer.run(serve)` re-parses `sys.argv` which still contains `serve`.
- **F2**: `MemoryRouter(postgres_backend=...)` crashes with `TypeError: missing required positional argument 'backends'` because the 35.6c fix added the `postgres_backend` kwarg but kept `backends` required. This breaks `cli/tui.py:266` and `cli/rich_cli.py:83` whenever `SOVEREIGN_DB_DSN` is set.
- **F3**: `cli/serve.py:58` passes `backends=[]` (a list) where `MemoryRouter` expects a dict. Every `self.backends.items()` call throws `AttributeError`. 35.6f hit this bug in the integration test and fixed it in the test, but not in `cli/serve.py`.
- **F5**: `web/server.py:110` calls `orchestrator.list_workers()` which doesn't exist on `Orchestrator`. 35.6d plan listed this as Bug 7 but the delivered prompt relabelled Bug 7 to "removed unused Layer import" — the original Bug 7 was never done.

After this plan, `jarvis serve` starts without crashing, accepts task submissions, and returns worker listings. The foundation is solid.

## Current state

### F1 — `cli/main.py:19-27`

```python
def main() -> None:
    """Main entry point."""
    # Check if user is calling 'serve' command
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Import and call the serve function directly
        from cli.serve import serve
        # Use typer to run the serve command
        import typer
        typer.run(serve)
        return
```

Problem: `typer.run(serve)` calls `serve` via typer's argument parser, which reads `sys.argv`. `sys.argv` is still `['jarvis', 'serve', '--port', '7001']` (or similar). Typer sees `serve` as a positional argument that `serve()` doesn't accept → exit code 2.

### F2 — `core/memory_router.py:164-174`

```python
    def __init__(
        self,
        backends: dict[str, MemoryBackend],
        emitter: "TraceEmitter | None" = None,
        compactor: "MemoryCompactor | None" = None,
        postgres_backend: MemoryBackend | None = None,
    ) -> None:
        """Initialize the memory router with backends.
        ...
        """
        # Convert postgres_backend to backends dict if provided
        if postgres_backend is not None:
            backends = backends.copy()
            backends["postgres"] = postgres_backend
        self.backends = backends
```

Problem: `backends` has no default. Call sites in `cli/tui.py:266` and `cli/rich_cli.py:83` pass `MemoryRouter(postgres_backend=PostgresBackend(...))` without `backends=`. At runtime: `TypeError: __init__() missing 1 required positional argument: 'backends'`. The `.copy()` call on line 172 also crashes if `backends` is `None`.

### F3 — `cli/serve.py:58`

```python
    # Create base dependencies
    memory_router = MemoryRouter(backends=[], emitter=emitter)
```

Problem: `backends` is typed `dict[str, MemoryBackend]`. Passing `[]` (a list) works at construction (Python doesn't enforce types) but every subsequent `self.backends.items()` call in `MemoryRouter.fetch()`, `.write()`, `.list_keys()` throws `AttributeError: 'list' object has no attribute 'items'`. 35.6f's integration test hit this exact bug and fixed it in the test with `backends={}`, but did not fix the production call site.

### F5 — `core/orchestrator.py` (after `list_tasks` at line 659)

```python
    async def list_tasks(self) -> list[Task]:
        """
        Return list of tasks in the orchestrator.
        ...
        """
        if hasattr(self, "_active_tasks"):
            return self._active_tasks
        return []
```

`web/server.py:110` calls `orchestrator.list_workers()` which doesn't exist. The `hasattr` guard in `web/server.py:109` means the endpoint returns `{"workers": []}` silently — no error, but no data either. The method needs to exist and return real worker info.

`WorkerProfile` schema (`core/schemas.py:156-170`) has: `worker_id`, `worker_type`, `depth_preference`, `preferred_model`, `capabilities`, `preferred_complexity`, `tasks_completed`, `avg_confidence`. The `list_workers()` return shape should expose the useful subset.

## What to change

### Step 1 — Fix F1: strip `serve` from `sys.argv` before `typer.run`

**File**: `cli/main.py`
**Lines**: 19-27 (the serve dispatch block)

Replace:
```python
def main() -> None:
    """Main entry point."""
    # Check if user is calling 'serve' command
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Import and call the serve function directly
        from cli.serve import serve
        # Use typer to run the serve command
        import typer
        typer.run(serve)
        return
```

With:
```python
def main() -> None:
    """Main entry point."""
    # Check if user is calling 'serve' command
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Strip the 'serve' subcommand from argv so typer.run only sees options
        # (--host, --port, --reload). Without this, typer sees 'serve' as a
        # positional argument and crashes with "Got unexpected extra argument".
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from cli.serve import serve
        import typer
        typer.run(serve)
        return
```

**Why this approach**: `typer.run(serve)` uses typer's argument parser, which reads `sys.argv`. Stripping `serve` from position 1 leaves `[jarvis, --port, 7001]` which typer parses correctly against `serve()`'s `--host/--port/--reload` options. This is the minimal fix — no refactor of `serve()`'s signature, no switch from argparse to typer for the rest of the CLI.

### Step 2 — Fix F2: make `backends` optional in `MemoryRouter.__init__`

**File**: `core/memory_router.py`
**Lines**: 164-174

Replace:
```python
    def __init__(
        self,
        backends: dict[str, MemoryBackend],
        emitter: "TraceEmitter | None" = None,
        compactor: "MemoryCompactor | None" = None,
        postgres_backend: MemoryBackend | None = None,
    ) -> None:
        """Initialize the memory router with backends.

        Args:
            backends: Dictionary of backend name to backend instance
            emitter: Trace emitter for events
            compactor: Optional memory compactor for tiered memory management
            postgres_backend: Optional single postgres backend (converted to backends dict for compatibility)
        """
        # Convert postgres_backend to backends dict if provided
        if postgres_backend is not None:
            backends = backends.copy()
            backends["postgres"] = postgres_backend
        self.backends = backends
```

With:
```python
    def __init__(
        self,
        backends: dict[str, MemoryBackend] | None = None,
        emitter: "TraceEmitter | None" = None,
        compactor: "MemoryCompactor | None" = None,
        postgres_backend: MemoryBackend | None = None,
    ) -> None:
        """Initialize the memory router with backends.

        Args:
            backends: Dictionary of backend name to backend instance. Optional;
                      defaults to empty dict. If postgres_backend is also
                      provided, it is added under the "postgres" key.
            emitter: Trace emitter for events
            compactor: Optional memory compactor for tiered memory management
            postgres_backend: Optional single postgres backend (converted to backends dict for compatibility)
        """
        backends = backends or {}
        if postgres_backend is not None:
            backends = backends.copy()
            backends["postgres"] = postgres_backend
        self.backends = backends
```

**Why `backends or {}` and not `backends = backends if backends is not None else {}`**: They're equivalent for this use case. `or {}` is the existing codebase idiom (see `core/orchestrator.py:57`: `self._emitter = emitter or MemoryTraceEmitter()`). Match the surrounding style.

**Call sites that now work**:
- `cli/tui.py:266`: `MemoryRouter(postgres_backend=PostgresBackend(...))` — `backends` defaults to `{}`, then `postgres_backend` is added.
- `cli/rich_cli.py:83`: same.
- `cli/serve.py:58`: `MemoryRouter(backends=[], emitter=emitter)` — wait, this passes a list, not a dict. That's F3. Fix in Step 3.

### Step 3 — Fix F3: change `backends=[]` to `backends={}` in `cli/serve.py`

**File**: `cli/serve.py`
**Line**: 58

Replace:
```python
    memory_router = MemoryRouter(backends=[], emitter=emitter)
```

With:
```python
    memory_router = MemoryRouter(backends={}, emitter=emitter)
```

**Why not just `MemoryRouter(emitter=emitter)`** (relying on the F2 fix to default `backends` to `{}`): Explicit is better than implicit here. The serve entry point is the one place where an empty router is intentional (no persistent backends configured), and making that visible in the call site helps the next reader. Two characters (`[]` → `{}`) is the minimal change.

### Step 4 — Fix F5: add `list_workers()` to `Orchestrator`

**File**: `core/orchestrator.py`
**Insert after**: the `list_tasks` method (after line 668, before `submit_subtask` or wherever the class ends — check the live file)

Add:
```python
    async def list_workers(self) -> list[dict]:
        """
        Return list of registered workers with their profile metadata.

        Returns:
            List of dicts, one per registered worker, with keys:
            worker_id, worker_type, capabilities, preferred_model,
            preferred_complexity, tasks_completed, avg_confidence.
            Workers without a profile return a minimal dict with just worker_id.
        """
        result = []
        for worker_id, worker in self.workers.items():
            profile = getattr(worker, "profile", None)
            if profile is None:
                result.append({"worker_id": worker_id})
                continue
            result.append({
                "worker_id": worker_id,
                "worker_type": getattr(profile, "worker_type", "unknown"),
                "capabilities": getattr(profile, "capabilities", []),
                "preferred_model": getattr(profile, "preferred_model", None),
                "preferred_complexity": getattr(profile, "preferred_complexity", 0.5),
                "tasks_completed": getattr(profile, "tasks_completed", 0),
                "avg_confidence": getattr(profile, "avg_confidence", 0.0),
            })
        return result
```

**Why `getattr` with defaults**: `WorkerProfile` is a Pydantic BaseModel with all fields defined, so direct attribute access would work for conformant profiles. But `OllamaWorker` accepts `profile=None` and constructs a default internally; other worker subclasses might not set every field. `getattr` with defaults is defensive and matches the `hasattr` pattern already in `web/server.py:109`. It costs nothing and prevents a `list_workers()` call from crashing the web endpoint if a worker has a non-standard profile.

**Why return `list[dict]` not `list[WorkerProfile]`**: the web endpoint serializes this to JSON. Pydantic models serialize, but `dict` is the lingua franca for JSON responses and doesn't require `.model_dump()` at the call site. `web/server.py:111` does `return {"workers": workers}` — FastAPI's `JSONResponse` handles `list[dict]` natively.

### Step 5 — Add test for `list_workers()`

**File**: `tests/test_orchestrator.py`
**Insert after**: the existing `test_list_tasks_returns_list` test (search for it)

Add:
```python
    @pytest.mark.asyncio
    async def test_list_workers_returns_registered_workers(self, orchestrator, memory_router):
        """Test that list_workers returns a list of dicts with worker metadata."""
        # Register a worker first
        profile = WorkerProfile(
            worker_id="test_worker",
            worker_type="test",
            depth_preference=0.5,
            speculation_tolerance=0.5,
            source_skepticism=0.5,
            verbosity=0.5,
            preferred_model="mock-model",
            escalation_threshold=0.8,
            capabilities=["test", "general"],
            preferred_complexity=0.5,
        )
        llm = MockLLMAdapter()
        worker = EchoWorker(profile=profile, llm=llm, memory_router=memory_router)
        orchestrator.register_worker("test_worker", worker)

        # Call list_workers
        workers = await orchestrator.list_workers()

        # Assert returns a list with one entry
        assert isinstance(workers, list)
        assert len(workers) == 1

        # Assert the worker dict has expected fields
        w = workers[0]
        assert w["worker_id"] == "test_worker"
        assert w["worker_type"] == "test"
        assert "test" in w["capabilities"]
        assert w["preferred_model"] == "mock-model"

    @pytest.mark.asyncio
    async def test_list_workers_returns_empty_list_when_no_workers(self, orchestrator):
        """Test that list_workers returns empty list when no workers registered."""
        workers = await orchestrator.list_workers()
        assert isinstance(workers, list)
        assert len(workers) == 0
```

### Step 6 — Add test for F1 (serve subcommand dispatch)

**File**: `tests/test_main.py`
**Append**:

```python
def test_serve_subcommand_strips_serve_from_argv():
    """Test that 'jarvis serve' dispatches to serve() without typer crashing on the 'serve' arg.

    Regression test for F1: typer.run(serve) was re-parsing sys.argv which still
    contained 'serve', causing 'Got unexpected extra argument (serve)' exit code 2.
    """
    import sys
    with patch('cli.serve.serve') as mock_serve:
        with patch('typer.run') as mock_typer_run:
            original_argv = sys.argv
            try:
                sys.argv = ['jarvis', 'serve', '--port', '7001']
                from cli.main import main
                main()
                # typer.run should have been called (meaning serve was dispatched)
                mock_typer_run.assert_called_once()
                # After main() returns, sys.argv should have 'serve' stripped
                # (sys.argv is mutated in-place by the fix)
                assert 'serve' not in sys.argv[1:], f"serve should be stripped from argv, got {sys.argv}"
            finally:
                sys.argv = original_argv
```

### Step 7 — Add test for F2 (MemoryRouter with postgres_backend only)

**File**: `tests/test_memory_router.py`
**Append to `TestMemoryRouter` class**:

```python
    def test_memory_router_with_only_postgres_backend(self, mock_backend):
        """Test that MemoryRouter can be constructed with postgres_backend and no backends arg.

        Regression test for F2: backends was required positional, so
        MemoryRouter(postgres_backend=...) crashed with TypeError.
        """
        router = MemoryRouter(postgres_backend=mock_backend)
        assert "postgres" in router.backends
        assert router.backends["postgres"] == mock_backend
        assert len(router.backends) == 1

    def test_memory_router_with_no_backends_at_all(self):
        """Test that MemoryRouter can be constructed with no backends at all."""
        router = MemoryRouter()
        assert router.backends == {}
        assert len(router.backends) == 0
```

## Verification gates (run in order, all must pass)

### Gate 1 — Unit tests for changed files

```bash
python -m pytest tests/test_orchestrator.py tests/test_main.py tests/test_memory_router.py tests/test_serve.py -v --tb=short
```

**Expected**: All tests pass. New tests `test_list_workers_returns_registered_workers`, `test_list_workers_returns_empty_list_when_no_workers`, `test_serve_subcommand_strips_serve_from_argv`, `test_memory_router_with_only_postgres_backend`, `test_memory_router_with_no_backends_at_all` all pass. Existing tests still pass. Zero failures.

If any pre-existing test fails (other than the known flaky `test_lm_studio_adapter.py::test_health_check_without_server`), STOP and report.

### Gate 2 — F1 functional verification

```bash
python -c "
import sys
sys.argv = ['jarvis', 'serve', '--port', '17001']
from cli.main import main
try:
    main()
except SystemExit as e:
    if e.code == 0 or e.code is None:
        print('F1 PASS: jarvis serve dispatched without typer error')
    else:
        print(f'F1 FAIL: SystemExit code {e.code}')
        sys.exit(1)
"
```

**Expected**: Prints `F1 PASS: jarvis serve dispatched without typer error`. The serve process will start (uvicorn); you'll need Ctrl+C to stop it. The PASS message prints before uvicorn binds, so you should see it. If you see `Got unexpected extra argument (serve)`, F1 is not fixed — STOP.

Note: this gate starts a real server. Run it in a terminal you can Ctrl+C. Alternatively, mock `uvicorn.run` and just verify dispatch:

```bash
python -c "
import sys
from unittest.mock import patch
sys.argv = ['jarvis', 'serve', '--port', '17001']
with patch('cli.serve.uvicorn.run'):
    with patch('cli.serve.asyncio.run') as mock_aio:
        mock_aio.return_value = 'test-token'
        with patch('cli.serve.AuthManager'):
            from cli.main import main
            try:
                main()
                print('F1 PASS: dispatched without typer error')
            except SystemExit as e:
                print(f'F1 FAIL: SystemExit {e.code}'); sys.exit(1)
"
```

Use the mocked version for CI; use the real version for manual verification.

### Gate 3 — F2 functional verification

```bash
python -c "
from core.memory_router import MemoryRouter
# F2: postgres_backend without backends= should not crash
mr = MemoryRouter(postgres_backend='fake_backend')
assert 'postgres' in mr.backends
assert mr.backends['postgres'] == 'fake_backend'
print('F2 PASS: MemoryRouter(postgres_backend=...) works')
# Also verify no-args construction
mr2 = MemoryRouter()
assert mr2.backends == {}
print('F2 PASS: MemoryRouter() with no args works')
"
```

**Expected**: Both PASS lines print. If `TypeError: missing required positional argument 'backends'`, F2 is not fixed — STOP.

### Gate 4 — F3 functional verification

```bash
python -c "
from core.memory_router import MemoryRouter
from core.observability import MemoryTraceEmitter
# F3: serve.py's MemoryRouter(backends={}) should not crash on .items()
mr = MemoryRouter(backends={}, emitter=MemoryTraceEmitter())
assert hasattr(mr.backends, 'items'), 'backends must be a dict, not a list'
print('F3 PASS: backends is a dict with .items() method')
"
```

**Expected**: Prints `F3 PASS`. If `AttributeError: 'list' object has no attribute 'items'`, F3 is not fixed — STOP.

### Gate 5 — F5 functional verification

```bash
python -c "
import asyncio
from core.orchestrator import Orchestrator
from core.memory_router import MemoryRouter
from core.observability import MemoryTraceEmitter
from workers.echo_worker import EchoWorker, MockLLMAdapter
from core.schemas import WorkerProfile

mr = MemoryRouter(backends={}, emitter=MemoryTraceEmitter())
orch = Orchestrator(memory_router=mr, emitter=MemoryTraceEmitter())

# Register a worker
profile = WorkerProfile(
    worker_id='test', worker_type='test', depth_preference=0.5,
    speculation_tolerance=0.5, source_skepticism=0.5, verbosity=0.5,
    preferred_model='mock', escalation_threshold=0.8, capabilities=['test'],
)
worker = EchoWorker(profile=profile, llm=MockLLMAdapter(), memory_router=mr)
orch.register_worker('test', worker)

workers = asyncio.run(orch.list_workers())
assert isinstance(workers, list)
assert len(workers) == 1
assert workers[0]['worker_id'] == 'test'
assert workers[0]['worker_type'] == 'test'
print('F5 PASS: list_workers returns', workers)
"
```

**Expected**: Prints `F5 PASS: list_workers returns [...]` with the worker dict. If `AttributeError: 'Orchestrator' object has no attribute 'list_workers'`, F5 is not fixed — STOP.

### Gate 6 — Full test suite

```bash
python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py --ignore=tests/test_anthropic_adapter.py --ignore=tests/test_gemini_adapter.py --ignore=tests/test_postgres_backend.py --ignore=tests/test_qdrant_backend.py --tb=short
```

**Expected**: All tests pass except known environment-specific failures (missing optional deps: `pynvml`, `icalendar`, `faster_whisper`, `asyncpg`, `qdrant-client`). The 5 new tests added in Steps 5-7 all pass. Test count increases by 5 from the pre-plan baseline.

If you're running on Windows with all deps installed, the only acceptable failure is the pre-existing flaky `test_lm_studio_adapter.py::test_health_check_without_server`.

### Gate 7 — Lint and type check on changed files

```bash
ruff check cli/main.py core/memory_router.py cli/serve.py core/orchestrator.py tests/test_orchestrator.py tests/test_main.py tests/test_memory_router.py
mypy core/memory_router.py core/orchestrator.py --ignore-missing-imports
```

**Expected**: Zero errors on both. If ruff flags unused imports from the changes, remove them. If mypy flags type errors introduced by the changes, fix them. Pre-existing ruff/mypy errors in these files (there are some — see Plan 39/40) are out of scope; only fix errors introduced by this plan's changes.

## STOP conditions

- **If Gate 1 reveals pre-existing test failures unrelated to this plan**, stop and report. Do not try to fix them as part of this plan.
- **If a file outside the in-scope list needs editing**, stop and report. The in-scope list is: `cli/main.py`, `core/memory_router.py`, `cli/serve.py`, `core/orchestrator.py`, `tests/test_orchestrator.py`, `tests/test_main.py`, `tests/test_memory_router.py`. No other files.
- **If any fix requires more than 30 lines of new code** (excluding tests), stop — the plan was underscoped. The four fixes should be ~20 lines of production code total.
- **If `cli/tui.py` or `cli/rich_cli.py` need changes**, stop. F2 should make them work without modification (they already call `MemoryRouter(postgres_backend=...)` correctly once `backends` is optional). If they don't work after F2, the bug is elsewhere — report it.
- **If `web/server.py` needs changes**, stop. F5 adds the method that `web/server.py:110` already calls. The web server's `hasattr` guard means it works whether or not the method exists, but the method should exist after this plan. No changes to `web/server.py` are in scope.

## Out of scope

The following are NOT fixed by this plan. They are queued for future plans:

- **F6** — MemoryRouter call-signature mismatch across 15+ files (Plan 37). The `fetch(dict, collection=...)` / `write(dict, document_id=...)` pattern in `rating_system.py`, `evaluator.py`, `instruction_generator.py`, `instruction_versioning.py`, `orchestrator_improvement.py`, `trace_optimiser.py`, `worker_factory.py`, `worker_persistence.py`, `scratchpad.py`, `resource_manager.py`, `retention.py`. These will be fixed by extending `MemoryRouter` with `fetch_by_filter()` and `write_to_collection()` methods.
- **F7** — Trace spam from `WorkerBase` defaulting to `ConsoleTraceEmitter` (Plan 38).
- **llama_cpp CI ignore** — `.github/workflows/ci.yml` runs `pytest tests/ -v` without `--ignore=tests/test_llama_cpp_adapter.py`. The test file cannot be collected without `llama_cpp` installed. Fix: add `pytest.importorskip("llama_cpp")` at the top of `tests/test_llama_cpp_adapter.py` (Plan 38.5).
- **ruff/mypy triage** — 365 ruff errors and 116 mypy errors across the codebase (Plans 39-40).
- **InputSanitiser wiring** — built but never called from WebScraper, TelegramGateway, or QueryHandler. Clean Architecture Rule 13 violation (queued).
- **WorkerFactory wiring** — constructed in `cli/serve.py` but never called to create workers. The OllamaWorker registered in 35.6f bypasses the factory. Wiring the factory is a larger change that depends on F6 being fixed first (WorkerFactory calls MemoryRouter with the wrong signature).

## Closing steps (after all gates pass)

1. `git add cli/main.py core/memory_router.py cli/serve.py core/orchestrator.py tests/test_orchestrator.py tests/test_main.py tests/test_memory_router.py`
2. `git commit -m "fix: F1 F2 F3 F5 — jarvis serve end-to-end"`
3. `git tag prompt-36`
4. `git show prompt-36 --stat` — verify file list matches the in-scope list. If unexpected file appears, `git tag -d prompt-36`, clean, re-tag.
5. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail (what changed on each line)
   - **Implementation Notes**: any mid-prompt failures and how resolved (if none, say "none")
   - **Testing Results**: baseline → final test count, with exact command used
   - **Verification Gate Output**: literal output of each gate (at least Gates 2-5)
6. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Move F1, F2, F3, F5 from "What's broken" to a "Recently fixed" subsection (delete after one prompt)
   - Update "What works right now" to add: `jarvis serve` (starts FastAPI server, accepts task submissions, returns worker listings)
7. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
8. `git commit -m "docs: prompt-36 changelog and handoff update"`
9. `git push origin master && git push origin prompt-36`
