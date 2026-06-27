# Web GUI Fixes 1 (Rev2) — Error Tracking + Error Boundaries + Root Cause Fixes

**Not a plan** — direct Devin execution. No jarvis-open/jarvis-close, no tag, no CHANGELOG.

**Rev2 fixes**: (1) `navigator.sendBeacon` for unload-safe flush. (2) `response.ok` check. (3) Logging in error.tsx/global-error.tsx. (4) Max 100 buffer cap. (5) ErrorBoundary on Sidebar/StatusBar/BottomBar. (6) Dedup via `_handled` flag. (7) Max 3 retries. (8) Idempotent `startErrorLogging`. (9) Pydantic validation on backend. (10) Fixed title `]` typo. (11) `componentName` in log. (12) Separate build steps. (13) Absolute log path. (14) Conditional stack traces.

---

## Step 1: Create Error Logging Hook

Create `src/hooks/useErrorLogger.ts`:

```typescript
"use client";
import { useEffect } from "react";

export interface ErrorLogEntry {
  timestamp: string;
  type: "error" | "unhandledrejection" | "component";
  message: string;
  stack?: string;
  filename?: string;
  line?: number;
  column?: number;
  componentStack?: string;
  componentName?: string; // Rev2: which panel caught this
}

const MAX_BUFFER_SIZE = 100; // Rev2: cap to prevent OOM
const errorBuffer: ErrorLogEntry[] = [];
let flushInterval: ReturnType<typeof setInterval> | null = null;
let isStarted = false; // Rev2: idempotent guard

function addToBuffer(entry: ErrorLogEntry) {
  // Rev2: cap buffer — drop oldest when full
  if (errorBuffer.length >= MAX_BUFFER_SIZE) {
    errorBuffer.shift();
  }
  errorBuffer.push(entry);
  console.error("[ERROR LOG]", entry);
}

function flushSync() {
  if (errorBuffer.length === 0) return;
  const batch = [...errorBuffer];
  errorBuffer.length = 0;
  // Rev2: use sendBeacon for unload-safe delivery
  if (typeof navigator !== "undefined" && navigator.sendBeacon) {
    const blob = new Blob([JSON.stringify({ errors: batch })], { type: "application/json" });
    navigator.sendBeacon("/api/errors/log", blob);
  }
}

export function startErrorLogging() {
  // Rev2: idempotent — prevent duplicate listeners/intervals
  if (isStarted) return () => {};
  isStarted = true;

  if (typeof window === "undefined") return () => {};

  const errorHandler = (event: ErrorEvent) => {
    // Rev2: skip errors already handled by ErrorBoundary
    if ((event.error as any)?._handled) return;
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

  // Rev2: flush on page unload
  const beforeUnloadHandler = () => flushSync();
  window.addEventListener("beforeunload", beforeUnloadHandler);

  // Flush every 5 seconds
  flushInterval = setInterval(async () => {
    if (errorBuffer.length === 0) return;
    const batch = [...errorBuffer];
    errorBuffer.length = 0;
    try {
      const res = await fetch("/api/errors/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ errors: batch }),
      });
      // Rev2: check response.ok — HTTP errors (404, 405, 422) silently drop errors
      if (!res.ok) {
        // Restore batch (capped)
        for (const e of batch.reverse()) {
          if (errorBuffer.length >= MAX_BUFFER_SIZE) break;
          errorBuffer.unshift(e);
        }
      }
    } catch (e) {
      // Network failure — restore batch (capped)
      for (const e of batch.reverse()) {
        if (errorBuffer.length >= MAX_BUFFER_SIZE) break;
        errorBuffer.unshift(e);
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
    flushSync(); // Rev2: flush on cleanup (SPA navigation)
  };
}

export function logComponentError(error: Error, componentStack?: string, componentName?: string) {
  // Rev2: mark error as handled to prevent window.onerror duplicate
  (error as any)._handled = true;
  addToBuffer({
    timestamp: new Date().toISOString(),
    type: "component",
    message: error.message,
    stack: error.stack,
    componentStack,
    componentName, // Rev2: which panel caught this
  });
}
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
  retryCount: number; // Rev2: prevent infinite retry loops
}

const MAX_RETRIES = 3; // Rev2: max retry attempts
const isDev = process.env.NODE_ENV === "development"; // Rev2: conditional stack traces

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, retryCount: 0 };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Rev2: pass componentName to log
    logComponentError(error, errorInfo.componentStack, this.props.componentName);
  }

  handleRetry = () => {
    // Rev2: increment retry count, disable after MAX_RETRIES
    this.setState((prev) => ({ hasError: false, error: null, retryCount: prev.retryCount + 1 }));
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const name = this.props.componentName || "Component";
      const retriesLeft = MAX_RETRIES - this.state.retryCount;

      return (
        <div
          style={{
            padding: "1rem",
            margin: "0.5rem",
            background: "#1a1a2e",
            border: "1px solid #ef4444",
            borderRadius: "4px",
            color: "#e0e0e0",
            fontFamily: "monospace",
            fontSize: "13px",
          }}
        >
          <div style={{ color: "#ef4444", fontWeight: "bold", marginBottom: "0.5rem" }}>
            {/* Rev2: fixed title — was "[X] Error]" with extra ] */}
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
            <button
              onClick={this.handleRetry}
              style={{
                marginTop: "0.5rem",
                padding: "0.25rem 0.75rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              Retry ({retriesLeft} left)
            </button>
          ) : (
            <div style={{ marginTop: "0.5rem", color: "#64748b", fontSize: "12px" }}>
              Retry disabled — fix the root cause
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

## Step 3: Create Next.js Error Boundaries (with logging)

Create `src/app/error.tsx`:

```tsx
"use client";
import { useEffect } from "react";
import { logComponentError } from "@/hooks/useErrorLogger";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Rev2: log page-level errors that escape panel boundaries
  useEffect(() => {
    logComponentError(error, undefined, "PageErrorBoundary");
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
import { useEffect } from "react";
import { logComponentError } from "@/hooks/useErrorLogger";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Rev2: log layout-level fatal errors
  useEffect(() => {
    logComponentError(error, undefined, "GlobalErrorBoundary");
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

  // Rev2: wrap shell components in ErrorBoundary too
  return (
    <div className="jarvis-shell" data-testid="jarvis-shell">
      <ErrorBoundary componentName="StatusBar"><StatusBar /></ErrorBoundary>
      <ErrorBoundary componentName="Sidebar"><Sidebar /></ErrorBoundary>
      <MainPane>{children}</MainPane>
      <ErrorBoundary componentName="RightPanel"><RightPanel /></ErrorBoundary>
      <ErrorBoundary componentName="BottomBar"><BottomBar /></ErrorBoundary>

      {/* Drawers at shell level */}
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

## Step 5: Create Backend Error Log Endpoint (with validation)

Add to `web/server.py`:

```python
from pathlib import Path
from pydantic import BaseModel
from typing import List
import json

# Rev2: absolute path derived from server file location
ERROR_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "frontend-errors.log"

class ErrorLogItem(BaseModel):
    """Rev2: validated error log entry."""
    timestamp: str
    type: str
    message: str
    stack: str | None = None
    filename: str | None = None
    line: int | None = None
    column: int | None = None
    componentStack: str | None = None
    componentName: str | None = None

class ErrorLogRequest(BaseModel):
    """Rev2: validated request body."""
    errors: List[ErrorLogItem]

@app.post("/api/errors/log")
async def log_frontend_errors(request: ErrorLogRequest):
    """Receive frontend error logs and append to local file."""
    ERROR_LOG_FILE.parent.mkdir(exist_ok=True)
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        for error in request.errors:
            f.write(json.dumps(error.model_dump(), default=str) + "\n")
    return {"status": "ok", "received": len(request.errors)}

@app.get("/api/errors/log")
async def get_frontend_errors():
    """Retrieve frontend error log for upload to GLM."""
    if not ERROR_LOG_FILE.exists():
        return {"errors": [], "count": 0}
    lines = ERROR_LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    errors = []
    for line in lines:
        if line.strip():
            try:
                errors.append(json.loads(line))
            except:
                pass
    return {"errors": errors, "count": len(errors)}

@app.delete("/api/errors/log")
async def clear_frontend_errors():
    """Clear frontend error log after upload."""
    if ERROR_LOG_FILE.exists():
        ERROR_LOG_FILE.unlink()
    return {"status": "cleared"}
```

---

## Step 6: Build (separate steps — Rev2 fix)

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

Upload this to GLM for diagnosis.

Clear after:
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
