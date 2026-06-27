# Web GUI Fixes 1 — Error Tracking + Error Boundaries + Root Cause Fixes

**Not a plan** — this is a direct Devin execution prompt. No jarvis-open/jarvis-close, no tag, no CHANGELOG. Just fix the GUI.

---

## Objective

The web GUI has thousands of errors when loading. The root cause is likely 1-2 cascading failures hidden by the lack of error boundaries. This prompt does 3 things:

1. **Add error tracking** — log all frontend errors to a local file you can upload to GLM
2. **Add error boundaries** — catch errors per-component instead of crashing the whole page
3. **Fix root causes** — once errors are visible, fix the actual problems

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
}

// In-memory buffer (flushed to API on interval)
const errorBuffer: ErrorLogEntry[] = [];
let flushInterval: ReturnType<typeof setInterval> | null = null;

export function startErrorLogging() {
  if (typeof window === "undefined") return;

  // Catch uncaught errors
  const errorHandler = (event: ErrorEvent) => {
    const entry: ErrorLogEntry = {
      timestamp: new Date().toISOString(),
      type: "error",
      message: event.message,
      filename: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error?.stack,
    };
    errorBuffer.push(entry);
    console.error("[ERROR LOG]", entry);
  };

  // Catch unhandled promise rejections
  const rejectionHandler = (event: PromiseRejectionEvent) => {
    const entry: ErrorLogEntry = {
      timestamp: new Date().toISOString(),
      type: "unhandledrejection",
      message: String(event.reason?.message || event.reason),
      stack: event.reason?.stack,
    };
    errorBuffer.push(entry);
    console.error("[ERROR LOG]", entry);
  };

  window.addEventListener("error", errorHandler);
  window.addEventListener("unhandledrejection", rejectionHandler);

  // Flush errors to API every 5 seconds
  flushInterval = setInterval(async () => {
    if (errorBuffer.length === 0) return;
    const batch = [...errorBuffer];
    errorBuffer.length = 0; // Clear buffer
    try {
      await fetch("/api/errors/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ errors: batch }),
      });
    } catch (e) {
      // If API fails, put errors back in buffer
      errorBuffer.unshift(...batch);
    }
  }, 5000);

  return () => {
    window.removeEventListener("error", errorHandler);
    window.removeEventListener("unhandledrejection", rejectionHandler);
    if (flushInterval) clearInterval(flushInterval);
  };
}

export function logComponentError(error: Error, componentStack?: string) {
  const entry: ErrorLogEntry = {
    timestamp: new Date().toISOString(),
    type: "component",
    message: error.message,
    stack: error.stack,
    componentStack,
  };
  errorBuffer.push(entry);
  console.error("[ERROR LOG]", entry);
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
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logComponentError(error, errorInfo.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

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
            {this.props.componentName ? `[${this.props.componentName}]` : "[Component"} Error]
          </div>
          <div style={{ color: "#94a3b8", marginBottom: "0.5rem" }}>{this.state.error?.message}</div>
          <details style={{ color: "#64748b" }}>
            <summary style={{ cursor: "pointer", color: "#94a3b8" }}>Stack trace</summary>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "11px", marginTop: "0.5rem" }}>
              {this.state.error?.stack}
            </pre>
          </details>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
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
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

---

## Step 3: Create Next.js Error Boundaries

Create `src/app/error.tsx`:

```tsx
"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      style={{
        padding: "2rem",
        background: "#0c0c0f",
        color: "#e0e0e0",
        minHeight: "100vh",
        fontFamily: "monospace",
      }}
    >
      <h2 style={{ color: "#ef4444", marginBottom: "1rem" }}>Page Error</h2>
      <pre
        style={{
          whiteSpace: "pre-wrap",
          fontSize: "13px",
          color: "#94a3b8",
          background: "#1a1a2e",
          padding: "1rem",
          borderRadius: "4px",
          border: "1px solid #2a2a3e",
        }}
      >
        {error.message}
        {"\n\n"}
        {error.stack}
      </pre>
      <button
        onClick={reset}
        style={{
          marginTop: "1rem",
          padding: "0.5rem 1rem",
          background: "#3b82f6",
          color: "white",
          border: "none",
          borderRadius: "4px",
          cursor: "pointer",
        }}
      >
        Try Again
      </button>
    </div>
  );
}
```

Create `src/app/global-error.tsx`:

```tsx
"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body
        style={{
          padding: "2rem",
          background: "#0c0c0f",
          color: "#e0e0e0",
          fontFamily: "monospace",
        }}
      >
        <h2 style={{ color: "#ef4444" }}>Fatal Error — Layout Crashed</h2>
        <pre
          style={{
            whiteSpace: "pre-wrap",
            fontSize: "13px",
            color: "#94a3b8",
          }}
        >
          {error.message}
          {"\n\n"}
          {error.stack}
        </pre>
        <button
          onClick={reset}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            background: "#3b82f6",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Try Again
        </button>
      </body>
    </html>
  );
}
```

---

## Step 4: Wrap Every Panel in ErrorBoundary

Update `src/app/page.tsx` — wrap each panel in `<ErrorBoundary>` with `componentName`:

```tsx
"use client";
import { ErrorBoundary } from "@/components/ErrorBoundary";
// ... existing imports ...

export default function Home() {
  // ... existing hooks ...

  switch (activeView) {
    case VIEWS.HOME:
      return <ErrorBoundary componentName="TerminalPanel"><TerminalPlaceholder /></ErrorBoundary>;
    case VIEWS.TASKS:
      return <ErrorBoundary componentName="TasksPanel"><TasksPanel /></ErrorBoundary>;
    case VIEWS.WORKERS:
      return <ErrorBoundary componentName="WorkersPanel"><WorkersPanel /></ErrorBoundary>;
    case VIEWS.APPROVALS:
      return <ErrorBoundary componentName="ApprovalQueuePanel"><ApprovalQueuePanel /></ErrorBoundary>;
    case VIEWS.COSTS:
      return <ErrorBoundary componentName="CostDashboardPanel"><CostDashboardPanel /></ErrorBoundary>;
    case VIEWS.TOOLS:
      return <ErrorBoundary componentName="SkillsPanel"><SkillsPanel /></ErrorBoundary>;
    case VIEWS.HELP:
      return <ErrorBoundary componentName="HelpPanel"><HelpPanel /></ErrorBoundary>;
    case VIEWS.TERMINAL:
      return <ErrorBoundary componentName="TerminalPanel"><TerminalPanel /></ErrorBoundary>;
    case VIEWS.SYSTEM:
      return <ErrorBoundary componentName="SystemStatsPanel"><SystemStatsPanel /></ErrorBoundary>;
    case VIEWS.SUBAGENTS:
      return <ErrorBoundary componentName="SubagentPanel"><SubagentPanel /></ErrorBoundary>;
    case VIEWS.MODELS:
      return <ErrorBoundary componentName="ModelsPanel"><ModelsPanel /></ErrorBoundary>;
    case VIEWS.RESOURCES:
      return <ErrorBoundary componentName="ResourceMonitorPanel"><ResourceMonitorPanel /></ErrorBoundary>;
    default:
      return <ErrorBoundary componentName="TerminalPanel"><TerminalPlaceholder /></ErrorBoundary>;
  }
}
```

---

## Step 5: Start Error Logging in ShellClient

Update `src/components/shell/ShellClient.tsx` — add error logging on mount:

```tsx
"use client";
import { useEffect } from "react";
import { startErrorLogging } from "@/hooks/useErrorLogger";
// ... existing imports ...

export function ShellClient({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const cleanup = startErrorLogging();
    return cleanup;
  }, []);

  // ... rest of existing code ...
}
```

---

## Step 6: Create Backend Error Log Endpoint

Add to `web/server.py`:

```python
import json
from datetime import datetime
from pathlib import Path

ERROR_LOG_FILE = Path("logs/frontend-errors.log")

@app.post("/api/errors/log")
async def log_frontend_errors(data: dict):
    """Receive frontend error logs and append to local file."""
    ERROR_LOG_FILE.parent.mkdir(exist_ok=True)
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        for error in data.get("errors", []):
            f.write(json.dumps(error, default=str) + "\n")
    return {"status": "ok", "received": len(data.get("errors", []))}
```

Also add an endpoint to retrieve the log:

```python
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

## Step 7: Build and Test

```bash
cd src && npx tsc --noEmit
cd src && npm run build
cd src && npm run dev
```

Open the browser to `http://localhost:3000`.

**What you should see:**
- If a component has an error: a red-bordered box with the component name, error message, and stack trace
- If the layout crashes: a full-page error with a "Try Again" button
- Errors are logged to `logs/frontend-errors.log` on the backend

---

## Step 8: Collect Error Log

After navigating through all panels (click each sidebar item), collect the error log:

```bash
cat logs/frontend-errors.log
```

OR via API:
```bash
curl http://localhost:8000/api/errors/log
```

This log is what you upload to GLM for diagnosis.

After collecting, clear the log:
```bash
curl -X DELETE http://localhost:8000/api/errors/log
```

---

## Step 9: Fix Root Causes

Read the error log. You'll see patterns like:
- `Cannot read property 'map' of undefined` → a store is returning undefined instead of an array
- `X is not a function` → a component is importing a function that doesn't exist or has a different name
- `Network request failed` → API endpoint not running or wrong URL
- `Hydration mismatch` → server/client rendering difference

Fix the ROOT CAUSE of each unique error (not each instance). One fix may resolve dozens of errors.

**Do NOT fix errors by adding try/catch or null checks around the symptom.** Fix the actual cause — the wrong store shape, the missing export, the broken API call.

---

## Step 10: Verify

After fixing root causes:
```bash
cd src && npx tsc --noEmit && npm run build
cd src && npm run dev
```

Open browser. Navigate through every panel. Check:
- No red error boxes
- No console errors (F12 → Console)
- All panels render content (not blank)
- Sidebar navigation works
- StatusBar shows model name
- Drawers (Memory, Settings) open/close

Clear error log and collect again:
```bash
curl -X DELETE http://localhost:8000/api/errors/log
# Navigate through all panels
curl http://localhost:8000/api/errors/log
```

If error count is 0 or near-0, the GUI is stable.

---

## Files to Create
- `src/hooks/useErrorLogger.ts`
- `src/components/ErrorBoundary.tsx`
- `src/app/error.tsx`
- `src/app/global-error.tsx`

## Files to Edit
- `src/app/page.tsx` (wrap panels in ErrorBoundary)
- `src/components/shell/ShellClient.tsx` (start error logging)
- `web/server.py` (add error log endpoints)

## No jarvis-open, No jarvis-close, No tag, No CHANGELOG

This is a direct fix. Commit when done:
```bash
git add -A
git commit -m "fix: add error tracking + error boundaries to web GUI"
git push origin master
```
