# Sovereign AI Agent Framework — Project Handoff

**Last updated**: 2026-06-21 — global_rules.md upgraded to v2 (self-evolution added); Plan 53 in progress

**Test baseline**: 1167 passed, 55 skipped, 0 failures, 0 warnings

**Static analysis baseline (post-prompt-54)**:
- Ruff: 111 errors (was 358 — Plan 54 fixed 246 F401 across 118 files)
- Mypy: 282 errors (was 309 — Plan 51 fixed 27: 13 shadowing + 14 float→int)
- Bandit: 0 B108 in Plan 53 scope (test_calendar_skill.py); 22 pre-existing B108 in other test files deferred to follow-up (test_approval_gate.py: 11, test_query_handler.py: 7, test_skill_registry.py: 2, test_security.py: 1, test_file_writer.py: 1)
- pip-audit: 55 CVEs across 14 packages (deferred to Plan 56)
- Vulture: 47 high-confidence findings (deferred to Plan 57)

**Devin rules file**: globalrules/global_rules.md v2.1 (22 rules). L19 (datetime consistency), L20 (self-evolution meta-rule — every plan's closing report MUST include a rule-proposal section), L21 (CHANGELOG append position). Shipped in Plan 54.

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

### F4 — `cli/serve.py` constructs cognition-loop subsystems but never wires them
- **Cause**: Subsystems constructed with `_` prefix (Plan 46) to silence F841. Never wired into request path.
- **Fix**: Plan 52 — wire `worker_factory`, `output_evaluator`, `trace_optimiser`, `worker_persistence` into orchestrator loop.
- **Verification**: Start `jarvis serve`, hit `POST /api/tasks` — should return a real `task_id`.

### F9 — 55 dependency CVEs across 14 packages
- Deferred to Plan 56. Run `pip-audit` for current list.

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
| TrajectoryExporter | `system/trajectory_exporter.py` | Functional (prompt-45) but not reachable. Wiring deferred to Plan 52. |
| MemoryCompactor | `core/memory_compactor.py` | Same |
| MCPServer | `skills/mcp_server.py` | Built but never started |
| MCPAdapter | `adapters/mcp_adapter.py` | Built but never constructed |

When a subsystem is wired into a runtime entry point, remove it from this table.

---

## What's deferred (not started)

1. **Marine stack** — weather, AIS, tidal, passage_planner. Ship as portable SKILL.md files.
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

2. **Pull latest**:
   ```powershell
   git pull origin master
   ```

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

## User domain context

- **Media production** — video scripts, content creation
- **3D printing and CNC machining** — file generation, design workflows
- **Sailing** — route planning, weather monitoring, AIS tracking

---

## Next 5 prompts

### Plan 55 — Full checkpoint scan + Marine stack start (P2)
- 5-plan milestone: full scan. Then start marine stack as SKILL.md files.

### Plan 56 — Dependency updates (P2)
- Fix 55 CVEs across 14 packages. Upgrade or pin vulnerable dependencies.

### Plan 57 — Vulture cleanup (P3)
- Fix 47 high-confidence dead code findings.

### Plan 58 — Remaining datetime.utcnow() cleanup (P3)
- Fix 28 remaining utcnow in 4 test files: test_retention.py (12), test_memory_compactor.py (8), test_event_trigger.py (7), test_memory_router.py (1).
- Fix 90 remaining utcnow in 17 production files (core/*): orchestrator, escalation, approval_gate (remaining), task_state_machine, multi_worker, retention, memory_compactor, voice_interface, auth, notification, a2a_protocol, schemas, memory_router, evaluator, event_trigger, orchestrator_improvement, worker_factory.
- Per L19 (new in v2.1 rules): both test and production must use datetime.now(timezone.utc). No mixing naive/aware.

### Plan 59 — (open slot for next GLM scoping)
