---
name: jarvis-scan
description: "Run the 6-tool full checkpoint scan SEQUENTIALLY (never in parallel). Use at 5-plan milestones (55, 60, 65, 70, 75, 80) or when a full baseline is needed. Each tool runs alone, output captured, before the next starts."
---

# Jarvis Scan — Sequential Full Checkpoint Scan

**CRITICAL (L24)**: run each tool ONE AT A TIME. Parallel execution corrupts output streams and produces wrong counts. Plan 55 reported "37 CVEs" when actual was 55 because 6 tools ran in parallel.

## Tool 1: pytest (full suite)

```powershell
python -m pytest tests/ -q --tb=short | Select-Object -Last 5
```

Wait for completion. Record: `<N> passed, <M> skipped`. Expected: `1167 passed, 55 skipped`.

## Tool 2: ruff (full-repo)

```powershell
ruff check . 2>&1 | Select-Object -Last 5
```

Wait for completion. Record: `Found <N> errors.` Get breakdown:
```powershell
ruff check . --statistics 2>&1
```

## Tool 3: mypy (full-repo — ONLY at 5-plan checkpoints)

```powershell
mypy . --ignore-missing-imports 2>&1 | Select-Object -Last 5
```

**This is the ONLY time `mypy .` is allowed.** All other plans use file-scoped mypy only. This will take 2-5 minutes. Wait for completion. Record: `Found <N> errors in <M> files.`

## Tool 4: bandit (full-repo)

```powershell
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache,globalrules 2>&1 | Select-Object -Last 10
```

Wait for completion. Record severity breakdown. B108 should be 0 (suppressed via scoped `# nosec B108` annotations per Plan 59).

## Tool 5: pip-audit

```powershell
pip-audit 2>&1 | Select-Object -Last 10
```

Wait for completion. Record: `Found <N> known vulnerabilities in <M> packages.`

## Tool 6: vulture

```powershell
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | Select-Object -Last 10
```

Wait for completion. Record: `<N> high-confidence findings.`

## Compile summary

After ALL 6 tools complete (do NOT compile mid-scan), create a summary:
```powershell
$summary = @(
    "## Full Checkpoint Scan Results",
    "",
    "**Date**: 2026-06-21",
    "**Tests**: <tool 1 result>",
    "**Ruff**: <tool 2 result> errors",
    "**Mypy (full-repo)**: <tool 3 result> errors",
    "**Bandit**: <tool 4 result>",
    "**pip-audit**: <tool 5 result> CVEs",
    "**Vulture**: <tool 6 result> findings"
)
Set-Content -Path "C:\Jarvis\scan\logs\checkpoint-scan.md" -Value $summary -Encoding utf8
Get-Content C:\Jarvis\scan\logs\checkpoint-scan.md
```

These become the fresh baselines for the next 5 plans.
