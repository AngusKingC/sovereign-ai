# Plan 38.6: Manual TUI verification for prompt-37.6.1 Gates 5/6 (Rule 19 remediation)

> **This is REV1 of Plan 38.6.** Single-scope plan: execute the manual TUI verification that prompt-37.6.1 deferred to here. This closes the Rule 19 violation loop — prompt-37.6.1 marked Gates 5/6 SKIPPED with "manual verification requires interactive TUI session" reasoning that Rule 19 explicitly forbids. This plan either does the verification or formally defers again with a new Plan-N ticket. No silent skip allowed.
>
> **Critical sequencing rule**: Same as Rule 19. Paste literal output. No "PASSED" without evidence. No "SKIPPED" without plan authority.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-38.5..HEAD -- cli/tui.py cli/main.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> If any of these files changed since prompt-38.5, compare against live code; on mismatch, STOP.

## Status

- **Priority**: P1 (process discipline — closes Rule 19 violation loop)
- **Effort**: S (single manual verification session, ~15-30 minutes of TUI interaction)
- **Risk**: LOW (no code changes — verification only)
- **Depends on**: prompt-38.5 (commit `669799d`, tag `prompt-38.5`)
- **In scope**: `CHANGELOG.md` (append verification evidence), `SOVEREIGN_AI_HANDOFF.md` (update "Last updated" line, remove Plan 38.6 from deferred-actions list)
- **Out of scope**: production code, test code, any file edits beyond docs

## Why this matters

Prompt-37.6.1 added Rule 19 to the handoff, then immediately violated Rule 19 by marking Gates 5/6 SKIPPED with reasoning Rule 19 explicitly forbids. The CHANGELOG entry at line 7221-7237 records the deferral:

> "The prompt-37.6.1 plan called for manual TUI verification (Steps 6 and 7). Devin marked them SKIPPED. Rule 19 (which Devin himself just added) forbids this."
>
> "Decision: Option B - Formally defer with Plan-N ticket. Option A (execute manual verification now) is not possible in this automated execution environment (no interactive shell available for TUI mode)."
>
> "Deferral: Plan 38.6 - 'Manual TUI verification for prompt-37.6.1 Gates 5/6'"

This plan is Plan 38.6. **It exists to either execute the verification or formally defer again — but not to silently skip.** If the verification environment still lacks an interactive shell, this plan must create Plan 38.8 (or similar) as the next deferral target, with explicit reasoning and a concrete plan for when it will become possible.

Per Rule 19 (handoff line 326): *"Do not mark a gate SKIPPED unless the plan explicitly allows skipping it. 'Manual verification' is not a skip reason — if the plan calls for manual verification, do the manual verification and paste the result."*

## What's broken

Prompt-37.6.1's CHANGELOG entry (lines 6881-6887) contains:

```
#### Gate 5 — Manual TUI test — ACTUAL OUTPUT

SKIPPED - Manual verification requires interactive TUI session. This is an
automated execution environment. The 8 automated tests in test_tui.py now pass
(previously skipped), verifying the wiring programmatically.

#### Gate 6 — Adapter swap test — ACTUAL OUTPUT

SKIPPED - Manual verification requires interactive TUI session. The
test_tui_adapter_swap_preserves_memory_router test now passes (previously
skipped), verifying the adapter swap preserves memory_router programmatically.
```

These are the exact "SKIPPED with manual verification reasoning" entries Rule 19 forbids. The automated tests passing does not substitute for the manual verification the plan called for — that's the whole point of Rule 19.

**Verification required** (per prompt-37.6.1 CHANGELOG line 7227-7235, which is itself the deferral contract):

1. Start `jarvis` (TUI mode)
2. Type `hello`, paste the response verbatim into CHANGELOG
3. Type `what did I just say?`, paste the response verbatim
4. Verify the second response references "hello" (memory_router wired correctly)
5. Type `/adapter lm_studio`, paste the swap result
6. Type `test query after swap`, paste the response
7. Verify the new worker has `memory_router` (not None) after the swap
8. Exit TUI

## What to change

### Step 1 — Drift check + baseline evidence

```powershell
# Drift check
git diff --stat prompt-38.5..HEAD -- cli/tui.py cli/main.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md

# Baseline test counts (must match prompt-38.5 final state)
python -m pytest tests/ -q --tb=short 2>&1 | Select-Object -Last 3
```

**Expected baseline**: 1080 passed, 29 skipped, 1 failed (flaky lm_studio), 1 warning (Gemini suppressed).

**STOP if baseline doesn't match.** Investigate drift.

**Paste literal output into CHANGELOG as Step 1 evidence** (Rule 19).

### Step 2 — Verify F7 trace spam fix is in place

Before testing the TUI, verify the F7 fix from prompt-38 is still in effect. The TUI manual test will be much harder to interpret if trace events are spamming stdout alongside the LLM response.

```powershell
# Verify WorkerBase default emitter is MemoryTraceEmitter (F7 fix from prompt-38)
Select-String -Path C:\Jarvis\core\worker_base.py -Pattern "MemoryTraceEmitter|ConsoleTraceEmitter"
```

**Expected**: At least one match for `MemoryTraceEmitter` as the default. No matches for `ConsoleTraceEmitter` as a default (it's fine if it appears as an explicit opt-in elsewhere).

**If ConsoleTraceEmitter is still the default**: STOP. F7 regression — investigate before proceeding. The TUI manual test will be unreadable if trace events are spamming stdout.

**Paste literal output into CHANGELOG.**

### Step 3 — Execute Gate 5 (manual TUI test — memory_router verification)

**This step requires an interactive shell.** If the execution environment doesn't have one, skip to Step 3-DEFERRED below.

#### Step 3a — Start the TUI

```powershell
cd C:\Jarvis
python -m cli.tui
```

Or equivalently:

```powershell
cd C:\Jarvis
python -m cli.main
```

(The TUI entry point is `cli.tui:main` per `cli/main.py:135-136`.)

**If TUI crashes on startup**: STOP. Document the error verbatim in CHANGELOG. Common causes:
- Circular import (cognition stack imports something that imports TUI)
- Missing required argument to a component
- `emitter` mismatch
- Ollama not running (TUI may try to connect on startup)

**If TUI starts successfully**: proceed to Step 3b.

#### Step 3b — Type "hello" and capture response

In the TUI, type `hello` and press Enter.

**Capture the response verbatim** (copy-paste the entire response text, not a summary). Include any error messages, trace events (should be none after F7 fix), or unexpected output.

**If the response is empty or an error**: STOP. The wiring may be wrong. Document verbatim in CHANGELOG.

#### Step 3c — Type "what did I just say?" and capture response

In the TUI, type `what did I just say?` and press Enter.

**Capture the response verbatim.**

**Memory router verification**: The second response should reference "hello" (or otherwise demonstrate that the TUI has access to conversation history). If the response is "I don't know what you said" or similar, the memory_router may not be wired correctly into the orchestrator's query handler.

**Paste both queries and both responses into CHANGELOG** (Rule 19 — literal output, not summary):

```
#### Gate 5 — Manual TUI test (prompt-37.6.1 remediation) — ACTUAL OUTPUT

Query 1: "hello"
Response 1: <paste verbatim>

Query 2: "what did I just say?"
Response 2: <paste verbatim>

Memory verification: <"response references hello — memory_router wired correctly" / "response does not reference hello — memory_router may not be wired correctly" / "TUI crashed: <error>">
```

#### Step 3-DEFERRED (only if no interactive shell available)

If Step 3a cannot be executed because the environment lacks an interactive shell:

1. **Do NOT mark Step 3 as SKIPPED.** That's the exact Rule 19 violation pattern this plan exists to fix.
2. Create a new deferral ticket: **Plan 38.8 — Manual TUI verification for prompt-37.6.1 Gates 5/6 (second deferral)**.
3. Document in CHANGELOG:

```
#### Gate 5 — Manual TUI test (prompt-37.6.1 remediation) — SECOND DEFERRAL

Plan 38.6 was created to execute the manual TUI verification deferred from
prompt-37.6.1. Plan 38.6 also lacks an interactive shell in this execution
environment. Per Rule 19, this cannot be silently skipped — it must be
formally deferred again.

New deferral target: Plan 38.8 — Manual TUI verification (second deferral).

When Plan 38.8 will become possible: <concrete trigger condition, e.g., "when
the execution environment gains an interactive shell", "when the user
executes this plan manually on their Windows machine", etc.>
```

4. Add Plan 38.8 to `SOVEREIGN_AI_HANDOFF.md`'s deferred-actions list.
5. Proceed to Step 4 (Gate 6) — same deferral logic applies if it can't be executed.

**Note**: A second deferral is allowed by Rule 19, but a third deferral should trigger a re-evaluation of whether manual TUI verification is the right approach. Maybe the verification should be automated (rewrite the test_tui_adapter_swap_preserves_memory_router test to exercise more of the TUI flow), or maybe the manual verification requirement should be removed from the plan template entirely. That's a future plan's decision.

### Step 4 — Execute Gate 6 (adapter swap test)

**This step requires the TUI from Step 3 still running.** If Step 3 was deferred, Step 4 must also be deferred (same reason).

#### Step 4a — Type `/adapter lm_studio` and capture swap result

In the running TUI, type `/adapter lm_studio` and press Enter.

**Capture the swap result verbatim.** Include any error messages, success indicators, or unexpected output.

**If adapter swap crashes**: STOP. The adapter-swap path at `cli/tui.py:491-497` (`_on_adapter_selected` method) may be wrong. Document verbatim in CHANGELOG.

#### Step 4b — Type "test query after swap" and capture response

Type `test query after swap` and press Enter.

**Capture the response verbatim.**

#### Step 4c — Verify new worker has memory_router (not None)

This is harder to verify from the TUI itself (the worker's `memory_router` attribute isn't directly visible in the UI). Options:

**Option A — Trace event inspection**: If the TUI emits trace events for adapter swaps (it should, via the `emitter`), inspect the trace to verify `memory_router` is not None on the new worker.

**Option B — Programmatic check via separate Python session**:

```powershell
# In a separate PowerShell window (TUI still running in the first)
cd C:\Jarvis
python -c "
from unittest.mock import patch, AsyncMock, MagicMock
with patch('adapters.ollama.OllamaAdapter'):
    from cli.tui import JarvisTUI
    app = JarvisTUI()
    original_memory_router = app.worker.memory_router
    # Simulate the adapter swap
    from cli.adapter_factory import create_worker
    new_worker = create_worker('lm_studio', 'llama3', memory_router=app.memory_router)
    print('Original memory_router:', original_memory_router)
    print('New worker memory_router:', new_worker.memory_router)
    print('Same object:', new_worker.memory_router is original_memory_router)
    print('Not None:', new_worker.memory_router is not None)
"
```

This duplicates the logic of `test_tui_adapter_swap_preserves_memory_router` but lets you verify it interactively while the TUI is running.

**Option C — TUI command**: If the TUI has a `/status` or `/inspect` command that shows the current worker's memory_router state, use that. (Check `cli/tui.py` for available slash commands.)

**Paste the swap result, query response, and memory_router verification into CHANGELOG**:

```
#### Gate 6 — Adapter swap test (prompt-37.6.1 remediation) — ACTUAL OUTPUT

Adapter swap command: "/adapter lm_studio"
Swap result: <paste verbatim>

Query after swap: "test query after swap"
Response: <paste verbatim>

Memory router preserved: <"yes — new worker has memory_router (verified via <option A/B/C>)" / "no — new worker has memory_router=None" / "could not verify: <reason>">
```

**If memory_router is None after swap**: STOP. The adapter-swap path at `cli/tui.py:491-497` is wrong — `memory_router` isn't being passed to the new worker. Document verbatim in CHANGELOG.

#### Step 4-DEFERRED (only if Step 3 was deferred)

If Step 3 was deferred to Plan 38.8, Step 4 must also be deferred to Plan 38.8. Document in CHANGELOG:

```
#### Gate 6 — Adapter swap test (prompt-37.6.1 remediation) — SECOND DEFERRAL

Plan 38.6 also lacks an interactive shell. Deferred to Plan 38.8 alongside
Gate 5. See Gate 5 second deferral entry above for details.
```

### Step 5 — Exit TUI

If the TUI is still running from Steps 3-4:

Type `/exit` (or press Ctrl+C if no `/exit` command) to exit cleanly.

**If TUI hangs on exit**: Document in CHANGELOG (this is a real bug, separate from the verification).

### Step 6 — Update CHANGELOG with all verification evidence

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only) a new section for prompt-38.6:

```
## Prompt 38.6 — Manual TUI verification for prompt-37.6.1 Gates 5/6

### Why this matters
Prompt-37.6.1 violated Rule 19 by marking Gates 5/6 SKIPPED with "manual
verification requires interactive TUI session" reasoning. This plan either
executes the verification or formally defers again — no silent skip.

### Step 1 — Baseline evidence
<literal pytest output>

### Step 2 — F7 fix verification
<literal Select-String output>

### Step 3 — Gate 5 (manual TUI test)
<either literal TUI output per Step 3b/3c, OR Step 3-DEFERRED documentation>

### Step 4 — Gate 6 (adapter swap test)
<either literal TUI output per Step 4a/4b/4c, OR Step 4-DEFERRED documentation>

### Step 5 — TUI exit
<exit behavior>

### Result
<either "Gates 5/6 executed — Rule 19 violation closed" OR "Gates 5/6 deferred to Plan 38.8 — Rule 19 violation still open, formally tracked">
```

### Step 7 — Update handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`

**Changes**:
1. Update "Last updated" line to reference prompt-38.6
2. **If Gates 5/6 executed successfully**: Remove Plan 38.6 from deferred-actions list (it's done). Update "Recently fixed" section to note prompt-37.6.1's Rule 19 violation is now closed.
3. **If Gates 5/6 deferred to Plan 38.8**: Replace "Plan 38.6" with "Plan 38.8" in deferred-actions list. Add a note about the second deferral and the trigger condition for when Plan 38.8 will become possible.

## Verification gates

### Gate 1 — Drift check

```powershell
git diff --stat prompt-38.5..HEAD -- cli/tui.py cli/main.py
```

**Expected**: empty output (no code drift since prompt-38.5).

**Allowed**: Non-empty for `SOVEREIGN_AI_HANDOFF.md` and `CHANGELOG.md` (standard docs-commit drift, per known landmine).

### Gate 2 — Step 1 baseline evidence in CHANGELOG

```powershell
Select-String -Path CHANGELOG.md -Pattern "Step 1 — Baseline evidence"
```

**Expected**: 1 match.

### Gate 3 — F7 fix verified in place

```powershell
Select-String -Path C:\Jarvis\core\worker_base.py -Pattern "MemoryTraceEmitter"
```

**Expected**: at least 1 match.

### Gate 4 — Gate 5 evidence in CHANGELOG

```powershell
Select-String -Path CHANGELOG.md -Pattern "Gate 5 — Manual TUI test \(prompt-37.6.1 remediation\) — ACTUAL OUTPUT|Gate 5 — Manual TUI test \(prompt-37.6.1 remediation\) — SECOND DEFERRAL"
```

**Expected**: at least 1 match (either executed or second-deferral documented).

### Gate 5 — Gate 6 evidence in CHANGELOG

```powershell
Select-String -Path CHANGELOG.md -Pattern "Gate 6 — Adapter swap test \(prompt-37.6.1 remediation\) — ACTUAL OUTPUT|Gate 6 — Adapter swap test \(prompt-37.6.1 remediation\) — SECOND DEFERRAL"
```

**Expected**: at least 1 match.

### Gate 6 — Handoff updated correctly

```powershell
# If Gates 5/6 executed:
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Plan 38.6" | Where-Object { $_.Line -match "deferred|pending" }
# Expected: zero matches (Plan 38.6 removed from deferred list)

# If Gates 5/6 deferred to Plan 38.8:
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Plan 38.8"
# Expected: at least 1 match (Plan 38.8 added to deferred list)
```

## STOP conditions

- **If Step 1 baseline is not 1080/29/1/1** — drift since prompt-38.5. Investigate.
- **If Step 2 shows ConsoleTraceEmitter as default** — F7 regression. Investigate before proceeding.
- **If Step 3a TUI crashes on startup** — wiring bug. Document verbatim, STOP.
- **If Step 3b response is empty or error** — partial wiring bug. Document verbatim, STOP.
- **If Step 3c response doesn't reference "hello"** — memory_router not wired into query handler. Document, STOP.
- **If Step 4a adapter swap crashes** — adapter-swap path bug at `cli/tui.py:491-497`. Document, STOP.
- **If Step 4c memory_router is None after swap** — adapter-swap path doesn't pass memory_router to new worker. Document, STOP.
- **If Step 3-DEFERRED is taken AND Plan 38.8 isn't created** — Rule 19 violation. A second deferral is allowed but must be formally tracked with a new Plan-N ticket.
- **If any file outside the in-scope list needs editing** — STOP. This plan is verification only, no code changes.

## Out of scope

- Any production code changes (verification only)
- Any test code changes
- Plan 38.7 (Gemini SDK migration) — separate plan
- Plan 39 (broad-except audit, system/) — separate plan
- Re-evaluating whether manual TUI verification should be replaced with automated verification — that's a future plan's decision if Plan 38.8 also has to defer

## Closing steps

**Execute these in order. Do not mark a step done until it's actually done.**

1. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md` (only docs — no code changes in this plan)
2. `git commit -m "docs: prompt-38.6 — manual TUI verification for prompt-37.6.1 Gates 5/6 (Rule 19 remediation)"`
   - **Conditional — second deferral?** If Gates 5/6 deferred to Plan 38.8, append: ` [partial: tui-verification-deferred-to-38.8]`
3. `git tag prompt-38.6`
4. `git show prompt-38.6 --stat` — verify only CHANGELOG and handoff were modified
5. `git rev-parse prompt-38.6` — confirm hash matches the commit
6. Update `CHANGELOG.md` (if not already done in Step 6) with:
   - All Step evidence (1, 2, 3 or 3-DEFERRED, 4 or 4-DEFERRED, 5)
   - Final result: "Gates 5/6 executed" OR "Gates 5/6 deferred to Plan 38.8"
7. Update `SOVEREIGN_AI_HANDOFF.md` (if not already done in Step 7):
   - "Last updated" line references prompt-38.6
   - If executed: Plan 38.6 removed from deferred list, "Recently fixed" section updated
   - If deferred: Plan 38.8 added to deferred list with trigger condition
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md` (if updates in steps 6-7 weren't already committed)
9. `git commit -m "docs: prompt-38.6 changelog and handoff update"` (if not already committed in step 2)
10. `git push origin master && git push origin prompt-38.6`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-38.6` — verify the tag exists on the remote. **Do not skip this step.** (Per known landmine: prompt-38's tag-push gate was skipped — must not recur.)

## After Plan 38.6 lands

Two outcomes:

### Outcome A — Gates 5/6 executed successfully

Rule 19 violation from prompt-37.6.1 is closed. The "deferred to Plan 38.6" entries in prompt-37.6.1's CHANGELOG section now have actual evidence in prompt-38.6's CHANGELOG section. The audit trail is complete.

### Outcome B — Gates 5/6 deferred to Plan 38.8

Rule 19 violation from prompt-37.6.1 is still open, but now formally tracked through two deferral tickets (Plan 38.6 → Plan 38.8). The third deferral (if it happens) should trigger re-evaluation of whether manual TUI verification is the right approach.

Either way, the next plans in the queue are:

- **Plan 38.7** — Gemini SDK migration (eliminates the last remaining warning)
- **Plan 39** — Broad-except audit, part 2 (system/) — ~132 sites in resource_manager, model_acquisition, profiler, model_registry, monitor_daemon

Plans 38.7 and 39 can land in parallel with Plan 38.8 (if created) — they're independent.

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This is a small focused plan to close the Rule 19 violation loop from prompt-37.6.1. Check that:

1. The plan correctly addresses the Rule 19 violation — either executes the manual verification or formally defers again with a new Plan-N ticket. No silent skip path.

2. The STOP conditions are real — every place something could go wrong (TUI crash, empty response, memory_router None after swap) has an explicit STOP, not silent continuation.

3. The Step 3-DEFERRED and Step 4-DEFERRED paths correctly create Plan 38.8 as the next deferral target, with a concrete trigger condition for when Plan 38.8 will become possible.

4. The verification commands are correct:
   - `python -m cli.tui` is the right TUI entry point (per `cli/main.py:135-136`)
   - `python -m cli.main` is the equivalent fallback
   - The adapter swap path at `cli/tui.py:491-497` is correctly identified as `_on_adapter_selected`
   - The programmatic memory_router check (Option B in Step 4c) correctly uses `cli.adapter_factory.create_worker`

5. The closing-step structure is consistent with the standard prompt template. Tag-push gate (closing step 11) is explicit and references the prompt-38 landmine.

6. The "Outcome A vs Outcome B" framing in the "After Plan 38.6 lands" section correctly distinguishes the two possible results and what each means for the Rule 19 violation loop.

7. The plan doesn't try to fix the underlying Rule 19 violation pattern itself — that's a meta-concern for a future plan. This plan just executes (or formally defers) the specific verification that prompt-37.6.1 skipped.

**Output format**: Lead with verdict (ship as-is / ship with fix / send back), then list specific issues by severity. Skip praise. Cite specific line numbers when flagging factual errors.

**Known landmines to check against** (from SOVEREIGN_AI_HANDOFF.md "Claude review workflow" section):
- Tag-push gate must be verified with `git ls-remote --tags origin | findstr prompt-38.6` — closing step 11 includes this. Verify it's not skipped.
- Rule 19 evidence requirement — every step requires literal output pasted into CHANGELOG. Verify the plan enforces this, especially for Step 3-DEFERRED and Step 4-DEFERRED (deferral documentation is also evidence).
- No `global_rules.md` citations (file is unreachable, can't be verified).
- No re-guessing of disproved hypotheses — this plan builds on prompt-37.6.1's deferral contract, doesn't re-litigate the original Gates 5/6 reasoning.
- Drift check (Gate 1) distinguishes code files (must be empty) from docs files (allowed).
