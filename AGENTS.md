# AGENTS.md — Sovereign AI Rules

Devin's always-on rules. Read before every coding session.

**Rule naming**:
- **AR{n}** = Architecture Rules (AR1-AR20)
- **OR{n}** = Operational Rules (OR1-OR38)

**If a rule's application is unclear or ambiguous**, read LANDMINES.md to find the source landmine and understand the diagnostic context behind the rule.

---

## Architecture Rules

AR1. `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/`.

AR2. `workers/` may import from `core/` and `adapters/` but never from `cli/`.

AR3. `memory/` may import from `core/` only.

AR4. `adapters/` may import from `core/` only.

AR5. `skills/` may import from `core/` only.

AR6. `web/` may import from `core/` only.

AR7. `system/` may import from `core/` and `memory/`.

AR8. `cli/` may import from anywhere.

AR9. No raw LLM calls outside `adapters/`.

AR10. No memory access outside `MemoryRouter`.

AR11. `TraceEmitter` via constructor injection only. Never use the global `emit_trace()` function.

AR12. All I/O operations are async.

AR13. No global mutable state. (Known deferred violation: `_global_registry` in `core/commands.py`, `_global_emitter` in `core/observability.py` — removal requires DI refactor.)

AR14. All public functions and methods have return type annotations.

AR15. `InputSanitiser` MUST be called on all externally-sourced content before it enters LLM context.

AR16. `ApprovalTrustRegistry` MUST be consulted by `ApprovalGate` before raising any approval request.

AR17. Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes. No unauthenticated endpoints except `/health`.

AR18. No broad `except Exception: pass` without inline comment + WARNING trace.

AR19. All code execution and terminal command execution MUST go through `SandboxExecutor` (Docker-isolated). No direct `asyncio.create_subprocess_shell()` for code or command execution outside of: (a) `core/sandbox.py` itself, (b) `skills/docker/skill.py` (container management, not code execution), (c) test fixtures that mock subprocess. This prevents a malicious or buggy agent from damaging the host system. (Source: Kimi competition gap analysis #13 — CRITICAL security vulnerability; `skills/code_execution/skill.py:143` and `skills/terminal/skill.py:150` used `create_subprocess_shell` without isolation)

AR20. Local LLM adapters that require a custom build of `llama.cpp` (e.g., PrismML's Q1_0 ternary weight fork) MUST be implemented as adapter-managed subprocess servers, NOT as in-process Python bindings. The adapter is responsible for: (a) verifying the binary exists, (b) launching `llama-server` as a subprocess, (c) health-checking the HTTP endpoint, (d) calling the OpenAI-compatible API via `httpx`, (e) graceful shutdown on adapter close. This avoids fragile C++ build dependencies in `requirements.txt` and keeps the modified `llama.cpp` as an external binary managed by `system/model_acquisition.py`. (Source: GLM-direct, Plan 74.5 — PrismML Ternary Bonsai integration requires Q1_0 quantization support not in stock `llama-cpp-python`)

AR21. `src/` (TypeScript/React frontend) follows TypeScript strict mode (`"strict": true` in `tsconfig.json`) and ESLint with `@typescript-eslint/recommended`. `src/` does NOT import from any Python directory (`core/`, `adapters/`, `cli/`, `web/`, `backend/`, etc.). `src/` communicates with the backend exclusively via HTTP (fetch) and SSE (EventSource). Type safety is enforced by TypeScript strict mode (equivalent to AR14 for Python). Code quality is enforced by ESLint (equivalent to ruff for Python). (Source: Plan 80 Tier 2 review — AR1-AR8 are Python-only; TypeScript directory needs its own governance rule.)

---

## Operational Rules

### Environment
OR1. PowerShell only. Never use `grep`, `cat`, `sed`, `awk`, `head`, `tail`, `touch`. Use `Select-String`, `Get-Content`, `Set-Content`, `Add-Content`, `Get-ChildItem`, `Measure-Object`, `Where-Object`, `ForEach-Object`.

OR2. File-scoped mypy only. Never `mypy .` — except at 5-plan checkpoints (55, 60, 65, 70, 75, 80) where full-repo mypy is the point.

OR3. Run scan tools (pytest, ruff, mypy, bandit, pip-audit, vulture) ONE AT A TIME. Parallel execution corrupts output streams. (Source: L2)

OR4. When counting bandit findings by ID, filter on `>> Issue: [B` pattern only, not bare ID string (ID appears in multiple line types).

### Edit discipline
OR5. Never use `replace_all`. Edit each occurrence individually or use targeted line-specific replacements. (Source: L1)

OR6. Syntax check after every file edit, BEFORE tests: `python -c "import ast; ast.parse(open('<file>.py').read())"`. If syntax error, STOP.

OR7. Structured-markdown edits (AGENTS.md, AI_HANDOFF.md, plan files, CHANGELOG.md) — Edit tool only with exact `old_str`/`new_str` pairs. NEVER PowerShell `-replace`, `ForEach-Object`, or `Set-Content`. (Source: L3)

OR8. Diff check after every file edit: `git diff --stat <file>`. Confirm only intended files changed.

### Git discipline
OR9. Tag EVERY prompt. Even docs-only plans must have `git tag prompt-{N}`.

OR10. Tag verification before push: `git tag --list prompt-{N}`. If empty, tag wasn't created.

OR11. Post-push verification (mandatory): `git ls-remote --tags origin | Select-String "prompt-{N}"`. If empty, push failed.

### Commit discipline (NEW — Plan 72)
OR32. Never use `git commit --no-verify`. Pre-commit hooks are the last gate before commit; bypassing them defeats the purpose of having hooks. If a hook fails, fix the issue — do not bypass the hook. The only acceptable exception is a hotfix to a broken hook itself, and even then, document the bypass in the commit message. (Source: landmine L11 — Plan 71 execution, Devin used `--no-verify` on both the checkpoint and docs commits, bypassing the pre-commit hooks that Plan 71 had just configured)

### CHANGELOG discipline
OR12. Append to END only. Never insert at top. Oldest entry at top, newest at bottom.

OR13. Use temp-file pattern (not here-strings). Append via `Add-Content` with `-Encoding utf8`. After appending, DELETE the temp file. (Source: L4)

OR14. Simplified format: ~10-15 lines per entry. Title, changed files, results, test count. No fluff.

### Scope discipline
OR15. Pre-declare scope before editing. List files you WILL edit and files you will NOT edit. Any file outside the "will edit" list requires STOP and Prompt Creator authorization.

OR16. HARD STOP on scope expansion. If you discover work outside the plan's scope,
STOP and report using this format:
  - Discovered: <what you found>
  - Impact if deferred: <what breaks or blocks>
  - Proposed addition: <specific files/steps needed>
  - Estimated risk: <low/medium/high and why>
Do not fix unilaterally — even a 1-line fix. (Source: L8)

OR17. Baseline reconciliation. If S1 actual count ≠ plan's expected count, update PLANS.md baseline with actual number + reason. Don't let stale baselines propagate. (Source: L7)

OR26. Governance-doc edits discovered at /jarvis-open must be a separate commit and tag. If `git status` at S0.1 shows modified/untracked governance docs (`AGENTS.md`, `AI_HANDOFF.md`, `PLANS.md`, `CHANGELOG.md`, `LANDMINES.md`) or plan files (`GLM Prompts/`), commit them as a standalone `docs: cleanup pre-prompt-{N}` commit and tag as `docs-cleanup-{N}` -- do NOT bundle them into the next `prompt-{N}` tag. The CHANGELOG entry for `prompt-{N}` must list only the files actually edited as part of the plan body. (Source: GLM observation, Plan 63a execution -- 13 files were bundled into `prompt-63a` tag; CHANGELOG only documented 5.)

### Test discipline
OR18. Tests change with code. Full test suite MUST pass before tagging.

OR19. Test fixture parameters may be required by pytest/middleware/pydantic even if vulture flags them as unused. Don't remove without checking decorator context. (Source: L5)

OR25. Test deletion is a scope deviation. If a test listed in the plan's S4 test specification cannot be made to pass due to mocking complexity, fixture difficulty, or API mismatch, STEP and report to the user. Do NOT delete the test, comment it out, or replace it with a "deferred to a future plan" note. Tests specified in the plan are part of the plan's scope; removing them is a HARD STOP under OR16. (Source: GLM observation, Plan 63a execution -- two integration tests were silently deleted after failing twice, leaving the plan's central wiring claim unverified.)

### Datetime discipline
OR20. Never mix naive/aware `datetime`. Use `datetime.now(timezone.utc)` everywhere. Never `datetime.utcnow()` or bare `datetime.now()`. Watch for `default_factory=datetime.utcnow` (use `default_factory=lambda: datetime.now(timezone.utc)` instead). (Source: L6)

### Temp file discipline
OR21. Temp files go in `C:\Jarvis\temp\` or `C:\Jarvis\scan\logs\`, NOT repo root. After appending to CHANGELOG.md (or wherever consumed), DELETE the temp file. Before `git add`, check for stray files.

### Always-on compliance
OR22. Re-read AGENTS.md before any file edit; never edit outside scope. Before editing any file, re-read this document to verify the edit complies with all rules. If an edit would violate a rule, STOP and report. Devin MUST NOT edit files outside the plan's declared scope; if you discover work that needs doing outside scope, STOP and report it. (Source: L8)

### Verbosity & Audit
OR23. Cite rules by number when applying them. When executing a step that applies a rule, cite it: "Applying AR{n}: <rule name>" or "Applying OR{n}: <rule name>". When a rule prevents an action, cite it: "Blocked by AR{n}: <rule name>". This creates an audit trail and makes rule compliance explicit and verifiable in the execution log.

### Test with new implementations
OR24. Every new implementation (new module, new class, new public function) MUST have a corresponding test file with tests covering the key paths. No implementation is "complete" until its tests pass. (Source: Prompt Creator-direct, no landmine)

### Type remediation discipline
OR27. When fixing type errors requires interface changes that would break existing tests, add compatibility shims to maintain backward compatibility. The shim should delegate to the new implementation while accepting the old signature. Mark the shim as deprecated with a docstring noting the legacy status. This allows type fixes without test modifications, which are outside scope for type-remediation plans. (Source: L9)

### PowerShell discipline
OR28. PowerShell session cleanup: After each command execution block, Devin MUST close the PowerShell session. If executing multiple commands in sequence, use a single session with `;` separation rather than spawning multiple sessions. At plan closing (or every 20 commands, whichever comes first), verify no orphaned processes remain:
- **On Windows**: `Get-Process powershell | Where-Object { $_.Id -ne $PID } | Measure-Object` — if count >5, kill orphans before proceeding.
- **On Linux/macOS**: `ps aux | grep -c powershell` or skip this check (Devin runs on Windows; this fallback is for local verification only).
(Source: L10 — Devin leaves zombie PowerShell processes after execution)

### Hook discipline (NEW — Plan 74)
OR33. Never exclude files from pre-commit hooks (mypy, ruff, black, etc.) to bypass errors. If a hook fails on a file outside the plan's scope, STOP and report per OR16 — do not edit `.pre-commit-config.yaml` to exclude the file. The correct response is either: (a) fix the error if it's in-scope, (b) STOP and report if it's out-of-scope, or (c) use `$env:SKIP="<hook_id>"; git commit` (PowerShell syntax) for a single commit if the hook itself is broken. Never edit hook config to permanently exclude files. (Source: landmine L12 — Plan 73 execution, Devin attempted to exclude core/task_state_machine.py from mypy hook instead of fixing the type errors)

### Task list discipline (REVISED — Governance Directive 01)
OR34. Execute plan steps in strict numerical order (S0 → S1 → S2 → ... → Sn). Do not START a later step until the current step is complete. Do not MARK a task complete based on work done in a different section — a task is complete only when its corresponding plan section is fully executed in order. If S0 (opening) edits a governance doc and S6 (plan body) also edits the same doc, completing S0 does NOT complete S6, and you must not start S6 until S1-S5 are done. If a step is blocked, STOP and report — do not jump ahead to a later step. (Source: landmine L17 — Plan 76 execution; revised by Governance Directive 01 to prohibit starting out of order, not just marking complete out of order)

### Git output discipline (NEW — Governance Directive 01)
OR35. Use token-efficient git commands to reduce context consumption:
- Use `git status -s` (short format) for routine checks, NOT `git status` (full format). Short format returns one line per changed file.
- Use `git diff --stat` for overview, NOT `git diff` (full diff). Only use full `git diff` when you need to see specific line changes.
- Use `git log --oneline -N` (with count limit, e.g., `-5`), NEVER bare `git log`.
- Pipe all git output through `Select-Object -Last N` to truncate: `git status -s | Select-Object -Last 10`
- If output is needed in full (e.g., diagnosing a specific issue), note why before running the full command.

### PowerShell output discipline (NEW — Governance Directive 01)
OR36. Minimize PowerShell output to reduce context token consumption:
- Always pipe command output through `Select-Object -Last N` (default N=5 unless more is needed).
- For multi-command verification, chain with `;` and capture only the final summary line.
- Never run a command that produces >20 lines of output without truncation.
- For pre-commit hooks: run with `2>&1 | Select-Object -Last 10` to capture only pass/fail summary. If a hook fails, re-run that specific hook without truncation to see full output.
- For pytest: always use `-q --tb=short` flags. For targeted tests with `-v`, pipe through `Select-Object -Last 20`.
- For ruff/mypy: pipe through `Select-Object -Last 3` — you only need the error count.


### Batch verification (RENUMBERED — Governance Patch 03)
OR37. Batch verification commands to reduce the number of separate command executions and output blocks:
- Instead of running 6 separate verification commands (syntax, ruff, mypy, detect-secrets, vulture, tests), chain them with `;` and capture only the final summary.
- Example: `python -c "import ast; ast.parse(open('file.py').read())" ; ruff check file.py ; mypy file.py --ignore-missing-imports ; echo "---CHECKS DONE---" 2>&1 | Select-Object -Last 5`
- If any check fails, the failure will appear in the last 5 lines. Then re-run the failing check individually for full output.
- This reduces 6 Devin actions + 6 output blocks to 1 Devin action + 1 output block.

### Prompt Creator Prompts directory hygiene (REVISED — Governance Patch 04)
OR38. At decade boundary tags (prompt-{N}0 where N > 0, e.g., prompt-80, prompt-90), delete the previous decade's plan files from `GLM Prompts/` directory. Delete files matching `plan-{previous_decade}*` (e.g., at prompt-80, delete plan-70* through plan-79*; at prompt-90, delete plan-80* through plan-89*). Commit the deletions as part of the decade boundary plan's docs commit (C12). This prevents the directory from growing unbounded and avoids "deleted files reappear" cycles. Do NOT delete governance directives, governance patches, or the current decade's files.

**Catch-up clause** (revised at Governance Patch 04): if `GLM Prompts/` contains files from decade N-2 or earlier at any plan's opening (S0.1), where N is the current decade, delete them at that opening as a `docs: cleanup pre-{tag}` commit per OR26. Files from the immediately previous decade (N-1) are NOT eligible for catch-up deletion — wait for the decade boundary. Example: at prompt-75 (N=70s), files from the 50s or earlier (N-2=50s) are eligible for catch-up; files from the 60s (N-1=60s) are NOT — wait for prompt-80.

**Decade definition**: the decade is determined by the tens digit of the prompt number. prompt-70 through prompt-79 = 70s decade. prompt-80 through prompt-89 = 80s decade. Named plans (e.g., `ar18-fix-all`, `rule-cleanup`) inherit the decade of their predecessor tag.

(Source: Prompt Creator observation; revised at Governance Patch 04 to disambiguate "2+ decades ago" which was misinterpreted as "previous decade" during ar18-fix-all execution, causing premature deletion of 60s files at 70s opening. Original language from Governance Patch 03.)

### Plan file retention (NEW — Governance Patch 04)
OR39. Plan files (`plan-{N}.md`, `plan-{N}-Rev{n}.md`, `plan-{N}-Rev{n}-context-brief.md`, `plan-{N}-context-brief.md`) MUST be committed to git. The current plan's files MUST be added in the C12 docs commit (`git add CHANGELOG.md PLANS.md LANDMINES.md "GLM Prompts/plan-{N}*.md"`). Plan files from previous plans discovered untracked at /jarvis-open (S0.1) are an OR26 violation — commit them as `docs: cleanup pre-{tag}` with tag `docs-cleanup-{N}` before proceeding. Plan files are part of the project record; they document what Devin executed against. Losing them to git history gaps makes retroactive review impossible. (Source: L20 — plan files for prompts 72-77 were never committed to git; only 70 and 71 were. The CHANGELOG and PLANS.md document what those plans did, but the actual plan files are lost to git.)

---

## Landmines that have graduated to rules

This section maps landmines to their corresponding rules.

| Landmine | Rule | Problem |
|---|---|---|
| L1 | OR5 | replace_all corrupts adjacent lines |
| L2 | OR3 | Parallel scan tools corrupt output streams |
| L3 | OR7 | PowerShell -replace corrupts structured markdown |
| L4 | OR13 | Temp files left in repo root get committed |
| L5 | OR19 | Vulture flags unused test fixtures incorrectly |
| L6 | OR20 | Naive/aware datetime mixing |
| L7 | OR17 | Stale baselines propagate through plans |
| L8 | OR16, OR22 | Scope drift: editing files outside declared scope |
| L10 | OR28 | Devin leaves zombie PowerShell processes after execution |
| L11 | OR32 | Devin bypassed pre-commit hooks with --no-verify |
| L12 | OR33 | Hiding type errors by excluding files from hooks |

---

## Reading and writing LANDMINES.md

**When to read LANDMINES.md**:
- Prompt Creator Workflow Step 3: re-read landmines before creating new plan
- Devin (on-demand): if an AGENTS.md rule's application is ambiguous, read the source landmine for diagnostic context

**When to write LANDMINES.md** (at C11, closing step 11):

Capture new failure patterns using this format:

```markdown
## L{n} — <one-line title of the failure pattern>

**Trigger**: <Plan #, step, specific command/file/context — be concrete>

**Impact**: <What broke as a result>
```

Keep entries concise — trigger and impact only. No narrative, no cross-references to other plans. No proposed fixes or rules — those come from AGENTS.md.

**Process for graduating a landmine to a rule**:
1. Devin captures L{n} at C11 (closing step 11)
2. Prompt Creator reviews at Workflow Step 4 and proposes rule OR{m} or VR{m}
3. Devin adds rule to AGENTS.md at S0.3 of next plan with source reference: "OR{m}. <rule statement> (Source: L{n})"
4. Rule is live; Devin complies with it going forward

LANDMINES.md is append-only — entries are never edited or removed after capture.
