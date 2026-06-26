# JArvis UI Plan Set — Round Table Review Brief
## Batch 1: Plans 81–84 | Rev1

---

## Part 1: Roles/Rules

Your job is to find issues in this plan set, not rewrite it. Assume this plan set will fail in 6 months — identify the most plausible reasons. Each issue must include a concrete failure scenario and evidence from the codebase. Criticize my reasoning, not my conclusions. You may respond "No issues found" if the plan set is sound.

Ban: style comments, formatting preferences, speculative future features, performance optimizations without measured impact.

---

## Part 2: Context

### What this batch covers
Four plans (81–84) that deliver the complete JArvis UI Shell for Sovereign AI. Plan 81 unifies the two-server backend and adds all API endpoints. Plan 82 builds frontend state (Zustand stores) and the persistent dashboard shell (CSS Grid, status bar, sidebar, main pane, right panel, bottom bar). Plan 83 builds all operational panels (Tasks, Workers, Approvals, Costs, Memory Drawer, Settings Drawer, Skills, Help). Plan 84 delivers comprehensive test coverage (Vitest + Playwright E2E).

### Key dependencies
- Plan 81 endpoints must exist before Plan 82 hooks can fetch data
- Plan 82 shell layout must exist before Plan 83 panels can render
- Plan 83 panels must exist before Plan 84 tests can mount them
- All plans depend on `prompt-80` (last completed plan — UI shell scaffold)

### Author's reasoning (attack this, not the conclusion)

**Decision 1: Backend unification in Plan 81 (merge backend/main.py into web/server.py).**
My reasoning: The two-server architecture (`backend/main.py` mocked + `web/server.py` real) is broken. `next.config.ts` has no rewrites, so API calls from the frontend go nowhere. The `backend/` directory is a leftover from an earlier scaffold. Merging eliminates confusion, ensures all endpoints share the same auth/CORS/middleware stack, and gives the frontend a single backend to talk to.

**Decision 2: No mocked data — all endpoints wired to real orchestrator methods.**
My reasoning: Mocked data creates a "mocked→real" migration debt. The orchestrator already has `cost_tracker`, `worker_circuit_breaker`, `approval_gate`, and `memory_router`. Thin getter methods in `orchestrator.py` shape the data for API consumption. If a method doesn't exist yet (e.g., `get_session_timeline`), return a realistic empty structure rather than hardcoded mocks. This ensures the frontend types match the real data shapes from day one.

**Decision 3: Zustand `activeView` for routing instead of Next.js App Router pages.**
My reasoning: The dashboard is a persistent shell — status bar, sidebar, bottom bar are always visible. URL-based routing would cause full page reloads, losing SSE connections and terminal scrollback. `activeView` enables instant panel switching. The tradeoff is no URL state (refresh resets to home), but this is acceptable for a desktop-only operations tool.

**Decision 4: Terminal placeholder in Plan 83 (xterm.js deferred to Plan 85).**
My reasoning: xterm.js + WebSocket PTY is complex and requires backend PTY handler work. The terminal is not critical for the operational dashboard's core value (task orchestration, worker monitoring, cost tracking). A placeholder maintains shell layout integrity without blocking the batch.

**Decision 5: Settings drawer fields are mocked (no real backend write endpoints).**
My reasoning: Cost policy, circuit breaker config, and sandbox config are read from existing objects. Write endpoints would require new `update_*` methods in core modules. This is deferred to Plan 86 (PEMADS + settings integration) to keep Plan 83 focused on UI rendering.

### Confidence levels

| Decision | Confidence | Risk if wrong |
|----------|------------|---------------|
| Backend unification | 90% | Low — backend/main.py is clearly a leftover |
| Real data vs mocked | 75% | High — some orchestrator methods may not exist |
| Zustand activeView | 70% | Medium — scalability concern with 20+ panels |
| Terminal deferred | 85% | Low — placeholder is sufficient |
| Settings mocked | 80% | Low — read-only settings still useful |

### Open questions

1. **Backend unification risk**: Does `web/server.py` have all the middleware (CORS, auth) that `backend/main.py` has? If not, merging may break CORS for the frontend.

2. **Orchestrator getter methods**: Are `cost_tracker.get_spend_summary()` and `worker_circuit_breaker.get_status()` actually callable? I haven't verified their signatures.

3. **Playwright dual webServer**: Will starting both backend (:8000) and frontend (:3000) in Playwright config cause port conflicts or race conditions in CI?

4. **SSE test reliability**: The `sse.spec.ts` reconnect test uses `context.setOffline(true)` — is this reliable across browsers?

---

## Part 3: Answer Format

Respond with:

1. **Critical issues** — will cause Devin STOP condition, test failure, or broken build if not addressed
2. **Significant issues** — should be addressed but won't necessarily cause failure
3. **Minor issues** — nice to fix
4. **Other concerns** — anything else you noticed

For each issue: concrete failure scenario + suggested fix.
Permitted: "No issues found" if the plan set is sound after review.
