# Sovereign AI — Devin Guidelines

**Always-active project rules. Read at the start of every session.**
For per-plan evolving rules (L1-L25+), read `## Section 0: Rules` at the top of the current plan file.

---

## Project context

- **What**: local-first, self-improving AI assistant framework (Python 3.11, Textual TUI + Rich CLI + FastAPI web server)
- **Workflow**: GLM drafts plans → Claude reviews → Devin executes → user relays results
- **Scale**: 14 LLM adapters, ~237 files, ~32,694 LOC, ~1167 tests
- **Repo**: https://github.com/AngusKingC/sovereign-ai
- **OS**: Windows (PowerShell, not Unix)

## Current state (post-Plan 58.6, as of 2026-06-22)

- **Tests**: 1166 passed, 56 skipped, 0 failed
- **Static analysis**: ruff 111, mypy 283, vulture 20, pip-audit 19 CVEs, bandit 0 high (B108 skipped via CI)
- **datetime**: `datetime.utcnow()` = 0 in core/ (Plans 58+58.6 fixed), 46 remaining in system/+skills/ (Plan 58.7 in progress). bare `datetime.now()` = 0 (Plan 58.5 fixed)
- **Plan cadence**: 5-plan milestones with full scans (Plans 55, 60, 65, 70, 75, 80)

## Optimized queue to core complete (24 plans)

1. **Phase 1** (current debt): Plan 58.7 (utcnow in system/skills — in progress), 59 (ruff + B108), 60 (full scan)
2. **Phase 2** (measurement layer): 61 (trace store), 62 (eval harness), 62.5 (eval validation), 63a (improvement loop wire), 63b (improvement loop validate)
3. **Phase 3** (user-facing): 64-65 (Postgres persistence)
4. **Phase 4** (debt with measurement): 66-74 (mypy batches with eval gates)
5. **Phase 5** (wire dormant subsystems): 75-80 (MonitorDaemon, MemoryCompactor, TriggerEngine, ResourceBudget, VerbosityManager, TrajectoryExporter)

**Deferred indefinitely**: Marine stack Python, horizontal capabilities (Telegram/Voice/Retention), sandboxed execution, function-calling loop, Docker deployment.

---

## Stable rules (ALWAYS follow — these don't change between plans)

### Environment
1. **PowerShell only.** Never use `grep`, `cat`, `sed`, `awk`, `head`, `tail`, `touch`. Use `Select-String`, `Get-Content`, `Set-Content`, `Add-Content`, `Get-ChildItem`, `Measure-Object`, `Where-Object`, `ForEach-Object`.
2. **File-scoped mypy only.** Never `mypy .` — except in 5-plan checkpoint plans (55, 60, 65, 70, 75, 80) where full-repo mypy is the point.
3. **Sequential scans.** Run scan tools (pytest, ruff, mypy, bandit, pip-audit, vulture) ONE AT A TIME. Parallel execution corrupts output streams and produces wrong counts.
4. **Bandit finding count — use specific filter.** When counting bandit findings by ID (e.g., B108), filter on the literal `>> Issue: [B` pattern (the issue header line), not just the ID string. The ID appears in multiple line types per finding (issue header, "More Info" URL, and after suppression, "nosec encountered" warning lines), so `bandit ... | Select-String "B108" | Measure-Object -Line` overcounts by ~2x and triggers false-positive STOP conditions. Use:
   ```powershell
   bandit -r <scope> -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String ">> Issue: \[B108" | Measure-Object -Line
   ```
   Or read the `Total issues (by severity):` summary line at the end of bandit output for the authoritative medium/high counts.

### Edit discipline
5. **Never use `replace_all`.** It corrupted `a2a_protocol.py` and `escalation.py` in Plan 58 by mangling adjacent lines. Edit each occurrence individually or use targeted line-specific replacements.
6. **Syntax check after every file edit, BEFORE tests:**
   ```powershell
   python -c "import ast; ast.parse(open('file.py').read())"
   ```
   If syntax error, STOP — fix before proceeding. Don't wait 90 seconds for tests to catch it.
7. **Structured-markdown edits — Edit tool only.** When editing `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, plan files in `GLM Prompts/`, or `CHANGELOG.md`, use the Edit tool with exact `old_str`/`new_str` pairs. NEVER use PowerShell `-replace`, `ForEach-Object`, or `Set-Content` for structured markdown — these have corrupted the handoff (Plan 60 S2.2 `ForEach-Object` over `---` separators inserted the prompt-59 row 5 times; Plan 60 S3.1 `-replace` chains left duplicate L24/M24 and L25/M25 entries). If the plan provides exact `old_str`/`new_str` pairs, use them as-is. If the plan provides only prose instructions, STOP and request GLM guidance via user.
8. **Diff check after every file edit:**
   ```powershell
   git diff --stat <file>
   ```
   Confirm only intended files changed. If unexpected files appear, STOP.

### Git discipline
9. **Tag EVERY prompt.** Even docs-only plans must have `git tag prompt-{N}`. Tag the docs commit if no code commit exists. (Plan 56 skipped this — caused verification failure.)
10. **Tag verification before push:**
   ```powershell
   git tag --list prompt-{N}
   ```
   If empty, tag wasn't created. Create it before proceeding to push.
11. **Post-push verification (mandatory):**
    ```powershell
    git ls-remote --tags origin | Select-String "prompt-{N}"
    ```
    If empty, push failed. Fix before reporting completion.

### CHANGELOG discipline
12. **Append to END only.** Never insert at the top. Oldest entry at top, newest at bottom.
13. **Use temp-file pattern** (not here-strings, which hang when auto-indented):
    ```powershell
    $lines = @("...", "...")
    Set-Content -Path $temp -Value $lines -Encoding utf8
    Get-Content $temp | Add-Content -Path "C:\Jarvis\CHANGELOG.md" -Encoding utf8
    ```
14. **Simplified format**: ~10-15 lines per entry. Title, changed files, results, test count math. No fluff.

### Scope discipline
15. **Pre-declare scope before editing.** List files you WILL edit and files you will NOT edit. Any file outside the "will edit" list requires STOP and GLM authorization.
16. **HARD STOP on scope expansion.** If you discover work that needs doing outside the plan's scope, STOP and report. Do not fix it unilaterally — even if it looks like a 1-line fix. (Plan 58's two HARD STOPs worked correctly: 1 authorized, 1 deferred.)
17. **Baseline reconciliation.** If S1 actual count ≠ plan's expected count, you MUST update the handoff baseline in C10 with the actual number + reason for the difference. Don't let stale baselines propagate.

### Architecture (never violate)
18. `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, or `system/`.
19. `TraceEmitter` via constructor injection only. Never use the global `emit_trace()` function.
20. No raw LLM calls outside `adapters/`.
21. No memory access outside `MemoryRouter`.
22. All I/O operations are async.

### Temp file discipline
23. **Temp files go in `C:\Jarvis\temp\` or `C:\Jarvis\scan\logs\`, NOT repo root.** After the temp file's content has been appended to CHANGELOG.md (or wherever it's consumed), DELETE the temp file. Never leave temp files in repo root — they get committed accidentally and pollute the working tree.
    ```powershell
    # After appending temp file to CHANGELOG:
    Remove-Item "C:\Jarvis\temp\changelog-entry-prompt-{N}.md"
    ```
    Before any `git add`, check for stray temp files:
    ```powershell
    Get-ChildItem C:\Jarvis\*.md | Where-Object { $_.Name -match "changelog-entry|temp|tmp" }
    ```
    If any found, delete them before committing.

---

## Known landmines (learned the hard way)

- **L19**: never mix naive/aware `datetime`. Use `datetime.now(timezone.utc)` everywhere. Never `datetime.utcnow()` or bare `datetime.now()`. Two patterns to watch: `datetime.utcnow()` (direct call) and `default_factory=datetime.utcnow` (function reference without parentheses — use `default_factory=lambda: datetime.now(timezone.utc)` instead).
- **L24**: run scan tools sequentially. Plan 55 ran 6 tools in parallel — output streams mixed, reported "37 CVEs" when actual was 55. Wrong baseline propagated to handoff.
- **L25**: test fixture parameters may be required by pytest/middleware/pydantic even if vulture flags them as unused. Don't remove without checking decorator context.
- **Stale baselines**: always verify counts via grep at S1. The handoff's numbers may be from 5 plans ago. If actual ≠ expected, STOP and report — don't silently proceed with wrong scope.

---

## C9 rule-proposal discipline (L20 self-evolution)

Every plan's closing report MUST include either:

**Option A — propose a new rule:**
```
## Rule proposal for global_rules.md
Trigger: <what happened this prompt — concrete, with file + line>
Recurrence: <prompt numbers where this pattern bit, or "first occurrence">
Proposed rule: L{n+1}. <one-line statement>
Anchor: <prompt + file + line>
Why existing rules didn't catch it: <one line>
```

**Option B — explicit none WITH justification:**
```
## Rule proposal — none
Patterns considered this prompt:
- [pattern 1]: not rule-worthy because [reason]
- [pattern 2]: not rule-worthy because [reason]
```

**Silence is NOT acceptable.** "None" without listing patterns considered is also not acceptable. If you can't list at least 2 patterns you considered, you didn't reflect genuinely.

GLM may request re-reflection if the "none" justification is shallow.

---

## For per-plan evolving rules

Read `## Section 0: Rules` at the top of the current plan file. These rules grow over time via L20 self-evolution (Devin proposes via C9, GLM accepts/rejects). Current count: 25 rules (L1-L25). Check the plan's Section 0 for the latest version.

---

## Quick reference: plan execution flow

1. Read Section 0 of the plan file (evolving rules)
2. Read this AGENTS.md (stable rules) — already loaded
3. Execute S0 (opening verification: tag check, pull, HEAD check)
4. Execute S1-S5 (steps with verification gates + STOP conditions)
5. Execute C1-C13 (closing sequence: test, lint, commit, tag, docs, push, verify)
6. Submit C9 rule proposal (Option A or Option B with justification)
7. Paste all evidence per the completion checklist

**When in doubt, STOP and report.** Do not improvise. (L4)
