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

**Trigger**: Plan 60, S2.2 used `ForEach-Object` over `---` separators in SOVEREIGN_AI_HANDOFF.md — inserted the prompt-59 row 5 times. Plan 60, S3.1 used `-replace` chains on AGENTS.md — left duplicate landmine naming entries (later consolidated into L{n} scheme).

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
