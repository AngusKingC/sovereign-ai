# Plan 98 — Security & Sandbox Visibility (Phase 5a)

**Tag**: `prompt-98` | **Depends on`: `prompt-97`

---

## Scope

Expose the sandbox execution system and approval trust registry via Web UI. Backend: sandbox status/logs endpoints, trust registry CRUD endpoints. Frontend: Sandbox Dashboard (container list, logs), Trust Registry Editor, Input Sanitiser Status.

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §3.5 Gap #5 (HIGH), §6 Phase 5

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-97` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

S0.4. **Post-Plan 95 scan state** (verified clean):
- `test_list_workers` is FIXED (no longer skipped). AsyncMock return_value corrected in Plan 95.
- Governance files are updated: jarvis-close has C9 (concrete templates) + C16 (Git Bash cleanup), AI_HANDOFF says "Git Bash on Windows", jarvis-open uses `test -f`.
- `.txt` files moved to `txt/` folder during Plan 95 scan. Use `txt/requirements.txt` not `requirements.txt`.
- Vitest: 7 tests skipped (WorkerCreator, WorkerEditor, ModelsPanel not yet implemented).
- Playwright E2E deferred (web server startup issue — not blocking).

S0.5. **Pre-verification** (mandatory before coding):
- Read `core/sandbox.py` — confirm `SandboxExecutor` API: `_check_docker_available()`, `execute_python()`, `execute_command()`.
- Read `core/approval_trust.py` — confirm `ApprovalTrustRegistry` API: `get_all_trusted()`, `set_trust()`, `revoke_trust()`, `TrustLevel` enum values.
- Read `core/input_sanitiser.py` — confirm `InputSanitiser` API: `sanitise()`, `is_clean()`.
- Verify `orchestrator.approval_gate.trust_registry` is accessible. If `trust_registry` is private, add a public getter.

---

## S1. Add sandbox API endpoints

Create `api/sandbox.py`:

```python
"""API router for sandbox execution visibility."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Any

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

@router.get("/status")
async def get_sandbox_status() -> dict[str, Any]:
    """Check if Docker sandbox is available and get container list."""
    from core.sandbox import SandboxExecutor
    executor = SandboxExecutor()
    docker_available = await executor._check_docker_available()
    if not docker_available:
        return {"available": False, "containers": [], "message": "Docker not available — using subprocess fallback"}

    import asyncio
    def _list_containers():
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 4:
                    containers.append({"id": parts[0], "image": parts[1], "status": parts[2], "name": parts[3]})
        return containers

    containers = await asyncio.to_thread(_list_containers)
    return {"available": True, "containers": containers}

@router.get("/logs/{container_id}")
async def get_container_logs(container_id: str, lines: int = 100) -> dict[str, Any]:
    """Get container logs."""
    import asyncio
    def _get_logs():
        import subprocess
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container_id],
            capture_output=True, text=True, timeout=10
        )
        return {"stdout": result.stdout, "stderr": result.stderr}

    try:
        logs = await asyncio.to_thread(_get_logs)
        return {"container_id": container_id, **logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {e}")
```

Wire into `web/server.py`:
```python
from api.sandbox import router as sandbox_router
app.include_router(sandbox_router)
```

---

## S2. Add trust registry API endpoints

Create `api/trust.py`:

```python
"""API router for approval trust registry."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/trust", tags=["trust"])

@router.get("")
async def list_trusted() -> dict[str, Any]:
    """List all trusted commands/patterns."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'approval_gate') or not orchestrator.approval_gate:
        raise HTTPException(status_code=503, detail="Approval gate not configured")

    trust_registry = getattr(orchestrator.approval_gate, 'trust_registry', None)
    if not trust_registry:
        return {"trusted": []}

    trusted = await trust_registry.get_all_trusted()
    return {"trusted": trusted}

class TrustUpdateRequest(BaseModel):
    command: str
    trust_level: str  # "permanent_trust", "session_trust", "never_allow"

@router.put("")
async def set_trust(request: TrustUpdateRequest) -> dict[str, Any]:
    """Set trust level for a command."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'approval_gate') or not orchestrator.approval_gate:
        raise HTTPException(status_code=503, detail="Approval gate not configured")

    trust_registry = getattr(orchestrator.approval_gate, 'trust_registry', None)
    if not trust_registry:
        raise HTTPException(status_code=503, detail="Trust registry not configured")

    from core.approval_trust import TrustLevel
    level_map = {
        "permanent_trust": TrustLevel.PERMANENT_TRUST,
        "session_trust": TrustLevel.SESSION_TRUST,
        "never_allow": TrustLevel.NEVER_ALLOW,
    }
    level = level_map.get(request.trust_level)
    if not level:
        raise HTTPException(status_code=400, detail=f"Invalid trust level: {request.trust_level}")

    await trust_registry.set_trust(request.command, level)
    return {"status": "updated", "command": request.command, "trust_level": request.trust_level}

@router.delete("/{command}")
async def revoke_trust(command: str) -> dict[str, Any]:
    """Revoke trust for a command."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'approval_gate') or not orchestrator.approval_gate:
        raise HTTPException(status_code=503, detail="Approval gate not configured")

    trust_registry = getattr(orchestrator.approval_gate, 'trust_registry', None)
    if not trust_registry:
        raise HTTPException(status_code=503, detail="Trust registry not configured")

    await trust_registry.revoke_trust(command)
    return {"status": "revoked", "command": command}
```

Wire into `web/server.py`:
```python
from api.trust import router as trust_router
app.include_router(trust_router)
```

---

## S3. Add input sanitiser status endpoint

Add to `web/server.py`:
```python
@app.get("/api/sanitiser/status")
async def get_sanitiser_status() -> dict[str, Any]:
    """Get input sanitiser configuration and recent activity."""
    from core.input_sanitiser import InputSanitiser
    sanitiser = InputSanitiser()
    return {
        "enabled": True,
        "rules": ["html_strip", "command_injection_strip", "prompt_injection_strip", "normalise", "truncate"],
        "max_length": 10000,
    }
```

---

## S4. Add API functions to `src/lib/api.ts`

```typescript
export interface SandboxContainer { id: string; image: string; status: string; name: string; }
export interface SandboxStatus { available: boolean; containers: SandboxContainer[]; message?: string; }
export interface TrustEntry { command: string; trust_level: string; }

export async function getSandboxStatus(): Promise<SandboxStatus> {
  const res = await fetch(`/api/sandbox/status`);
  if (!res.ok) throw new Error(`Sandbox ${res.status}`);
  return res.json();
}

export async function getContainerLogs(containerId: string, lines: number = 100): Promise<any> {
  const res = await fetch(`/api/sandbox/logs/${containerId}?lines=${lines}`);
  if (!res.ok) throw new Error(`Logs ${res.status}`);
  return res.json();
}

export async function getTrustedCommands(): Promise<{ trusted: TrustEntry[] }> {
  const res = await fetch(`/api/trust`);
  if (!res.ok) throw new Error(`Trust ${res.status}`);
  return res.json();
}

export async function setTrust(command: string, trustLevel: string): Promise<any> {
  const res = await fetch(`/api/trust`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, trust_level: trustLevel }),
  });
  if (!res.ok) throw new Error(`Set trust ${res.status}`);
  return res.json();
}

export async function revokeTrust(command: string): Promise<any> {
  const res = await fetch(`/api/trust/${command}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Revoke trust ${res.status}`);
  return res.json();
}

export async function getSanitiserStatus(): Promise<any> {
  const res = await fetch(`/api/sanitiser/status`);
  if (!res.ok) throw new Error(`Sanitiser ${res.status}`);
  return res.json();
}
```

---

## S5. Create `src/components/panels/SandboxPanel.tsx`

```tsx
"use client";
import { useState } from "react";
import { usePolling } from "@/hooks/usePolling";
import { getSandboxStatus, getContainerLogs, SandboxStatus } from "@/lib/api";

export function SandboxPanel() {
  const { data, isLoading } = usePolling<SandboxStatus>(getSandboxStatus, 10000);
  const [logs, setLogs] = useState<string | null>(null);
  const [selectedContainer, setSelectedContainer] = useState<string | null>(null);

  const handleViewLogs = async (containerId: string) => {
    setSelectedContainer(containerId);
    const result = await getContainerLogs(containerId);
    setLogs(result.stdout + "\n" + result.stderr);
  };

  if (isLoading || !data) return <div data-testid="sandbox-panel" className="p-4">Loading...</div>;

  return (
    <div data-testid="sandbox-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">Sandbox Dashboard</h2>

      <div className={`p-3 rounded ${data.available ? "bg-emerald-900/30" : "bg-amber-900/30"}`}>
        <span className="text-sm">{data.available ? "✓ Docker sandbox available" : "⚠ " + (data.message || "Docker not available")}</span>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">Containers ({data.containers.length})</h3>
        <div className="space-y-2">
          {data.containers.map((c) => (
            <div key={c.id} className="border border-slate-700 rounded p-3 bg-slate-900">
              <div className="flex justify-between items-center">
                <div>
                  <span className="font-mono text-sm">{c.name || c.id.slice(0, 12)}</span>
                  <span className="ml-2 text-xs text-slate-500">{c.image}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${c.status.includes("Up") ? "bg-emerald-900" : "bg-slate-700"}`}>{c.status}</span>
                  <button onClick={() => handleViewLogs(c.id)} className="text-xs text-blue-400 hover:text-blue-300">View Logs</button>
                </div>
              </div>
            </div>
          ))}
          {data.containers.length === 0 && <p className="text-slate-500 text-sm">No containers running.</p>}
        </div>
      </div>

      {logs && selectedContainer && (
        <div className="border border-slate-700 rounded p-3 bg-slate-950">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm font-medium">Logs: {selectedContainer.slice(0, 12)}</h3>
            <button onClick={() => { setLogs(null); setSelectedContainer(null); }} className="text-xs text-slate-400">✕</button>
          </div>
          <pre className="text-xs text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">{logs}</pre>
        </div>
      )}
    </div>
  );
}
```

---

## S6. Create `src/components/panels/TrustRegistryPanel.tsx`

```tsx
"use client";
import { useState, useEffect } from "react";
import { getTrustedCommands, setTrust, revokeTrust, TrustEntry } from "@/lib/api";

export function TrustRegistryPanel() {
  const [trusted, setTrusted] = useState<TrustEntry[]>([]);
  const [newCommand, setNewCommand] = useState("");
  const [newLevel, setNewLevel] = useState("session_trust");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try { const result = await getTrustedCommands(); setTrusted(result.trusted || []); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to load"); }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!newCommand.trim()) return;
    try { await setTrust(newCommand, newLevel); setNewCommand(""); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to set trust"); }
  };

  const handleRevoke = async (command: string) => {
    try { await revokeTrust(command); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to revoke"); }
  };

  return (
    <div data-testid="trust-registry-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">Trust Registry</h2>
      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="flex gap-2">
        <input type="text" placeholder="Command pattern..." value={newCommand}
          onChange={(e) => setNewCommand(e.target.value)} className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm" />
        <select value={newLevel} onChange={(e) => setNewLevel(e.target.value)} className="px-2 py-2 bg-slate-800 border border-slate-700 rounded text-sm">
          <option value="session_trust">Session Trust</option>
          <option value="permanent_trust">Permanent Trust</option>
          <option value="never_allow">Never Allow</option>
        </select>
        <button onClick={handleAdd} className="px-4 py-2 bg-blue-600 rounded text-sm">Add</button>
      </div>

      <div className="space-y-2">
        {trusted.map((t, i) => (
          <div key={i} className="border border-slate-700 rounded p-2 bg-slate-900 flex justify-between items-center">
            <div>
              <span className="font-mono text-sm">{t.command}</span>
              <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                t.trust_level === "permanent_trust" ? "bg-emerald-900" :
                t.trust_level === "never_allow" ? "bg-red-900" : "bg-amber-900"
              }`}>{t.trust_level}</span>
            </div>
            <button onClick={() => handleRevoke(t.command)} className="text-xs text-red-400 hover:text-red-300">Revoke</button>
          </div>
        ))}
        {trusted.length === 0 && <p className="text-slate-500 text-sm">No trust entries.</p>}
      </div>
    </div>
  );
}
```

---

## S7. Update uiStore, Sidebar, page.tsx

Add `VIEWS.SANDBOX: "sandbox"` and `VIEWS.TRUST: "trust"` to uiStore.
Add 2 nav items to Sidebar (icons: `Shield`, `Lock` from lucide-react).
Add routing to page.tsx.

---

## S8. Add tests

Create `tests/test_sandbox_api.py` (4 tests) and `tests/test_trust_api.py` (4 tests).
Add 2 Vitest component tests.

Minimum 10 new tests.

---

## S9. Verify build

```bash
ruff check api/sandbox.py api/trust.py
mypy api/sandbox.py api/trust.py --ignore-missing-imports
python -m pytest tests/test_sandbox_api.py tests/test_trust_api.py -vvv
cd src && npx tsc --noEmit && npm run build
python -m pytest tests/ -vvv
```

---

## STOP condition

If Docker not available on Windows, sandbox status endpoint returns `available: false` — this is expected, not a STOP.

---

## Files WILL create (5)
- `api/sandbox.py`, `api/trust.py`
- `src/components/panels/SandboxPanel.tsx`, `TrustRegistryPanel.tsx`
- `tests/test_sandbox_api.py`, `tests/test_trust_api.py`

## Files WILL edit (5)
- `web/server.py` (include routers + sanitiser endpoint)
- `src/lib/api.ts`, `src/stores/uiStore.ts`, `src/components/shell/Sidebar.tsx`, `src/app/page.tsx`
- `src/__tests__/components.test.tsx`

## Files will NOT edit
- `core/sandbox.py`, `core/approval_trust.py`, `core/input_sanitiser.py` (use as-is)

---

## Closing

Run `/jarvis-close`. Tag `prompt-98`. CHANGELOG entry. Update PLANS.md.
