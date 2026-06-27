# Web GUI Fixes 1 — Round Table Review Brief

---

## Part 1: Roles/Rules

Your job is to find issues in this prompt, not rewrite it. The prompt adds error tracking + error boundaries to a Next.js 15 frontend that currently has zero error handling. Assume this approach will fail — identify how. Each issue must include a concrete failure scenario. You may respond "Clean pass" if the approach is sound.

Ban: style comments, formatting preferences, speculative future features.

---

## Part 2: Context

### Problem

The Sovereign AI web GUI (Next.js 15 + TypeScript + Zustand) has **thousands of errors when loading**. The root cause is likely 1-2 cascading failures, but they're invisible because:

- No `error.tsx` or `global-error.tsx` (Next.js error boundaries)
- No React `ErrorBoundary` component wrapping panels
- No global error listener (`window.onerror`)
- No error logging — errors vanish into the console

When one component crashes, Next.js shows a blank page or raw stack trace. Devin can't tell which component is the root cause, so it tries to fix "thousands of issues" when it's really 1-2 cascading.

### Solution Proposed in Prompt

The prompt creates 4 files and edits 3:

| Step | File | Purpose |
|------|------|---------|
| 1 | `src/hooks/useErrorLogger.ts` | Catches `window.onerror` + `unhandledrejection`, buffers errors, flushes to backend every 5s via `POST /api/errors/log` |
| 2 | `src/components/ErrorBoundary.tsx` | React class component catches render errors per-panel, shows red error box with stack trace + retry button, logs to error buffer |
| 3 | `src/app/error.tsx` + `src/app/global-error.tsx` | Next.js error boundaries — page-level and layout-level fallback |
| 4 | `src/app/page.tsx` (edit) | Wrap every panel in `<ErrorBoundary componentName="X">` |
| 5 | `src/components/shell/ShellClient.tsx` (edit) | Call `startErrorLogging()` on mount |
| 6 | `web/server.py` (edit) | Add `POST /api/errors/log` (append to `logs/frontend-errors.log`), `GET /api/errors/log` (retrieve), `DELETE /api/errors/log` (clear) |

### Architecture

```
Browser → window.onerror → useErrorLogger buffer → POST /api/errors/log every 5s → logs/frontend-errors.log
         ↘ ErrorBoundary componentDidCatch → same buffer → same flush
         ↘ Next.js error.tsx → page-level fallback (no logging, just UI)
```

### Key Design Decisions

**Decision 1: In-memory buffer + 5s flush interval (not real-time).**
Reasoning: Real-time logging on every error would flood the network if a component errors in a render loop. 5s batch is a balance between latency and load. Risk: if the page crashes before the 5s flush, errors in the buffer are lost.

**Decision 2: ErrorBoundary is a React class component (not function).**
Reasoning: React's `getDerivedStateFromError` + `componentDidCatch` only work with class components. There's no hook equivalent. This is a React limitation, not a design choice.

**Decision 3: Error log is JSONL file on disk (not database).**
Reasoning: This is a debugging tool, not a production feature. A flat file is simple, easy to `cat` and upload, and doesn't require schema/migration. The file is `logs/frontend-errors.log`.

**Decision 4: Every panel wrapped in ErrorBoundary individually.**
Reasoning: If TasksPanel crashes, WorkersPanel should still render. Individual boundaries isolate failures. The `componentName` prop identifies which panel errored.

**Decision 5: No jarvis-open/jarvis-close, no tag, no CHANGELOG.**
Reasoning: This is a direct bug fix, not a plan. Adding plan overhead would slow down the fix. Commit message: `fix: add error tracking + error boundaries to web GUI`.

### Open Questions

1. **Buffer loss on crash**: If the page hard-crashes (e.g., out of memory) before the 5s flush fires, errors in the buffer are lost. Should the flush interval be shorter (1s)? Or should errors be sent immediately via `navigator.sendBeacon()` (which works even during page unload)?

2. **Backend not running**: If the FastAPI backend isn't running when the frontend loads, `POST /api/errors/log` will fail. The hook catches this and puts errors back in the buffer — but the buffer grows unbounded. Should there be a max buffer size (e.g., 100 entries)?

3. **Error log file growth**: `logs/frontend-errors.log` grows forever. Should there be a size limit or rotation? Or is it acceptable for a debugging tool that gets cleared manually?

4. **ErrorBoundary retry button**: Clicking "Retry" calls `setState({ hasError: false })`, which re-renders the component. If the error is deterministic (same props → same crash), this creates an infinite retry loop. Should the retry be disabled after 3 attempts?

5. **`startErrorLogging()` return value**: The function returns a cleanup function, but `useEffect` in ShellClient may not call it if the component unmounts during initial render. Is the cleanup guaranteed?

6. **CORS for error logging**: The frontend calls `POST /api/errors/log` via relative path (`/api/errors/log`). This goes through the Next.js rewrite proxy. But if the proxy isn't configured for POST requests (only GET), the call fails. Does the existing `next.config.ts` rewrite handle POST?

---

## Part 3: Answer Format

Respond with:

1. **Verdict**: "Clean pass" OR "Issues found"
2. **If issues found, categorize**:
   - **CRITICAL**: Data loss, security vulnerability, irreversible damage
   - **HIGH**: Will cause Devin STOP, test failure, or the error tracking itself fails
   - **MEDIUM**: Degraded functionality, some errors missed
   - **LOW**: Style, naming, minor
3. **For each issue**: concrete failure scenario + suggested fix
4. **Other concerns**: anything not covered above

Permitted: "Clean pass" if the approach is sound.
