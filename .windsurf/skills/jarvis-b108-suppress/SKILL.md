---
name: jarvis-b108-suppress
description: "Use when suppressing bandit B108 findings in test files. Handles exact line-number placement, scoped nosec format, and replace_all ban."
---

# Jarvis B108 Suppress — Scoped Bandit B108 Suppression

## When to use

When bandit finds B108 (hardcoded_tmp_directory) findings in test files. These are typically `/tmp` paths in test fixtures that are safe for local-first single-user context.

## Procedure

### Step 1: Get exact line numbers from bandit

```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108"
```

Bandit reports findings on the line containing the actual string literal, NOT the line with the function call opener.

### Step 2: For EACH finding, read the exact line

```powershell
Get-Content <file> | Select-Object -Skip (<line_number> - 1) -First 1
```

### Step 3: Add scoped `# nosec B108` annotation

On the EXACT line bandit reports, append:
```
  # nosec B108 -- local-first; test fixture path
```

**Example**:
```python
# Before:
            scope_pattern="/tmp/*",

# After:
            scope_pattern="/tmp/*",  # nosec B108 -- local-first; test fixture path
```

### Step 4: Edit each occurrence INDIVIDUALLY

**NEVER use `replace_all`.** Edit each line by its specific line number.

### Step 5: Verify all B108 findings suppressed

```powershell
bandit -r tests/ -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-String "B108" | Measure-Object -Line
```

Expected: `0`. If any remain, the `# nosec B108` wasn't placed on the correct line.

### Step 6: Syntax check + tests

```powershell
git diff --name-only | ForEach-Object { python -c "import ast; ast.parse(open('$_').read())" 2>&1 }
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

### Step 7: Document in CHANGELOG

```
Suppressions added:
- # nosec B108 x<N> — local-first; test fixture paths (<files>)
```

## Suppression tool confusion warning

- `# noqa: RULE` controls ruff only
- `# nosec RULE` controls bandit only
- `# type: ignore[code]` controls mypy only
- Writing `# noqa: B108` does NOTHING for bandit
- Always use `# nosec B108` for bandit B108 findings
