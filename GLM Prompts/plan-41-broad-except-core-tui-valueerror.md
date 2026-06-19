# Plan 41: Broad-except audit, part 1 (core/) — TUI ValueError handling + structured exception patterns

> **Executor instructions**: This plan addresses the broad-except pattern in `core/` files. Per session 2 handoff: ~53 broad-except sites across core/ files (orchestrator, approval_gate, task_state_machine, memory_router, worker_base). Many silently swallow exceptions with `except Exception: pass` — violating handoff Rule 17 ("No broad `except Exception: pass` without inline comment + WARNING trace event").
>
> **Two scopes bundled**:
> 1. **TUI `/adapter` ValueError handling** (Plan 39/40 referenced this as deferred to Plan 41) — when user runs `/adapter openai` without `OPENAI_API_KEY` set, the TUI currently crashes with traceback. Fix: catch ValueError in TUI's `_on_adapter_selected` and display user-friendly message.
> 2. **Core/ broad-except audit** — replace `except Exception: pass` patterns with either (a) specific exception types, (b) inline comment + WARNING trace event per Rule 17, or (c) re-raise if the exception shouldn't be swallowed.
>
> **Critical**: This is a refactoring plan, not a feature plan. Do NOT change behavior — only change how exceptions are handled. If a broad-except is genuinely swallowing an exception that should propagate, that's a behavior change requiring GLM/user approval.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-40..HEAD -- core/ cli/tui.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `core/`, `cli/tui.py`: expected empty. For handoff/CHANGELOG: allowed per known-landmine procedure.

## Status

- **Priority**: P1 (systemic code quality issue + TUI UX bug)
- **Effort**: M (5 core files to audit + 1 TUI fix)
- **Risk**: MEDIUM (exception handling changes can subtly alter behavior — must verify no test regressions)
- **Depends on**: prompt-40 (commit `076a81e`, tag `prompt-40`)
- **Planned at**: master HEAD post-prompt-40, 2026-06-19
- **In scope**:
  - Production: `core/orchestrator.py` (19 except blocks, 5 with pass)
  - Production: `core/approval_gate.py` (23 except blocks, 13 with pass)
  - Production: `core/task_state_machine.py` (11 except blocks, 7 with pass)
  - Production: `core/memory_router.py` (9 except blocks, 4 with pass)
  - Production: `core/worker_base.py` (1 except block, 0 with pass — minimal)
  - Production: `cli/tui.py` (TUI `/adapter` ValueError handling — add try/except around `create_adapter` call)
  - Docs: `SOVEREIGN_AI_HANDOFF.md` (update "What's broken" to remove F7 if fully fixed, update Rule 17 compliance status, add landmine for Devin chat report test counts)
  - Changelog: `CHANGELOG.md` (per-step literal evidence)
- **Out of scope**: broad-except audit for system/ (Plan 42), skills/ (Plan 43), web/ (separate plan), adapters/ (separate plan), gateways/ (separate plan), ruff/mypy triage, trajectory_exporter redesign, marine stack

## Why this matters

Two reasons this plan exists now:

1. **TUI `/adapter` ValueError handling is a deferred bug from Plan 39/40.** When user runs `/adapter openai` without `OPENAI_API_KEY` set, `cli/adapter_factory.py:create_adapter()` raises `ValueError("OPENAI_API_KEY environment variable not set")`. The TUI's `_on_adapter_selected` doesn't catch this — the TUI crashes with traceback. Plan 39 added a comment in `adapter_factory.py` documenting this gap and deferring the fix to Plan 41. This plan executes that fix.

2. **Broad-except pattern in core/ violates Rule 17.** Handoff Rule 17: "No broad `except Exception: pass` without inline comment + WARNING trace event." Verified counts in core/:
   - `orchestrator.py`: 19 except blocks, 5 with `pass`
   - `approval_gate.py`: 23 except blocks, 13 with `pass`
   - `task_state_machine.py`: 11 except blocks, 7 with `pass`
   - `memory_router.py`: 9 except blocks, 4 with `pass`
   - `worker_base.py`: 1 except block, 0 with `pass`
   - **Total: 63 except blocks, 29 with `pass`** — many silently swallow exceptions

The `except Exception: pass` pattern is recurring mistake #4 ("Broad `except Exception: pass` hiding real failures"). When an exception is silently swallowed, bugs hide. The fix is either:
- (a) **Specific exception types** — catch only what you expect (e.g., `except (ConnectionError, TimeoutError):` instead of `except Exception:`)
- (b) **Inline comment + WARNING trace event** — if you genuinely must catch all exceptions (e.g., in a cleanup path where you don't want to mask the original error), document why and emit a WARNING trace
- (c) **Re-raise** — if the exception shouldn't be swallowed at all, remove the try/except

**Bonus**: This plan also codifies the new landmine about Devin chat report test counts being unreliable (recurring pattern from prompt-39 and prompt-40).

**Expected outcome**: 0 broad-except violations of Rule 17 in core/ (all 29 `pass` patterns addressed). TUI `/adapter` command handles missing API keys gracefully. Test suite stays at ~1124 passed, 0 failed, 0 warnings (no behavior changes).

## What's broken

### A. TUI `/adapter` ValueError not handled (deferred from Plan 39)

**File**: `cli/tui.py` — `_on_adapter_selected` method (line 491)

Current code:
```python
def _on_adapter_selected(self, adapter_name: str) -> None:
    """Handle adapter selection from modal."""
    # Create new worker with REAL memory_router (not None)
    self.worker = create_worker(adapter_name, "llama3", memory_router=self.memory_router)
    # ...
```

`create_worker` calls `create_adapter`, which raises `ValueError` if API key env var not set. The TUI doesn't catch this — crashes with traceback.

**Fix**: Wrap the `create_worker` call in try/except ValueError, display user-friendly message via `self.output.update_content(...)`.

### B. Core/ broad-except violations (Rule 17)

Verified by grepping each core file for `except Exception` patterns. Examples:

**orchestrator.py line 320-321**:
```python
except Exception:
    pass
```
Silently swallows whatever exception occurred. No comment, no trace event.

**approval_gate.py line 360-361**:
```python
except Exception:
    pass
```
Same pattern. 13 occurrences in this file alone.

**task_state_machine.py line 90-91**:
```python
except Exception:
    pass
```
7 occurrences in this file.

Each `except Exception: pass` needs to be classified:
- **Cleanup path** (e.g., in a finally block where you don't want to mask the original error) → add inline comment + WARNING trace event per Rule 17
- **Expected exception** (e.g., network timeout) → replace with specific exception type
- **Shouldn't be caught** → remove the try/except, let it propagate

## What to change

### Step 1 — Fix TUI `/adapter` ValueError handling

**File**: `cli/tui.py` — `_on_adapter_selected` method (line 491)

**Current**:
```python
def _on_adapter_selected(self, adapter_name: str) -> None:
    """Handle adapter selection from modal."""
    self.worker = create_worker(adapter_name, "llama3", memory_router=self.memory_router)
    self.orchestrator.register_worker("ollama_worker", self.worker)
    asyncio.create_task(self.process_command(f"/adapter {adapter_name}"))
```

**Fixed**:
```python
def _on_adapter_selected(self, adapter_name: str) -> None:
    """Handle adapter selection from modal."""
    try:
        self.worker = create_worker(adapter_name, "llama3", memory_router=self.memory_router)
        self.orchestrator.register_worker("ollama_worker", self.worker)
        asyncio.create_task(self.process_command(f"/adapter {adapter_name}"))
    except ValueError as e:
        # User-friendly error message for missing API key or unknown adapter
        # (create_adapter raises ValueError if env var not set — see cli/adapter_factory.py)
        error_msg = str(e)
        # Add helpful URL for API key errors
        if "API_KEY" in error_msg or "_TOKEN" in error_msg:
            env_var = error_msg.split("environment variable")[0].strip()
            urls = {
                "OPENAI_API_KEY": "https://platform.openai.com/api-keys",
                "COHERE_API_KEY": "https://dashboard.cohere.com/api-keys",
                "GROQ_API_KEY": "https://console.groq.com/keys",
                "ANTHROPIC_API_KEY": "https://console.anthropic.com/settings/keys",
                "MISTRAL_API_KEY": "https://console.mistral.ai/api-keys",
                "TOGETHER_API_KEY": "https://api.together.xyz/settings/api-keys",
                "DEEPSEEK_API_KEY": "https://platform.deepseek.com/api_keys",
                "HUGGINGFACE_API_KEY": "https://huggingface.co/settings/tokens",
                "HF_TOKEN": "https://huggingface.co/settings/tokens",
            }
            url = urls.get(env_var, "")
            url_hint = f"\n\nGet a key at: {url}" if url else ""
            self.output.update_content(
                f"[red]✗ Cannot switch to {adapter_name}: {error_msg}{url_hint}[/red]"
            )
        else:
            self.output.update_content(
                f"[red]✗ Cannot switch to {adapter_name}: {error_msg}[/red]"
            )
```

**Before applying the fix**, verify the correct TUI method by running:
```powershell
Select-String -Path cli\tui.py -Pattern "self\.output"
```
Confirm that `self.output` exists and has an `update_content` method. If the attribute name is different (e.g., `self.output_panel`) or the method is different (e.g., `write()` or `append()`), adapt the fix to use the correct call. **If this verification is skipped and the method name is wrong, the except block will itself raise `AttributeError`, crashing the TUI — arguably worse than the original `ValueError` crash.**

**Verify**: Step 1 is verified at Gate 2 (which uses `Select-String` to confirm `except ValueError` and `platform.openai.com/api-keys` are present in `cli/tui.py`). Proceed to Step 2 once the fix is applied. No separate `python -c` invocation needed — Gate 2's grep-based check is strictly more reliable than a source-text inspection via `inspect.getsource`.

### Step 2 — Audit `core/orchestrator.py` broad-except patterns

**File**: `core/orchestrator.py` (19 except blocks, 5 with `pass`)

For each `except Exception: pass` pattern, classify and fix:

**Procedure**:
1. Read each `except Exception: pass` block in context (the surrounding 10 lines)
2. Classify each:
   - **Cleanup path** (in finally, or after primary operation completed) → add inline comment + WARNING trace event
   - **Expected exception** (network, parse, etc.) → replace with specific exception type
   - **Shouldn't be caught** → remove try/except, let it propagate (FLAG THIS — may be behavior change)
3. For each fix, paste the before/after diff to CHANGELOG as evidence

**Example fix for cleanup path** (orchestrator.py line 320-321):
```python
# Before:
except Exception:
    pass

# After (cleanup path — emit trace event per Rule 17):
except Exception as e:
    # Cleanup path — don't mask the original error, but log for debugging
    # Per Rule 17: broad except requires inline comment + WARNING trace
    await self._emitter.emit(TraceEvent(
        event_type=TraceEventType.OPERATION_ERROR,
        component=TraceComponent.ORCHESTRATOR,
        level=TraceLevel.WARNING,
        message=f"Cleanup failed: {type(e).__name__}: {e}",
        data={"exception_type": type(e).__name__, "exception_message": str(e)},
        duration_ms=0,
    ))
```

**Example fix for expected exception**:
```python
# Before:
except Exception:
    pass

# After (specific exception type):
except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
    # Network timeout — retry or report
    await self._emitter.emit(TraceEvent(...))
```

**Example fix for shouldn't-be-caught** (FLAG for GLM review):
```python
# Before:
except Exception:
    pass

# After (remove try/except entirely — let exception propagate):
# (removed try/except block)
```

**If removing a try/except would change behavior**: STOP. Document the specific case in CHANGELOG. Do NOT remove without GLM/user approval. Apply the cleanup-path fix (with WARNING trace) instead and note "behavior-preserving — should be reviewed for whether exception should propagate."

**Verify** (paste literal output):
```powershell
# Count remaining broad-except + pass patterns
Select-String -Path core\orchestrator.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0 (all 5 pass patterns addressed)

# Run orchestrator tests
python -m pytest tests/test_orchestrator.py -v --tb=short
# All tests still pass
```

### Step 3 — Audit `core/approval_gate.py` broad-except patterns

**File**: `core/approval_gate.py` (23 except blocks, 13 with `pass`)

Same procedure as Step 2. This file has the most `pass` patterns (13) — the highest concentration in core/.

**Verify** (paste literal output):
```powershell
Select-String -Path core\approval_gate.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_approval_gate.py -v --tb=short
# All tests still pass
```

### Step 4 — Audit `core/task_state_machine.py` broad-except patterns

**File**: `core/task_state_machine.py` (11 except blocks, 7 with `pass`)

Same procedure.

**Verify** (paste literal output):
```powershell
Select-String -Path core\task_state_machine.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_task_state_machine.py -v --tb=short
# All tests still pass
```

### Step 5 — Audit `core/memory_router.py` broad-except patterns

**File**: `core/memory_router.py` (9 except blocks, 4 with `pass`)

Same procedure.

**Verify** (paste literal output):
```powershell
Select-String -Path core\memory_router.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" } | Measure-Object -Line
# Should be 0

python -m pytest tests/test_memory_router.py -v --tb=short
# All tests still pass
```

### Step 6 — Audit `core/worker_base.py` broad-except patterns

**File**: `core/worker_base.py` (1 except block, 0 with `pass`)

Minimal — only 1 except block, no `pass` patterns. Quick verification that the existing except block is appropriate (has inline comment or specific exception type).

**Verify** (paste literal output):
```powershell
Select-String -Path core\worker_base.py -Pattern "except Exception" -Context 0,1
# Should show the 1 except block with appropriate handling (not bare pass)
```

### Step 7 — Add new landmine to handoff: Devin chat report test counts unreliable

**File**: `SOVEREIGN_AI_HANDOFF.md` — "Known landmines" section

Add:
```
- **Devin chat report test counts unreliable** (prompt-39, prompt-40 had this):
  Devin's chat summary of test counts (e.g., "1118 passed") has been 6 tests
  lower than the handoff's actual measurement (e.g., "1124 passed") for two
  consecutive prompts. The handoff is the authoritative source — always verify
  test counts from the handoff, not from Devin's chat report. Pattern may be
  due to Devin counting --ignore'd tests differently or running a subset.
  When in doubt, run `python -m pytest tests/ -q --tb=no --ignore=tests/test_llama_cpp_adapter.py`
  directly to get the authoritative count.
```

### Step 8 — Update handoff

**File**: `SOVEREIGN_AI_HANDOFF.md`

1. Update "Last updated" to reference prompt-41.
2. Update "What's broken" section — remove or update any items fixed by this plan (TUI `/adapter` ValueError).
3. Update Rule 17 compliance status in "Architecture rules" section — note that core/ is now compliant (29 `pass` patterns addressed).
4. Update "Test environment prerequisites" if any changes.
5. Update TUI slash commands documentation:
   > **TUI slash commands** — `/adapter` now handles missing API keys gracefully (displays user-friendly message with URL instead of crashing). Supports 10 adapters.
6. Update "Next 5 prompts" to reflect Plan 42 (broad-except audit system/) as next in queue.

### Step 9 — Update CHANGELOG with literal evidence

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 evidence: TUI ValueError handling verification output
- Step 2 evidence: orchestrator.py before/after diff for each of 5 `pass` patterns + test results
- Step 3 evidence: approval_gate.py before/after diff for each of 13 `pass` patterns + test results
- Step 4 evidence: task_state_machine.py before/after diff for each of 7 `pass` patterns + test results
- Step 5 evidence: memory_router.py before/after diff for each of 4 `pass` patterns + test results
- Step 6 evidence: worker_base.py verification output
- Final test counts: ~1124 passed, ~61 skipped, 0 failed, 0 warnings (unchanged — no behavior changes)

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-40..HEAD -- core/ cli/tui.py
```

**Expected**: empty output.

### Gate 2 — TUI ValueError handling exists

```powershell
Select-String -Path cli\tui.py -Pattern "except ValueError"
Select-String -Path cli\tui.py -Pattern "platform.openai.com/api-keys"
```

**Expected**: at least 1 match each.

### Gate 3 — Zero `except Exception: pass` in core/

```powershell
# Count remaining broad-except + pass patterns across all core files
Get-ChildItem -Path core\ -Filter "*.py" | ForEach-Object {
    $matches = Select-String -Path $_.FullName -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" }
    if ($matches.Count -gt 0) {
        Write-Host "$($_.Name): $($matches.Count) violations"
    }
}
```

**Expected**: no output (zero violations across all core files).

**Scope note**: This grep catches bare `except Exception: pass` patterns (and the `as e` variant when `pass` is the only line in the block). It does NOT catch `except Exception as e:` blocks that swallow via logging-only (e.g., `except Exception as e: logger.debug(e)` without re-raising). Those swallowing patterns are addressed in the Step 2-6 procedures (Devin reads each except block in context and classifies it) but are not verified by this gate. They will be caught in the ruff triage (Plan 46). A clean Gate 3 confirms bare-pass patterns are eliminated — it does NOT confirm all swallowing patterns are addressed.

### Gate 4 — All core tests still pass

```powershell
python -m pytest tests/test_orchestrator.py tests/test_approval_gate.py tests/test_task_state_machine.py tests/test_memory_router.py tests/test_worker_base.py -v --tb=short
```

**Expected**: all tests pass (no behavior changes from exception handling refactoring).

### Gate 5 — Full test suite unchanged

```powershell
python -m pytest tests/ -q --tb=short --ignore=tests/test_llama_cpp_adapter.py
```

**Expected**:
- Passed: ~1124 (unchanged from prompt-40)
- Skipped: ~61 (unchanged)
- Failed: 0
- Warnings: 0

**Acceptable ranges**:
- Passed: {1122, 1123, 1124, 1125, 1126} — small variations OK if test count methodology shifts
- Skipped: {60, 61, 62}
- Failed: {0}
- Warnings: {0}

### Gate 6 — Handoff updated

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Devin chat report test counts unreliable"
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "handles missing API keys gracefully"
```

**Expected**: at least 1 match each.

### Gate 7 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-41
```

**Expected**: 1 match. **Do not skip this step.**

## STOP conditions

- **If removing a try/except would change behavior**: STOP. Document the specific case. Apply behavior-preserving fix (cleanup path with WARNING trace) instead. Note "should be reviewed for whether exception should propagate" in CHANGELOG.
- **If any core test fails after broad-except refactoring**: STOP. The refactoring introduced a behavior change. Investigate root cause — may need to keep the broad-except with WARNING trace instead of removing.
- **If Gate 5 shows test count change**: STOP. Investigate whether the refactoring caused test failures or new skips.
- **If Gate 7 shows no match**: push the tag, re-verify.
- **If you find yourself about to defer any step citing "per memory" or "Mistake Pattern N"**: STOP. Per landmine, Devin memories are not authoritative.

## Out of scope

- Broad-except audit for system/ (Plan 42)
- Broad-except audit for skills/ (Plan 43)
- Broad-except audit for web/, adapters/, gateways/ (separate plans)
- ruff/mypy triage
- trajectory_exporter redesign
- marine stack
- Re-verification of blocked adapters from prompt-39/40 (external issues)
- Production adapter code changes (if tests reveal deprecated models — per scope-creep landmine, STOP and report)

## Closing steps

1. `git add cli/tui.py core/orchestrator.py core/approval_gate.py core/task_state_machine.py core/memory_router.py core/worker_base.py SOVEREIGN_AI_HANDOFF.md CHANGELOG.md`
2. `git commit -m "fix: prompt-41 — broad-except audit (core/) + TUI /adapter ValueError handling + Devin chat count landmine"`
3. `git tag prompt-41`
4. `git show prompt-41 --stat` — verify file list
5. `git rev-parse prompt-41` — confirm hash
6. Update `CHANGELOG.md` (append-only) with all step evidence per Rule 19
7. Update `SOVEREIGN_AI_HANDOFF.md` per Step 8
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-41 changelog and handoff update"`
10. `git push origin master && git push origin prompt-41`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-41` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 41 lands

**Core/ is Rule 17 compliant** — zero `except Exception: pass` patterns without inline comment + WARNING trace.

**TUI `/adapter` command handles missing API keys gracefully** — displays user-friendly message with URL instead of crashing with traceback.

**New landmine codified**: Devin chat report test counts unreliable — handoff is authoritative source.

**Test suite unchanged**: ~1124 passed, ~61 skipped, 0 failed, 0 warnings. Exception handling refactoring preserved all behavior.

**Remaining broad-except audit work**:
- Plan 42: system/ (~132 sites)
- Plan 43: skills/ (~183 sites)
- Separate plans: web/, adapters/, gateways/

**Then horizontal cleanup queue**:
- Plan 44: InputSanitiser wiring
- Plan 45: InputSanitiser redesign
- Plan 46: ruff triage
- Plan 47: mypy triage
- Plan 48+: trajectory_exporter redesign, graphify integration, marine stack

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This plan audits broad-except patterns in core/ + fixes TUI ValueError handling. Check that:

1. **Is the TUI ValueError fix correct?** The fix wraps `create_worker` in try/except ValueError, displays user-friendly message with URL hint. Is the URL hint lookup (hardcoded dict) appropriate, or should it be in adapter_factory.py for consistency?

2. **Is the broad-except classification approach sound?** Three options: (a) cleanup path with WARNING trace, (b) specific exception type, (c) remove try/except. The plan says "if removing would change behavior, STOP" — is this the right safeguard?

3. **Is the verification approach correct?** Gate 3 counts `except Exception` patterns followed by `pass` — should be 0 after refactoring. But what about `except Exception as e:` patterns that also swallow? Should the grep be broader?

4. **Is the scope appropriate?** 5 core files, 29 `pass` patterns to address. Is this manageable in one plan, or should it be split (e.g., one plan per file)?

5. **Is the new landmine (Devin chat report test counts unreliable) clearly framed?** Does it need examples of the discrepancy (prompt-39: 1098 chat vs 1104 handoff; prompt-40: 1118 chat vs 1124 handoff)?

6. **No known landmines violated**:
   - Tag-push gate (closing step 11) ✅
   - Rule 19 evidence requirement ✅
   - No `global_rules.md` citations ✅
   - No "per memory" citations ✅
   - No re-guessing disproved hypotheses ✅
   - Drift check distinguishes code vs docs ✅
   - Test-count methodology documented ✅
   - "No interactive shell" landmine — N/A (no verification work in this plan) ✅
   - Scope creep landmine — N/A (no production adapter changes) ✅
   - **NEW: Devin chat report test counts unreliable** — this plan ADDS the landmine ✅
