# Plan 67 — Skills and Tests Mypy Remediation

## Context Brief

Plans 64-66 reduced mypy errors from 294 to 134 (all in non-core, non-system code). Core/ and system/ are now at 0 errors. The remaining 134 errors break down as: 76 in `tests/`, 42 in `skills/`, 8 in `memory/`+`cli/`+`workers/`, 4 in `scripts/`, and 4 in `skills/` subdirectories (screenshot, home_assistant, git, docker — 1 each).

This plan targets the two largest remaining clusters: `skills/` (42 errors in 7 files) and `tests/` (76 errors in 9 files). Together they account for 118 of 134 errors (88%). Fixing these brings the full-repo count to ~16, within striking distance of zero for the Plan 70 milestone scan.

**Scope**: Fix mypy errors in `skills/` (7 files, 42 errors) and `tests/` (9 files, 76 errors). No new features. No new horizontal capability.

**Conventions**: "Apply OR6" means run syntax/import check after editing: `python -c "import ast; ast.parse(open('<file>.py').read())"`. OR6 is defined in AGENTS.md — read at S0.2.

---

## S0 — Opening

S0.1. Run `/jarvis-open` — verifies `prompt-66` tag on origin, confirms working copy is clean and on master. If the workflow is missing or fails, STOP and report.

S0.2. Read `AGENTS.md` in full. AGENTS.md is always-on — every file edit in this plan MUST comply with its rules. If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for the trigger and diagnostic context behind the rule.

S0.3. Add the following new rules to AGENTS.md and commit before any coding step:

**OR28 — PowerShell session cleanup**: After each command execution block, Devin MUST close the PowerShell session. If executing multiple commands in sequence, use a single session with `;` separation rather than spawning multiple sessions. At plan closing (or every 20 commands, whichever comes first), verify no orphaned processes remain:
- **On Windows**: `Get-Process powershell | Where-Object { $_.Id -ne $PID } | Measure-Object` — if count >5, kill orphans before proceeding.
- **On Linux/macOS**: `ps aux | grep -c powershell` or skip this check (Devin runs on Windows; this fallback is for local verification only).
(Source: L10 — Devin leaves zombie PowerShell processes after execution)

Also append L10 to LANDMINES.md:

```
## L10 — Devin leaves zombie PowerShell processes after execution

**Trigger**: Plans 64-66 execution, Devin spawned hundreds of PowerShell processes without exiting them. Each command execution created a new session that was never disposed.

**Impact**: Memory exhaustion, handle exhaustion, system instability. User's PC became sluggish with hundreds of orphaned PowerShell processes consuming resources.
```

---

## S1 — Full-Repo Mypy Baseline (READ-ONLY)

S1.1. Run: `mypy . --ignore-missing-imports > plan-67-baseline.log 2>&1`
Count errors per file. Save `plan-67-baseline.log` for Plan 70 milestone reference.

S1.2. Categorize all errors by type:
- **import-not-found / import-untyped**: Missing stubs (pytest, pydantic, httpx, etc.) — these can be fixed with `# type: ignore[import-untyped]` or `--ignore-missing-imports`
- **Union-attr / arg-type / assignment**: Real type mismatches — need code fixes
- **override / abstract**: Interface violations — need method fixes
- **Other**: Categorize and report

S1.3. **STOP gate**: Report findings to user before proceeding. Expected:
- `skills/`: ~42 errors in ~7 files
- `tests/`: ~76 errors in ~9 files
- `memory/cli/workers/scripts/`: ~16 errors in ~6 files
- **Total**: ~134

If total >150, STOP and report (unexpected drift). If `core/` or `system/` show any errors (>0), STOP and report (regression from Plan 66).

---

## S2 — Skills Mypy Remediation (42 errors, 7 files)

**Per OR27**: If fixing a type error requires changing a runtime type that would break existing tests, add a compatibility shim instead of modifying the test.

**After each file**: Run `mypy <file> --ignore-missing-imports` and `ruff check <file>`. Verify the specific errors targeted are resolved and no new errors appear. Apply OR6.

**Decision guide for None guards** (applies to all S2 and S3 fixes):
- Use `assert x is not None` if the None state is a **programmer error** — it should never happen in production, and silently returning would mask a bug.
- Use `if x is None: return <default>` if None is a **valid, recoverable input** — the caller may legitimately pass None, and the function should handle it gracefully.
- When in doubt, read the caller context. If the value comes from a config file, environment variable, or user input, treat it as recoverable. If it comes from an internal constructor or fixture, treat it as a programmer error.

**Rollback strategy**: If a fix in S2 or S3 breaks a test, `git checkout -- <file>` to revert that file. Document the failed fix in a side note for post-plan review. Do NOT spend more than 2 iterations on a single file — if the fix is harder than expected, STOP and report.

**# type: ignore logging**: Every time you add `# type: ignore[...]`, record it in a list: file, line number, reason. In S5.3, review this list. If any file has >3 `# type: ignore` comments, flag it for refactoring consideration in a future plan.

### S2.0 — Skills triage (READ-ONLY, before any S2 edits)

Before fixing any skills file, read each of the 7 files briefly (~2 min each) and classify:
1. **Is the union type intentional or accidental?** — If `dict | list | None` is how the API actually works (intentional), use `isinstance()` guards. If the union exists because the code was written before strict typing (accidental), consider normalizing the return type upstream.
2. **Are there platform-specific concerns?** — e.g., `winsound` in tts/skill.py is Windows-only.
3. **Estimated effort**: Sort the 7 files by expected difficulty (easy = simple guards, medium = isinstance + cast, hard = operator dispatch or interface redesign).

Report the triage to the user. If any file is assessed as "hard" and would require interface redesign, STOP and report — that's beyond a type-remediation plan's scope.

### S2.1 — skills/email/email_skill.py (12 errors)

Expected error types:
- `arg-type`: `str | None` passed where `str` expected (IMAP/SMTP server, credentials)
- `union-attr`: `bytes | tuple | None` doesn't have `.decode()` or indexing
- `index`: `bytes | tuple | None` is not indexable

Fix approach:
- Server/credential `str | None`: These come from config — treat as **recoverable**. Use `if server is None: raise ConnectionError("...")` or `if server is None: return` rather than assert.
- `.decode()` on `bytes | tuple | None`: Use `isinstance(data, bytes)` check before `.decode()`.
- Narrow types explicitly where mypy can't infer.

### S2.2 — skills/notes/notes_skill.py (11 errors)

Expected error types:
- `union-attr`: `dict | list | None` doesn't have `.sort()` or `__iter__`
- `arg-type`: `dict | list` not accepted where `dict` expected
- `call-overload`: `list.__setitem__` doesn't accept `str` keys

Fix approach:
- Add `isinstance(data, list)` / `isinstance(data, dict)` type guards
- Use `cast()` where type is known but mypy can't infer
- Restructure `list.__setitem__` calls to use `.append()` or dict construction

### S2.3 — skills/reminder/reminder_skill.py (6 errors)

Expected error types:
- `union-attr`: `None` has no `__iter__` or `.get()`
- `index`: `str` doesn't support `str` indexing
- `return-value`: `list[str | dict]` not `list[dict]`
- `call-overload`: `list.__setitem__` with `str` key

Fix approach:
- Add None guards before iteration
- Add `isinstance()` checks for str vs dict
- Fix return type annotations

### S2.4 — skills/calculator/skill.py (6 errors)

Expected error types:
- `operator`: Cannot call function of unknown type
- `assignment`: `type[unaryop]` not `type[operator]`
- `operator`: Unsupported operand types for `*` and `/`

Fix approach:
- Add explicit type annotations for operator mappings
- Use `cast()` for operator type narrowing
- Add `Callable` type hints for dynamic operator lookup

### S2.5 — skills/calendar/calendar_skill.py (5 errors)

Expected error types:
- `arg-type`: `str | None` not accepted by `open()`

Fix approach:
- Add `assert path is not None` or `if path is None: return` before `open()` calls

### S2.6 — skills/tts/skill.py (2 errors)

Expected error types:
- `attr-defined`: Module has no attribute `PlaySound` / `SND_FILENAME`

Fix approach:
- Add `if TYPE_CHECKING` guard or `# type: ignore[attr-defined]` for platform-specific winsound attributes (Windows-only module, unavailable on type-check environment)

### S2.7 — Remaining skills with 1 error each (screenshot, home_assistant, git, docker)

Fix each individually — likely `call-arg` or `arg-type` errors from interface changes in Plans 64-65. Read each file, identify the specific error, apply targeted fix.

### S2.8 — Skills verification

Run: `mypy skills/ --ignore-missing-imports`
Expected: 0 errors (or close to 0 — some `import-untyped` may need `# type: ignore`)
Run: `ruff check skills/`
Expected: 0 errors

---

## S3 — Tests Mypy Remediation (76 errors, 9 files)

**Key constraint**: Tests are NOT read-only in this plan (unlike Plans 64-66). This plan explicitly includes test file edits for type remediation. However, test **behavior** must not change — only type annotations and assertions.

**After each file**: Run `mypy <file> --ignore-missing-imports` and `ruff check <file>`. Then run `python -m pytest <test_file> -q --tb=short` to verify the tests still pass. Apply OR6.

### S3.0 — Test fixture audit (READ-ONLY, before any S3 edits)

Before fixing any test file, scan the 9 test files and categorize each fixture:
1. **Required but not typed**: Fixture always returns a non-None value but the return type isn't annotated. Fix: add return type annotation to the fixture.
2. **Optional by design**: Fixture may return None (e.g., PostgresTraceStore when no DB available). Fix: add `assert x is not None` in the test body — the test should skip or fail if the dependency is missing.
3. **Mock mismatches**: Fixture creates a `Mock()` that doesn't match the real class signature. Fix: add `# type: ignore[arg-type]` with a comment noting the intentional mock isolation (e.g., `# type: ignore[arg-type] — mock isolation test, MockOrchestrator intentionally differs from Orchestrator`).

Report the audit to the user. Do not proceed with S3 edits until audit is complete.

### S3.1 — tests/test_postgres_trace_store.py (15 errors)

Expected error types:
- `union-attr`: `PostgresTraceStore | None` doesn't have `.store_trace()`, `.query_traces()`, `.get_trace_by_id()`
- `misc`: async generator return type

Fix approach:
- Add `assert store is not None` after fixture creation (standard pattern)
- Fix async generator return type annotation

### S3.2 — tests/test_query_handler.py (15 errors)

Expected error types:
- `arg-type`: `MockOrchestrator` not accepted where `Orchestrator` expected
- `var-annotated`: Need type annotation for `workers`, `calls`
- `union-attr` / `operator` / `index`: `dict | None` and `str | None` access

Fix approach:
- Add type annotations for mock variables: `workers: dict[str, Any] = {}`, `calls: list[Any] = []`
- Add `# type: ignore[arg-type]` for mock-subclass mismatches (standard test pattern)
- Add None guards for optional dict/str access

### S3.3 — tests/test_model_acquisition.py (14 errors)

Expected error types:
- `arg-type`: `MockResourceManager` not `ResourceManager`
- `var-annotated`: Need type annotations
- `operator`: `str | None` in `in` operator

Fix approach:
- Add `# type: ignore[arg-type]` for mock mismatches
- Add type annotations for fixture variables
- Add `assert` guards for None before `in` operator

### S3.4 — tests/test_resource_manager.py (10 errors)

Expected error types:
- `attr-defined`: `TraceEmitter` has no attribute `get_events`
- `var-annotated`: Need type annotations for `calls`, `models`

Fix approach:
- Add `# type: ignore[attr-defined]` for test-only trace emitter methods
- Add type annotations for fixture variables

### S3.5 — tests/test_scratchpad.py (9 errors)

Expected error types:
- `union-attr`: `Scratchpad | None` doesn't have `.entries`, `.is_compacted`, `.completed_at`
- `override`: `fetch_by_filter` / `write_to_collection` signature mismatch
- `var-annotated`: Need type annotation for `writes`

Fix approach:
- Add `assert pad is not None` after fixture creation
- Add `# type: ignore[override]` for mock class signature mismatches
- Add type annotation for `writes: list[Any] = []`

### S3.6 — tests/test_task_state_machine.py (7 errors)

Expected error types:
- `override`: `build_prompt` / `parse_output` signature incompatible with `WorkerBase`
- `operator`: `str | None` in `in` operator

Fix approach:
- Add `# type: ignore[override]` for test subclass signature differences
- Add `assert` guard before `in` operator

### S3.7 — tests/test_model_registry.py (2 errors)

Expected error types:
- `attr-defined`: `TraceEmitter` has no attribute `get_events`
- `var-annotated`: Need type annotation

Fix approach:
- Add `# type: ignore[attr-defined]`
- Add type annotation

### S3.8 — tests/test_observability.py (1 error)

Expected: `arg-type` — `None` passed where `TraceEmitter` expected. Add `# type: ignore[arg-type]` or use `MemoryTraceEmitter()`.

### S3.9 — tests/test_retention_manager.py (1 error)

Fix the single error (likely `method-assign` from Plan 66's retention_manager changes).

### S3.10 — Tests verification

Run: `mypy tests/ --ignore-missing-imports`
Expected: 0 errors (or very close — some `import-not-found` for pytest may persist)
Run: `ruff check tests/`
Expected: 0 errors
Run: `python -m pytest tests/ -q --tb=short`
Expected: 1231 passed, 68 skipped (±5 tolerance)

---

## S4 — Remaining Directories (16 errors, 6 files)

Fix the smaller clusters after skills and tests are clean.

### S4.1 — memory/router.py (2 errors)

Expected: `assignment` — `MemoryBackend | None` not assignable to `MemoryBackend`
Fix: Add `assert` or use `cast()` after initialization.

### S4.2 — cli/tui.py + cli/rich_cli.py (4 errors)

Expected: `assignment` — `None` not assignable to concrete types; `ModelHandler` not `AdapterHandler`
Fix: Add type annotations or `cast()` for constructor assignments.

### S4.3 — scripts/verify_tui_e2e.py (4 errors)

Expected: `attr-defined` — `CognitionStack` has no attribute `memory_router`, `orchestrator`, etc.
Fix: Add `# type: ignore[attr-defined]` or add type stubs.

### S4.4 — workers/ollama_worker.py (1 error)

Expected: `abstract` — `NullMemoryBackend` missing abstract `list_keys` method
Fix: Implement `list_keys` or add `# type: ignore[abstract]`.

### S4.5 — Remaining verification

Run: `mypy memory/ cli/ scripts/ workers/ --ignore-missing-imports`
Expected: 0 errors
Run: `ruff check memory/ cli/ scripts/ workers/`
Expected: 0 errors

---

## S5 — Full Verification

S5.1. Full test suite: `python -m pytest tests/ -q --tb=short`. Expected: 1231 passed, 68 skipped (±5 tolerance).
- **If test count drops >5 from baseline**: Run `git diff tests/` to identify which tests changed. Investigate before proceeding.
- **If test count drops 1-5**: Within tolerance but note which tests changed in PLANS.md reconciliation.

S5.2. Ruff check on ALL touched files. Expected: 0 errors.

S5.3. File-scoped mypy on ALL touched files. Expected: 0 errors per file. Also review the `# type: ignore` log. Flag any file with >3 ignores for refactoring consideration in a future plan.

S5.4. Full-repo mypy count (soft gate): `mypy . --ignore-missing-imports 2>&1 | Select-String "error:" | Measure-Object`. Record the count.
- **If ≥50**: Re-run baseline and file detailed report identifying which files regressed. Significant errors remain — Plan 67 partial.
- **If 20–49**: Document in CHANGELOG as "partial remediation" with list of remaining high-impact files.
- **If <20**: Major cleanup achieved. Record as success for Plan 70 milestone.

S5.5. PowerShell cleanup (OR28): On Windows, `Get-Process powershell | Where-Object { $_.Id -ne $PID } | Measure-Object`. If count >5, kill orphans before proceeding. On Linux/macOS, skip or use `ps aux | grep -c powershell`.

---

## S6 — Closing

Run `/jarvis-close` — handles test suite, ruff, mypy, commit, tag, CHANGELOG, PLANS.md, LANDMINES.md, rule proposal, docs commit, push, and post-push verification.

**Expected CHANGELOG entry**:
```
## <date> HH:MM — prompt-67

**Plan**: Skills and Tests Mypy Remediation

**Changed**:
- skills/email/email_skill.py: Fixed 12 mypy errors (None guards, type narrowing)
- skills/notes/notes_skill.py: Fixed 11 mypy errors (isinstance guards, cast)
- skills/reminder/reminder_skill.py: Fixed 6 mypy errors (None guards, return types)
- skills/calculator/skill.py: Fixed 6 mypy errors (operator type annotations)
- skills/calendar/calendar_skill.py: Fixed 5 mypy errors (None guards before open())
- skills/tts/skill.py: Fixed 2 mypy errors (winsound platform guards)
- skills/ (4 files): Fixed 4 individual errors (arg-type, call-arg)
- tests/test_postgres_trace_store.py: Fixed 15 mypy errors (assert guards)
- tests/test_query_handler.py: Fixed 15 mypy errors (type annotations, type: ignore)
- tests/test_model_acquisition.py: Fixed 14 mypy errors (mock annotations, None guards)
- tests/test_resource_manager.py: Fixed 10 mypy errors (attr-defined, var-annotated)
- tests/test_scratchpad.py: Fixed 9 mypy errors (assert guards, override)
- tests/test_task_state_machine.py: Fixed 7 mypy errors (override, operator)
- tests/test_model_registry.py: Fixed 2 mypy errors (attr-defined, annotation)
- tests/test_observability.py: Fixed 1 mypy error (arg-type)
- tests/test_retention_manager.py: Fixed 1 mypy error (method-assign)
- memory/router.py: Fixed 2 mypy errors (assignment)
- cli/tui.py, cli/rich_cli.py: Fixed 4 mypy errors (assignment, cast)
- scripts/verify_tui_e2e.py: Fixed 4 mypy errors (attr-defined)
- workers/ollama_worker.py: Fixed 1 mypy error (abstract)
- AGENTS.md: Added OR28 (PowerShell session cleanup)
- LANDMINES.md: Added L10 (zombie PowerShell processes)

**Results**:
- Tests: <count> passed, <count> skipped
- Ruff: 0 errors
- Mypy (file-scoped on touched files): 0 errors
- Mypy (full-repo): <count> errors (was 134)
- Tag: prompt-67 verified on origin

**If ≥50 errors remain**: Mypy remediation incomplete (Plan 67 partial). Remaining errors concentrated in: [list high-impact files]. Recommend Plan 68 follow-up targeting [specific directories].
**If <20 errors remain**: Mypy remediation major success. Skills, tests, and remaining directories all clean.
```

**C9 rule proposal**: Assess whether any recurring pattern emerged. Candidate: "test mypy errors follow predictable patterns (assert guards, mock type: ignore, var annotations)" — but this is not a failure pattern, it's a known mypy limitation. If no systemic pattern, state: "No new rule proposals this plan."

---

## Scope Declaration

**WILL edit**:
- skills/email/email_skill.py
- skills/notes/notes_skill.py
- skills/reminder/reminder_skill.py
- skills/calculator/skill.py
- skills/calendar/calendar_skill.py
- skills/tts/skill.py
- skills/screenshot/skill.py
- skills/home_assistant/skill.py
- skills/git/skill.py
- skills/docker/skill.py
- tests/test_postgres_trace_store.py
- tests/test_query_handler.py
- tests/test_model_acquisition.py
- tests/test_resource_manager.py
- tests/test_scratchpad.py
- tests/test_task_state_machine.py
- tests/test_model_registry.py
- tests/test_observability.py
- tests/test_retention_manager.py
- memory/router.py
- cli/tui.py
- cli/rich_cli.py
- scripts/verify_tui_e2e.py
- workers/ollama_worker.py
- AGENTS.md (OR28 only)
- LANDMINES.md (L10 only)

**Will NOT edit**:
- Any `core/` file (clean since Plan 66)
- Any `system/` file (clean since Plan 66)
- Any `adapters/` file
- Any `web/` file
- Any `gateways/` file
- Any `orchestrator/` file
- CHANGELOG.md, PLANS.md (closing handles these)

**Hard scope boundary** (OR15, OR16): If any fix requires editing a file outside the "WILL edit" list, STOP and report. Do NOT expand scope unilaterally.
