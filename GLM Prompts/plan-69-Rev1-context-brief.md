# Plan 69 Context Brief — Repo Hygiene: Governance Doc Fixes + Stale File Cleanup

**For**: Claude review (Rev 1)
**Plan file**: `/home/z/my-project/download/plan-69-Rev1.md`

---

## Project state at Plan 69 start

- **Mypy**: 0 errors full-repo (247+ source files) — remediation complete
- **Tests**: 1253 passed, 67 skipped, 0 failed (Plan 68 just completed)
- **Ruff**: 0 errors
- **Skill taxonomy**: Live — SkillTier enum + 25 classifications + CONTEXT.md all working

## What this plan does

1. **S1**: Fix CHANGELOG.md — wrong year on prompt-67 date (2025→2026), placeholder timestamps, tag note, old filename references
2. **S2**: Fix PLANS.md — remove duplicate "Baseline Reconciliation Notes" section
3. **S3**: Fix AGENTS.md — header says OR1-OR23 but rules go up to OR28
4. **S4**: Delete stale files — temp/changelog-entry-prompt-58.7.md, empty exports/trajectories.jsonl
5. **S5**: Add missing `__init__.py` — 5 directories (3 skills, marine/, gui/)
6. **S6**: Fix stale code reference — core/verbosity.py references deleted global_rules.md → update to AR11

All changes are docs/cleanup only — no Python implementation changes. No test behavior changes expected.

## Key design decisions

- **No new AGENTS.md rules this plan** — purely cleanup, no new patterns
- **Architecture rules for orchestrator/evals/api/gateways/ NOT added** — that's a design decision requiring user input, not cleanup
- **workers/base.py stub NOT removed** — removing it is a design decision, deferred
- **15 skills lacking SKILL.md NOT addressed** — that's feature work (Plan 70+)
- **Duplicate PLANS.md section**: The second "Baseline Reconciliation Notes" section is historical cruft from Plans 60-67 that was never cleaned up when the reconciled first section was added

## Risk areas for review

1. **S2.1 PLANS.md dedup**: Which section to keep? The first (line ~127) has the reconciled baselines. The second (line ~233) has per-plan deltas. I chose to keep the first and delete the second — but the second has granular per-plan data that might be useful for auditing. Should both sections be merged instead?
2. **S1.2–S1.3 placeholder timestamps**: I suggested using actual git timestamps or `--:--` as deliberate placeholder. Is there a better approach?
3. **S4.2 exports/trajectories.jsonl**: This is a 0-line tracked file. Is there any runtime code that expects it to exist? Deleting it might break something that creates it on startup.
4. **Missing `__init__.py` for marine/ skills**: These are spec-only (SKILL.md, no code). Adding `__init__.py` makes them importable packages, but they have no code to import. Is this premature?
