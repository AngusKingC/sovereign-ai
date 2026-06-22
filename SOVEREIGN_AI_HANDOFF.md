# Sovereign AI Agent Framework — Project Handoff

**Last updated**: 2026-06-22 — post-prompt-58.7 + Plan 59 review optimizations

**Repository**: https://github.com/AngusKingC/sovereign-ai
**Default branch**: `master`
**Clone (Devin, Windows)**: Devin's local working copy (path managed by Devin Desktop)
**Clone (GLM, review sandbox)**: `/home/z/my-project/sovereign-ai-framework/` (Linux; optional deps NOT installed — see L19)
**`origin` remote**: points to the GitHub repo above. All `git push origin` / `git pull origin` commands target this repo.

**Test baseline**: 1166 passed, 56 skipped, 0 failures, 0 warnings

> **⚠ Verification needed (B2 from Plan 59 review, 2026-06-22)**: The CHANGELOG entries for 58.5, 58.6, and 58.7 contain contradictory baseline counts (see NOTE blocks in CHANGELOG.md). The 1166/56 figure above is the post-58.7 state as reported, but the progression from 58.5 (1167/55) to 58.6 (1166/56) shows one test moved from passed to skipped — the specific test was not identified. **Plan 59 S1.1 MUST capture the actual baseline** by running `python -m pytest tests/ -q --tb=short` on Windows. If the actual count differs from 1166/56, investigate per L3 landmine (silent skip). Per L19, GLM must NOT run pytest on clone (missing optional deps — anthropic, cohere, google, groq, openai, asyncpg, qdrant — would give a false count).

---

## Table of contents

1. [Repository & environment](#repository--environment) — repo URL, clone paths, Python version, OS, optional deps
2. [Project vision](#project-vision)
3. [What works right now](#what-works-right-now)
4. [What's broken right now](#whats-broken-right-now)
5. [What's built but not reachable](#whats-built-but-not-reachable)
6. [What's deferred (not started)](#whats-deferred-not-started)
7. [Opening + Closing steps](#opening--closing-steps-mandatory--glm-copies-these-into-every-plan) — mandatory template for every plan
8. [Architecture rules](#architecture-rules-never-violate)
9. [Dependency injection rules](#dependency-injection-rules)
10. [Completed prompts](#completed-prompts)
11. [Known landmines](#known-landmines)
12. [Hardware context](#hardware-context)
13. [Environment](#environment) — Python version, install/run commands, optional deps
14. [User domain context](#user-domain-context)
15. [Next 5 prompts](#next-5-prompts)

---

## Repository & environment

- **Repo**: https://github.com/AngusKingC/sovereign-ai (GitHub, private)
- **Default branch**: `master`
- **Tags**: `prompt-{N}` for each completed plan (e.g. `prompt-58.7`). Tag-push gate is mandatory (L5/L17/Rule 21).
- **Clone (Devin)**: Windows local path managed by Devin Desktop. All plan execution happens here.
- **Clone (GLM review)**: `/home/z/my-project/sovereign-ai-framework/` on Linux sandbox. Used for read-only verification (line numbers, file existence, ruff/bandit counts). **Cannot run pytest** — optional deps not installed (see L19).
- **`origin` remote**: always refers to the GitHub repo above.

---

**Static analysis baseline (post-prompt-55 — 5-plan milestone)**:
- Ruff: 111 errors (F401=0 since Plan 54; per Plan 55 full-scan baseline — actual count captured by Devin at Plan 59 S1.2)
- Mypy (full-repo): 283 errors (was 282 — delta +1)
- Bandit: 3179 low, 22 medium (22 B108 pre-existing in tests/, deferred)
- pip-audit: 19 CVEs across 4 packages (was 55 — Plan 56 fixed 36 CVEs)
- Vulture: 20 high-confidence findings (was 32 — Plan 57 removed 16, deferred 16 as Category C)

**Devin rules**: **Devin Desktop config (2026-06-22)** — three layers of rules/tools:
1. **AGENTS.md** (repo root, always-on): 22 stable rules across 6 categories. Devin Desktop auto-discovers this.
2. **Section 0** (per-plan, evolving): L1-L26 rules that grow via L20 self-evolution (Devin proposes via C9, GLM accepts/rejects). Canonical source: `globalrules/global_rules_v2.md` in this repo (v2.4, 25 rules — Plan 59 Section 0 extended to L26, the repo copy will catch up at next docs sync).
3. **Workflows + Skills** (`.windsurf/` directory):
   - `/jarvis-close` — full C1-C13 closing sequence (prevents "forgot to tag")
   - `/jarvis-verify` — post-edit syntax + diff + test checks
   - `/jarvis-scan` — sequential 6-tool full scan (L24 enforced)
   - `jarvis-b108-suppress` skill — auto-invoked on B108 bandit findings
   - `jarvis-f841-triage` skill — auto-invoked on F841 ruff findings
The `/globalrules/` folder is reference-only (frozen Plan 54 snapshot).

---

## Project Vision

A local-first, self-improving AI assistant for one user's specific context: media production, sailing, 3D printing, CNC machining. Runs locally by default, escalates to cloud when the task demands it, monitors open-loop background tasks (weather, AIS, email) and interrupts only when necessary.

**Core philosophy**: Strong, robust, simple core. Wire as you go. No new horizontal capability until the existing stack is reachable and demonstrably improving worker outputs.

---

## What works right now

- **`jarvis`** (no args) — starts Textual TUI with full cognition stack wired. User can type queries, get responses from local Ollama. Memory is stateful across queries.
- **`jarvis "query"`** — non-interactive single-query mode via Rich CLI.
- **`jarvis --rich`** — Rich-based interactive CLI with slash commands.
- **`jarvis --setup` / `--reconfigure` / `--doctor`** — SetupWizard runs, writes config + `.env`, doctor checks Ollama/Postgres/Qdrant/Obsidian reachability.
- **`jarvis serve`** — starts FastAPI server. Accepts task submissions via POST /api/tasks, returns worker listings via GET /api/workers.
- **TUI slash commands** — `/help`, `/status`, `/clear`, `/exit`, `/model`, `/adapter`, `/theme` work. `/adapter` supports 10 adapters.
- **Session manager** — in-memory mode works. Postgres persistence does not.
- **Command history** — in-memory mode works. Postgres persistence does not.

---

## What's broken right now

> **Note**: Previously tracked issues F4 and F9 have been resolved. Kept here for historical context — see "What's built but not reachable" for currently-dormant subsystems.

### F4 — `cli/serve.py` cognition-loop wiring (RESOLVED by Plan 52)
- **Was**: Subsystems constructed with `_` prefix (Plan 46) to silence F841, never wired into request path.
- **Fix (Plan 52)**: `worker_factory`, `output_evaluator`, `trace_optimiser` wired into orchestrator loop in `cli/serve.py` and `cli/tui.py`.
- **Remaining**: `TrajectoryExporter` still dormant — see "What's built but not reachable" table below. Wiring deferred to a future plan (not Plan 52, which is complete).

### F9 — Dependency CVEs (PARTIALLY RESOLVED by Plan 56)
- **Was**: 55 dependency CVEs across 14 packages.
- **Fix (Plan 56)**: 11 packages upgraded, 36 CVEs fixed. pip-audit: 55→19 CVEs.
- **Remaining**: 19 CVEs across 4 packages — deferred pending upstream patches (Starlette blocked by FastAPI incompatibility, chromadb/diskcache no confirmed fixes). Run `pip-audit` for current list.

---

## What's built but not reachable

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
| TrajectoryExporter | `system/trajectory_exporter.py` | Functional (prompt-45) but not reachable. Wiring NOT done in Plan 52 (Plan 52 wired cognition loop only). Deferred to a future plan. |
| MemoryCompactor | `core/memory_compactor.py` | Same |
| MCPServer | `skills/mcp_server.py` | Built but never started |
| MCPAdapter | `adapters/mcp_adapter.py` | Built but never constructed |
| MarineWeather (SKILL.md) | `skills/marine/weather/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |
| MarineAIS (SKILL.md) | `skills/marine/ais/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |
| MarineTidal (SKILL.md) | `skills/marine/tidal/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |
| MarinePassagePlanner (SKILL.md) | `skills/marine/passage_planner/SKILL.md` | Spec only — no Python implementation yet (Plan 61) |

When a subsystem is wired into a runtime entry point, remove it from this table.

---

## What's deferred (not started)

1. **Marine stack Python implementation** — weather, AIS, tidal, passage_planner. SKILL.md specs exist (created Plan 55). Implement as Python skills — Plan 61.
2. **Sandboxed execution** for `skills/terminal/` and `skills/code_execution/`. Currently runs subprocesses on host.
3. **Streaming output** from Ollama through worker pipeline to TUI/Web GUI.
4. **Function-calling / tool-use loop.** Route-once-generate-once is a generation behind.
5. **Deployment story.** Docker compose with Postgres + Qdrant + Jarvis + Ollama.
6. **Eval harness.** Held-out task suite to measure self-improvement.
7. **Plan mode.** Agent proposes, user approves, agent executes.

---

## Opening + Closing steps (mandatory — GLM copies these into every plan)

These are the template steps GLM includes in every plan file. Devin executes them from the plan, not from this handoff.

### Opening steps (GLM puts these at the start of every plan's Step 0)

1. **Verify previous prompt completed** (prevents starting on stale state):
   ```powershell
   git ls-remote --tags origin | findstr prompt-{N-1}
   ```
   If empty, STOP — previous prompt's tag wasn't pushed. Fix that first.

2. **Verify local working copy is clean and on master** (do NOT pull):
   ```powershell
   git status
   git branch --show-current
   git rev-parse HEAD
   ```
   - `git status` should show "nothing to commit, working tree clean"
   - `git branch --show-current` should show `master`
   - `git rev-parse HEAD` should match the expected post-`prompt-{N-1}` HEAD
   - **Do NOT run `git pull origin master`.** Devin's local working copy is authoritative. Pulling from GitHub risks overwriting local work or pulling in unexpected changes. The previous-tag check above is sufficient to confirm the prior plan was pushed.
   - **If review fixes need to be applied** (e.g. CHANGELOG/handoff corrections from GLM review), they are applied MANUALLY to the local copy BEFORE the plan starts — not via git pull.

Note: `Start-Transcript` does NOT work with Devin's multi-terminal architecture — Devin runs commands in separate terminal instances. The execution log is the user's chat paste (which shows every command + output). Do not use `Start-Transcript`.

### Closing steps (GLM puts these at the end of every plan)

1. Run full test suite: `python -m pytest tests/ -q --tb=short`. Confirm zero new failures.
2. `ruff check <files_touched>` — zero errors.
3. `mypy <files_touched> --ignore-missing-imports` — zero errors. **File-scoped only** (L18).
4. `git add . && git commit -m "checkpoint: prompt-{N}" && git tag prompt-{N}`
5. `git show prompt-{N} --stat` — verify file list contains only files in this plan.
6. Update `CHANGELOG.md` with **SIMPLIFIED** entry (~10 lines):
   ```
   ## YYYY-MM-DD HH:MM — prompt-{N}
   
   **Plan**: <one-line plan title>
   
   **Changed**:
   - <file>: <what changed (1 line)>
   
   **Results**:
   - Mypy: <before> → <after>
   - Tests: <count> passed, <count> skipped, <count> failed
   - Tag: prompt-{N} verified on origin
   ```
   Use `-Encoding utf8` on both `Get-Content` and `Add-Content` (L15).
7. **Execution log**: the user pastes Devin's chat transcript to GLM after each prompt. This IS the execution log — it contains every command, output, error, and thinking step. GLM reads it to extract actual counts, issues for next prompt, and STOP conditions. No separate log file or transcript is needed.
8. Update this handoff: move completed plan to "Completed prompts" table, update test baseline + static analysis baseline, refill "Next 5 prompts" queue.
9. **Rule proposal (self-evolution — L20 in global_rules_v2.md, L24 in this handoff)**: scan your work this prompt for recurring error patterns or landmines not covered by `global_rules.md`. If found, append a `## Rule proposal for global_rules.md` section to your closing report with:
   ```
   Trigger: <what happened this prompt — concrete, e.g. "TypeError comparing naive and aware datetime in test_calendar.py line 47">
   Recurrence: <prompt numbers where this same pattern bit, or "first occurrence">
   Proposed rule: L{n+1}. <one-line rule statement>
   Anchor: <prompt number + file + line>
   Why existing rules didn't catch it: <one line>
   ```
   If no new failure patterns were encountered, append: `## Rule proposal — none (no new failure patterns this prompt)`. Silence is NOT acceptable — explicit reflection is required. GLM reviews each proposal after the plan completes and updates `global_rules.md` (now v2) if accepted.
10. `git add CHANGELOG.md SOVEREIGN_AI_HANDOFF.md && git commit -m "docs: prompt-{N} changelog and handoff update"`
11. `git push origin master && git push origin prompt-{N}`

### Plan completion checklist (GLM puts this at the end of every plan — Devin must paste ALL before reporting done)

```
1. C1 test suite: <paste last 3 lines of pytest>
2. C4 tag created: <paste git tag --list prompt-{N}>
3. C5 file list: <paste git show prompt-{N} --stat>
4. C10 pushed: <paste git push origin prompt-{N}>
5. C11 tag on origin: <paste git ls-remote --tags origin | findstr prompt-{N}>
6. Handoff updated: <paste the new completed-prompts table row>
7. Handoff baselines updated: <paste the test baseline + mypy count lines>
8. Rule proposal section: <paste either the proposal block OR "none — no new failure patterns this prompt">
```

If any check fails or output is missing (including the rule-proposal section), the plan is NOT complete (Rule 21, L17, L24).

**CHANGELOG append procedure**: simplified entries (~10 lines). Use `-Encoding utf8` on both `Get-Content` and `Add-Content` (L15). For entries >20 lines, use temp-file pattern. NEVER use `Get-Content | Measure-Object` for line counts — use `[System.IO.File]::ReadAllLines(...).Count`.

### Claude review workflow

Plans go through Claude review before Devin execution. Context briefs are ~30-50 lines, pointer-based (reference handoff sections by pointer, don't copy). No cap on revision rounds — continue until PLACE with zero findings.

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
12. No global mutable state. (Known violations: `_global_registry` in `core/commands.py`, `_global_emitter` in `core/observability.py`. Removal deferred — requires DI refactor.)
13. All I/O operations are async.
14. `InputSanitiser` MUST be called on all externally-sourced content before it enters LLM context. ✅ Wired (prompt-44, redesigned prompt-45).
15. `ApprovalTrustRegistry` MUST be consulted by `ApprovalGate` before raising any approval request.
16. Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes. No unauthenticated endpoints except `/health`.
17. No broad `except Exception: pass` without inline comment + WARNING trace. ✅ All directories compliant.
18. Tests change with code. Full test suite MUST pass before tagging.
19. Execute steps and gates in listed order. Gate output must be pasted literally — "PASSED" without evidence is forbidden.
20. `table_name` in `memory/postgres.py` MUST be validated against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$` at construction time.
21. **Closing steps C1-C11 are MANDATORY. A plan is NOT complete until the completion checklist passes.** Tag-push gate verification (`git ls-remote --tags origin | findstr prompt-NN`) is mandatory. Handoff baselines MUST be updated.

---

## Dependency injection rules

- `TraceEmitter` and `CommandRegistry` constructed ONCE in `cli/main.py` and passed down. (Currently violated — deferred.)
- All components receive emitter via constructor: `emitter: TraceEmitter | None = None`. Default to `MemoryTraceEmitter()`, never `ConsoleTraceEmitter()`.
- Never import `get_trace_emitter`, `set_trace_emitter`, `emit_trace`, `_global_emitter`, or `_global_registry` anywhere.
- When passing emitter to `super().__init__()`, the parameter MUST appear in the subclass `__init__` signature BEFORE the `super()` call.

---

## Completed prompts

| # | Prompt | Tests | Notes |
|---|---|---|---|
| 44 | InputSanitiser wiring | 1134 | 5 entry points wired. 7 wiring tests. |
| 45 | InputSanitiser redesign + trajectory_exporter | 1167 | 6-layer defense. 27 new tests. fetch_by_type() added. 6 tests un-skipped. |
| 46 | F821 + F811 + F841 cleanup | 1167 | 3 F821, 8 F811, 33 F841 fixed. |
| 47 | E402 + gateways/__init__.py + unused imports | 1167 | E402: 35→22, F401: 260→247. |
| 48 | Security: B608 + B104 + CI bandit/pip-audit/vulture | 1167 | SQL injection fixed. CI jobs added. |
| 48.1 | CHANGELOG append procedure fix | 1167 | L15 landmine. Temp-file pattern. |
| 49 | ApprovalGate schema + TraceEvent kwargs | 1167 | 10 Field(default=None) + 3 TraceEvent kwargs. ~108 mypy eliminated. |
| 49b | Migrate old-API callers | 1166 | 17 call sites across 8 skills. 32 mypy eliminated. |
| 50 | MockMemoryRouter/MockStateMachine inheritance | 1166 | 122 mypy eliminated across 8 test files. |
| 51 | Exception shadowing + float→int + DI fixes | 1166 | 27 mypy eliminated. e→inner_e, float→int casts. |
| 52 | F4 wiring — cognition-loop into serve.py | 1166 | worker_factory etc. wired into request path. |
| 53 | Test suite health — calendar + B108 + datetime | 1167 | Calendar test fixed. 22 B108 fixed. 81 utcnow fixed in 15 test files. 28 test utcnow + 90 production utcnow deferred to Plan 58. |
| 54 | F401 bulk cleanup + global_rules v2.1 ship + handoff fix | 1167 | 246 F401 fixed across 118 files. v2.1 rules shipped (L19/L20/L21). Handoff baselines updated. globalrules/ folder created. |
| 55 | 5-plan milestone: full scan + Marine stack start | 1167 | 4 SKILL.md files created (weather, AIS, tidal, passage_planner). Full-repo scan: ruff=111, mypy=283, bandit=22B108+3179low, pip-audit=37CVEs, vulture=32. Fresh baselines for Plans 56-60. |
| 56 | Dependency updates | 1167 | 11 packages upgraded (aiohttp, cryptography, idna, pygments, pypdf, pytest, python-dotenv, python-multipart, urllib3, pillow, setuptools). pip-audit: 55→19 CVEs. Starlette deferred (FastAPI incompatibility), chromadb/diskcache deferred (no confirmed fixes). |
| 57 | Vulture cleanup | 1167 | 16 dead-code findings removed (12 adapters + 3 core + 1 worker). 16 deferred as Category C (5 core + 11 tests). Vulture: 32→20. |
| 58 | Datetime UTCNow Cleanup | 1167 | 107 datetime.utcnow() calls replaced with datetime.now(timezone.utc) (28 test + 78 production + 1 scope expansion). Zero utcnow remain. 46+ bare datetime.now() calls deferred to Plan 58.5 (pre-existing L19 violations outside scope). |
| 58.5 | Bare datetime.now() cleanup | 1167 | 231 bare datetime.now() calls replaced with datetime.now(timezone.utc) (205 test + 26 production). Zero bare datetime.now() remain. 0 Category C deferrals (all calls were Category A/B - safe to convert). L19 compliance achieved for all datetime calls. |
| 58.6 | Datetime UTCNow in Field(default_factory=...) | 1166 | 12 datetime.utcnow function references in Field(default_factory=...) replaced with lambda: datetime.now(timezone.utc) (8 files). Zero utcnow remain in core/. 2 pre-existing ruff errors suppressed with scoped noqa. |
| 58.7 | Datetime UTCNow in system/ and skills/ | 1166 | 46 datetime.utcnow() calls replaced with datetime.now(timezone.utc) (10 in system/, 36 in skills/). 1 default_factory=datetime.utcnow replaced with lambda: datetime.now(timezone.utc). Zero utcnow remain repo-wide. 1 F541 ruff error fixed. |

---

## Known landmines

- **L1**: `global_rules.md` is Devin-local and unreachable. Don't cite it as authority. C8 targets the handoff.
- **L2**: Gates marked PASSED without literal output (Rule 19). All gates must require pasted output.
- **L3**: `@pytest.mark.skip` because mocking was hard. Fix the mock, don't skip.
- **L4**: Tagging with a red test suite forbidden.
- **L5/L17/Rule 21**: Tag-push gate mandatory. `git ls-remote --tags origin | findstr prompt-NN` must return the tag.
- **L7**: Per-file counts that don't match evidence. Always cite the source.
- **L9**: Devin memories are not authoritative. All authority comes from the handoff.
- **L10**: Test count assertions require measurement. Always paste output.
- **L11**: "No interactive shell" not a valid skip reason.
- **L12**: Scope creep. Only in-scope files.
- **L13**: Capture actual counts at plan-start, don't predict from prior scans.
- **L14**: Bandit commands MUST use `--exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache`.
- **L15**: CHANGELOG simplified (~10 lines). `-Encoding utf8` mandatory on both `Get-Content` and `Add-Content`.
- **L16**: Pydantic v2 + mypy requires `Field(default=None, ...)`, not `Field(None, ...)`.
- **L17/Rule 21**: Closing steps mandatory. Plan not complete until completion checklist passes.
- **L18**: File-scoped mypy only per-plan. NEVER `mypy .`. Full-repo mypy only at 5-plan checkpoints (55, 60...).
- **L19**: GLM must NOT run mypy/bandit/pytest/pip-audit/vulture on clone. Counts come from execution log.
- **L20**: Line numbers in plans verified against clone SHA. Note the SHA in the plan.
- **L21**: Plans must use PowerShell commands (`Select-String`, `Measure-Object`), not `grep`/`sed`/`awk`/`cut`/`wc`.
- **L22 (recurring mistakes)**: If GLM notices Devin repeating the same mistake or inefficient workflow pattern across multiple prompts (e.g. running `mypy .` instead of file-scoped, skipping tag-push, using Unix commands on Windows), GLM should add a step to the next plan instructing Devin to add the lesson to its `global_rules.md` file. Example plan step: "Add to `global_rules.md`: 'Always use file-scoped mypy (e.g. `mypy file.py`), never `mypy .` — it takes 2-5 minutes and stalls the terminal.' If `global_rules.md` doesn't exist or can't be edited, skip and document the skip in CHANGELOG." This ensures Devin's behavioral guardrails stay current with recurring issues GLM observes from the execution logs. **Note**: As of 2026-06-21, this mechanism is now **structural** — every plan's closing sequence includes C9 (rule-proposal step) per L24 below. GLM no longer needs to add ad-hoc rule-addition steps; the structural mechanism handles it.
- **L23 (test-production datetime coupling)**: when changing `datetime.utcnow()` to `datetime.now(timezone.utc)` in test files, check if production code compares datetimes with test data. If production uses `utcnow()` (naive) and tests use `now(timezone.utc)` (aware), Python raises `TypeError: can't compare offset-naive and offset-aware datetimes`. Both must change together. Always scope datetime changes to include both test AND production files that interact with the same datetime values. **Captured as global_rules_v2.md L19** — Devin now has this as a behavioral rule, not just a GLM-side landmine.
- **L24 (self-evolution meta-mechanism — NEW 2026-06-21)**: Every plan's closing sequence MUST include a rule-proposal step (C9 above). Devin scans its work for failure patterns not covered by `global_rules.md` and either (a) submits a structured proposal, or (b) explicitly states "none — no new failure patterns this prompt." Silence is NOT acceptable — explicit reflection is required. GLM reviews each proposal after the plan completes and updates `global_rules.md` if accepted. This makes `global_rules.md` a living document that grows with the project's actual failures, rather than relying on GLM to notice recurring patterns reactively (which is what L22 attempted, less reliably). First active prompt: Plan 54 (or whichever plan first ships global_rules_v2.md to Devin).
- **L25 (L-numbering collision — flagged 2026-06-22 by Plan 59 review, deferred to Plan 60)**: This handoff's "Known landmines" section uses labels L1-L24, but per-plan Section 0 (in plan files) ALSO uses labels L1-Lxx with DIFFERENT meanings. Example: handoff L20 = "line numbers verified against clone SHA," but Plan 59 Section 0 L20 = "self-evolution rule proposal." Same label, different rules — causes confusion when cross-referencing. **Deferred fix**: rename handoff landmines from `L1-L24` to `M1-M24` (minefield) at Plan 60 (5-plan milestone, full scan). Reserve `L1-Lxx` for per-plan evolving rules only. Update all cross-references in plan files and CHANGELOG entries at that time.

**Verification cadence (L18)**:
- Every plan: ruff (file-scoped) + mypy (file-scoped) + pytest.
- Every 5th plan (55, 60...): full scan (ruff + mypy . + bandit + pip-audit + vulture + pytest).
- Security-sensitive plans: always run bandit.
- Dependency-touching plans: always run pip-audit.
- Docs-only plans: git tag check + pytest count only.

---

## Hardware context

- **GPU**: NVIDIA RTX 3060 Mobile — 6GB VRAM
- **RAM**: ~15.6GB available after VRAM
- **OS**: Windows
- **Local LLM**: Ollama with `qwen2.5-coder:7b` (Q4_K_M)

---

## Environment

- **Python**: 3.12.13 (Devin's venv on Windows; GLM sandbox has 3.12.13 in `/home/z/.venv/`)
- **OS (Devin)**: Windows — use PowerShell, not Unix commands (L21). `Select-String` not `grep`, `Measure-Object` not `wc`.
- **OS (GLM review sandbox)**: Linux — cannot run pytest/mypy/bandit/pip-audit/vulture meaningfully because optional deps are not installed (L19). Use for read-only verification only (file existence, line numbers, ruff/bandit static counts).
- **Install (Devin)**: `pip install -r requirements.txt` in venv. CLI entry point `jarvis` installed via `pip install -e .`.
- **Run tests (Devin)**: `python -m pytest tests/ -q --tb=short`
- **Optional dependencies** (in `requirements.txt` but NOT installed in GLM sandbox — causes collection errors on `test_anthropic_adapter.py`, `test_cohere_adapter.py`, `test_gemini_adapter.py`, `test_groq_adapter.py`, `test_openai_adapter.py`, `test_postgres_backend.py`, `test_qdrant_backend.py`):
  - `anthropic`, `cohere`, `google-genai`, `groq`, `openai` — LLM provider SDKs
  - `asyncpg` — Postgres async driver (for `memory/postgres.py`)
  - `qdrant-client` — vector DB SDK (for `memory/qdrant.py`)
- **GLM sandbox limitation**: `pip install` is blocked by PEP 668 (externally-managed-environment). GLM must NOT attempt to install optional deps — counts come from Devin's execution log per L19.

---

## User domain context

- **Media production** — video scripts, content creation
- **3D printing and CNC machining** — file generation, design workflows
- **Sailing** — route planning, weather monitoring, AIS tracking

---

## Next 5 prompts

### Plan 59 — Ruff cleanup (113→0) + B108 scoped suppressions (READY FOR EXECUTION)
- **Status**: Reviewed by GLM on 2026-06-22. Decision: PLACE → revised → READY. All blocking findings (B1, B2) and high-severity findings (H1, H2) addressed.
- **Blocking fixes applied** (commits `9fe2cf5`, `648f8bb` on branch `review/plan-59-revisions`): duplicate prompt-57 CHANGELOG entries removed; 58.6/58.7 baseline contradictions flagged; L25 landmine added; Plan 59 added to this queue.
- **Plan file**: local-only (gitignored under `GLM Prompts/`). Revised plan at `/home/z/my-project/download/plan-59.md` — copy to Devin's local plan folder before execution.
- **Verification needed at S1.1**: capture actual test baseline on Windows to resolve B2 contradiction (1166/56 vs 1167/55).
- **Baselines**: per handoff Plan 55 full-scan (ruff=111, B108=22 in tests/). Actual counts captured by Devin at S1.1/S1.2/S1.3 — do NOT trust GLM clone counts (L19).

### Plan 60 — Full checkpoint scan (P1)
- 5-plan milestone: full scan. Verify Plans 57-59 progress.
- **Includes**: L25 landmine fix (renumber handoff landmines L1-L24 → M1-M24 to avoid collision with per-plan Section 0 L-rules).

### Plan 61 — Marine stack Python implementation (P2)
- Implement the 4 Marine SKILL.md files as Python skills (weather first, then tidal, AIS, passage_planner).

### Plan 62 — (open slot for next GLM scoping)
### Plan 63 — (open slot)
### Plan 64 — (open slot)
