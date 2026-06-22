# Plan 55 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-21
**Plan**: 55 — Full checkpoint scan + Marine stack start (5-plan milestone)
**Pointer-based**: references handoff sections by pointer, doesn't copy content.

---

## What this plan does (2 things)

1. **Full checkpoint scan** — runs all 6 tools (pytest, ruff, mypy ., bandit -r, pip-audit, vulture) to establish fresh baselines for Plans 56-60. This is the ONLY plan where `mypy .` is allowed (L18 exception for 5-plan checkpoints).

2. **Marine stack start** — creates 4 SKILL.md files under `skills/marine/` (weather, AIS, tidal, passage_planner). These are spec-only (no Python) — implementation deferred to Plan 59. This is the first new horizontal capability since cognition-loop wiring.

## Why folded into one plan

5-plan milestones are checkpoint + forward motion. Scan alone is too small for a plan; Marine start alone doesn't need the scan. Combining gives the scan a purpose (fresh baselines for the new capability) and gives the Marine start a verification context.

## Baselines (from Plan 54 closing report + handoff)

- **Tests**: 1167 passed, 55 skipped, 0 failed
- **Ruff**: 111 errors (F401=0 since Plan 54)
- **Mypy**: 282 errors (file-scoped samples; full-repo count TBD this plan)
- **Bandit**: 22 B108 in tests/ (pre-existing, deferred)
- **pip-audit**: ~55 CVEs across ~14 packages
- **Vulture**: ~47 high-confidence findings
- **prompt-54 tag on origin**: `e90b44d` ✅ verified
- **master HEAD**: `32344c0` ✅ verified

## Section 0: Rules (NEW — inline approach)

Per user direction 2026-06-21: rules now travel inline with each plan as `## Section 0: Rules` at the top. No separate rules file to ship/update/verify. GLM maintains canonical content in `/home/z/my-project/download/global_rules_v2.md` (v2.2, 23 rules: L1-L23). Each plan's Section 0 is a copy.

**Devin's C9 rule proposal from Plan 54 was ACCEPTED**: L23 (verification gate scoping) is now in Section 0. This is the first successful L20 activation — Devin proposed a rule, GLM accepted it, it's now inline in Plan 55's Section 0.

The `/globalrules/` folder in the repo (committed in Plan 54) is now **reference-only**. Devin reads rules from Section 0 of the current plan, NOT from `/globalrules/global_rules.md`.

## Landmines relevant to this plan (reference handoff §Known landmines)

- **L5**: don't expand scope — scan + SKILL.md only, no Python implementation
- **L17**: closing steps C1-C13 mandatory, paste evidence
- **L18**: file-scoped mypy only — **EXCEPTION: this plan uses `mypy .` (5-plan checkpoint)**
- **L20**: self-evolution — C9 rule-proposal step MANDATORY
- **L21**: CHANGELOG append to END, temp-file pattern
- **L22**: PowerShell commands only
- **L23** (NEW, from Devin's Plan 54 C9 proposal): verification gates must match prior plan's actual scope

## Review focus for Claude

1. **Is Section 0: Rules inline approach correct?** Rules travel with each plan, no separate file. The /globalrules/ folder is reference-only. This is a significant simplification from the v2.1 ship-verify-backup dance in Plan 54.

2. **Is `mypy .` in S1.3 acceptable?** L18 says "Never `mypy .`" but explicitly excepts 5-plan checkpoints (55, 60, 65...). This IS Plan 55. The exception is documented in L18 itself.

3. **Is the Marine stack scope correct?** 4 SKILL.md files (weather, AIS, tidal, passage_planner) — spec only, no Python. Implementation deferred to Plan 59. This matches the handoff's "Marine stack" deferral note.

4. **Are the API choices reasonable?**
   - Weather: Open-Meteo Marine (free, no key) ✅
   - AIS: AISHub (requires user-provided API key via env var) — acceptable, documented
   - Tidal: NOAA CO-OPS (free, no key) ✅
   - Passage planner: aggregates the above, no external API ✅

5. **Is C10 handoff update scope correct?** Adds row 55 to Completed table, updates 5 baselines from scan results, restructures Next-5-Prompts (removes 55, adds 60, inserts Plan 59 for Marine Python implementation).

6. **Is the STOP condition for mypy regression (>50 increase) reasonable?** Plans 51-54 reduced mypy from ~309 to ~282. A >50 increase would indicate something went very wrong (e.g. scan reveals errors the file-scoped checks missed, or a dependency update introduced new type issues).

7. **Should the 22 B108 findings be addressed in this plan?** No — per L5, they're pre-existing debt outside this plan's scope. They're logged in the scan summary (S2) and noted in the handoff. A future housekeeping plan will address them.

## Files this plan touches

- **`skills/marine/weather/SKILL.md`** — NEW (spec only)
- **`skills/marine/ais/SKILL.md`** — NEW (spec only)
- **`skills/marine/tidal/SKILL.md`** — NEW (spec only)
- **`skills/marine/passage_planner/SKILL.md`** — NEW (spec only)
- **`C:\Jarvis\scan\logs\plan-55-checkpoint-scan.md`** — NEW (scan summary, NOT committed)
- **`CHANGELOG.md`** — append prompt-55 entry (~18 lines, per L21)
- **`SOVEREIGN_AI_HANDOFF.md`** — substantial C10 update (baselines + Completed row + Next-5 restructure)

## Expected outcome

- Tests: 1167 passed (unchanged — SKILL.md files don't affect tests)
- Ruff: ~111 errors (unchanged — no Python touched)
- Mypy (full-repo): ~282 errors (fresh baseline established)
- Bandit: 22 B108 (pre-existing, logged)
- pip-audit: ~55 CVEs (fresh baseline)
- Vulture: ~47 findings (fresh baseline)
- Marine stack: 4 SKILL.md files created (spec only)
- L20 self-evolution: C9 rule-proposal section in closing report (2nd activation)
- Handoff: fresh baselines for Plans 56-60
