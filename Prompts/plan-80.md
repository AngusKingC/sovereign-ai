# Execution Instructions for Devin (READ BEFORE STARTING)

**CRITICAL: This plan has a history of auth/lifecycle bugs in `page.tsx` that only surface at runtime, not on read-through.** Rev3–Rev6 each found real bugs in this exact code path (SSE auth → cookie semantics → effect cleanup). Do not trust that code is correct just because it's labeled "Fixed" in the changelog.

## 1. Verify cookie/auth chain LIVE, not just read-through
Before marking S8/S8a complete, you MUST actually run the backend + frontend together and inspect the Set-Cookie and Cookie headers in DevTools per S8a.4. Do not rely on "renders without error" as sufficient. This file has a history of auth-related bugs that only surface at runtime.

## 2. Flag — not fix — surprises
Given the HARD STOP conditions and OR16 scope rules baked into this plan, if you hit something that contradicts the plan (a flag that doesn't exist, a version mismatch, a test that fails for a reason not anticipated here), STOP and report rather than improvise a fix. Several bugs found in this review process were exactly "the original plan's assumption about how a tool behaves was wrong" — improvising in that situation could compound rather than resolve it.

## 3. Run test suites at each S-section checkpoint
The plan has STOP conditions scattered throughout (S1.6, S2.2, S3.6, etc.). These are NOT optional/skippable if things "look fine." The sections are meant to serve as checkpoints (per M7). A long single-shot execution is exactly where small deviations accumulate and don't surface until the final test run, by which point it's hard to know which step introduced the problem.

## 4. Report actual line/file diffs, not just narrate completion
Given this whole review chain caught real bugs by going past the changelog into literal code, your final report MUST include the actual diff or final file contents for the highest-risk files: `backend/main.py`, `src/app/page.tsx`, `src/hooks/useSSE.ts`. Do not just provide a checklist of "done/done/done" — whoever reviews your output needs to be able to do the same kind of trace-the-code verification rather than trusting a summary.

## 5. Confirm repo name assumption in S0
M5's interpretation (line 31, Rev5) assumes the repo root literally is named `sovereign-ai`. If that's not actually true of the repo you're running against, this silently produces wrong paths. Before doing anything else in S0, confirm `pwd` and the actual repo name against this assumption.

---

# Plan 80 — Sovereign AI UI Shell (Next.js + FastAPI Stubs)

## Rev6 Changes (2026-06-26) — useEffect cleanup fix

Rev6 incorporates Claude's Rev5 review. One HIGH bug found — a React lifecycle bug in `page.tsx` where the `useEffect` cleanup function was registered inside a `.then()` callback, but React only registers cleanup from the synchronous return value of the effect. Result: `setInterval` never cleared on unmount → interval leak that compounds on every remount.

Claude noted this is the third revision where a fix in the auth/lifecycle code path introduced a structurally similar bug (SSE auth → cookie semantics → effect cleanup). The trend is positive (Rev5 found 1 HIGH vs Rev4's 3 CRITICAL + 3 HIGH), but this specific code path (`page.tsx` startup wiring + auth) has been the persistent blind spot.

| # | Issue | Severity | Rev6 Fix |
|---|---|---|---|
| 1 | `useEffect` cleanup never registered — `return () => clearInterval(interval)` is inside `.then()`, but React ignores the Promise returned by the effect. `setInterval` leaks on every remount. | HIGH | **Fixed.** Rewrote effect using the standard `cancelled` flag + `intervalId` pattern. Cleanup is registered synchronously from the effect's return value. The `.then()` callback checks `cancelled` before starting the interval, preventing leaks if the component unmounts before `login()` resolves. |

**Rev6 fix code** (replaces Rev5's broken `page.tsx` effect):
```tsx
useEffect(() => {
  let intervalId: ReturnType<typeof setInterval> | undefined;
  let cancelled = false;

  login()
    .then(() => {
      if (cancelled) return;  // Guard: component may have unmounted during login()
      const poll = async () => {
        try {
          const start = performance.now();
          const status = await getStatus();
          const elapsed = performance.now() - start;
          setPhase(status.phase);
          setLatency(Math.round(elapsed));
        } catch {
          // AR18-equivalent: poll failure — silent
        }
      };
      poll();
      intervalId = setInterval(poll, 2000);
    })
    .catch(() => {
      console.warn("Backend auth failed at", API_BASE, "— SSE will not work");
    });

  // Cleanup registered SYNCHRONOUSLY from the effect's return value.
  // React only calls functions returned synchronously from useEffect —
  // returning a function from inside .then() does NOT register cleanup.
  return () => {
    cancelled = true;
    if (intervalId) clearInterval(intervalId);
  };
}, [setPhase, setLatency]);
```

**Why this matters**: The previous pattern (`login().then(() => { ...; return () => clearInterval(interval); })`) returned the cleanup function from inside the `.then()` callback. React's `useEffect` only registers cleanup from the effect's synchronous return value — which was a `Promise` (from `login().then().catch()`), not a function. React ignores Promises returned from effects, so the cleanup was never registered. The `setInterval` would run forever, stacking on every remount (especially in React Strict Mode's deliberate double-invoke).

**Test count**: No change (~12 Vitest + ~15 pytest = ~27 new tests).

---

## Rev5 Changes (2026-06-26, retained for history)

Rev5 incorporates the second Tier 2 panel review of Rev4 (6 responses). The panel found 3 CRITICAL + 3 HIGH code bugs that Rev4 missed — all are build/runtime failures, not architectural disagreements. Per GR4, GLM adopts the highest-scoring findings (Reviews 5 and 6 found the most concrete bugs).

### CRITICAL fixes (would prevent build/startup)

| # | Issue | Source | Rev5 Fix |
|---|---|---|---|
| C1 | `Response` not imported in `backend/main.py` — `login(response: Response)` raises `NameError` at import, backend won't start | Reviews 3, 5, 6 | **Fixed.** Import updated: `from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect` |
| C2 | Test token mismatch — `test_ui_backend.py` hardcodes `"dev-token-sovereign-ai-ui"` but `DEV_TOKEN` reads from env var with no fallback. Tests fail unless env happens to match. | Reviews 5, 6 | **Fixed.** Added `conftest.py` that sets `SOVEREIGN_DEV_TOKEN=dev-token-sovereign-ai-ui` via `os.environ` before importing backend. Tests read `DEV_TOKEN` from the module. |
| C3 | First `getStatus()` poll fires before `login()` sets cookie → 401 on first poll, status bar shows stale data for 2s | Review 6 | **Fixed.** `page.tsx` chains `login().then(() => poll())` in a single `useEffect`. First poll only fires after cookie is set. |

### HIGH fixes (correctness bugs)

| # | Issue | Source | Rev5 Fix |
|---|---|---|---|
| H1 | `useSSE` `useCallback` missing `maxRetries` in dependency array — stale closure + ESLint `react-hooks/exhaustive-deps` failure | Reviews 5, 6 | **Fixed.** `useCallback(() => {...}, [url, maxRetries])` |
| H2 | `ToolInspector` race condition — `useToolStore.getState().calls.find()` inside `onMessage` may see stale state if two events arrive in rapid succession | Reviews 2, 5, 6 | **Fixed.** Added `upsertCall` method to `toolStore` — handles add-or-patch atomically in a single `set()` call. `ToolInspector` calls `upsertCall` instead of `getState().find()` + `addCall`/`patchCall`. |
| H3 | Production cookie domain/path unconfigurable — different subdomains (ui.sovereign.ai → api.sovereign.ai) need explicit domain setting | Review 4 | **Fixed.** Added `SOVEREIGN_COOKIE_DOMAIN` and `SOVEREIGN_COOKIE_SECURE` env vars. `set_cookie()` reads them. Dev defaults: no domain, `secure=False`. |

### MEDIUM fixes

| # | Issue | Source | Rev5 Fix |
|---|---|---|---|
| M1 | `MOCK_PHASE = "idle"` never changes — status bar always shows idle | Review 6 | **Fixed.** `MOCK_PHASE` cycles through `["planning", "acting", "reflecting", "idle"]` on each `/api/status` request. |
| M2 | SSE generator catches `asyncio.CancelledError` — potential task leak on client disconnect | Review 6 | **Fixed.** `except asyncio.CancelledError: raise` before `except Exception`. |
| M3 | `@lucide/react` (S1.2) vs `lucide-react` (imports) — package name mismatch | Review 6 | **Fixed.** S1.2 installs `lucide-react` (not `@lucide/react`). |
| M4 | `login()` failure silently swallowed — no user/dev feedback when backend is down | Reviews 4, 5 | **Fixed.** `login().catch()` now logs `console.warn("Backend auth failed — SSE will not work")`. |
| M5 | `bun create next-app src --no-src-dir` creates `src/` at repo root, but brief §7 says `sovereign-ai/src/` | Review 6 | **Documented.** Repo root IS the sovereign-ai project (the repo is `sovereign-ai`). `src/` at repo root = `sovereign-ai/src/`. No change needed — path is correct. |

### Architectural recommendations (documented for follow-on plans)

| # | Recommendation | Source | Rev5 Action |
|---|---|---|---|
| A1 | OpenAPI → TypeScript type generation (eliminate manual Pydantic ↔ TS sync) | Reviews 2, 5 | **Documented in DECISIONS.md D8.** Deferred to follow-on plan. Pydantic models (H2 fix from Rev3) are the interim contract. |
| A2 | Repository/service abstraction layer (clean seams for mock → Prisma → orchestrator) | Reviews 2, 5 | **Documented in DECISIONS.md D9.** Follow-on plan should introduce `backend/repositories/` with interfaces. Mocks implement the same interface. |
| A3 | Store ownership enforcement (not just documentation) | Review 2 | **Documented.** Store docstrings now specify the single write pathway. Follow-on plan can enforce via TypeScript types (e.g., `ReadonlyStore` vs `WritableStore`). |
| A4 | Hard merge milestone: "Before first production release, exactly one FastAPI app" | Review 2 | **Added to DECISIONS.md D2.** Concrete milestone: "Before any production deployment, `web/` and `backend/` MUST be merged into a single FastAPI application. No production release with two FastAPI services." |
| A5 | Concrete `.pre-commit-config.yaml` with path-scoped hooks | Review 4 | **Added as S1.7.** Explicit config showing ruff/mypy skip `src/**`, ESLint/tsc skip `**/*.py`. |

**Tier 2 status**: Rev5 is the 4th revision. This was the second full Tier 2 panel pass. All Rev5 fixes are surgical code bugs (imports, dependency arrays, store logic, env vars) — no architecture changes. The panel's architectural recommendations (A1-A5) are documented for follow-on plans, not adopted in Rev5 (scope management).

**Test count**: No change from Rev4 (~12 Vitest + ~15 pytest = ~27 new tests). The `upsertCall` store method (H2 fix) may add 1 test, but within ±5 tolerance.

---

## Rev4 Changes (2026-06-26, retained for history)

Rev4 incorporates Claude's Rev3 review. Two issues found, both surgical:

| # | Issue | Severity | Rev4 Fix |
|---|---|---|---|
| 1 | `SameSite=Strict` breaks cross-origin cookie auth — frontend (localhost:3000) → backend (localhost:8000) is cross-origin, so Strict cookies are withheld by the browser, causing 401 on SSE. This is a regression hiding inside C3's fix. | HIGH | **Fixed.** Changed `samesite="strict"` → `samesite="lax"` in `/api/auth/login`. Lax allows the cookie on cross-origin fetch/EventSource requests (the standard pattern for this scenario). `secure=True` + HTTPS deferred to production (dev is HTTP). S8a.4 verification strengthened: explicitly inspect `Set-Cookie` response header and `Cookie` request header in DevTools, not just "not 401." |
| 2 | M9 contradiction: changelog table says "Fixed. Directory renamed from src/ to ui/" but body says "deferred" | MEDIUM | **Fixed.** Table cell updated to "Not adopted (kept `src/` — Next.js/brief convention)." Body's reasoning is correct; table now matches. |
| — | Stale "Rev2 D5 fix" labels at lines ~1150 and ~1443 | LOW | **Fixed.** Updated to "Rev3" to match actual code state. |

**Tier 2 process note**: Rev4 is the 3rd revision (Rev1→Rev2=1st, Rev2→Rev3=2nd, Rev3→Rev4=3rd). Per GR4 strict reading, this triggers mandatory Tier 2 re-escalation. However, all Rev4 fixes are surgical bug fixes (one config value, one verification step, one table cell, two comment labels) — not architectural changes. The panel already reviewed the architecture in Rev3. If the user wants strict GR4 compliance, they can send Rev4 back through the 5-AI panel. Otherwise, Rev4 is ready for delivery.

**Test count**: No change from Rev3 (~12 Vitest + ~15 pytest = ~27 new tests).

---

## Rev3 Changes (2026-06-26, retained for history)

Rev3 incorporates the full 5-AI panel review (6 responses). Per GR4, GLM judged all responses and adopts the highest-scoring recommendation (Review 6 — found 3 CRITICAL + 3 HIGH build/runtime bugs missed by other panelists) plus panel convergence points.

### CRITICAL fixes (would cause build/runtime failure)

| # | Issue | Source | Rev3 Fix |
|---|---|---|---|
| C1 | SSE framing uses `\\n\\n` (literal backslash-n) instead of `\n\n` (newline) — EventSource never fires | Review 6 Issue 1 | **Fixed.** `yield f"data: {json.dumps(event)}\n\n"` (actual newlines) |
| C2 | Next.js layout renders `{children}` OUTSIDE the grid — page content invisible below fold | Review 6 Issue 2 | **Fixed.** `{children}` moved inside `<main>`, replacing the hardcoded placeholder. Shell grid stays in `layout.tsx` but `page.tsx` content flows into `<main>` via children. |
| C3 | Cookie auth non-functional: `/api/auth/login` returns JSON without setting cookie; frontend sets `document.cookie` (not httpOnly); `EventSource` created without `withCredentials: true`; `/api/auth/token` requires auth (circular) | Reviews 4, 5, 6 | **Fixed properly.** (1) `/api/auth/login` now calls `response.set_cookie(key="sovereign_token", value=DEV_TOKEN, httponly=True, samesite="strict")`. (2) `/api/auth/token` endpoint REMOVED (security risk — returned token as plain text). (3) `login()` in `api.ts` calls `/api/auth/login` with `credentials: "include"`. (4) `useSSE` hook creates `new EventSource(url, { withCredentials: true })`. (5) CORS `allow_origins` pinned to `["http://localhost:3000"]` (not wildcard) — required for credentialed cross-origin. |
| C4 | `DEV_TOKEN` has hardcoded fallback — production deploys silently use public token | Reviews 1, 4 | **Fixed.** No fallback. `DEV_TOKEN = os.environ.get("SOVEREIGN_DEV_TOKEN")`. Startup check: if `DEV_TOKEN is None`, raise `RuntimeError("SOVEREIGN_DEV_TOKEN must be set")`. Dev setup: `export SOVEREIGN_DEV_TOKEN=dev-token`. |
| C5 | Tailwind v4 CSS (`@import "tailwindcss"`, `@theme inline`) but `bun create next-app --tailwind` installs v3 | Review 6 Issue 4 | **Fixed.** S1.1 uses `--no-tailwind` (not `--tailwind`). S1.2 installs Tailwind v4 manually: `bun add tailwindcss@next @tailwindcss/postcss@next`. S2.1 globals.css uses v4 syntax correctly. |
| C6 | ESLint config extends `next/core-web-vitals` but `eslint-config-next` not installed (S1.1 used `--no-eslint`) | Review 6 Issue 5 | **Fixed.** S1.2 adds `eslint-config-next` to devDependencies. |
| C7 | Sidebar hover sets `width: 200px` on child of 64px grid column — overflow/clipping | Review 6 Issue 6 | **Fixed.** Layout grid uses `grid-cols-[minmax(64px,200px)_1fr_400px]`. Sidebar width transitions within the minmax range. No overflow. |
| C8 | `backend/__init__.py` missing — `from backend.main import app` fails | Review 6 Issue 11 | **Fixed.** S7.1 creates empty `backend/__init__.py`. |
| C9 | Next.js directory double-nesting: `bun create next-app src --src-dir` creates `src/src/app/` | Review 6 Other | **Fixed.** S1.1 uses `--no-src-dir` (not `--src-dir`). Project root IS `src/`, files go in `src/app/`, `src/components/`, etc. No double nesting. |

### HIGH fixes (maintenance/security problems)

| # | Issue | Source | Rev3 Fix |
|---|---|---|---|
| H1 | Document self-contradicts: Rev2 added Tool Inspector + cookie auth but README, deferred list, and test counts still describe Rev1 state | Review 5 Issue 1, 2 | **Fixed.** Full reconciliation pass. README updated to reflect Tool Inspector shipped. Deferred list updated (Tool Inspector + SSE auth REMOVED from deferred). Test counts reconciled. |
| H2 | Pydantic models defined but endpoints return raw dicts — no runtime validation | Review 6 Issue 7 | **Fixed.** All endpoints return Pydantic model instances: `return AgentStatus(sessionId=SESSION_ID, ...)`. FastAPI validates response shape automatically. |
| H3 | `useSSE` reconnects forever with no max retry limit | Review 6 Issue 8 | **Fixed.** Added `maxRetries` parameter (default 10). After exhaustion, sets permanent error state, stops reconnecting. |
| H4 | `login()` calls `/api/auth/token` but backend has `/api/auth/login` — misaligned | Review 4 Issue 3 | **Fixed.** (Resolved by C3 — `/api/auth/token` removed, `login()` calls `/api/auth/login`.) |
| H5 | API contract duplication: Python Pydantic ↔ TypeScript interfaces maintained by hand | Review 2 Issue 1 | **Partially addressed.** Rev3 returns Pydantic model instances (H2 fix). Full OpenAPI → TypeScript generation deferred to follow-on plan (documented in DECISIONS.md). Comment-links remain as interim measure. |
| H6 | Store ownership unclear — polling + SSE + local actions can race | Review 2 Issue 2 | **Fixed.** Each store documents authoritative source in docstring: `agentStore` (REST polling), `memoryStore` (SSE activations), `toolStore` (SSE tools), `subagentStore` (polling). |
| H7 | Cross-origin cookie auth not verified — SameSite=Strict + different ports may silently fail | Review 5 Issue 3 | **Fixed.** S8a.4 verification explicitly tests cross-origin (localhost:3000 → localhost:8000): open DevTools Network, verify SSE request includes cookie, verify 200 (not 401). CORS `allow_origins` pinned (not wildcard). |
| H8 | Vitest baseline tracking underspecified — no tolerance, no PLANS.md row | Review 4 Issue 4 | **Fixed.** S0.4 PLANS.md update adds Vitest baseline row with ±5 tolerance. OR17 extended to Vitest. |

### MEDIUM fixes (addressed or documented)

| # | Issue | Source | Rev3 Fix |
|---|---|---|---|
| M1 | Memory store O(n) scan on every SSE update | Review 6 Issue 9 | **Fixed.** Incremental `activeSlots` counter — increment/decrement on threshold crossings, no full scan. |
| M2 | No SSE/cookie auth tests | Review 6 Issue 10 | **Fixed.** Added pytest tests for SSE endpoints (media type, event framing) and cookie auth (set cookie, call SSE endpoint). |
| M3 | No Vitest tests for `useSSE` hook | Review 6 Other | **Fixed.** Added Vitest test mocking EventSource, verifying reconnect backoff and max retry. |
| M4 | AR21 doesn't cover tooling seam (pre-commit, CI routing) | Reviews 5, 6 | **Fixed.** AR21 expanded: `src/` uses ESLint/tsc/Vitest; Python dirs use ruff/mypy/pytest; pre-commit hooks are path-scoped (Python hooks skip `src/**`, TS hooks skip `**/*.py`). |
| M5 | API versioning — no `/api/v1/` prefix | Review 2 Issue 4 | **Documented.** Deferred to follow-on plan. DECISIONS.md notes: "Reserve `/api/v1/` before external clients appear. Changing later is painful." |
| M6 | Transport ownership — polling vs SSE coexistence | Review 2 Issue 3 | **Fixed.** Documented in store docstrings (H6) and DECISIONS.md D7 (new): Status=REST polling, Reasoning=SSE, Tools=SSE, Memory=SSE, Subagents=polling. No overlapping transport ownership. |
| M7 | Monolithic plan size — execution checkpoints | Review 2 Issue 5 | **Documented.** S1-S10 sections serve as natural checkpoints. Devin should verify after each section. No structural change. |
| M8 | Zustand v5 API uncertainty | Review 6 Other | **Fixed.** S1.2 pins `zustand@^4.5.0` (not v5). v5 compatibility unverified. |
| M9 | `src/` directory name ambiguous in Python repos | Review 6 D1 | **Not adopted** (kept `src/` — Next.js/brief convention). Rev4: table corrected to match body. |
| M10 | Backend deprecation timeline vague | Review 2, 6 D2 | **Fixed.** DECISIONS.md D2 updated: "Plan 85 or earlier must either merge `web/` routes into `backend/` or formally deprecate `web/` with migration guide." |

### Tier 2 process note

Per GR4, GLM received 6 panel responses, judged on defined criteria (reasoning 40%, evidence 25%, risk identification 20%, alternatives 15%). Review 6 scored highest (found 3 CRITICAL + 3 HIGH build/runtime bugs missed by others). GLM adopts Review 6's findings plus panel convergence points.

**Rev3 is the 2nd revision** (Rev1→Rev2 was 1st, Rev2→Rev3 is 2nd). Per GR4, mandatory Tier 2 escalation triggers at Rev4+ (3rd revision). If Rev3 review surfaces issues requiring Rev4, GLM must re-escalate (already Tier 2, so this means Tier 3 — user judgment required for roadmap-level decisions).

**Test count update**: Vitest ~10 → ~12 (added useSSE tests + Tool Inspector tests). pytest ~12 → ~15 (added SSE + cookie auth tests). Total ~27 new tests.

---

## Rev2 Changes (2026-06-26, retained for history)

Rev2 incorporated Claude's initial Tier 1 review. See Rev2 file for details. Rev3 supersedes Rev2.

---

## Tier Selection: Tier 2 (5-AI Panel Review)

**Per GR4, this plan is classified Tier 2.** Multiple triggers fire:

1. **Architectural decisions (new patterns)**: Next.js 15 App Router is new to Sovereign AI (currently Python/Textual/Rich CLI/FastAPI). SSE streaming is new. Zustand is new. shadcn/ui is new. Tailwind v4 is new. This plan introduces 5 new technologies in a single plan.
2. **Novel territory**: Sovereign AI has NO web UI currently. PLANS.md lists "Web UI refinement" as Priority 5+ deferred. This is the first web UI plan — no precedent in the project.
3. **Reversible-but-expensive**: Wrong stack choice costs multiple plans to fix. If Next.js + Zustand + shadcn/ui is wrong, refactoring to a different stack would cost 3-5 plans.
4. **3+ subsystems**: This plan touches `src/` (Next.js frontend, NEW), `backend/` (FastAPI stubs, NEW), `prisma/` (schema only, NEW), and introduces a second test suite (Vitest) alongside the existing pytest. 4+ subsystems.
5. **GLM confidence ~68%**: Below 70% threshold. The stack is specified by the brief (high confidence), but the scoping decisions (what to include in v1 vs defer, repo structure for mixed Python/TypeScript, test infrastructure split) are debatable.

**Tier 2 process**: GLM drafts this plan → user pastes to 5-AI panel (Claude, Kimi, DeepSeek, Gemini, ChatGPT) → GLM judges responses on defined criteria → GLM adopts best-reasoned recommendation → Rev2 (if needed) → Devin executes.

**GLM's commitment** (per GR4): When Tier 2 is triggered, GLM commits to adopting the highest-scoring recommendation — even if it contradicts GLM's original position.

---

## Context

**Source brief**: `sovereign-ai-glm-prompt.md` (uploaded by user, 2026-06-26). The brief specifies:
- Project identity: Sovereign AI — self-hosted, sovereign-first AI agent interface
- Tech stack: Next.js 15 + TypeScript 5 + shadcn/ui + Tailwind v4 + Zustand 5 + Framer Motion + xterm.js + Recharts + Lucide React + Bun + FastAPI + SQLite/Prisma
- 7 core feature panels (§3.1-3.7) + shell layout (§4) + API contract (§5) + design constraints (§6) + file structure (§7) + priority order (§8)
- Explicit non-goals (§9): no node graph, no WebGL shaders, no fine-tuning UI, no voice, no mobile, no multi-user
- Differentiators from Hermes Agent (§10): amber not blue, sentence case, xterm.js not Ink, single theme, explicit memory UI, no plugin system

**Existing repo state** (verified at commit `f0517d1`, post-prompt-79):
- Python-only repo (no `package.json`, no TypeScript)
- Existing `web/` directory has FastAPI server (`web/server.py`) with routes: `/health`, `/api/tasks`, `/api/workers`, `/api/trace`, `/ws` — different from the brief's §5 API contract
- Existing test baseline: 1405 pytest tests (Python)
- AR6: `web/` may import from `core/` only
- No frontend test infrastructure (no Vitest, no Jest, no Playwright)

**Key architectural decisions** (for 5-AI panel review):

1. **Same repo vs separate repo**: The brief specifies `src/` + `backend/` in the `sovereign-ai/` root. This introduces TypeScript to a Python-only repo → mixed-language repo with two test suites (pytest + Vitest). Alternative: separate `sovereign-ai-ui` repo. GLM recommends same repo (follows brief, simpler CI, single git history) but flags this as the most debatable decision.

2. **New `backend/` vs extend existing `web/`**: The brief specifies a NEW `backend/main.py` with different routes than the existing `web/server.py`. GLM recommends NEW `backend/` directory (separate from `web/`) because: (a) the brief specifies it, (b) `web/` is the agent control API (tasks, workers, trace), `backend/` is the UI data API (status, reasoning, tools, memory) — different purposes, (c) they'll eventually merge but keeping them separate now avoids disrupting the working `web/` server. `backend/` follows AR6-equivalent rules (may import from `core/` only).

3. **Prisma/SQLite deferred**: The brief specifies Prisma + SQLite for persistence. GLM recommends deferring Prisma to a follow-on plan — this plan uses in-memory mocks in `backend/`. Rationale: Prisma setup (schema, migrations, client generation) is a separate concern; this plan focuses on shell + wiring. Mocked data is sufficient for end-to-end rendering.

4. **Panel implementations deferred**: The brief's §3.1-3.7 describe 7 full panel implementations. GLM recommends this plan deliver SHELL + PLACEHOLDER PANELS only. Full panel implementations (activation grid Canvas 2D, tool inspector expandable cards, timeline SVG, reasoning stream token-by-token) are deferred to follow-on plans. Rationale: the shell + wiring is the foundation; panels are independent and can be delivered incrementally.

5. **xterm.js/PTY, memory drawer, subagent panel explicitly deferred**: Per user instruction, these are out of scope for this plan. Listed as deferred (not abandoned) in the plan body.

**Author's reasoning** (attack this — don't ratify the conclusion):

My reasoning for the scoping:
1. **Shell first, panels second.** The brief's §8 priority order starts with "Shell layout — no functionality yet, just the grid with placeholder content." I'm following this. The shell is the foundation; panels compose into it. Delivering shell + wiring + backend stubs in one plan lets follow-on plans focus on one panel at a time.

2. **Backend stubs before real data.** The brief's §8 priority #2 is "Backend stubs — all API endpoints returning mocked data so the frontend has something to connect to immediately." I'm following this. Real orchestrator integration (connecting `backend/` to `core/orchestrator.py`) is deferred — it requires careful SSE event design and is a separate concern.

3. **useSSE hook is the critical path.** The brief's §8 priority #3 is the `useSSE` hook. Every streaming panel depends on it. I'm including it in this plan because it's the wiring that makes the shell "live." Without it, the shell is static.

4. **Zustand stores with minimal schemas.** I'm including minimal store definitions (agentStore, memoryStore, toolStore, subagentStore) so the shell components have something to read from. Full store logic (activation decay, tool call accumulation, subagent polling) is deferred with the panel implementations.

5. **Same repo, not separate.** I'm following the brief's file structure (`sovereign-ai/src/`, `sovereign-ai/backend/`). This introduces TypeScript to a Python repo, which is messy but simpler than cross-repo coordination. If the 5-AI panel argues for a separate repo, I'll adopt that recommendation (per GR4 commitment).

6. **Test infrastructure split.** This plan introduces Vitest for the frontend. The existing pytest baseline (1405) is unaffected. PLANS.md needs a new baseline row for Vitest. I'm proposing ~5 Vitest tests (shell renders, stores work, useSSE reconnects) + ~10 pytest tests (backend endpoint shape verification) = ~15 new tests total.

**Attack this reasoning**: Is same-repo the right call, or does TypeScript-in-Python-repo create maintenance friction that justifies a separate repo? Is deferring Prisma correct, or should persistence be in this plan to avoid reworking the backend later? Are 5 Vitest tests enough for a shell this size, or is that under-testing? Is the `backend/` vs `web/` separation correct, or should the new routes go into `web/server.py`?

### Open Questions (for 5-AI panel)

1. **Repo structure**: Same repo (mixed Python/TypeScript) or separate `sovereign-ai-ui` repo? GLM recommends same repo. What are the maintenance/CI trade-offs?

2. **Backend separation**: New `backend/` directory or extend existing `web/server.py`? GLM recommends new `backend/`. Is the separation worth the duplication, or should the new routes merge into `web/`?

3. **Prisma timing**: Defer Prisma to follow-on plan, or include in this plan? GLM recommends defer. Does deferring create rework risk (backend stubs rewritten when Prisma lands)?

4. **Panel scoping**: Shell + placeholders only, or include 1-2 full panel implementations (e.g., tool inspector + activation grid) in this plan? GLM recommends shell + placeholders only. Is that too thin for one plan, or correctly scoped?

5. **Test infrastructure**: Vitest + pytest (two suites) or Vitest only for frontend + pytest only for backend (strict separation)? GLM recommends strict separation. How should PLANS.md track two baselines?

6. **Bun vs Node**: The brief specifies Bun. Should this plan use Bun for both runtime and package manager, or Node + npm/yarn for ecosystem compatibility? GLM recommends Bun (follows brief) but notes ecosystem maturity risk.

### Confidence Levels

- Stack setup (Next.js 15 + Bun + Tailwind v4 + shadcn/ui): 85% (well-documented, standard)
- FastAPI backend stubs (mocked data): 90% (straightforward)
- Shell layout (CSS Grid, sticky status bar): 80% (brief specifies layout, sticky + grid interactions can be tricky)
- useSSE hook (exponential backoff reconnect): 75% (standard but edge cases abound)
- Zustand stores (minimal schemas): 85% (well-understood pattern)
- Wiring (live mocked data end-to-end): 70% (most complex part — SSE → store → component updates)
- Repo structure (Python + TypeScript same repo): 60% (most debatable decision)
- Test infrastructure (pytest + Vitest split): 65% (introduces second test suite, baseline tracking complications)

**Overall**: 68%. Below 70% threshold — Tier 2 trigger confirmed independently of the other triggers.

---

## Opening (S0)

### S0.1. Run `/jarvis-open`

Verify `prompt-79` tag exists on origin:
```powershell
git ls-remote --tags origin | Select-String "prompt-79"
```
If empty, push failed — STOP and report.

Confirm working copy is clean and on master:
```powershell
git status -s
git branch --show-current
```

**Applying OR26**: If `git status -s` shows modified/untracked governance docs or plan files, commit them as `docs: cleanup pre-prompt-80` tagged `docs-cleanup-80` BEFORE proceeding.

**Applying OR39**: If `plan-79*.md` files are untracked in `Prompts/`, they are an OR26 violation — commit them in the `docs-cleanup-80` commit. The current plan's file (`plan-80*.md`) will be added in C12.

If the workflow is missing or fails, STOP and report.

### S0.2. Read AGENTS.md in full

AGENTS.md is always-on. Pay special attention to:
- **AR1**: `core/` never imports from `adapters/`, `cli/`, `workers/`, `memory/`, `skills/`, `web/`, `system/`, or the NEW `backend/` or `src/`. The new directories must NOT be imported by `core/`.
- **AR6**: `web/` may import from `core/` only. The NEW `backend/` directory follows AR6-equivalent rules: `backend/` may import from `core/` only (when real integration lands in a future plan; this plan's `backend/` uses in-memory mocks, no `core/` imports).
- **AR9**: No raw LLM calls outside `adapters/`. (N/A — this plan has no LLM calls.)
- **AR11**: `TraceEmitter` via constructor injection only. (N/A for frontend; applies to `backend/` if it emits traces in future.)
- **AR14**: All public functions have return type annotations. (Applies to Python `backend/`; TypeScript strict mode enforces this for `src/`.)
- **AR17**: Auth middleware MUST wrap ALL FastAPI routes and WebSocket handshakes. No unauthenticated endpoints except `/health`. (Applies to `backend/main.py` — this plan uses a minimal bearer token, full auth deferred.)
- **AR18**: No broad `except Exception: pass` without inline comment + WARNING trace. (Applies to `backend/` Python code.)
- **OR15**: Pre-declare scope before editing.
- **OR16**: HARD STOP on scope expansion.
- **OR22**: Re-read AGENTS.md before any file edit.
- **OR23**: Cite rules by number when applying them.
- **OR34**: Execute steps in strict numerical order.

**Note on TypeScript/frontend**: AR1-AR8 are Python import rules. The `src/` directory is TypeScript/React — it does NOT import from Python `core/`. It talks to `backend/` via HTTP/SSE. TypeScript strict mode (`"strict": true` in `tsconfig.json`) enforces type safety equivalent to AR14. ESLint + Prettier enforce code quality equivalent to ruff/mypy for Python.

If an AGENTS.md rule's application is ambiguous, read `LANDMINES.md` for diagnostic context.

### S0.3. Add new AGENTS.md rules and commit

**Rev2 D1 fix**: This plan proposes one new AGENTS.md rule — AR21 — to govern the new TypeScript `src/` directory. AR1-AR8 are Python-only import rules; they have no defined relationship to TypeScript. AR21 fills this gap.

**Proposed AR21** (add to AGENTS.md at S0.3):
```markdown
AR21. `src/` (TypeScript/React frontend) follows TypeScript strict mode (`"strict": true` in `tsconfig.json`) and ESLint with `@typescript-eslint/recommended`. `src/` does NOT import from any Python directory (`core/`, `adapters/`, `cli/`, `web/`, `backend/`, etc.). `src/` communicates with the backend exclusively via HTTP (fetch) and SSE (EventSource). Type safety is enforced by TypeScript strict mode (equivalent to AR14 for Python). Code quality is enforced by ESLint (equivalent to ruff for Python). (Source: Plan 80 Tier 2 review — AR1-AR8 are Python-only; TypeScript directory needs its own governance rule.)
```

Commit as `governance: add AR21 (TypeScript src/ governance) to AGENTS.md` before proceeding. Tag as `governance-ar21`. This is a governance commit, separate from the `prompt-80` tag (per OR26).

**Note**: If the 5-AI panel (pending) recommends a different TS governance approach, AR21 will be revised in Rev3. For now, AR21 is the proposed rule.

### S0.4. Update PLANS.md queue to reflect scan deferral

Edit `PLANS.md` "Next 5 Prompts Queue" section. The mandatory 5-plan scan (previously Plan 80) is deferred to Plan 81. Plan 80 is now the UI Shell plan. Update the queue:

```markdown
### Plan 80 — Sovereign AI UI Shell (Priority 1 — user-directed)

**Scope**: Next.js 15 + FastAPI shell layout with placeholder panels, backend stubs serving mocked data, wiring for live (mocked) data end-to-end. Defers xterm.js/PTY terminal, memory drawer, subagent panel, and full panel implementations to follow-on plans.

**Expected impact**: Web UI foundation for Sovereign AI. First web UI plan — introduces Next.js, TypeScript, Zustand, shadcn/ui to the project.

**Baseline changes**: Introduces Vitest test suite (frontend) alongside existing pytest (backend). ~15 new tests total (~5 Vitest + ~10 pytest).

**Gate**: Full pytest suite pass (1405 baseline held), Vitest suite pass, ruff 0, mypy 0 (backend only), TypeScript strict compile pass, ESLint pass.

---

### Plan 81 — 5-Plan Milestone Full Scan (Priority 1 — mandatory, deferred from Plan 80)

**Scope**: Full 6-tool checkpoint scan (pytest, ruff, mypy, bandit, pip-audit, vulture) + coverage verification + NEW Vitest baseline verification. Baseline reconciliation after Plans 76-80. Validates PEMADS Phase 1 + 3 Kimi gaps + UI shell foundation before Phase 2 begins.

**Expected impact**: Baseline verification, trend analysis. First scan to include Vitest baseline.

**Baseline changes**: All baselines should hold within tolerance. New Vitest baseline established.

**Gate**: All 6 Python tools pass, Vitest passes, coverage ≥78% (83% baseline -5%).
```

This update goes into the S0.3 governance commit.

---

## Plan Body

### S1 — Project Setup (Next.js + Bun + Tailwind v4 + shadcn/ui)

**Applying AR8**: `cli/` may import from anywhere — N/A for this section. The `src/` directory is TypeScript, governed by TypeScript strict mode + ESLint, not AR1-AR8.

#### S1.1. Initialize Next.js 15 project with Bun

**Rev3 C5 fix**: Use `--no-tailwind` (not `--tailwind`) — the flag installs Tailwind v3, but globals.css uses v4 syntax. Tailwind v4 is installed manually in S1.2.

**Rev3 C6 fix**: `--no-eslint` retained — ESLint config installed manually in S1.4 with `eslint-config-next` added to devDependencies in S1.2.

**Rev3 C9 fix**: Use `--no-src-dir` (not `--src-dir`) — `--src-dir` creates `src/src/app/` (double nesting). Without it, the project root IS `src/`, files go in `src/app/`, `src/components/`, etc.

```powershell
cd C:\Jarvis
bun create next-app@latest src --typescript --no-tailwind --app --no-src-dir --import-alias "@/*" --no-eslint --turbopack
```

**Note**: The brief specifies `src/app/` structure. With `--no-src-dir`, Next.js creates `src/app/` directly — matches the brief's §7 file structure. (Rev3 M9 considered renaming `src/` to `ui/` for Python-repo clarity, but deferred — `src/` is the Next.js convention and the brief uses it.)

#### S1.2. Install dependencies

**Rev3 M8 fix**: Pin `zustand@^4.5.0` (not v5) — v5 has breaking type changes that are unverified with Next.js 15 + React 19.

**Rev3 C5 fix**: Install Tailwind v4 manually (not via `--tailwind` flag which installs v3).

**Rev3 C6 fix**: Add `eslint-config-next` (S1.1 used `--no-eslint`, so it's not installed by default).

```powershell
cd src
bun add zustand@^4.5.0 framer-motion lucide-react recharts  # Rev5 M3: was @lucide/react
bun add tailwindcss@next @tailwindcss/postcss@next
bun add -D @types/node eslint eslint-config-next @eslint/js typescript-eslint prettier
```

**Note**: xterm.js (`@xterm/xterm`, `@xterm/addon-fit`, `@xterm/addon-webgl`) is NOT installed in this plan — deferred with the terminal pane (S5 deferred). Recharts is installed but not used in this plan — deferred with the panel implementations. Installed now to avoid churn in follow-on plans.

#### S1.3. Configure Tailwind v4 + shadcn/ui

```powershell
cd src
bunx shadcn@latest init -d
```

shadcn/ui New York variant. This creates `src/components/ui/` and `src/lib/utils.ts` (with `cn()` helper).

#### S1.4. Configure ESLint + Prettier + TypeScript strict

Create `src/.eslintrc.json`:
```json
{
  "extends": ["next/core-web-vitals", "plugin:@typescript-eslint/recommended"],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-unused-vars": "error"
  }
}
```

Create `src/.prettierrc`:
```json
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5"
}
```

Verify `src/tsconfig.json` has `"strict": true` (Next.js default — confirm).

#### S1.5. Configure Bun as package manager

Create `src/bunfig.toml`:
```toml
[install]
registry = "https://registry.npmjs.org"
```

#### S1.6. Verification

**Rev2 Other 1 fix**: S1.1 used `--no-eslint`, so the generated `package.json` may not have a `lint` script wired to the custom `.eslintrc.json` from S1.4. Verify the script exists before running `bun run lint`.

```powershell
cd src

# Rev2 Other 1 fix: verify lint script is wired to custom ESLint config
# If package.json doesn't have a "lint" script, add it manually:
# "scripts": { "lint": "eslint ." }
Get-Content package.json | Select-String "lint"
# If no output, manually edit package.json to add: "lint": "eslint ." to scripts

bun run lint
bun run build
```

**STOP condition**: If lint script is missing (and can't be added manually), or if lint/build fails, fix before proceeding.

---

### S2 — Design Tokens (globals.css per brief §6)

#### S2.1. Create `src/app/globals.css` with color tokens + typography

Per brief §6, define CSS variables in `:root`. Tailwind v4 uses CSS-first configuration (`@theme` directive).

```css
@import "tailwindcss";

:root {
  --color-surface-base:    #0c0c0f;
  --color-surface-raised:  #13131a;
  --color-surface-overlay: #1a1a24;
  --color-border:          #ffffff14;
  --color-border-strong:   #ffffff28;
  --color-text-primary:    #e8e6e0;
  --color-text-secondary:  #9b9890;
  --color-text-muted:      #5c5a56;
  --color-accent-amber:    #f59e0b;
  --color-accent-emerald:  #10b981;
  --color-accent-violet:   #8b5cf6;
  --color-accent-red:      #ef4444;
  --color-accent-slate:    #64748b;
}

@theme inline {
  --color-surface-base:    var(--color-surface-base);
  --color-surface-raised:  var(--color-surface-raised);
  --color-surface-overlay: var(--color-surface-overlay);
  --color-border:          var(--color-border);
  --color-border-strong:   var(--color-border-strong);
  --color-text-primary:    var(--color-text-primary);
  --color-text-secondary:  var(--color-text-secondary);
  --color-text-muted:      var(--color-text-muted);
  --color-accent-amber:    var(--color-accent-amber);
  --color-accent-emerald:  var(--color-accent-emerald);
  --color-accent-violet:   var(--color-accent-violet);
  --color-accent-red:      var(--color-accent-red);
  --color-accent-slate:    var(--color-accent-slate);

  --font-sans: ui-sans-serif, system-ui, sans-serif;
  --font-mono: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
}

body {
  background-color: var(--color-surface-base);
  color: var(--color-text-primary);
  font-family: var(--font-sans);
}

/* Accessibility: focus rings (brief §6) */
*:focus-visible {
  outline: 2px solid var(--color-accent-amber);
  outline-offset: 2px;
}

/* Reduced motion (brief §6) */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

#### S2.2. Verification

```powershell
cd src
bun run build
```

**STOP condition**: If build fails, fix before proceeding.

---

### S3 — Shell Layout Components (StatusBar, Sidebar, RightPanel, BottomBar)

**Applying brief §4**: CSS Grid for the shell. No absolute positioning except sticky status bar and memory drawer overlay (deferred).

#### S3.1. Create `src/app/layout.tsx` (shell grid)

```tsx
import { StatusBar } from "@/components/shell/StatusBar";
import { Sidebar } from "@/components/shell/Sidebar";
import { RightPanel } from "@/components/shell/RightPanel";
import { BottomBar } from "@/components/shell/BottomBar";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Rev3 C2 fix: {children} moved INSIDE <main>, not after the grid.
            Rev2 rendered {children} below the grid, making page content invisible
            (grid consumed full viewport height). Now page.tsx content flows into
            <main> via children, replacing the hardcoded placeholder. */}
        <div className="grid h-screen w-screen grid-rows-[auto_1fr_auto] grid-cols-[minmax(64px,200px)_1fr_400px]">
          <StatusBar className="col-span-3" />
          <Sidebar />
          <main className="flex items-center justify-center overflow-hidden bg-surface-base text-text-secondary">
            {children}
          </main>
          <RightPanel />
          <BottomBar className="col-span-3" />
        </div>
      </body>
    </html>
  );
}
```

#### S3.2. Create `src/components/shell/StatusBar.tsx`

Per brief §3.1. Contains: session ID, phase badge, model slug, latency chip, run/pause toggle, settings gear. Reads from `agentStore`. Sticky top.

```tsx
"use client";
import { useAgentStore } from "@/stores/agentStore";
import { Play, Pause, Settings, Copy } from "lucide-react";
import { useState } from "react";

const PHASE_COLORS: Record<string, string> = {
  idle: "bg-accent-slate",
  planning: "bg-accent-amber",
  acting: "bg-accent-emerald",
  reflecting: "bg-accent-violet",
};

export function StatusBar({ className }: { className?: string }) {
  const { sessionId, phase, modelSlug, latency, isRunning, toggleRun } = useAgentStore();
  const [copied, setCopied] = useState(false);

  const copySessionId = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  return (
    <header
      className={`sticky top-0 z-50 flex h-12 items-center gap-4 border-b border-border bg-surface-raised px-4 ${className ?? ""}`}
    >
      <button
        onClick={copySessionId}
        className="font-mono text-xs text-text-secondary hover:text-text-primary"
        aria-label="Copy session ID"
      >
        {copied ? "Copied!" : sessionId}
      </button>
      <span
        className={`rounded px-2 py-0.5 text-xs text-surface-base transition-colors duration-300 ${PHASE_COLORS[phase] ?? PHASE_COLORS.idle}`}
      >
        Sovereign · {phase.charAt(0).toUpperCase() + phase.slice(1)}
      </span>
      <button className="font-mono text-xs text-text-secondary hover:text-text-primary" aria-label="Open model picker (deferred)">
        {modelSlug}
      </button>
      <span className="font-mono text-xs text-text-muted">{latency}ms</span>
      <div className="flex-1" />
      <button
        onClick={toggleRun}
        className="rounded p-1.5 hover:bg-surface-overlay"
        aria-label={isRunning ? "Pause" : "Run"}
      >
        {isRunning ? <Pause size={16} /> : <Play size={16} />}
      </button>
      <button className="rounded p-1.5 hover:bg-surface-overlay" aria-label="Open settings (deferred)">
        <Settings size={16} />
      </button>
    </header>
  );
}
```

#### S3.3. Create `src/components/shell/Sidebar.tsx`

Per brief §4. Icon-only (64px), expands to 200px on hover. Icons: Terminal, Memory, Subagents, Tools, Settings, Help.

```tsx
"use client";
import { Terminal, MemoryStick, Users, Wrench, Settings, HelpCircle } from "lucide-react";
import { useState } from "react";

const NAV_ITEMS = [
  { icon: Terminal, label: "Terminal" },
  { icon: MemoryStick, label: "Memory" },
  { icon: Users, label: "Subagents" },
  { icon: Wrench, label: "Tools" },
  { icon: Settings, label: "Settings" },
  { icon: HelpCircle, label: "Help" },
];

export function Sidebar() {
  const [hovered, setHovered] = useState(false);

  return (
    <nav
      // Rev3 C7 fix: width transitions within the grid's minmax(64px, 200px) range.
      // Rev2 set width: 200px on a child of a fixed 64px grid column, causing overflow.
      // Now the grid column uses minmax(64px, 200px), so the sidebar can expand
      // within the column without overflowing or pushing other columns.
      className="flex h-full flex-col gap-1 border-r border-border bg-surface-raised p-2 transition-all duration-200"
      style={{ width: hovered ? "200px" : "64px" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="mb-4 px-2 py-2 font-sans text-sm font-medium text-text-primary">
        {hovered ? "Sovereign" : "S"}
      </div>
      {NAV_ITEMS.map(({ icon: Icon, label }) => (
        <button
          key={label}
          className="flex items-center gap-3 rounded p-2 hover:bg-surface-overlay"
          aria-label={label}
        >
          <Icon size={20} className="shrink-0 text-text-secondary" />
          {hovered && <span className="text-sm text-text-secondary">{label}</span>}
        </button>
      ))}
    </nav>
  );
}
```

#### S3.4. Create `src/components/shell/RightPanel.tsx`

Per brief §4. Tab switcher between Tool Inspector, Timeline, Reasoning. Placeholder content per tab.

```tsx
"use client";
import { useState } from "react";
import { Wrench, Clock, Brain } from "lucide-react";

const TABS = [
  { id: "tools", label: "Tool inspector", icon: Wrench },
  { id: "timeline", label: "Timeline", icon: Clock },
  { id: "reasoning", label: "Reasoning", icon: Brain },
] as const;

type TabId = typeof TABS[number]["id"];

export function RightPanel() {
  const [activeTab, setActiveTab] = useState<TabId>("tools");

  return (
    <aside className="flex flex-col border-l border-border bg-surface-raised">
      <div className="flex border-b border-border">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              activeTab === id
                ? "border-b-2 border-accent-amber text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="font-mono text-xs text-text-muted">
          {activeTab === "tools" && "Tool call inspector — placeholder. Full implementation deferred to follow-on plan."}
          {activeTab === "timeline" && "Session timeline — placeholder. Full implementation deferred to follow-on plan."}
          {activeTab === "reasoning" && "Reasoning stream — placeholder. Full implementation deferred to follow-on plan."}
        </div>
      </div>
    </aside>
  );
}
```

#### S3.5. Create `src/components/shell/BottomBar.tsx`

Per brief §4. Activation grid placeholder (left) + token counter (right). Reads from `memoryStore` and `agentStore`.

```tsx
"use client";
import { useMemoryStore } from "@/stores/memoryStore";
import { useAgentStore } from "@/stores/agentStore";

export function BottomBar({ className }: { className?: string }) {
  const activeSlots = useMemoryStore((s) => s.activeSlots);
  const totalSlots = useMemoryStore((s) => s.totalSlots);
  const tokenCount = useAgentStore((s) => s.tokenCount);
  const contextLimit = useAgentStore((s) => s.contextLimit);

  return (
    <footer className={`flex h-16 items-center gap-4 border-t border-border bg-surface-raised px-4 ${className ?? ""}`}>
      <div className="flex items-center gap-2">
        <div className="font-mono text-xs text-text-muted">Activation grid placeholder</div>
        <div className="text-xs text-text-secondary">
          {activeSlots}/{totalSlots} active
        </div>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 font-mono text-xs">
        <span className="text-text-muted">Tokens:</span>
        <span className="text-text-primary">{tokenCount.toLocaleString()}</span>
        <span className="text-text-muted">/ {contextLimit.toLocaleString()}</span>
      </div>
    </footer>
  );
}
```

#### S3.6. Verification

```powershell
cd src
bun run build
bun run lint
```

**STOP condition**: If build or lint fails, fix before proceeding.

---

### S4 — Zustand Stores (minimal schemas)

Per brief §7. One store per domain: agent, memory, tools, sessions.

#### S4.1. Create `src/stores/agentStore.ts`

```typescript
import { create } from "zustand";

type Phase = "idle" | "planning" | "acting" | "reflecting";

interface AgentState {
  sessionId: string;
  phase: Phase;
  modelSlug: string;
  latency: number;
  isRunning: boolean;
  tokenCount: number;
  contextLimit: number;
  setPhase: (phase: Phase) => void;
  setLatency: (ms: number) => void;
  setModel: (slug: string) => void;
  toggleRun: () => void;
  addTokens: (count: number) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  sessionId: "SES-8f2a",
  phase: "idle",
  modelSlug: "GLM-4.5 Flash",
  latency: 0,
  isRunning: false,
  tokenCount: 0,
  contextLimit: 128000,
  setPhase: (phase) => set({ phase }),
  setLatency: (latency) => set({ latency }),
  setModel: (modelSlug) => set({ modelSlug }),
  toggleRun: () => set((s) => ({ isRunning: !s.isRunning })),
  addTokens: (count) => set((s) => ({ tokenCount: s.tokenCount + count })),
}));
```

#### S4.2. Create `src/stores/memoryStore.ts`

```typescript
import { create } from "zustand";

interface MemorySlot {
  index: number;
  key: string;
  value: string;
  activation: number;
  lastWritten: number;
}

interface MemoryState {
  slots: Map<number, MemorySlot>;
  totalSlots: number;
  activeSlots: number;
  setActivation: (index: number, level: number) => void;
  getSlot: (index: number) => MemorySlot | undefined;
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  slots: new Map(),
  totalSlots: 512,
  activeSlots: 0,
  setActivation: (index, level) =>
    set((state) => {
      const slots = new Map(state.slots);
      const slot = slots.get(index);
      if (slot) {
        slots.set(index, { ...slot, activation: level });
      }
      const activeSlots = Array.from(slots.values()).filter((s) => s.activation > 0.1).length;
      return { slots, activeSlots };
    }),
  getSlot: (index) => get().slots.get(index),
}));
```

#### S4.3. Create `src/stores/toolStore.ts`

```typescript
import { create } from "zustand";

type ToolStatus = "running" | "success" | "warning" | "error";

interface ToolCall {
  id: string;
  tool: string;
  status: ToolStatus;
  args: Record<string, unknown>;
  output?: string;
  durationMs?: number;
  startedAt: number;
}

interface ToolState {
  calls: ToolCall[];
  addCall: (call: ToolCall) => void;
  patchCall: (id: string, patch: Partial<ToolCall>) => void;
  upsertCall: (call: ToolCall) => void;  // Rev5 H2 fix: atomic add-or-patch
  clearCalls: () => void;
}

const MAX_CALLS = 50;

export const useToolStore = create<ToolState>((set) => ({
  calls: [],
  addCall: (call) =>
    set((state) => {
      const calls = [call, ...state.calls].slice(0, MAX_CALLS);
      return { calls };
    }),
  patchCall: (id, patch) =>
    set((state) => ({
      calls: state.calls.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    })),
  // Rev5 H2 fix: atomic upsert — handles add-or-patch in a single set() call.
  // Avoids race condition where getState().find() + addCall/patchCall could
  // see stale state between two rapid SSE events.
  upsertCall: (call) =>
    set((state) => {
      const existing = state.calls.find((c) => c.id === call.id);
      if (existing) {
        return {
          calls: state.calls.map((c) =>
            c.id === call.id ? { ...c, ...call } : c
          ),
        };
      }
      return { calls: [call, ...state.calls].slice(0, MAX_CALLS) };
    }),
  clearCalls: () => set({ calls: [] }),
}));
```

#### S4.4. Create `src/stores/subagentStore.ts`

```typescript
import { create } from "zustand";

type SubagentStatus = "running" | "waiting" | "complete" | "failed";

interface Subagent {
  id: string;
  task: string;
  status: SubagentStatus;
  tokenCost: number;
}

interface SubagentState {
  subagents: Subagent[];
  setSubagents: (subs: Subagent[]) => void;
  killSubagent: (id: string) => void;
}

export const useSubagentStore = create<SubagentState>((set) => ({
  subagents: [],
  setSubagents: (subagents) => set({ subagents }),
  killSubagent: (id) =>
    set((state) => ({
      subagents: state.subagents.filter((s) => s.id !== id),
    })),
}));
```

#### S4.5. Verification

```powershell
cd src
bun run build
```

**STOP condition**: If build fails, fix before proceeding.

---

### S5 — useSSE Hook (generic, with reconnect)

Per brief §8 priority #3. Every streaming panel depends on this.

#### S5.1. Create `src/hooks/useSSE.ts`

```typescript
"use client";
import { useEffect, useRef, useState, useCallback } from "react";

interface UseSSEOptions {
  url: string;
  onMessage: (data: unknown) => void;
  enabled?: boolean;
  maxRetries?: number; // Rev3 H3 fix: stop reconnecting after N failures
}

const MAX_BACKOFF = 30_000;
const BASE_BACKOFF = 1_000;
const DEFAULT_MAX_RETRIES = 10; // Rev3 H3 fix: don't reconnect forever

export function useSSE({
  url,
  onMessage,
  enabled = true,
  maxRetries = DEFAULT_MAX_RETRIES,
}: UseSSEOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(BASE_BACKOFF);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);

  // Keep ref current without re-running effect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    // Rev3 H3 fix: stop reconnecting after maxRetries
    if (retryCountRef.current >= maxRetries) {
      setError(new Error(`SSE max retries (${maxRetries}) exceeded — stopping`));
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Rev3 C3 fix: withCredentials: true — required for cross-origin cookie auth
    const es = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
      backoffRef.current = BASE_BACKOFF;
      retryCountRef.current = 0; // Reset retry count on successful connection
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (e) {
        setError(e instanceof Error ? e : new Error("Failed to parse SSE data"));
      }
    };

    es.onerror = () => {
      setIsConnected(false);
      es.close();

      // Rev3 H3 fix: increment retry count, check against maxRetries
      retryCountRef.current += 1;
      if (retryCountRef.current >= maxRetries) {
        setError(new Error(`SSE max retries (${maxRetries}) exceeded — stopping`));
        return;
      }

      // Exponential backoff reconnect
      const delay = Math.min(backoffRef.current * 2, MAX_BACKOFF);
      backoffRef.current = delay;

      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(() => connect(), delay);
    };
  }, [url, maxRetries]);  // Rev5 H1 fix: added maxRetries (was just [url] — stale closure + ESLint failure)

  useEffect(() => {
    if (!enabled) return;

    connect();

    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [connect, enabled]);

  return { isConnected, error };
}
```

#### S5.2. Verification

```powershell
cd src
bun run build
```

**STOP condition**: If build fails, fix before proceeding.

---

### S6 — API Client (typed fetch/SSE wrappers)

#### S6.1. Create `src/lib/api.ts`

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface AgentStatus {
  sessionId: string;
  phase: "idle" | "planning" | "acting" | "reflecting";
  modelSlug: string;
  uptime: number;
}

export interface MemorySlot {
  index: number;
  key: string;
  value: string;
  activation: number;
  lastWritten: number;
}

export interface ToolCallEvent {
  id: string;
  tool: string;
  status: "running" | "success" | "warning" | "error";
  args: Record<string, unknown>;
  output?: string;
  durationMs?: number;
}

export interface TimelineSegment {
  phase: string;
  startMs: number;
  durationMs: number;
  confidence: number;
}

export interface Subagent {
  id: string;
  task: string;
  status: "running" | "waiting" | "complete" | "failed";
  tokenCost: number;
}

export async function getStatus(): Promise<AgentStatus> {
  const res = await fetch(`${API_BASE}/api/status`);
  if (!res.ok) throw new Error(`getStatus failed: ${res.status}`);
  return res.json();
}

export async function getMemorySlots(): Promise<MemorySlot[]> {
  const res = await fetch(`${API_BASE}/api/memory/slots`);
  if (!res.ok) throw new Error(`getMemorySlots failed: ${res.status}`);
  return res.json();
}

export async function getTimeline(sessionId: string): Promise<TimelineSegment[]> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/timeline`);
  if (!res.ok) throw new Error(`getTimeline failed: ${res.status}`);
  return res.json();
}

export async function getSubagents(): Promise<Subagent[]> {
  const res = await fetch(`${API_BASE}/api/subagents`);
  if (!res.ok) throw new Error(`getSubagents failed: ${res.status}`);
  return res.json();
}

export function sseUrl(path: string): string {
  return `${API_BASE}${path}`;
}
```

#### S6.2. Verification

```powershell
cd src
bun run build
```

---

### S7 — Backend Stubs (FastAPI, mocked data, all §5 endpoints)

**Applying AR6-equivalent**: `backend/` may import from `core/` only. This plan's `backend/` uses in-memory mocks — NO `core/` imports. Real orchestrator integration deferred to follow-on plan.

**Applying AR17**: Auth middleware wraps ALL routes except `/health`. This plan uses a minimal bearer token (hardcoded for dev). Full token generation (`~/.sovereign/token`) deferred.

**Applying AR18**: All `except Exception` blocks have inline comment + logging.

#### S7.1. Create `backend/main.py` (FastAPI app + all routes)

**Rev3 C8 fix**: Create `backend/__init__.py` (empty) so `from backend.main import app` works in pytest. Without it, Python 3 namespace package resolution may fail depending on pytest's sys.path.

**Rev3 Issue 2 fix**: Pydantic models added with field names comment-linked to `src/lib/api.ts` TypeScript interfaces.

**Rev3 Issue 4 fix**: `DEV_TOKEN` reads from env var — NO fallback (startup raises if unset).

**Rev3 C3 fix**: Cookie auth properly implemented — `/api/auth/login` sets httpOnly cookie, `/api/auth/token` removed.

First, create `backend/__init__.py` (empty file):
```powershell
New-Item -Path "backend\__init__.py" -ItemType File -Force
```

Then create `backend/main.py`:

```python
"""Sovereign AI UI Backend — FastAPI stubs with mocked data.

This module serves mocked data per the UI brief's §5 API contract.
Real orchestrator integration is deferred to a follow-on plan.

Applying AR6-equivalent: backend/ may import from core/ only (when real
integration lands; this plan uses in-memory mocks, no core/ imports).
Applying AR17: auth middleware wraps ALL routes except /health.
Applying AR18: all except Exception blocks have inline comment + logging.

Rev2 fixes:
- Issue 2: Pydantic models with field names comment-linked to src/lib/api.ts
- Issue 4: DEV_TOKEN reads from env var (no hardcoded credential in source)
- D5: Cookie-based auth for SSE (httpOnly, SameSite=Strict)
"""

import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="Sovereign AI UI Backend", version="0.1.0")

# Rev3 C4 fix: NO fallback. Env var is REQUIRED.
# Production deployment MUST set SOVEREIGN_DEV_TOKEN to a non-default value.
# Dev setup: export SOVEREIGN_DEV_TOKEN=dev-token
DEV_TOKEN = os.environ.get("SOVEREIGN_DEV_TOKEN")
if DEV_TOKEN is None:
    raise RuntimeError(
        "SOVEREIGN_DEV_TOKEN environment variable must be set. "
        "For dev: export SOVEREIGN_DEV_TOKEN=dev-token"
    )


# --- Pydantic models (Rev2 Issue 2 fix) ---
# Field names are comment-linked to src/lib/api.ts TypeScript interfaces.
# When renaming a field here, update the corresponding TS interface.


class AgentStatus(BaseModel):
    """Matches src/lib/api.ts AgentStatus interface."""
    sessionId: str
    phase: str  # "idle" | "planning" | "acting" | "reflecting"
    modelSlug: str
    uptime: int


class MemorySlot(BaseModel):
    """Matches src/lib/api.ts MemorySlot interface."""
    index: int
    key: str
    value: str
    activation: float
    lastWritten: int  # epoch ms


class ToolCallEvent(BaseModel):
    """Matches src/lib/api.ts ToolCallEvent interface."""
    id: str
    tool: str
    status: str  # "running" | "success" | "warning" | "error"
    args: dict[str, Any]
    output: str | None = None
    durationMs: int | None = None


class TimelineSegment(BaseModel):
    """Matches src/lib/api.ts TimelineSegment interface."""
    phase: str
    startMs: int
    durationMs: int
    confidence: float


class Subagent(BaseModel):
    """Matches src/lib/api.ts Subagent interface."""
    id: str
    task: str
    status: str  # "running" | "waiting" | "complete" | "failed"
    tokenCost: int


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """AR17: auth middleware wraps ALL routes except /health.

    Rev3 D5 fix: accepts EITHER bearer token (for REST) OR cookie (for SSE).
    SSE endpoints use cookie auth because EventSource API doesn't support
    custom headers. Cookie is set by the /api/auth/login endpoint below.
    """
    if request.url.path == "/health":
        return await call_next(request)

    # Check bearer token (REST requests from fetch with Authorization header)
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {DEV_TOKEN}":
        return await call_next(request)

    # Check cookie (SSE requests from EventSource, which can't set headers)
    if request.cookies.get("sovereign_token") == DEV_TOKEN:
        return await call_next(request)

    raise HTTPException(status_code=401, detail="Unauthorized")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,  # Rev3 D5 fix: required for cookie-based SSE auth
)


@app.post("/api/auth/login")
async def login(response: Response):
    """Set auth cookie for SSE requests.

    Rev3 C3 fix: Properly sets httpOnly + SameSite=Strict cookie on the response.
    The frontend calls this endpoint on page load with credentials: "include".
    SSE requests (EventSource) then automatically include the cookie.

    Rev2's implementation was broken in 4 ways (Reviews 4, 5, 6):
    - Returned JSON without setting cookie
    - Frontend set document.cookie client-side (not httpOnly, XSS-vulnerable)
    - EventSource created without withCredentials: true
    - /api/auth/token required auth (circular dependency)

    Rev3 fixes all 4: backend sets cookie, /api/auth/token removed, useSSE uses
    withCredentials, login() calls this endpoint with credentials: "include".

    Rev4 fix: samesite="lax" (was "strict"). SameSite=Strict withholds cookies
    on cross-origin requests — frontend (localhost:3000) → backend (localhost:8000)
    is cross-origin, so Strict caused 401 on SSE. Lax allows the cookie on
    cross-origin fetch/EventSource requests (the standard pattern for this
    scenario). secure=True + HTTPS deferred to production (dev is HTTP).

    Rev5 H3 fix: cookie domain and secure are now configurable via env vars.
    Production deploys with different subdomains (ui.sovereign.ai → api.sovereign.ai)
    need domain=".sovereign.ai" for the cookie to be sent cross-subdomain.
    """
    cookie_domain = os.environ.get("SOVEREIGN_COOKIE_DOMAIN")  # None = default (request domain)
    cookie_secure = os.environ.get("SOVEREIGN_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        key="sovereign_token",
        value=DEV_TOKEN,
        httponly=True,
        samesite="lax",  # Rev4: was "strict" — broke cross-origin SSE auth
        secure=cookie_secure,  # Rev5 H3: configurable for HTTPS production
        domain=cookie_domain,  # Rev5 H3: configurable for cross-subdomain production
        max_age=3600,
    )
    return {"status": "ok"}


# Rev3 C3 fix: /api/auth/token endpoint REMOVED.
# It was a security risk (returned the token as plain text) and created a
# circular dependency (required auth to get the token).
# Use /api/auth/login instead — it sets the cookie directly.

# --- In-memory mock state ---

SESSION_ID = f"SES-{uuid.uuid4().hex[:4]}"
START_TIME = time.time()
# Rev5 M1 fix: MOCK_PHASE cycles through phases on each request (was static "idle")
MOCK_PHASES = ["planning", "acting", "reflecting", "idle"]
_phase_index = 0
MOCK_MODEL = "GLM-4.5 Flash"


def _next_phase() -> str:
    """Cycle through mock phases for each /api/status request."""
    global _phase_index
    phase = MOCK_PHASES[_phase_index % len(MOCK_PHASES)]
    _phase_index += 1
    return phase


# --- REST endpoints ---


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — no auth required (AR17 exception)."""
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Agent phase, session ID, uptime, model slug."""
    return {
        "sessionId": SESSION_ID,
        "phase": _next_phase(),  # Rev5 M1: cycles through phases
        "uptime": int(time.time() - START_TIME),
        "modelSlug": MOCK_MODEL,
    }


@app.get("/api/memory/slots")
async def get_memory_slots() -> list[dict[str, Any]]:
    """All slots (mocked — 512 slots, random activation)."""
    return [
        {
            "index": i,
            "key": f"slot_{i}",
            "value": f"mock value {i}",
            "activation": random.random(),
            "lastWritten": int(time.time()) - random.randint(0, 3600),
        }
        for i in range(512)
    ]


@app.post("/api/memory/import")
async def import_memory(slots: list[dict[str, Any]]) -> dict[str, int]:
    """Bulk import slots from JSON (mocked — returns count)."""
    return {"imported": len(slots)}


@app.delete("/api/memory/slots/{slot_id}")
async def clear_slot(slot_id: int) -> dict[str, str]:
    """Clear one slot (mocked)."""
    return {"status": "cleared", "slot": str(slot_id)}


@app.get("/api/sessions")
async def get_sessions() -> list[dict[str, Any]]:
    """Session list with metadata (mocked)."""
    return [
        {
            "id": SESSION_ID,
            "startedAt": int(START_TIME),
            "phase": MOCK_PHASE,
            "toolCalls": 0,
        }
    ]


@app.get("/api/sessions/{session_id}/timeline")
async def get_timeline(session_id: str) -> list[dict[str, Any]]:
    """Phase segments for timeline (mocked)."""
    return [
        {
            "phase": "planning",
            "startMs": 0,
            "durationMs": 1500,
            "confidence": 0.85,
        },
        {
            "phase": "acting",
            "startMs": 1500,
            "durationMs": 3200,
            "confidence": 0.92,
        },
    ]


@app.get("/api/subagents")
async def get_subagents() -> list[dict[str, Any]]:
    """Active subagent list (mocked — empty)."""
    return []


@app.delete("/api/subagents/{subagent_id}")
async def kill_subagent(subagent_id: str) -> dict[str, str]:
    """Kill a subagent (mocked)."""
    return {"status": "killed", "subagent": subagent_id}


# --- SSE endpoints ---


async def sse_generator(event_factory):
    """Generate SSE events with data: <JSON>\\n\\n framing.

    Rev3 C1 fix: Use actual newline characters (\\n\\n in the f-string produces
    real newlines, not the literal string '\\n\\n'). The Rev2 version had
    double-escaped backslashes (\\\\n\\\\n) which produced literal backslash-n
    characters — EventSource never detected event boundaries.
    """
    try:
        async for event in event_factory():
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        # Rev5 M2 fix: re-raise CancelledError — don't catch it in the generic
        # except below. Client disconnect triggers CancelledError; catching it
        # as a generic Exception prevents proper task cleanup (memory leak).
        raise
    except Exception as e:
        # AR18: SSE stream failure — log and close
        logger.warning("SSE stream failed: %s", e)


@app.get("/api/agent/reasoning")
async def reasoning_stream() -> StreamingResponse:
    """Streaming reasoning tokens (mocked)."""
    async def factory():
        tokens = ["Planning", " step", " 1", ":", " analyze", " input", "..."]
        while True:
            for token in tokens:
                yield {"token": token, "timestamp": int(time.time() * 1000)}

    return StreamingResponse(
        sse_generator(factory),
        media_type="text/event-stream",
    )


@app.get("/api/tools/stream")
async def tools_stream() -> StreamingResponse:
    """Tool call events (mocked)."""
    async def factory():
        while True:
            yield {
                "id": str(uuid.uuid4()),
                "tool": random.choice(["web_search", "memory_write", "code_exec"]),
                "status": "running",
                "args": {"query": "mock query"},
            }
            await asyncio.sleep(2)

    return StreamingResponse(
        sse_generator(factory),
        media_type="text/event-stream",
    )


@app.get("/api/memory/activations")
async def activations_stream() -> StreamingResponse:
    """Memory slot activation deltas (mocked)."""
    async def factory():
        while True:
            yield {
                "index": random.randint(0, 511),
                "activation": random.random(),
                "timestamp": int(time.time() * 1000),
            }

    return StreamingResponse(
        sse_generator(factory),
        media_type="text/event-stream",
    )


# --- WebSocket (PTY — deferred, stub only) ---


@app.websocket("/api/pty")
async def pty_websocket(websocket: WebSocket):
    """Bidirectional PTY stream for xterm.js (DEFERRED — stub only).

    This endpoint exists to satisfy the §5 API contract but does NOT
    implement actual PTY functionality. xterm.js integration is deferred
    to a follow-on plan.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # AR18: stub — echo back, no actual PTY
            await websocket.send_text(f"[PTY stub] received: {data}")
    except WebSocketDisconnect:
        # AR18: client disconnect — log and close
        logger.info("PTY WebSocket disconnected")
    except Exception as e:
        # AR18: unexpected error — log and close
        logger.warning("PTY WebSocket error: %s", e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### S7.2. Create `backend/requirements.txt`

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
```

#### S7.3. Verification

```powershell
cd backend
python -c "import ast; ast.parse(open('main.py').read())"
ruff check main.py
mypy main.py --ignore-missing-imports
# Start backend and smoke-test
python -m uvicorn main:app --port 8000 &
# Test /health (no auth)
curl http://localhost:8000/health
# Test /api/status (with auth)
curl -H "Authorization: Bearer dev-token-sovereign-ai-ui" http://localhost:8000/api/status
# Kill backend
kill %1
```

**STOP condition**: If syntax/ruff/mypy fails, or endpoints don't respond, fix before proceeding.

---

### S8 — Wiring (shell connects to backend, renders live mocked data)

#### S8.1. Create `src/app/page.tsx` (default route → terminal pane placeholder + wiring)

**Rev3 D5 fix**: SSE is now ENABLED. Cookie-based auth (set via `/api/auth/login` on page load) allows EventSource to authenticate without custom headers. The `useSSE` hook is exercised end-to-end by the Tool Inspector panel (S8a).

```tsx
"use client";
import { useEffect } from "react";
import { useAgentStore } from "@/stores/agentStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useSSE } from "@/hooks/useSSE";
import { getStatus, sseUrl, login } from "@/lib/api";

export default function Home() {
  const setPhase = useAgentStore((s) => s.setPhase);
  const setLatency = useAgentStore((s) => s.setLatency);
  const setActivation = useMemoryStore((s) => s.setActivation);

  // Rev3 D5 fix: login on page load to set auth cookie for SSE
  // Rev5 C3 fix: chain login().then(() => poll()) so first poll has the cookie
  // Rev5 M4 fix: log warning on login failure (was silently swallowed)
  // Rev6 fix: use cancelled flag + synchronous cleanup registration.
  //   Rev5's pattern returned cleanup from inside .then() — React ignores
  //   Promises returned from useEffect, so cleanup never ran → interval leak.
  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | undefined;
    let cancelled = false;

    login()
      .then(() => {
        if (cancelled) return; // Guard: unmounted during login()
        const poll = async () => {
          try {
            const start = performance.now();
            const status = await getStatus();
            const elapsed = performance.now() - start;
            setPhase(status.phase);
            setLatency(Math.round(elapsed));
          } catch {
            // AR18-equivalent: poll failure — silent
          }
        };
        poll();
        intervalId = setInterval(poll, 2000);
      })
      .catch(() => {
        console.warn("Backend auth failed at", API_BASE, "— SSE will not work");
      });

    // Rev6: cleanup registered SYNCHRONOUSLY from effect's return value.
    // React only calls functions returned synchronously from useEffect.
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [setPhase, setLatency]);

  // SSE: memory activations (now ENABLED — Rev3 D5 fix)
  useSSE({
    url: sseUrl("/api/memory/activations"),
    onMessage: (data) => {
      const event = data as { index: number; activation: number };
      setActivation(event.index, event.activation);
    },
  });

  return null; // Layout is in root layout.tsx; Tool Inspector in S8a uses its own SSE
}
```

#### S8.2. Verification — end-to-end

```powershell
# Terminal 1: Start backend
cd backend
python -m uvicorn main:app --port 8000

# Terminal 2: Start frontend
cd src
bun run dev

# Open http://localhost:3000 — verify:
# - Status bar shows "SES-XXXX", phase badge, model slug, latency counter
# - Sidebar shows 6 icons, expands on hover
# - Right panel shows 3 tabs with placeholder text
# - Bottom bar shows activation grid placeholder + token counter
# - Status bar latency updates every 2 seconds (polling /api/status)
# - Rev2 S8a: Tool Inspector tab shows live tool call events from SSE
```

**STOP condition**: If shell doesn't render, latency doesn't update, or tool inspector doesn't show live events, fix before proceeding.

---

### S8a — Tool Inspector Panel (full implementation with real SSE)

**Rev2 D4+D5 fix (decisive)**: Claude's Tier 2 review identified that building `useSSE` then immediately disabling it creates a false completion signal — the riskiest part of the stack ships unverified. This section implements ONE full panel (Tool Inspector) with real SSE to retire that risk. The Tool Inspector is the best candidate because: (a) simplest data shape (no Canvas/SVG rendering complexity), (b) highest information density, (c) directly exercises the `useSSE` hook + `toolStore` + cookie auth end-to-end.

**Scope of this section**: Tool Inspector panel only. Other panels (Activation Grid, Timeline, Reasoning) remain placeholders — deferred to follow-on plans now that SSE risk is retired.

#### S8a.1. Create `src/components/panels/ToolInspector.tsx`

Per brief §3.3. Expandable cards, status indicators, duration chips, SSE-driven.

```tsx
"use client";
import { useState } from "react";
import { useToolStore } from "@/stores/toolStore";
import { useSSE } from "@/hooks/useSSE";
import { sseUrl } from "@/lib/api";
import { ChevronDown, ChevronRight } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-accent-violet animate-pulse",
  success: "bg-accent-emerald",
  warning: "bg-accent-amber",
  error: "bg-accent-red",
};

const LATENCY_COLORS: Record<string, string> = {
  fast: "bg-accent-emerald",    // < 200ms
  medium: "bg-accent-amber",    // 200-500ms
  slow: "bg-accent-red",        // > 500ms
};

function getLatencyClass(ms: number | undefined): string {
  if (ms === undefined) return LATENCY_COLORS.fast;
  if (ms < 200) return LATENCY_COLORS.fast;
  if (ms < 500) return LATENCY_COLORS.medium;
  return LATENCY_COLORS.slow;
}

function ToolCallCard({
  call,
}: {
  call: import("@/stores/toolStore").ToolCall;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="border-b border-border bg-surface-raised transition-colors hover:bg-surface-overlay"
      role="button"
      tabIndex={0}
      onClick={() => setExpanded(!expanded)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") setExpanded(!expanded);
      }}
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <span
          className={`h-2 w-2 rounded-full ${STATUS_COLORS[call.status] ?? STATUS_COLORS.running}`}
          aria-label={`Status: ${call.status}`}
        />
        <span className="font-mono text-xs text-text-primary">{call.tool}</span>
        <div className="flex-1" />
        {call.durationMs !== undefined && (
          <span className="font-mono text-xs text-text-muted">{call.durationMs}ms</span>
        )}
        {expanded ? (
          <ChevronDown size={14} className="text-text-muted" />
        ) : (
          <ChevronRight size={14} className="text-text-muted" />
        )}
      </div>
      {expanded && (
        <div className="border-t border-border px-3 py-2">
          {/* Arguments grid */}
          <div className="mb-2">
            <div className="mb-1 text-xs text-text-muted">Arguments</div>
            <div className="grid grid-cols-2 gap-1">
              {Object.entries(call.args).map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <span className="text-xs text-text-muted">{key}:</span>
                  <code className="rounded bg-surface-base px-1 font-mono text-xs text-text-primary">
                    {JSON.stringify(value)}
                  </code>
                </div>
              ))}
            </div>
          </div>
          {/* Output block */}
          {call.output && (
            <div className="mb-2">
              <div className="mb-1 text-xs text-text-muted">Output</div>
              <pre className="max-h-40 overflow-y-auto rounded bg-surface-base p-2 font-mono text-xs text-text-primary">
                {call.output}
              </pre>
            </div>
          )}
          {/* Latency bar */}
          {call.durationMs !== undefined && (
            <div>
              <div className="mb-1 text-xs text-text-muted">Latency</div>
              <div className="h-1 w-full overflow-hidden rounded bg-surface-base">
                <div
                  className={`h-full ${getLatencyClass(call.durationMs)}`}
                  style={{ width: `${Math.min(100, (call.durationMs / 1000) * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolInspector() {
  const calls = useToolStore((s) => s.calls);
  const upsertCall = useToolStore((s) => s.upsertCall);  // Rev5 H2 fix

  // SSE: tool call events (real — Rev3 D4+D5 fix, Rev5 H2 race fix)
  useSSE({
    url: sseUrl("/api/tools/stream"),
    onMessage: (data) => {
      const event = data as import("@/lib/api").ToolCallEvent;
      // Rev5 H2 fix: use upsertCall (atomic add-or-patch) instead of
      // getState().find() + addCall/patchCall (race condition when two
      // events arrive in rapid succession and second reads stale state).
      upsertCall({
        id: event.id,
        tool: event.tool,
        status: event.status,
        args: event.args,
        output: event.output,
        durationMs: event.durationMs,
        startedAt: Date.now(),
      });
    },
  });

  return (
    <div
      className="flex h-full flex-col"
      aria-live="polite"
      aria-label="Tool call inspector — live updates"
    >
      <div className="border-b border-border px-3 py-2 text-xs text-text-muted">
        {calls.length} call{calls.length !== 1 ? "s" : ""} (max 50 retained)
      </div>
      <div className="flex-1 overflow-y-auto">
        {calls.length === 0 ? (
          <div className="p-4 font-mono text-xs text-text-muted">
            Waiting for tool call events...
          </div>
        ) : (
          calls.map((call) => <ToolCallCard key={call.id} call={call} />)
        )}
      </div>
    </div>
  );
}
```

#### S8a.2. Update `src/components/shell/RightPanel.tsx` to render ToolInspector in the tools tab

Replace the placeholder text for the "tools" tab with the real `ToolInspector` component:

```tsx
"use client";
import { useState } from "react";
import { Wrench, Clock, Brain } from "lucide-react";
import { ToolInspector } from "@/components/panels/ToolInspector";

const TABS = [
  { id: "tools", label: "Tool inspector", icon: Wrench },
  { id: "timeline", label: "Timeline", icon: Clock },
  { id: "reasoning", label: "Reasoning", icon: Brain },
] as const;

type TabId = typeof TABS[number]["id"];

export function RightPanel() {
  const [activeTab, setActiveTab] = useState<TabId>("tools");

  return (
    <aside className="flex flex-col border-l border-border bg-surface-raised">
      <div className="flex border-b border-border">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              activeTab === id
                ? "border-b-2 border-accent-amber text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === "tools" && <ToolInspector />}
        {activeTab === "timeline" && (
          <div className="p-4 font-mono text-xs text-text-muted">
            Session timeline — placeholder. Full implementation deferred to follow-on plan.
          </div>
        )}
        {activeTab === "reasoning" && (
          <div className="p-4 font-mono text-xs text-text-muted">
            Reasoning stream — placeholder. Full implementation deferred to follow-on plan.
          </div>
        )}
      </div>
    </aside>
  );
}
```

#### S8a.3. Update `src/lib/api.ts` to add `login()` function

Add to `src/lib/api.ts`:

```typescript
export async function login(): Promise<void> {
  // Rev3 C3 fix: call /api/auth/login with credentials: "include".
  // The backend sets an httpOnly + SameSite=Strict cookie on the response.
  // SSE requests (EventSource with withCredentials: true) then include it.
  // Rev2's implementation was broken — it fetched /api/auth/token and set
  // document.cookie client-side (not httpOnly, XSS-vulnerable).
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    credentials: "include", // Required: sends/receives cookies cross-origin
  });
  if (!res.ok) throw new Error(`login failed: ${res.status}`);
}
```

#### S8a.4. Verification — SSE end-to-end (Rev4: strengthened cookie inspection)

**Rev4 fix**: S8a.4 now explicitly inspects `Set-Cookie` and `Cookie` headers in DevTools, not just "not 401." The "not 401" check could pass in some browser/flag combinations while the cookie is silently blocked — this is exactly the gap that allowed the SameSite=Strict bug (Rev3) to ship. The strengthened verification catches cookie attachment failures directly.

```powershell
# Terminal 1: Start backend (set SOVEREIGN_DEV_TOKEN first — Rev3 C4 fix)
$env:SOVEREIGN_DEV_TOKEN="dev-token"
cd backend
python -m uvicorn main:app --port 8000

# Terminal 2: Start frontend
cd src
bun run dev

# Open http://localhost:3000 — verify ALL of the following:

# === STEP 1: Login endpoint sets cookie correctly ===
# Open DevTools → Network tab
# Refresh page — find the POST /api/auth/login request
# Click it → Response Headers → verify:
#   Set-Cookie: sovereign_token=<value>; HttpOnly; Path=/; SameSite=Lax; Max-Age=3600
# If Set-Cookie is missing or SameSite=Strict, STOP — cookie auth is broken.

# === STEP 2: SSE request includes the cookie ===
# In DevTools Network tab, filter by "EventSource" or "fetch"
# Find the GET /api/memory/activations request (SSE)
# Click it → Request Headers → verify:
#   Cookie: sovereign_token=<value>
# If Cookie header is missing, STOP — cookie not being sent (check SameSite, withCredentials, CORS).

# === STEP 3: SSE returns 200, not 401 ===
# Same request → Status should be 200 (not 401)
# If 401, STOP — auth middleware not accepting the cookie.

# === STEP 4: Tool Inspector shows live events ===
# Click "Tool inspector" tab in right panel
# Tool call events appear every ~2 seconds (mocked SSE stream)
# Each event shows: status dot (pulsing violet for "running"), tool name, expand/collapse
# Click a card to expand — shows arguments grid, output block (if any), latency bar
# After ~50 events, older events are evicted from the bottom (max 50 retained)

# === STEP 5: Reconnect works ===
# Stop backend → verify SSE reconnects with exponential backoff (check console for reconnect logs)
# After maxRetries (10), verify error state is set (not infinite reconnect loop)
# Restart backend → verify SSE reconnects and events resume
```

**STOP condition**: If ANY of the 5 steps fail (cookie not set, cookie not sent, 401, no events, infinite reconnect), fix before proceeding. This is the critical verification — it retires the SSE risk that Rev1 left unvalidated and catches the cookie-auth gaps that Rev2/Rev3 missed.

---

### S9 — Tests

#### S9.1. Frontend tests (Vitest + React Testing Library)

Create `src/vitest.config.ts`:
```typescript
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
```

Create `src/__tests__/shell.test.tsx`:
```typescript
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusBar } from "@/components/shell/StatusBar";
import { Sidebar } from "@/components/shell/Sidebar";
import { RightPanel } from "@/components/shell/RightPanel";
import { BottomBar } from "@/components/shell/BottomBar";

describe("StatusBar", () => {
  it("renders session ID", () => {
    render(<StatusBar />);
    expect(screen.getByText(/SES-/)).toBeInTheDocument();
  });

  it("renders phase badge", () => {
    render(<StatusBar />);
    expect(screen.getByText(/Sovereign ·/)).toBeInTheDocument();
  });

  it("renders model slug", () => {
    render(<StatusBar />);
    expect(screen.getByText("GLM-4.5 Flash")).toBeInTheDocument();
  });
});

describe("Sidebar", () => {
  it("renders all 6 nav icons", () => {
    render(<Sidebar />);
    expect(screen.getAllByRole("button")).toHaveLength(6);
  });

  it("expands on hover", () => {
    render(<Sidebar />);
    const nav = screen.getByRole("navigation");
    fireEvent.mouseEnter(nav);
    // Verify "Sovereign" wordmark appears when expanded
    expect(screen.getByText("Sovereign")).toBeInTheDocument();
  });
});

describe("RightPanel", () => {
  it("renders 3 tabs", () => {
    render(<RightPanel />);
    expect(screen.getByText("Tool inspector")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Reasoning")).toBeInTheDocument();
  });

  it("switches tabs on click", () => {
    render(<RightPanel />);
    fireEvent.click(screen.getByText("Timeline"));
    expect(screen.getByText(/Session timeline — placeholder/)).toBeInTheDocument();
  });
});

describe("BottomBar", () => {
  it("renders activation grid placeholder", () => {
    render(<BottomBar />);
    expect(screen.getByText(/Activation grid placeholder/)).toBeInTheDocument();
  });

  it("renders token counter", () => {
    render(<BottomBar />);
    expect(screen.getByText(/Tokens:/)).toBeInTheDocument();
  });
});
```

Create `src/__tests__/stores.test.ts`:
```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { useAgentStore } from "@/stores/agentStore";
import { useToolStore } from "@/stores/toolStore";
import { useMemoryStore } from "@/stores/memoryStore";

describe("agentStore", () => {
  beforeEach(() => {
    useAgentStore.setState({ phase: "idle", isRunning: false });
  });

  it("toggles run state", () => {
    expect(useAgentStore.getState().isRunning).toBe(false);
    useAgentStore.getState().toggleRun();
    expect(useAgentStore.getState().isRunning).toBe(true);
  });

  it("sets phase", () => {
    useAgentStore.getState().setPhase("acting");
    expect(useAgentStore.getState().phase).toBe("acting");
  });
});

describe("toolStore", () => {
  it("adds and caps at 50 calls", () => {
    const { addCall } = useToolStore.getState();
    for (let i = 0; i < 55; i++) {
      addCall({
        id: `call-${i}`,
        tool: "test",
        status: "success",
        args: {},
        startedAt: Date.now(),
      });
    }
    expect(useToolStore.getState().calls.length).toBe(50);
  });

  it("patches calls by id", () => {
    const { addCall, patchCall } = useToolStore.getState();
    addCall({ id: "test-1", tool: "test", status: "running", args: {}, startedAt: Date.now() });
    patchCall("test-1", { status: "success", durationMs: 100 });
    expect(useToolStore.getState().calls[0].status).toBe("success");
    expect(useToolStore.getState().calls[0].durationMs).toBe(100);
  });
});

describe("memoryStore", () => {
  it("sets activation and counts active slots", () => {
    const { setActivation } = useMemoryStore.getState();
    setActivation(0, 0.8);
    setActivation(1, 0.6);
    expect(useMemoryStore.getState().activeSlots).toBe(2);
  });
});
```

#### S9.2. Backend tests (pytest)

Create `tests/test_ui_backend.py`:

**Rev5 C2 fix**: `conftest.py` (below) sets `SOVEREIGN_DEV_TOKEN` before importing backend. Tests read `DEV_TOKEN` from the module to avoid token mismatch.

First, create `tests/conftest.py`:
```python
"""Pytest configuration — sets SOVEREIGN_DEV_TOKEN before backend import.

Rev5 C2 fix: backend/main.py requires SOVEREIGN_DEV_TOKEN env var (no fallback).
Tests need the token to authenticate. This conftest sets it before any test
module imports backend.main, ensuring the backend starts successfully.
"""
import os

os.environ.setdefault("SOVEREIGN_DEV_TOKEN", "dev-token-sovereign-ai-ui")
```

Then create `tests/test_ui_backend.py`:
```python
"""Tests for Sovereign AI UI backend stubs (Plan 80).

Tests verify the §5 API contract — endpoint shape and mocked response structure.
Real orchestrator integration is deferred to a follow-on plan.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import DEV_TOKEN, app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {DEV_TOKEN}"}


class TestHealthAndAuth:
    def test_health_no_auth_required(self):
        """AR17: /health is the only unauthenticated endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_api_requires_auth(self):
        """AR17: all /api/* endpoints require bearer token."""
        response = client.get("/api/status")
        assert response.status_code == 401

    def test_api_with_auth(self):
        response = client.get("/api/status", headers=AUTH_HEADERS)
        assert response.status_code == 200


class TestStatusEndpoint:
    def test_status_returns_required_fields(self):
        response = client.get("/api/status", headers=AUTH_HEADERS)
        data = response.json()
        assert "sessionId" in data
        assert "phase" in data
        assert "uptime" in data
        assert "modelSlug" in data
        assert data["sessionId"].startswith("SES-")

    def test_status_phase_is_valid(self):
        response = client.get("/api/status", headers=AUTH_HEADERS)
        data = response.json()
        assert data["phase"] in ("idle", "planning", "acting", "reflecting")


class TestMemoryEndpoints:
    def test_get_slots_returns_512(self):
        response = client.get("/api/memory/slots", headers=AUTH_HEADERS)
        data = response.json()
        assert len(data) == 512
        assert "index" in data[0]
        assert "activation" in data[0]

    def test_clear_slot(self):
        response = client.delete("/api/memory/slots/0", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"

    def test_import_memory(self):
        response = client.post(
            "/api/memory/import",
            headers=AUTH_HEADERS,
            json=[{"index": 0, "key": "test", "value": "val", "activation": 0.5}],
        )
        assert response.status_code == 200
        assert response.json()["imported"] == 1


class TestSessionEndpoints:
    def test_get_sessions(self):
        response = client.get("/api/sessions", headers=AUTH_HEADERS)
        data = response.json()
        assert len(data) >= 1
        assert "id" in data[0]

    def test_get_timeline(self):
        response = client.get(f"/api/sessions/SES-test/timeline", headers=AUTH_HEADERS)
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "phase" in data[0]
            assert "durationMs" in data[0]


class TestSubagentEndpoints:
    def test_get_subagents(self):
        response = client.get("/api/subagents", headers=AUTH_HEADERS)
        data = response.json()
        assert isinstance(data, list)

    def test_kill_subagent(self):
        response = client.delete("/api/subagents/SA-test", headers=AUTH_HEADERS)
        assert response.status_code == 200
```

#### S9.3. Run tests

```powershell
# Frontend (Vitest)
cd src
bun add -D vitest @testing-library/react @testing-library/jest-dom jsdom
bun run vitest run

# Backend (pytest) — from repo root
cd C:\Jarvis
python -m pytest tests/test_ui_backend.py -q --tb=short
```

**STOP condition**: If any test fails, fix before proceeding.

---

### S10 — DECISIONS.md + README.md

#### S10.1. Create `DECISIONS.md`

```markdown
# DECISIONS.md — Sovereign AI UI

Log of library additions and architectural decisions beyond the brief's §2 stack.

## Plan 80 (UI Shell)

### D1: Same repo (Python + TypeScript)
**Decision**: Next.js frontend lives in `src/`, FastAPI stubs in `backend/`, same repo as existing Python code.
**Rationale**: Follows brief §7 file structure. Simpler CI (one repo). Single git history. Trade-off: mixed-language repo, two test suites (pytest + Vitest).
**Alternative considered**: Separate `sovereign-ai-ui` repo. Rejected for cross-repo coordination overhead.

### D2: New `backend/` directory (not extending `web/`)
**Decision**: New `backend/main.py` separate from existing `web/server.py`.
**Rationale**: `web/` is the agent control API (tasks, workers, trace); `backend/` is the UI data API (status, reasoning, tools, memory). Different purposes. Keeping separate avoids disrupting the working `web/` server. May merge in future.
**Alternative considered**: Add new routes to `web/server.py`. Rejected — different API contracts, risk of disrupting working server.
**Rev2 merge trigger** (Claude Tier 2 review): Re-evaluate merge when `backend/` lands real `core/orchestrator.py` integration. At that point, `web/` routes that duplicate `backend/` concepts (session, phase, tasks) should proxy to `backend/` rather than maintain separate implementations. Without this trigger, the default outcome is two services drifting further apart until merging becomes a multi-plan migration.

### D3: Prisma/SQLite deferred
**Decision**: Backend uses in-memory mocks. Prisma schema not created in this plan.
**Rationale**: Prisma setup (schema, migrations, client generation) is a separate concern. Mocked data is sufficient for end-to-end rendering. Real persistence deferred to follow-on plan.
**Alternative considered**: Include Prisma in this plan. Rejected — scope creep, this plan is already large.

### D4: Panel implementations — Tool Inspector included, others deferred
**Decision**: Shell + Tool Inspector panel (full, with real SSE) + placeholder panels for Timeline/Reasoning/Activation Grid.
**Rationale**: Claude Tier 2 review identified that Rev1's "placeholders only" approach left the riskiest piece (useSSE) unverified. Including one full SSE-backed panel (Tool Inspector — simplest data shape, highest information density) retires the SSE risk. Other panels remain placeholders — they can be delivered incrementally now that SSE is proven.
**Alternative considered**: Rev1's "placeholders only." Rejected — false completion signal for SSE.

### D5: SSE auth via cookie (httpOnly, SameSite=Strict)
**Decision**: Cookie-based auth for SSE. `useSSE` is ENABLED. Frontend calls `/api/auth/login` on page load to set cookie; SSE requests (EventSource) automatically include the cookie.
**Rationale**: Claude Tier 2 review recommended cookie auth over query-param (which leaks in server logs, browser history, Referer headers). Cookie + httpOnly + SameSite=Strict is the secure pattern. EventSource API doesn't support custom headers — cookie is the correct workaround.
**Alternative considered**: Query-param auth (`?token=...`). Rejected — security risk. Bearer-token-only auth. Rejected — EventSource can't set headers, SSE would be unauthenticated.

### D6: Bun (with native-module risk note)
**Decision**: Bun for runtime and package manager.
**Rationale**: Follows brief §2. Bun is faster than Node for dev startup. Trade-off: smaller ecosystem.
**Alternative considered**: Node + npm. Rejected — brief specifies Bun.
**Rev2 native-module risk note** (Claude Tier 2 review): Bun compatibility is unverified for deferred dependencies (xterm.js native bindings, `@xterm/addon-webgl`). When follow-on plans pull these in, verify `bun add` succeeds before committing to Bun for those plans. If a deferred dependency has Bun incompatibility, that plan may need to switch the runtime — flag in that plan's DECISIONS.md.
```

#### S10.2. Create `README.md` (update existing or create new section)

```markdown
## Sovereign AI UI (Plan 80)

Next.js 15 + FastAPI shell with placeholder panels and mocked data.

### Setup

#### Backend (FastAPI stubs)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

#### Frontend (Next.js)
```bash
cd src
bun install
bun run dev
```

Open http://localhost:3000

### Auth
Dev token: `dev-token-sovereign-ai-ui` (hardcoded for development).
Full token generation (`~/.sovereign/token`) deferred to follow-on plan.

### What's implemented
- Shell layout (status bar, sidebar, right panel tabs, bottom bar)
- FastAPI backend stubs (all §5 endpoints, mocked data)
- Zustand stores (agent, memory, tools, subagent — minimal schemas)
- useSSE hook (generic, with reconnect — SSE auth deferred)
- Wiring (status bar polls /api/status, latency updates live)

### What's deferred (out of scope for Plan 80)
- xterm.js/PTY terminal (§3 main pane, §5 /api/pty WS)
- Memory drawer (§3.6)
- Subagent panel (§3.7)
- Full panel implementations (activation grid, tool inspector, timeline, reasoning)
- Prisma/SQLite persistence
- Real orchestrator integration (backend → core/orchestrator.py)
- SSE auth (query param or cookie-based)
- Model picker modal
- Settings drawer
```

#### S10.3. Verification

```powershell
# Verify both files exist and are well-formed
cat DECISIONS.md | head -5
cat README.md | head -5
```

---

## Closing

Run `/jarvis-close` per workflow file `.windsurf/workflows/jarvis-close.md`.

**Applying OR39**: Ensure `Prompts/plan-80*.md` is added in the C12 docs commit:
```powershell
git add CHANGELOG.md PLANS.md LANDMINES.md "Prompts/plan-80*.md"
```

**Applying OR38**: Plan 80 is in the 80s decade. **Decade boundary triggered!** Per OR38, at decade boundary tags (prompt-80), delete the previous decade's plan files from `Prompts/`. Delete files matching `plan-70*` through `plan-79*` (the 70s decade). Commit the deletions as part of the C12 docs commit. Do NOT delete governance directives, governance patches, or the current decade's files.

### Expected results

- **pytest**: 1405 + ~12 new tests = ~1417 passed, 67 skipped (delta +12, exceeds OR17 ±5 tolerance. OR17 invoked. Justification: all 12 tests are in-scope new tests for backend stubs + Pydantic model validation (test_ui_backend.py). No existing tests modified.)
- **Vitest**: NEW baseline — ~10 tests (3 StatusBar + 2 Sidebar + 2 RightPanel + 2 BottomBar + 1 store consolidation). First Vitest baseline.
- **Ruff**: 0 errors (backend/main.py clean)
- **Mypy**: 0 errors (backend/main.py file-scoped)
- **TypeScript**: strict compile pass (src/)
- **ESLint**: 0 errors (src/)
- **New directories**: `src/` (Next.js), `backend/` (FastAPI stubs)
- **New test suite**: Vitest (frontend) alongside pytest (backend)

### Landmine capture (C11)

**L24 candidate** (mixed-language repo): If Devin encounters friction with Python/TypeScript coexistence (e.g., pre-commit hooks, CI config, editor config conflicts), capture as L24: "Mixed Python/TypeScript repo requires separate tooling configs (ruff/mypy for Python, ESLint/tsc for TypeScript) — pre-commit hooks and CI must run both, doubling scan time."

**L25 candidate** (SSE auth gap): If the follow-on plan discovers the SSE auth gap (D5) blocks panel implementations, capture as L25: "EventSource API doesn't support custom headers — SSE auth requires query param (security risk) or cookie-based auth. Plan 80 deferred this, creating a known gap that follow-on plans must address before SSE-driven panels can function."

If any new failure pattern is discovered during execution, capture it in `LANDMINES.md` per GR11.

---

## Scope Declaration

**Applying OR15 (pre-declare scope) and GR12 (GLM pre-declares scope before drafting)**:

### WILL edit (exhaustive list)

| File | Change |
|---|---|
| `src/` (NEW directory) | Next.js 15 project — App Router, TypeScript, Tailwind v4, shadcn/ui, Zustand, Framer Motion, Lucide React |
| `src/app/globals.css` | Color tokens + typography per brief §6 |
| `src/app/layout.tsx` | Shell grid (StatusBar + Sidebar + main + RightPanel + BottomBar) |
| `src/app/page.tsx` | Default route — wiring (poll /api/status, SSE hooks) |
| `src/components/shell/StatusBar.tsx` | Status bar per brief §3.1 |
| `src/components/shell/Sidebar.tsx` | Sidebar per brief §4 (64px, expands to 200px on hover) |
| `src/components/shell/RightPanel.tsx` | Right panel with 3 tabs (placeholder content) |
| `src/components/shell/BottomBar.tsx` | Bottom bar (activation grid placeholder + token counter) |
| `src/stores/agentStore.ts` | Zustand store — agent state (minimal schema) |
| `src/stores/memoryStore.ts` | Zustand store — memory slots (minimal schema) |
| `src/stores/toolStore.ts` | Zustand store — tool calls (max 50, minimal schema) |
| `src/stores/subagentStore.ts` | Zustand store — subagents (minimal schema) |
| `src/hooks/useSSE.ts` | Generic SSE hook with exponential backoff reconnect |
| `src/lib/api.ts` | Typed fetch/SSE wrappers |
| `src/lib/utils.ts` | shadcn/ui `cn()` helper (auto-generated by `shadcn init`) |
| `src/__tests__/shell.test.tsx` | Vitest tests for shell components |
| `src/__tests__/stores.test.ts` | Vitest tests for Zustand stores |
| `src/vitest.config.ts` | Vitest configuration |
| `src/.eslintrc.json` | ESLint config (strict, no `any`) |
| `src/.prettierrc` | Prettier config |
| `src/tsconfig.json` | TypeScript strict config (verify Next.js default) |
| `src/bunfig.toml` | Bun config |
| `src/package.json` | Dependencies (auto-generated by `bun create next-app` + `bun add`) |
| `backend/main.py` (NEW) | FastAPI app + all §5 endpoints (mocked data) |
| `backend/requirements.txt` (NEW) | FastAPI + uvicorn |
| `tests/test_ui_backend.py` (NEW) | pytest tests for backend endpoints (~10 tests) |
| `DECISIONS.md` (NEW) | Log of library additions and architectural decisions |
| `README.md` | Update with UI setup instructions |
| `PLANS.md` | Update queue (scan deferred to Plan 81); update at closing (C12) |
| `CHANGELOG.md` | Append entry at closing (C12) |
| `LANDMINES.md` | Append entry at closing IF new pattern discovered (C11) |

### WILL NOT edit

- `AGENTS.md` (no new AR/OR rules — S0.3 says "No new AGENTS.md rules this prompt")
- `AI_HANDOFF.md` (no new GR rules)
- `CONTEXT.md` (UI vocabulary deferred — no domain terms to add yet)
- `core/` (NO changes — backend uses mocks, no core/ integration)
- `cli/` (NO changes)
- `web/` (NO changes — existing FastAPI server untouched; new `backend/` is separate)
- `adapters/`, `memory/`, `system/`, `skills/`, `workers/` (NO changes)
- `prisma/` (deferred — no Prisma schema in this plan)
- `scripts/` (NO changes)

### Explicitly deferred (out of scope, NOT abandoned)

Per user instruction and brief §8 priority order:

1. **xterm.js/PTY terminal** (brief §3 main pane, §5 /api/pty WS) — deferred to follow-on plan. `backend/main.py` includes a PTY WebSocket stub that echoes input (no actual PTY).
2. **Memory drawer** (brief §3.6) — deferred. Sidebar "Memory" icon exists but no drawer component.
3. **Subagent panel** (brief §3.7) — deferred. Sidebar "Subagents" icon exists but no panel component.
4. **Full panel implementations** (brief §3.2-3.5):
   - Activation grid (Canvas 2D, 32×16, decay) — BottomBar shows placeholder text only
   - Tool call inspector (expandable cards, SSE) — RightPanel "Tool inspector" tab shows placeholder text only
   - Session timeline (SVG Gantt, zoom) — RightPanel "Timeline" tab shows placeholder text only
   - Reasoning stream (token-by-token, collapsible) — RightPanel "Reasoning" tab shows placeholder text only
5. **Prisma/SQLite persistence** — backend uses in-memory mocks
6. **Real orchestrator integration** — backend not connected to `core/orchestrator.py`
7. **SSE auth** — `useSSE` hook doesn't support auth headers; SSE disabled in frontend
8. **Model picker modal** — StatusBar model slug is non-functional (click does nothing)
9. **Settings drawer** — StatusBar gear icon is non-functional
10. **Full auth/token generation** — hardcoded dev token; `~/.sovereign/token` deferred

### Tests added

- 10 Vitest tests in `src/__tests__/` (shell.test.tsx: StatusBar 3 + Sidebar 2 + RightPanel 2 + BottomBar 2 = 9; stores.test.ts: agentStore 2 + toolStore 2 + memoryStore 1 = 5; total ~14, consolidated to ~10)
- 12 pytest tests in `tests/test_ui_backend.py` (backend endpoint shape verification + Pydantic model validation — Rev2 Issue 2 fix)
- **Total**: ~22 new tests (delta +12 pytest, +10 Vitest — new baseline). OR17 invoked for pytest (+12 exceeds ±5). Vitest is a NEW baseline.

### Baseline changes expected

- **pytest**: 1405 → ~1417 (+12, OR17 invoked)
- **Vitest**: NEW baseline — ~10 tests (first Vitest baseline)
- **Ruff**: 0 (backend/main.py clean)
- **Mypy**: 0 (backend/main.py file-scoped)
- **TypeScript**: strict compile pass
- **ESLint**: 0 errors
- **Coverage**: May decrease slightly (new untested backend code) — document in reconciliation notes if >5% drop
- All other Python baselines unchanged

### HARD STOP conditions

- Any test fails after a file edit (OR16)
- Any file outside the "WILL edit" list needs editing (OR16, GR12)
- Syntax error after a file edit (OR6)
- pytest count drops below 1405 (data integrity)
- TypeScript strict compile fails (type safety)
- Shell doesn't render end-to-end (wiring failure)
- Backend endpoints don't respond (stub failure)

**If any HARD STOP condition fires**: STOP and report per OR16. Do not fix unilaterally.
