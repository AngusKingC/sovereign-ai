# LANDMINES.md — Sovereign AI Failure Patterns

Append-only historical record of failure patterns. See AGENTS.md for guidance on reading and writing entries.

---

## L1 — replace_all corrupts adjacent lines

**Trigger**: Plan 58, files `a2a_protocol.py` and `escalation.py` — used `replace_all` which mangled adjacent lines.

**Impact**: File corruption, had to revert and re-edit manually. Loss of time, risk of silent corruption if not caught.

---

## L2 — Parallel scan tools corrupt output streams

**Trigger**: Plan 55, ran 6 tools in parallel (pytest, ruff, mypy, bandit, pip-audit, vulture) — output streams mixed, reported "37 CVEs" when actual was 55.

**Impact**: Wrong baseline propagated to HANDOFF.md. Incorrect project state tracking. Cascade of stale counts in subsequent plans.

---

## L3 — PowerShell -replace corrupts structured markdown

**Trigger**: Plan 60, S2.2 used `ForEach-Object` over `---` separators in AI_HANDOFF.md — inserted the prompt-59 row 5 times. Plan 60, S3.1 used `-replace` chains on AGENTS.md — left duplicate landmine naming entries (later consolidated into L{n} scheme).

**Impact**: File corruption in critical documentation. Handoff became unreadable, had to manually repair. Risk of corruption propagating through multiple files.

---

## L4 — Temp files left in repo root get committed

**Trigger**: Multiple plans, temp files created during closing sequence (CHANGELOG temp files, scan logs) left in repo root or forgotten in `C:\Jarvis\` root instead of `C:\Jarvis\temp\` or `C:\Jarvis\scan\logs\`.

**Impact**: Stray files polluted git working tree, got committed accidentally, cluttered repo. Had to clean up commits retroactively.

---

## L5 — Vulture flags unused test fixtures incorrectly

**Trigger**: Plan {N}, vulture flagged test fixture parameters as unused even though pytest/middleware/pydantic required them via decorator context.

**Impact**: False positive in vulture scan. Developer tempted to remove "unused" parameters, which breaks tests. Risk of silent test failures if parameter is removed without understanding decorator.

---

## L6 — Naive/aware datetime mixing

**Trigger**: Multiple plans, code mixed `datetime.utcnow()` (naive) with `datetime.now(timezone.utc)` (aware), or used `default_factory=datetime.utcnow` (function reference without parentheses, returns the function object, not a datetime).

**Impact**: Runtime errors, comparison failures between naive and aware datetimes. Silent bugs in serialization/deserialization.

---

## L7 — Stale baselines propagate through plans

**Trigger**: Plan {N}, S1 actual counts differ from plan's expected counts (from 5+ plans ago), but Devin proceeded silently instead of updating PLANS.md baseline.

**Impact**: Wrong scope projections in subsequent plans. Handoff baseline drifts further from reality. Difficult to diagnose which plan introduced the divergence.

---

## L8 — Scope drift: editing files outside declared scope

**Trigger**: Plan {N}, Devin discovered work that needed doing outside the plan's declared scope but fixed it unilaterally ("it's just a 1-line fix").

**Impact**: Scope creep, untracked changes, makes it hard to isolate what a plan actually accomplished. Plan becomes a grab-bag of unrelated fixes.

---

## L9 — Runtime type changes for mypy break test assertions

**Trigger**: Plan 64, Devin changed runtime types (wrapping dicts as Message objects, changing string returns to enum values) to satisfy mypy. Tests asserting on dict-like access or string values broke.

**Impact**: 2 failed test rounds, time lost reverting. Fix: per OR27, add compatibility shims that preserve old runtime behavior while satisfying type checker. Never change runtime types in type-remediation plans without verifying test assertions first.

---

## L10 — Devin leaves zombie PowerShell processes after execution

**Trigger**: Plans 64-66 execution, Devin spawned hundreds of PowerShell processes without exiting them. Each command execution created a new session that was never disposed.

**Impact**: Memory exhaustion, handle exhaustion, system instability. User's PC became sluggish with hundreds of orphaned PowerShell processes consuming resources.

---

## L11 — Devin bypassed pre-commit hooks with --no-verify

**Trigger**: Plan 71 execution, Devin used `git commit --no-verify` on both the checkpoint commit (72e2aa6) and the docs commit, bypassing the pre-commit hooks that Plan 71 had just configured.

**Impact**: Hooks configured but never actually run. Issues that hooks would catch (trailing whitespace, secrets, etc.) slip through. Defeats the purpose of having pre-commit hooks as a quality gate.

---

## L12 — Hiding type errors instead of fixing them

**Trigger**: Plan 73 execution, Devin attempted to exclude core/task_state_machine.py from mypy pre-commit hook to bypass pre-existing type errors, instead of fixing the errors with proper type annotations (cast(), type hints).

**Impact**: Type errors accumulate, making the codebase progressively harder to maintain. Hiding errors defeats the purpose of type checking. The correct fix is to add proper type annotations, not to exclude files from type checking.

---

## L15 — Vulture whitelist file encoding + CLI syntax bugs

**Trigger**: Plan 72 created vulture-whitelist.txt via PowerShell `>` redirection (defaults to UTF-16), which vulture couldn't read. Workflow docs used `vulture <paths> vulture-whitelist.txt` syntax, but vulture treats the file as a PATH to scan, not a whitelist.

**Impact**: Vulture whitelist check silently passed (command errored, but `continue-on-error: true` in CI masked it) — new dead code wasn't caught for Plans 72-74.5. CI vulture job failed continuously but the root cause wasn't diagnosed until Plan 75.

---

## L16 — Removing pre-commit hook without transferring dependencies

**Trigger**: Plan 74 removed mypy pre-commit hook (which had types-PyYAML in additional_dependencies) but didn't add types-PyYAML to requirements-dev.txt. Plan 75 full-repo mypy scan failed on test_setup_wizard.py:111 (missing yaml stubs).

**Impact**: Type stub dependencies were lost when hook was removed, causing silent mypy regressions. The gap was invisible between Plans 74-74.5 because pre-commit no longer ran mypy. CI may not have caught it if CI mypy job also used the hook's additional_dependencies.

---

## L17 — Devin marks task list items complete based on file edits, not plan section completion

**Trigger**: Plan 76 execution, Devin completed S0 (opening sequence, which included governance doc commits per S0.4-S0.6 of the plan). Devin then marked S6, S7, S8 (plan body governance sections) as complete — even though S1-S5 (code implementation) were not yet started. The task list showed "1, 6, 7, 8 complete" when only S0 was actually done. Devin conflated "I edited AI_HANDOFF.md at S0.4" with "I completed S6 (Update AI_HANDOFF.md)."

**Impact**: Task list progress is misleading. User sees governance tasks "complete" and assumes Devin skipped code implementation. Makes it impossible to track actual plan progress. Could lead to premature closing if Devin trusts the task list over the plan section order.

**Mitigation**: OR34 (execute steps in strict numerical order, do not start a later step until current is complete).

---

## L18 — CRLF line ending mismatch causes vulture line number drift

**Trigger**: Plan rule-cleanup, vulture reported core/event_trigger.py:107 for last_check_time, but the whitelist had line 88. Investigation revealed the file has 312 lines (CRLF) on Windows but git shows 263 lines (LF). The line number difference (107 vs 88) is exactly the CRLF line count delta (312 - 263 = 49 lines; 107 - 88 = 19, but the actual shift is due to how line endings affect line counting in different tools).

**Impact**: Vulture reports line numbers that don't match git HEAD or the whitelist. Pre-commit hooks fail because the whitelist entry doesn't match the reported line number. Requires adding both line number variants to the whitelist (LF and CRLF versions) to pass on Windows.

**Mitigation**: When vulture reports a line number that doesn't match the whitelist on Windows, check if the file has CRLF line endings (git config core.autocrlf true). Add both line number variants to the whitelist if necessary. Use .NET UTF8Encoding API (without BOM) for temp file writes to avoid encoding issues.

---

## L20 — Plan files not committed to git, creating history gaps (RETROACTIVE)

**Note**: This landmine is a RETROACTIVE capture. The events (plans 72-77 not committed to git) occurred during prompts 72-77 but were never recorded as a landmine at the time. Identified during governance-patch-04 review of the ar18-fix-all/rule-cleanup retrospective. Future audits should not treat L20 as a contemporaneous observation — it's a backward-looking capture of a gap that existed from prompt-71 onward.

**Trigger**: Plans 72-77 executed between prompt-71 and prompt-77. Plan files (`plan-72.md`, `plan-73.md`, `plan-74.md`, `plan-74.5.md`, `plan-75.md`, `plan-76.md`, `plan-77.md` + context briefs) were created in Devin's working tree (`c:\Jarvis\Prompts\`) but never `git add`ed. At prompt-77's Prompts/ listing, only plan-61 through plan-71 were tracked. ar18-fix-all then deleted plan-61 through plan-69 (catch-up cleanup), leaving only plan-70 and plan-71 in git history. Plans 72-77 are documented in CHANGELOG/PLANS.md but the actual plan files are lost.

**Impact**: Retroactive review of plans 72-77 is impossible — the instructions Devin followed cannot be inspected. If a bug is traced back to a specific plan's instructions, there's nothing to review. The git history is incomplete for 6 plans. Future plans that reference "the pattern established in plan-72" have no primary source to consult.

**Mitigation**: Two-prong approach:
1. (OR26) Plan files from PREVIOUS plans discovered untracked at /jarvis-open (S0.1) are an OR26 violation — commit them as `docs: cleanup pre-{tag}` with tag `docs-cleanup-{N}` before proceeding. This is the first line of defense: if untracked plans are discovered at opening, they must be cleaned up BEFORE the plan body executes.
2. (OR39) Plan files from the CURRENT plan MUST be added in C12 docs commit. jarvis-close.md Step 12 updated to explicitly add `Prompts/plan-{N}*.md` to `git add`. This is the second line of defense: even if OR26's opening check misses something, the closing check ensures the current plan's file is committed.

---

## L21 — PowerShell corrupts TypeScript files with backticks and template literals

**Trigger**: Plan 91, S10 verification — PowerShell commands used to write TypeScript files (`src/lib/api.ts`, `src/components/shell/Sidebar.tsx`, `src/components/shell/StatusBar.tsx`) corrupted the content. PowerShell interprets backticks (`) as escape characters and `${}` as variable expansion, which broke TypeScript template literals.

**Impact**: TypeScript compilation failed with numerous syntax errors (TS1109, TS1005, TS1128, TS2657, TS1127). Files had to be reverted multiple times. The Node.js writer script approach (array-of-strings + `.join('\n')`) was required to bypass PowerShell's string parsing.

**Mitigation**: OR38 — When writing TypeScript files on Windows, use Node.js writer scripts with the array-of-strings + `.join('\n')` pattern instead of PowerShell string operations. The Node.js approach sidesteps PowerShell's string parsing entirely by writing the file through a separate process.

---
