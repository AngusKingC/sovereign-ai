# Plan 63a Context Brief -- Improvement Loop Wire

## What to Review

1. **Scope discipline** -- Does the plan avoid editing `core/orchestrator_improvement.py` (already exists) and `evals/` (already validated)? Only adds wire layer.
2. **Wiring correctness** -- Does `core/orchestrator.py` invoke the improvement loop via the wire module (not directly) after task completion, with fire-and-forget and done callback?
3. **Command type necessity** -- Is adding `IMPROVE` to `CommandType` useful? (Claude: yes, keep both automatic and manual modes.)
4. **Test coverage** -- Do the 9 integration tests verify the wire (connections between components) rather than re-testing existing logic?

## Key Pointers

- `core/orchestrator.py` (Plan 60+): Orchestrator with `process_task`, `register_worker`, state machine. Accepts `improvement_loop` in `__init__` but never calls it. **This is the gap Plan 63a closes.**
- `core/orchestrator_improvement.py` (Plan 60+): `OrchestratorImprovementLoop` with `record_routing_decision`, `get_routing_accuracy`, `check_and_trigger_update`. Already tested. **Do not edit.**
- `evals/harness.py` (Plan 62): `EvalHarness` with `evaluate`, `evaluate_batch`, `summary`. Trace emitter integration. **Do not edit.**
- `memory/postgres_trace_store.py` (Plan 61): `PostgresTraceStore` with `store_trace`, `query_traces`. **Do not edit.**
- `core/commands.py` (Plan 60+): `CommandType` enum (no IMPROVE), `CommandRegistry`, `CommandHandler` ABC. Plan 63a adds IMPROVE type + handler.
- `orchestrator/` directory: Does not exist yet. Plan 63a creates `orchestrator/__init__.py` and `orchestrator/improvement_loop.py`.

## Architecture Notes

**Wire layer pattern**: `orchestrator/improvement_loop.py` is a thin orchestration module that connects existing components. It adds no new logic -- only routing and error handling. It is the **single integration point** for all improvement loop calls.

**Fire-and-forget with done callback**: Orchestrator invokes improvement loop via `asyncio.create_task()` + `task.add_done_callback(lambda t: t.exception())` to suppress "Task exception was never retrieved" warnings. Task processing is never blocked.

**Command vs automatic**: Both modes exist -- automatic invocation after every task completion (via wire module) AND manual `/improve` command (via `ImproveCommandHandler`). These serve different needs and don't conflict.

**Circular import protection**: `TYPE_CHECKING` guards for type annotations referencing `core/orchestrator.py`. Runtime imports inside method bodies.

## Known Risks

- **Circular imports**: `orchestrator/improvement_loop.py` imports from `core/` and `evals/`. Mitigated by `TYPE_CHECKING` guards and runtime imports.
- **Mock overfitting**: Integration tests mock all three components. Verify mocks don't assert on implementation details that could change in future plans.
- **Trace store query format**: The wire queries traces by `event_type`. If trace event format changes in future plans, the query filter may need updating. Document this dependency.
- **Mypy on wire module**: New module may introduce typing errors. Plan includes dedicated mypy check on wire module before full suite.

## Questions for Claude (answered in review)

1. Should improvement be fully automatic or manual? **Answer: Keep both.**
2. Is `orchestrator/` the right place for the wire? **Answer: Yes, but add `orchestrator/__init__.py`.**
3. Should the orchestrator invoke improvement loop synchronously or asynchronously? **Answer: Async fire-and-forget, but route through wire module and add done callback.**
