# Plan 86 — Terminal xterm.js + System Panels + Subagent UI

**Tag**: `prompt-86` | **Depends on**: `prompt-85`

### Scope

Replace the TerminalPlaceholder (Plan 83) with a real xterm.js terminal backed by a WebSocket PTY endpoint. Add SystemStats panel (CPU/memory/GPU/uptime) and SubagentPanel (view/kill running subagents). Add `useWebSocket` hook (separate from `useSSE` — PTY is bidirectional). Extend `subagentStore` with incremental upsert and status transitions. Add `/ws/pty` WebSocket endpoint to `web/server.py`.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-85` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S1. Add xterm.js dependencies to `src/package.json`

Add to dependencies:
```json
{
  "@xterm/xterm": "^5.5.0",
  "@xterm/addon-fit": "^0.10.0",
  "@xterm/addon-web-links": "^0.11.0"
}
```

Run `cd src && npm install`.

### S2. Create `src/hooks/useWebSocket.ts`

Bidirectional WebSocket hook (distinct from `useSSE` which is one-way server→client):

```typescript
"use client";
import { useEffect, useRef, useState, useCallback } from "react";

interface UseWebSocketOptions {
  onMessage?: (data: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (err: Event) => void;
  enabled?: boolean;
  maxRetries?: number;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const { enabled = true, maxRetries = 10 } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Rev2 H3 fix — store callbacks in refs to avoid reconnect storms.
  // Inline arrow functions passed as onMessage/onOpen/etc would otherwise
  // change identity on every render, causing the useEffect to clean up
  // and reconnect the WebSocket on every render. Refs stabilize identity.
  const onMessageRef = useRef(options.onMessage);
  const onOpenRef = useRef(options.onOpen);
  const onCloseRef = useRef(options.onClose);
  const onErrorRef = useRef(options.onError);

  useEffect(() => {
    onMessageRef.current = options.onMessage;
    onOpenRef.current = options.onOpen;
    onCloseRef.current = options.onClose;
    onErrorRef.current = options.onError;
  }); // Update refs every render, but don't trigger WebSocket reconnect

  const send = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const connect = () => {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        retryCountRef.current = 0;
        onOpenRef.current?.();
      };

      ws.onmessage = (event) => {
        onMessageRef.current?.(event.data);
      };

      ws.onerror = (event) => {
        setError(new Error("WebSocket error"));
        onErrorRef.current?.(event);
      };

      ws.onclose = () => {
        setIsConnected(false);
        onCloseRef.current?.();
        if (retryCountRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
          retryCountRef.current++;
          reconnectTimerRef.current = setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [url, enabled, maxRetries]); // Rev2 H3 fix — callbacks omitted from deps (stored in refs)

  return { isConnected, error, send };
}
```

### S3. Create `src/components/panels/TerminalPanel.tsx` (replaces TerminalPlaceholder)

Real xterm.js terminal backed by WebSocket PTY:

```tsx
"use client";
import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { useWebSocket } from "@/hooks/useWebSocket";
import { sseUrl } from "@/lib/api";
import "@xterm/xterm/css/xterm.css";

export function TerminalPanel() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);

  // PTY WebSocket URL — uses absolute BACKEND_URL (WebSocket cannot be proxied through Next.js rewrites)
  const wsUrl = sseUrl("/ws/pty").replace("http", "ws");

  const { send, isConnected } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      termRef.current?.write(data);
    },
  });

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "monospace",
      theme: { background: "#0c0c0f", foreground: "#e0e0e0" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon());
    term.open(containerRef.current);
    fit.fit();

    termRef.current = term;
    fitRef.current = fit;

    term.onData((data) => {
      send(data);
    });

    const handleResize = () => fit.fit();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      term.dispose();
    };
  }, [send]);

  return (
    <div data-testid="terminal-panel" data-terminal className="h-full p-2">
      <div className="text-xs text-slate-500 mb-1">
        Terminal {isConnected ? "● connected" : "○ disconnected"}
      </div>
      <div ref={containerRef} className="h-[calc(100%-24px)]" />
    </div>
  );
}
```

### S4. Add `/ws/pty` WebSocket endpoint to `web/server.py`

**Rev2 H1+H2 fix**: The original PTY implementation had two critical issues:
1. **H1**: `select.select()` and `os.read()` are blocking syscalls called inside an async def — this freezes Uvicorn's event loop, causing all concurrent requests to time out.
2. **H2**: `import pty` is unconditional — `pty` is Unix-only, so on Windows the endpoint crashes at import time with `ModuleNotFoundError`.

The fix:
- Move all blocking syscalls to `asyncio.get_event_loop().run_in_executor(None, ...)` so they run in a thread pool, not the event loop.
- Move `pty` import inside a platform guard (`if sys.platform != "win32"`).
- On Windows, either use `pywinpty` (if installed) or return a clean 501 error.
- Use separate async reader/writer tasks with proper cancellation on disconnect.

```python
# In web/server.py create_app():
import sys
import asyncio
import logging

logger = logging.getLogger(__name__)

@app.websocket("/ws/pty")
async def pty_websocket(websocket: WebSocket):
    """WebSocket PTY endpoint for terminal access.

    Auth: token query param (same as existing /ws endpoint).
    Spawns a pseudo-terminal, streams output, receives input.

    Rev2 H1 fix: All blocking syscalls (select, os.read, os.write) run in
    executor to avoid freezing the asyncio event loop.
    Rev2 H2 fix: Platform-specific imports inside guards. Windows uses
    pywinpty if available, otherwise returns 501.
    """
    token = websocket.query_params.get("token")
    if not token or not auth_manager.validate_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Rev2 H2 fix — platform-specific imports inside guard
    if sys.platform == "win32":
        try:
            import winpty  # type: ignore
        except ImportError:
            logger.warning("pywinpty not installed — PTY endpoint unavailable on Windows")
            await websocket.close(code=4002, reason="PTY unavailable on Windows (pywinpty not installed)")
            return
        # Windows implementation using winpty (similar pattern, different API)
        await _windows_pty_websocket(websocket, winpty)
        return

    # Unix implementation
    try:
        import pty
        import os
        import select
        import signal
    except ImportError:
        await websocket.close(code=4003, reason="PTY unavailable on this platform")
        return

    await websocket.accept()

    loop = asyncio.get_event_loop()
    master, slave = pty.openpty()
    pid = os.fork()

    if pid == 0:
        # Child process — becomes the shell
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(master)
        os.close(slave)
        os.execvp("bash", ["bash"])
    else:
        # Parent process — relay I/O via executor (Rev2 H1 fix)
        os.close(slave)

        async def read_pty_output():
            """Read from PTY master, send to WebSocket. Runs blocking read in executor."""
            try:
                while True:
                    # Rev2 H1 fix — run blocking select in executor
                    readable, _, _ = await loop.run_in_executor(
                        None, lambda: select.select([master], [], [], 0.1)
                    )
                    if master in readable:
                        # Rev2 H1 fix — run blocking os.read in executor
                        data = await loop.run_in_executor(
                            None, lambda: os.read(master, 4096)
                        )
                        if not data:
                            break  # PTY closed
                        await websocket.send_text(data.decode("utf-8", errors="replace"))
            except Exception as e:
                logger.warning(f"PTY read error: {e}")

        async def read_websocket_input():
            """Read from WebSocket, write to PTY master."""
            try:
                while True:
                    message = await websocket.receive_text()
                    # Rev2 H1 fix — run blocking os.write in executor
                    await loop.run_in_executor(
                        None, lambda: os.write(master, message.encode())
                    )
            except Exception as e:
                logger.warning(f"WebSocket read error: {e}")

        try:
            # Run reader and writer concurrently, cancel both when either finishes
            reader_task = asyncio.create_task(read_pty_output())
            writer_task = asyncio.create_task(read_websocket_input())

            done, pending = await asyncio.wait(
                [reader_task, writer_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        finally:
            os.close(master)
            try:
                os.kill(pid, signal.SIGTERM)
                await asyncio.sleep(0.1)  # Give process time to exit
                os.kill(pid, signal.SIGKILL)  # Force kill if still alive
            except ProcessLookupError:
                pass  # Already dead
            os.waitpid(pid, 0)


async def _windows_pty_websocket(websocket, winpty_module):
    """Windows PTY implementation using pywinpty. Separate function for clarity."""
    await websocket.accept()
    loop = asyncio.get_event_loop()

    # Create winpty PTY process
    pty_proc = winpty_module.PTY()
    pty_proc.spawn("cmd.exe")  # or powershell.exe

    async def read_pty_output():
        try:
            while True:
                # winpty read is blocking — run in executor
                data = await loop.run_in_executor(
                    None, lambda: pty_proc.read(4096)
                )
                if data:
                    await websocket.send_text(data)
        except Exception as e:
            logger.warning(f"Windows PTY read error: {e}")

    async def read_websocket_input():
        try:
            while True:
                message = await websocket.receive_text()
                # winpty write is blocking — run in executor
                await loop.run_in_executor(
                    None, lambda: pty_proc.write(message)
                )
        except Exception as e:
            logger.warning(f"Windows WebSocket read error: {e}")

    try:
        reader_task = asyncio.create_task(read_pty_output())
        writer_task = asyncio.create_task(read_websocket_input())

        done, pending = await asyncio.wait(
            [reader_task, writer_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        pty_proc.close()
```

### S5. Create `src/components/panels/SystemStatsPanel.tsx`

System statistics panel showing CPU, memory, GPU, uptime, active workers. Polls `GET /api/system` (already exists from Plan 81).

```tsx
"use client";
import { usePolling } from "@/hooks/usePolling";
import { getSystemStats, SystemStats } from "@/lib/api";

export function SystemStatsPanel() {
  const { data, isLoading } = usePolling<SystemStats>(getSystemStats, 5000);

  if (isLoading || !data) {
    return <div data-testid="system-stats-panel" className="p-4">Loading...</div>;
  }

  return (
    <div data-testid="system-stats-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">System Stats</h2>

      <div className="space-y-2">
        <StatBar label="CPU" value={data.cpu_percent} unit="%" max={100} />
        <StatBar label="Memory" value={data.memory_percent} unit="%" max={100} />
        {data.gpu_percent !== undefined && (
          <StatBar label="GPU" value={data.gpu_percent} unit="%" max={100} />
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-slate-500">Uptime:</span>{" "}
          {Math.floor(data.uptime_seconds / 3600)}h {Math.floor((data.uptime_seconds % 3600) / 60)}m
        </div>
        <div>
          <span className="text-slate-500">Active Workers:</span> {data.active_workers}
        </div>
      </div>
    </div>
  );
}

function StatBar({ label, value, unit, max }: { label: string; value: number; unit: string; max: number }) {
  const pct = (value / max) * 100;
  const color = pct > 80 ? "bg-red-500" : pct > 60 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span>{value.toFixed(1)}{unit}</span>
      </div>
      <div className="h-2 bg-slate-800 rounded">
        <div className={`h-full rounded ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
```

### S6. Extend `src/stores/subagentStore.ts`

Add incremental upsert, status transitions, and spawn/terminate methods:

```typescript
import { create } from "zustand";

export interface Subagent {
  id: string;
  task: string;
  status: "running" | "waiting" | "complete" | "failed";
  tokenCost: number;
  startedAt?: string;
  completedAt?: string;
  error?: string;
}

interface SubagentState {
  subagents: Subagent[];
  setSubagents: (subagents: Subagent[]) => void;
  addSubagent: (subagent: Subagent) => void;
  updateStatus: (id: string, status: Subagent["status"], error?: string) => void;
  updateTokenCost: (id: string, cost: number) => void;
  killSubagent: (id: string) => Promise<void>;  // Rev2 L1 fix — async (calls backend)
  clearCompleted: () => void;
}

export const useSubagentStore = create<SubagentState>((set) => ({
  subagents: [],
  setSubagents: (subagents) => set({ subagents }),
  addSubagent: (subagent) =>
    set((s) => ({ subagents: [...s.subagents, subagent] })),
  updateStatus: (id, status, error) =>
    set((s) => ({
      subagents: s.subagents.map((sa) =>
        sa.id === id
          ? {
              ...sa,
              status,
              error,
              completedAt: status === "complete" || status === "failed" ? new Date().toISOString() : sa.completedAt,
            }
          : sa
      ),
    })),
  updateTokenCost: (id, cost) =>
    set((s) => ({
      subagents: s.subagents.map((sa) =>
        sa.id === id ? { ...sa, tokenCost: cost } : sa
      ),
    })),
  killSubagent: async (id: string) => {
    // Rev2 L1 fix — call backend to terminate subagent before removing from store.
    // The original code only removed the subagent from local state, leaving it
    // running on the backend (consuming tokens and VRAM).
    try {
      await fetch(`/api/subagents/${id}`, { method: 'DELETE' });
    } catch (err) {
      console.error(`Failed to kill subagent ${id}:`, err);
      // Still remove from store even if backend call fails — user intent is clear
    }
    set((s) => ({ subagents: s.subagents.filter((sa) => sa.id !== id) }));
  },
  clearCompleted: () =>
    set((s) => ({
      subagents: s.subagents.filter(
        (sa) => sa.status !== "complete" && sa.status !== "failed"
      ),
    })),
}));
```

### S7. Create `src/components/panels/SubagentPanel.tsx`

```tsx
"use client";
import { useSubagentStore } from "@/stores/subagentStore";
import { STATUS_BADGES } from "@/lib/statusUtils";

export function SubagentPanel() {
  const { subagents, killSubagent, clearCompleted } = useSubagentStore();

  const running = subagents.filter((s) => s.status === "running");
  const waiting = subagents.filter((s) => s.status === "waiting");
  const done = subagents.filter((s) => s.status === "complete" || s.status === "failed");

  return (
    <div data-testid="subagent-panel" className="p-4 space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Subagents</h2>
        {done.length > 0 && (
          <button onClick={clearCompleted} className="text-sm text-slate-400 hover:text-slate-200">
            Clear completed
          </button>
        )}
      </div>

      {subagents.length === 0 && (
        <p className="text-slate-500 text-sm">No subagents running.</p>
      )}

      {running.length > 0 && (
        <Section title="Running" count={running.length}>
          {running.map((sa) => (
            <SubagentCard key={sa.id} subagent={sa} onKill={() => killSubagent(sa.id)} />
          ))}
        </Section>
      )}

      {waiting.length > 0 && (
        <Section title="Waiting" count={waiting.length}>
          {waiting.map((sa) => (
            <SubagentCard key={sa.id} subagent={sa} onKill={() => killSubagent(sa.id)} />
          ))}
        </Section>
      )}

      {done.length > 0 && (
        <Section title="Completed" count={done.length}>
          {done.map((sa) => (
            <SubagentCard key={sa.id} subagent={sa} />
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-slate-400 mb-2">{title} ({count})</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function SubagentCard({ subagent, onKill }: { subagent: import("@/stores/subagentStore").Subagent; onKill?: () => void }) {
  const badge = STATUS_BADGES[subagent.status];
  return (
    <div className="border border-slate-700 rounded p-3 bg-slate-900">
      <div className="flex justify-between items-start">
        <div>
          <span className="font-mono text-sm">{subagent.id}</span>
          <span className={`ml-2 text-xs px-2 py-0.5 rounded ${badge.class}`}>{badge.label}</span>
        </div>
        {onKill && subagent.status === "running" && (
          <button onClick={onKill} className="text-xs text-red-400 hover:text-red-300">Kill</button>
        )}
      </div>
      <p className="text-sm text-slate-300 mt-1">{subagent.task}</p>
      <div className="text-xs text-slate-500 mt-1">
        Tokens: {subagent.tokenCost}
        {subagent.error && <span className="text-red-400 ml-2">Error: {subagent.error}</span>}
      </div>
    </div>
  );
}
```

### S8. Update `src/stores/uiStore.ts` — add new views

Add to VIEWS enum:
```typescript
export const VIEWS = {
  HOME: "home",
  TASKS: "tasks",
  WORKERS: "workers",
  APPROVALS: "approvals",
  COSTS: "costs",
  TOOLS: "tools",
  HELP: "help",
  TERMINAL: "terminal",    // NEW
  SYSTEM: "system",        // NEW
  SUBAGENTS: "subagents",  // NEW
} as const;
```

### S9. Update `src/components/shell/Sidebar.tsx`

Add 3 new nav items: Terminal (icon: Terminal), System (icon: Activity), Subagents (icon: Users). Total: 10 nav items + 2 drawer buttons.

### S10. Update `src/app/page.tsx` — add view routing

Add to the switch statement:
```tsx
case VIEWS.TERMINAL:
  return <TerminalPanel />;
case VIEWS.SYSTEM:
  return <SystemStatsPanel />;
case VIEWS.SUBAGENTS:
  return <SubagentPanel />;
```

Delete `src/components/panels/TerminalPlaceholder.tsx` (replaced by TerminalPanel).

### S11. Verify build

```powershell
cd src && npx tsc --noEmit && npm run build
```

### STOP condition

If `npx tsc --noEmit` reports errors, STOP and fix. If `npm run build` fails, STOP and fix.

### Files WILL create (5)
- `src/hooks/useWebSocket.ts`
- `src/components/panels/TerminalPanel.tsx`
- `src/components/panels/SystemStatsPanel.tsx`
- `src/components/panels/SubagentPanel.tsx`
- `src/lib/statusUtils.ts` (badge color mapping)

### Files WILL edit (5)
- `src/package.json` (add @xterm/xterm, @xterm/addon-fit, @xterm/addon-web-links)
- `src/stores/subagentStore.ts` (extend with addSubagent, updateStatus, updateTokenCost, clearCompleted; killSubagent is now async — Rev2 L1 fix)
- `src/stores/uiStore.ts` (add TERMINAL, SYSTEM, SUBAGENTS views)
- `src/components/shell/Sidebar.tsx` (add 3 nav items)
- `src/app/page.tsx` (add view routing for 3 new panels)
- `web/server.py` (add /ws/pty WebSocket PTY endpoint; add DELETE /api/subagents/{id} endpoint — Rev2 L1 fix)

### Files WILL delete (1)
- `src/components/panels/TerminalPlaceholder.tsx`

### Files will NOT edit
- `core/` (no backend logic changes)
- `system/`
- `adapters/`
- `workers/`
- `memory/`
- `skills/`

### Closing

Run `/jarvis-close`. Tag `prompt-86`. CHANGELOG entry for Plan 86. Update PLANS.md.

---
