# Plan 70 — Context Brief for Claude Review

## What this plan does
5-plan milestone full scan (pytest, ruff, mypy, bandit, pip-audit, vulture). No code or doc changes — scan only, with baseline updates at closing.

## Key files to verify in review
- `.windsurf/workflows/jarvis-scan.md` — the canonical scan procedure (GLM plan must match this)
- `PLANS.md` — current baselines (test: 1253/67, ruff: 0, mypy: 0, bandit: 3179/0/0, pip-audit: 19, vulture: 23)
- `AGENTS.md` OR2 — file-scoped mypy except at 5-plan checkpoints (55, 60, 65, 70...)
- `AGENTS.md` OR3 — scan tools run ONE AT A TIME (Source: L2)

## Expected results
- Tests: 1253 passed, 67 skipped (±5)
- Ruff: 0 errors
- Mypy (full-repo): 0 errors (Plan 67 cleaned all 181 files)
- Bandit: ~3179 low, 0 medium, 0 high
- pip-audit: ~19 CVEs
- Vulture: ~23 findings

## Risks
- Mypy full-repo may find new errors if Plan 68 (skill taxonomy) or Plan 69 (init files) introduced untyped code — but both were mypy-clean at file scope
- pip-audit count may shift if dependency versions changed on Devin's machine since Plan 60
- vulture count may shift due to new modules from Plan 68 (skill_taxonomy.py, classifications.py)

## What Claude should check
1. Does the plan follow jarvis-scan.md exactly? (same tool order, same exclude flags, same output capture)
2. Is the queue shift correct? (Plan 72 tentative scan → open slot, new Plan 75 added)
3. Are the PLANS.md update instructions at C10 complete? (all 6 baselines, captured line, cadence next milestone)
4. Any missing verification steps or gaps in the scan procedure?
