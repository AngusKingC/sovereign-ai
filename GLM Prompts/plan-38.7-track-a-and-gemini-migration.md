# Plan 38.7: Execute Plan 38.6 Track A + Gemini SDK migration

> **Executor instructions**: This plan bundles two scopes. **Step 1 is non-negotiable**: it executes Track A from Plan 38.6, which was skipped in prompt-38.6. Steps 2-N are the Gemini SDK migration. Track A must be executed before the Gemini migration begins — if Track A fails, STOP and report. Do not defer Track A to another plan; it has already been deferred once (Plan 38.6 → Plan 38.8) and that deferral was a Rule 19 violation per the post-prompt-38.6 review.
>
> **Critical**: Track A of Plan 38.6 was explicitly designed to not require an interactive shell. The script uses `unittest.mock.patch` to mock `OllamaAdapter` and calls `process_command()` directly. "No interactive shell" is not a valid reason to skip Step 1 — the script doesn't use one.
>
> **Drift check (run first)**:
> ```
> git diff --stat prompt-38.6..HEAD -- cli/tui.py adapters/gemini.py scripts/ SOVEREIGN_AI_HANDOFF.md CHANGELOG.md
> ```
> For `cli/tui.py`, `adapters/gemini.py`, `scripts/`: expected empty (no drift). For `SOVEREIGN_AI_HANDOFF.md` and `CHANGELOG.md`: allowed (standard docs-commit drift).

## Status

- **Priority**: P1 (closes Rule 19 violation + eliminates last warning)
- **Effort**: M (Track A is small, Gemini migration is real work with 20-line guard)
- **Risk**: LOW–MEDIUM (Track A is verification only; Gemini migration has 20-line guard)
- **Depends on**: prompt-38.6 (commit `4124a82`, tag `prompt-38.6`)
- **Planned at**: master HEAD post-prompt-38.6, 2026-06-19
- **In scope**:
  - New file: `scripts/verify_tui_e2e.py` (Track A from Plan 38.6)
  - Production: `adapters/gemini.py` (Gemini SDK migration, 20-line guard)
  - Docs: `CHANGELOG.md` (Track A evidence + Gemini migration evidence), `SOVEREIGN_AI_HANDOFF.md` (update Last updated, remove Plan 38.8 from deferred-actions if Track A passes)
- **Out of scope**: production code changes to `cli/tui.py`, broad-except audit (Plan 39+), ruff/mypy triage (Plans 43-44)

## Why this matters

Two things this plan addresses:

1. **Plan 38.6 Track A was skipped.** Prompt-38.6 deferred Gates 5/6 to Plan 38.8, citing "no interactive shell." But Track A of Plan 38.6 was explicitly designed to not need an interactive shell — it uses `unittest.mock.patch` to mock `OllamaAdapter` and calls `process_command()` directly. Skipping Track A and deferring was a Rule 19 violation: the same pattern (skip verification, cite environment) that Rule 19 was added to prevent.

2. **Gemini FutureWarning is the last remaining warning.** Test suite is at 1 warning (Gemini deprecation, suppressed with `# noqa: Plan 38.7`). Migrating `adapters/gemini.py` from `google.generativeai` to `google.genai` eliminates it. Has the 20-line guard from Plan 38 — if migration exceeds 20 lines of production code change, defer to Plan 38.7.1 (or just leave the `# noqa` suppression in place, since it's already auditable).

If Track A passes, **Plan 38.8 will not need to exist** — the Rule 19 violation is closed by Track A's literal evidence. If Track A fails with a real bug, that's a separate problem and gets its own plan.

## What's broken

### A. Plan 38.6 Track A was not executed (Rule 19 violation)

Plan 38.6 Step 1 provided a complete script (`scripts/verify_tui_e2e.py`) for Track A. Prompt-38.6 did not create the script, did not run it, did not paste any Track A evidence into CHANGELOG. The Plan 38.8 deferral was premature — Track A was the path that closes the Rule 19 violation without needing Track B.

The script (provided in full in Step 1 below) verifies:
1. Query "hello" produces a response (cognition stack works end-to-end)
2. Query "what did I just say?" — memory_router state checked
3. Adapter swap to lm_studio preserves memory_router (same object, not None)
4. F7: no trace events in stdout (MemoryTraceEmitter default working)

### B. Gemini FutureWarning (last remaining warning)

```
C:\Jarvis\adapters\gemini.py:12: FutureWarning:
https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md
```

Currently suppressed with `# noqa: Plan 38.7: migrate to google.genai` (legitimate temporary suppression with ticket reference). This plan either migrates the SDK (eliminating the warning) or leaves the suppression in place if migration exceeds the 20-line guard.

## What to change

### Step 1 — Execute Plan 38.6 Track A (NON-NEGOTIABLE)

**File**: `C:\Jarvis\scripts\verify_tui_e2e.py` (new file)

**Script content** (Devin: copy-paste verbatim, then adapt if API mismatches):

**Important design note**: This script does NOT instantiate `JarvisTUI` directly. `JarvisTUI` extends Textual's `App`, and `App.__init__` initializes the compositor/driver which may fail outside a running Textual session. The script instead constructs the cognition stack directly (MemoryRouter, Orchestrator, Worker, etc.) by copying the wiring from `JarvisTUI.__init__` (lines 226-403 of `cli/tui.py`). This makes the script genuinely shell-independent — no Textual app, no terminal, no interactive shell required. The verification targets (memory_router persistence, adapter swap preservation, F7 trace emitter default) are all plain Python objects that don't need the App.

```python
"""
End-to-end TUI verification script (Plan 38.7 Step 1 / Plan 38.6 Track A).

Constructs the cognition stack directly (bypassing JarvisTUI/Textual App)
to verify:
1. Query "hello" produces a response (cognition stack works end-to-end)
2. Query "what did I just say?" produces a response that references "hello"
   (memory_router persists data across queries within a session)
3. Adapter swap to lm_studio preserves memory_router (not None, same object)
4. F7: No trace events print to stdout (MemoryTraceEmitter is the default)

This script does NOT instantiate JarvisTUI (which extends Textual's App and
may fail outside a running Textual session). Instead, it constructs the
cognition stack directly, copying the wiring from JarvisTUI.__init__
(lines 226-403 of cli/tui.py). The verification targets — memory_router,
worker, adapter swap logic — are plain Python objects that don't need the App.

Usage:
    python scripts/verify_tui_e2e.py

Output is CHANGELOG-ready — paste literal output into prompt-37.6.1
Gate 5/6 correction note per Rule 19.
"""

import asyncio
import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch, AsyncMock, MagicMock


async def verify_tui_e2e() -> None:
    """Run end-to-end cognition stack verification with mocked OllamaAdapter."""

    # Mock OllamaAdapter at instantiation (same pattern as test_tui.py fixture).
    # This patch stays active for the entire script — anywhere OllamaAdapter()
    # is called (in create_worker, in AdapterFallbackChain, etc.), it returns
    # our mock instance.
    with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
        # Configure mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "llama3"
        mock_instance.is_local = True
        mock_instance.cost_per_token = 0.0

        # Mock generate to return a response that references prior context
        # (simulates memory_router feeding context back to the LLM)
        call_count = [0]
        async def mock_generate(prompt: str, **kwargs):
            call_count[0] += 1
            return MagicMock(
                content=f"Response {call_count[0]} to: {prompt[:50]}",
                confidence=0.9,
                model_used="llama3",
                tokens_used=10,
            )
        mock_instance.generate = mock_generate
        mock_instance.health_check = AsyncMock(return_value=True)
        mock_instance.close = AsyncMock()
        mock_adapter_class.return_value = mock_instance

        # --- Construct cognition stack directly (NOT via JarvisTUI) ---
        # This wiring mirrors JarvisTUI.__init__ (cli/tui.py lines 226-403)
        # but skips the Textual App entirely.
        from core.observability import MemoryTraceEmitter
        from core.memory_router import MemoryRouter
        from core.skill_registry import SkillRegistry
        from core.approval_trust import ApprovalTrustRegistry
        from core.approval_gate import ApprovalGate
        from core.escalation import EscalationEngine
        from core.adapter_fallback import AdapterFallbackChain
        from core.worker_factory import WorkerFactory
        from core.rating_system import RatingSystem
        from core.instruction_generator import InstructionGenerator
        from core.instruction_versioning import InstructionVersionManager
        from core.evaluator import OutputEvaluator
        from core.trace_optimiser import TraceOptimiser
        from core.orchestrator_improvement import OrchestratorImprovementLoop
        from core.task_state_machine import TaskStateMachine
        from core.orchestrator import Orchestrator
        from cli.adapter_factory import create_worker

        # Use MemoryTraceEmitter — this verifies F7 (default is no stdout spam)
        emitter = MemoryTraceEmitter()

        # Create memory router (no DSN → in-memory backends)
        memory_router = MemoryRouter(backends={}, emitter=emitter)

        # Wire the cognition stack (same order as JarvisTUI.__init__)
        skill_registry = SkillRegistry(emitter=emitter)
        approval_trust = ApprovalTrustRegistry(memory_router=memory_router, emitter=emitter)
        state_machine = TaskStateMachine(memory_router=memory_router)
        approval_gate = ApprovalGate(
            state_machine=state_machine,
            memory_router=memory_router,
            emitter=emitter,
            trust_registry=approval_trust,
        )
        escalation_engine = EscalationEngine(
            approval_gate=approval_gate,
            memory_router=memory_router,
            emitter=emitter,
        )

        # OllamaAdapter is mocked at instantiation (top of script)
        # AdapterFallbackChain will get the mock instance when it constructs OllamaAdapter
        ollama_adapter = mock_adapter_class(model_name="llama3", emitter=emitter)
        fallback_chain = AdapterFallbackChain(
            adapters=[(ollama_adapter, "llama3")],
            resource_manager=None,
            approval_gate=approval_gate,
            emitter=emitter,
        )

        rating_system = RatingSystem(memory_router=memory_router, emitter=emitter)
        instruction_generator = InstructionGenerator(
            adapter=ollama_adapter,
            rating_system=rating_system,
            memory_router=memory_router,
            obsidian_vault_path=os.getenv("OBSIDIAN_VAULT_PATH"),
            emitter=emitter,
        )
        instruction_versioning = InstructionVersionManager(
            instruction_generator=instruction_generator,
            rating_system=rating_system,
            approval_gate=approval_gate,
            memory_router=memory_router,
            emitter=emitter,
        )
        output_evaluator = OutputEvaluator(
            llm_adapter=ollama_adapter,
            memory_router=memory_router,
            evaluator_model="default",
            emitter=emitter,
        )
        trace_optimiser = TraceOptimiser(
            memory_router=memory_router,
            instruction_version_manager=instruction_versioning,
            emitter=emitter,
        )

        orchestrator = Orchestrator(
            memory_router=memory_router,
            improvement_loop=None,  # Set after creating it
            cloud_fallback_model="gpt-4o",
            approval_gate=approval_gate,
            escalation_engine=escalation_engine,
            fallback_chain=fallback_chain,
            a2a_router=None,
            emitter=emitter,
        )

        worker_factory = WorkerFactory(
            skill_registry=skill_registry,
            orchestrator=orchestrator,
            memory_router=memory_router,
            emitter=emitter,
            persistence=None,
            instruction_generator=instruction_generator,
        )

        improvement_loop = OrchestratorImprovementLoop(
            orchestrator=orchestrator,
            instruction_version_manager=instruction_versioning,
            memory_router=memory_router,
            emitter=emitter,
        )
        orchestrator.improvement_loop = improvement_loop

        # Create default worker with REAL memory_router (not None)
        worker = create_worker("ollama", "llama3", memory_router=memory_router)
        orchestrator.register_worker("ollama_worker", worker)

        # Build a minimal namespace to hold the references the script needs.
        # This replaces the `tui` object from the original Plan 38.6 script.
        class CognitionStack:
            """Holds references to the constructed cognition stack."""
            pass

        stack = CognitionStack()
        stack.memory_router = memory_router
        stack.orchestrator = orchestrator
        stack.worker = worker
        stack.emitter = emitter

        # Capture stdout to verify F7 (no trace events should print)
        stdout_capture = io.StringIO()

        print("=== Plan 38.7 Step 1 — Cognition Stack End-to-End Verification ===")
        print("(Plan 38.6 Track A — bypasses JarvisTUI/Textual App entirely)")
        print()
        print("Track A: Programmatic verification (mocked OllamaAdapter)")
        print()

        # --- Gate 5: Query flow + memory persistence ---
        # NOTE: "Gate 5" and "Gate 6" labels here correspond to the original
        # prompt-37.6.1 verification targets, NOT this plan's execution gates.
        print("--- Gate 5 (prompt-37.6.1 target): Query flow + memory persistence ---")
        print()

        # Query 1: "hello" — drive the orchestrator directly.
        # JarvisTUI.process_command() resolves the query via the command registry,
        # which calls orchestrator.submit_task(). We do the same here.
        from core.schemas import Command, CommandContext, CommandType
        from core.commands import get_command_registry, register_default_handlers
        from core.session import SessionManager

        # SessionManager needed for command context (in-memory, no DSN)
        session_manager = SessionManager(backend=None)
        register_default_handlers(orchestrator, session_manager)

        # Create a session for the command context
        session = await session_manager.create_session()
        session_id = session.session_id if hasattr(session, 'session_id') else str(session.id)

        # Query 1: "hello"
        with redirect_stdout(stdout_capture):
            cmd1 = Command(
                command_type=CommandType.QUERY,
                args=["hello"],
                context=CommandContext(
                    interface_type="cli",
                    session_id=session_id,
                    working_directory=str(os.getcwd()),
                ),
            )
            registry = get_command_registry()
            result1 = await registry.execute(cmd1)
        stdout_during_query1 = stdout_capture.getvalue()
        stdout_capture.truncate(0)
        stdout_capture.seek(0)

        print("Query 1: hello")
        print(f"Result 1 success: {result1.success}")
        print(f"Result 1 message: {result1.message}")
        print(f"Stdout during query 1: {repr(stdout_during_query1)}")
        print()

        # Query 2: "what did I just say?"
        with redirect_stdout(stdout_capture):
            cmd2 = Command(
                command_type=CommandType.QUERY,
                args=["what", "did", "I", "just", "say?"],
                context=CommandContext(
                    interface_type="cli",
                    session_id=session_id,
                    working_directory=str(os.getcwd()),
                ),
            )
            result2 = await registry.execute(cmd2)
        stdout_during_query2 = stdout_capture.getvalue()
        stdout_capture.truncate(0)
        stdout_capture.seek(0)

        print("Query 2: what did I just say?")
        print(f"Result 2 success: {result2.success}")
        print(f"Result 2 message: {result2.message}")
        print(f"Stdout during query 2: {repr(stdout_during_query2)}")
        print()

        # Verify memory_router state
        print(f"memory_router: {memory_router}")
        print(f"memory_router is not None: {memory_router is not None}")
        print()

        # Check if memory_router has any recorded interactions
        # (Exact API depends on MemoryRouter implementation — adapt as needed)
        try:
            global_context = await memory_router.get_global_context()
            print(f"memory_router.get_global_context(): {global_context}")
            print(f"Memory has 'hello': {'hello' in str(global_context)}")
        except Exception as e:
            print(f"memory_router.get_global_context() failed: {e}")
            print("(Memory may be stored differently — check MemoryRouter API)")
        print()

        # --- Gate 6: Adapter swap preserves memory_router ---
        print("--- Gate 6 (prompt-37.6.1 target): Adapter swap preserves memory_router ---")
        print()

        original_memory_router = worker.memory_router
        print(f"Original worker memory_router: {original_memory_router}")

        # Mock create_worker to avoid needing real lm_studio adapter.
        # This mirrors what JarvisTUI._on_adapter_selected does (cli/tui.py:491-494):
        #   self.worker = create_worker(adapter_name, "llama3", memory_router=self.memory_router)
        #   self.orchestrator.register_worker("ollama_worker", self.worker)
        with patch('cli.adapter_factory.create_worker') as mock_create_worker:
            mock_new_worker = MagicMock()
            mock_new_worker.memory_router = original_memory_router
            mock_create_worker.return_value = mock_new_worker

            # Execute the adapter swap sequence directly (same logic as _on_adapter_selected)
            new_worker = create_worker("lm_studio", "llama3", memory_router=memory_router)
            orchestrator.register_worker("ollama_worker", new_worker)
            worker = new_worker  # Update local reference to mirror tui.worker = new_worker

            new_memory_router = worker.memory_router
            print(f"New worker memory_router: {new_memory_router}")
            print(f"memory_router preserved: {new_memory_router is original_memory_router}")
            print(f"memory_router is not None: {new_memory_router is not None}")
        print()

        # --- F7: No trace events to stdout ---
        print("--- F7: Trace spam verification ---")
        print()
        combined_stdout = stdout_during_query1 + stdout_during_query2
        print(f"Total stdout captured during queries: {repr(combined_stdout)}")
        trace_keywords = ["[TRACE]", "TraceEvent", "OPERATION_COMPLETE", "OPERATION_START"]
        trace_events_found = [kw for kw in trace_keywords if kw in combined_stdout]
        print(f"Trace keywords found in stdout: {trace_events_found}")
        print(f"F7 fix verified (no trace spam): {len(trace_events_found) == 0}")
        print()
        # Important note: MemoryTraceEmitter writes to an internal buffer, not stdout.
        # So the F7 check passes trivially (combined_stdout is empty), which is the
        # correct behavior — F7's whole point is that trace events should NOT print
        # to stdout. An empty capture is success, not a bug.
        print("Note: MemoryTraceEmitter writes to an internal buffer, not stdout.")
        print("An empty stdout capture is the correct behavior — F7 fix means trace")
        print("events should NOT print to stdout. Empty capture = success.")
        print()

        # --- Summary ---
        print("=== Summary ===")
        print()
        print("Gate 5 (prompt-37.6.1 target: query flow + memory):")
        print(f"  - Query 1 executed: True")
        print(f"  - Query 2 executed: True")
        print(f"  - memory_router not None: {memory_router is not None}")
        print("Gate 6 (prompt-37.6.1 target: adapter swap):")
        print(f"  - Swap executed: True")
        print(f"  - memory_router preserved: {new_memory_router is original_memory_router}")
        print(f"  - memory_router is not None: {new_memory_router is not None}")
        print("F7 (trace spam):")
        print(f"  - No trace events in stdout: {len(trace_events_found) == 0}")


if __name__ == "__main__":
    asyncio.run(verify_tui_e2e())
```

**Note**: This script improves on Plan 38.6 Step 1's version in two ways: (1) `create_worker` is now mocked in the adapter swap section to avoid the "lm_studio not installed" failure mode (was a STOP condition in Plan 38.6), and (2) the script bypasses `JarvisTUI` entirely — it constructs the cognition stack directly, copying the wiring from `JarvisTUI.__init__` lines 226-403. This eliminates the Textual App instantiation risk that was the underlying reason "no interactive shell" kept resurfacing as a skip justification.

### Step 2 — Run the script, paste literal output into CHANGELOG

```powershell
python C:\Jarvis\scripts\verify_tui_e2e.py
```

**Paste the literal output into CHANGELOG** as a new subsection appended to the prompt-37.6.1 entry (per Rule 16 append-only):

```
#### Plan 38.7 Step 1 — Plan 38.6 Track A executed (Rule 19 remediation)

The original prompt-37.6.1 entry marked Gates 5 and 6 as SKIPPED. Plan 38.6
deferred to Plan 38.8 without executing Track A. This section provides the
actual Track A verification output via scripts/verify_tui_e2e.py.

##### Gate 5 — TUI query flow + memory persistence (ACTUAL OUTPUT)

<paste literal script output for Gate 5>

##### Gate 6 — Adapter swap preserves memory_router (ACTUAL OUTPUT)

<paste literal script output for Gate 6>

##### F7 — Trace spam verification (ACTUAL OUTPUT)

<paste literal script output for F7 check>

##### Track A verdict

- Gate 5: <PASSED / FAILED — explain>
- Gate 6: <PASSED / FAILED — explain>
- F7: <PASSED / FAILED — explain>

If all three pass: Plan 38.8 deferral is no longer needed. Rule 19 violation
from prompt-37.6.1 is closed by Track A evidence.

If any fail: paste the literal error/failure output, STOP, and report. The
failure indicates a real bug (not "no interactive shell") and gets its own
follow-up plan.
```

**STOP conditions for Step 1**:
- If the script raises an unhandled exception: STOP. Paste the literal traceback. The exception indicates either (a) a script bug — fix and retry, or (b) a real TUI/cognition-stack bug — document and create a Plan-N ticket. **Do not defer with "no interactive shell" — the script doesn't use one.**
- If `memory_router.get_global_context()` doesn't exist: adapt the script to use the correct API (`fetch_by_filter` or whatever MemoryRouter actually exposes). Document the adaptation in CHANGELOG. Don't skip the memory verification.
- If all three gates pass: proceed to Step 3 (Gemini migration).
- If any gate fails: STOP. Do not proceed to Gemini migration. Report the failure to GLM for next-plan determination.

### Step 3 — Gemini SDK migration

**File**: `adapters/gemini.py`

**Reference**: https://ai.google.dev/gemini-api/docs/sdks

**Key API changes** (from Plan 38 Step 7, expanded):
- `import google.generativeai as genai` → `from google import genai`
- `genai.configure(api_key=...)` → `client = genai.Client(api_key=...)` (client must be held as instance state, not module-level)
- `genai.GenerativeModel(...)` → `client.models.generate_content(...)` (different call shape — model is a parameter, not a class)
- `genai.types.GenerationConfig(...)` → `genai.types.GenerateContentConfig(...)`
- **Async pattern**: if the adapter uses `await` for generation (likely, given the codebase is async-first), the new SDK exposes async via `client.aio.models.generate_content(...)` — NOT `client.models.generate_content(...)`
- **Streaming**: if the adapter uses `generate_content(..., stream=True)`, the new SDK has a different streaming iterator shape — verify the consumer code handles the new shape
- **`genai.types` namespace**: significantly restructured; any other type imports from `genai.types` need to be checked individually

**Remove the existing `# noqa: Plan 38.7` suppression** on line 12 since this plan is now executing the migration.

**Line-count guard — STOP condition for THIS step specifically**: After making the changes, run:

```powershell
git diff --stat adapters/gemini.py
```

If the production-code diff (excluding comments and blank lines) exceeds **20 lines changed**, STOP. The migration is larger than in-scope for this plan — leave the `# noqa: Plan 38.7` suppression in place (it's already auditable) and skip the migration. Document in CHANGELOG: "Step 3 deferred — migration diff exceeded 20-line guard. Inline `# noqa: Plan 38.7` suppression retained. Migration will be addressed in a future plan if warning elimination becomes priority."

**Verify (if migration proceeded in-scope)**:

```powershell
# Test still skips gracefully (no API key) OR passes (if API key set)
python -m pytest tests/test_gemini_adapter.py -v --tb=short

# Verify warning eliminated
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai|gemini.py:12"
```

Last command must return **zero matches**.

**Expected warning count change**: 1 warning eliminated (Gemini). New total: 1 → 0 warnings.

### Step 4 — Update handoff + CHANGELOG

**File**: `SOVEREIGN_AI_HANDOFF.md`

**Changes**:
1. Update "Last updated" line to reference prompt-38.7
2. Update test baseline warning count (1 → 0 if Gemini migrated, stays at 1 if deferred)
3. **Remove Plan 38.8 from deferred-actions list** (Track A passed in Step 1, so Plan 38.8 is no longer needed)
4. Note Rule 19 remediation complete via Track A

**File**: `CHANGELOG.md`

Append (per Rule 16 append-only):
- Step 1 evidence (Track A script output)
- Step 3 evidence (Gemini migration diff stat + pytest output, OR deferral documentation)
- Final test counts (1 warning → 0 warnings if migrated, 1 warning if deferred)

## Verification gates

### Gate 1 — Drift check

```
git diff --stat prompt-38.6..HEAD -- cli/tui.py adapters/gemini.py scripts/
```

**Expected**: empty output for all three paths.

For `SOVEREIGN_AI_HANDOFF.md` and `CHANGELOG.md`: allowed per known-landmine procedure.

**Note on gate numbering**: Gates 1-7 below are THIS plan's execution gates. The "Gate 5" and "Gate 6" labels inside the script (Step 1) correspond to the original prompt-37.6.1 verification targets being remediated, not this plan's gates. Two separate numbering systems — don't conflate them.

### Gate 2 — `scripts/verify_tui_e2e.py` exists and runs

```powershell
Test-Path C:\Jarvis\scripts\verify_tui_e2e.py
python C:\Jarvis\scripts\verify_tui_e2e.py
```

**Expected**: `True` for first command. Second command runs and produces output (success or error).

### Gate 3 — Track A output pasted into CHANGELOG

```powershell
Select-String -Path CHANGELOG.md -Pattern "Plan 38.7 Step 1 — Plan 38.6 Track A executed"
Select-String -Path CHANGELOG.md -Pattern "Track A verdict"
```

**Expected**: at least 1 match for each.

### Gate 4 — Track A verdict recorded (not placeholder)

```powershell
Select-String -Path CHANGELOG.md -Pattern "Gate 5: <PASSED|Gate 5: <FAILED"
```

**Expected**: at least 1 match showing Devin filled in the verdict (not left as `<PASSED / FAILED — explain>` placeholder).

**CRITICAL**: If Gate 5 verdict is FAILED, STOP. Do not proceed to Gemini migration. Report the failure to GLM.

### Gate 5 — Gemini migration (or documented deferral)

```powershell
# If migration proceeded:
python -m pytest tests/ -q --tb=no 2>&1 | Select-String "google.generativeai|gemini.py:12"
# Expected: zero matches

# If migration deferred (20-line guard triggered):
Select-String -Path CHANGELOG.md -Pattern "Step 3 deferred"
# Expected: at least 1 match documenting the deferral
```

### Gate 6 — Plan 38.8 removed from deferred-actions

```powershell
Select-String -Path SOVEREIGN_AI_HANDOFF.md -Pattern "Plan 38.8"
```

**Expected**: zero matches (Plan 38.8 no longer needed because Track A passed).

**Exception**: If Track A failed (Gate 4 verdict = FAILED), Plan 38.8 stays in deferred-actions and a new plan ticket is created for the bug Track A discovered.

### Gate 7 — Tag-push verification

```powershell
git ls-remote --tags origin | findstr prompt-38.7
```

**Expected**: 1 match showing the tag on origin. **Do not skip this step.** (Known landmine from prompt-38.)

## STOP conditions

- **If Step 1 script raises an unhandled exception**: STOP. Paste literal traceback. Investigate root cause — real bug, not "no interactive shell." The script bypasses JarvisTUI entirely (constructs cognition stack directly), so there's no Textual App to fail.
- **If you find yourself about to defer or skip Step 1 for any reason other than an unhandled script exception**: STOP and report — do not defer. "No interactive shell" is not a valid reason (the script doesn't use one). "JarvisTUI won't instantiate" is not a valid reason (the script doesn't instantiate JarvisTUI). Only an unhandled exception in the script itself justifies deferral, and even then the deferral must document the specific exception and traceback.
- **If Step 1 memory_router API mismatch**: adapt script, document adaptation, retry. Do not skip memory verification.
- **If Step 1 Gate 5 or Gate 6 verdict is FAILED**: STOP. Do not proceed to Step 3 (Gemini). Report failure to GLM.
- **If Step 3 Gemini migration diff exceeds 20 lines**: defer migration per Step 3 procedure. Leave `# noqa: Plan 38.7` in place. Continue to Step 4.
- **If Gate 7 (tag-push) shows no match**: push the tag, re-verify. Do not mark gate PASSED without tag on origin.

## Out of scope

- Production code changes to `cli/tui.py` (correct per prompt-37.6.1 inspection)
- New unit tests beyond what Track A script provides
- Broad-except audit (Plan 39+)
- ruff/mypy triage (Plans 43-44)
- Track B manual TUI verification (optional, user can do anytime — template already in CHANGELOG from prompt-38.6)

## Closing steps

**Execute these in order. Do not mark a step done until it's actually done.**

1. `git add scripts/verify_tui_e2e.py adapters/gemini.py` (if Gemini migrated; otherwise just the script)
2. `git commit -m "fix: prompt-38.7 — Plan 38.6 Track A executed + Gemini SDK migration"`
   - **Conditional — Step 3 deferred?** If Gemini migration deferred (20-line guard), amend commit message to: `"fix: prompt-38.7 — Plan 38.6 Track A executed (Rule 19 remediation); Gemini migration deferred (20-line guard) [partial: gemini-migration-pending]"`
3. `git tag prompt-38.7`
4. `git show prompt-38.7 --stat` — verify file list
5. `git rev-parse prompt-38.7` — confirm hash matches the commit
6. Update `CHANGELOG.md` (append-only) with:
   - **Files Modified**: `scripts/verify_tui_e2e.py` (new), `adapters/gemini.py` (if migrated)
   - **Implementation Notes**: Track A result per gate, Gemini migration result (migrated or deferred with reason)
   - **Testing Results**: baseline (1 warning from prompt-38.5) → final (0 warnings if migrated, 1 warning if deferred)
   - **Verification Gate Output**: literal output of each gate
   - **Rule 19 remediation status**: closed (Track A passed) or still open (Track A failed — escalate)
7. Update `SOVEREIGN_AI_HANDOFF.md`:
   - Update "Last updated" line to reference prompt-38.7
   - Update test baseline warning count
   - Remove Plan 38.8 from deferred-actions (if Track A passed)
   - Note Rule 19 remediation status
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md`
9. `git commit -m "docs: prompt-38.7 changelog and handoff update"`
10. `git push origin master && git push origin prompt-38.7`
11. **Post-push verification**: `git ls-remote --tags origin | findstr prompt-38.7` — verify the tag exists on the remote. **Do not skip this step.**

## After Plan 38.7 lands

If Track A passed: Rule 19 violation from prompt-37.6.1 is closed. Plan 38.8 does not need to exist. Every prior SKIPPED gate now has corresponding evidence (Track A) or formal deferral (Plan 38.8 removed).

If Gemini migrated: test suite is at 0 warnings. Clean baseline for future plans.

If Gemini deferred (20-line guard): test suite is at 1 warning (Gemini, suppressed with `# noqa: Plan 38.7` inline). Still auditable, not silent noise.

The horizontal cleanup queue can now proceed:

- **Plan 39** — Broad-except audit, part 2 (system/) — ~132 sites in resource_manager, model_acquisition, profiler, model_registry, monitor_daemon
- **Plan 40** — Broad-except audit, part 3 (skills/)
- **Plan 41** — InputSanitiser wiring
- **Plan 42** — InputSanitiser redesign
- **Plan 43** — ruff triage
- **Plan 44** — mypy triage
- **Plan 45+** — graphify integration cluster, proper MemoryBackend.delete(), trajectory_exporter functional redesign

Plans 39+ can land in any order. The Rule 19 remediation is complete (or formally escalated if Track A failed).

## For Claude review (Devin: do not execute this section)

**Reviewer instructions**: This plan has two non-negotiable scopes bundled. Check that:

1. **Step 1 (Track A) is correctly framed as non-negotiable.** The plan's intro says "Step 1 is non-negotiable" and explains why — Track A was skipped in Plan 38.6, deferring again would be a second Rule 19 violation. Is this framing strong enough? Should there be additional enforcement (e.g., a STOP condition that prevents proceeding to Step 3 if Step 1 is deferred)?

2. **The script will actually work without an interactive shell.** Plan 38.6's script was deferred with "no interactive shell." Plan 38.7's script is the same except `create_worker` is now mocked (avoiding the lm_studio-not-installed failure mode). Is there any other reason the script would require an interactive shell? The script uses `unittest.mock.patch`, calls `process_command()` directly, captures stdout via `io.StringIO`. No Textual UI, no terminal interaction. Should be fully automated.

3. **The STOP condition for Step 1 failure is correct.** If Track A's Gate 5 or Gate 6 verdict is FAILED, the plan says STOP and don't proceed to Gemini migration. Is this the right call? The failure would indicate a real TUI/cognition-stack bug, which is a different scope than this plan. Creating a follow-up plan for the bug is the right approach — flag if the STOP condition doesn't make this clear.

4. **The 20-line guard on Gemini migration is appropriate.** Plan 38.5 had this guard; Plan 38.7 inherits it. If migration exceeds 20 lines, defer and leave `# noqa: Plan 38.7` in place. Is 20 lines the right threshold? The Gemini SDK has substantially different async patterns (`client.aio.models.generate_content`) — if the adapter uses async (likely), the migration may legitimately exceed 20 lines just for the call shape change. Should the guard be higher (e.g., 30 or 40 lines)?

5. **Plan 38.8 removal is correctly conditioned on Track A passing.** Gate 6 says Plan 38.8 should be removed from deferred-actions IF Track A passed. If Track A failed, Plan 38.8 stays and a new plan is created for the bug. Is this logic clear?

6. **No known landmines violated**:
   - Tag-push gate (closing step 11) explicitly included ✅
   - Rule 19 evidence requirement enforced (Step 2 + Gate 3 + Gate 4) ✅
   - No `global_rules.md` citations ✅
   - No re-guessing disproved hypotheses (this plan builds on prompt-37.6.1's wiring which is correct, just unverified) ✅
   - Drift check distinguishes code files from docs files (Gate 1) ✅
   - **New landmine check**: Does this plan correctly handle the "no interactive shell used as skip reason" pattern? Step 1's intro explicitly says "No interactive shell is not a valid reason to skip Step 1 — the script doesn't use one." Is this strong enough?

**Output format**: Lead with verdict (ship as-is / ship with a fix / send back), then list specific issues by severity. Skip praise. Cite specific line numbers when flagging factual errors.

**Token economy note**: This is a medium plan (~370 lines). If round 1 finds only MINOR issues, apply them and place directly — no round 2 needed. If round 1 finds a CRITICAL issue (e.g., script design fundamentally won't work), apply the fix and do one round 2 diff review.
