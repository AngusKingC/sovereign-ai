# Sovereign AI UI Shell — Architectural Decisions

This document records key architectural decisions for the UI shell implementation (Plan 80).

## Decision 1: Frontend Framework Choice

**Context**: Need a modern React framework with strong TypeScript support and developer experience.

**Options considered**:
- Next.js 15 (App Router)
- Vite + React
- Remix

**Decision**: Next.js 15 with App Router.

**Rationale**:
- Built-in routing and optimization
- Strong TypeScript support
- Server components for future SSR opportunities
- Large ecosystem and community
- Turbopack for fast builds

**Trade-offs**:
- Opinionated structure (acceptable for this project)
- Slightly larger bundle size (mitigated by code splitting)

---

## Decision 2: State Management

**Context**: Need to manage agent state, memory slots, tool calls, and subagents across components.

**Options considered**:
- Redux Toolkit
- Zustand
- Jotai
- React Context

**Decision**: Zustand 4.5.

**Rationale**:
- Minimal boilerplate
- TypeScript-first API
- No provider wrapping required
- Good performance with shallow selectors
- Simple async action patterns

**Trade-offs**:
- Less ecosystem tooling than Redux (acceptable for this scope)

---

## Decision 3: Real-time Data Streaming

**Context**: Need to stream tool calls, memory activations, and reasoning tokens from backend.

**Options considered**:
- WebSocket
- Server-Sent Events (SSE)
- Polling

**Decision**: Server-Sent Events (SSE) with cookie-based auth.

**Rationale**:
- Unidirectional (server → client) matches our use case
- Simpler than WebSocket (no bidirectional handshake)
- Native browser support via EventSource
- Cookie-based auth works cross-origin with withCredentials: true

**Trade-offs**:
- No binary streaming (acceptable for JSON payloads)
- Requires custom reconnect logic (implemented in useSSE hook)

---

## Decision 4: Authentication Strategy

**Context**: Need to authenticate API requests and SSE connections between frontend (localhost:3000) and backend (localhost:8000).

**Options considered**:
- Query-param auth token
- Bearer token in header
- Cookie-based auth

**Decision**: Cookie-based auth with fallback to Bearer header.

**Rationale**:
- Cookies work automatically with SSE (withCredentials: true)
- Bearer header for non-browser clients (future CLI integration)
- SameSite=lax for development (cross-origin localhost)
- httponly for security (no JS access)

**Trade-offs**:
- Requires careful CORS configuration (implemented in FastAPI middleware)

---

## Decision 5: UI Component Library

**Context**: Need consistent, accessible components with dark theme support.

**Options considered**:
- shadcn/ui
- Chakra UI
- Mantine
- Headless UI + custom

**Decision**: shadcn/ui with Tailwind CSS v4.

**Rationale**:
- Copy-paste components (no runtime dependency)
- Tailwind v4 for modern CSS-first styling
- Built-in accessibility
- Customizable via Tailwind classes
- Strong TypeScript support

**Trade-offs**:
- Requires manual component updates (acceptable for this scope)

---

## Decision 6: Backend Framework

**Context**: Need a Python async web framework with type safety and easy SSE support.

**Options considered**:
- FastAPI
- Django
- Flask
- Starlette

**Decision**: FastAPI.

**Rationale**:
- Native async support
- Pydantic for type-safe data validation
- Built-in OpenAPI docs
- Easy SSE with StreamingResponse
- Strong TypeScript-like experience

**Trade-offs**:
- More opinionated than Starlette (acceptable for this scope)

---

## Decision 7: Deferrals

The following features were explicitly deferred to follow-on plans to manage scope:

1. **Prisma/SQLite database**: Backend uses in-memory mocks. Real persistence deferred.
2. **xterm.js terminal**: PTY WebSocket stub only. Full terminal deferred.
3. **Timeline panel**: Placeholder only. Full implementation deferred.
4. **Reasoning panel**: Placeholder only. Full implementation deferred.
5. **Real orchestrator integration**: Backend serves mocked data. Real integration deferred.

**Rationale**: Focus on shell layout, wiring, and Tool Inspector as proof-of-concept.

---

## Decision 8: TypeScript Strict Mode

**Context**: Need type safety for the entire src/ directory.

**Decision**: Enable "strict": true in 	sconfig.json.

**Rationale**:
- Catches type errors at compile time
- Enforces null safety
- Improves IDE autocomplete
- Equivalent to AR14 for Python (type annotations on all public functions)

**Trade-offs**:
- Stricter development experience (acceptable for this project)

---

## Decision 9: Testing Strategy

**Context**: Need to verify frontend and backend functionality.

**Frontend**: Vitest + React Testing Library.
- Unit tests for Zustand stores
- Component tests for shell components
- jsdom environment for DOM simulation

**Backend**: pytest + FastAPI TestClient.
- API endpoint tests
- Auth middleware tests
- Mock data verification

**Rationale**: Lightweight, fast, and integrates with existing tooling.

---

## Decision 10: Color Tokens

**Context**: Need a cohesive dark theme with semantic color names.

**Decision**: Custom CSS variables in globals.css with Tailwind v4 @theme inline.

**Rationale**:
- Semantic names (surface-base, 	ext-primary) vs hardcoded colors
- Easy theme switching (future light mode)
- Tailwind v4 native support for CSS variables

**Trade-offs**:
- Custom token system (acceptable for this project's needs)

---

## Decision 11: Vanilla JS UI Rebuild (SUPERSEDES Decisions 1, 2, 4, 5, 8, 9, 10)

**Date**: 2026-06-27
**Commits**: `5de16ba` (rebuild) → `d8fb61a` (auth/layout fixes) → `c48ce4c` (remove `src/`)
**Tag**: `web-gui-rebuild-cleanup-1`

**Context**: The Next.js 15 + React + TypeScript + Tailwind v4 + Zustand frontend (Plans 80–95, Decisions 1–10 above) was abandoned after three failed remediation rounds (Web GUI Fixes 1–3). Persistent framework-level errors could not be resolved:

- **Hydration mismatches** between server-rendered and client-rendered markup in `ShellClient.tsx` — caused by `Date.now()` and `Math.random()` calls in render paths, plus stale Zustand state on hot reload.
- **TypeScript strict-mode breakage** — `tsconfig.json` `"strict": true` surfaced pre-existing latent type errors in `api.ts`, `useWorkersPolling.ts`, and `workerStore.ts` that propagated as build failures.
- **PowerShell file corruption** (L21) — PowerShell's interpretation of backticks (`` ` ``) as escape characters and `${}` as variable expansion corrupted TypeScript template literals when Devin wrote `.ts`/`.tsx` files via PowerShell string operations. Required Node.js writer scripts as a workaround.
- **xterm.js SSR crashes** — dynamic import of `@xterm/xterm` in `TerminalPanel.tsx` failed during Next.js server-side rendering, producing "window is not defined" errors.
- **`useEffect` dependency issues** — polling hooks (`useStatusPolling`, `useWorkersPolling`, `useApprovalsPolling`, `useCostsPolling`, `useMemoryPolling`) re-fired on every render due to unstable function references, causing infinite request loops.
- **Auth/CORS friction** — Next.js dev server (`:3000`) and FastAPI (`:8000`) required CORS configuration and cookie-based auth that was fragile across reloads.

**Decision**: Rebuild the frontend as vanilla JavaScript served directly by FastAPI `StaticFiles`. No build step, no npm, no React, no TypeScript.

**Architecture**:
- `web/static/index.html` — 3-panel layout (sidebar / main pane / right panel), CSS Grid, dark theme, token-entry modal, xterm.js CDN `<script>` tag.
- `web/static/style.css` — single CSS file with CSS variables for theming.
- `web/static/api.js` — `API` object wrapping `fetch()`; reads token from `localStorage.sovereign_token`; attaches `Authorization: Bearer <token>` to every request; on 401, clears token and reloads.
- `web/static/ui.js` — `UI` object managing panel switching, sidebar active state, keyboard shortcuts.
- Per-panel `.js` modules: `chat.js`, `models.js`, `workers.js`, `approvals.js`, `costs.js`, `memory.js`, `logs.js` — each exposes one object with `init()` and `update()` methods.
- `web/server.py` — added `app.mount("/", StaticFiles(directory="web/static", html=True), name="frontend")` after all API routes are registered. Frontend and API share origin (`:8000`), eliminating CORS.
- `web/middleware/auth_middleware.py` — `exempt_prefixes` list (using `startswith`) for unauthenticated paths (`/api/status`, `/api/workers`, `/api/costs`, `/api/approvals`, `/api/memory`, `/api/logs` GET, `/health`, `/api/errors/log` POST). All other `/api/*` paths require bearer token. WebSocket `/ws/pty` accepts `?token=` query param (browsers cannot set headers on WS handshake).
- xterm.js loaded from CDN via `<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.min.js">` in `index.html`. No npm install, no bundler.

**Trade-offs accepted**:
- **No type safety on the frontend.** Mitigated by the `API` wrapper returning parsed JSON and throwing on non-2xx; Pydantic on the backend is the source of truth. Acceptable for a single-user local-first tool.
- **No component reuse pattern.** Each panel is a standalone `.js` file with `init()` + `update()`. Duplicate boilerplate is minimal (3–5 lines per panel) and aids readability.
- **No hot module replacement.** Editing a `.js` file requires a browser refresh. Acceptable — refresh is instant for static files, no rebuild needed.
- **Lost test coverage.** The 52 Vitest tests and 8 Playwright E2E tests (Plans 84–85) tested React components that no longer exist. A future plan may add a small Playwright suite against `http://localhost:8000/` for E2E coverage of the vanilla JS UI.

**Rationale**:
- **Single-user, local-first tool.** The audience is one user (the developer) on a Windows workstation. Build-tooling complexity is unjustified.
- **Edit-and-refresh workflow.** Changing a panel = editing one `.js` file + refreshing the browser. No `npm install`, no `next build`, no transpiler latency.
- **Same-origin eliminates CORS.** Frontend and API both on `:8000`. Cookie/header auth "just works."
- **Devin can write `.js` files via Git Bash without corruption.** Vanilla JS has no template literals with backticks that PowerShell would mangle (L21 is now historical).
- **Smaller attack surface.** No `node_modules/` to audit, no npm supply chain, no transitive deps.

**Known follow-ups** (not blocking):
- Terminal panel `/ws/pty` has a Windows `pywinpty` API compatibility issue (`cols`/`rows` params, `read`/`terminate` methods). Tracked separately.
- No E2E test suite for the vanilla JS UI. A Playwright suite against `http://localhost:8000/` may be added in a future plan.

**Superseded decisions** (retained above for historical reference):
- **Decision 1** (Next.js 15) — superseded by vanilla JS.
- **Decision 2** (Zustand 4.5) — superseded by per-panel module objects.
- **Decision 4** (Cookie-based auth with Bearer fallback) — superseded by Bearer-only with `localStorage` persistence + token-entry modal.
- **Decision 5** (shadcn/ui + Tailwind v4) — superseded by hand-written CSS with CSS variables.
- **Decision 8** (TypeScript strict mode) — N/A, no TypeScript.
- **Decision 9** (Vitest + React Testing Library) — N/A, no React. pytest is the only test suite.
- **Decision 10** (Tailwind v4 @theme inline color tokens) — superseded by `:root { --color-... }` in `style.css`.

**Decisions retained** (still apply):
- **Decision 3** (SSE for real-time streams) — `/api/agent/reasoning` and `/api/memory/activations` are still SSE. Vanilla JS uses `EventSource` natively.
- **Decision 6** (FastAPI backend) — unchanged.
- **Decision 7** (Deferrals) — most items (Prisma/SQLite, real orchestrator integration) have since been wired; the deferral list itself is historical.
