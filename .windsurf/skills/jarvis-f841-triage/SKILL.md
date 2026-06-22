---
name: jarvis-f841-triage
description: "Use when triaging ruff F841 unused-variable findings before applying fixes. Classifies into Category A (safe), B (manual — side effects), or C (defer — framework). Must run before any --fix --unsafe-fixes."
---

# Jarvis F841 Triage — Unused Variable Classification

## When to use

When ruff reports F841 (unused-variable) findings. The unsafe fix removes the variable assignment, but the RHS might have side effects.

## Procedure

### Step 1: List all F841 findings

```powershell
ruff check . --select F841 2>&1
```

### Step 2: For EACH finding, read the line and classify

**Category A — Safe to auto-fix**: RHS is TRULY pure (literal, simple variable, no function calls, no property access). One-line manual scan of each RHS required.

**Category B — Manual fix**: RHS has side effects (function calls, trace emissions, method calls). Fix: remove `variable = `, keep the RHS expression.

**Category C — Defer**: might be needed by framework (pytest fixture, middleware, pydantic validator). Check three contexts:
1. `@pytest.fixture` decorator?
2. Middleware chain consumption?
3. Pydantic validator enforced at runtime?
If any: keep, add `# noqa: F841 -- <reason>`.

### Step 3: Apply fixes (AFTER triage, not before)

**Category A**: `ruff check . --select F841 --fix --unsafe-fixes` (only after confirming all A are truly pure)

**Category B**: edit each individually (NEVER `replace_all`). Remove `variable = `, keep RHS.

**Category C**: add `# noqa: F841 -- <reason>`

### Step 4: Syntax check + diff + tests

```powershell
git diff --name-only | ForEach-Object { python -c "import ast; ast.parse(open('$_').read())" 2>&1 }
git diff --stat
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

### Step 5: Document suppressions in CHANGELOG

```
Suppressions added:
- # noqa: F841 x<N> — <reason per finding>
```

## Critical reminders

- **Triage is mandatory** (Step 2). Do NOT skip to `--fix --unsafe-fixes`.
- **Never use `replace_all`** for Category B.
- **One-line manual scan of each RHS** for Category A — don't trust ruff alone.
