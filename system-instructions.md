# ANTIGRAVITY RUNTIME GOVERNANCE: Sovereign AI Agent Framework

## 1. Zero-Tolerance Constraints (Architecture Laws)
- **Strict Clean Architecture:** Core must NEVER import adapters, workers, memory, or cli.
  - `workers/` -> imports from `core/` and `adapters/` only.
  - `memory/` -> imports from `core/` only.
  - `adapters/` -> imports from `core/` only.
  - `cli/` -> imports from anywhere. Nothing imports from `cli/`.
- **Async-First:** Every single I/O operation MUST be async. No synchronous blocking calls.
- **Data Boundaries:** Pydantic everywhere. Zero raw dicts cross component boundaries.
- **Type Safety:** Every public function must have explicit return type annotations. Reject untyped signatures.
- **Memory Routing:** Absolutely NO memory access outside of `MemoryRouter`.
- **Design Philosophy:** Composition over inheritance. Avoid deep class hierarchies.

## 2. Coding Patterns & Error Handling
- **Custom Exceptions (`core/exceptions.py`):**
  - Use `InvalidStateTransitionError` for illegal transitions.
  - Use `WorkerNotFoundError` for worker lookup failures (NEVER use `ValueError`).
  - Use `ApprovalDeniedError` for denied approvals.
  - Never raise raw `ValueError` or `Exception` for these domain cases.
- **Observability:** Every component must emit `TraceEvents`. All trace calls MUST be wrapped in a `try-except` block to prevent application crashes.
- **TraceEmitter Class Pattern:** When passing `emitter` to `super().__init__()`, the parameter MUST appear in the subclass `__init__` signature as `emitter: TraceEmitter | None = None` BEFORE the `super()` call. (Prevent `NameError`).
- **Magic Strings:** Absolutely no magic strings. Use Enums. Never use raw strings for enum values.
- **LLM Decoupling:** No raw LLM calls outside of adapters.
- **Hardware Context:** Never hardcode hardware assumptions. Query `SystemProfiler` and `ResourceManager` dynamically. Base model selection on live VRAM/RAM detection.

## 3. Mandatory Checkpoint Procedure (Execute after EVERY prompt)
Before reporting completion or proceeding to the next task, you MUST execute these steps in order:
1. Run full test suite: `python -m pytest tests/ -v --ignore=tests/test_llama_cpp_adapter.py`
2. Confirm zero regressions against baseline (235 passed, 23 skipped).
3. Execute checkpoint script: `python scripts/checkpoint.py prompt-{N}` (Replace {N} with current prompt number).
4. Verify local tag: `git tag | grep prompt-{N}`
5. Verify remote push: `git ls-remote --tags origin | grep prompt-{N}`
6. Update `c:\Jarvis\CHANGELOG.md` with incremental changes, architectural decisions, test results, and rationale.
7. Output report format: Include test count, checkpoint tag name, and remote backup status.

## 4. Guardrails & Technical Debt (Do Not Touch)
- Do NOT attempt to fix `_global_registry` in `core/commands.py` (line 147).
- Do NOT attempt to fix `_global_emitter` in `core/observability.py` (line 313).
- These are documented violations reserved for a future Dependency Injection refactor.
