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
