# Plan 68 Context Brief — Phase 1 Foundation: Skill Taxonomy + CONTEXT.md

**For**: Claude review (Rev 1)
**Plan file**: `/home/z/my-project/download/plan-68.md`

---

## Project state at Plan 68 start

- **Mypy**: 0 errors full-repo (247 source files) — remediation era complete after Plans 64-67
- **Tests**: 1230 passed, 67 skipped, **2 pre-existing failures** (identity unknown — not shown in truncated log)
- **Ruff**: 0 errors
- **Feature roadmap**: Added to PLANS.md at Plan 67 close — 16 features across 4 phases

## What this plan does

1. **S1**: Fix 2 pre-existing test failures (quick cleanup before Plan 70 milestone scan)
2. **S2 (F1)**: Skill Taxonomy — `core/skill_taxonomy.py` (SkillTier enum + SkillClassification dataclass + SkillTaxonomyRegistry) + `skills/_classifications.py` (20 built-in classifications)
3. **S3 (F2)**: CONTEXT.md — shared vocabulary file at repo root
4. **S4**: 18 new tests (13 taxonomy + 5 CONTEXT.md)

## Key design decisions

- **SkillTier has 3 values**: USER_INVOKED, AGENT_INVOKED, HYBRID (HYBRID reserved for future — no existing skills use it yet)
- **SkillClassification is frozen dataclass**: Immutable after creation, prevents accidental mutation
- **SkillTaxonomyRegistry is separate from SkillRegistry**: Taxonomy handles classification only; existing `_registry.py` handles skill discovery/loading. Single responsibility.
- **build_default_registry() is a factory function**: Not a singleton. Tests can create fresh registries without state pollution.
- **CONTEXT.md is at repo root**: Not in core/ or skills/ — it's project-level, referenced by all agents.
- **No new AGENTS.md rules this plan**: OR28 was added at Plan 67 S0.3. No new patterns emerged.

## Architecture compliance

- `core/skill_taxonomy.py` → core/ may not import adapters/, cli/, workers/, memory/, skills/, web/, system/ (AR1) ✅
- `skills/_classifications.py` → imports from core/ only (AR5) ✅
- No raw LLM calls (AR9), no memory access outside MemoryRouter (AR10), no TraceEmitter needed here (AR11) ✅
- All public functions have return type annotations (AR14) ✅

## Risk areas for review

1. **S1.1 unknown failures**: The 2 pre-existing failures weren't captured in the truncated execution log. If they require architectural changes, this plan has a STOP gate at S1.2.
2. **Skill count**: I counted 20 skills in the `skills/` directory. Verify this matches the actual repo.
3. **Tier assignments**: I classified calculator/terminal/docker as USER_INVOKED and calendar/notes/reminder as AGENT_INVOKED. Review if these assignments match the user's mental model.
4. **HYBRID tier**: Currently unused but defined for forward compatibility. Worth including or should we defer?
5. **`skills/_classifications.py` naming**: Underscore prefix suggests internal module. Is this the right convention, or should it be `skills/classifications.py`?
