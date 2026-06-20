# Sovereign AI — Full Project Audit (2026-06-20)

Post prompt-43c baseline: 1127 passed, 61 skipped, 0 failed, 0 warnings (on Windows with all deps).
Linux (this environment): 996 passed, 6 skipped, 0 failed (missing adapter SDKs); 27 failed in calendar/transcription/tts/profiler tests (missing deps).

## 1. Static Analysis — Ruff (423 errors)

Verified by re-running `ruff check . --select F401,F841,E402,F821,F541,F811` (authoritative count).

| Category | Count | Fixable? | Risk | Priority |
|----------|-------|----------|------|----------|
| F401 unused imports | 260 | Yes (`--fix`) | LOW — dead code, no runtime impact | P3 |
| F841 unused variables | 81 | Yes (manual) | LOW-MED — some are dead stores, some hide bugs | P2-P3 |
| E402 imports not at top | 33 | Yes (manual) | LOW — style only, Python runs fine | P3 |
| F821 undefined names | 26 name-occurrences across 24 lines | No (manual) | **CRITICAL** — will crash at runtime | **P1** |
| F541 f-string no placeholders | 15 | Yes (`--fix`) | LOW — cosmetic | P3 |
| F811 redefined-while-unused | 8 | Yes (`--fix`) | MED — Scratchpad duplicate is a real bug | P2 |

### F821 Undefined Names — CRITICAL (26 name-occurrences across 24 lines)

26 is the count of distinct undefined-name occurrences reported by ruff. Two lines have two names each: `core/worker_factory.py:581` (`LLMResponse`, `WorkerOutput`) and `core/orchestrator.py:721` (`A2ARequest`, `A2AResponse`). This gives **24 distinct lines** with 26 name-occurrences (verified by `ruff check . --select F821 | cut -d: -f1-2 | sort -u | wc -l`).

**Runtime bugs (will crash if code path is reached) — 6 files, 9 line-occurrences, 10 name-occurrences:**

| File | Line | Missing name | Severity | Why it matters |
|------|------|-------------|----------|----------------|
| `cli/command_history.py` | 97 | `uuid4` | **HIGH** | Used in Task construction — `from uuid import UUID` exists but `uuid4` not imported |
| `core/session.py` | 237, 280 | `Task` | **HIGH** | `from core.schemas import Task` is inside a function but used outside its scope |
| `core/worker_base.py` | 78 | `TraceEmitter` | MED | TYPE_CHECKING guard — runtime only fails if default is triggered |
| `core/worker_factory.py` | 581 | `LLMResponse` + `WorkerOutput` (2 names on 1 line) | MED | Inside a function that may not be reached |
| `system/trajectory_exporter.py` | 88, 96, 100 | `records` | MED | Dead code after `return 0` (Plan 45 deferral) |
| `workers/echo_worker.py` | 69 | `core` | LOW | String annotation used as type hint — works at runtime via string eval |

**TYPE_CHECKING-only issues (not runtime bugs — string annotations not evaluated):**

| File | Line | Missing name | Notes |
|------|------|-------------|-------|
| `core/escalation.py` | 32 | `TraceEmitter` | String annotation — not runtime |
| `core/handlers.py` | 28, 428 | `Orchestrator` | String annotation — not runtime |
| `core/notification.py` | 54 | `TelegramGateway` | String annotation — not runtime |
| `core/orchestrator.py` | 44, 721 | `A2ARouter` (line 44) + `A2ARequest` + `A2AResponse` (2 names on line 721) | String annotation — not runtime |
| `core/retention.py` | 46 | `MemoryRouter` | String annotation — not runtime |
| `system/model_acquisition.py` | 255, 256, 304, 305, 734, 810 | `ResourceManager`, `ModelRegistry` | String annotation — not runtime |
| `system/resource_manager.py` | 227, 290 | `ModelRegistry` | String annotation — not runtime |

### F811 Redefined-While-Unused — Notable

| File | Line | Redefinition | Issue |
|------|------|-------------|-------|
| `core/schemas.py` | 600 | `Scratchpad` redefined | **Real bug** — class defined twice (line 504 and 600), second has `is_compacted` field. The second definition silently shadows the first. |
| `cli/tui.py` | 53 | `CommandHistory` imported twice | Duplicate import |
| `core/escalation.py` | 60, 130, 185 | `TraceEventType` re-imported | Already imported at module level, re-imported inside functions |
| `core/memory_router.py` | 391-392 | `datetime`, `uuid4` re-imported | Already imported at module level |

### F841 Unused Variables — Key Findings

| File | Variable | Issue |
|------|----------|-------|
| 7 adapters (anthropic, cohere, deepseek, groq, mistral, openai, together) | `response` in health check | `response = await client.create(...)` but response is never used. Should prefix with `_` or just `await` without assignment. |
| `cli/serve.py` | `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory` | Constructed but never passed anywhere — these subsystems are built but unused in the serve path |
| `cli/tui.py` | `output_evaluator`, `trace_optimiser`, `worker_factory` | Same — constructed but never referenced |
| `core/approval_gate.py` | `emit_error` (5 occurrences) | Exception assigned but never used — should use `logger.warning(str(emit_error))` per Rule 17 |
| `cli/setup_wizard.py` | `ollama_reachable` | Assigned but never checked |

## 2. Static Analysis — Mypy (180 errors in 55 files)

### Top mypy error categories:

| Category | Count | Example | Fix approach |
|----------|-------|---------|-------------|
| ApprovalGate API mismatch | 14+ | Unexpected keyword `action`, `context` for `request_approval()` | Schema has changed but callers not updated |
| `float` vs `int` type mismatch | 14 | `tokens_used` assigned `float` where `int` expected | Add `int()` wrapping |
| Read deleted variable `e` | 13 | `except Exception as e: ... log(str(e))` but `e` deleted | Remove `del e` or use `e` before deletion |
| ModelRegistry undefined | 6 | TYPE_CHECKING string annotations | Add to TYPE_CHECKING imports |
| None type not handled | 5+ | `str | None` passed where `str` expected | Add `or ""` / `assert` guards |
| ApprovalResponse/Request missing fields | 8+ | Missing `scope_id`, `decision_reason`, `approved_by` | Schema has new required fields |
| Scratchpad `is_compacted` missing | 1 | First definition lacks field | Remove duplicate class definition |

### ApprovalGate API Drift — Critical Pattern

The `request_approval()` method signature has changed but **14+ callers** still use the old API:
- Old: `request_approval(action="shell", context=...)`
- New: `request_approval(action_type=ApprovalActionType.SHELL_COMMAND, ...)`

Affected files: `skills/terminal/`, `skills/code_execution/`, `skills/docker/`, `skills/git/`, `skills/home_assistant/`, `skills/http_client/`, `skills/pdf/`, `skills/spreadsheet/`, `skills/web_scraper/`, `skills/web_search/`, `core/escalation.py`, `core/approval_gate.py`

## 3. Test Failures (27 failing, environment-dependent)

| Test suite | Failures | Root cause |
|------------|----------|-----------|
| `test_calendar_skill.py` | 8 | Calendar skill expects real ICS parsing — mock needs updating |
| `test_skill_transcription.py` | 8 | faster_whisper not installed — tests should use `pytest.importorskip` |
| `test_skill_tts.py` | 3 | TTS skill mock expects different API — skill was refactored |
| `test_system_profiler.py` | 7 | Profiler tests expect Ollama running + GPU — should mock external deps |

**Note**: On Windows (Devin's environment), all 1127 tests pass because the adapter SDKs are installed. The 27 failures here are Linux environment-specific (missing SDKs).

## 4. E402 Import Ordering (33 errors)

Two patterns:
1. **`web/server.py` and `web/middleware/auth_middleware.py`**: `logging.getLogger()` call placed before imports, forcing all subsequent imports to be E402. Fix: move logger initialization after all imports.
2. **Various files**: Local imports inside functions. These are fine (not runtime bugs) but ruff flags them.

## 5. Test Warnings (878 warnings, mainly in Linux env)

| Category | Count | Fix |
|----------|-------|-----|
| `datetime.utcnow()` deprecation | 166 | Replace with `datetime.now(datetime.UTC)` |
| Unclosed file ResourceWarning | ~12 | Add proper `close()` or use context managers |
| PytestUnraisableExceptionWarning | 1 | Unhandled exception in async cleanup |

## 6. Architectural Issues Found

### 6a. Duplicate `Scratchpad` class in `core/schemas.py`
- Line 504: Original definition (5 fields)
- Line 600: Redefinition (6 fields — adds `is_compacted`)
- The second silently shadows the first. `core/scratchpad.py:155` references `is_compacted` which mypy flags because the first definition doesn't have it. **Fix**: Remove the first definition, keep the second.

### 6b. `cli/serve.py` constructs subsystems it never uses
- `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory` are all constructed but never referenced
- This is the F4 bug from the handoff — `jarvis serve` registers a worker but the cognition loop components (evaluator, trace optimiser, worker factory) are never wired into the request path
- Not a crash bug, but these are wasted allocations and the serve path doesn't self-improve

### 6c. `gateways/__init__.py` missing
- Causes mypy "found twice under different module names" error
- Fix: Add empty `gateways/__init__.py`

### 6d. `cli/command_history.py:97` — `uuid4` not imported
- `from uuid import UUID` exists but `uuid4` is missing
- Will crash at runtime when `add_command()` creates a Task

## 7. Recommended Fix Plan Sequence

### Plan 45 — InputSanitiser redesign (already planned)
Current scope is correct. No changes needed.

### Plan 46 — Ruff F821 + F811 + critical F841 cleanup
**Priority**: P1 (runtime crash bugs)
**Scope**:
1. Fix `cli/command_history.py:97` — add `uuid4` to `from uuid import UUID, uuid4`
2. Fix `core/session.py:237,280` — add `Task` to module-level imports (currently imported inside a function but used outside its scope)
3. Fix `core/schemas.py` — remove duplicate `Scratchpad` class (line 504-511), keep line 600-615 version
4. Fix `cli/tui.py:53` — remove duplicate `CommandHistory` import
5. Fix `core/escalation.py` — remove redundant `TraceEventType` re-imports (3 occurrences)
6. Fix `core/memory_router.py` — remove redundant `datetime`/`uuid4` re-imports
7. Fix `core/approval_gate.py` — use `emit_error` instead of swallowing (5 occurrences, Rule 17)
8. Fix `system/trajectory_exporter.py` — remove dead code after `return 0` (lines 82-100)
9. Fix `workers/echo_worker.py:69` — change `"core.memory_router.MemoryRouter"` to proper TYPE_CHECKING import
10. Fix 7 adapter health checks — prefix `response` with `_` or remove assignment
11. Fix `cli/serve.py` F841 — prefix `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory` with `_` to acknowledge they're intentionally unused (see 6b: these subsystems are constructed for future wiring but not yet in the request path)

**Note**: `core/session.py:237,280` is HIGH severity (will crash at runtime if code path reached) and was previously listed in Plan 48. Moved here because P1 runtime bugs must not be deferred to a P2 plan.

**Note on cli/serve.py**: Item 11 addresses the F841 ruff errors (unused variables). The deeper architectural issue — that these subsystems are built but never wired into the request path (F4 from handoff: "serve constructs 14 subsystems but the cognition loop doesn't self-improve") — is not fixed by prefixing with `_`. That wiring work requires a separate plan after the InputSanitiser and static-analysis cleanup is done. Recommend adding as Plan 48b or rolling into Plan 48.

### Plan 47 — E402 import ordering + missing __init__.py
**Priority**: P2
**Scope**:
1. Fix `web/server.py` — move `logging.getLogger()` after all imports
2. Fix `web/middleware/auth_middleware.py` — same pattern
3. Add `gateways/__init__.py`
4. Remove unused imports: `JSONResponse` from `web/server.py`, `AuthenticationError` from `auth_middleware.py`, `asyncio` from `gateway.py` + `gemini.py`

### Plan 48 — ApprovalGate API drift + mypy error remediation
**Priority**: P2
**Scope**:
1. Update all 14+ callers of `request_approval()` to use new API signature
2. Fix `ApprovalResponse`/`ApprovalRequest` missing field errors
3. Fix `tokens_used` float→int mismatches in adapters
4. Fix `except Exception as e` / `del e` / read-deleted-variable patterns (13 occurrences)
5. Fix `str | None` → `str` type narrowing in adapters

### Plan 49 — Test suite health
**Priority**: P2
**Scope**:
1. Add `pytest.importorskip("faster_whisper")` to transcription tests
2. Fix calendar skill test mocks
3. Fix TTS skill test mocks
4. Fix profiler test mocks (external deps)
5. Replace `datetime.utcnow()` with `datetime.now(datetime.UTC)` across all test files

### Plan 50 — Ruff F401 bulk cleanup (260 unused imports)
**Priority**: P3 (safe, mechanical, no behavior change)
**Scope**: Run `ruff check . --select F401 --fix` then verify tests pass. Low risk, high noise reduction.

## 8. Key Metrics

| Metric | Value |
|--------|-------|
| Ruff errors | **423** (260 F401 + 81 F841 + 33 E402 + 26 F821 + 15 F541 + 8 F811) — verified by re-running ruff |
| Mypy errors | 180 in 55 files |
| Test baseline (Windows) | 1127 passed, 61 skipped, 0 failed, 0 warnings |
| Test baseline (Linux, no SDKs) | 996 passed, 6 skipped + 27 env-dependent failures |
| Runtime crash bugs (F821) | **6 files / 9 line-occurrences / 10 name-occurrences** (not TYPE_CHECKING guards) |
| Duplicate class definitions | 1 (`Scratchpad` in schemas.py) |
| Deprecated API usage | 166 `datetime.utcnow()` calls |
| Missing __init__.py | 1 critical (`gateways/`) |
| ApprovalGate API drift | 14+ callers using old signature |

## 9. Cross-plan sequencing hazard

`cli/serve.py` is in scope for both Plan 44 REV3 (Step 6 — adds `input_sanitiser` kwarg to Orchestrator constructor) and Plan 46 (item 11 — prefixes unused `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory` with `_`). These are different edits in the same function (`serve()`). Whichever plan runs second should include `cli/serve.py` in its drift-check pathspec and verify the first plan's changes are still present.

Additionally, the F4 wiring bug (Section 6b — cognition-loop components built but never used in serve path) has **no home** in the current Plan 45–50 sequence. Plan 46 item 11 only silences the F841 lint warnings; it does not wire the subsystems. A future plan (suggest Plan 48b) should wire `output_evaluator`, `trace_optimiser`, and `worker_factory` into the serve request path so `jarvis serve` actually self-improves.
