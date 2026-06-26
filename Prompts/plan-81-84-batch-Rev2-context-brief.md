# JArvis UI Plan Set — Round Table Review Brief
## Batch 1: Plans 81–84 | Rev2 (Re-Review After Adjudication)

---

## Part 1: Roles/Rules

Your job is to find issues in this revised plan set, not rewrite it. This is a **re-review of Rev2** after the Prompt Creator adjudicated Rev1's findings. Focus your attention on (a) whether the resolutions actually fix the underlying issues without introducing new flaws, and (b) whether the rejected issue (C7) was correctly rejected. You may respond **"Clean pass"** if the plan set is sound — do not pad with false concerns.

Each issue must include a concrete failure scenario and cite specific lines from the plan or codebase. Criticize my reasoning, not my conclusions. Ban: style comments, formatting preferences, speculative future features, performance optimizations without measured impact, re-raising issues already RESOLVED/ADDRESSED without new evidence.

---

## Part 2: Context

### What this batch covers (unchanged from Rev1)

Four plans delivering the complete JArvis UI Shell: Plan 81 unifies `backend/main.py` and `web/server.py` into a single FastAPI app and adds 12 API endpoints wired to real orchestrator methods. Plan 82 builds Zustand stores + persistent dashboard shell (CSS Grid, status bar, sidebar, main pane, right panel, bottom bar). Plan 83 builds operational panels (Tasks, Workers, Approvals, Costs, Memory Drawer, Settings Drawer, Skills, Help, Terminal Placeholder). Plan 84 delivers Vitest + Playwright E2E coverage.

### What changed in Rev2 (focus your review here)

Rev1 → Rev2 incorporated panel adjudication of 36 issues (12 critical, 8 significant, 10 minor, 6 other). Full adjudication log is at the end of the batch file (lines 1036–1092). The substantive changes the panel has NOT yet reviewed:

**New code introduced by resolutions:**
- **C1 (memoryStore)**: New `src/stores/memoryStore.ts` added to Plan 82 S1, plus memory polling hook in S2, plus tests in Plan 84 S1.
- **C8 (drawer/page routing)**: New `uiStore` with separate `activeView` and `activeDrawer` states. Memory/Settings open drawers, not views. Sidebar reduced from 9 to 7 nav items + 2 drawer buttons.
- **C12 (approval_gate public getter)**: New `list_pending()` public accessor on `core/approval_gate.py` added in Plan 81 S3, replacing direct `_pending_requests` access.
- **C2 (auth)**: Documented same-origin proxy strategy. No `NEXT_PUBLIC_` token. Test fixture `client_no_auth` added with `dependency_overrides`.
- **C6 (Playwright)**: Dual webServer replaced with single webServer + shell script. `timeout: 120000` added. Chromium-only for SSE tests.

**Rejected issue — please re-engage:**
- **C7 (Zustand vs URL routing)** — REJECTED. Author's reasoning: dashboard is a persistent shell with always-visible status/sidebar/bottom bars; URL routing causes full page reloads, losing SSE + terminal scrollback. Tradeoff accepted: no URL state (refresh resets to home view). Author considers this acceptable for a desktop-only operations tool.

### Author's reasoning (attack this, not the conclusion)

**On C7 rejection**: I'm 70% confident Zustand `activeView` is correct for v1. The risk if wrong: Plan 89+ would need to add URL routing without a rewrite. If the panel disagrees, I need a concrete scenario where v1 users would be harmed by the missing URL state.

**On new architectural additions (C1, C8, C12)**: I'm 80% confident these are sound because they mirror existing patterns (Zustand stores already exist in Plan 80; public getters are idiomatic). The risk if wrong: cross-store coupling bugs that won't surface until Plan 83 panels mount.

**On Playwright single-webServer shell script (C6)**: I'm 65% confident. Shell scripts are platform-specific and Devin runs on Windows PowerShell. Risk if wrong: CI Playwright runs fail with non-zero exit codes that look like test failures.

### Confidence levels (Rev2)

| Decision | Confidence | Risk if wrong |
|----------|------------|---------------|
| C1 memoryStore addition | 80% | Low — mirrors existing store patterns |
| C8 uiStore separation | 80% | Medium — drawer state transitions need test coverage |
| C12 list_pending() getter | 90% | Low — idiomatic Python |
| C2 same-origin auth | 75% | Medium — test fixture correctness unverified |
| C6 Playwright shell script | 65% | High — Windows/PowerShell compatibility |
| C7 Zustand routing (rejected) | 70% | Medium — v1 acceptable, v2+ cost unclear |

### Open questions for the panel

1. **C7 re-engagement**: Is there a concrete v1 user scenario where missing URL state causes harm? If yes, what is the minimum fix that doesn't force a rewrite?

2. **C6 Windows compatibility**: The Playwright shell script (single webServer) needs to start both backend (:8000) and frontend (:3000). On Windows PowerShell, what's the idiomatic equivalent of `&` background operator? Has the plan specified it?

3. **C8 drawer state transitions**: With `activeView` and `activeDrawer` as separate states, can both be non-empty simultaneously? If yes, what's the expected visual hierarchy (drawer over view)? The plan doesn't specify.

4. **C1 memoryStore polling cadence**: Memory slots could number in the thousands. What's the polling interval? Is there pagination? The plan adds the hook but doesn't specify rate or pagination.

---

## Part 3: Answer Format

Respond with:

1. **Verdict**: "Clean pass" OR "Issues found"
2. **If issues found, categorize**:
   - **HIGH** — would cause Devin STOP condition, test failure, broken build, data loss, security vulnerability, or Windows incompatibility. Blocks split.
   - **LOW** — style, naming, speculative future, perf without measured impact. Prompt Creator adjudicates.
3. **For each issue**: concrete failure scenario + suggested fix + cite specific plan lines
4. **C7 verdict specifically**: "Accept rejection" or "Reject the rejection" with reasoning
5. **Other concerns** — open field for anything not covered above

Permitted: "Clean pass" if Rev2 is sound. Do not invent issues to fill space.
