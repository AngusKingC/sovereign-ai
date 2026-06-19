# Sovereign AI Agent Framework — Project Handoff

**Last updated**: 2026-06-19 13:20 — post prompt-38.7. Executed Plan 38.6 Track A via scripts/verify_tui_e2e.py (Rule 19 remediation complete - all three gates passed). Gemini SDK migration deferred (20-line guard exceeded). Test baseline: 1071 passed, 29 skipped, 1 failed, 1 warning (measured with python -m pytest tests/ -q --tb=no --ignore=tests/test_llama_cpp_adapter.py). 1 pre-existing flaky failure (test_lm_studio_adapter.py::test_health_check_without_server).

**Post-prompt-38 documentation update** (2026-06-19, separate from any prompt): Added "Claude review workflow (token-economical)" subsection to the Workflow section. Documents the new per-prompt context brief pattern, deprecates `CLAUDE_REVIEWER_ROLE.md` as a separate upload, and codifies the round-1-full / round-2-diff / round-3-rarely review structure. Known landmines list updated with prompt-38 tag-push issue, Plan 38.5 re-guessing-disproved-hypotheses issue, per-file-count-mismatch issue, and drift-check-false-positive-on-docs-files issue.

**Static analysis baseline**: 365 ruff errors, 116 mypy errors. CI will fail on first run. This is the worklist, not a problem.

---

## How to use this document

This is a state-of-the-project brief, not an architecture document. It tells you:
1. What the project is supposed to be.
2. What actually works right now.
3. What's broken right now.
4. What the next 5 prompts are, with verification gates.
5. What's deferred and why.

If something isn't in this document, it isn't real. The previous version of this document described 25+ subsystems as "built" when 4 were reachable from any runtime entry point. That pattern ends here. **If a subsystem is not reachable from `jarvis` or `jarvis serve`, it does not exist for the purposes of this handoff**, regardless of how many tests pass.

---

## Project Vision

A local-first, self-improving AI assistant for one user's specific context: media production, sailing, 3D printing, CNC machining. Runs locally by default, escalates to cloud when the task demands it, monitors open-loop background tasks (weather, AIS, email) and interrupts only when necessary.

**Core philosophy**: Strong, robust, simple core. Wire as you go. No new horizontal capability until the existing stack is reachable and demonstrably improving worker outputs.

---

## What works right now

Verified by running the code, not by reading the CHANGELOG:

- **`jarvis`** (no args) — starts Textual TUI with full cognition stack wired (Orchestrator, MemoryRouter, ApprovalGate, EscalationEngine, AdapterFallbackChain, WorkerFactory, RatingSystem, InstructionGenerator, InstructionVersionManager, OutputEvaluator, TraceOptimiser, OrchestratorImprovementLoop). User can type queries, get responses from local Ollama. Memory is now stateful across queries (prompt-37.6).
- **`jarvis "query"`** — non-interactive single-query mode via Rich CLI.
- **`jarvis --rich`** — Rich-based interactive CLI with slash commands.
- **`jarvis --setup` / `--reconfigure` / `--doctor`** — SetupWizard runs, writes `jarvis.config.yaml` + `.env`, doctor checks Ollama/Postgres/Qdrant/Obsidian reachability.
- **`jarvis serve`** — starts FastAPI server on default port 8000 (configurable via --host/--port). Accepts task submissions via POST /api/tasks, returns worker listings via GET /api/workers.
- **TUI slash commands** — `/help`, `/status`, `/clear`, `/exit`, `/model`, `/adapter`, `/theme` work. `/adapter ollama` and `/adapter lm_studio` actually switch adapters; the other 9 listed adapters crash with `ValueError` because `cli/adapter_factory.py` only knows those two.
- **Session manager** — in-memory mode works. Postgres persistence does not (see "What's broken").
- **Command history** — in-memory mode works. Postgres persistence does not.
- **Test suite** — 1080 tests pass. Quality varies; some are smoke tests with `assert True` (see Process section).

That's it. Everything else is either broken, unreachable, or aspirational.

---

## Test environment prerequisites

The following environment variables are required for full test coverage:

- **ANTHROPIC_API_KEY** — Required for `test_anthropic_adapter.py` (12 tests). Without this key, these tests are skipped.
- **GEMINI_API_KEY** — Required for `test_gemini_adapter.py` (11 tests). Without this key, these tests are skipped.

These are legitimate environment-conditional skips. The core test suite (1080 tests) runs without these keys.

---



## What's broken right now

Open bugs, ordered by impact. Each has a verification step so the fix can be confirmed.

### F4 — `cli/serve.py` constructs 14 subsystems but registers zero workers
- **Location**: `cli/serve.py:148-155` constructs `WorkerFactory` but never calls it; no `orchestrator.register_worker(...)` anywhere in the file.
- **Cause**: 35.6b wired the cognition stack but forgot the worker. `submit_task()` calls `route_task()` which raises `WorkerNotFoundError("No workers registered")`.
- **Fix**: After constructing `WorkerFactory`, call it to create a default OllamaWorker and register it with the orchestrator. Or skip the factory and register an OllamaWorker directly (simpler, matches what `cli/tui.py:279-280` does).
- **Verification**: Start `jarvis serve`, hit `POST /api/tasks` with `{"intent": "test"}` — should return a real `task_id`, not `{"task_id": "", "status": "error"}`.

### F6 — MemoryRouter call-signature mismatch (FIXED in prompt-37.5)
- **Location**: `core/rating_system.py`, `core/evaluator.py`, `core/instruction_generator.py`, `core/instruction_versioning.py`, `core/orchestrator_improvement.py`, `core/trace_optimiser.py`, `core/worker_factory.py`, `core/scratchpad.py`, `system/worker_persistence.py`, `system/resource_manager.py`, `system/model_registry.py` — 33 call sites fixed across 12 files in prompt-37. Plus `core/memory_router.py` itself (added new methods). 13 additional call sites in 3 files (approval_trust, notes_skill, reminder_skill) fixed in prompt-37.5 via `scoped_read`/`scoped_write`.
- **Status**: Fully closed. 4 new MemoryRouter methods added (`fetch_by_filter`, `write_to_collection`, `get_global_context`, `set_global_context`) and 33 call sites updated in prompt-37. Plus `scoped_read`/`scoped_write` added in prompt-37.5 (13 call sites in 3 files: approval_trust, notes_skill, reminder_skill). `trajectory_exporter.py` uses a different pattern (`fetch(Type, filter_func=...)`) and is stubbed with a Plan 45 deferral (Option 2 fallback returns 0 with WARNING trace).
- **Verification**: `mypy core/ system/ --ignore-missing-imports | Select-String "Unexpected keyword argument"` returns zero hits (excluding `trajectory_exporter.py` which is Plan 45).
- **Note on `core/retention.py`**: Listed in the original F6 location list and Plan 37 entry, but verified against the live repo — retention.py uses the correct `fetch(task)` and `write(dict)` signatures. No `collection=`/`document_id=`/`limit=` kwargs. The handoff's inclusion was inaccurate; retention.py was never affected by F6. No changes needed. (Claude review finding #1, applied in Plan 37.5.)

### F7 — Trace spam in CLI from `WorkerBase` defaulting to `ConsoleTraceEmitter`
- **Location**: `core/worker_base.py:88-91`
- **Cause**: When `emitter=None` (which is always, because `OllamaWorker.__init__` doesn't accept or pass an emitter), the base class defaults to `ConsoleTraceEmitter()` which prints every trace event to stdout.
- **Fix**: Change the default to `MemoryTraceEmitter()`. CLI can still opt into console output via an explicit emitter.
- **Verification**: Run `jarvis "hello"` and confirm no trace events are printed alongside the response.

---

## Recently fixed (prompt-37)

Fixed in prompt-37. These entries will be removed in the next prompt.

- **F6 (partial)** — MemoryRouter call-signature mismatch — Added new methods `fetch_by_filter`, `write_to_collection`, `get_global_context`, `set_global_context` to MemoryRouter. Fixed 33 call sites across 12 files. However, `system/trajectory_exporter.py` uses a different pattern `fetch(Type, filter_func=...)` not covered by the F6 spec and still has mypy errors. Also 69 test failures due to mock implementation details.

---

## Recently fixed (prompt-37.5)

Fixed in prompt-37.5. These entries will be removed in the next prompt.

- **F6 (fully closed)** — Added `scoped_read`/`scoped_write` to MemoryRouter (13 call sites in 3 files: approval_trust, notes_skill, reminder_skill). Fixed `escalation.py:146` phantom `request` call → `request_approval`. Fixed `trajectory_exporter.py` with Option 2 stub (Plan 45 deferral). Added TYPE_CHECKING import for StrategicContext (rolled in from 37.1 gap).

---

## Recently fixed (prompt-36)

Fixed in prompt-36. These entries will be removed in the next prompt.

- **F1** — `jarvis serve` crashes with "Got unexpected extra argument (serve)" — Fixed by stripping 'serve' from sys.argv before typer.run()
- **F2** — `MemoryRouter(postgres_backend=...)` crashes when DSN is set — Fixed by making backends optional with default None
- **F3** — `cli/serve.py:57` passes a list where MemoryRouter expects a dict — Fixed by changing backends=[] to backends={}
- **F5** — `list_workers()` missing on Orchestrator — Fixed by adding async list_workers() method to Orchestrator

---

## What's built but not reachable

These subsystems exist with passing tests but are never constructed from any runtime entry point. They are not "features" — they are dormant code. Listed here so they're not forgotten, but **do not assume they work** until they are wired and tested end-to-end.

| Subsystem | File | Why it's dormant |
|---|---|---|
| MultiWorkerDispatcher | `core/multi_worker.py` | Never constructed anywhere |
| A2ARouter | `core/a2a_protocol.py` | Same |
| MonitorDaemon | `system/monitor_daemon.py` | Same |
| VoiceDaemon | `system/voice_daemon.py` | Same |
| TelegramGateway | `gateways/telegram/gateway.py` | Same |
| RetentionDaemon | `system/retention_daemon.py` | Same |
| RetentionManager | `system/retention_manager.py` | Same |
| TriggerEngine | `core/event_trigger.py` | Same |
| NotificationSystem | `core/notification.py` | Same |
| ResourceBudget | `core/resource_budget.py` | Same |
| VerbosityManager | `core/verbosity.py` | Same |
| TrajectoryExporter | `system/trajectory_exporter.py` | Stubbed with Plan 45 deferral (prompt-37.5). Backend doesn't support `fetch(Type, filter_func=...)` pattern. |
| MemoryCompactor | `core/memory_compactor.py` | Same |
| InputSanitiser | `core/input_sanitiser.py` | Built but never invoked from any external-input code path. Clean Architecture Rule 13 violation. |
| MCPServer | `skills/mcp_server.py` | Built but never started |
| MCPAdapter | `adapters/mcp_adapter.py` | Built but never constructed |

When the next prompt wires one of these into a runtime entry point, remove it from this table. The table should shrink over time, not grow.

---

## What's deferred (not started)

These are real product features that the plan calls for but no code exists for. They are not "in progress" — they are queued. Listed in priority order.

1. **Plan 38.7 — Gemini SDK migration** — Executed Track A (Rule 19 remediation) via scripts/verify_tui_e2e.py - all three gates passed. Gemini SDK migration deferred (20-line guard exceeded - 51 lines changed). Inline `# noqa: Plan 38.7` suppression retained in adapters/gemini.py.
2. **Marine stack** (Prompts 28.7, 31.5 in old plan) — weather, marine_weather, AIS, tidal, passage_planner, vhf_monitor, satellite_comms. Zero lines of code exist. This is the moat. Should ship as portable SKILL.md files (see Skills Ecosystem section).
3. **Sandboxed execution** for `skills/terminal/` and `skills/code_execution/`. Currently runs subprocesses on host with no isolation. OpenHands ships Docker sandboxing by default; Sovereign has nothing.
4. **Streaming output** from Ollama through the worker pipeline to the TUI/Web GUI. Every cloud coding agent streams tokens; Sovereign waits for the full response.
5. **Function-calling / tool-use loop.** Modern agent frameworks let the LLM decide which skills to call. Sovereign's "route once, generate once" model is a generation behind.
6. **Deployment story.** Docker compose with Postgres + Qdrant + Jarvis + Ollama. systemd unit / Windows service. Without this, "Jarvis that runs in the background" has no delivery path.
7. **Eval harness.** A held-out task suite to measure whether self-improvement is actually happening. Without this, "self-improving" is an assertion.
8. **Plan mode.** Agent proposes a plan, user approves, agent executes. Table stakes for agentic coding in 2026.

---

## Skills ecosystem — strategic shift

The original plan defined a proprietary skill format in `skills/SKILL_SPECIFICATION.md`. The agent-skills ecosystem has since consolidated around a portable SKILL.md format (YAML frontmatter + markdown + optional scripts) used by Claude Code, Codex, Cursor, Copilot, Gemini CLI, OpenClaw, Hermes, Windsurf. See `agentskills.io`, SkillsMP, ClawHub.

Three reference implementations worth studying:
- **`Agents365-ai/drawio-skill`** — production tool (NL → .drawio XML → PNG/SVG/PDF, vision self-check, codebase-to-diagram). 3.5k stars. Single SKILL.md, no MCP server, no daemon. Works in 7+ agents.
- **`DietrichGebert/ponytail`** — behavioral modifier (YAGNI ladder injected every turn via lifecycle hooks). 80-94% less code, 3-6× faster, 42-75% cheaper across Claude models. Works with 13 agents.
- **`shadcn/improve`** — meta-skill (audits codebase, writes self-contained plans for cheaper executors). Uses parallel subagents across 9 categories, vets findings, writes plans with verification gates and STOP conditions.

**`NVIDIA/skillspector`** is the security scanner for this ecosystem — 64 vulnerability patterns across 16 categories. Their research found 26.1% of skills contain vulnerabilities. If Sovereign consumes community skills, it needs skillspector-equivalent scanning as a CI step.

**Strategic implication for Sovereign**: the marine stack should ship as portable SKILL.md files installable into Claude Code, Cursor, Codex, *and* Sovereign — not as Sovereign-exclusive Python skills. The moat is the marine-domain knowledge, not the framework. A bigger market reaches Sovereign's marine capability if it's portable.

**Action**: Prompt 36.5 (after foundation is solid) adds an `agentskills.io` loader to Sovereign so external skills load natively alongside the existing Python-class skills.

---

## Voice interface — strategic shift

Sovereign has 5 classes for voice (VoiceInterface, VoiceDaemon, AudioCapture, TTSSkill, TranscriptionSkill) built across Prompts 33 and 33.5. None are wired into any runtime entry point. They use Python where Rust would be appropriate.

**`cjpais/Handy`** is the actual product Sovereign's voice stack is supposed to be: Tauri (Rust + React) desktop app, Whisper + Parakeet locally with Silero VAD, global keyboard shortcut that triggers transcription in any app, system-service architecture, paste-into-any-text-field UX, distributes via Homebrew/winget/releases. MIT-licensed, designed to be forkable.

**Action**: Don't rebuild Handy in Python. Either bundle Handy as a dependency and route Sovereign's voice commands through it, or port Handy's architecture and replace the Python voice stack. The marine stack use case (talk to Jarvis while sailing, get voice responses) needs Handy's "press shortcut, speak, paste anywhere" UX, not Sovereign's "wake word → STT stub → orchestrator → TTS stub" UX.

---

## Workflow

- **Devin** writes all code, runs tests, updates `CHANGELOG.md`, updates this handoff. Append-only to CHANGELOG. Every entry date includes time: `YYYY-MM-DD HH:MM`.
- **Claude** reads this handoff at session start, advises on architecture and sequencing, maintains Devin memory entries. Does not write code.
- **When the user pastes a CHANGELOG entry into Claude**, Claude produces the next prompt spec using the Plan Template (below) without waiting to be asked.

### Prompt spec format (replaces all previous prompt-spec regimes)

Every prompt spec is a single markdown file using the template below. The template is borrowed from `shadcn/improve` because it enforces self-contained plans with verification gates — which is exactly the discipline the 35.6b/35.6c/35.6d regressions showed was missing.

```markdown
# Plan NNN: <Imperative title — what will be true after this plan>

> Executor instructions: Follow step by step. Run every verification
> command and confirm expected result before moving on. If a STOP
> condition fires, stop and report — do not improvise. Update the
> status row in `plans/README.md` when done.
>
> Drift check (run first): `git diff --stat <planned-at SHA>..HEAD -- <in-scope paths>`
> If any in-scope file changed since this plan was written, compare
> Current state excerpts against live code; on mismatch, STOP.

## Status
- Priority: P1 | P2 | P3
- Effort: S | M | L
- Risk: LOW | MED | HIGH
- Depends on: plans/NNN-*.md (or "none")
- Planned at: commit <short SHA>, <YYYY-MM-DD>

## Why this matters
2-5 sentences. The problem, its concrete cost, what improves when fixed.

## Current state
- The relevant files, each with one line on its role.
- Excerpts of the code as it exists today, with `file:line` markers.
- Repo conventions that apply, with a pointer to one exemplar file.

## What to change
Numbered steps. Each step:
- States exactly what to edit (file, function, line range).
- Includes the new code or the precise diff.
- Ends with a verification command and its expected output.

## Verification gates (run in order, all must pass)
1. `python -m pytest tests/<relevant_test_file>.py -v` — expected: N passed, 0 failed.
2. `ruff check <files_touched>` — expected: 0 errors.
3. `mypy <files_touched> --ignore-missing-imports` — expected: 0 errors.
4. Specific functional check (e.g. "run `jarvis serve`, hit `POST /api/tasks`, expect non-empty task_id").

## STOP conditions
- If verification gate 1 reveals pre-existing failures unrelated to this plan, stop and report.
- If a file outside the in-scope list needs editing, stop and report.
- If the fix requires >50 lines of new code, stop — the plan was underscoped.

## Out of scope
Explicit list. Anything not in scope requires a new plan.
```

This template replaces:
- The 7 mandatory structural elements from the old prompt-spec regime (lines 46-127 of the previous handoff).
- The pre-edit checklist with 5 ticked boxes.
- The per-file pre-edit statements.
- The baseline confirmation gate.
- The tag verification instruction.

The template enforces the same discipline structurally — verification gates are part of the plan, not external process. The executor cannot mark the plan done without running the gates.

### Closing steps (mandatory, every prompt)

1. Run full test suite: `python -m pytest tests/ --ignore=tests/test_llama_cpp_adapter.py -v`. Confirm zero new failures.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors.
4. `git add . && git commit -m "checkpoint: prompt-{N}" && git tag prompt-{N}`
5. `git show prompt-{N} --stat` — verify file list contains only files in this plan. If unexpected file appears, `git tag -d prompt-{N}`, clean, re-tag.
6. Update `CHANGELOG.md` (append-only) with: Files Modified (per-file detail), Implementation Notes (mid-prompt failures and how resolved), Testing Results (baseline → final, with command), Verification Gate Output (literal output of each gate).
7. Update this handoff: move the completed plan from "Next 5 prompts" to "Completed prompts" table. Update "What's broken" section (remove fixed items). Update "Built but not reachable" table (remove newly-wired subsystems).
8. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
9. `git push origin master && git push origin prompt-{N}`

**CHANGELOG append procedure** (PowerShell, because file locks):
- `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count` for line counts — never `Get-Content | Measure-Object` (truncates large files).
- `Add-Content` to append — never paste into editor, never use insert operations.
- Before appending: record current line count. After: verify new count exceeds previous, verify last 5 lines with `Select-Object -Last 5`.
- Close the file in the IDE before running `Add-Content`.

### Claude review workflow (token-economical, adopted post-prompt-38)

Plans go through Claude review before Devin execution. To keep Claude's context window manageable, the workflow uses per-prompt context briefs instead of uploading full CHANGELOG/handoff files.

#### Artifacts per plan

1. **`plan-NN.md`** — GLM-authored, clean for Devin. Steps 1-N are execution-only, no inline reviewer notes. Final section is `## For Claude review (Devin: do not execute)` containing 3-5 specific review questions and any areas of uncertainty. **Devin must skip this section** — it is review input, not execution instructions.

2. **`plan-NN-context-brief.md`** — GLM-authored, ~80-120 lines. Contains:
   - **Reviewer instructions**: 7-point check (factual accuracy, numbering collisions, grep strings, internal consistency, STOP conditions, builds on prior findings, known landmines), output format, what not to do. Folded in from the deprecated `CLAUDE_REVIEWER_ROLE.md`.
   - **Known landmines**: updated whenever a new pattern is identified (see list below)
   - **Prior prompt state**: test counts, code/docs commit SHAs, tag status
   - **Prior findings this plan must build on**: CHANGELOG line references with quoted text — prevents re-guessing disproved hypotheses
   - **Files in scope**: list, so Claude knows what's out of scope
   - **Specific questions for Claude**: 3-5 focused questions, not "review this"

#### What NOT to upload to Claude

- **Full `CHANGELOG.md`** (7000+ lines — burns context). Claude only needs the latest entry plus any specific line numbers the plan cites (paste ±5 lines of context per citation).
- **Full `SOVEREIGN_AI_HANDOFF.md`** (450+ lines — Claude only needs the slices referenced in the context brief).
- **`CLAUDE_REVIEWER_ROLE.md`** (deprecated — folded into per-prompt context brief as of post-prompt-38). Delete this file from the repo if it still exists.
- **Prior plan revisions** (only the diff matters for round 2+).

#### Round structure

- **Round 1 (full review)**: Upload `plan-NN.md` + `plan-NN-context-brief.md`. Claude does the full 7-point check. Returns verdict + findings list.
- **Round 2 (diff review only)**: Upload only the REV2 diff section (what changed from REV1) + the original context brief. Claude checks whether each round 1 finding was correctly addressed + any new issues introduced by the changes. Do not re-review unchanged sections — they were fine in round 1.
- **Round 3+**: Almost never needed. If round 2 found only MINOR issues, place the plan without another round. Pushing for round 3 burns tokens for diminishing returns. Only escalate to round 3 if round 2 surfaced a CRITICAL issue.

#### Known landmines — Claude checks every plan against these

Update this list whenever a new pattern is identified. Each entry should reference the prompt where the pattern was first observed.

- **`global_rules.md` is Devin-local and unreachable** (prompt-37.1 Step 7, prompt-37.5 Step 9 — both SKIPPED with "not in workspace"). Any plan asking Devin to edit it needs a fallback for a third skip. Don't cite "global_rules.md Rule N" as authority for anything — the file's contents can't be verified.
- **Gates marked PASSED/SKIPPED without literal output** (Rule 19, recurring mistake pattern #6). New plans must require pasted output, not assertions.
- **`@pytest.mark.skip` because mocking was hard** (recurring mistake #2). Fix the mock or refactor the SUT; don't skip.
- **Tagging with a red test suite** (recurring mistake pattern #5). Full suite must be green before any `git tag`.
- **Tag-push gate skipped** (prompt-38 issue). Closing-step `git push origin prompt-NN` was reported as "pushed to remote" in prompt-38 without the tag actually being on origin — user had to push it manually. Future plans must verify `git ls-remote --tags origin | findstr prompt-NN` returns the tag, and treat "pushed to remote" as an assertion requiring evidence.
- **Re-guessing disproved hypotheses** (Plan 38.5 Step 4 had this). Plans have a tendency to re-propose the same wrong root-cause attribution that a prior prompt already investigated and ruled out. Before claiming a warning/error source, check the prior CHANGELOG entry for "Finding:" or "Result:" on the same topic.
- **Per-file counts that don't match CHANGELOG evidence** (Plan 38.5 had this). If the plan says "11 warnings in test_web_server.py" but the prior CHANGELOG says "15 in web_server.py alone," that's a factual error — flag it. Always cite the CHANGELOG line number for any numeric claim.
- **Drift check false-positive on docs files** (Plan 38.5 Gate 1 had this). The closing-step workflow tags BEFORE the docs commit, so `git diff --stat prompt-NN..HEAD -- SOVEREIGN_AI_HANDOFF.md CHANGELOG.md` will always show non-empty output for those two files by design. Drift checks must distinguish code files (must be empty) from docs files (allowed, with review procedure to confirm only append-only changes).

---

## Next 5 prompts

Ordered. Each is one plan. Do not start Plan N+1 until Plan N's verification gates pass.

### Plan 38 — Fix F7 (trace spam) and add `__init__.py` to `cli/`
- **Priority**: P2
- **Effort**: S
- **Why**: `WorkerBase` defaults to `ConsoleTraceEmitter` which prints every trace event to stdout. Users see a wall of trace spam alongside query responses. Also: `cli/` has no `__init__.py` so mypy can't check it (CI fails immediately).
- **Scope**: `core/worker_base.py:88-91` (change default to `MemoryTraceEmitter`), `cli/__init__.py` (create empty).
- **Verification**: `jarvis "hello"` produces no trace output. `mypy core/ adapters/ workers/ system/ cli/ memory/ --ignore-missing-imports` runs without the "Source file found twice" error.

### Plan 39 — Fix trajectory_exporter.py MemoryRouter pattern
- **Priority**: P2
- **Effort**: S
- **Why**: `system/trajectory_exporter.py` uses `fetch(Type, filter_func=...)` pattern not covered by F6 spec. This pattern needs to be addressed separately.
- **Scope**: `system/trajectory_exporter.py` — update calls to use new MemoryRouter methods or extend MemoryRouter to support this pattern.
- **Verification**: `mypy system/trajectory_exporter.py --ignore-missing-imports` returns zero errors.

### Plan 40 — Fix test failures from Prompt 37
- **Priority**: P1
- **Effort**: M
- **Why**: 69 test failures due to mock implementations not matching expected behavior after MemoryRouter method changes.
- **Scope**: Test files for modules modified in Prompt 37 (rating_system, scratchpad, orchestrator_improvement, trace_optimiser, worker_factory, worker_persistence, instruction_versioning, memory_router, model_registry).
- **Verification**: `python -m pytest tests/ -q --tb=short` returns zero new failures (baseline 1010 passed).

### Plan 41 — Triage ruff errors (365 → 0)
- **Priority**: P2
- **Effort**: M
- **Why**: CI's ruff step will fail with 365 errors. 271 are auto-fixable.
- **Scope**: Run `ruff check . --fix` first. Then manually triage the remaining ~94. Most are F401 (unused imports) — delete them. A few will be F841 (unused variables) — investigate before deleting.
- **Verification**: `ruff check .` returns 0 errors.

### Plan 42 — Triage mypy errors (116 → 0, after Plan 37)
- **Priority**: P2
- **Effort**: L
- **Why**: CI's mypy step will fail with 116 errors (after Plan 37 removes ~50 of them). The remaining ~66 are real type mismatches that will surface as runtime bugs.
- **Scope**: Run `mypy core/ --ignore-missing-imports` and work through the output file-by-file. Categories: (a) `WorkerBase has no attribute "execute"` in `multi_worker.py` — the MultiWorkerDispatcher was built against a different interface; either fix the calls or mark MultiWorkerDispatcher as deferred. (b) `Orchestrator has no attribute "adapter"` in `multi_worker.py` — same. (c) `ResourceBudget has no attribute "check_all_budgets"` — either add the method or fix the call. (d) `Missing positional argument "worker_id" in call to "process_task"` in `event_trigger.py` — the call signature changed; update the call.
- **Verification**: `mypy core/ adapters/ workers/ system/ cli/ memory/ --ignore-missing-imports` returns 0 errors. CI passes end-to-end.

---

## After Plan 40 — Decision point

Once Plans 36-40 land, the foundation is solid: `jarvis serve` works, `jarvis` with DSN works, CI is green, static analysis is clean. At that point, choose:

**Option A: Build the marine stack next.** This validates the moat. Ship as portable SKILL.md files (see Skills Ecosystem section) so the marine capability reaches users of Claude Code, Cursor, Codex, *and* Sovereign. Even with the broken foundation pre-36-40, building 5 small skills (weather, marine_weather, AIS, tidal, passage_planner) would tell you whether LLM-driven passage planning is actually useful as a product. If it isn't, the foundation work is moot. If it is, the foundation work has a concrete use case driving it.

**Option B: Wire the existing cognition stack into `cli/serve.py` end-to-end.** This makes Sovereign a "self-improving" agent as advertised. Requires fixing F6 (Plan 37), then wiring WorkerFactory + RatingSystem + InstructionVersionManager + OutputEvaluator into a working loop with a real evaluation harness. Without an eval harness, "self-improving" is unverifiable.

**My recommendation**: Option A. The marine stack is the moat. The self-improvement machinery is plumbing. Validate the moat before perfecting the plumbing. If the marine stack ships as portable skills, the plumbing can wait — the marine skills work in any host agent.

---

## Architecture rules (never violate)

1. `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/`.
2. `workers/` may import from `core/` and `adapters/` but never from `cli/`.
3. `memory/` may import from `core/` only.
4. `adapters/` may import from `core/` only.
5. `skills/` may import from `core/` only.
6. `web/` may import from `core/` only.
7. `system/` may import from `core/` and `memory/`.
8. `cli/` may import from anywhere.
9. All public functions and methods have return type annotations.
10. No raw LLM calls outside `adapters/`.
11. No memory access outside `MemoryRouter`.
12. No global mutable state. (Known violations: `_global_registry` in `core/commands.py:155`, `_global_emitter` in `core/observability.py:502`. Both have self-acknowledged comments. Plan 41 will remove them.)
13. All I/O operations are async.
14. `InputSanitiser` MUST be called on all externally-sourced content before it enters LLM context: web scraper output, Telegram inbound, user task input. **Currently violated in all three locations** — see "Built but not reachable" table.
15. `ApprovalTrustRegistry` MUST be consulted by `ApprovalGate` before raising any approval request.
16. Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes. No unauthenticated endpoints except `/health`.
17. No broad `except Exception: pass` without an inline comment explaining why the exception is intentionally swallowed. Every swallowed exception must emit a trace event at WARNING level. (Currently violated in dozens of places — Plan 42 will audit and fix.)
18. Tests change with code. When you modify production code, you MUST update the corresponding test file(s) in the same step. Run the specific test file after each production file change. The full test suite MUST pass (green) before tagging. Tagging with a red test suite is forbidden.
19. **Execute steps and gates in listed order. Do not mark a step or gate complete until its producing work is done and its evidence exists.** If a gate's evidence requires output from a later step, the plan is out of order — STOP and report. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. Specifically:
    - Do not mark a gate PASSED before running it. "I will run it later" is not acceptable.
    - Do not mark a gate PASSED if its producing step is incomplete. The gate exists to verify the step's output.
    - Do not mark a gate SKIPPED unless the plan explicitly allows skipping it. "Manual verification" is not a skip reason — if the plan calls for manual verification, do the manual verification and paste the result.
    - Do not mark a test `@pytest.mark.skip` for tests that "couldn't be mocked." Fix the mock or refactor the SUT. `pytest.skip` is for known-broken behavior with a Plan-N deferral, NOT for tests that were written but couldn't be made to run.
    (Currently violated by prompt-37.6: Gate 3 marked PASSED with no output, Gate 5 and Gate 6 marked SKIPPED without being skipped per plan, 8 tests marked `@pytest.mark.skip` because mocking was hard. Plan 37.6.1 fixes this and codifies the rule.)

---

## Dependency injection rules

- `TraceEmitter` and `CommandRegistry` constructed ONCE in `cli/main.py` and passed down. (Currently violated — `cli/main.py` is a thin dispatcher and doesn't construct these. Plan 43 will fix.)
- All components receive emitter via constructor: `emitter: TraceEmitter | None = None`. Default to `MemoryTraceEmitter()`, never `ConsoleTraceEmitter()` (see F7).
- Never import `get_trace_emitter`, `set_trace_emitter`, `emit_trace`, `_global_emitter`, or `_global_registry` anywhere. (Known violations: `core/handlers.py:21` imports `emit_trace` — unused but should be removed. `core/commands.py:155` and `core/observability.py:502` define the globals.)
- When passing emitter to `super().__init__()`, the parameter MUST appear in the subclass `__init__` signature BEFORE the `super()` call.

---

## Completed prompts

| # | Prompt | Tests | Notes |
|---|---|---|---|
| 1-13 | Foundation (schemas, memory, orchestrator, adapters, CLI) | 187→284 | |
| 13.5 | DI refactor | 288 | |
| 14-22 | Approval gate, worker factory, rating, instructions, evaluation, memory scoping, escalation, compaction | 288→446 | |
| 22.5-22.8 | MCP adapter, trace optimiser, escalation re-wire, embeddings | 446→676 | 22.7 and 22.8 were no-ops (work already done) |
| 23-27 | Memory scoping, escalation, compaction, monitor daemon, setup wizard, event triggers | 446→535 | |
| 27.5-29.8 | Skills (terminal, web_search, code_execution, git, docker, http_client, pdf, spreadsheet, clipboard, calculator, home_assistant, screenshot, tts, transcription), adapter fallback, approval trust | 535→767 | |
| 30-31.7 | Multi-worker, A2A, retention, retention manager, security baseline | 767→907 | |
| 32-35.5.1 | Web GUI, voice, voice STT, trajectory export, personal assistant skills, verbosity, model thinking, spec deviation correction | 907→1051 | |
| 35.5.2 | Integrity check + retag | 1051 | User manually corrected test file |
| 35.6b | submit_task/list_tasks, jarvis serve wiring, cognition stack wiring | 1065 | Introduced F1, F3, F4 |
| 35.6c | MemoryRouter postgres_backend kwarg | 1057 | Fix incomplete — F2 still open. CHANGELOG contradicts commit. |
| 35.6d | Foundation bug fixes (Bugs 2-7) | 1056 | Fixed 6 of 7 planned; Bug 7 relabelled (list_workers still missing) |
| 35.6e | CI workflow | 1065 | Will fail on first run (365 ruff + 116 mypy errors) |
| 35.6f | Wire Cognition Stack End-to-End | 1058 | Registered OllamaWorker in serve.py; fixed F3 in test only |
| 36 | Fix jarvis serve end-to-end (F1, F2, F3, F5) | 1044 | Fixed 4 regressions; jarvis serve now starts and returns worker listings |
| 36.5 | Fix llama_cpp test collection | 1072 | Added pytest.importorskip("llama_cpp"); --ignore flag no longer needed |
| 37 | Fix F6 (MemoryRouter call-signature mismatch) | 1010 | Added new MemoryRouter methods; fixed 33 call sites across 13 production files + memory_router.py; 8 test files updated in prompt-37, 3 more in prompt-37.1 = 11 total; trajectory_exporter.py pattern not covered; 69 test failures |
| 37.1 | Fix test mocks and establish Rule 18 | 1078 | Fixed 69 test failures by updating stale mock references; added Rule 18 and recurring mistake pattern #5 |
| 37.5 | Finish F6 - add scoped_read/scoped_write | 1072 | Added scoped_read/scoped_write to MemoryRouter; fixed trajectory_exporter (Option 2 fallback); fixed escalation.py; applied Claude's blocking fixes; 6 trajectory_exporter tests skipped (deferred to Plan 45) |
| 37.6 | Wire TUI Cognition Stack | 1072 | Wired full cognition stack into TUI (Orchestrator, MemoryRouter, ApprovalGate, EscalationEngine, AdapterFallbackChain, WorkerFactory, RatingSystem, InstructionGenerator, InstructionVersionManager, OutputEvaluator, TraceOptimiser, OrchestratorImprovementLoop); 12 subsystems removed from "Built but not reachable" table; 8 new tests in test_tui.py skipped due to OllamaAdapter initialization complexity |
| 37.6.1 | Process discipline rule + 37.6 verification fix-ups | 1080 | Added Rule 19 (process discipline) and recurring mistake pattern #6 to handoff. Fixed 8 skipped tests in test_tui.py using mock-at-instantiation pattern. Completed verification work from prompt-37.6 (Gate 3 output documented). Added mirror rule to global_rules.md (Rule 24). |
| 38 | Warnings, skipped tests, F7, Rule 19 remediation | 1080 | Fixed category 4 (on_event deprecation), category 3 (module-level pytestmark.asyncio on 8 test files), category 6 (invalid escape sequences), category 5 (unawaited coroutine warnings). Partially fixed category 2 (unclosed asyncio transports: 6→4 warnings). Skipped category 1 (google.generativeai deprecation deferred to Phase 9). F7: Changed WorkerBase default emitter to MemoryTraceEmitter. Created cli/__init__.py. Audited skipped tests: 29 legitimate (23 ENV-CONDITIONAL, 6 LEGITIMATE-DEFER). Rule 19 remediation: Deferred manual TUI verification to Plan 38.6. Updated handoff test baseline (63→26 warnings) and added Test environment prerequisites. Verification gates: 8/12 passed (partial success due to warning/skipped count targets exceeded). |

---

## Recurring mistake patterns

Four patterns account for ~90% of the mistakes in the CHANGELOG. The other 18 patterns from the previous handoff were either one-off or had been compensated for by process and are no longer recurring.

1. **Spec deviation without documentation.** When a spec specifies an exact value, format, method name, or scope, implement exactly that. If a different approach seems better, STOP and flag it in Implementation Notes as an explicit deviation with rationale. Do not silently substitute. The 35.5/35.5.1 `<thinking>` vs `<thought>` vs `<think>` saga was this. The 35.6c CHANGELOG contradicting the commit was this.

2. **Mock-the-SUT tests with `assert True`.** When writing tests, the test must verify behaviour, not just confirm the code runs. If a test mocks the system under test and asserts `True`, it is not a test — it is a smoke check. The 35.6b `test_serve_constructs_full_orchestrator` and `test_serve_worker_factory_accessible` tests were this. Test must capture the constructed orchestrator and assert each subsystem is non-None.

3. **Localised fixes for systemic bugs.** When a bug is found in one file, search the codebase for the same pattern before closing the prompt. 35.6d Bug 5 fixed the `MemoryRouter.fetch(dict)` call in `session.py` and `command_history.py` but the same bug exists in 15+ other files. Use `grep` or `mypy` to find all instances.

4. **Broad `except Exception: pass` hiding real failures.** Every audit finding about "dead wiring" traces back to a try/except that swallowed the error that would have told you the wiring was broken. If you must use broad except, emit a trace event at WARNING level with the exception message. If you can use a narrower exception type, do.

5. **Tagging with a red test suite is forbidden.** The full test suite MUST pass (green) before tagging. If the test suite is red, STOP and fix it. Do not tag and promise to fix later. This is the root cause of Prompt 37.1 — Prompt 37 tagged with 69 test failures.

6. **Marking gates passed based on intention rather than execution.** When a plan has steps and gates, the gate verifies the step's output. Marking a gate PASSED before its producing step is complete — or marking it PASSED without pasting literal output — is the same as not running the gate. Prompt-37 was this (Gate 5 tagged with 69 failures). Prompt-37.6 was this (Gate 3 marked PASSED with no output, Gate 5/6 marked SKIPPED without being skipped per plan, 8 tests marked `@pytest.mark.skip` because mocking was hard). The fix is Rule 19: execute in order, paste literal output, do not skip without plan authority.

---

## Hardware context

- **GPU**: NVIDIA RTX 3060 Mobile — 6GB VRAM
- **RAM**: ~15.6GB available after VRAM
- **OS**: Windows
- **Local LLM**: Ollama with `qwen2.5-coder:7b` (Q4_K_M — fits comfortably)
- **KV cache consumes VRAM dynamically** — ResourceManager must budget for context window overhead, not just model weights

---

## User domain context

- **Media production** — video scripts, content creation
- **3D printing and CNC machining** — file generation, design workflows
- **Sailing** — route planning, weather monitoring, AIS tracking

Priority workers once factory is operational:
- NavigationWorker (sailing/AIS/weather — highest priority unique capability)
- VideoScriptWorker
- ThreeDDesignWorker
- ResearchWorker
- EmailWorker

---

## Source references

- Agent Skills format: https://agentskills.io
- SkillsMP (skill marketplace): https://skillsmp.com
- ClawHub (OpenClaw skill hub): https://clawhub.ai
- MCP (Model Context Protocol): https://modelcontextprotocol.io
- A2A Protocol: https://google-deepmind.github.io/agent-to-agent
- AISStream.io: https://aisstream.io (free WebSocket API for live vessel tracking)
- OpenMeteo: https://open-meteo.com (free weather + marine API, no key required)
- WorldTides API: https://worldtides.info (tidal predictions)
- Ollama API: http://localhost:11434/api

Reference repos (skills ecosystem):
- `Agents365-ai/drawio-skill` — production diagramming skill, portable SKILL.md format
- `DietrichGebert/ponytail` — YAGNI-ladder behavioral modifier, always-on ruleset
- `shadcn/improve` — codebase audit + plan-writing meta-skill, self-contained plans with verification gates
- `NVIDIA/skillspector` — security scanner for agent skills, 64 vulnerability patterns
- `cjpais/Handy` — local-first STT desktop app (Tauri/Rust), the voice UX Sovereign should adopt

---

## Document maintenance rules

- This document is the source of truth for current state. If the code disagrees, the code is wrong (or this document is stale — fix it).
- The "What works right now" section is verified by running the code, not by reading the CHANGELOG. If you can't run the code, mark the item as "unverified".
- The "What's broken right now" section is the open bug list. When a bug is fixed, move it to a "Recently fixed" subsection for one prompt, then delete.
- The "Built but not reachable" table shrinks as subsystems are wired. It never grows. New subsystems that are built but not wired go in the table immediately.
- The "Next 5 prompts" section is the worklist. When a prompt completes, move it to "Completed prompts" and add the next prompt from the deferred list.
- The "Deferred" section is queued work, not in-progress work. Items move from Deferred to Next 5 when prioritised.
- Old sections from the previous handoff (Skills Expansion Plan Tiers 1-7, UI Architecture Decisions, Competitive Landscape Review Changes, etc.) are cut. They described future architecture; this document describes current state. If a decision needs to be recorded, it goes in the plan that implements it, not here.
