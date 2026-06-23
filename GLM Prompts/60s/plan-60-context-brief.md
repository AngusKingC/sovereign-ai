# Plan 60 — Context Brief for Claude Review

**Plan**: 60 — 5-Plan Milestone Full Checkpoint Scan + L25 Landmine Rename (L→M)
**Author**: GLM (post-prompt-59 execution-log review)
**Date**: 2026-06-22
**Plan file**: `/home/z/my-project/download/plan-60.md`
**Handoff reference**: `SOVEREIGN_AI_HANDOFF.md` (uploaded), specifically sections: [Start here], [GLM workflow], [Devin plan template], [Known landmines] (L1-L25, soon to be M1-M25), [Completed prompts], [Next 5 prompts]

---

## What's different from Plan 59

Plan 59 was a Phase 1 debt-cleanup plan (ruff 110→0 + B108 suppressions). Plan 60 is a **5-plan milestone** (mandatory full scan per L18 verification cadence) plus a **deferred landmine rename** (L25 from handoff, flagged by Plan 59 review).

Three differences worth Claude's attention:

1. **Full-repo mypy is permitted here (and only here)**. Per L18, file-scoped mypy is the rule — except at 5-plan milestones (55, 60, 65, ...). Plan 60's S1.3 runs `mypy . --ignore-missing-imports` and captures the full-repo count. This is the exception, not the rule.

2. **Docs-only plan → docs-only exception applies** (handoff Rule 21 / closing step note). Plan 60 touches ZERO `.py` files (only `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, `CHANGELOG.md`, and possibly some plan files in `GLM Prompts/`). Skip C2 (ruff) and C3 (mypy) at closing. All other closing steps (C1, C4-C13) remain mandatory.

3. **L25 landmine rename**: handoff landmines L1-L25 → M1-M25. Per-plan Section 0 L1-L26 stays as L1-L26 (no rename). Only handoff landmine references are renamed. The rename itself was flagged as deferred work in handoff landmine L25 (now M25 after S3 completes).

---

## What this plan does (1-2 lines per step)

- **S0**: Opening verification (prompt-59 tag, clean working tree, AGENTS.md read + add new rule 22, capture AGENTS.md SHA).
- **S1**: Full scan baseline — sequentially run pytest, ruff, mypy (full-repo), bandit (with new rule 22 filter), pip-audit, vulture. Compare each to handoff baselines per AGENTS.md rule 15.
- **S2**: Fix the missing prompt-59 row in completed prompts table (Plan 59 C10 missed closing step 7a — GLM found this at Plan 60 Step 2 verification).
- **S3**: L25 landmine rename — L1-L25 → M1-M25 in handoff + AGENTS.md + plan files + CHANGELOG. Includes S3.6 update to the (now M25) entry to mark fix as DONE.
- **S4**: Update handoff baselines block with S1 actual counts.
- **S5**: Refresh 4 status sections in handoff ("What works" / "What's broken" / "What's built but not reachable" / "What's deferred").
- **S6**: Shift "Next 5 prompts" queue — Plan 61 becomes active, add Plan 65 (next 5-plan milestone) as new open slot.
- **S7**: Final verification (docs-only — skip ruff/mypy, run pytest only).
- **Closing**: Run `/jarvis-close` with tag `prompt-60`. Docs-only exception: skip C2/C3.

---

## Baselines (sourced from handoff, NOT from GLM clone per L19)

- **Tests**: 1166 passed, 56 skipped (verified at Plan 59 S1.1)
- **Ruff (full-repo)**: 0 errors (post-Plan 59)
- **Mypy (full-repo)**: 283 errors (per handoff Plan 55 baseline — Plan 60 recaptures)
- **Bandit**: 3179 low, 0 medium, 0 high (post-Plan 59 B108 suppressions)
- **pip-audit**: 19 CVEs across 4 packages (per handoff Plan 56 — Starlette, chromadb, diskcache, +1)
- **Vulture**: 20 high-confidence findings (per handoff Plan 57 — 16 removed, 16 deferred Category C)
- **prompt-59 tag on origin**: `2e9f883819e197b480969330899618b5c9d6d81f` (verified by GLM at Plan 60 Step 2)
- **AGENTS.md SHA at plan start**: TBD by Devin at S0.4 (post-prompt-59 state + new rule 22)

---

## New AGENTS.md rule proposed (rule 22)

**Rule 22 — Bandit finding count via Issue-header filter**

> When counting bandit findings by ID, filter on the literal `>> Issue: [B` pattern (the issue header line), not just the ID string. The ID appears in multiple line types per finding (issue header, "More Info" URL, and after suppression, "nosec encountered" warning lines), so `bandit ... | Select-String "B108" | Measure-Object -Line` overcounts by ~2x and triggers false-positive STOP conditions.

**Trigger (from Plan 59 execution log)**:
- S1.3: `bandit ... | Select-String "B108" | Measure-Object -Line` returned 44 (expected 22). Each B108 finding has 2 lines containing "B108" (issue header + More Info URL). Devin correctly recovered by examining actual output, but this triggered a STOP and cost time.
- S6.2: After suppressions, same command returned 15 lines — all "nosec encountered (B108)" warning lines, 0 actual findings. Devin correctly identified as bandit quirk.

**Expected benefit**: Avoids false-positive STOP conditions and incorrect "B108 not clean" reports in any future plan that touches bandit findings.

**Existing AGENTS.md rules that interact**: Rule 3 (sequential scans), Rule 15 (baseline reconciliation). Rule 22 is more specific — it tells Devin HOW to count bandit findings correctly, which prevents Rule 15 from triggering on false positives.

---

## Review focus questions for Claude

1. **S3 scope soundness**: The L25 rename targets handoff landmines L1-L25 → M1-M25, leaving per-plan Section 0 L1-L26 untouched. Is this scoping correct? Are there other L-references in the handoff or plan files that could be mistakenly renamed (or mistakenly left as L)?

2. **S3.3/S3.4 STOP threshold**: The plan says "if cross-reference search finds >50 handoff-L references, STOP and request GLM guidance". Is 50 a reasonable threshold? Should it be lower (e.g., 20) to catch scope creep earlier, or higher (e.g., 100) to avoid false alarms?

3. **Docs-only exception coverage**: Plan 60 touches `SOVEREIGN_AI_HANDOFF.md`, `AGENTS.md`, `CHANGELOG.md`, and possibly plan files in `GLM Prompts/`. None are `.py` files. Is the docs-only exception (skip C2 ruff + C3 mypy) correctly applied? Are there any closing steps that should NOT be skipped despite docs-only status?

4. **S1.3 mypy threshold**: Plan 60 says "STOP if mypy count > 283 by >10". Is >10 the right threshold? Mypy is deferred to Phase 4 (Plans 66-74) — any new errors introduced by Plans 56-59 should be flagged, but small drift (1-5 errors) may be acceptable. Should the threshold be tighter (e.g., >5) or looser (e.g., >20)?

5. **S2 prompt-59 row fix**: The fix adds a single row to the completed prompts table. Is the row content accurate based on Plan 59's execution log? Are there any details missing (e.g., specific file counts, suppression counts) that should be in the row's "Notes" column?

6. **New rule 22 placement**: The plan puts rule 22 in the "Environment" section (after existing rules 1-3 about scan tools). Is this the right section? Should it instead go in a new "Scan counting" section, or under "Edit discipline" (since it's about how to interpret scan output)?

7. **S6 queue shift**: The plan adds Plan 65 (next 5-plan milestone) as a new open slot at the bottom of the Next 5 prompts queue. Is this the right approach, or should Plan 65 be more specific (e.g., "5-plan milestone full scan + Postgres persistence check")?

8. **S3.6 entry update for M25**: The plan updates the (former L25, now M25) landmine entry text to say "RESOLVED by Plan 60" instead of "deferred to Plan 60". Is this update clear, or should the entry also document what the resolution was (e.g., "renamed L1-L25 → M1-M25 across 4 file types: handoff, AGENTS.md, plan files, CHANGELOG")?

---

## Out-of-scope items (per plan)

- 283 mypy errors → Phase 4 (Plans 66-74)
- 20 vulture findings → permanent Category C deferrals
- 19 pip-audit CVEs → upstream patches
- Marine stack Python → deferred indefinitely
- Trace store / eval harness / improvement loop → Phase 2 (Plans 61-63)
- Postgres persistence → Phase 3 (Plans 64-65)
- Renaming per-plan Section 0 L-rules → NOT in scope (only handoff landmines renamed)
- Renaming AGENTS.md stable rules (1-22) → NOT in scope (numbered rules, not L-labels)
- Any code change to `.py` files → NOT in scope (docs-only plan)
