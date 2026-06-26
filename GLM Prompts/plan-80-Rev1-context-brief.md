# Plan 80 Rev1 Context Brief — Sovereign AI UI Shell (Tier 2)

**Tier 2 plan — 5-AI panel review required.** This brief is framed for the 5-AI panel (Claude, Kimi, DeepSeek, Gemini, ChatGPT), not just Claude. GLM commits to adopting the highest-scoring recommendation per GR4.

## Part 1: Roles/Rules

Your job is to find issues in this plan, not rewrite it. Assume this plan will fail — identify how.

Each issue you report must include:
- A concrete failure scenario (what breaks, when, why)
- Evidence from the codebase, brief, or governance documents
- The impact if the issue is not addressed
- A suggested fix (optional — GLM decides whether to adopt)

You may report "No issues found" if the plan is sound. Do not invent problems.

Ban: style comments, formatting suggestions, speculative future features, "nice to have" items. Substance only.

**Special focus for this panel**: The 6 open questions in Part 2 are the core of this review. Each panelist should address all 6 directly. GLM will judge responses on the quality of reasoning, not on whether they agree with GLM's position.

---

## Part 2: Context

### Plan Scope

Build the Sovereign AI web UI shell — the foundation for all future UI work. This plan delivers:

1. **Next.js 15 + TypeScript + Tailwind v4 + shadcn/ui + Zustand + Framer Motion** project setup (new `src/` directory)
2. **FastAPI backend stubs** serving mocked data for all §5 API endpoints (new `backend/` directory)
3. **Shell layout components**: StatusBar (sticky top), Sidebar (64px, expands on hover), RightPanel (3 tabs with placeholders), BottomBar (activation grid placeholder + token counter)
4. **Zustand stores** (minimal schemas): agentStore, memoryStore, toolStore, subagentStore
5. **`useSSE` hook** — generic, with exponential backoff reconnect
6. **API client** — typed fetch/SSE wrappers
7. **Wiring** — shell polls `/api/status`, latency updates live. SSE hooks present but disabled (auth gap — see D5)
8. **Tests** — 5 Vitest (frontend) + 10 pytest (backend)
9. **DECISIONS.md** — logs architectural decisions
10. **Design tokens** — `globals.css` with brief §6 color palette

**Explicitly deferred** (out of scope, listed in plan, NOT abandoned):
- xterm.js/PTY terminal, memory drawer, subagent panel
- Full panel implementations (activation grid, tool inspector, timeline, reasoning — placeholders only)
- Prisma/SQLite (in-memory mocks), real orchestrator integration, SSE auth, model picker modal, settings drawer, full token generation

### Source Brief

`sovereign-ai-glm-prompt.md` specifies:
- Tech stack (§2): Next.js 15, TypeScript 5 strict, shadcn/ui New York, Tailwind v4, Zustand 5, Framer Motion, xterm.js, Recharts, Lucide React, Bun, FastAPI, SQLite/Prisma
- 7 core panels (§3.1-3.7) + shell layout (§4) + API contract (§5) + design tokens (§6) + file structure (§7) + priority order (§8)
- Differentiators from Hermes Agent (§10): amber `#f59e0b` not electric blue, sentence case, xterm.js not Ink, single dark theme, explicit memory UI, no plugin system

### Existing Repo State (verified at commit `f0517d1`, post-prompt-79)

- **Python-only repo** (no `package.json`, no TypeScript)
- **Existing `web/` directory** has FastAPI server (`web/server.py`) with routes: `/health`, `/api/tasks`, `/api/workers`, `/api/trace`, `/ws` — DIFFERENT from brief's §5 API contract
- **Test baseline**: 1405 pytest tests, 67 skipped
- **AR6**: `web/` may import from `core/` only
- **No frontend test infrastructure** (no Vitest, Jest, or Playwright)
- **PLANS.md** lists "Web UI refinement" as Priority 5+ deferred — this plan is the first web UI work

### Key Architectural Decisions (for 5-AI panel review)

| # | Decision | GLM Position | Confidence |
|---|---|---|---|
| D1 | Same repo (Python + TypeScript) vs separate `sovereign-ai-ui` repo | Same repo | 60% |
| D2 | New `backend/` directory vs extend existing `web/server.py` | New `backend/` | 75% |
| D3 | Defer Prisma/SQLite (in-memory mocks) vs include in this plan | Defer | 70% |
| D4 | Shell + placeholder panels only vs include 1-2 full panel implementations | Shell + placeholders only | 75% |
| D5 | SSE auth deferred (EventSource API limitation) vs address now | Defer | 65% |
| D6 | Bun vs Node+npm for runtime/package manager | Bun (follows brief) | 70% |

### Open Questions (address all 6 directly)

1. **Repo structure (D1)**: Same repo (mixed Python/TypeScript, two test suites) or separate `sovereign-ai-ui` repo? GLM recommends same repo (follows brief §7, simpler CI, single git history). What are the maintenance/CI trade-offs? Does mixed-language create pre-commit hook conflicts? How should PLANS.md track two test baselines (pytest + Vitest)?

2. **Backend separation (D2)**: New `backend/` directory or extend existing `web/server.py` with the new routes? GLM recommends new `backend/` (different API contracts, avoids disrupting working `web/` server). Is the separation worth the duplication, or should the new routes merge into `web/`? If separate, when/how do they eventually merge?

3. **Prisma timing (D3)**: Defer Prisma to follow-on plan, or include in this plan? GLM recommends defer (scope management, mocked data is sufficient for shell rendering). Does deferring create rework risk (backend stubs rewritten when Prisma lands)? Or is the mocked-data → Prisma migration clean enough to defer?

4. **Panel scoping (D4)**: Shell + placeholders only, or include 1-2 full panel implementations (e.g., tool inspector + activation grid) in this plan? GLM recommends shell + placeholders only (foundation first, panels incremental). Is that too thin for one plan, or correctly scoped? If the panel feels too thin, which 1-2 panels would deliver the most value as full implementations?

5. **SSE auth gap (D5)**: `useSSE` hook doesn't support auth headers (EventSource API limitation). Plan leaves SSE disabled (`enabled: false`), renders via polling only. Is this acceptable for the shell plan, or does it undermine the "live data" claim? Should this plan use query-param auth (security risk — token in URL/logs) or cookie-based auth (requires backend CORS+credentials config) instead of deferring?

6. **Bun vs Node (D6)**: The brief specifies Bun. Should this plan use Bun for both runtime and package manager, or Node + npm/yarn for ecosystem compatibility? GLM recommends Bun (follows brief). What's the maturity risk? Does Bun's smaller ecosystem justify the risk for a foundation plan, or should Node+npm be the safer choice?

### Author's Reasoning (Attack This — Don't Ratify the Conclusion)

My reasoning for the scoping:

1. **Shell first, panels second.** The brief's §8 priority order starts with "Shell layout — no functionality yet, just the grid with placeholder content." I'm following this literally. The shell is the foundation; panels compose into it. Delivering shell + wiring + backend stubs in one plan lets follow-on plans focus on one panel at a time. **Attack**: Is "shell + stubs + wiring" too much for one plan, or too little? Should the first plan be smaller (shell only, no backend) or larger (shell + 1-2 full panels)?

2. **Backend stubs before real data.** The brief's §8 priority #2 is "Backend stubs — all API endpoints returning mocked data so the frontend has something to connect to immediately." I'm following this. Real orchestrator integration (connecting `backend/` to `core/orchestrator.py`) is deferred — it requires careful SSE event design and is a separate concern. **Attack**: Is deferring real integration the right call, or does it create a "works in dev, breaks in prod" gap?

3. **useSSE hook is the critical path.** The brief's §8 priority #3 is the `useSSE` hook. Every streaming panel depends on it. I'm including it in this plan because it's the wiring that makes the shell "live." But I'm leaving SSE disabled due to the auth gap (D5). **Attack**: Is including the hook but disabling it worse than not including it at all? Does it create false confidence that SSE is "done"?

4. **Same repo, not separate.** I'm following the brief's file structure (`sovereign-ai/src/`, `sovereign-ai/backend/`). This introduces TypeScript to a Python repo, which is messy but simpler than cross-repo coordination. **Attack**: Is the messiness worth it? What specific problems will arise (pre-commit hooks, CI, editor configs, import paths)?

5. **Test infrastructure split.** This plan introduces Vitest for the frontend. The existing pytest baseline (1405) is unaffected. PLANS.md needs a new baseline row for Vitest. I'm proposing ~5 Vitest tests + ~10 pytest tests. **Attack**: Is 5 Vitest tests enough for a shell this size? What's the right test coverage for a foundation plan — minimal (smoke tests) or thorough (component-level)?

6. **Deferring Prisma.** I'm deferring Prisma to keep this plan focused on shell + wiring. Mocked data is sufficient for end-to-end rendering. **Attack**: Does deferring Prisma create rework? When Prisma lands, will the backend stubs need to be rewritten, or can they be refactored incrementally?

### Confidence Levels

| Area | Confidence | Reason |
|---|---|---|
| Stack setup (Next.js 15 + Bun + Tailwind v4 + shadcn/ui) | 85% | Well-documented, standard |
| FastAPI backend stubs (mocked data) | 90% | Straightforward |
| Shell layout (CSS Grid, sticky status bar) | 80% | Brief specifies layout, sticky + grid interactions can be tricky |
| useSSE hook (exponential backoff reconnect) | 75% | Standard but edge cases abound |
| Zustand stores (minimal schemas) | 85% | Well-understood pattern |
| Wiring (live mocked data end-to-end) | 70% | Most complex part — SSE → store → component updates |
| Repo structure (Python + TypeScript same repo) | 60% | Most debatable decision — D1 |
| Test infrastructure (pytest + Vitest split) | 65% | Introduces second test suite, baseline tracking complications |
| **Overall** | **68%** | Below 70% threshold — Tier 2 trigger confirmed |

---

## Part 3: Answer Format

Respond with:

1. **Pre-mortem** (1-2 sentences): "If this plan failed in 6 months, the most plausible reason would be..."

2. **Open questions** (address all 6 directly — D1 through D6):
   - For each: state your position, confidence level, and reasoning
   - If you agree with GLM's position, say why (don't just ratify — engage with the trade-offs)
   - If you disagree, propose an alternative with concrete reasoning

3. **Issues** (0-N, each with):
   - Issue title
   - Severity: CRITICAL / HIGH / MEDIUM / LOW
   - Concrete failure scenario
   - Evidence from codebase, brief, or docs
   - Suggested fix (optional — GLM decides whether to adopt)

4. **Other concerns** (open field — anything unexpected)

5. **Overall verdict**: PROCEED / REVISE / REJECT

If no issues and all 6 open questions are resolved: "No issues found. PROCEED."

---

## Tier Disclosure

This plan is classified **Tier 2** (5-AI panel) per GR4. Triggers:

1. ✅ Architectural decisions (new patterns): Next.js, SSE, Zustand, shadcn/ui — all new to Sovereign AI
2. ✅ Novel territory: First web UI plan — no precedent in the project
3. ✅ Reversible-but-expensive: Wrong stack choice costs multiple plans to fix
4. ✅ 3+ subsystems: `src/`, `backend/`, `prisma/` (deferred), hooks/stores — 4+ subsystems
5. ✅ GLM confidence 68% (below 70% threshold)

**Tier 2 process**: GLM drafts this plan + context brief → user pastes to 5-AI panel (Claude, Kimi, DeepSeek, Gemini, ChatGPT) → GLM judges responses on defined criteria → GLM adopts best-reasoned recommendation → Rev2 (if needed) → Devin executes.

**GLM's commitment** (per GR4): When Tier 2 is triggered, GLM commits to adopting the highest-scoring recommendation — even if it contradicts GLM's original position. This is what makes the pattern work: if GLM always overrode the panel, there'd be no point.

**Judging criteria** (GLM will use to evaluate panel responses):
1. **Reasoning quality** (40%): Does the response engage with the trade-offs, not just state a position?
2. **Evidence** (25%): Does the response cite concrete examples from the brief, repo, or industry?
3. **Risk identification** (20%): Does the response surface risks GLM didn't identify?
4. **Constructive alternatives** (15%): If disagreeing, does the response propose a workable alternative?

The response with the highest weighted score across all 6 open questions will be adopted. If multiple responses tie, GLM will adopt the most conservative (least scope) recommendation.
