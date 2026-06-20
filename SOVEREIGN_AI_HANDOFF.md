# Sovereign AI Agent Framework — Project Handoff

**Last updated**: 2026-06-20 — post prompt-45, handoff amended by GLM session.

**Broad-except audit status (Rule 17)**: core/ ✅ (29 patterns, prompt-41), system/ ✅ (103 patterns, prompt-42+42.1), skills/ ✅ (219 patterns, prompt-43a+43b), web/ ✅ (10 patterns, prompt-43c), adapters/ ✅ (43 patterns, prompt-43c), gateways/ ✅ (5 patterns, prompt-43c). **All directories now fully compliant**.

**InputSanitiser wiring status (Rule 14)**: ✅ Fully wired (prompt-44). Sanitisation at all external-input entry points: HTTP/WebSocket (web/server.py), Telegram (gateways/telegram/gateway.py), Web Scraper (skills/web_scraper/skill.py), Orchestrator.submit_task() (defense-in-depth), QueryHandler.execute() (CLI/TUI).

**InputSanitiser defense status (Plan 45)**: ✅ Redesigned with real defense logic. Layered defense: Unicode normalisation, length truncation, injection tag stripping, HTML stripping, command injection stripping, prompt injection stripping. Backward compatible with test_security.py (BLOCKED_PATTERNS, is_clean, add_pattern preserved).

**TrajectoryExporter status (Plan 45)**: ✅ Functional. Uses MemoryRouter.fetch_by_type() to fetch completed tasks, filters by complexity_score, converts to ShareGPT format, writes JSONL. 6 previously skipped tests now passing.

**Test baseline**: 1167 passed, 55 skipped, 0 failed, 0 warnings (measured with `python -m pytest tests/ -q --tb=no`). Improvement: +33 passed, -6 skipped (Plan 45).

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
- **TUI slash commands** — `/help`, `/status`, `/clear`, `/exit`, `/model`, `/adapter`, `/theme` work. `/adapter` now supports 10 adapters: ollama, lm_studio, openai, cohere, groq, anthropic, mistral, together, deepseek, huggingface. Remaining 4 (llama_cpp, mcp, base) are special-purpose. `/adapter` now handles missing API keys gracefully with user-friendly error messages and helpful URLs (prompt-41).
- **Session manager** — in-memory mode works. Postgres persistence does not (see "What's broken").
- **Command history** — in-memory mode works. Postgres persistence does not.
- **Test suite** — 1127 tests pass, 61 skipped (24 integration + 37 existing), 0 warnings. Quality varies; some are smoke tests with `assert True` (see Process section).

**Adapter verification status** (as of prompt-40):
10 of 14 LLM adapters have test coverage as of prompt-40:
- Ollama: ✅ verified (prompt-38.7)
- LM Studio: ✅ verified (prompt-38.7.1)
- Groq: ✅ verified (prompt-39)
- Mistral: ⚠️ code correct, 4/6 integration tests passed, 2 failed due to rate limit (external issue) (prompt-40)
- Together: ⚠️ code correct, no API key provided for verification (prompt-40)
- DeepSeek: ⚠️ code correct, all 6 integration tests failed due to insufficient balance (external billing issue) (prompt-40)
- HuggingFace: ⚠️ code correct, all 6 integration tests failed due to DNS resolution error (network issue) (prompt-40)
- OpenAI: ⚠️ code correct, blocked by insufficient quota (prompt-39)
- Cohere: ⚠️ code correct, blocked by deprecated models (prompt-39)
- Anthropic: ⚠️ code correct, blocked by credit balance (prompt-38.7.1)
- Gemini: ⚠️ code correct, blocked by service outage (prompt-38.7.1)
- Remaining 3 (llama_cpp, mcp_adapter, base): special-purpose or working as intended

That's it. Everything else is either broken, unreachable, or aspirational.

---

## Test environment prerequisites

**Standard test measurement command**: `python -m pytest tests/ -q --tb=no `

**Integration tests**: Some tests require real services or API keys:
- `tests/test_lm_studio_adapter.py::test_health_check_with_server` — requires LM Studio running at http://localhost:1234/v1
- `tests/test_openai_adapter.py::TestOpenAIAdapterIntegration` — requires `OPENAI_API_KEY` env var (get at https://platform.openai.com/api-keys)
- `tests/test_cohere_adapter.py::TestCohereAdapterIntegration` — requires `COHERE_API_KEY` env var (get at https://dashboard.cohere.com/api-keys)
- `tests/test_groq_adapter.py::TestGroqAdapterIntegration` — requires `GROQ_API_KEY` env var (get at https://console.groq.com/keys)
- `tests/test_anthropic_adapter.py::TestAnthropicAdapterIntegration` — requires `ANTHROPIC_API_KEY` env var (get at https://console.anthropic.com/settings/keys)
- `tests/test_gemini_adapter.py::TestGeminiAdapterIntegration` — requires `GEMINI_API_KEY` env var (get at https://aistudio.google.com/app/apikey)
- `tests/test_mistral_adapter.py::TestMistralAdapterIntegration` — requires `MISTRAL_API_KEY` env var (get at https://console.mistral.ai/api-keys)
- `tests/test_together_adapter.py::TestTogetherAdapterIntegration` — requires `TOGETHER_API_KEY` env var (get at https://api.together.xyz/settings/api-keys)
- `tests/test_deepseek_adapter.py::TestDeepSeekAdapterIntegration` — requires `DEEPSEEK_API_KEY` env var (get at https://platform.deepseek.com/api_keys)
- `tests/test_huggingface_adapter.py::TestHuggingFaceAdapterIntegration` — requires `HUGGINGFACE_API_KEY` (or `HF_TOKEN`) env var (get at https://huggingface.co/settings/tokens)

Integration tests skip gracefully when prerequisites aren't available. Run them with prerequisites set to verify end-to-end behavior.

---



## What's broken right now

Open bugs, ordered by impact. Each has a verification step so the fix can be confirmed.

### F4 — `cli/serve.py` constructs 14 subsystems but registers zero workers
- **Location**: `cli/serve.py:148-155` constructs `WorkerFactory` but never calls it; no `orchestrator.register_worker(...)` anywhere in the file.
- **Cause**: 35.6b wired the cognition stack but forgot the worker. `submit_task()` calls `route_task()` which raises `WorkerNotFoundError("No workers registered")`.
- **Fix**: After constructing `WorkerFactory`, call it to create a default OllamaWorker and register it with the orchestrator. Or skip the factory and register an OllamaWorker directly (simpler, matches what `cli/tui.py:279-280` does).
- **Verification**: Start `jarvis serve`, hit `POST /api/tasks` with `{"intent": "test"}` — should return a real `task_id`, not `{"task_id": "", "status": "error"}`.

### F6 — MemoryRouter call-signature mismatch — CLOSED (prompt-37.5)

### F7 — Trace spam in CLI — CLOSED (prompt-38, WorkerBase default changed to MemoryTraceEmitter)

---

## Broad-except audit progress (Rule 17)

| Layer | Status | Patterns fixed | Prompt |
|---|---|---|---|
| `core/` | ✅ Rule 17 compliant | 29 | prompt-41 |
| `system/` | ✅ FULLY Rule 17 compliant | 103 (95 + 8) | prompt-42 + 42.1 |
| `skills/` | ✅ FULLY Rule 17 compliant | 219 (100 + 119) | prompt-43a + 43b |
| `web/`, `adapters/`, `gateways/` | ❌ Not started | TBD | Plan 43c (next) |

**351 broad-except patterns eliminated across core/ + system/ + skills/.** One known exception: audio_capture.py's sync `close()` method uses inline comment only (can't emit async WARNING trace from sync method).

**Key lesson**: Use `-match "pass"` (catches `pass # comment`) for grep, NOT `pass$` (misses commented pass lines). Learned the hard way in prompt-42 when Devin found 16 violations that GLM's grep missed.

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
| MCPServer | `skills/mcp_server.py` | Built but never started |
| MCPAdapter | `adapters/mcp_adapter.py` | Built but never constructed |

When the next prompt wires one of these into a runtime entry point, remove it from this table. The table should shrink over time, not grow.

---

## What's deferred (not started)

These are real product features that the plan calls for but no code exists for. They are not "in progress" — they are queued. Listed in priority order.

1. **Marine stack** (Prompts 28.7, 31.5 in old plan) — weather, marine_weather, AIS, tidal, passage_planner, vhf_monitor, satellite_comms. Zero lines of code exist. This is the moat. Should ship as portable SKILL.md files (see Skills Ecosystem section).
2. **Sandboxed execution** for `skills/terminal/` and `skills/code_execution/`. Currently runs subprocesses on host with no isolation. OpenHands ships Docker sandboxing by default; Sovereign has nothing.
3. **Streaming output** from Ollama through the worker pipeline to the TUI/Web GUI. Every cloud coding agent streams tokens; Sovereign waits for the full response.
4. **Function-calling / tool-use loop.** Modern agent frameworks let the LLM decide which skills to call. Sovereign's "route once, generate once" model is a generation behind.
5. **Deployment story.** Docker compose with Postgres + Qdrant + Jarvis + Ollama. systemd unit / Windows service. Without this, "Jarvis that runs in the background" has no delivery path.
6. **Eval harness.** A held-out task suite to measure whether self-improvement is actually happening. Without this, "self-improving" is an assertion.
7. **Plan mode.** Agent proposes a plan, user approves, agent executes. Table stakes for agentic coding in 2026.

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

1. Run full test suite: `python -m pytest tests/ -v`. Confirm zero new failures.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors.
4. `git add . && git commit -m "checkpoint: prompt-{N}" && git tag prompt-{N}`
5. `git show prompt-{N} --stat` — verify file list contains only files in this plan. If unexpected file appears, `git tag -d prompt-{N}`, clean, re-tag.
6. Update `CHANGELOG.md` (append-only) with: Files Modified (per-file detail), Implementation Notes (mid-prompt failures and how resolved), Testing Results (baseline → final, with command), Verification Gate Output (literal output of each gate). **Per-step CHANGELOG entries required**: after each step, append a CHANGELOG entry documenting what was done, what failed (if anything), and how it was resolved. Do not batch all entries into a single summary at the end. Earlier prompts had per-step entries and were more verbose — that was better.
7. Update this handoff: move the completed plan from "Next 5 prompts" to "Completed prompts" table. Update "What's broken" section (remove fixed items). Update "Built but not reachable" table (remove newly-wired subsystems). **Refill the "Next 5 prompts" queue**: when a plan completes, add the next plan from the deferred list so the queue always has 5 entries.
8. **Update `global_rules.md`** when a new recurring mistake pattern or landmine is identified in this prompt. Rules are behavioral guardrails (not memories) and should be kept current. Add a new step to the plan if needed. Do not cite global_rules.md as authority — it is Devin-local and unreachable for verification — but keeping it current improves Devin's behavior.
9. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
10. `git push origin master && git push origin prompt-{N}`

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
- **Devin memories are not authoritative** (post-prompt-38.7 policy change). All Devin memories were deleted; new memories are added only when GLM/user explicitly requests via a plan step. Any plan or report that cites "per memory X" or "Mistake Pattern N" (where N is a Devin-memory concept, not a handoff recurring-mistake pattern) is a Rule 19 violation — the citation is unverifiable. All workarounds, methodologies, and constraints must live in the handoff or the plan itself.
- **Test count assertions without measurement** (prompt-39, prompt-40, prompt-41 had this). Devin sometimes asserts test counts (e.g., "~1124 passed, 0 warnings") without actually measuring, copying from prior prompt baselines instead. This has occurred in chat reports, CHANGELOG entries, and handoff updates. The actual measurement may differ (e.g., prompt-41 claimed ~1124/0 warnings but actual was 1127/0 warnings). Rule 19 requires literal evidence — always paste the `Select-Object -Last 3` output of `python -m pytest tests/ -q --tb=no` as proof of the count, never assert from memory or copy from prior prompts.
- **"No interactive shell" used as skip reason when programmatic verification was provided** (prompt-38.6 had this — Devin deferred Track A citing "no interactive shell" when the plan provided programmatic verification commands). If the plan gives you commands to run, run them. Do not substitute "manual verification" reasoning for executing the provided commands.
- **Scope creep via "necessary" model updates** (prompt-39 had this — Devin unilaterally updated model names in adapter code while adding tests). When tests reveal production code issues, STOP and report. Do not silently fix them outside the plan's scope. The plan author decides whether to expand scope.
- **Broader grep for broad-except patterns** (learned in prompt-42). GLM's original `pass$` grep missed `pass # comment` patterns. Devin's `-match "pass"` caught them. Always use the broader grep that catches `pass` anywhere after `except Exception`, not just at end of line.

---

## Completed prompts (detail)

### Plan 41 — Broad-except audit, part 1 (core/) — COMPLETED
- **Priority**: P1
- **Effort**: M
- **Why**: Architecture Rule 17 violation: dozens of `except Exception: pass` blocks without trace events. These hide real failures and are the single most common source of "dead wiring" findings. Addresses TUI `/adapter` ValueError handling that Plan 39's comment referenced.
- **Scope**: Audit `core/` for broad `except Exception` blocks. For each: either (a) add a trace event at WARNING level with the exception message, or (b) narrow the exception type to what's actually expected, or (c) if the exception is truly ignorable, add an inline comment explaining why.
- **Verification**: `Select-String -Path core\ -Pattern "except Exception" -Recurse` returns zero hits (or only hits with inline comments and trace events).
- **Result**: Fixed 37 broad-except patterns across 5 files: orchestrator (12), approval_gate (13), task_state_machine (7), memory_router (4), worker_base (1). All now have inline comments + WARNING trace events per Rule 17. Fixed TUI /adapter ValueError handling with user-friendly error messages and API key URLs. Added Devin chat report test counts landmine to handoff.

### Plan 42 — Broad-except audit, part 2 (system/) — COMPLETED
- **Priority**: P1
- **Effort**: L
- **Why**: Same as Plan 41, but for `system/` directory. Found 95 violations across 9 files.
- **Result**: Fixed 95 broad-except patterns across 9 files. Rule 17 clarification: inline comment alone is NOT sufficient; pass must be replaced with WARNING trace event. Additional violations found in audio_capture.py (3) and model_evaluator.py (5) — outside Plan 42 scope, fixed in Plan 42.1.

### Plan 42.1 — Remaining system/ broad-except patterns — COMPLETED
- **Priority**: P1
- **Effort**: S
- **Result**: Fixed 8 broad-except patterns (audio_capture: 3, model_evaluator: 5). system/ is now FULLY Rule 17 compliant — 103 patterns total (95 from prompt-42 + 8 from prompt-42.1). Note: audio_capture.py close() method is synchronous, so one pattern uses inline comment only.

### Plan 43a — Broad-except audit, part 3 (skills/) — COMPLETED
- **Priority**: P1
- **Effort**: L (split from Plan 43 due to total count exceeding 200)
- **Why**: Same as Plan 41, but for `skills/` directory. Total violations across skills/: 219. Split into 43a (files with 20+ violations) and 43b (files with <20 violations).
- **Scope**: Audit skills/ files with 20+ violations for broad `except Exception` blocks. Apply same three-option fix pattern.
- **Files**: notes/notes_skill.py (46 violations), calendar/calendar_skill.py (30 violations), reminder/reminder_skill.py (24 violations).
- **Verification**: `Select-String -Path skills\notes\notes_skill.py, skills\calendar\calendar_skill.py, skills\reminder\reminder_skill.py -Pattern "except Exception" -Context 0,1 | Where-Object { $_.Context.PostContext -match "pass" -and $_.Context.PostContext -notmatch "#" }` returns zero hits.
- **Result**: Fixed 100 broad-except patterns across 3 files. All violations were cleanup paths (trace emission failure and event loop timing failure). Added inline comments per Rule 17. Test suite unchanged: 1127 passed, 61 skipped, 0 failed, 0 warnings.

### Plan 43b — Broad-except audit, part 3 (skills/ - remainder) — COMPLETED
- **Priority**: P1
- **Effort**: M
- **Why**: Same as Plan 43a, but for the remaining 18 skills/ files with <20 violations each (total 119 violations remaining).
- **Scope**: Audit remaining skills/ files for broad `except Exception` blocks. Apply same three-option fix pattern.
- **Files**: calculator (6), clipboard (6), code_execution (6), docker (10), email (16), file_reader (3), file_writer (4), git (14), home_assistant (6), http_client (8), pdf (8), screenshot (2), spreadsheet (10), terminal (6), transcription (3), tts (3), web_scraper (2), web_search (6).
- **Verification**: `Select-String -Path skills\ -Pattern "except Exception" -Recurse` returns zero hits (or only hits with inline comments and trace events).
- **Result**: Fixed 119 broad-except patterns across 18 files. All violations were cleanup paths (trace emission failure and event loop timing failure). Added inline comments per Rule 17. Test suite unchanged: 1127 passed, 61 skipped, 0 failed, 0 warnings.

### Plan 43c — Broad-except audit, part 4 (web/, adapters/, gateways/) — COMPLETED
- **Priority**: P1
- **Effort**: M
- **Why**: Architecture Rule 17 violation: core/, system/, and skills/ are now fully compliant, but web/, adapters/, and gateways/ have not been audited. The same broad `except Exception: pass` patterns that hid dead wiring in core/ and system/ likely exist here too.
- **Scope**: Audit `web/`, `adapters/`, and `gateways/` for broad `except Exception` blocks. Apply same three-option fix pattern as Plans 41-43b. Use the broader grep (`-match "pass"`) that catches `pass # comment` patterns — learned the hard way in prompt-42.
- **Files**: web/server.py (10), web/middleware/auth_middleware.py (1), adapters/anthropic.py (3), adapters/cohere.py (4), adapters/deepseek.py (4), adapters/groq.py (4), adapters/huggingface.py (4), adapters/lm_studio.py (4), adapters/mistral.py (4), adapters/openai.py (4), adapters/together.py (4), adapters/gemini.py (1), adapters/llama_cpp.py (2), adapters/ollama.py (5), gateways/telegram/gateway.py (5).
- **Verification**: `Select-String -Path web\,adapters\,gateways\ -Pattern "except Exception" -Recurse` returns zero hits (or only hits with inline comments and trace events).
- **Result**: Fixed 59 broad-except patterns across 15 files: 44 pass, 14 return-fallback, 1 continue. All now have WARNING trace/logging before pass/return/continue. Followed each file's existing logging convention (logging.warning() for sync contexts, await self._emitter.emit(TraceEvent(...)) for async contexts, print() for sync method). Fixed one missed return-fallback in adapters/ollama.py health_check during verification. Test suite unchanged: 1127 passed, 61 skipped, 0 failed, 0 warnings.

### Plan 44 — InputSanitiser wiring — COMPLETED
- **Priority**: P1
- **Effort**: M
- **Why**: Architecture Rule 14 violation: InputSanitiser is built but never invoked from any external-input code path (web scraper, Telegram inbound, user task input). This is a security vulnerability.
- **Scope**: Wire InputSanitiser into all external-input entry points: HTTP/WebSocket (web/server.py), Telegram (gateways/telegram/gateway.py), Web Scraper (skills/web_scraper/skill.py), Orchestrator.submit_task() (defense-in-depth), QueryHandler.execute() (CLI/TUI). Also updated CLI entry points (cli/serve.py, cli/tui.py, cli/rich_cli.py) to construct and pass InputSanitiser.
- **Verification**: All entry points call InputSanitiser before content enters LLM context. Integration tests added to verify wiring (7 tests in TestInputSanitiserWiring).
- **Result**: InputSanitiser wired into 5 external-input entry points. Defense-in-depth strategy: boundary sanitisation (HTTP/WebSocket, Telegram, Web Scraper) + sink sanitisation (Orchestrator.submit_task()) + CLI/TUI sanitisation (QueryHandler.execute()). Dependency injection pattern used throughout. Test suite: 1134 passed, 61 skipped, 0 failed, 0 warnings.

---

## Next 5 prompts

Ordered. Each is one plan. Do not start Plan N+1 until Plan N's verification gates pass.

### Plan 45 — InputSanitiser redesign + trajectory_exporter functional redesign
- **Priority**: P2
- **Effort**: L
- **Why**: Current InputSanitiser is trivially bypassable — 10 hardcoded literal strings with naive `str.replace`, no HTML stripping, no command injection prevention, no length limits. Also, trajectory_exporter has 6 skipped tests deferred from prompt-37.5 that need a real `fetch(Type, filter_func=...)` implementation or the current Option 2 stub needs to be replaced with working code.
- **Scope**: Implement actual sanitization logic in `core/input_sanitiser.py` (HTML stripping, command injection prevention, length limits, regex-based pattern matching instead of hardcoded strings). Fix trajectory_exporter's `fetch(Type, filter_func=...)` pattern to work with MemoryRouter's actual API. Un-skip the 6 deferred tests.
- **Verification**: `python -m pytest tests/test_input_sanitiser.py -v` passes. `python -m pytest tests/test_trajectory_exporter.py -v` — all 6 previously-skipped tests now pass.

### Plan 46 — ruff triage
- **Priority**: P2
- **Effort**: M
- **Why**: 365 ruff errors, 271 auto-fixable with `ruff check . --fix`. Also catches `except Exception as e:` swallowing patterns not verified by the broad-except audit gates. CI will never pass until these are cleared.
- **Scope**: Run `ruff check . --fix` for auto-fixable errors. Manually triage the remaining ~94 errors. Ensure no auto-fix breaks tests.
- **Verification**: `ruff check .` returns zero errors. Full test suite still passes.

### Plan 47 — mypy triage
- **Priority**: P2
- **Effort**: M
- **Why**: 116 mypy errors. CI will never pass until these are cleared. Many are likely import errors or missing type annotations that are straightforward to fix.
- **Scope**: Run `mypy . --ignore-missing-imports` and fix all errors. Add return type annotations where missing (Rule 9). Ensure no fix breaks tests.
- **Verification**: `mypy . --ignore-missing-imports` returns zero errors. Full test suite still passes.

### Plan 48 — Fix F4: `cli/serve.py` constructs 14 subsystems but registers zero workers
- **Priority**: P1
- **Effort**: S
- **Why**: `cli/serve.py` constructs `WorkerFactory` but never calls it; no `orchestrator.register_worker(...)` anywhere in the file. `submit_task()` calls `route_task()` which raises `WorkerNotFoundError("No workers registered")`. This breaks the web server's task submission endpoint.
- **Scope**: After constructing `WorkerFactory` in `cli/serve.py`, call it to create a default OllamaWorker and register it with the orchestrator. Or skip the factory and register an OllamaWorker directly (simpler, matches what `cli/tui.py:279-280` does).
- **Verification**: Start `jarvis serve`, hit `POST /api/tasks` with `{"intent": "test"}` — should return a real `task_id`, not `{"task_id": "", "status": "error"}`.

### Plan 49 — Marine stack (weather, AIS, tidal, passage_planner, vhf_monitor, satellite_comms)
- **Priority**: P2
- **Effort**: L
- **Why**: This is the moat — the domain-specific capability that differentiates Sovereign from generic AI assistants. Zero lines of code exist for marine features.
- **Scope**: Implement marine stack as portable SKILL.md files installable into Claude Code, Cursor, Codex, and Sovereign. Start with weather and AIS as highest-value features.
- **Verification**: SKILL.md files load and execute correctly in Sovereign. Integration tests pass for each marine skill.

---

## After Plan 49 — Decision point

Once Plans 45-49 land, the foundation is solid: InputSanitiser redesigned and robust, trajectory_exporter functional, static analysis clean, web server workers registered, marine stack started. At that point, choose:

**Option A: Build the marine stack next.** This validates the moat. Ship as portable SKILL.md files (see Skills Ecosystem section) so the marine capability reaches users of Claude Code, Cursor, Codex, *and* Sovereign. Building 5 small skills (weather, marine_weather, AIS, tidal, passage_planner) would tell you whether LLM-driven passage planning is actually useful as a product.

**Option B: Wire the existing cognition stack into `cli/serve.py` end-to-end.** This makes Sovereign a "self-improving" agent as advertised. Requires wiring WorkerFactory + RatingSystem + InstructionVersionManager + OutputEvaluator into a working loop with a real evaluation harness. Without an eval harness, "self-improving" is unverifiable.

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
12. No global mutable state. (Known violations: `_global_registry` in `core/commands.py:155`, `_global_emitter` in `core/observability.py:502`. Both have self-acknowledged comments. Removal deferred — requires DI refactor of TraceEmitter/CommandRegistry construction.)
13. All I/O operations are async.
14. `InputSanitiser` MUST be called on all externally-sourced content before it enters LLM context: web scraper output, Telegram inbound, user task input. **Currently violated in all three locations** — see "Built but not reachable" table.
15. `ApprovalTrustRegistry` MUST be consulted by `ApprovalGate` before raising any approval request.
16. Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes. No unauthenticated endpoints except `/health`.
17. No broad `except Exception: pass` without an inline comment explaining why the exception is intentionally swallowed. Every swallowed exception must emit a trace event at WARNING level. **Current compliance**: core/ ✅ (29 patterns, prompt-41), system/ ✅ (103 patterns, prompt-42+42.1), skills/ ✅ (219 patterns, prompt-43a+43b). web/, adapters/, gateways/ still pending (Plan 43c). **Grep lesson**: use `-match "pass"` (catches `pass # comment`), NOT `pass$` (misses commented pass lines) — learned the hard way in prompt-42.
18. Tests change with code. When you modify production code, you MUST update the corresponding test file(s) in the same step. Run the specific test file after each production file change. The full test suite MUST pass (green) before tagging. Tagging with a red test suite is forbidden.
19. **Execute steps and gates in listed order. Do not mark a step or gate complete until its producing work is done and its evidence exists.** If a gate's evidence requires output from a later step, the plan is out of order — STOP and report. Gate output must be pasted literally into the CHANGELOG; "PASSED" without evidence is forbidden. Specifically:
    - Do not mark a gate PASSED before running it. "I will run it later" is not acceptable.
    - Do not mark a gate PASSED if its producing step is incomplete. The gate exists to verify the step's output.
    - Do not mark a gate SKIPPED unless the plan explicitly allows skipping it. "Manual verification" is not a skip reason — if the plan calls for manual verification, do the manual verification and paste the result.
    - Do not mark a test `@pytest.mark.skip` for tests that "couldn't be mocked." Fix the mock or refactor the SUT. `pytest.skip` is for known-broken behavior with a Plan-N deferral, NOT for tests that were written but couldn't be made to run.
    (Currently violated by prompt-37.6: Gate 3 marked PASSED with no output, Gate 5 and Gate 6 marked SKIPPED without being skipped per plan, 8 tests marked `@pytest.mark.skip` because mocking was hard. Plan 37.6.1 fixes this and codifies the rule.)

---

## Dependency injection rules

- `TraceEmitter` and `CommandRegistry` constructed ONCE in `cli/main.py` and passed down. (Currently violated — `cli/main.py` is a thin dispatcher and doesn't construct these. Deferred until after Plans 43c-47.)
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
| 38.7.1 | Clean baseline — Gemini migration, LM Studio test fix, adapter verification | 1089 | Gemini SDK migration (google.generativeai → google.genai), fixed LM Studio test (mocked unit test + integration test), converted Anthropic/Gemini adapter unit tests to mocked (10 unit tests now run without API keys), verified trajectory_exporter skips still legitimate (6 Plan 45 deferrals), cleaned up requirements.txt (removed duplicate llama-cpp-python, fixed spacing, updated google-genai). Test baseline: 1089 passed, 19 skipped (13 integration tests + 6 Plan 45), 0 warnings. Adapter verification: Ollama ✅, LM Studio ✅, Anthropic ❌ (insufficient credit), Gemini ❌ (service unavailable). |
| 41 | Broad-except audit, part 1 (core/) | 1127 | Fixed 37 broad-except patterns across 5 files: orchestrator (12), approval_gate (13), task_state_machine (7), memory_router (4), worker_base (1). All now have inline comments + WARNING trace events per Rule 17. Fixed TUI /adapter ValueError handling with user-friendly error messages and API key URLs. Added Devin chat report test counts landmine to handoff. |
| 41 fix-up | Test baseline correction + warning investigation | 1127 | Corrected test baseline in CHANGELOG and handoff to actual measurement (1127 passed, 61 skipped, 0 warnings). Removed --ignore flag from standard measurement command. Investigated warning: found pre-existing ResourceWarnings about unclosed files in calendar_skill.py and asyncio/subprocess — not related to broad-except refactoring. Reframed landmine to capture "assertion without measurement" pattern. |
| 42 | Broad-except audit, part 2 (system/) | 1127 | Fixed 95 broad-except patterns across 9 files: resource_manager (39), model_acquisition (11), profiler (10), model_registry (12), monitor_daemon (9), voice_daemon (5), trajectory_exporter (1), retention_manager (6), retention_daemon (2). All now have WARNING trace events per Rule 17 (not just inline comments). Additional violations found in audio_capture.py (3 patterns) and model_evaluator.py (5 patterns) - outside Plan 42 scope, to be addressed in future plan. All system tests pass. |
| 42.1 | Fix-up — remaining system/ broad-except patterns | 1127 | Fixed 8 broad-except patterns across 2 files: audio_capture (3), model_evaluator (5). All now have WARNING trace events per Rule 17. system/ is now FULLY Rule 17 compliant — zero except Exception: pass patterns across ALL system/ files (103 patterns total: 95 from prompt-42 + 8 from prompt-42.1). Note: audio_capture.py close() method is synchronous, so one pattern uses inline comment only (cannot emit async trace event). Test baseline unchanged: 1127 passed, 61 skipped, 0 failed, 0 warnings. |
| 43a | Broad-except audit, part 3a (skills/ - 20+ violations) | 1127 | Fixed 100 broad-except patterns across 3 files: notes_skill (46), calendar_skill (30), reminder_skill (24). All violations were cleanup paths (trace emission failure, event loop timing failure). Added inline comments per Rule 17. Test suite unchanged. |
| 43b | Broad-except audit, part 3b (skills/ - remainder) | 1127 | Fixed 119 broad-except patterns across 18 files (calculator: 6, clipboard: 6, code_execution: 6, docker: 10, email: 16, file_reader: 3, file_writer: 4, git: 14, home_assistant: 6, http_client: 8, pdf: 8, screenshot: 2, spreadsheet: 10, terminal: 6, transcription: 3, tts: 3, web_scraper: 2, web_search: 6). skills/ is now FULLY Rule 17 compliant — 219 patterns total (100 from 43a + 119 from 43b). Test suite unchanged. |
| 43c | Broad-except audit, part 4 (web/, adapters/, gateways/) | 1127 | Fixed 59 broad-except patterns across 15 files: web/ (11), adapters/ (43), gateways/ (5). Pattern types: 44 pass, 14 return-fallback, 1 continue. All now have WARNING trace/logging before pass/return/continue. Followed each file's existing logging convention. Test suite unchanged. All directories now fully Rule 17 compliant. |

---

## Recurring mistake patterns

Six patterns account for ~90% of the mistakes in the CHANGELOG.

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
- **Local fine-tuning**: Karpathy's `autoresearch` is relevant to the "train my own workers" goal. Adapt for QLoRA fine-tuning on 6GB RTX 3060 — feasible with 4-bit quantization and LoRA adapters. This is deferred until after Plans 43c-47 but should not be forgotten.

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
