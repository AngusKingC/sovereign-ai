# Plan 99 — Observability & Trace Viewer (Phase 5b)

**Tag**: `prompt-99` | **Depends on**: `prompt-98`

---

## Scope

Expose the trace store and session manager via Web UI. Backend: trace query endpoint, session CRUD endpoints. Frontend: Trace Viewer panel (search, filter, visualize), Session Manager panel (create, switch, rename, delete).

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §2.8 (Observability gaps), §2.9 (Session management), §6 Phase 5

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-98` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

S0.4. **Post-Plan 95 scan state** (verified clean):
- `test_list_workers` is FIXED (no longer skipped). AsyncMock return_value corrected in Plan 95.
- Governance files are updated: jarvis-close has C9 (concrete templates) + C16 (Git Bash cleanup), AI_HANDOFF says "Git Bash on Windows", jarvis-open uses `test -f`.
- `.txt` files moved to `txt/` folder during Plan 95 scan. Use `txt/requirements.txt` not `requirements.txt`.
- Vitest: 7 tests skipped (WorkerCreator, WorkerEditor, ModelsPanel not yet implemented).
- Playwright E2E deferred (web server startup issue — not blocking).

S0.5. **Pre-verification** (mandatory before coding):
- Read `core/observability.py` — confirm `TraceEmitter` API: `get_events(limit)`, `emit()`. Check if events have `component`, `event_type`, `level`, `message`, `metadata` attributes.
- Read `core/session.py` — confirm `SessionManager` API: `create_session()`, `get_history()`, `query_sessions()`, `summarize()`, `archive_expired_sessions()`.
- Verify `orchestrator._emitter` and `orchestrator.session_manager` exist. If either is missing, endpoints return 503 (expected — not a STOP).

---

## S1. Add trace query API endpoint

Create `api/traces.py`:

```python
"""API router for trace event querying."""
from fastapi import APIRouter, HTTPException, Query
from typing import Any

router = APIRouter(prefix="/api/traces", tags=["traces"])

@router.get("")
async def query_traces(
    component: str | None = None,
    event_type: str | None = None,
    level: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> dict[str, Any]:
    """Query trace events with filters."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, '_emitter') or not orchestrator._emitter:
        raise HTTPException(status_code=503, detail="Trace emitter not configured")

    # Get events from emitter's in-memory buffer
    events = orchestrator._emitter.get_events(limit=limit + offset)

    # Apply filters
    filtered = events
    if component:
        filtered = [e for e in filtered if getattr(e, 'component', '') == component]
    if event_type:
        filtered = [e for e in filtered if getattr(e, 'event_type', '') == event_type]
    if level:
        filtered = [e for e in filtered if getattr(e, 'level', '') == level]

    # Paginate
    paginated = filtered[offset:offset + limit]

    return {
        "events": [
            {
                "event_id": getattr(e, 'event_id', ''),
                "timestamp": getattr(e, 'timestamp', '').isoformat() if hasattr(getattr(e, 'timestamp', ''), 'isoformat') else str(getattr(e, 'timestamp', '')),
                "component": getattr(e, 'component', ''),
                "event_type": getattr(e, 'event_type', ''),
                "level": getattr(e, 'level', ''),
                "message": getattr(e, 'message', ''),
                "metadata": getattr(e, 'metadata', {}),
            }
            for e in paginated
        ],
        "total": len(filtered),
        "limit": limit,
        "offset": offset,
    }

@router.get("/components")
async def list_components() -> dict[str, Any]:
    """List all trace components for filter dropdown."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, '_emitter') or not orchestrator._emitter:
        return {"components": []}

    events = orchestrator._emitter.get_events(limit=1000)
    components = list(set(getattr(e, 'component', '') for e in events if getattr(e, 'component', '')))
    return {"components": sorted(components)}
```

Wire into `web/server.py`:
```python
from api.traces import router as traces_router
app.include_router(traces_router)
```

---

## S2. Add session API endpoints

Create `api/sessions.py`:

```python
"""API router for session management."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.get("")
async def list_sessions() -> dict[str, Any]:
    """List all sessions."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'session_manager') or not orchestrator.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not configured")

    sessions = await orchestrator.session_manager.query_sessions()
    return {"sessions": [{"session_id": s.session_id, "created": str(s.created), "summary": s.summary} for s in sessions]}

@router.post("")
async def create_session() -> dict[str, Any]:
    """Create a new session."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'session_manager') or not orchestrator.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not configured")

    session_id = await orchestrator.session_manager.create_session()
    return {"session_id": session_id, "status": "created"}

@router.get("/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get session details and history."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'session_manager') or not orchestrator.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not configured")

    history = await orchestrator.session_manager.get_history(session_id)
    return {
        "session_id": session_id,
        "messages": [
            {"role": m.role, "content": m.content[:500]}  # Truncate for UI
            for m in history
        ],
        "message_count": len(history),
    }

class SessionUpdateRequest(BaseModel):
    summary: str | None = None

@router.put("/{session_id}")
async def update_session(session_id: str, request: SessionUpdateRequest) -> dict[str, Any]:
    """Update session (rename/summary)."""
    # SessionManager may not support direct rename — use summary
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'session_manager') or not orchestrator.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not configured")

    if request.summary:
        await orchestrator.session_manager.summarize(session_id)
    return {"session_id": session_id, "status": "updated"}

@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """Archive/delete a session."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'session_manager') or not orchestrator.session_manager:
        raise HTTPException(status_code=503, detail="Session manager not configured")

    await orchestrator.session_manager.archive_expired_sessions()
    return {"session_id": session_id, "status": "archived"}
```

Wire into `web/server.py`:
```python
from api.sessions import router as sessions_router
app.include_router(sessions_router)
```

---

## S3. Add API functions to `src/lib/api.ts`

```typescript
export interface TraceEvent {
  event_id: string;
  timestamp: string;
  component: string;
  event_type: string;
  level: string;
  message: string;
  metadata: Record<string, unknown>;
}

export interface SessionInfo {
  session_id: string;
  created: string;
  summary: string;
}

export async function queryTraces(filters?: { component?: string; event_type?: string; level?: string; limit?: number }): Promise<{ events: TraceEvent[]; total: number }> {
  const params = new URLSearchParams();
  if (filters?.component) params.set("component", filters.component);
  if (filters?.event_type) params.set("event_type", filters.event_type);
  if (filters?.level) params.set("level", filters.level);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const res = await fetch(`/api/traces?${params}`);
  if (!res.ok) throw new Error(`Traces ${res.status}`);
  return res.json();
}

export async function getTraceComponents(): Promise<{ components: string[] }> {
  const res = await fetch(`/api/traces/components`);
  if (!res.ok) throw new Error(`Components ${res.status}`);
  return res.json();
}

export async function getSessions(): Promise<{ sessions: SessionInfo[] }> {
  const res = await fetch(`/api/sessions`);
  if (!res.ok) throw new Error(`Sessions ${res.status}`);
  return res.json();
}

export async function createSession(): Promise<{ session_id: string }> {
  const res = await fetch(`/api/sessions`, { method: "POST" });
  if (!res.ok) throw new Error(`Create session ${res.status}`);
  return res.json();
}

export async function getSession(sessionId: string): Promise<any> {
  const res = await fetch(`/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Session ${res.status}`);
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<any> {
  const res = await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete session ${res.status}`);
  return res.json();
}
```

---

## S4. Create `src/components/panels/TraceViewerPanel.tsx`

```tsx
"use client";
import { useState, useEffect } from "react";
import { queryTraces, getTraceComponents, TraceEvent } from "@/lib/api";

export function TraceViewerPanel() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [components, setComponents] = useState<string[]>([]);
  const [filterComponent, setFilterComponent] = useState("");
  const [filterLevel, setFilterLevel] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadTraces = async () => {
    setIsLoading(true);
    try {
      const result = await queryTraces({
        component: filterComponent || undefined,
        level: filterLevel || undefined,
        limit: 100,
      });
      setEvents(result.events);
    } catch { } finally { setIsLoading(false); }
  };

  useEffect(() => { getTraceComponents().then(r => setComponents(r.components)).catch(() => {}); }, []);
  useEffect(() => { loadTraces(); }, [filterComponent, filterLevel]);

  return (
    <div data-testid="trace-viewer-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">Trace Viewer</h2>

      <div className="flex gap-2">
        <select value={filterComponent} onChange={(e) => setFilterComponent(e.target.value)} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs">
          <option value="">All components</option>
          {components.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filterLevel} onChange={(e) => setFilterLevel(e.target.value)} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs">
          <option value="">All levels</option>
          <option value="DEBUG">Debug</option>
          <option value="INFO">Info</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
        </select>
        <button onClick={loadTraces} className="px-3 py-1 bg-blue-600 rounded text-xs">Refresh</button>
      </div>

      <div className="space-y-1 max-h-[70vh] overflow-y-auto">
        {events.map((e, i) => (
          <div key={i} className={`border-l-2 pl-2 py-1 text-xs ${
            e.level === "ERROR" ? "border-red-500" : e.level === "WARNING" ? "border-amber-500" : "border-slate-600"
          }`}>
            <div className="flex gap-2">
              <span className="text-slate-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
              <span className="text-blue-400">{e.component}</span>
              <span className="text-slate-500">{e.event_type}</span>
              {e.level !== "INFO" && <span className={`font-medium ${e.level === "ERROR" ? "text-red-400" : "text-amber-400"}`}>{e.level}</span>}
            </div>
            <div className="text-slate-300 mt-0.5">{e.message}</div>
          </div>
        ))}
        {events.length === 0 && !isLoading && <p className="text-slate-500 text-sm">No trace events.</p>}
      </div>
    </div>
  );
}
```

---

## S5. Create `src/components/panels/SessionManagerPanel.tsx`

```tsx
"use client";
import { useState, useEffect } from "react";
import { getSessions, createSession, deleteSession, SessionInfo } from "@/lib/api";

export function SessionManagerPanel() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try { const r = await getSessions(); setSessions(r.sessions || []); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to load"); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    try { await createSession(); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to create"); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`Delete session ${id}?`)) return;
    try { await deleteSession(id); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to delete"); }
  };

  return (
    <div data-testid="session-manager-panel" className="p-4 space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Sessions</h2>
        <button onClick={handleCreate} className="px-3 py-1 bg-emerald-600 rounded text-sm">+ New Session</button>
      </div>
      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="space-y-2">
        {sessions.map((s) => (
          <div key={s.session_id} className="border border-slate-700 rounded p-3 bg-slate-900 flex justify-between items-center">
            <div>
              <span className="font-mono text-sm">{s.session_id}</span>
              {s.summary && <span className="ml-2 text-xs text-slate-500">{s.summary}</span>}
              <div className="text-xs text-slate-600">{s.created}</div>
            </div>
            <button onClick={() => handleDelete(s.session_id)} className="text-xs text-red-400 hover:text-red-300">Delete</button>
          </div>
        ))}
        {sessions.length === 0 && <p className="text-slate-500 text-sm">No sessions.</p>}
      </div>
    </div>
  );
}
```

---

## S6. Update uiStore, Sidebar, page.tsx

Add `VIEWS.TRACES: "traces"` and `VIEWS.SESSIONS: "sessions"` to uiStore.
Add 2 nav items to Sidebar (icons: `Activity`, `FolderTree` from lucide-react).
Add routing to page.tsx.

---

## S7. Add tests

Create `tests/test_trace_api.py` (4 tests) and `tests/test_session_api.py` (4 tests).
Add 2 Vitest component tests.

Minimum 10 new tests.

---

## S8. Verify build

```bash
ruff check api/traces.py api/sessions.py
mypy api/traces.py api/sessions.py --ignore-missing-imports
python -m pytest tests/test_trace_api.py tests/test_session_api.py -vvv
cd src && npx tsc --noEmit && npm run build
python -m pytest tests/ -vvv
```

---

## STOP condition

If `orchestrator._emitter` or `orchestrator.session_manager` not configured, endpoints return 503 (expected).

---

## Files WILL create (6)
- `api/traces.py`, `api/sessions.py`
- `src/components/panels/TraceViewerPanel.tsx`, `SessionManagerPanel.tsx`
- `tests/test_trace_api.py`, `tests/test_session_api.py`

## Files WILL edit (5)
- `web/server.py` (include routers)
- `src/lib/api.ts`, `src/stores/uiStore.ts`, `src/components/shell/Sidebar.tsx`, `src/app/page.tsx`
- `src/__tests__/components.test.tsx`

## Files will NOT edit
- `core/observability.py`, `core/session.py`, `memory/postgres_trace_store.py` (use as-is)

---

## Closing

Run `/jarvis-close`. Tag `prompt-99`. CHANGELOG entry. Update PLANS.md.
