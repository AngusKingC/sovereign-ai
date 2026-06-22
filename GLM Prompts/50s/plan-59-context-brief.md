# Plan 59 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-22
**Plan**: 59 — Ruff cleanup (113→0) + B108 scoped suppressions (FRESH DRAFT, post-58.7)

---

## What's different from the previous Plan 59

This is a **fresh rewrite** of Plan 59. The previous version (REV3) was approved by Claude but never executed. Since then:
- Plan 58.5, 58.6, 58.7 completed (datetime fully fixed, L19 compliant)
- Devin Desktop config installed (AGENTS.md, workflows, skills)
- L26 added (grep datetime.utcnow without parens — from Devin's C9 in Plan 58.7)
- Baseline changed: 113 ruff (was 112), 1166/56 tests (was 1167/55)
- Claude's review of Plan 58.6 identified 2 specific fixes now folded into this plan:
  - schemas.py E402: move import instead of suppressing
  - notification.py F821: use TYPE_CHECKING guard instead of noqa

## What this plan does

1. **S2**: Safe auto-fix (20 errors: F541 x15, F401 x2, F811 x3)
2. **S3**: F841 unsafe auto-fix with A/B/C triage (47 errors) — `jarvis-f841-triage` skill auto-invokes
3. **S4**: Manual fixes (46 errors: E402 x22, F821 x22, E731 x1, E741 x1) — includes the 2 specific fixes from Claude's 58.6 review
4. **S5**: B108 scoped `# nosec B108` annotations (22 findings) — `jarvis-b108-suppress` skill auto-invokes + remove CI `-s B108` flag
5. **Closing**: Run `/jarvis-close` workflow (first plan using the new Devin Desktop config)

## Ruff breakdown (verified via clone on master post-58.7)

| Rule | Count | Fix type | Risk |
|---|---|---|---|
| F841 | 47 | Unsafe auto-fix | Medium — RHS may have side effects |
| E402 | 22 | Manual (move import or suppress) | Low |
| F821 | 22 | Manual (missing import, typo, TYPE_CHECKING) | **High — may be real bugs** |
| F541 | 15 | Safe auto-fix | None |
| F811 | 3 | Safe auto-fix | None |
| F401 | 2 | Safe auto-fix | None |
| E731 | 1 | Manual (lambda→def) | Low |
| E741 | 1 | Manual (rename var) | Low |
| **Total** | **113** | | |

## Specific fixes folded in from Claude's Plan 58.6 review

1. **schemas.py line 442 E402**: the `from typing import Protocol, runtime_checkable` mid-file should be moved to the existing import block at line 10. Change `from typing import Any, Optional` → `from typing import Any, Optional, Protocol, runtime_checkable` at line 10, delete line 442, remove the `# noqa: E402`.

2. **notification.py line 54 F821**: `TelegramGateway` type annotation is unresolvable (core/ can't import from gateways/ per architecture rule 16). Use TYPE_CHECKING guard instead of `# noqa: F821`:
   ```python
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from gateways.telegram.gateway import TelegramGateway
   ```

## Baselines

- **Tests**: 1166 passed, 56 skipped (check AGENTS.md for latest)
- **Ruff**: 113 errors
- **B108**: 22 findings (CI skips via `-s B108`)
- **prompt-58.7 tag on origin**: `66315df` ✅ verified

## First plan using Devin Desktop config

This plan references:
- `/jarvis-close` workflow for closing sequence (C1-C13)
- `/jarvis-verify` workflow for post-edit checks
- `jarvis-b108-suppress` skill (auto-invoked on B108 work)
- `jarvis-f841-triage` skill (auto-invoked on F841 work)
- AGENTS.md rules 1-21 (always-on, don't need to paste in Section 0)

## Review focus for Claude

1. **Is the Section 0 slimming correct?** Section 0 now says "AGENTS.md is active, don't repeat stable rules" and only lists L1-L26 (evolving rules). The 22 stable rules are in AGENTS.md (always-on). Is this the right split, or should stable rules still be in Section 0 as a backup?

2. **Is the F821 decision procedure still sound?** Same 3-step procedure as before (grep file, grep codebase, classify). Two specific F821 fixes from Claude's 58.6 review are now included. Any others to flag?

3. **Is the CI `-s B108` removal (S5.5) correct?** After 22 scoped suppressions, the blanket skip becomes redundant. Remove it so bandit checks B108 going forward (fail loudly on new violations).

4. **Is the F841 triage still adequate?** Same A/B/C categories, same mandatory per-finding review before `--fix --unsafe-fixes`. The `jarvis-f841-triage` skill handles this automatically now.

5. **Are the 2 specific fixes (schemas.py E402, notification.py F821) correctly specified?** These come from Claude's own review of Plan 58.6 — just confirming they're folded in correctly.

6. **Is the `/jarvis-close` reference sufficient for the closing sequence?** The plan says "Run `/jarvis-close` with tag prompt-59" instead of repeating C1-C13 inline. The workflow file has the full sequence. Is this the right level of delegation, or should the plan still list the steps inline as a backup?
