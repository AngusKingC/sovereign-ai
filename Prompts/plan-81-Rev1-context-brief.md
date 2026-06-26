# Plan 81 Rev1 Context Brief — Playwright E2E Testing Infrastructure

## Part 1: Roles/Rules

Your job is to find issues in this plan, not rewrite it. Assume this plan will fail — identify how.

Each issue must include: concrete failure scenario, evidence, impact, suggested fix (optional).

You may report "No issues found. PROCEED." — do not invent problems.

Ban: style, formatting, speculative features. Substance only.

---

## Part 2: Context

### Plan Scope

Install Playwright E2E testing so Devin can run `bun run test:e2e` and verify the UI works end-to-end before tagging a plan complete. No more manual DevTools inspection.

**Why**: prompt-80 shipped with broken Vitest tests (shell.test.tsx, 0 tests ran), missing pytest tests (6 vs 12-15 specified), and a CORS error the user hit on first run. All would have been caught by E2E tests.

**What ships**:
1. Playwright config with `webServer` auto-start (backend + frontend)
2. 15 E2E tests: shell layout, tool inspector + SSE, error states, CORS
3. Fix for broken `shell.test.tsx` (vitest alias issue — prerequisite)
4. PLANS.md Playwright baseline row
5. OR17 updated to cover Playwright + Vitest

### Key Dependencies

- prompt-80's `src/` (Next.js frontend) — must be functional
- prompt-80's `backend/main.py` (FastAPI stubs) — must start with `SOVEREIGN_DEV_TOKEN` set
- Rev3-Rev6 fixes must be in place (CORS, cookie auth, useSSE withCredentials, maxRetries)

### What Was Verified by GLM (2026-06-26, commit `41356ae`)

- `backend/main.py` exists with CORS middleware (`allow_origins=["http://localhost:3000"]`, `allow_credentials=True`)
- `samesite="lax"` (Rev4 fix), `SOVEREIGN_COOKIE_DOMAIN` + `SOVEREIGN_COOKIE_SECURE` env vars (Rev5 H3 fix)
- `useSSE.ts` has `withCredentials: true` + `maxRetries` + `retryCount` (Rev3 C3 + Rev5 H1 fixes)
- `DEV_TOKEN` requires env var, no fallback (Rev3 C4 fix) — **this caused the user's CORS error**
- `backend/__init__.py` exists (empty, Rev5 C8 fix)
- `tests/conftest.py` exists (Rev5 C2 fix)
- `src/__tests__/shell.test.tsx` exists but has import resolution failure (broken)
- `src/__tests__/stores.test.ts` works (9 tests pass)
- `tests/test_ui_backend.py` has only 6 `def test_` functions (plan specified ~12-15)

### Author's Reasoning (Attack This)

1. **Playwright over Cypress/Puppeteer.** Playwright is faster, has better API, `webServer` config auto-starts servers, multi-browser support. Cypress is slower, single-browser. Puppeteer is lower-level with no test runner. **Attack**: Is Playwright the right choice, or is the ecosystem risk (newer than Cypress) a concern?

2. **Chromium-only.** Install only Chromium, not Firefox/WebKit. Covers 95% of cases, keeps install fast. **Attack**: Should we test all 3 browsers from the start, or is Chromium sufficient for a self-hosted tool?

3. **webServer auto-start.** Config auto-starts backend (with `SOVEREIGN_DEV_TOKEN=dev-token-e2e`) + frontend. Devin doesn't need to manually start servers. `reuseExistingServer: !process.env.CI` — reuses in dev, fresh in CI. **Attack**: Is this reliable? What if ports are already in use? What if backend takes >30s to start?

4. **Fix shell.test.tsx as prerequisite (S2).** The broken Vitest test is fixed before E2E tests, because both use the same `@/` import alias. **Attack**: Should the Vitest fix be a separate plan, or is it correctly scoped as a prerequisite here?

5. **15 E2E tests.** Covers shell layout (6), tool inspector + SSE (5), error states (2), CORS (4). **Attack**: Is this enough coverage? Too much? Should the maxRetries test (35s slow) be included or deferred?

6. **data-testid attributes.** Added to ToolInspector cards, StatusBar latency, BottomBar activation grid. **Attack**: Should we use text-based selectors instead (more resilient to DOM changes), or are data-testid attributes the right call?

7. **OR17 update.** Extend baseline reconciliation to include Playwright + Vitest (was pytest-only). **Attack**: Is this a rule change that needs governance review, or is it a straightforward extension?

### Open Questions

1. **SSE testing timing**: Playwright's auto-waiting waits for elements, but SSE events arrive asynchronously. Is `timeout: 10_000` (10s) enough for the first event, given the mock backend sends every ~2s?

2. **maxRetries test**: The test waits 35s for 10 retries with backoff. Is this too slow for CI? Should it be marked `test.slow()` or deferred?

3. **webServer reliability**: If the backend crashes on startup (e.g., missing `SOVEREIGN_DEV_TOKEN`), Playwright's webServer will timeout after 30s. Is the error message clear enough for Devin to diagnose?

4. **CORS test approach**: The CORS test checks for console errors containing "CORS". Is this reliable across browsers, or should it intercept network requests instead?

### Confidence Levels

- Playwright install + config: 90% (standard, well-documented)
- webServer auto-start: 80% (backend needs env var, timing may vary)
- Shell layout tests: 85% (straightforward DOM assertions)
- Tool Inspector + SSE tests: 75% (async timing, SSE mocking complexity)
- Error state tests: 70% (console message capture, route interception)
- CORS tests: 85% (direct API requests + console error check)
- Vitest fix (S2): 90% (alias configuration is the likely root cause)
- Overall: 82%

---

## Part 3: Answer Format

1. **Pre-mortem** (1-2 sentences)
2. **Open questions** (address all 4)
3. **Issues** (0-N, with severity, scenario, evidence, fix)
4. **Other concerns**
5. **Verdict**: PROCEED / REVISE / REJECT

---

## Tier Disclosure

**Tier 1** (Claude only). Justification:
- Single subsystem (testing infrastructure in `src/e2e/`)
- Well-understood pattern (Playwright is industry standard)
- GLM confidence 82% (above 70%)
- Not novel territory (E2E testing is well-established)
- Reversible (Playwright is easy to remove)

If Claude's review surfaces significant disagreement on the webServer config or SSE testing approach, GLM will escalate to Tier 2.
