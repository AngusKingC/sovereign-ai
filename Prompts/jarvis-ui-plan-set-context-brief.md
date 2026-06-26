# JArvis UI Plan Set — Round Table Review Brief

## Part 1: Roles/Rules

Your job is to find issues in this plan set, not rewrite it. Assume this plan set will fail — identify how. Each issue must include a concrete failure scenario. Criticize my reasoning, not my conclusions.

## Part 2: Context

### What this plan set covers
Six plans (81–86) + one named plan (infra-remediation) that restructure the Sovereign AI project's next phase to integrate UI development alongside backend functionality. The current PLANS.md roadmap (Plans 82–85) was purely PEMADS-focused. This restructure interleaves UI build-out with PEMADS delivery so that each backend feature ships with its corresponding frontend surface.

### Key design decisions and my reasoning

**Decision 1: Sub-parts (82a–82g) instead of separate plan numbers.**
My reasoning: A single plan number with sub-parts shares one git tag, one CHANGELOG entry, and one closing sequence. This reduces GLM↔Devin handoffs from 7 to 1 for the main UI build (Plan 82). With Devin's 200k context window, all 7 sub-parts fit in a single execution. The sub-parts provide natural verification checkpoints without requiring full closing sequences between each.

**Attack this reasoning**: Is 7 sub-parts too many? Does the single-tag approach make it harder to roll back if 82d fails but 82a–82c succeeded? Should sub-parts have their own checkpoint commits?

**Decision 2: Plan 82 replaces PEMADS Phase 2 in the queue.**
My reasoning: The UI is currently broken (missing `lib/api.ts`). Fixing it and building the operational dashboard is higher priority than PEMADS Phase 2 because (a) the broken app blocks all UI work, (b) operational panels (circuit breaker, costs, approvals) are needed for safe PEMADS operation, and (c) the model picker UI (Plan 83) is a prerequisite for the expert panel selector.

**Attack this reasoning**: Is delaying PEMADS Phase 2 by one plan acceptable? Does the spec require PEMADS before the UI is useful? Could the scan (Plan 81) and UI build (Plan 82) run in parallel?

**Decision 3: Frontend uses Zustand `activeView` for routing instead of Next.js App Router pages.**
My reasoning: The dashboard shell is a persistent layout where panels swap in/out of the main area. URL-based routing would cause full page reloads, losing terminal scrollback and SSE connections. Zustand `activeView` enables instant panel switching without navigation events.

**Attack this reasoning**: Is this a scalability trap? When we add 20+ panels, will `activeView` become unmanageable? Should we use Next.js parallel routes or intercepting routes instead?

**Decision 4: `backend/main.py` (mocked data) for Plan 82, real integration in Plans 83–85.**
My reasoning: Mocked data lets us build and test the frontend independently. Real orchestrator integration requires adding methods to core modules (list_tasks, circuit_breaker status, etc.) that would make Plan 82 too large. Plans 83–85 swap mocked endpoints for real ones as part of their backend work.

**Attack this reasoning**: Does this create a "two-server" problem? The project currently has `web/server.py` (real orchestrator) and `backend/main.py` (mocked). If both exist, which one does `jarvis serve` start? Will the mocked data shapes diverge from real orchestrator return types?

**Decision 5: CLI improvements bundled with PEMADS Phase 4 (Plan 86) instead of a separate plan.**
My reasoning: The CLI improvements (operational dashboard screens + slash commands) are lower priority than the Web UI. Bundling them with PEMADS Phase 4 (also lower priority than Phase 2/3) keeps the plan count manageable. The CLI reads from the same Orchestrator that the Web UI backend uses, so it naturally follows the Web UI build.

**Attack this reasoning**: Should CLI improvements come earlier? Users who don't want the Web UI still need operational visibility in the terminal. Is deferring CLI to Plan 86 a mistake?

### Confidence levels

| Decision | Confidence | Risk if wrong |
|----------|------------|---------------|
| Sub-parts vs separate plans | 85% | Medium — rollback complexity |
| UI before PEMADS | 90% | Low — UI is broken, must fix first |
| Zustand activeView | 70% | Medium — scalability concern |
| Mocked backend then real | 75% | High — data shape divergence |
| CLI deferred to Plan 86 | 65% | Medium — CLI users left waiting |

### Open questions for the round table

1. **Tag granularity**: Should sub-parts get intermediate checkpoint tags (e.g., `prompt-82c`) in addition to the final `prompt-82`? This would make rollback easier but adds tagging complexity and may conflict with OR9 (tag every prompt).

2. **Backend unification**: Should we merge `backend/main.py` and `web/server.py` into a single FastAPI app? Or keep them separate and have `jarvis serve` choose which one to start based on a flag? The current two-server architecture is confusing.

3. **Real vs mocked data for Plan 82**: Should Plan 82 wire directly into the real orchestrator (making the plan larger but eliminating the mocked→real migration)? Or is the two-step approach (mocked in 82, real in 83–85) safer?

4. **Playwright E2E scope**: Is 9 E2E tests enough for the initial UI build? Or should Plan 82 include E2E tests for every panel?

## Part 3: Answer Format

Respond with:

1. **Critical issues** — will cause plan failure if not addressed
2. **Significant issues** — should be addressed but won't necessarily cause failure
3. **Minor issues** — nice to fix
4. **Other concerns** — anything else you noticed

For each issue: concrete failure scenario + suggested fix.
Permitted: "No issues found" if the plan set is sound.
