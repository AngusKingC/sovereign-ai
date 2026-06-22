# Plan 53 Context Brief (for Claude review)

**Current revision**: REV4 (2026-06-20)

## Prior prompt state

- **Test baseline (prompt-52)**: 1166 passed, 55 skipped, 1 failed (calendar, pre-existing)
- **Mypy**: 282 errors
- **prompt-52 tag**: `58f06c6` on origin ✅
- **Clone SHA**: `81dd2d4` (L20)

## Prior findings

- Calendar test uses hardcoded date `20260620T140000Z` (line 56) — now in past, test fails
- 22 B108 bandit findings — `tests/skills/test_calendar_skill.py` uses `"test.ics"` in working directory
- 109 `datetime.utcnow()` calls across 15 test files — Python 3.12 deprecation warning
- Other calendar tests in same file (lines 93, 99, 130, 136) already use dynamic `strftime` dates — follow that pattern

## Files in scope

16 test files: `tests/skills/test_calendar_skill.py` (Step 1+2), 15 files for datetime.utcnow (Step 3). Test-only, no production code.

## Review focus (REV4)

**What changed in REV4** (2 edits, from Claude round-3 finding):
1. "Current state" line: "109 occurrences" → "81 occurrences" (was missed in REV3).
2. C6 CHANGELOG: "datetime.now(datetime.UTC) (109 occurrences)" → "datetime.now(timezone.utc) (81 occurrences)" (corrects both count and API name).

All occurrences of "109" now corrected to "81" throughout the plan. All occurrences of "datetime.UTC" in the CHANGELOG corrected to "timezone.utc" to match Step 3.1's actual implementation.

**Claude should verify**:
1. No remaining "109" anywhere in the plan.
2. C6 CHANGELOG says "timezone.utc" (not "datetime.UTC").
3. No other changes from REV3.

## Landmines relevant

See handoff L1-L22. Most relevant: L17/Rule 21 (completion checklist), L18 (file-scoped mypy), L21 (PowerShell only), L22 (recurring mistakes → global_rules.md).

## Revision history

- REV1: initial draft (2026-06-20) — calendar test fix + B108 + datetime.utcnow deprecation
