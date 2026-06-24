# Plan 69 — Repo Hygiene: Governance Doc Fixes + Stale File Cleanup

**Plan**: 69
**Rev**: 2 (incorporates Claude review feedback on Rev 1)
**Type**: Docs/cleanup
**Priority**: 1
**Estimated scope**: ~10 files edited, ~1 file deleted, ~1 file git-rm-cached

### Rev history
- **Rev 1**: Initial plan from comprehensive repo scan findings.
- **Rev 2**: Applied Claude review — 4 decision points resolved: (1) timestamps use git log then --:-- fallback, (2) delete second PLANS.md reconciliation section (per-plan data in git), (3) exports/trajectories.jsonl NOT deleted (runtime code uses it), add to .gitignore instead, (4) __init__.py templates match existing pattern. Added AI_HANDOFF.md CONTEXT.md governance section.

---

## S0 — Opening

S0.1. Run `/jarvis-open`. Verify `prompt-67` tag on origin, clean working copy on master.

S0.2. Read AGENTS.md in full. Every file edit in this plan MUST comply with its rules.

S0.3. **No new AGENTS.md rules this prompt.** All existing rules (OR1–OR28, AR1–AR18) apply.

---

## S1 — CHANGELOG Fixes

### S1.1 — Fix prompt-67 date (CRITICAL)

**File**: `CHANGELOG.md`

Find the prompt-67 entry's date line. It currently reads `2025-06-24` — the year is wrong. Change to `2026-06-24`.

Syntax check (OR6): `python -c "import ast; ast.parse(open('CHANGELOG.md').read())"` — this will fail because CHANGELOG is not Python. Instead, verify manually:
```powershell
Select-String "2025-06-24" CHANGELOG.md
```
After fix:
```powershell
Select-String "2026-06-24" CHANGELOG.md | Select-Object -First 1
```

### S1.2 — Fix prompt-54 placeholder timestamp

**File**: `CHANGELOG.md`

Find the prompt-54 entry. It has `HH:MM` as a placeholder timestamp. **Priority: use git log first, fall back to `--:--`.**
```powershell
git log --format="%ai" prompt-54 | Select-Object -First 1
```
If git returns a timestamp, use it. If no result, replace `HH:MM` with `--:--` (deliberate placeholder that signals "time unknown" vs `HH:MM` which looks like a copy-paste mistake).

### S1.3 — Fix prompt-56 placeholder timestamp

Same process as S1.2 for the prompt-56 entry: try `git log --format="%ai" prompt-56 | Select-Object -First 1`, fall back to `--:--` if no result.

### S1.4 — Fix prompt-56 tag note

The CHANGELOG says "Tag: prompt-56 skipped (no file changes to commit)" but the tag actually exists on origin. Fix the entry to reflect reality:
```powershell
git tag --list prompt-56
git ls-remote --tags origin prompt-56
```
If the tag exists, update the entry to say: `Tag: prompt-56 verified on origin`

### S1.5 — Fix old filename references

Find all references to `SOVEREIGN_AI_HANDOFF.md` in CHANGELOG.md and update them to `AI_HANDOFF.md`. These are historical entries, so the format should be:
- Change `SOVEREIGN_AI_HANDOFF.md` → `AI_HANDOFF.md` (just the filename, don't rewrite history)

Also check LANDMINES.md for the same reference and update if found.

After fixes, diff check (OR8):
```powershell
git diff --stat CHANGELOG.md LANDMINES.md
```

---

## S2 — PLANS.md Fixes

### S2.1 — Remove duplicate "Baseline Reconciliation Notes" section

**File**: `PLANS.md`

PLANS.md has two `## Baseline Reconciliation Notes` sections — one starting around line 127 and another around line 233. The first section (line 127) contains the current reconciled baselines. The second section (line 233) contains the historical per-plan deltas that are redundant with the first.

**Action**: Delete the second `## Baseline Reconciliation Notes` section entirely (from the `##` heading through the `---` separator before `## Key Document Cross-References`). Keep the first section only.

Verify structure after deletion:
```powershell
Select-String "## Baseline Reconciliation Notes" PLANS.md
```
Expected: Only ONE match.

### S2.2 — Verify PLANS.md structure

After S2.1, verify the remaining sections are in the correct order:
1. Test Baseline
2. Static Analysis Baseline
3. Completed Prompts
4. Next 5 Prompts Queue
5. Baseline Reconciliation Notes (singular)
6. Status Sections
7. Research-Backed Feature Roadmap
8. Key Document Cross-References
9. How to Update This Document

---

## S3 — AGENTS.md Header Fix

### S3.1 — Update rule numbering header

**File**: `AGENTS.md`

Line 7 currently reads:
```
- **OR{n}** = Operational Rules (OR1-OR23)
```

Change to:
```
- **OR{n}** = Operational Rules (OR1-OR28)
```

This reflects the actual state of the document (OR24–OR28 were added in Plans 63a–67).

Verify:
```powershell
Select-String "OR1-OR28" AGENTS.md
```

---

## S4 — Stale File Cleanup

### S4.1 — Remove stale temp file

Delete `temp/changelog-entry-prompt-58.7.md` — this violates OR21/L4 (temp files should be deleted after use).

```powershell
git rm temp/changelog-entry-prompt-58.7.md
```

### S4.2 — Untrack runtime export file (DO NOT DELETE)

`exports/trajectories.jsonl` is a 0-line tracked file, but it IS referenced by runtime code — `system/trajectory_exporter.py` uses it as the default export path (`export_path: str = "exports/trajectories.jsonl"`). Tests also assert this path. **Do NOT delete the file.**

Instead, untrack it from git and add it to `.gitignore` so it's created at runtime but never committed:

1. Add `exports/` to `.gitignore`:
```powershell
Add-Content -Path .gitignore -Value "`nexports/" -Encoding utf8
```

2. Untrack the file (keeps it on disk, removes from git):
```powershell
git rm --cached exports/trajectories.jsonl
```

3. Verify it's still on disk but untracked:
```powershell
Test-Path exports/trajectories.jsonl
git status exports/trajectories.jsonl
```
Expected: File exists on disk, shows as untracked in git status.

### S4.3 — Verify no other stale temp files

```powershell
Get-ChildItem -Path temp -Filter "*.md" -Recurse
Get-ChildItem -Path scan -Filter "changelog-entry-*" -Recurse
```
If any found, delete them too.

---

## S5 — Missing `__init__.py` Files

### S5.1 — Add missing `__init__.py` to skill directories

Three skill directories have `skill.py` but no `__init__.py`:

1. `skills/file_reader/__init__.py` (NEW)
2. `skills/file_writer/__init__.py` (NEW)
3. `skills/web_scraper/__init__.py` (NEW)

Create each matching the existing pattern in skill `__init__.py` files (e.g., `skills/calculator/__init__.py` uses `"""Calculator skill module."""`). Use `<Name> skill module.` format:

1. `skills/file_reader/__init__.py`: `"""File reader skill module."""`
2. `skills/file_writer/__init__.py`: `"""File writer skill module."""`
3. `skills/web_scraper/__init__.py`: `"""Web scraper skill module."""`

### S5.2 — Add missing `__init__.py` to marine directory

`skills/marine/` has subdirectories but no `__init__.py`. Add for consistency — even spec-only packages should be importable. Create:
```python
"""Marine skills package."""
```

### S5.3 — Add missing `__init__.py` to gui directory

`gui/` has `reference.py` but no `__init__.py`. Add for consistency. Create:
```python
"""GUI module."""
```

### S5.4 — Verify all new files

```powershell
python -c "import ast; ast.parse(open('skills/file_reader/__init__.py').read())"
python -c "import ast; ast.parse(open('skills/file_writer/__init__.py').read())"
python -c "import ast; ast.parse(open('skills/web_scraper/__init__.py').read())"
python -c "import ast; ast.parse(open('skills/marine/__init__.py').read())"
python -c "import ast; ast.parse(open('gui/__init__.py').read())"
```

---

## S6 — Stale Code Reference Fix

### S6.1 — Update core/verbosity.py comment

**File**: `core/verbosity.py`

Find the comment referencing `global_rules.md` (around line 37). Change:
```
Constructor-injected emitter pattern per global_rules.md Rule 2
```
To:
```
Constructor-injected emitter pattern per AR11 (TraceEmitter via constructor injection only)
```

This replaces a reference to a deleted file with the corresponding AGENTS.md rule.

---

## S6b — AI_HANDOFF.md: Add CONTEXT.md to Document Governance

CONTEXT.md was created in Plan 68 but wasn't added to the document governance system. It's a 6th governing document with a distinct responsibility (shared vocabulary) that all agents reference.

### S6b.1 — Add CONTEXT.md to Document Relationships table

**File**: `AI_HANDOFF.md`

In the `## Document Relationships` section, add a new row to the table after `AGENTS.md`:

```
| `CONTEXT.md` | Shared vocabulary — domain terms, conventions, skill tier definitions, and decision framework. Referenced by all agents for consistent terminology. | GLM (creates), all agents (read) | When domain terms or conventions change |
```

### S6b.2 — Add CONTEXT.md to single source of truth list

Add after the existing entries:
```
- Shared vocabulary / domain terms → `CONTEXT.md` only (AGENTS.md carries rules, not vocabulary)
```

### S6b.3 — Add CONTEXT.md to read order

**GLM (new chat)**: Add CONTEXT.md after LANDMINES.md:
```
- GLM (new chat): `AI_HANDOFF.md` → `PLANS.md` → `LANDMINES.md` → `CONTEXT.md` → start workflow
```

**GLM (Step 3)**: Add CONTEXT.md to re-read list:
```
- GLM (Step 3 of workflow): re-read `AI_HANDOFF.md` + `LANDMINES.md` + `CONTEXT.md`
```

**Devin**: Add to S0.2 read sequence:
```
- Devin (S0.2): `AGENTS.md` + `CONTEXT.md` (domain vocabulary for consistent naming)
```

Verify:
```powershell
Select-String "CONTEXT.md" AI_HANDOFF.md
```
Expected: At least 4 matches (table row, single source, read order x2).

---

## S7 — Verification

S7.1. Full test suite:
```powershell
python -m pytest tests/ -q --tb=short
```
Expected: **1253+ passed, ~67 skipped, 0 failed**. This is a docs/cleanup plan — no code changes that could break tests.

S7.2. Ruff on changed Python files:
```powershell
ruff check skills/file_reader/__init__.py skills/file_writer/__init__.py skills/web_scraper/__init__.py skills/marine/__init__.py gui/__init__.py core/verbosity.py
```
Expected: 0 errors.

S7.3. Mypy on changed Python files:
```powershell
mypy core/verbosity.py --ignore-missing-imports
```
Expected: 0 errors.

S7.4. Verify no stale references remain:
```powershell
Select-String "SOVEREIGN_AI_HANDOFF" CHANGELOG.md LANDMINES.md AGENTS.md
Select-String "global_rules" core/verbosity.py
Select-String "2025-06-24" CHANGELOG.md
Select-String "exports/" .gitignore
```
Expected: No matches for first three. `exports/` should appear in .gitignore.

---

## S8 — Closing

Run `/jarvis-close`. This handles:
- Full test suite
- Ruff check
- Mypy check (file-scoped)
- Git add, commit, tag `prompt-69`
- CHANGELOG entry
- PLANS.md update (completed prompts row, baselines, queue shift)
- LANDMINES.md (if new pattern — none expected)
- Rule proposal (C9)
- Docs commit
- Push + post-push verification

### Expected CHANGELOG entry
```
## 2026-06-24 — prompt-69

**Plan**: Repo Hygiene: Governance Doc Fixes + Stale File Cleanup

**Changed**:
- CHANGELOG.md: Fixed prompt-67 date (2025→2026), placeholder timestamps, tag note, old filename references
- PLANS.md: Removed duplicate "Baseline Reconciliation Notes" section
- AGENTS.md: Updated header OR1-OR23 → OR1-OR28
- core/verbosity.py: Updated stale global_rules.md reference → AR11
- skills/file_reader/__init__.py: NEW (missing package init)
- skills/file_writer/__init__.py: NEW (missing package init)
- skills/web_scraper/__init__.py: NEW (missing package init)
- skills/marine/__init__.py: NEW (missing package init)
- gui/__init__.py: NEW (missing package init)

**Untracked**:
- exports/trajectories.jsonl: Added exports/ to .gitignore, untracked via git rm --cached (file still on disk for runtime use)

**Deleted**:
- temp/changelog-entry-prompt-58.7.md: Stale temp file

**Results**:
- Tests: <count> passed, <count> skipped, 0 failed
- Ruff: 0 errors
- Mypy: 0 errors (file-scoped)
- Tag: prompt-69 verified on origin
```

---

## Pre-declared scope

**WILL edit**:
- `CHANGELOG.md` (date fix, timestamp fixes, tag note, filename references)
- `PLANS.md` (remove duplicate section)
- `AGENTS.md` (header fix)
- `AI_HANDOFF.md` (add CONTEXT.md to Document Relationships + read order)
- `core/verbosity.py` (comment reference fix)
- `.gitignore` (add exports/ to ignore runtime output)
- `skills/file_reader/__init__.py` (NEW)
- `skills/file_writer/__init__.py` (NEW)
- `skills/web_scraper/__init__.py` (NEW)
- `skills/marine/__init__.py` (NEW)
- `gui/__init__.py` (NEW)

**Will git-rm**:
- `temp/changelog-entry-prompt-58.7.md` (delete from disk and git)
- `exports/trajectories.jsonl` (git rm --cached only — keep on disk, add to .gitignore)

**Will NOT edit**:
- Any `.py` implementation files (no skill.py, worker, adapter, or core module changes)
- `test/` files (no test changes)
- `LANDMINES.md` (no new landmines)
- `system/`, `workers/`, `adapters/`, `cli/`, `memory/`, `web/` directories
- Architecture rules in AGENTS.md (adding AR9+ for orchestrator/evals/api/gateways is a design decision — deferred)
- `workers/base.py` stub (design decision — deferred)
- `skills/_registry.py` or `workers/_registry.py` stubs (feature work — deferred)
- Any file not listed above
