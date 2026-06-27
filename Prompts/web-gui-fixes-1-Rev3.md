# Web GUI Fixes 1 (Rev3) — Error Tracking + Error Boundaries

**Direct Devin execution. No plan overhead.**

**Rev3 fixes**: (1) `retryCount` NOT reset in `getDerivedStateFromError` — was completely broken. (2) Buffer restore checks `isStarted` — prevents orphaned errors. (3) `flushSync` only clears buffer if `sendBeacon` returns true. (4) `WeakSet` instead of mutating error objects. (5) `flushSync()` called from `error.tsx`/`global-error.tsx` for early crashes. (6) Backend uses `asyncio.to_thread` for file I/O. (7) `useRef` guard in error.tsx prevents duplicate logging. (8) `Optional[str]` for Python 3.9 compat. (9) Buffer keeps first 20 unique errors + last 80 (root cause preserved). (10) Dedup by message hash.

---

## Step 1: Create Error Logging Hook

Create `src/hooks/useErrorLogger.ts`:

```typescript
"use client";

export interface ErrorLogEntry {
  timestamp: string;
  type: "error" | "unhandledrejection" | "component";
  message: string;
  stack?: string;
  filename?: string;
  line?: number;
  column?: number;
  componentStack?: string;
  componentName?: string;
}

const MAX_BUFFER_SIZE = 100;
const MAX_UNIQUE_FIRST = 20; // Rev3: preserve first N unique errors (root cause)
const errorBuffer: ErrorLogEntry[] = [];
const uniqueErrors: ErrorLogEntry[] = []; // Rev3: separate buffer for first-seen errors
const seenMessages = new Set<string>(); // Rev3: dedup by message hash
let flushInterval: ReturnType<typeof setInterval> | null = null;
let isStarted = false;

// Rev3: WeakSet instead of mutating error objects (frozen errors won't throw)
const handledErrors = new WeakSet<Error>();

function getErrorHash(entry: { message: string; stack?: string }): string {
  // Rev3: simple hash for dedup — first 100 chars of message + first 200 of stack
  return (entry.message.slice(0, 100) + "|" + (entry.stack || "").slice(0, 200));
}

function addToBuffer(entry: ErrorLogEntry) {
  const hash = getErrorHash(entry);
  if (seenMessages.has(hash)) {
    // Rev3: skip duplicate — we've seen this exact error before
    return;
  }
  seenMessages.add(hash);

  // Rev3: first MAX_UNIQUE_FIRST unique errors go to uniqueErrors (never evicted)
  if (uniqueErrors.length < MAX_UNIQUE_FIRST) {
    uniqueErrors.push(entry);
  }

  // All errors also go to the main buffer (capped)
  if (errorBuffer.length >= MAX_BUFFER_SIZE) {
    errorBuffer.shift(); // Drop oldest from main buffer
  }
  errorBuffer.push(entry);
  console.error("[ERROR LOG]", entry);
}

function getAllBuffered(): ErrorLogEntry[] {
  // Rev3: flush unique errors first (root cause), then recent errors
  const uniqueNotYetFlushed = uniqueErrors.filter(e => !errorBuffer.includes(e));
  return [...uniqueNotYetFlushed, ...errorBuffer];
}

function clearAllBuffers() {
  errorBuffer.length = 0;
  uniqueErrors.length = 0;
  seenMessages.clear();
}

function flushSync() {
  const allErrors = getAllBuffered();
  if (allErrors.length === 0) return;

  // Rev3: only clear if sendBeacon succeeds (or is unavailable — then try fetch)
  if (typeof navigator !== "undefined" && navigator.sendBeacon) {
    const blob = new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" });
    const success = navigator.sendBeacon("/api/errors/log", blob);
    if (success) {
      clearAllBuffers();
      return;
    }
    // sendBeacon failed — don't clear buffer, errors are still in memory
  }
  // Fallback: try synchronous fetch (best effort)
  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/errors/log", false); // synchronous
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({ errors: allErrors }));
    if (xhr.status === 200) {
      clearAllBuffers();
    }
  } catch {
    // Both failed — errors remain in buffer for next attempt
  }
}

export function startErrorLogging() {
  // Rev3: check window BEFORE setting isStarted (SSR guard)
  if (typeof window === "undefined") return () => {};
  if (isStarted) return () => {};
  isStarted = true;

  const errorHandler = (event: ErrorEvent) => {
    // Rev3: WeakSet check instead of mutation
    if (event.error && handledErrors.has(event.error)) return;
    addToBuffer({
      timestamp: new Date().toISOString(),
      type: "error",
      message: event.message,
      filename: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error?.stack,
    });
  };

  const rejectionHandler = (event: PromiseRejectionEvent) => {
    addToBuffer({
      timestamp: new Date().toISOString(),
      type: "unhandledrejection",
      message: String(event.reason?.message || event.reason),
      stack: event.reason?.stack,
    });
  };

  window.addEventListener("error", errorHandler);
  window.addEventListener("unhandledrejection", rejectionHandler);

  const beforeUnloadHandler = () => flushSync();
  window.addEventListener("beforeunload", beforeUnloadHandler);

  flushInterval = setInterval(async () => {
    const allErrors = getAllBuffered();
    if (allErrors.length === 0) return;

    // Clear buffers before sending (if send fails, we restore)
    const uniqueBackup = [...uniqueErrors];
    const mainBackup = [...errorBuffer];
    const seenBackup = new Set(seenMessages);
    clearAllBuffers();

    try {
      const res = await fetch("/api/errors/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ errors: allErrors }),
      });
      if (!res.ok) {
        // Rev3: restore buffers if send failed AND logger is still active
        if (isStarted) {
          uniqueErrors.push(...uniqueBackup);
          errorBuffer.push(...mainBackup);
          seenMessages.clear();
          seenBackup.forEach(m => seenMessages.add(m));
        }
        // If !isStarted, cleanup already ran — try sendBeacon as last resort
        else if (typeof navigator !== "undefined" && navigator.sendBeacon) {
          navigator.sendBeacon("/api/errors/log", new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" }));
        }
      }
    } catch {
      // Network failure — same restore logic
      if (isStarted) {
        uniqueErrors.push(...uniqueBackup);
        errorBuffer.push(...mainBackup);
        seenMessages.clear();
        seenBackup.forEach(m => seenMessages.add(m));
      } else if (typeof navigator !== "undefined" && navigator.sendBeacon) {
        navigator.sendBeacon("/api/errors/log", new Blob([JSON.stringify({ errors: allErrors })], { type: "application/json" }));
      }
    }
  }, 5000);

  return () => {
    window.removeEventListener("error", errorHandler);
    window.removeEventListener("unhandledrejection", rejectionHandler);
    window.removeEventListener("beforeunload", beforeUnloadHandler);
    if (flushInterval) clearInterval(flushInterval);
    flushInterval = null;
    isStarted = false;
    flushSync(); // Flush on SPA navigation
  };
}

export function logComponentError(error: Error, componentStack?: string, componentName?: string) {
  // Rev3: WeakSet instead of mutation (won't throw on frozen objects)
  handledErrors.add(error);
  addToBuffer({
    timestamp: new Date().toISOString(),
    type: "component",
    message: error.message,
    stack: error.stack,
    componentStack,
    componentName,
  });
}

// Rev3: export flushSync for error.tsx/global-error.tsx to call on early crashes
export { flushSync };
```

---

## Step 2: Create Error Boundary Component

Create `src/components/ErrorBoundary.tsx`:

```typescript
"use client";
import React from "react";
import { logComponentError } from "@/hooks/useErrorLogger";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  componentName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

const MAX_RETRIES = 3;
const isDev = process.env.NODE_ENV === "development";

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  // Rev3: do NOT reset retryCount here — only set hasError + error
  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logComponentError(error, errorInfo.componentStack, this.props.componentName);
  }

  handleRetry = () => {
    // Rev3: increment retryCount, check limit BEFORE resetting hasError
    this.setState((prev) => {
      const nextCount = prev.retryCount + 1;
      if (nextCount > MAX_RETRIES) return prev; // Don't retry if over limit
      return { hasError: false, error: null, retryCount: nextCount };
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const name = this.props.componentName || "Component";
      const retriesLeft = Math.max(0, MAX_RETRIES - this.state.retryCount);

      return (
        <div style={{
          padding: "1rem", margin: "0.5rem", background: "#1a1a2e",
          border: "1px solid #ef4444", borderRadius: "4px",
          color: "#e0e0e0", fontFamily: "monospace", fontSize: "13px",
        }}>
          <div style={{ color: "#ef4444", fontWeight: "bold", marginBottom: "0.5rem" }}>
            [{name}] Error
          </div>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>{this.state.error?.message}</div>
          {isDev && (
            <details style={{ color: "#64748b" }}>
              <summary style={{ cursor: "pointer", color: "#94a3b8" }}>Stack trace</summary>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "11px", marginTop: "0.5rem" }}>
                {this.state.error?.stack}
              </pre>
            </details>
          )}
          {retriesLeft > 0 ? (
            <button onClick={this.handleRetry} style={{
              marginTop: "0.5rem", padding: "0.25rem 0.75rem", background: "#3b82f6",
              color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "12px",
            }}>
              Retry ({retriesLeft} left)
            </button>
          ) : (
            <div style={{ marginTop: "0.5rem", color: "#64748b", fontSize: "12px" }}>
              Retry limit reached — fix the root cause
            </div>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
```

---

## Step 3: Create Next.js Error Boundaries (with logging + flush)

Create `src/app/error.tsx`:

```tsx
"use client";
import { useEffect, useRef } from "react";
import { logComponentError, flushSync } from "@/hooks/useErrorLogger";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const loggedRef = useRef(false); // Rev3: prevent duplicate logging on re-render

  useEffect(() => {
    if (!loggedRef.current) {
      try {
        logComponentError(error, undefined, "PageErrorBoundary");
        flushSync(); // Rev3: immediately flush — error.tsx may fire before startErrorLogging
      } catch (e) {
        console.error("[ERROR LOG] Failed to log page error:", e);
      }
      loggedRef.current = true;
    }
  }, [error]);

  const isDev = process.env.NODE_ENV === "development";

  return (
    <div style={{ padding: "2rem", background: "#0c0c0f", color: "#e0e0e0", minHeight: "100vh", fontFamily: "monospace" }}>
      <h2 style={{ color: "#ef4444", marginBottom: "1rem" }}>Page Error</h2>
      <div style={{ color: "#94a3b8", marginBottom: "1rem" }}>{error.message}</div>
      {isDev && (
        <pre style={{ whiteSpace: "pre-wrap", fontSize: "13px", color: "#64748b", background: "#1a1a2e", padding: "1rem", borderRadius: "4px" }}>
          {error.stack}
        </pre>
      )}
      <button onClick={reset} style={{ marginTop: "1rem", padding: "0.5rem 1rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>
        Try Again
      </button>
    </div>
  );
}
```

Create `src/app/global-error.tsx`:

```tsx
"use client";
import { useEffect, useRef } from "react";
import { logComponentError, flushSync } from "@/hooks/useErrorLogger";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const loggedRef = useRef(false);

  useEffect(() => {
    if (!loggedRef.current) {
      try {
        logComponentError(error, undefined, "GlobalErrorBoundary");
        flushSync(); // Rev3: immediately flush — global-error may fire before startErrorLogging
      } catch (e) {
        console.error("[ERROR LOG] Failed to log global error:", e);
      }
      loggedRef.current = true;
    }
  }, [error]);

  const isDev = process.env.NODE_ENV === "development";

  return (
    <html>
      <body style={{ padding: "2rem", background: "#0c0c0f", color: "#e0e0e0", fontFamily: "monospace" }}>
        <h2 style={{ color: "#ef4444" }}>Fatal Error — Layout Crashed</h2>
        <div style={{ color: "#94a3b8", marginBottom: "1rem" }}>{error.message}</div>
        {isDev && (
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "13px", color: "#64748b" }}>
            {error.stack}
          </pre>
        )}
        <button onClick={reset} style={{ marginTop: "1rem", padding: "0.5rem 1rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>
          Try Again
        </button>
      </body>
    </html>
  );
}
```

---

## Step 4: Wrap Panels AND Shell Components in ErrorBoundary

Update `src/app/page.tsx` — wrap each panel:

```tsx
"use client";
import { ErrorBoundary } from "@/components/ErrorBoundary";
// ... existing imports ...

export default function Home() {
  // ... existing hooks ...
  switch (activeView) {
    case VIEWS.HOME: return <ErrorBoundary componentName="TerminalPanel"><TerminalPlaceholder /></ErrorBoundary>;
    case VIEWS.TASKS: return <ErrorBoundary componentName="TasksPanel"><TasksPanel /></ErrorBoundary>;
    case VIEWS.WORKERS: return <ErrorBoundary componentName="WorkersPanel"><WorkersPanel /></ErrorBoundary>;
    case VIEWS.APPROVALS: return <ErrorBoundary componentName="ApprovalQueuePanel"><ApprovalQueuePanel /></ErrorBoundary>;
    case VIEWS.COSTS: return <ErrorBoundary componentName="CostDashboardPanel"><CostDashboardPanel /></ErrorBoundary>;
    case VIEWS.TOOLS: return <ErrorBoundary componentName="SkillsPanel"><SkillsPanel /></ErrorBoundary>;
    case VIEWS.HELP: return <ErrorBoundary componentName="HelpPanel"><HelpPanel /></ErrorBoundary>;
    case VIEWS.TERMINAL: return <ErrorBoundary componentName="TerminalPanel"><TerminalPanel /></ErrorBoundary>;
    case VIEWS.SYSTEM: return <ErrorBoundary componentName="SystemStatsPanel"><SystemStatsPanel /></ErrorBoundary>;
    case VIEWS.SUBAGENTS: return <ErrorBoundary componentName="SubagentPanel"><SubagentPanel /></ErrorBoundary>;
    case VIEWS.MODELS: return <ErrorBoundary componentName="ModelsPanel"><ModelsPanel /></ErrorBoundary>;
    case VIEWS.RESOURCES: return <ErrorBoundary componentName="ResourceMonitorPanel"><ResourceMonitorPanel /></ErrorBoundary>;
    default: return <ErrorBoundary componentName="TerminalPanel"><TerminalPlaceholder /></ErrorBoundary>;
  }
}
```

Update `src/components/shell/ShellClient.tsx` — wrap shell components + start logging:

```tsx
"use client";
import { useEffect } from "react";
import { startErrorLogging } from "@/hooks/useErrorLogger";
import { ErrorBoundary } from "@/components/ErrorBoundary";
// ... existing imports ...

export function ShellClient({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const cleanup = startErrorLogging();
    return cleanup;
  }, []);

  return (
    <div className="jarvis-shell" data-testid="jarvis-shell">
      <ErrorBoundary componentName="StatusBar"><StatusBar /></ErrorBoundary>
      <ErrorBoundary componentName="Sidebar"><Sidebar /></ErrorBoundary>
      <MainPane>{children}</MainPane>
      <ErrorBoundary componentName="RightPanel"><RightPanel /></ErrorBoundary>
      <ErrorBoundary componentName="BottomBar"><BottomBar /></ErrorBoundary>

      {activeDrawer && (
        <>
          <div className="drawer-backdrop" onClick={closeDrawer} data-testid="drawer-backdrop" />
          {activeDrawer === "memory" && <ErrorBoundary componentName="MemoryDrawer"><MemoryDrawer /></ErrorBoundary>}
          {activeDrawer === "settings" && <ErrorBoundary componentName="SettingsDrawer"><SettingsDrawer /></ErrorBoundary>}
        </>
      )}
    </div>
  );
}
```

---

## Step 5: Create Backend Error Log Endpoint (async I/O + Python 3.9 compat)

Add to `web/server.py`:

```python
import asyncio
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional

# Rev3: absolute path
ERROR_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "frontend-errors.log"

# Rev3: Optional[str] for Python 3.9 compat (was str | None)
class ErrorLogItem(BaseModel):
    timestamp: str
    type: str
    message: str
    stack: Optional[str] = None
    filename: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    componentStack: Optional[str] = None
    componentName: Optional[str] = None

class ErrorLogRequest(BaseModel):
    # Rev3: max 200 items per batch
    errors: List[ErrorLogItem] = Field(default_factory=list, max_length=200)

@app.post("/api/errors/log")
async def log_frontend_errors(request: ErrorLogRequest):
    """Receive frontend error logs and append to local file."""
    # Rev3: async file I/O — don't block event loop
    def _write():
        ERROR_LOG_FILE.parent.mkdir(exist_ok=True)
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            for error in request.errors:
                f.write(json.dumps(error.model_dump(), default=str) + "\n")
    await asyncio.to_thread(_write)
    return {"status": "ok", "received": len(request.errors)}

@app.get("/api/errors/log")
async def get_frontend_errors():
    """Retrieve frontend error log for upload to GLM."""
    # Rev3: async file read
    def _read():
        if not ERROR_LOG_FILE.exists():
            return []
        lines = ERROR_LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        errors = []
        for line in lines:
            if line.strip():
                try:
                    errors.append(json.loads(line))
                except:
                    pass
        return errors
    errors = await asyncio.to_thread(_read)
    return {"errors": errors, "count": len(errors)}

@app.delete("/api/errors/log")
async def clear_frontend_errors():
    """Clear frontend error log after upload."""
    def _clear():
        if ERROR_LOG_FILE.exists():
            ERROR_LOG_FILE.unlink()
    await asyncio.to_thread(_clear)
    return {"status": "cleared"}
```

---

## Step 6: Build (separate steps)

```bash
cd src && npx tsc --noEmit
```

Then:
```bash
cd src && npm run build
```

Then (separate terminal):
```bash
cd src && npm run dev
```

---

## Step 7: Collect Error Log

After navigating through all panels:

```bash
cat logs/frontend-errors.log
```

Or via API:
```bash
curl http://localhost:8000/api/errors/log
```

Upload this to GLM for diagnosis. Clear after:
```bash
curl -X DELETE http://localhost:8000/api/errors/log
```

---

## Step 8: Fix Root Causes

Read the error log. Fix the ROOT CAUSE of each unique error. Do NOT add try/catch around symptoms.

---

## Step 9: Verify

```bash
cd src && npx tsc --noEmit && npm run build
cd src && npm run dev
```

Navigate through every panel. Check:
- No red error boxes
- No console errors (F12 → Console)
- All panels render content

Clear log, navigate again, collect:
```bash
curl -X DELETE http://localhost:8000/api/errors/log
# navigate through all panels
curl http://localhost:8000/api/errors/log
```

If error count is 0 or near-0, the GUI is stable.

---

## Step 10: Commit

```bash
git add -A
git commit -m "fix: add error tracking + error boundaries to web GUI"
git push origin master
```
