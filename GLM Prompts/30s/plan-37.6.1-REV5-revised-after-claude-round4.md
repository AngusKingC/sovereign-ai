# Plan 37.6.1 REV5 (revised after Claude review round 4): Process discipline rule + 37.6 verification fix-ups

> **This is REV5 of the plan.** Differences from REV4 (the version Claude last reviewed): Claude's round 4 findings applied. Specifically:
> - **Gate 8**: added explicit STOP if `actual_baseline_passed < 1072` or `actual_baseline_skipped < 8` (prevents the `baseline + 8` math from masking a regression where the 8 skipped tests disappeared from the suite).
> - **Step 8**: added IMPORTANT callout preserving em-dash (—) in CHANGELOG headings so Gates 5/6/7 grep strings match.
> - **Step 3a fallback**: clarified that the `partial: global_rules.md-mirror-pending` tag goes in the final closing-step commit message, not a separate intermediate commit.
> - **Step 9**: completely rewritten. Original proposed in-place editing of prompt-37.6's stale "Closing steps" status flags, which violated append-only Rule 16. New Step 9 appends a "Correction note" subsection instead.
> - **Closing step 7**: added explicit instruction to update stale "1044 tests pass" count in handoff's "What works right now" prose.
>
> **Executor instructions**: This plan has two scopes bundled into one small prompt. (1) Add a new architecture rule about sequential execution and evidence-before-marking, addressing a process gap observed in prompt-37.6 where gates were marked PASSED before their producing steps were done. (2) Complete the verification work that prompt-37.6 skipped — fix the 8 skipped tests, run Gates 3/5/6 with literal output, paste evidence into CHANGELOG.
>
> **Critical sequencing rule for THIS plan**: Steps must be executed in listed order. Gates must be run only after their producing step is complete. Gate output must be pasted literally into the CHANGELOG — no "PASSED" without evidence. If you find yourself wanting to mark a gate before its step is done, STOP. That's the exact pattern this plan exists to fix.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-37.6..HEAD -- core/memory_router.py cli/tui.py tests/test_tui.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> If any of these files changed since prompt-37.6, compare the "Current state" against live code before proceeding; on mismatch, STOP.

## Status

- **Priority**: P0 (process discipline gap + verification debt)
- **Effort**: S
- **Risk**: LOW (1 production test file change + verification work + documentation)
- **Depends on**: prompt-37.6 (commit `7a2bf11`, tag `prompt-37.6`)
- **Planned at**: commit `142321e`, 2026-06-18
- **In scope**: 1 test file (`tests/test_tui.py`) + 1 documentation file (`SOVEREIGN_AI_HANDOFF.md`) + 1 changelog (`CHANGELOG.md`) + 1 non-repo memory file (`global_rules.md`, Devin-local)
- **Out of scope**: Plan 38 (F7 trace spam — next plan after this lands), production code changes (37.6's wiring is correct, no changes needed), broad-except audit (Plan 38.5+)

## Why this matters

Prompt-37.6 landed with the production code correct but verification incomplete. Three gates were skipped (Gate 5 manual TUI, Gate 6 adapter swap, Gate 3 has no documented output despite being marked PASSED), and 8 tests in `tests/test_tui.py` were marked `@pytest.mark.skip` with the reason "OllamaAdapter initialization complexity." This is recurring mistake #2 (mock-the-SUT tests with `assert True`) wearing a new hat — tests that exist but never run, giving false confidence that the wiring is verified.

Worse, the task log showed gates being marked PASSED **before** the steps that produce their evidence were complete. For example, Gate 8 ("Handoff 'What works right now' updated") was marked PASSED before Step 6 (the step that updates the handoff) was logged as complete. This is the same root pattern as prompt-37 tagging with 69 failures: marking a gate passed based on intention rather than execution.

This plan does two things:
1. **Codifies a new rule** (Rule 19 in handoff, mirror in `global_rules.md`) making sequential execution and evidence-before-marking explicit. Adds recurring mistake pattern #6 to the handoff documenting the failure mode.
2. **Completes the 37.6 verification work** — fixes the 8 skipped tests using the mock-at-instantiation pattern, runs Gates 3/5/6 with literal output pasted into the CHANGELOG.

## What's broken (verified against live repo at commit 142321e)

### A. 8 skipped tests in `tests/test_tui.py`

All 8 tests in `TestTUICognitionWiring` are decorated with `@pytest.mark.skip(reason="TUI __init__ constructs OllamaAdapter which requires complex initialization. The adapter is used by multiple components (InstructionGenerator, OutputEvaluator, AdapterFallbackChain) and mocking at the class level doesn't work because TUI creates its own instance. Manual verification (Gate 3) confirms memory_router is not None.")`.

**The mocking problem is real but solvable.** The skip reason says "mocking at the class level doesn't work because TUI creates its own instance." The fix is to mock at the point of instantiation, not at the class level:

```python
@pytest.fixture
def app(self):
    """Construct JarvisTUI with OllamaAdapter mocked at instantiation.
    
    Uses yield (not return) so the patch stays active for the duration
    of each test method. This is critical for test_tui_adapter_swap_preserves_memory_router,
    which triggers additional OllamaAdapter constructions during the swap.
    """
    with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
        # Configure the mock INSTANCE that OllamaAdapter() will return
        mock_instance = MagicMock()
        mock_instance.model_name = "llama3"
        mock_instance.is_local = True
        mock_instance.cost_per_token = 0.0
        mock_instance.generate = AsyncMock(return_value=MagicMock(
            content="mock response",
            confidence=0.9,
            model_used="llama3",
            tokens_used=10,
        ))
        mock_instance.health_check = AsyncMock(return_value=True)
        mock_instance.close = AsyncMock()
        mock_adapter_class.return_value = mock_instance
        
        # Now when JarvisTUI calls OllamaAdapter(...), it gets mock_instance.
        # Use yield (NOT return) so the patch stays active for the duration of
        # the test method — required for tests that trigger additional
        # OllamaAdapter() calls (e.g., adapter swap). See Step 4.
        from cli.tui import JarvisTUI
        yield JarvisTUI()
```

With this fixture, all 8 tests can run and verify behavior. The fixture mocks `OllamaAdapter` itself (not its methods), so when `cli/tui.py` does `adapter = OllamaAdapter(...)`, it gets the mock instance. This is the standard "mock at instantiation" pattern. **The `yield` (not `return`) is load-bearing** — see Step 4's IMPORTANT callout for why.

**Verify each test actually exercises behavior** (recurring mistake #2 prevention):
- `test_tui_constructs_memory_router` — assert `app.memory_router is not None` and `hasattr(app.memory_router, 'fetch_by_filter')`
- `test_tui_passes_memory_router_to_orchestrator` — assert `app.orchestrator.memory_router is app.memory_router`
- `test_tui_passes_memory_router_to_worker` — assert `app.worker.memory_router is app.memory_router`
- `test_tui_constructs_approval_gate` — assert `app.orchestrator.approval_gate is not None` and `app.orchestrator.approval_gate.trust_registry is not None`
- `test_tui_constructs_rating_system` — assert `app.orchestrator.improvement_loop is not None` (improvement_loop depends on rating_system)
- `test_tui_constructs_instruction_generator` — assert `app.orchestrator.improvement_loop is not None` (improvement_loop depends on instruction_generator)
- `test_tui_constructs_orchestrator_improvement_loop` — assert `app.orchestrator.improvement_loop is not None`
- `test_tui_adapter_swap_preserves_memory_router` — simulate adapter swap, assert new worker has memory_router (not None) and it's the same object

### B. Gate 3 has no documented output

Prompt-37.6's CHANGELOG says "Gate 3: TUI constructs memory_router (not None) - PASSED" but provides no literal output. The 8 test skip reasons reference "Manual verification (Gate 3) confirms memory_router is not None" — but there's no evidence Gate 3 was actually run.

**Required**: Run Gate 3 with the mock pattern and paste the literal output into the CHANGELOG. Output should look like:
```
memory_router: <MemoryRouter object at 0x...>
orchestrator.memory_router: <MemoryRouter object at 0x...>  (same object)
worker.memory_router: <MemoryRouter object at 0x...>  (same object)
orchestrator.improvement_loop: <OrchestratorImprovementLoop object at 0x...>
orchestrator.approval_gate: <ApprovalGate object at 0x...>
```

### C. Gate 5 (manual TUI test) was skipped

Prompt-37.6 summary: "Steps 5-6 manual verification skipped (relied on Gates 3-4 for verification)." But Gate 4 was 8 skipped tests and Gate 3 has no output. The wiring is entirely unverified at runtime.

**Required**: Actually start `jarvis`, type "hello", paste the response. Type "what did I just say?", paste the response. If memory_router is wired, the second response should reference "hello". Paste both queries and both responses (or the error if it crashes) into the CHANGELOG.

### D. Gate 6 (adapter swap) was skipped

**Required**: In TUI, type `/adapter lm_studio`, then type a query, paste the response. Verify the new worker has `memory_router` (not None). Paste the literal query/response into the CHANGELOG.

### E. Process discipline gap — gates marked before steps done

Prompt-37.6's task log showed gates being marked PASSED before the steps that produce their evidence were complete. For example:
- Gate 8 ("Handoff 'What works right now' updated") marked PASSED before Step 6 (the step that updates the handoff) was logged as complete
- Gate 4 ("TUI constructs full cognition stack") marked PASSED with 8 skipped tests
- Gate 5 and Gate 6 marked SKIPPED (manual verification) — but manual verification was never actually done

This is the same root pattern as prompt-37 tagging with 69 failures: marking a gate passed based on intention rather than execution.

## What to change

### Step 1 — Add Rule 19 to handoff (process discipline)

**File**: `SOVEREIGN_AI_HANDOFF.md`
**Location**: End of "Architecture rules (never violate)" section, after Rule 18.

Add:

```
19. **Execute steps and gates in listed order. Do not mark a step or gate complete until its producing work is done and its evidence exists.** If a gate's evidence requires output from a later step, the plan is out of order — STOP and report. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. Specifically:
    - Do not mark a gate PASSED before running it. "I will run it later" is not acceptable.
    - Do not mark a gate PASSED if its producing step is incomplete. The gate exists to verify the step's output.
    - Do not mark a gate SKIPPED unless the plan explicitly allows skipping it. "Manual verification" is not a skip reason — if the plan calls for manual verification, do the manual verification and paste the result.
    - Do not mark a test `@pytest.mark.skip` for tests that "couldn't be mocked." Fix the mock or refactor the SUT. `pytest.skip` is for known-broken behavior with a Plan-N deferral, NOT for tests that were written but couldn't be made to run.
    (Currently violated by prompt-37.6: Gate 3 marked PASSED with no output, Gate 5 and Gate 6 marked SKIPPED without being skipped per plan, 8 tests marked `@pytest.mark.skip` because mocking was hard. Plan 37.6.1 fixes this and codifies the rule.)
```

### Step 2 — Add recurring mistake pattern #6 to handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`
**Location**: End of "Recurring mistake patterns" section, after pattern #5.

Add:

```
6. **Marking gates passed based on intention rather than execution.** When a plan has steps and gates, the gate verifies the step's output. Marking a gate PASSED before its producing step is complete — or marking it PASSED without pasting literal output — is the same as not running the gate. Prompt-37 was this (Gate 5 tagged with 69 failures). Prompt-37.6 was this (Gate 3 marked PASSED with no output, Gate 5/6 marked SKIPPED without being skipped per plan, 8 tests marked `@pytest.mark.skip` because mocking was hard). The fix is Rule 19: execute in order, paste literal output, do not skip without plan authority.
```

### Step 3 — Add mirror rule to `global_rules.md`

**File**: `C:\Users\King\.codeium\windsurf\memories\global_rules.md` (Windows, Devin-local)

**IMPORTANT — this file is NOT inside the repo workspace.** It lives at an absolute Windows path. Use `Get-Content` / `Test-Path` with the full absolute path, not a workspace-relative lookup. Past skips (prompt-37.1 Step 7, prompt-37.5) happened because Devin treated this as a workspace file and silently skipped when its workspace-relative lookup failed. That silent skip is exactly what Rule 19 (added in Step 1 of this plan) forbids — silent skip is a STOP condition, not an acceptable outcome.

**Step 3a — Verify the file exists and is readable**:

```powershell
Test-Path C:\Users\King\.codeium\windsurf\memories\global_rules.md
```

- If `True` — proceed to Step 3b.
- If `False` — STOP. Do NOT silently skip. Report in CHANGELOG: "`global_rules.md` not found at `C:\Users\King\.codeium\windsurf\memories\global_rules.md`. Cannot add mirror rule. The closing-step commit message MUST include the tag `partial: global_rules.md-mirror-pending` (see Step 3-fallback note in Closing steps). The next plan's drift check must resolve this before landing." Then proceed to the rest of the plan (Steps 4-9) WITHOUT adding the mirror rule. **Do not create a separate intermediate commit for the fallback** — the `partial:` tag goes in the final closing-step commit message (see Closing steps for the conditional commit message template). Add a "Deferred actions" entry to the CHANGELOG so the next plan's drift check surfaces it.

**Step 3b — Read the current file and count existing rules** (per Plan 37.1 Step 7 — do NOT assume the count from memory):

```powershell
Get-Content C:\Users\King\.codeium\windsurf\memories\global_rules.md | Select-String "^Rule \d+"
```

This lists every existing rule line (e.g., `Rule 1:`, `Rule 2:`, ..., `Rule 23:`). The next sequential rule number is `<highest existing number> + 1`.

**Step 3c — Paste the actual `Select-String` output into the CHANGELOG as evidence** (required — this is the only externally-verifiable artifact for Step 3, since the file itself is not in the repo):

```
Step 3 evidence — global_rules.md rule inventory (read before adding Rule N+1):
<literal Select-String output>
Highest existing rule number: <N>
New rule number added: <N+1>
```

**Step 3d — Add the new rule** mirroring the handoff's Rule 19. Append to the file:

```
Rule <N+1>: Execute steps and gates in listed order. Do not mark a step or gate complete until its producing work is done and its evidence exists. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. Do not mark a gate SKIPPED unless the plan explicitly allows it. Do not mark a test @pytest.mark.skip for tests that "couldn't be mocked" — fix the mock or refactor the SUT.
```

Where `<N+1>` is the actual next sequential rule number from Step 3b. If there's a collision (the number is already used), STOP and report — do not silently renumber existing rules.

**Note**: This file is not in the repo and the reviewer cannot verify its contents directly. The CHANGELOG evidence from Step 3c is the only externally-verifiable artifact. Devin must read the file before writing to it (Rule 19 itself — never assert file content from memory), and the literal `Select-String` output must appear in the CHANGELOG — "Rule 24 added" without that evidence is forbidden.

### Step 4 — Fix the 8 skipped tests in `tests/test_tui.py`

**File**: `tests/test_tui.py`

Replace the 8 `@pytest.mark.skip` decorators with the mock-at-instantiation fixture pattern shown in Section A above. All 8 tests should run and pass. (Section A and the fixture below are now consistent — both use `yield JarvisTUI()` with the `self` parameter. Do not copy an older revision of Section A that used `return`.)

**Required fixture** (add at the top of the `TestTUICognitionWiring` class):

**IMPORTANT — use `yield`, not `return`**: The `with patch(...)` context manager must stay active for the duration of each test method, not just during construction. If you use `return JarvisTUI()`, the patch exits as soon as the fixture returns, and any test method that triggers additional `OllamaAdapter(...)` calls (e.g., `test_tui_adapter_swap_preserves_memory_router` simulates swapping adapters, which constructs a new worker and may construct a new `OllamaAdapter`) will hit the real class — likely hanging or throwing a connection error. Using `yield JarvisTUI()` keeps the patch active throughout the test method.

```python
@pytest.fixture
def app(self):
    """Construct JarvisTUI with OllamaAdapter mocked at instantiation.
    
    Uses yield (not return) so the patch stays active for the duration
    of each test method. This is critical for test_tui_adapter_swap_preserves_memory_router,
    which triggers additional OllamaAdapter constructions during the swap.
    """
    with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
        mock_instance = MagicMock()
        mock_instance.model_name = "llama3"
        mock_instance.is_local = True
        mock_instance.cost_per_token = 0.0
        mock_instance.generate = AsyncMock(return_value=MagicMock(
            content="mock response",
            confidence=0.9,
            model_used="llama3",
            tokens_used=10,
        ))
        mock_instance.health_check = AsyncMock(return_value=True)
        mock_instance.close = AsyncMock()
        mock_adapter_class.return_value = mock_instance
        
        from cli.tui import JarvisTUI
        yield JarvisTUI()  # ← yield, NOT return — keeps patch active during test
```

Then update each test to take `app` as a parameter and remove the `@pytest.mark.skip` decorator. The test bodies can stay mostly the same — they were already correct, they just never ran.

**Verify after this step**: `python -m pytest tests/test_tui.py -v --tb=short` — all 8 tests pass (not skipped).

### Step 5 — Run Gate 3 with mock pattern, paste literal output

**Command** (use the mock pattern from the plan's Gate 3 warning):

```python
python -c "
from unittest.mock import patch, AsyncMock, MagicMock
with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
    mock_instance = MagicMock()
    mock_instance.model_name = 'llama3'
    mock_instance.is_local = True
    mock_instance.cost_per_token = 0.0
    mock_instance.generate = AsyncMock()
    mock_instance.health_check = AsyncMock(return_value=True)
    mock_instance.close = AsyncMock()
    mock_adapter_class.return_value = mock_instance
    
    from cli.tui import JarvisTUI
    app = JarvisTUI()
    print('memory_router:', app.memory_router)
    print('orchestrator.memory_router:', app.orchestrator.memory_router)
    print('same object:', app.memory_router is app.orchestrator.memory_router)
    print('worker.memory_router:', getattr(app.worker, 'memory_router', 'MISSING'))
    print('orchestrator.improvement_loop:', app.orchestrator.improvement_loop)
    print('orchestrator.approval_gate:', getattr(app.orchestrator, 'approval_gate', 'MISSING'))
"
```

**Expected output** (literal — paste into CHANGELOG):
```
memory_router: <MemoryRouter object at 0x...>
orchestrator.memory_router: <MemoryRouter object at 0x...>
same object: True
worker.memory_router: <MemoryRouter object at 0x...>
orchestrator.improvement_loop: <OrchestratorImprovementLoop object at 0x...>
orchestrator.approval_gate: <ApprovalGate object at 0x...>
```

**If `same object: False`** — STOP. The wiring is wrong; orchestrator is getting a different memory_router than the one constructed. Investigate before proceeding.

**If `worker.memory_router: MISSING`** — STOP. The worker doesn't expose memory_router. Check `workers/ollama_worker.py`'s attribute name (might be `_memory_router` or similar).

### Step 6 — Run Gate 5 (manual TUI test), paste literal output

**Command**: `python -m cli.tui` (or whatever the TUI entry point is — check `cli/main.py`)

**Procedure**:
1. Start the TUI
2. Type `hello` and press Enter
3. Copy the response verbatim
4. Type `what did I just say?` and press Enter
5. Copy the response verbatim
6. If memory_router is wired, the second response should reference "hello" (or at least not be empty)
7. Exit the TUI

**Paste into CHANGELOG**:
```
Gate 5 — Manual TUI test (PASSED)

Query 1: "hello"
Response 1: <paste verbatim>

Query 2: "what did I just say?"
Response 2: <paste verbatim>

Memory verification: <"response references hello" / "response does not reference hello — memory may not be wired correctly" / "TUI crashed: <error>">
```

**If TUI crashes on startup**: STOP. The wiring is wrong. Investigate before proceeding. Common causes:
- Circular import (cognition stack imports something that imports TUI)
- Missing required argument to a component
- `emitter` mismatch

**If TUI starts but queries fail**: STOP. The wiring may be partially wrong (e.g., worker has memory_router but orchestrator doesn't). Investigate.

### Step 7 — Run Gate 6 (adapter swap), paste literal output

**Procedure** (in the running TUI from Step 6):
1. Type `/adapter lm_studio` and press Enter
2. Type `test query after swap` and press Enter
3. Copy the response verbatim
4. Verify the new worker has `memory_router` (not None) — this can be checked via a trace event or by querying the orchestrator's worker registry

**Paste into CHANGELOG**:
```
Gate 6 — Adapter swap test (PASSED)

Adapter swap command: "/adapter lm_studio"
Swap result: <"success" / "error: <error>">

Query after swap: "test query after swap"
Response: <paste verbatim>

Memory router preserved: <"yes — new worker has memory_router" / "no — new worker has memory_router=None">
```

**If adapter swap crashes or new worker has `memory_router=None`**: STOP. The adapter-swap path at `cli/tui.py:494` is wrong. Investigate.

### Step 8 — Update CHANGELOG with literal gate output

**File**: `CHANGELOG.md`

Append to prompt-37.6's entry (do not edit history — append-only per global_rules.md Rule 16):

**IMPORTANT — preserve the em-dash (—) character verbatim in the headings below.** Gates 5, 6, and 7 grep for `Gate N — <heading> — ACTUAL OUTPUT` using em-dash, not hyphen. If you retype the headings with hyphens (`-`) the grep returns 0 and the gate fails even though the content is present. Copy-paste the headings from this plan, do not retype them.

```
### Verification Gate Output (CORRECTION — added in Plan 37.6.1)

The original prompt-37.6 entry marked Gates 3, 5, 6 as PASSED/SKIPPED without literal output. This section provides the actual output.

#### Gate 3 — TUI constructs memory_router (not None) — ACTUAL OUTPUT

<paste literal output from Step 5>

#### Gate 5 — Manual TUI test — ACTUAL OUTPUT

<paste literal output from Step 6>

#### Gate 6 — Adapter swap test — ACTUAL OUTPUT

<paste literal output from Step 7>

#### Test file fix-up

The original 8 tests in tests/test_tui.py were @pytest.mark.skip. Plan 37.6.1 Step 4 fixed them using the mock-at-instantiation pattern. All 8 now run and pass.
```

### Step 9 — Append correction note for 37.6's stale "Closing steps" status flags (NOT an in-place edit)

**File**: `CHANGELOG.md`

**Append-only Rule 16 (global_rules.md) forbids editing historical entries in place.** Prompt-37.6's entry has a "Closing steps" section with stale status flags (`- Update CHANGELOG.md with this entry - IN PROGRESS`, etc.). The original draft of this plan proposed editing those flags in place — that would violate Rule 16. This step is corrected: do **not** edit 37.6's entry. Instead, append a correction note to the 37.6.1 entry you're writing in Step 8.

Append the following subsection to the 37.6.1 CHANGELOG entry (inside the same appended block from Step 8, not as a separate commit):

```
#### Correction note for prompt-37.6's "Closing steps" status flags

Prompt-37.6's CHANGELOG entry shows its "Closing steps" section with status flags `IN PROGRESS` / `PENDING` for tasks that are actually DONE (commits are pushed, tags exist on remote). This is a stale snapshot from when 37.6 was in progress. Per Rule 16 (append-only), the historical entry is not edited in place. This note records the correction: all three closing steps for prompt-37.6 are DONE.
```

If you find yourself tempted to edit 37.6's status flags in place, STOP. Append the correction note above instead. Editing history is recurring mistake #4 territory (broad-except hiding real failures) in spirit — it hides the original state. The correction note preserves the audit trail.

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-37.6..HEAD -- core/memory_router.py cli/tui.py tests/test_tui.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
```

**Expected**: empty output (no drift since prompt-37.6).

### Gate 2 — Rule 19 in handoff

```
grep -c "^19\. " SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 1 (the new Rule 19).

### Gate 3 — Recurring mistake pattern #6 in handoff

```
grep -c "^6\. \*\*Marking gates passed based on intention" SOVEREIGN_AI_HANDOFF.md
```

**Expected**: 1 (the new pattern #6).

### Gate 4 — 8 tests run and pass

```
python -m pytest tests/test_tui.py -v --tb=short
```

**Expected**: 8 passed, 0 skipped. If any test is still `@pytest.mark.skip`, STOP — the mock pattern wasn't applied correctly.

### Gate 5 — Gate 3 output pasted in CHANGELOG

```
grep -c "Gate 3 — TUI constructs memory_router (not None) — ACTUAL OUTPUT" CHANGELOG.md
```

**Expected**: 1 (the literal output section added in Step 8).

### Gate 6 — Gate 5 output pasted in CHANGELOG

```
grep -c "Gate 5 — Manual TUI test — ACTUAL OUTPUT" CHANGELOG.md
```

**Expected**: 1.

### Gate 7 — Gate 6 output pasted in CHANGELOG

```
grep -c "Gate 6 — Adapter swap test — ACTUAL OUTPUT" CHANGELOG.md
```

**Expected**: 1.

### Gate 8 — Full test suite

**Before starting Step 1, verify the baseline**: Run `python -m pytest tests/ -q --tb=short` and note the actual count. The expected baseline is `1072 passed, 37 skipped, 1 failed, 63 warnings` (verified in CHANGELOG and handoff). If the actual count differs from 1072/37, record the actual baseline in the CHANGELOG and adjust the Gate 8 expected final count accordingly (actual_baseline_passed + 8 = expected_final_passed, actual_baseline_skipped - 8 = expected_final_skipped).

**STOP BEFORE PROCEEDING — regression check**: If `actual_baseline_passed < 1072`, STOP. The test suite has regressed since prompt-37.6 — the 8 tests that 37.6 added as `@pytest.mark.skip` may have disappeared entirely (deleted, or never committed, or skipped at collection time). The math `baseline_passed + 8` would still produce 1080 and mask the regression. Investigate before converting skip→pass.

```
python -m pytest tests/ -q --tb=short
```

**Expected** (assuming baseline is 1072/37 as verified):
- Baseline (post prompt-37.6): **1072 passed, 37 skipped, 1 failed (flaky), 63 warnings**
- After prompt-37.6.1: **1080 passed** (1072 + 8 tests that were skipped, now running and passing), 29 skipped (37 - 8), 1 failed (flaky), ~63 warnings
- Acceptable range: **{1079, 1080, 1081}**. Anything outside is a regression. STOP.

**Note**: The math here is the inverse of prompt-37.6's. 37.6 added 8 tests as skipped (1072/37). 37.6.1 converts those 8 from skipped to passing (1080/29). If the count is 1072/37, the tests are still skipped — STOP, Step 4 didn't work.

**If the actual baseline differs from 1072/37** (e.g., Devin's environment has different optional deps installed, or other tests were skipped/added between plan-authoring and plan-execution), use the formula: `expected_final_passed = actual_baseline_passed + 8`, `expected_final_skipped = actual_baseline_skipped - 8`. Document the actual baseline in the CHANGELOG.

**Hard floor — regression check**: `actual_baseline_passed >= 1072` MUST hold. If it doesn't, the 8 tests that 37.6 added as skipped are gone from the suite entirely (deleted, missing import, collection error), and the `baseline + 8` math will silently mask the regression. STOP and investigate before converting skip→pass. Same logic for `actual_baseline_skipped >= 8` — if there aren't at least 8 skipped tests in the baseline, there's nothing to unskip.

### Gate 9 — Rule 19 honored (no gates marked before steps done)

Implicit in this plan's execution. If you're reading this and Gates 2-8 are all PASSED with literal output, Rule 19 is honored for this prompt.

### Gate 10 — `global_rules.md` updated

Cannot be verified from the repo (file is Devin-local). Devin must confirm in the CHANGELOG that `global_rules.md` was updated with the mirror rule, and report the actual rule number used.

## STOP conditions

- **If Step 4 (fix 8 tests) cannot make the tests pass** with the mock-at-instantiation pattern, STOP. The TUI may have a deeper wiring issue. Document the failure mode and defer to a refactor plan.
- **If Step 5 (Gate 3) shows `same object: False`** — orchestrator is getting a different memory_router. STOP. Wiring bug.
- **If Step 6 (Gate 5) TUI crashes on startup** — STOP. Wiring bug.
- **If Step 6 (Gate 5) queries fail** — STOP. Partial wiring bug.
- **If Step 7 (Gate 6) adapter swap crashes or new worker has `memory_router=None`** — STOP. Adapter-swap path bug.
- **If Gate 8 actual_baseline_passed < 1072** — STOP. Test suite regressed since 37.6; the 8 skipped tests may have disappeared. Investigate before converting skip→pass.
- **If Gate 8 actual_baseline_skipped < 8** — STOP. Not enough skipped tests to unskip; 37.6's 8 skipped tests may have been deleted or are failing at collection.
- **If Gate 8 shows anything other than {1079, 1080, 1081} passed** — STOP. Regression.
- **If any file outside the in-scope list needs editing** — STOP. Report which file and why.

## Out of scope

- **Plan 38 (F7 trace spam)** — next plan after this lands
- **Broad-except audit** — Plan 38.5+
- **Production code changes** — 37.6's wiring is correct (verified by inspection); only test file changes here
- **`cli/rich_cli.py`** — separate path, separate plan
- **Rule 18 amendment about `@pytest.mark.skip` abuse** — folded into Rule 19 (which mentions it explicitly)

## Closing steps

**Execute these in order. Do not mark a step done until it's actually done.**

1. `git add` the in-scope files: `tests/test_tui.py`, `SOVEREIGN_AI_HANDOFF.md`, `CHANGELOG.md`
2. `git commit -m "fix: prompt-37.6.1 — process discipline rule (Rule 19) + 37.6 verification fix-ups"`
   - **Conditional — Step 3 fallback fired?** If Step 3a reported `global_rules.md` not found and the `partial: global_rules.md-mirror-pending` tag is required, amend the commit message to: `"fix: prompt-37.6.1 — process discipline rule (Rule 19) + 37.6 verification fix-ups [partial: global_rules.md-mirror-pending]"`. Do not create a separate commit for the partial marker — fold it into this commit message.
3. `git tag prompt-37.6.1`
4. `git show prompt-37.6.1 --stat` — verify file list
5. **Post-tag verification (global_rules.md Rule 20)**: `git rev-parse prompt-37.6.1` — confirm hash matches the commit
6. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: per-file detail
   - **Implementation Notes**: which mock pattern was used, any tests that needed additional mocking beyond OllamaAdapter, any manual verification surprises
   - **Testing Results**: baseline (1072/37 from 37.6) → final (expected 1080/29). Include the actual baseline count measured at the start of execution.
   - **Verification Gate Output**: literal output of each gate (this is the whole point of this plan — paste everything)
   - **Deferred actions** (if Step 3 fallback fired): note that `global_rules.md` mirror rule is pending and the next plan's drift check must resolve it.
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-37.6.1
   - Update test baseline to the Gate 8 final count (both the headline "Test baseline" line near the top AND any "What works right now" prose that references a specific pass count — Claude's review caught that the handoff's "What works right now" section still says "1044 tests pass", which is stale from pre-37.5. Correct any stale count to the actual final count from Gate 8.)
   - Confirm Rule 19 (Step 1) and pattern #6 (Step 2) are present
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-37.6.1 changelog and handoff update"`
10. `git push origin master && git push origin prompt-37.6.1`
11. **Post-push verification (global_rules.md Rule 20)**: `git ls-remote --tags origin | grep prompt-37.6.1` — verify the tag exists on the remote. **Do not skip this step.**
12. **Update `global_rules.md` locally** (Step 3) — confirm in CHANGELOG that this was done, with the actual rule number used. If Step 3 fallback fired, the CHANGELOG already records the deferral from Step 3a.

## After Plan 37.6.1 lands

Process discipline is codified. Verification debt from 37.6 is cleared. The queue can now proceed to horizontal cleanup:

- **Plan 38** — F7 trace spam + `cli/__init__.py` (was Plan 38 before resequencing)
- **Plan 38.5** — Broad-except audit, part 1 (core/)
- **Plan 39** — Broad-except audit, part 2 (system/)
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45+** — graphify integration cluster, proper MemoryBackend.delete(), trajectory_exporter functional redesign

Plans 38+ can land in any order. The foundation is done. Process discipline is in place. Horizontal cleanup work won't be blocked by functional bugs or verification debt.
