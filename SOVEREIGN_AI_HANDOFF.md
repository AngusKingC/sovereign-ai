# Sovereign AI Agent Framework — Project Handoff

**Last updated**: 2026-06-20 — post prompt-49b + comprehensive review + L16/L17 landmines + Rule 21 (mandatory closing steps), handoff amended by GLM session 11. Plan numbering restructured based on scan findings. CHANGELOG append procedure updated with temp-file pattern (L15). Bandit exclude list codified (L14). Baseline-capture methodology codified (L13). Pydantic Field(default=None) pattern codified (L16). Mandatory closing steps + tag-push gate enforcement codified (L17, Rule 21).

**Broad-except audit status (Rule 17)**: core/ ✅ (29 patterns, prompt-41), system/ ✅ (103 patterns, prompt-42+42.1), skills/ ✅ (219 patterns, prompt-43a+43b), web/ ✅ (10 patterns, prompt-43c), adapters/ ✅ (43 patterns, prompt-43c), gateways/ ✅ (5 patterns, prompt-43c). **All directories now fully compliant**.

**InputSanitiser wiring status (Rule 14)**: ✅ Fully wired (prompt-44) + ✅ Implementation redesigned with 6-layer defense (prompt-45). Sanitisation at all external-input entry points: HTTP/WebSocket (web/server.py), Telegram (gateways/telegram/gateway.py), Web Scraper (skills/web_scraper/skill.py), Orchestrator.submit_task() (defense-in-depth), QueryHandler.execute() in core/handlers.py (CLI/TUI).

**Test baseline**: 1166 passed, 55 skipped, 1 pre-existing failure (calendar_skill — hardcoded test date `20260620T140000Z` is now in the past; fix in Plan 53), 0 warnings (measured with `python -m pytest tests/ -q --tb=no` on Windows with all deps). Linux scan env (no adapter SDKs): 1087 passed, 1 skipped, 2 env-only failures (postgres + pdfplumber).

**Static analysis baseline (post-prompt-50)**:
- Ruff: 358 errors (unchanged — Plan 50 was test-only)
- Mypy: 309 errors (was 435 — Plan 49 fixed ~108, Plan 49b fixed ~32, Plan 50 fixed ~127)
- Bandit: 22 medium+ (unchanged — B108 in tests, deferred to Plan 53)
- pip-audit: 55 CVEs across 14 packages (deferred to Plan 56)
- Vulture: 47 high-confidence findings (deferred to Plan 57)

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

## Plan numbering restructure (2026-06-20)

The 2026-06-20 full repo scan revealed 3 categories of issues the pre-scan audit didn't catch (security, dependency CVEs, dead code) and showed the mypy count was 567, not 180 (requiring the original Plan 48 to be split into 4 sub-plans). Rather than use letter-suffixed plans (48a/48b/48c/48d) which would collide with the existing prompt-NN tag namespace, all plans were renumbered in execution order.

**Old numbering → New numbering**:
| Old | New | What it does |
|---|---|---|
| 45 | 45 | InputSanitiser redesign + trajectory_exporter (DONE) |
| 46 | 46 | F821 + F811 + critical F841 cleanup (DONE) |
| 47 | 47 | E402 + gateways/__init__.py + flagged unused imports (DONE) |
| (new) | **48** | Security: B608 SQL injection + B104 suppression + bandit/pip-audit/vulture in CI |
| 48 | **49** | ApprovalGate API drift + ApprovalRequest field additions (~112 mypy errors) |
| (48 split) | **50** | MockMemoryRouter inheritance fix (107 mypy errors, test-only) |
| (48 split) | **51** | Adapter type fixes + `del e` patterns (27 mypy errors) |
| (48b in audit) | **52** | F4 wiring fix (cognition-loop components into serve request path) |
| 49 | **53** | Test suite health + 22 B108 fixes |
| 50 | **54** | F401 bulk cleanup (247 remaining) |
| 51 | **55** | Marine stack (the moat — deferred until after audit cleanup) |
| (new) | **56** | Dependency updates + diskcache migration |
| (new) | **57** | Dead code cleanup (47 vulture findings) |

**Next 5 prompts queue** (post-prompt-47): Plans 48, 49, 50, 51, 52.
**Deferred**: Plans 53, 54, 55, 56, 57.

**Tooling additions (effective Plan 48)**:
- **bandit** — security scan (SQL injection, hardcoded binds, eval, shell=True). CI job: `bandit -r . -ll --exclude tests/` (tests/ excluded until Plan 53 fixes B108).
- **pip-audit** — dependency CVE scan. CI job: `pip-audit --strict` (continue-on-error: true until Plan 56 fixes diskcache + pip).
- **vulture** — dead code detection. CI job: `vulture . --min-confidence 80` (continue-on-error: true until Plan 57 fixes 47 findings).
- **ruff + mypy + pytest** — unchanged, already in CI.

These 3 new tools catch what ruff + mypy miss: the 2 B608 SQL injection findings in `memory/postgres.py` would have been caught by bandit on the original PR that introduced them.

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

### F8 — 2× B608 SQL injection in memory/postgres.py (FOUND BY 2026-06-20 SCAN)
- **Location**: `memory/postgres.py:121` (SELECT), `memory/postgres.py:237` (INSERT).
- **Cause**: `self.table_name` interpolated via f-string into SQL. Values ($1, $2, $3) are parameterized correctly, but the table name is not (PostgreSQL doesn't support parameterized identifiers).
- **Fix**: Plan 48 Step 1 validates `table_name` against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$` at construction time, making the f-string interpolation safe.
- **Verification**: `bandit memory/postgres.py -ll` returns 0 medium+ findings after Plan 48.

### F9 — 55 dependency CVEs across 14 packages (FOUND BY 2026-06-20 SCAN, REVISED 2026-06-20 post-prompt-48 S3 fire)
- **Packages affected**: aiohttp, chromadb, cryptography, diskcache, idna, pillow, pygments, pypdf, pytest, python-dotenv, python-multipart, setuptools, starlette, urllib3.
- **diskcache 5.6.3**: CVE-2025-69872 (no fix available). Investigate usage in Plan 48 Step 3; if directly used, defer to Plan 56.
- **pip 25.0.1**: 5 CVEs (PYSEC-2026-196, CVE-2025-8869, CVE-2026-1703, CVE-2026-3219, CVE-2026-6357). Environmental — upgrade pip in dev venv. CI uses GitHub's setup-python which provides a recent pip.
- **Other 12 packages**: ~48 CVEs total. All deferred to Plan 56 (dependency updates).
- **Note**: the original 2026-06-20 scan reported only 6 CVEs because the scan environment had a partial requirements.txt install. Devin's Windows env with full deps shows 55 CVEs across 14 packages. Plan 48 captures the actual count at plan-start and defers all fixes to Plan 56.

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
| TrajectoryExporter | `system/trajectory_exporter.py` | ✅ Functional as of prompt-45 (Plan 45 Step 4 replaced stub with working implementation using `MemoryRouter.fetch_by_type()`). Still not reachable from `jarvis` or `jarvis serve` — wiring deferred to Plan 52 (F4 wiring fix). |
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
6. Update `CHANGELOG.md` (append-only) with a **SIMPLIFIED** entry. The CHANGELOG is a permanent, scannable record — not a narrative. Keep it short:
   ```
   ## YYYY-MM-DD HH:MM — prompt-{N}
   
   **Plan**: <one-line plan title>
   
   **Changed**:
   - <file>: <what changed (1 line)>
   - <file>: <what changed>
   
   **Results**:
   - Mypy: <before> → <after>
   - Tests: <count> passed, <count> skipped, <count> failed
   - Tag: prompt-{N} verified on origin
   ```
   Do NOT include: commands run, errors encountered, Devin's thinking, attempted solutions, literal output, or time taken. That goes in the execution log (below).

7. **Execution log (temporary, verbose, reviewed between prompts)**: at the START of each prompt, create `C:\Jarvis\scan\execution-log-prompt-{N}.md`. Write EVERYTHING to this file during execution:
   - Every command run and its output (literal paste)
   - Every error, failure, or unexpected result
   - Every STOP condition that fired and how it was resolved
   - Devin's thinking: why an approach was chosen, what alternatives were considered
   - Attempted solutions: "I tried X but it failed because Y, so I switched to Z"
   - Time taken per step (rough estimates — identifies bottlenecks)
   - **Issues to flag for next prompt**: anything that should be addressed in the next plan (e.g. "mypy . took 3 minutes — use file-scoped", "calendar test still failing — needs Plan 53", "found DI violation in gemini.py — add to Plan 51")
   
   At the END of the prompt (during closing steps), this file is reviewed by the user/GLM, issues are extracted for the next plan, and the file is **deleted**. The next prompt starts with a fresh execution log. This keeps the CHANGELOG clean while preserving the verbose audit trail for review.
8. Update this handoff: move the completed plan from "Next 5 prompts" to "Completed prompts" table. Update "What's broken" section (remove fixed items). Update "Built but not reachable" table (remove newly-wired subsystems). **Refill the "Next 5 prompts" queue**: when a plan completes, add the next plan from the deferred list so the queue always has 5 entries.
9. **Update `global_rules.md`** when a new recurring mistake pattern or landmine is identified in this prompt. Rules are behavioral guardrails (not memories) and should be kept current. Add a new step to the plan if needed. Do not cite global_rules.md as authority — it is Devin-local and unreachable for verification — but keeping it current improves Devin's behavior.
10. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
11. `git push origin master && git push origin prompt-{N}`

**CHANGELOG append procedure** (PowerShell — simplified format, post-prompt-50):
- CHANGELOG entries are now **SIMPLIFIED** (~10 lines per plan). See closing step 6 for the format. Do NOT write verbose narratives to the CHANGELOG — that goes in the execution log (step 7).
- For the simplified entries (~10 lines), `Add-Content` with a here-string is acceptable since entries are short. Use `-Encoding utf8` on BOTH `Get-Content` and `Add-Content` to prevent mojibake (L15).
- For entries >20 lines (rare with the simplified format), use the temp-file pattern:
  ```powershell
  $entry | Out-File -FilePath C:\Jarvis\scan\changelog-entry.md -Encoding utf8
  $before = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Get-Content C:\Jarvis\scan\changelog-entry.md -Encoding utf8 | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
  $after = [System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count
  Write-Host "Before: $before, After: $after"
  Remove-Item C:\Jarvis\scan\changelog-entry.md
  ```
- **`-Encoding utf8` is MANDATORY** on both `Get-Content` and `Add-Content`. Without it, PowerShell defaults to Windows-1252, which corrupts em-dashes and produces control characters (L15, prompt-38.7.1/prompt-40 corruption root cause).
- Line count verification: `[System.IO.File]::ReadAllLines(r"C:\Jarvis\CHANGELOG.md").Count` before and after. NEVER use `Get-Content | Measure-Object` (truncates large files).

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
- **Round 3+**: Continue review rounds as long as findings are surfaced. There is **no cap** on the number of revision rounds — go to REV4, REV5, REV6, or however many it takes until Claude returns a clean PLACE verdict with zero findings. Each round: upload the latest REV diff + the original context brief. Do not re-review unchanged sections from prior rounds. The plan is not placed until Claude returns PLACE with zero findings OR the user explicitly overrides and accepts the residual findings.

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
- **Hardcoded baseline counts from incomplete scans (L13, prompt-48 REV3)**: the 2026-06-20 full repo scan ran on Linux with a partial `requirements.txt` install, so pip-audit reported 6 CVEs instead of the real 55. Plan 48 (REV1) hardcoded "6 CVEs" as the expected baseline, causing S3 to fire on Devin's Windows env. Fix: plans must CAPTURE actual counts at plan-start (Step 0) and use them as baselines, not predict counts from prior scans. STOP conditions should fire on "tool can't run" or "in-scope finding missing", not on "count differs from hardcoded number".
- **Bandit scanning venv directories (L14, prompt-48 REV4)**: `bandit -r .` scans `.venv/`/`venv/`/`env/`/`.tox/` directories (thousands of third-party Python files with their own security findings). Plan 48's original scan ran on a clean clone with no in-repo venv → 26 findings. Devin's Windows env has a venv in `C:\Jarvis\` → 820 findings. Fix: ALL `bandit -r .` commands MUST use `--exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache`. Single-file commands (`bandit <file.py>`) don't need excludes.
- **PowerShell here-strings + `Add-Content` hang on large entries (L15, prompt-48.1)**: the `@" ... "@` here-string requires the closing `"@` at column 1 with zero leading whitespace; if auto-indented by the editor or mis-pasted, PowerShell waits forever for more input (Plan 48 Step 3 hung on this). Additionally, `Add-Content` with very long `-Value` is slow + file-lock-prone on 7000+ line CHANGELOG files. Fix: for CHANGELOG entries >20 lines, write to a temp file first (`$entry | Out-File -FilePath C:\Jarvis\scan\changelog-entry.md -Encoding utf8`), then append with `Get-Content C:\Jarvis\scan\changelog-entry.md | Add-Content -Path C:\Jarvis\CHANGELOG.md`. Verify with `[System.IO.File]::ReadAllLines(...).Count` before and after (use a floor — e.g., if entry is ~80 lines, verify increase ≥60 to catch truncation). The temp-file pattern avoids both the here-string parsing issue and the `Add-Content` file-lock deadlock. For entries ≤20 lines, `Add-Content -Value @"..."@` is still acceptable IF the closing `"@` is at column 1 — but the temp-file pattern is always safer. **Truncation-floor lesson (prompt-48.1 REV3)**: when setting truncation floors (S3b-style STOP conditions), derive the floor from the ACTUAL entry line count, not an estimate. Markdown tables are 1 line per row in raw text (not multi-line blocks), so a 14-row table is ~16 lines, not ~50. The 55-CVE table entry is 37 lines total, not ~80. A 60-line floor based on the bad estimate caused a false-positive S3b fire on Devin's correct 33-line append. Always measure the actual entry size with `wc -l` or `(Get-Content <temp>).Count` before setting the floor.
- **Pydantic v2 + mypy plugin does not recognize `Field(None, ...)` as Optional (L16, prompt-49)**: pydantic v2's mypy plugin requires `default=None` as a keyword argument (not positional `None`) to infer the field as Optional in type-checking mode. `Field(None, description=...)` produces "Missing named argument" errors at every caller site. Fix: use `Field(default=None, description=...)` for all Optional fields. This is a schema-level fix — no caller changes needed.
- **Closing steps skipped — plan reported complete but tag not on origin (L17, prompt-49b)**: Devin reported "tagged as prompt-49b" but the tag was never pushed to origin. The commit was pushed (`git push origin master`), the tag was not (`git push origin prompt-49b` was skipped or failed silently). This is the prompt-38 pattern recurring. Fix: every plan's closing steps must end with the literal output of `git ls-remote --tags origin | findstr prompt-NN` pasted to the CHANGELOG. If this output is empty, the plan is NOT complete — retry the push. If retry fails, report to the user. Do NOT claim the plan is complete without this evidence. See Architecture Rule 21 for the full enforcement text.
- **Step 0 verification overhead exceeds plan scope (L18, prompt-50)**: after adding bandit/pip-audit/vulture/mypy to the pipeline (Plan 48), Step 0 grew to 15-20 sub-steps for plans that make ~10 lines of changes. The verification overhead became 10x the actual work. Fix: Step 0 should be **proportional to plan scope**. For test-only plans (Plan 50, 53): skip bandit/pip-audit/vulture baselines (they scan production code, not tests) — only capture mypy + pytest. For production-code plans (Plan 51, 52): capture all relevant tools. For docs-only plans (Plan 48.1): skip everything except git tag check + test count. The handoff baseline must always reflect ACTUAL measured counts, not estimates — the calendar test failure (1166 passed, 1 failed) was in the handoff as "1167 passed, 0 failed" for 5 plans, causing every Step 0 to investigate the mismatch.

**Verification cadence (L18 enforcement — every 5 plans)**:
- **Every plan (50, 51, 52, 53, 54...)**: ruff (if touching `.py` files — file-scoped, <5s) + mypy (if touching typed code — **file-scoped only**, e.g. `mypy tests/test_approval_gate.py --ignore-missing-imports`, NOT `mypy .`) + pytest. These are fast (<30s combined) and catch regressions immediately. **NEVER run `mypy .` (full repo) per-plan — it takes 2-5 minutes and stalls Devin's terminal. Full-repo mypy is a checkpoint scan only.**
- **Every 5th plan (50, 55, 60, 65...)**: full scan — ruff + mypy `.` (full repo, 2-5 min) + bandit + pip-audit + vulture + pytest. This is the checkpoint scan that catches accumulated drift, new CVEs, and dead code. Takes 5-10 minutes but only runs at milestones.
- **Security-sensitive plans** (touching `memory/postgres.py`, `skills/code_execution/`, `skills/terminal/`, `core/auth.py`, `.github/workflows/ci.yml`): always run bandit, regardless of cadence.
- **Dependency-touching plans** (modifying `requirements.txt`): always run pip-audit, regardless of cadence.
- **Docs-only plans** (no `.py` changes): git tag check + pytest count only. Skip ruff/mypy/bandit/pip-audit/vulture entirely.

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

**Note**: Plans 45-50 complete. Plan 51 is next. Verification cadence: every plan runs ruff+mypy(file-scoped)+pytest; every 5th plan (55, 60...) runs full scan (ruff+mypy.+bandit+pip-audit+vulture). See L18.

### Plan 51 — Adapter type fixes + `del e` patterns + DI fixes (gemini.py emit_trace)
- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Why**: 27 mypy errors (14 `tokens_used: float vs int` in adapters + 13 `del e` read-deleted-variable). Plus 3 DI violations: `adapters/gemini.py` uses global `emit_trace()` instead of `self._emitter.emit()` (5 call sites), `core/handlers.py:21` has dead `emit_trace` import, `cli/tui.py:229` + `core/commands.py:74` use `ConsoleTraceEmitter` default instead of `MemoryTraceEmitter`.
- **Scope**: 7 adapters (anthropic, cohere, deepseek, groq, mistral, openai, together) for `tokens_used` fix; 13 `del e` sites across core/+adapters/; `adapters/gemini.py` for emit_trace→self._emitter.emit; `core/handlers.py` for dead import; `cli/tui.py` + `core/commands.py` for ConsoleTraceEmitter→MemoryTraceEmitter.
- **Verification**: `mypy adapters/ --ignore-missing-imports` (file-scoped) returns 0 NEW errors. `mypy adapters/gemini.py --ignore-missing-imports` shows no emit_trace references. Full test suite passes.

### Plan 52 — F4 wiring fix (cognition-loop components into serve request path)
- **Priority**: **P1** (elevated from P2 per 2026-06-20 comprehensive review — single highest-leverage next step)
- **Effort**: M
- **Risk**: MED
- **Why**: F4 (open since prompt-35.6b): `cli/serve.py` constructs `worker_persistence`, `output_evaluator`, `trace_optimiser`, `worker_factory` but never wires them into the request path. Plan 46 Step 5 prefixed them with `_` to silence F841 — this plan actually wires them. Without this, `jarvis serve` doesn't self-improve. The comprehensive review identified this as the unlock for the entire self-improvement story.
- **Scope**: `cli/serve.py` — wire the 4 subsystems into the orchestrator request loop. Remove the `_` prefixes from Plan 46.
- **Verification**: Start `jarvis serve`, hit `POST /api/tasks` with `{"intent": "test"}` — should return a real `task_id`. Cognition loop components invoked (verify via trace events).

### Plan 53 — Test suite health + B108 + calendar test fix + datetime.utcnow deprecation
- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Why**: 22 B108 bandit findings in tests (hardcoded /tmp), 1 calendar test failure (hardcoded date now in past), 908 datetime.utcnow() deprecation warnings. All test-suite hygiene.
- **Scope**: Fix calendar test (use relative date), replace /tmp with tempfile.mkdtemp(), replace datetime.utcnow() with datetime.now(datetime.UTC) in test files.
- **Verification**: `bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache -s B108` returns 0. Calendar test passes. Deprecation warnings reduced.

### Plan 54 — F401 bulk cleanup (246 unused imports)
- **Priority**: P3
- **Effort**: M
- **Risk**: LOW (mechanical, auto-fixable)
- **Why**: 246 F401 unused imports. `ruff check . --select F401 --fix` auto-fixes most. Remaining need manual triage.
- **Scope**: Run `ruff check . --select F401 --fix`, then triage remaining manually.
- **Verification**: `ruff check . --select F401` returns 0 errors. Full test suite passes.

### Plan 55 — Full checkpoint scan + Marine stack start (5-plan milestone)
- **Priority**: P2
- **Effort**: L
- **Risk**: MED
- **Why**: This is the 5-plan checkpoint (50→55). Run full scan (ruff+mypy.+bandit+pip-audit+vulture). Then start the marine stack — the moat. Ship as portable SKILL.md files.
- **Scope**: Full scan first. Then implement weather + AIS skills as SKILL.md files.
- **Verification**: Full scan shows accumulated improvements. Marine SKILL.md files load and execute correctly.

---

## After Plan 57 — Decision point

Once Plans 48-57 land, the foundation is solid: security tools in CI, ApprovalGate API fixed, all mypy errors cleared, F4 wiring done, test suite healthy, F401 bulk cleanup done, marine stack started, dependencies updated, dead code removed. At that point, choose:

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
20. `table_name` parameter in `memory/postgres.py` MUST be validated against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$` at construction time. f-string interpolation of `table_name` into SQL is permitted ONLY because of this validation. Any new SQL-interpolated identifier must follow the same pattern (validate at construction, then interpolate). **Currently enforced by Plan 48 Step 1.1.**
21. **Closing steps C1-C11 are MANDATORY and MUST all be executed in order. A plan is NOT complete until C11 (tag-push gate verification) passes.** Skipping any closing step — especially C10 (`git push origin prompt-NN`) and C11 (`git ls-remote --tags origin | findstr prompt-NN`) — is a Rule 19 violation. The code changes (Steps 1-N) and verification gates (Gates 1-7) are necessary but NOT sufficient. The closing steps are what make the plan "done": C1-C3 verify no regressions, C4-C5 commit + tag, C6-C9 update docs, C10-C11 push + verify the tag reached origin. **prompt-49b violated this rule**: Devin reported "tagged as prompt-49b" but the tag was never pushed to origin — the commit was pushed, the tag was not. This is the prompt-38 pattern recurring. **Enforcement**: every plan's closing steps must end with the literal output of `git ls-remote --tags origin | findstr prompt-NN` pasted to the CHANGELOG. If this output is empty, the plan is NOT complete — retry the push. If retry fails, report to the user. Do NOT claim the plan is complete without this evidence.

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
| 44 | InputSanitiser wiring | 1134 | InputSanitiser wired into 5 external-input entry points (web/server.py, gateways/telegram/gateway.py, skills/web_scraper/skill.py, core/orchestrator.py, core/handlers.py QueryHandler). Defense-in-depth: boundary + sink + CLI/TUI sanitisation. 7 wiring tests added. |
| 45 | InputSanitiser redesign + trajectory_exporter functional | 1167 | 6-layer InputSanitiser (normalise → truncate → strip_injection_tags → strip_html → strip_command_injection → strip_prompt_injection). 27 new tests. MemoryRouter.fetch_by_type() added. TrajectoryExporter functional (6 un-skipped tests). Test suite: 1134 → 1167 (+33 passed, -6 skipped). |
| 46 | F821 + F811 + critical F841 cleanup | 1167 | Fixed 3 F821 runtime crashes (cli/command_history.py uuid4, core/session.py Task, workers/echo_worker.py core). Fixed 8 F811 duplicates (core/schemas.py Scratchpad, cli/tui.py CommandHistory, core/escalation.py TraceEventType ×3, core/memory_router.py datetime/uuid4 ×2). Fixed 33 F841 unused vars (5 in approval_gate Rule 17, 7 in adapters, 4 in serve.py, plus 17 more discovered during verification). F821: 25→21, F811: 8→0, F841: 81→48. **Note**: original chat report claimed "21 F841 fixed" — actual was 33 (Rule 19 violation, landmine L10). |
| 47 | E402 + missing gateways/__init__.py + flagged unused imports | 1167 | Fixed E402 in web/server.py (7 errors) + web/middleware/auth_middleware.py (6 errors) by moving logging.getLogger() after imports. Created gateways/__init__.py (empty). Removed 13 unused imports. E402: 35→22, F401: 260→247. Mypy on 4 in-scope files: 53→44. |
| 48 | Security: B608 SQL injection + B104 suppression + CI bandit/pip-audit/vulture | 1167 | Fixed 2× B608 SQL injection in memory/postgres.py (table_name validation). Suppressed 2× B104 false positives. Added bandit+pip-audit+vulture to CI. |
| 48.1 | CHANGELOG append procedure fix (temp-file pattern + L15) | 1167 | Docs-only. Fixed PowerShell here-string hang. Added L15 landmine. |
| 49 | ApprovalGate schema Optional fields + TraceEvent kwargs | 1167 | Fixed 10 Field(None→default=None) + 3 TraceEvent kwargs. ~108 mypy errors eliminated. Added L16 landmine. |
| 49b | Migrate old-API callers to request_approval(request: ApprovalRequest) | 1166 | 17 call sites across 8 skill files migrated. 32 mypy errors eliminated. 1 pre-existing calendar test failure. |
| 50 | MockMemoryRouter/MockStateMachine inheritance fix | 1166 | 122 mypy errors eliminated across 8 test files. Mock classes now inherit from real classes. Test-only, no production code changes. |

---

## Recurring mistake patterns

Six patterns account for ~90% of the mistakes in the CHANGELOG.

1. **Spec deviation without documentation.** When a spec specifies an exact value, format, method name, or scope, implement exactly that. If a different approach seems better, STOP and flag it in Implementation Notes as an explicit deviation with rationale. Do not silently substitute. The 35.5/35.5.1 `<thinking>` vs `<thought>` vs `<think>` saga was this. The 35.6c CHANGELOG contradicting the commit was this.

2. **Mock-the-SUT tests with `assert True`.** When writing tests, the test must verify behaviour, not just confirm the code runs. If a test mocks the system under test and asserts `True`, it is not a test — it is a smoke check. The 35.6b `test_serve_constructs_full_orchestrator` and `test_serve_worker_factory_accessible` tests were this. Test must capture the constructed orchestrator and assert each subsystem is non-None.

3. **Localised fixes for systemic bugs.** When a bug is found in one file, search the codebase for the same pattern before closing the prompt. 35.6d Bug 5 fixed the `MemoryRouter.fetch(dict)` call in `session.py` and `command_history.py` but the same bug exists in 15+ other files. Use `grep` or `mypy` to find all instances.

4. **Broad `except Exception: pass` hiding real failures.** Every audit finding about "dead wiring" traces back to a try/except that swallowed the error that would have told you the wiring was broken. If you must use broad except, emit a trace event at WARNING level with the exception message. If you can use a narrower exception type, do.

5. **Tagging with a red test suite is forbidden.** The full test suite MUST pass (green) before tagging. If the test suite is red, STOP and fix it. Do not tag and promise to fix later. This is the root cause of Prompt 37.1 — Prompt 37 tagged with 69 test failures.

6. **Marking gates passed based on intention rather than execution.** When a plan has steps and gates, the gate verifies the step's output. Marking a gate PASSED before its producing step is complete — or marking it PASSED without pasting literal output — is the same as not running the gate. Prompt-37 was this (Gate 5 tagged with 69 failures). Prompt-37.6 was this (Gate 3 marked PASSED with no output, Gate 5/6 marked SKIPPED without being skipped per plan, 8 tests marked `@pytest.mark.skip` because mocking was hard). The fix is Rule 19: execute in order, paste literal output, do not skip without plan authority.

7. **Count assertions without measurement (recurs across prompts 39-47).** The prompt-46 chat report claimed "F841: 81 → 55 (21 critical errors fixed)" but the actual post-prompt-46 count was 48 (33 fixed). The prompt-45 chat report's "33 new tests" was accurate, but the pattern recurs: Devin sometimes asserts lint/test counts from memory or prior-prompt baselines instead of measuring. Rule 19 requires literal evidence — always paste the `Select-Object -Last 3` output of `ruff check . --select F841` (or equivalent) as proof of the count. The 2026-06-20 full repo scan caught this by re-running all tools against the actual repo state.

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
