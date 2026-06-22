# Plan 56 Context Brief

**To**: Claude reviewer
**From**: GLM
**Date**: 2026-06-21
**Plan**: 56 — Dependency updates (37 CVEs across 14 packages)

---

## What this plan does

Upgrades vulnerable Python dependencies to fix 37 CVEs found in Plan 55's pip-audit scan. Split into:
- **S2 (safe upgrades)**: 9 packages with minor/patch bumps — aiohttp, cryptography, idna, pygments, pypdf, pytest, python-dotenv, python-multipart, urllib3
- **S3 (risky upgrades)**: 3 packages with major version bumps — pillow 11→12, starlette 0.52→1.3, setuptools 65→78
- **S4 (no fix available)**: 2 packages — chromadb, diskcache (document and defer)

## Baselines (from Plan 55 scan)

- **Tests**: 1167 passed, 55 skipped, 0 failed
- **pip-audit**: 37 CVEs across 14 packages
- **prompt-55 tag on origin**: `b6e5cb2` ✅ verified
- **master HEAD**: `fb5d152` ✅ verified

## Section 0: Rules

Inline approach (same as Plan 55 REV4). 23 rules (L1-L23). No new rules added — GLM did not add rules mid-drafting (per L20, only Devin proposes via C9).

**Note on Plan 55's C9**: Devin submitted "none (no new failure patterns this prompt)". This is acceptable per L20 — explicit "none" satisfies the reflection requirement. However, GLM notes that the S1 parallel-scan output corruption (where running 6 tools simultaneously mixed their stdout streams, requiring Devin to re-run each individually) WAS a real failure pattern. Devin either didn't recognize it as a rule-worthy pattern or chose not to propose. This is fine — the mechanism allows "none" and GLM shouldn't second-guess Devin's reflection.

## Landmines relevant to this plan

- **L5**: don't expand scope — only upgrade dependencies, don't fix other issues
- **L9**: fix test file in same step as production file — if an upgrade breaks tests, fix the test or revert the package
- **L17**: closing steps C1-C13 mandatory
- **L20**: C9 rule-proposal MANDATORY
- **L21**: CHANGELOG append to END, temp-file pattern
- **L22**: PowerShell commands only
- **L23**: verification gates scoped to actual prior plan scope

## Review focus for Claude

1. **Is the safe/risky split correct?**
   - Safe (S2): aiohttp 3.13.3→3.13.4, cryptography 48.0.0→48.0.1, idna 3.11→3.15, pygments 2.19.2→2.20.0, pypdf 6.13.0→6.13.3, pytest 9.0.2→9.0.3, python-dotenv 1.2.1→1.2.2, python-multipart 0.0.22→0.0.31, urllib3 2.6.3→2.7.0
   - Risky (S3): pillow 11→12 (major), starlette 0.52→1.3 (major, FastAPI dep), setuptools 65→78 (major)

2. **Is the starlette FastAPI compatibility check in S3.2 adequate?** The plan checks `pip show fastapi` for version/requires before upgrading starlette. Should it also check the FastAPI changelog? Or is the pip-show check sufficient?

3. **Is the "upgrade one at a time" fallback in S2.2 STOP condition correct?** If the batch upgrade breaks tests, the plan says to upgrade one at a time to identify the offender. Is this the right approach, or should the plan default to one-at-a-time from the start?

4. **Is S4 (no-fix packages) handled correctly?** chromadb and diskcache have CVEs but no fix versions listed in pip-audit. The plan checks for newer versions via `pip index versions`. If a newer version exists but isn't listed as a fix, should the plan try upgrading anyway?

5. **Is the requirements.txt update in S5 correct?** `pip freeze > requirements.txt` captures ALL packages, not just the upgraded ones. If the project uses a minimal requirements.txt (only direct deps) vs a full freeze, this could be wrong. Should the plan check the existing requirements.txt format first?

6. **Is the STOP condition for test failures adequate?** The plan says revert and note in CHANGELOG. Should it also require investigating WHY the test failed (in case the test itself is wrong, not the package)?

## Files this plan touches

- **`requirements.txt`** — updated with new package versions
- **`CHANGELOG.md`** — append prompt-56 entry
- **`SOVEREIGN_AI_HANDOFF.md`** — update pip-audit baseline + Completed row 56 + Next-5 shift

## Expected outcome

- Tests: 1167 passed (unchanged — if all upgrades are compatible)
- pip-audit: 37 → ~15-20 CVEs (depending on how many risky upgrades succeed; chromadb + diskcache will remain)
- Safe upgrades: ~20 CVEs eliminated
- Risky upgrades: up to 15 more CVEs eliminated (if all 3 succeed)
- Deferred: chromadb (1 CVE), diskcache (1 CVE) — no fix available
