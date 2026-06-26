---
name: jarvis-scan
description: "Run the 6-tool full checkpoint scan SEQUENTIALLY (never in parallel). Use at 5-plan milestones (55, 60, 65, 70, 75, 80) or when a full baseline is needed. Each tool runs alone, output captured, before the next starts."
---

# Jarvis Scan — Sequential Full Checkpoint Scan

**CRITICAL (L24)**: run each tool ONE AT A TIME. Parallel execution corrupts output streams and produces wrong counts. Plan 55 reported "37 CVEs" when actual was 55 because 6 tools ran in parallel.

## Tool 1: pytest (full suite)

```bash
python -m pytest tests/ -vvv
```

**Note**: Do NOT use `-q --tb=short` or pipe to `tail -n 5`. Run with full verbose output (`-vvv`) so hangs, stuck tests, and failure details are all visible.

Wait for completion. Record: `<N> passed, <M> skipped`. Expected: check PLANS.md for current baseline.

## Tool 2: ruff (full-repo)

```bash
ruff check . 2>&1 | tail -n 5
```

Wait for completion. Record: `Found <N> errors.` Get breakdown:
```bash
ruff check . --statistics 2>&1
```

## Tool 3: mypy (full-repo — ONLY at 5-plan checkpoints)

```bash
mypy . --ignore-missing-imports 2>&1 | tail -n 5
```

**This is the ONLY time `mypy .` is allowed.** All other plans use file-scoped mypy only. This will take 2-5 minutes. Wait for completion. Record: `Found <N> errors in <M> files.`

## Tool 4: bandit (full-repo)

```bash
bandit -r . -ll --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache,globalrules 2>&1 | tail -n 10
```

Wait for completion. Record severity breakdown. B108 should be 0 (suppressed via scoped `# nosec B108` annotations per Plan 59).

## Tool 5: pip-audit

```bash
pip-audit 2>&1 | tail -n 10
```

Wait for completion. Record: `Found <N> known vulnerabilities in <M> packages.`

## Tool 6: vulture

```bash
vulture . --min-confidence 80 --exclude .venv,venv,env,.git,node_modules,__pycache__,build,dist,.tox,.eggs,.pytest_cache 2>&1 | tail -n 10
```

Wait for completion. Record: `<N> high-confidence findings.`

## Compile summary

After ALL 6 tools complete (do NOT compile mid-scan), create a summary:
```bash
cat > C:\\Jarvis\\scan\\logs\\checkpoint-scan.md << 'EOF'
## Full Checkpoint Scan Results

**Date**: <YYYY-MM-DD>
**Tests**: <tool 1 result>
**Ruff**: <tool 2 result> errors
**Mypy (full-repo)**: <tool 3 result> errors
**Bandit**: <tool 4 result>
**pip-audit**: <tool 5 result> CVEs
**Vulture**: <tool 6 result> findings
EOF
cat C:\\Jarvis\\scan\\logs\\checkpoint-scan.md
```

These become the fresh baselines for the next 5 plans.
