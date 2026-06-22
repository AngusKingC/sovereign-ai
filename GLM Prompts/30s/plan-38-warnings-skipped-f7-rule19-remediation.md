# Plan 38: Warnings cleanup + skipped-tests audit + F7 trace spam + Rule 19 remediation

> **This is REV1 of Plan 38.** Combines four tightly-coupled cleanup scopes into one plan:
> 1. Warnings cleanup (63 → 0): 6 categories, mechanical fixes plus real bugs
> 2. Skipped-tests audit (29 → ~9 legitimate): enumerate, classify, fix or formal-defer
> 3. F7 trace spam: `core/worker_base.py:88-91` default emitter change
> 4. Rule 19 remediation: Gates 5/6 from prompt-37.6.1 actually executed (or formally deferred with Plan-N tickets)
>
> **Critical sequencing rule for THIS plan**: Same as Rule 19 (now in handoff). Execute steps in order. Paste literal gate output. No "PASSED" without evidence. No "SKIPPED" without plan authority. If a step cannot be completed in an automated execution environment, document it as a deferral with a Plan-N ticket — do NOT mark SKIPPED.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-37.6.1..HEAD -- core/worker_base.py cli/ web/server.py adapters/gemini.py tests/ SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> If any of these files changed since prompt-37.6.1, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P1 (debt cleanup; no functional regressions, but blocks future plans by polluting test output)
- **Effort**: M (4 distinct scopes, but each is small)
- **Risk**: LOW–MEDIUM (warnings fixes touch production code in `web/server.py` and `adapters/gemini.py`; F7 touches `core/worker_base.py` default behavior)
- **Depends on**: prompt-37.6.1 (commit `00b930e`, tag `prompt-37.6.1`)
- **Planned at**: commit `4814712`, 2026-06-18
- **In scope**:
  - Production: `core/worker_base.py` (F7), `web/server.py` (on_event deprecation), `adapters/gemini.py` (google.generativeai migration), `cli/__init__.py` (new file — mypy visibility)
  - Tests: `tests/test_setup_wizard.py`, `tests/test_system_profiler.py` (unawaited coroutine bugs), 8 test files with module-level `pytestmark = pytest.mark.asyncio` (split sync vs async), `tests/test_trajectory_exporter.py` (verify Plan-45 deferral still valid), `tests/test_di_compliance.py` (locate `\J` escape)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (update test baseline, update "What works right now" stale 1044 count, document remaining skipped tests)
  - Changelog: `CHANGELOG.md` (per-step literal gate output)
- **Out of scope**: broad-except audit (Plan 38.5+), InputSanitiser wiring (Plan 41), ruff triage (Plan 43), mypy triage (Plan 44), trajectory_exporter functional redesign (Plan 45)

## Why this matters

Three reasons this plan exists now:

1. **63 warnings + 29 skipped tests are debt that compounds.** Every plan that lands without addressing them increases the surface area where a real bug hides behind noise. Categories 3 (sync methods marked async), 4 (on_event deprecation), 6 (escape sequence) are mechanical fixes that collapse 35+ warnings in a few edits. Categories 1, 2, 5 are real bugs that need their own focused work but are small enough to land here.

2. **F7 trace spam is a user-facing bug.** Running `jarvis "hello"` prints every trace event to stdout alongside the response. This is the most visible "the framework is unfinished" signal a user sees. One-line default change in `core/worker_base.py` fixes it.

3. **Prompt-37.6.1 violated Rule 19 in the same plan that added Rule 19.** Gates 5 and 6 were marked SKIPPED with "manual verification requires interactive TUI session" — exactly the reasoning Rule 19 forbids. This sets a precedent that Rule 19 is aspirational rather than enforced. This plan either executes Gates 5/6 properly or formally defers them with Plan-N tickets — but does not silently skip.

## What's broken (verified against live repo at commit 4814712)

### A. 63 test warnings (6 categories)

Confirmed by source inspection of fetched files:

| Cat | Count | Source | Type | Fix |
|-----|-------|--------|------|-----|
| 1 | 1 | `adapters/gemini.py:12` | `import google.generativeai as genai` — Google end-of-lifed the package | Migrate to `google.genai` API surface |
| 2 | 6 | `tests/skills/test_docker_skill.py`, `tests/skills/test_web_scraper.py` | `PytestUnraisableExceptionWarning` — unclosed asyncio transports (httpx.AsyncClient) | Add fixture teardown, use `async with httpx.AsyncClient()` pattern in test mocks |
| 3 | ~17 | 8 test files with `pytestmark = pytest.mark.asyncio` at module level containing sync methods | `PytestWarning: marked @pytest.mark.asyncio but not async` | Either remove `pytestmark` and add `@pytest.mark.asyncio` per async method, OR split sync methods into a separate test class without the pytestmark |
| 4 | ~17 | `web/server.py:49` | `DeprecationWarning: on_event is deprecated` (FastAPI) | Convert `@app.on_event("startup")` to `lifespan` handler |
| 5 | 3 | `tests/test_setup_wizard.py`, `tests/test_system_profiler.py` | `RuntimeWarning: coroutine ... was never awaited` — `mock_get_token` defined as async but called without `await` | Either change mock to `MagicMock` (sync) or add `await` to call site — depends on what the SUT actually does |
| 6 | 1 | Unknown file (not in fetched set) | `DeprecationWarning: invalid escape sequence '\J'` | Add `r""` raw-string prefix to offending string literal |

**Source files for category 3** (verified by grep across fetched test files): `test_docker_skill.py`, `test_approval_trust.py`, `test_mcp_adapter.py`, `test_mcp_server.py`, `test_ollama_adapter.py`, `test_profiler.py`, `test_security.py`, `test_trace_optimiser.py`.

### B. 29 skipped tests (legitimate vs hidden-bug)

| Count | Source | Reason | Action |
|-------|--------|--------|--------|
| 6 | `tests/test_trajectory_exporter.py` | `pytest.skip("Trajectory export deferred to Plan 45...")` — legitimate Plan-N deferral | Verify Plan 45 is still queued; keep skip but add `pytest.skip(..., allow_module_level=False)` and ensure skip message references Plan 45 explicitly. No code change. |
| 1 | `tests/test_anthropic_adapter.py:20` | `pytest.skip("ANTHROPIC_API_KEY environment variable not set")` — conditional, env-dependent | Keep. Document in handoff "Test environment prerequisites" subsection. |
| 1 | `tests/test_gemini_adapter.py:20` | `pytest.skip("GEMINI_API_KEY environment variable not set")` — conditional, env-dependent | Keep. Document in handoff "Test environment prerequisites" subsection. |
| ~21 | Unknown — not in fetched sample | Need `pytest --collect-only -q` to enumerate | Each must be classified: legitimate Plan-N deferral, env-conditional, or recurring mistake #2 in disguise. Fix-or-defer per classification. |

### C. F7 — trace spam from `WorkerBase` default emitter

- **Location**: `core/worker_base.py:88-91` (per handoff)
- **Cause**: `WorkerBase.__init__` defaults `emitter=None`, and when None, falls back to `ConsoleTraceEmitter()` which prints every trace event to stdout
- **Fix**: Change default to `MemoryTraceEmitter()` (no-op for stdout, still records events in memory for test inspection)
- **Side effect**: Tests that asserted on console output via capsys will break. Audit test files for `capsys.readouterr()` usage on trace events and update to inspect the emitter directly.

### D. `cli/__init__.py` missing

- `cli/` directory has no `__init__.py`, so mypy can't treat it as a package
- This is mechanical: create empty `cli/__init__.py` (or with explicit `__all__` if desired)
- Side effect: may surface new mypy errors that were previously hidden. Those go to Plan 44 (mypy triage).

### E. Rule 19 violation from prompt-37.6.1

- Gates 5 (manual TUI test) and 6 (adapter swap test) marked SKIPPED in CHANGELOG with reasoning that Rule 19 explicitly forbids
- CHANGELOG lines 6883 and 6887 contain "SKIPPED - Manual verification requires interactive TUI session. This is an automated execution environment."
- Rule 19 (just added by this same plan) says: "Do not mark a gate SKIPPED unless the plan explicitly allows skipping it. 'Manual verification' is not a skip reason — if the plan calls for manual verification, do the manual verification and paste the result."

## What to change

### Step 1 — Run baseline + collect-only (capture current state as evidence)

**Command sequence** (paste all output literally into CHANGELOG as Step 1 evidence):

```powershell
# Baseline test counts (matches prompt-37.6.1 final state)
python -m pytest tests/ -q --tb=short 2>&1 | Select-Object -Last 5

# Warning breakdown by category
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "Warning|warning" | Group-Object | Sort-Object Count -Descending

# Skipped tests enumerated
python -m pytest tests/ --collect-only -q 2>&1 | Select-String "skip" 
python -m pytest tests/ -v --tb=no 2>&1 | Select-String "SKIPPED"

# mypy errors (for reference — Plan 44 will address)
python -m mypy core/ system/ adapters/ workers/ skills/ --ignore-missing-imports 2>&1 | Measure-Object -Line
```

**STOP if baseline is not 1080 passed / 29 skipped / 1 failed / 63 warnings.** Investigate drift before proceeding.

**Paste into CHANGELOG** (literal — required by Rule 19):
```
#### Step 1 — Baseline evidence

Baseline test counts:
<literal last-5-lines of pytest>

Warning breakdown:
<literal group-by output>

Skipped tests enumerated:
<literal Select-String output>
```

### Step 2 — Fix category 4: `on_event` deprecation in `web/server.py`

**File**: `web/server.py`

**Change**: Convert `@app.on_event("startup")` (line 49) and any `@app.on_event("shutdown")` to the FastAPI `lifespan` handler pattern.

```python
# Before (deprecated):
@app.on_event("startup")
async def startup():
    ...

# After (lifespan pattern):
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup code here
    yield
    # shutdown code here (if any)

app = FastAPI(lifespan=lifespan)
```

**Verify**:
```powershell
python -m pytest tests/test_web_server.py -q --tb=short
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "on_event" 
```

First command: tests still pass. Second command: zero matches (deprecation gone).

**Expected warning count change**: ~17 warnings eliminated (one per `on_event` call). New total: ~46 warnings.

### Step 3 — Fix category 3: module-level `pytestmark = pytest.mark.asyncio` on 8 test files

**Files** (verified by grep):
- `tests/skills/test_docker_skill.py`
- `tests/test_approval_trust.py`
- `tests/test_mcp_adapter.py`
- `tests/test_mcp_server.py`
- `tests/test_ollama_adapter.py`
- `tests/test_profiler.py`
- `tests/test_security.py`
- `tests/test_trace_optimiser.py`

**Change**: For each file, remove the module-level `pytestmark = pytest.mark.asyncio` line and add `@pytest.mark.asyncio` decorator to each individual `async def test_*` method.

```python
# Before:
pytestmark = pytest.mark.asyncio

class TestFoo:
    async def test_a(self): ...
    def test_b(self): ...  # sync method — generates warning
    async def test_c(self): ...

# After:
class TestFoo:
    @pytest.mark.asyncio
    async def test_a(self): ...
    def test_b(self): ...  # sync method — no warning
    @pytest.mark.asyncio
    async def test_c(self): ...
```

**Verify per file**:
```powershell
python -m pytest tests/test_approval_trust.py -q --tb=short
# repeat for each of 8 files
```

All tests still pass.

**Expected warning count change**: ~17 warnings eliminated. New total: ~29 warnings.

### Step 4 — Fix category 6: invalid escape sequence

**Locate the offending file**:
```powershell
python -W error::DeprecationWarning -m pytest tests/ --collect-only 2>&1 | Select-String "invalid escape|DeprecationWarning"
```

This will produce a stack trace pointing at the exact file and line.

**Fix**: Add `r` prefix to the offending string literal (e.g., change `"C:\Jarvis"` to `r"C:\Jarvis"`).

**Verify**:
```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "invalid escape"
```

Zero matches.

**Expected warning count change**: 1 warning eliminated. New total: ~28 warnings.

### Step 5 — Fix category 5: unawaited coroutine in test_setup_wizard.py and test_system_profiler.py

**Files**: `tests/test_setup_wizard.py`, `tests/test_system_profiler.py`

**Root cause** (per session 2 handoff analysis): `mock_get_token` defined as `AsyncMock` but called without `await` somewhere in the test or SUT. Tests pass but don't exercise what they claim.

**Procedure**:
1. In each file, locate every `AsyncMock` assignment and trace where the mock is called
2. If the SUT calls the function synchronously (i.e., the real function should be sync), change `AsyncMock` to `MagicMock`
3. If the SUT awaits the function, the test code itself is wrong — find the call site and add `await`
4. Add an assertion that the mock was actually called: `mock_get_token.assert_called_once()` — this catches the "test passes but mock never invoked" failure mode

**Verify**:
```powershell
python -m pytest tests/test_setup_wizard.py tests/test_system_profiler.py -v --tb=short
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "was never awaited"
```

First command: tests still pass AND new `assert_called_once` assertions pass. Second command: zero matches.

**Expected warning count change**: 3 warnings eliminated. New total: ~25 warnings.

### Step 6 — Fix category 2: unclosed asyncio transports in skill tests

**Files**: `tests/skills/test_docker_skill.py`, `tests/skills/test_web_scraper.py`

**Root cause**: Tests use `httpx.AsyncClient` mocks that don't properly clean up their transport. On Windows this surfaces as `PytestUnraisableExceptionWarning`.

**Procedure**:
1. In each test that mocks `httpx.AsyncClient`, ensure the mock's `__aenter__` and `__aexit__` are both defined as `AsyncMock`
2. If the SUT uses `async with httpx.AsyncClient() as client:`, the mock must support that pattern
3. Add explicit fixture teardown if needed: `@pytest.fixture(autouse=True)` that closes any lingering transports

**Verify**:
```powershell
python -m pytest tests/skills/test_docker_skill.py tests/skills/test_web_scraper.py -v --tb=short
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "PytestUnraisableException"
```

First command: tests still pass. Second command: zero matches.

**Expected warning count change**: 6 warnings eliminated. New total: ~19 warnings.

### Step 7 — Fix category 1: `google.generativeai` deprecation in adapters/gemini.py

**File**: `adapters/gemini.py`

**Change**: Migrate from `google.generativeai` to `google.genai` (the new Google SDK API surface).

**This is real migration work, not a suppression.** Reference: https://ai.google.dev/gemini-api/docs/sdks

**Key API changes** (these are starting points — the actual diff may surface more):
- `import google.generativeai as genai` → `from google import genai`
- `genai.configure(api_key=...)` → `client = genai.Client(api_key=...)` (client must be held as instance state, not module-level)
- `genai.GenerativeModel(...)` → `client.models.generate_content(...)` (different call shape — model is a parameter, not a class)
- `genai.types.GenerationConfig(...)` → `genai.types.GenerateContentConfig(...)`
- **Async pattern**: if the adapter uses `await` for generation (likely, given the codebase is async-first), the new SDK exposes async via `client.aio.models.generate_content(...)` — NOT `client.models.generate_content(...)`
- **Streaming**: if the adapter uses `generate_content(..., stream=True)`, the new SDK has a different streaming iterator shape — verify the consumer code handles the new shape
- **`genai.types` namespace**: significantly restructured; any other type imports from `genai.types` need to be checked individually

**Line-count guard — STOP condition for THIS step specifically**: After making the changes, run:
```powershell
git diff --stat adapters/gemini.py
```
If the production-code diff (excluding comments and blank lines) exceeds **20 lines changed**, STOP. The migration is larger than in-scope for this plan — defer to Plan 38.5. Apply the deferral as follows:

1. Revert the partial migration: `git checkout adapters/gemini.py`
2. Add an inline suppression with a ticket reference at the import line:
   ```python
   import google.generativeai as genai  # noqa: W605 — Plan 38.5: migrate to google.genai
   ```
   (Use the appropriate warning code for the deprecation. `# noqa` with a Plan-N reference is a legitimate temporary suppression — the warning is hidden but the ticket is visible. This is NOT silent noise; the ticket reference makes it auditable.)
3. Add "Plan 38.5 — Gemini SDK migration" to the plan queue in `SOVEREIGN_AI_HANDOFF.md`'s deferred-actions list.
4. Document in CHANGELOG: "Step 7 deferred to Plan 38.5 — migration diff exceeded 20-line guard. Inline `# noqa` suppression added with ticket reference."
5. Adjust this plan's Gate 3 expected warning count: 1 warning NOT eliminated (suppressed, not fixed). New total: ~19 warnings instead of ~18.

**Verify (if migration proceeded in-scope)**:
```powershell
python -m pytest tests/test_gemini_adapter.py -v --tb=short
# Skip-if-no-API-key path still works
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai"
```

First command: test still skips gracefully (no API key) OR passes (if API key set). Second command: zero matches.

**Expected warning count change**: 1 warning eliminated (if migrated) OR 1 warning suppressed with Plan-38.5 reference (if deferred). New total: ~18 or ~19 warnings respectively.

### Step 8 — F7: Change `WorkerBase` default emitter

**File**: `core/worker_base.py` (lines 88-91 per handoff)

**Change**: Default `emitter` from `ConsoleTraceEmitter()` to `MemoryTraceEmitter()`.

```python
# Before:
if emitter is None:
    self.emitter = ConsoleTraceEmitter()

# After:
if emitter is None:
    self.emitter = MemoryTraceEmitter()
```

**Side-effect audit**: Search test files for assertions on console trace output:
```powershell
Select-String -Path tests\*.py -Pattern "capsys.*trace|trace.*capsys|readouterr.*trace"
```

For each match, update the test to inspect the emitter directly (e.g., `worker.emitter.events` for MemoryTraceEmitter) instead of capturing stdout.

**Verify**:
```powershell
# Unit tests still pass
python -m pytest tests/test_worker_base.py tests/test_ollama_worker.py -v --tb=short

# Manual verification — Gate 5 below
jarvis "hello"
```

First command: tests pass. Second command: no trace events printed alongside response (only the response itself).

### Step 9 — Create `cli/__init__.py`

**File**: `cli/__init__.py` (new file)

**Content**: Empty file (or minimal `__all__` if desired).

**Verify**:
```powershell
python -c "import cli; print(cli.__file__)"
python -m mypy cli/ --ignore-missing-imports 2>&1 | Measure-Object -Line
```

First command: prints a path (proves package is importable). Second command: mypy now scans `cli/` (may surface new errors — those go to Plan 44, not this plan).

### Step 10 — Skipped-tests audit (the remaining ~21)

**Procedure**:

1. Enumerate every skipped test in the suite:
```powershell
python -m pytest tests/ -v --tb=no --no-header 2>&1 | Select-String "SKIPPED" | Sort-Object
```

2. For each skipped test, classify into one of three categories:
   - **LEGITIMATE-DEFER**: skip message references a specific Plan-N ticket (e.g., "Plan 45"). Keep, but ensure Plan N is still in the queue.
   - **ENV-CONDITIONAL**: skip is conditional on an environment variable or external resource (e.g., API key, Postgres URL). Keep, but document the prerequisite in handoff "Test environment prerequisites" subsection.
   - **HIDDEN-BUG**: skip reason is "complexity", "couldn't mock", "OllamaAdapter initialization complexity", or similar. This is recurring mistake #2 in disguise. Fix it.

3. For each HIDDEN-BUG skip: apply the mock-at-instantiation pattern from Plan 37.6.1 Section A. If the SUT genuinely cannot be mocked without a major refactor, document a Plan-N deferral in the skip message itself (e.g., `pytest.skip("Deferred to Plan 46: requires SUT refactor to expose adapter injection point")`).

4. **Paste the full enumeration into the CHANGELOG** as Step 10 evidence (Rule 19 — no skipped test goes undocumented).

### Step 11 — Rule 19 remediation: actually run Gates 5 and 6 from prompt-37.6.1

**The prompt-37.6.1 plan called for manual TUI verification (Steps 6 and 7).** Devin marked them SKIPPED. Rule 19 (which Devin himself just added) forbids this.

**Two options, pick one**:

**Option A — Execute the manual verification now**:
1. Start `jarvis` (TUI mode)
2. Type `hello`, paste the response verbatim into CHANGELOG
3. Type `what did I just say?`, paste the response verbatim
4. Verify the second response references "hello" (memory_router wired correctly)
5. Type `/adapter lm_studio`
6. Type `test query after swap`, paste response
7. Verify new worker has `memory_router` (not None) — can check via trace event or worker registry inspection
8. Exit TUI

**Option B — Formally defer with a Plan-N ticket**:
If Option A is genuinely impossible (e.g., no interactive shell available in the execution environment), create a Plan 38.6 in the queue titled "Manual TUI verification for prompt-37.6.1 Gates 5/6". Update the CHANGELOG entry for prompt-37.6.1 to record the deferral:

```
#### Deferred verification — Plan 38.6

Gates 5 and 6 from prompt-37.6.1 were marked SKIPPED in the original execution. Per Rule 19 (added by that same plan), this was a violation. This entry records the deferral: Plan 38.6 will execute the manual TUI verification (Steps 6 and 7 of prompt-37.6.1) and paste literal output here.
```

**Do NOT mark this step complete without either (A) pasting the literal TUI output or (B) creating the Plan 38.6 ticket and pasting its name.** Rule 19's whole point.

### Step 12 — Update handoff "What works right now" prose count

**File**: `SOVEREIGN_AI_HANDOFF.md`

**Change**: Find the line in "What works right now" that says "1044 tests pass" (stale from pre-37.5). Update to the actual final count from this plan's Gate 8.

**Verify**:
```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "\d+ tests pass"
```

Should return one match, with the count matching Gate 8 final.

### Step 13 — Update handoff test baseline + add "Test environment prerequisites" subsection

**File**: `SOVEREIGN_AI_HANDOFF.md`

**Changes**:
1. Update the "Test baseline" line near the top to this plan's final count
2. Add a new subsection "Test environment prerequisites" listing every env-conditional skip:
   - `ANTHROPIC_API_KEY` — required for `test_anthropic_adapter.py`
   - `GEMINI_API_KEY` — required for `test_gemini_adapter.py`
   - Postgres URL — required for `test_postgres_backend.py` (if applicable)
   - etc.

**Verify**:
```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Test environment prerequisites"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Test baseline.*1080"  # or whatever final count is
```

Both return one match each.

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-37.6.1..HEAD -- core/worker_base.py cli/ web/server.py adapters/gemini.py tests/ SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
```

**Expected**: empty output (no drift since prompt-37.6.1).

### Gate 2 — Step 1 baseline evidence in CHANGELOG

```
grep -c "Step 1 — Baseline evidence" CHANGELOG.md
```

**Expected**: 1.

### Gate 3 — Warning count reduced to ≤19

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 1
```

**Expected**: line contains `XX warnings` where XX ≤ 19. If higher than 19, investigate which category didn't drop.

### Gate 4 — Category 4 (`on_event`) eliminated

```powershell
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "on_event"
```

**Expected**: zero matches.

### Gate 5 — F7 trace spam fixed (manual TUI verification)

```powershell
jarvis "hello"
```

**Procedure**:
1. Run the command
2. Capture stdout verbatim
3. Verify NO trace events are printed (only the LLM response)
4. Paste the literal output into CHANGELOG

```
Gate 5 — F7 trace spam fix (PASSED)

Command: jarvis "hello"
Output:
<paste verbatim — should be the LLM response only, no trace events>

Trace verification: <"no trace events in output — F7 fixed" / "trace events still present — F7 not fixed">
```

**If trace events still print**: STOP. The default emitter change didn't propagate — likely because `OllamaWorker.__init__` explicitly constructs `ConsoleTraceEmitter()`. Investigate `workers/ollama_worker.py` for an explicit emitter override.

### Gate 6 — `cli/__init__.py` exists

```powershell
Test-Path cli\__init__.py
```

**Expected**: True.

### Gate 7 — Skipped tests reduced to ≤9

```powershell
python -m pytest tests/ -v --tb=no --no-header 2>&1 | Select-String "SKIPPED" | Measure-Object -Line
```

**Expected**: ≤9 (6 trajectory_exporter Plan-45 deferrals + 2 API-key conditional + 1 for any remaining legitimate case).

**If count >9**: investigate the new skips. Either fix or formal-defer with Plan-N ticket.

### Gate 8 — Skipped-test enumeration in CHANGELOG

```
grep -c "Step 10 — Skipped-tests audit" CHANGELOG.md
```

**Expected**: 1. The enumeration must be present as evidence.

### Gate 9 — Rule 19 remediation evidence in CHANGELOG

```powershell
Select-String -Path CHANGELOG.md -Pattern "Gate 5 — Manual TUI test — ACTUAL OUTPUT|Deferred verification — Plan 38.6"
```

**Expected**: at least 1 match. Either the actual TUI output is pasted (Option A — literal output section present) or the Plan 38.6 deferral is recorded (Option B — deferral section present).

**Note on regex syntax**: `Select-String -Pattern` uses .NET regex natively, so the unescaped `|` works as alternation without needing `-E` or escaped `\|`. Do not use bare `grep -c "...\|..."` here — basic grep on some platforms treats `\|` literally, and PowerShell's `grep` alias (if present) maps to `Select-String` with different semantics. Use the PowerShell syntax shown above for consistency with the rest of this plan.

### Gate 10 — Handoff "What works right now" stale count fixed

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "1044 tests pass"
```

**Expected**: zero matches (the stale count is gone).

### Gate 11 — Handoff test environment prerequisites subsection added

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Test environment prerequisites"
```

**Expected**: 1 match.

### Gate 12 — Full test suite

```powershell
python -m pytest tests/ -q --tb=short
```

**Expected**:
- Passed: ≥1080 (same or higher than prompt-37.6.1 final — fix-or-defer should not reduce passing count)
- Skipped: ≤9 (down from 29)
- Failed: 1 (the pre-existing flaky `test_lm_studio_adapter.py::test_health_check_without_server`)
- Warnings: ≤19 (down from 63)

**Acceptable ranges**:
- Passed: {1080, 1081, 1082} — small variations OK if skipped tests converted
- Skipped: {6, 7, 8, 9} — must be ≤9
- Warnings: {15, 16, 17, 18, 19} — must be ≤19

Anything outside these ranges: STOP. Investigate.

## STOP conditions

- **If Step 1 baseline is not 1080/29/1/63** — drift since prompt-37.6.1. Investigate before proceeding.
- **If Step 7 (Gemini migration) production-code diff exceeds 20 lines** — defer to Plan 38.5 (revert partial migration, add `# noqa: W605 — Plan 38.5` inline suppression with ticket reference, add Plan 38.5 to handoff queue, document in CHANGELOG). This is a legitimate temporary suppression, NOT silent noise.
- **If Step 7 (Gemini migration) surfaces unfixable test failures despite being under the 20-line guard** — same deferral procedure as above.
- **If Step 8 (F7) shows trace events still print after default change** — `OllamaWorker` or another worker is explicitly overriding the default. Investigate before proceeding.
- **If Step 10 (skipped-test audit) cannot classify a skip** — STOP. Treat as HIDDEN-BUG and apply mock-at-instantiation pattern. If that fails, formal-defer with new Plan-N ticket.
- **If Step 11 (Rule 19 remediation) cannot execute Option A AND cannot create Plan 38.6 ticket** — STOP. This is exactly the pattern Rule 19 forbids.
- **If Gate 12 shows >9 skipped or >19 warnings** — investigate which Step didn't achieve its expected reduction.
- **If any file outside the in-scope list needs editing** — STOP. Report which file and why.

## Out of scope

- **Broad-except audit** — Plan 38.5+
- **ruff triage** (365 errors) — Plan 43
- **mypy triage** (116 errors) — Plan 44
- **trajectory_exporter functional redesign** — Plan 45 (the 6 skipped tests in test_trajectory_exporter.py stay skipped pending this)
- **Plan 38.6** — only created if Step 11 Option B is taken. Otherwise does not exist.

## Closing steps

**Execute these in order. Do not mark a step done until it's actually done.**

1. `git add` the in-scope files: `core/worker_base.py`, `cli/__init__.py`, `web/server.py`, `adapters/gemini.py`, modified test files, `SOVEREIGN_AI_HANDOFF.md`, `CHANGELOG.md`
2. `git commit -m "fix: prompt-38 — warnings cleanup + skipped-tests audit + F7 trace spam + Rule 19 remediation"`
3. `git tag prompt-38`
4. `git show prompt-38 --stat` — verify file list
5. **Post-tag verification (global_rules.md Rule 20)**: `git rev-parse prompt-38` — confirm hash matches the commit
6. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail with line counts
   - **Implementation Notes**: which warning categories were fixed, which were deferred and why, how many skipped tests converted vs deferred, F7 verification result, Rule 19 remediation result (Option A or B)
   - **Testing Results**: baseline (1080/29/1/63 from 37.6.1) → final (expected ≥1080/≤9/1/≤19)
   - **Verification Gate Output**: literal output of each gate (this is critical — paste everything per Rule 19)
   - **Deferred actions** (if any): list of Plan-N tickets created during this plan
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-38
   - Update test baseline to Gate 12 final count
   - Update "What works right now" prose count (Gate 10)
   - Add "Test environment prerequisites" subsection (Gate 11)
   - Remove F7 from "What's broken right now" section (it's fixed)
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-38 changelog and handoff update"`
10. `git push origin master && git push origin prompt-38`
11. **Post-push verification (global_rules.md Rule 20)**: `git ls-remote --tags origin | grep prompt-38` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 38 lands

Verification discipline is now actually enforced (Rule 19 remediated, not just codified). Test suite is clean enough that new warnings/skips will stand out in code review. The horizontal cleanup queue can now proceed:

- **Plan 38.5** — Broad-except audit, part 1 (core/)
- **Plan 38.6** (only if Step 11 Option B taken) — Manual TUI verification for prompt-37.6.1 Gates 5/6
- **Plan 39** — Broad-except audit, part 2 (system/)
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage (will be larger now that `cli/__init__.py` exists and mypy can scan the cli package)
- **Plan 45+** — graphify integration cluster, proper MemoryBackend.delete(), trajectory_exporter functional redesign (will eliminate the 6 remaining trajectory_exporter skips)

Plans 38.5+ can land in any order. The foundation is clean.