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
