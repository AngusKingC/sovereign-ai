# Plan 81 — Backend Unification + API Endpoints

**Tag**: `prompt-81` | **Depends on**: `prompt-80`

### Scope
Unify `backend/main.py` and `web/server.py` into a single FastAPI app. Add all missing API endpoints for the operational dashboard. Fix the broken frontend imports (`src/lib/api.ts` missing). No frontend components in this plan — pure backend infrastructure.

### S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-80` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. **NEW (Panel C3)**: Before writing any endpoint, verify each external method exists:
- Run `grep -n "def get_spend_summary\|def get_status\|def get_degraded" core/ system/ workers/ -r`
- Run `grep -n "_pending_requests\|fetch_by_filter\|_task_history" core/ -r`
- Produce a "Method Verification Table" in this plan's working notes: list each method, its actual signature, and whether it exists.
- If a method does NOT exist, add it to S3 (as a real getter with `# TODO: implement` comment) — do NOT return mocked data.
S0.4. No new AGENTS.md rules this prompt.

### S1. Audit and merge `backend/main.py` into `web/server.py`

**Before any merge, verify current state** (Panel C11):
1. Run `cat backend/main.py` — capture all endpoints, middleware, and imports
2. Run `cat web/server.py` — capture existing endpoints, middleware, and imports
3. Run `grep -r "backend.main\|from backend\|import backend" . --include="*.py" --include="*.yml" --include="*.yaml" --include="Dockerfile*" --include="*.toml" --include="*.sh"` — find all references to backend package
4. Produce a diff report: which endpoints exist in both, which are unique to backend/main.py, which middleware differs

**Merge rules** (Panel C1 from Panel 4):
- CORS: Verify `allow_origins` includes `http://localhost:3000`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
- Auth: All migrated endpoints must use the same auth middleware as existing web/server.py endpoints
- Endpoints to migrate: `GET /health`, `GET /api/status` (merge fields), `GET /api/tasks`, `GET /api/workers`, `POST /api/tasks`, `GET /api/memory/activations` (SSE), `GET /api/tools/stream` (SSE), `GET /api/agent/reasoning` (SSE), `GET /api/subagents`, `DELETE /api/subagents/{id}`

**After merge**:
- Delete `backend/main.py` and `backend/` directory
- Update `pyproject.toml` to remove `backend` package
- Update all references found in step 3 above

### S2. Add missing API endpoints to `web/server.py`

**Rule: NO mocked data. Only real methods or empty typed structures.** (Panel C3 — resolved contradiction)

For each endpoint below, follow this decision tree:
1. Does the method exist with the expected signature? → Wire directly.
2. Does the method exist with a different signature? → Adapt the wrapper in web/server.py.
3. Does the method NOT exist? → Add a thin getter in S3 that returns a properly typed empty structure. Mark with `# TODO: implement when [module] is ready`.

| Endpoint | Method | Data Source | Response Model | If Missing |
|----------|--------|-------------|----------------|------------|
| `GET /api/costs/summary` | GET | `cost_tracker.get_spend_summary()` | `CostSummaryResponse` | Return `{"daily_spend": 0.0, "daily_cap": 10.0, "monthly_spend": 0.0, "monthly_cap": 100.0, "alert_threshold": 80, "fallback_threshold": 90, "model_breakdown": {}}` |
| `GET /api/costs/daily` | GET | `cost_tracker.daily_usage` | `DailyCostResponse` | Return `{"date": "", "total_usd": 0.0, "entries": []}` |
| `GET /api/circuit-breaker/status` | GET | `worker_circuit_breaker.get_status()` + `get_degraded_worker_ratio()` | `CircuitStatusResponse` | Return `{"workers": [], "degraded_ratio": 0.0}` |
| `POST /api/circuit-breaker/reset` | POST | `worker_circuit_breaker.reset_circuit(worker_id)` | `ResetResponse` | Return `{"status": "not_implemented", "worker_id": ""}` (Rev5 L-B fix — was `"ok"`, misleading for ops dashboard) |
| `GET /api/approvals/pending` | GET | `approval_gate.list_pending()` (NEW public getter) | `List[ApprovalResponse]` | Return `[]` |
| `POST /api/approvals/{id}/respond` | POST | `approval_gate.respond(id, approved)` | `ApprovalResponse` | Return `{"status": "not_found", "id": ""}` |
| `GET /api/memory/slots` | GET | `memory_router.fetch_by_filter()` | `List[MemorySlotResponse]` | Return `[]` |
| `GET /api/memory/slots/export` | GET | `memory_router.fetch_by_filter()` | JSON blob | Return `[]` (Panel S4 — renamed from /memory/export) |
| `POST /api/memory/slots/import` | POST | `memory_router.scoped_write()` | `ImportResponse` | Return `{"imported": 0, "errors": []}` |
| `GET /api/skills` | GET | `skill_registry.list_skills()` (scan skills/ directory) | `List[SkillResponse]` | Return `[]` |
| `GET /api/sessions/{id}/timeline` | GET | `orchestrator.get_session_timeline(id)` | `List[TimelineResponse]` | Return `[]` |
| `GET /api/system` | GET | `system_monitor.get_stats()` | `SystemStatsResponse` | Return `{"cpu_percent": 0.0, "memory_percent": 0.0, "uptime_seconds": 0, "active_workers": 0}` |

**Auth strategy for SSE endpoints** (Panel C2, Rev3 H6 fix): SSE routes (`/api/memory/activations`, `/api/tools/stream`, `/api/agent/reasoning`) must use cookie-based auth (not Bearer headers, since EventSource cannot send custom headers). **Verify the existing auth middleware reads cookies. If it does NOT, add a cookie-based auth dependency for SSE routes specifically, falling back to the standard Bearer check for non-SSE routes.** Do not leave this as a 'verify and document' step — fix the middleware if verification fails. Document the final auth strategy in the endpoint comments.

### S3. Add orchestrator/core getter methods

Add these methods to the appropriate modules. All are thin wrappers — no new logic:

**`core/orchestrator.py`**:
```python
def list_tasks(self, status: Optional[str] = None) -> List[Task]:
    """Return tasks filtered by status."""

def get_task(self, task_id: str) -> Optional[Task]:
    """Return single task by ID."""

def list_workers_with_status(self) -> List[Dict]:
    """Return workers enriched with circuit breaker status."""

def get_session_timeline(self, session_id: str) -> List[Dict]:
    """Return phase timeline for a session."""
```

**`core/approval_gate.py`** (NEW public getter — Panel C12, Rev3 L3 fix):
```python
def list_pending(self) -> List[ApprovalResponse]:
    """Return list of pending approval requests as API response models.
    Public accessor for _pending_requests. Converts internal ApprovalRequest
    objects to ApprovalResponse models for API consumption.
    """
    # S0.3 verification: check if _pending_requests is dict or list
    # If dict: return [ApprovalResponse.from_request(r) for r in self._pending_requests.values()]
    # If list: return [ApprovalResponse.from_request(r) for r in self._pending_requests]
    # Add ApprovalResponse.from_request() classmethod to core/schemas.py if it doesn't exist
```
**Note**: ApprovalResponse must be defined in `core/schemas.py` before this getter. If `ApprovalResponse.from_request()` does not exist, add it as a classmethod that maps ApprovalRequest fields → ApprovalResponse fields.

**Additional thin getters** (Rev3 H4 fix — required for endpoints in S2 with 'If Missing' fallbacks. Each returns a properly typed empty structure marked `# TODO: implement when [module] is ready`. Do NOT return hardcoded mocked data from the endpoint handler — the endpoint must call these getters.):

**`core/skill_registry.py`** (if `list_skills()` doesn't exist):
```python
def list_skills(self) -> List[Dict[str, Any]]:
    """Return list of registered skills for UI consumption."""
    # TODO: implement when skill registry is complete
    return []
```

**`system/system_monitor.py`** (if `get_stats()` doesn't exist):
```python
def get_stats(self) -> Dict[str, Any]:
    """Return system stats for UI consumption."""
    # TODO: implement when system monitor is complete
    return {"cpu_percent": 0.0, "memory_percent": 0.0, "uptime_seconds": 0, "active_workers": 0}
```

**`core/worker_circuit_breaker.py`** (if `get_status()` doesn't exist):
```python
def get_status(self) -> Dict[str, Any]:
    """Return circuit breaker status for all workers."""
    # TODO: implement when circuit breaker is complete
    return {"workers": [], "degraded_ratio": 0.0}
```

**`memory/memory_router.py`** (if `fetch_by_filter()` doesn't exist):
```python
def fetch_by_filter(self, **kwargs) -> List[Dict[str, Any]]:
    """Return memory slots matching filter criteria."""
    # TODO: implement when memory router is complete
    return []
```

**`memory/memory_router.py`** (if `scoped_write()` doesn't exist — Rev4 H-A fix):
```python
def scoped_write(self, key: str, value: Any, scope: str = "default") -> Dict[str, Any]:
    """Write a memory slot within a scope. Returns import-style response."""
    # TODO: implement when memory router is complete
    return {"imported": 0, "errors": ["scoped_write not implemented"]}
```

**`core/approval_gate.py`** (if `respond()` doesn't exist — Rev4 H-A fix):
```python
def respond(self, request_id: str, approved: bool) -> Dict[str, Any]:
    """Respond to a pending approval request. Returns response status."""
    # TODO: implement when approval gate is complete
    return {"status": "not_found", "id": request_id}
```

**`core/worker_circuit_breaker.py`** (if `reset_circuit()` doesn't exist — Rev4 H-A fix, Rev5 L-B fix):
```python
def reset_circuit(self, worker_id: str) -> Dict[str, Any]:
    """Reset circuit breaker for a specific worker. Returns reset status."""
    # TODO: implement when circuit breaker is complete
    # Rev5 L-B fix — return "not_implemented" (was "ok"), to honestly signal the
    # stub did nothing. Operators relying on the Reset Circuit button need to
    # know the action didn't actually happen. Mirrors sibling stubs
    # (scoped_write returns errors, respond returns not_found).
    return {"status": "not_implemented", "worker_id": worker_id}
```

**`core/worker_circuit_breaker.py`** (if `get_degraded_worker_ratio()` doesn't exist — Rev4 H-A fix):
```python
def get_degraded_worker_ratio(self) -> float:
    """Return ratio of workers in degraded/open circuit state."""
    # TODO: implement when circuit breaker is complete
    return 0.0
```

**`system/cost_tracker.py`** (if `daily_usage` property doesn't exist — Rev4 H-A fix):
```python
@property
def daily_usage(self) -> Dict[str, Any]:
    """Return today's cost usage breakdown."""
    # TODO: implement when cost tracking is complete
    return {"date": "", "total_usd": 0.0, "entries": []}
```

**Verification note** (Rev4 H-A fix): The S0.3 Method Verification Table MUST cross-check every method referenced in the S2 endpoint table against the S3 getter list above. The complete list of methods requiring getters (existing or stubbed) is:
- `cost_tracker.get_spend_summary()` ✓ (Rev3 H4)
- `cost_tracker.daily_usage` ✓ (Rev4 H-A)
- `worker_circuit_breaker.get_status()` ✓ (Rev3 H4)
- `worker_circuit_breaker.get_degraded_worker_ratio()` ✓ (Rev4 H-A)
- `worker_circuit_breaker.reset_circuit(worker_id)` ✓ (Rev4 H-A)
- `approval_gate.list_pending()` ✓ (Rev3 C12)
- `approval_gate.respond(id, approved)` ✓ (Rev4 H-A)
- `memory_router.fetch_by_filter()` ✓ (Rev3 H4)
- `memory_router.scoped_write()` ✓ (Rev4 H-A)
- `skill_registry.list_skills()` ✓ (Rev3 H4)
- `orchestrator.get_session_timeline(id)` ✓ (Rev3 C3)
- `system_monitor.get_stats()` ✓ (Rev3 H4)
If any method is missing AND cannot be added as a thin getter, STOP and report.

**`system/cost_tracker.py`** (if `get_spend_summary` doesn't exist):
```python
def get_spend_summary(self) -> Dict[str, Any]:
    """Return spend summary for UI consumption."""
    # TODO: implement when cost tracking is complete
    return {
        "daily_spend": 0.0,
        "daily_cap": self.policy.daily_cap_usd if hasattr(self, 'policy') else 10.0,
        "monthly_spend": 0.0,
        "monthly_cap": self.policy.monthly_cap_usd if hasattr(self, 'policy') else 100.0,
        "alert_threshold": 80,
        "fallback_threshold": 90,
        "model_breakdown": {},
    }
```

### S4. Create `src/lib/api.ts`

This file is MISSING and breaks the frontend build. Create it with typed API wrappers.

**Auth handling** (Panel C2, Rev3 H2 fix): The frontend uses Next.js rewrites (proxy to backend) so regular fetch calls are same-origin. **All regular API calls MUST use relative paths (`/api/status`) so they route through the Next.js proxy. Do NOT use absolute `${BACKEND_URL}` URLs for fetch calls — that bypasses the proxy, breaks cookie auth, and makes the rewrite config dead code.** Auth is handled by the backend middleware via cookies set on the same origin. No Authorization header needed in api.ts for dev mode. For production, add a note: "Production auth: implement Next.js middleware to inject Bearer token."

**SSE URLs** are the exception — `EventSource` cannot be proxied through Next.js rewrites, so SSE URLs must use the absolute `BACKEND_URL` with `credentials: 'include'` to send cookies cross-origin.

```typescript
export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// All regular API functions use RELATIVE paths (/api/...) so they route through Next.js rewrites.
// Auth is handled by backend middleware via same-origin cookies.
// BACKEND_URL is reserved for SSE EventSource URLs only.

export interface AgentStatus {
  phase: "idle" | "planning" | "acting" | "reflecting";
  session_id: string;
  model: string;
  latency_ms: number;
  is_running: boolean;
}

export interface Task {
  id: string;
  intent: string;
  worker_id: string;
  status: "RECEIVED" | "EXECUTING" | "VALIDATING" | "COMPLETE" | "FAILED" | "CANCELLED" | "QUEUED";
  confidence: number;
  cost_usd: number;
  token_count: number;
  created_at: string;
  completed_at?: string;
}

export interface Worker {
  id: string;
  type: string;
  capabilities: string[];
  circuit_state: "CLOSED" | "OPEN" | "HALF_OPEN";
  failures: number;
  threshold: number;
  last_used?: string;
  task_count: number;
}

export interface CostSummary {
  daily_spend: number;
  daily_cap: number;
  monthly_spend: number;
  monthly_cap: number;
  alert_threshold: number;
  fallback_threshold: number;
  model_breakdown: Record<string, number>;
}

export interface ApprovalRequest {
  id: string;
  type: string;
  description: string;
  risk: "low" | "medium" | "high";
  expires_at: string;
}

export interface MemorySlot {
  index: number;
  key?: string;
  value_preview?: string;
  last_written?: string;
  activation: number;
}

export interface SkillInfo {
  name: string;
  tier: "USER_INVOKED" | "AGENT_INVOKED" | "HYBRID";
  enabled: boolean;
  methods: string[];
  requires: string[];
}

export interface TimelineSegment {
  phase: string;
  start: string;
  end: string;
  confidence: number;
}

export interface SystemStats {
  cpu_percent: number;
  memory_percent: number;
  gpu_percent?: number;
  uptime_seconds: number;
  active_workers: number;
}

export async function getStatus(): Promise<AgentStatus> {
  const res = await fetch(`/api/status`);
  if (!res.ok) throw new Error(`Status ${res.status}`);
  return res.json();
}

export async function getTasks(status?: string): Promise<Task[]> {
  const url = status ? `/api/tasks?status=${status}` : `/api/tasks`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Tasks ${res.status}`);
  return res.json();
}

export async function getWorkers(): Promise<Worker[]> {
  const res = await fetch(`/api/workers`);
  if (!res.ok) throw new Error(`Workers ${res.status}`);
  return res.json();
}

export async function getCostsSummary(): Promise<CostSummary> {
  const res = await fetch(`/api/costs/summary`);
  if (!res.ok) throw new Error(`Costs ${res.status}`);
  return res.json();
}

export async function getPendingApprovals(): Promise<ApprovalRequest[]> {
  const res = await fetch(`/api/approvals/pending`);
  if (!res.ok) throw new Error(`Approvals ${res.status}`);
  return res.json();
}

export async function respondApproval(id: string, approved: boolean): Promise<void> {
  const res = await fetch(`/api/approvals/${id}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  if (!res.ok) throw new Error(`Respond ${res.status}`);
}

export async function getMemorySlots(limit = 100, offset = 0): Promise<MemorySlot[]> {
  const res = await fetch(`/api/memory/slots?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Memory ${res.status}`);
  return res.json();
}

export async function exportMemory(): Promise<Blob> {
  const res = await fetch(`/api/memory/slots/export`);
  if (!res.ok) throw new Error(`Export ${res.status}`);
  return res.blob();
}

export async function importMemory(slots: Array<{key: string; value: unknown; scope?: string}>): Promise<void> {
  const res = await fetch(`/api/memory/slots/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(slots),
  });
  if (!res.ok) throw new Error(`Import ${res.status}`);
}

export async function getSkills(): Promise<SkillInfo[]> {
  const res = await fetch(`/api/skills`);
  if (!res.ok) throw new Error(`Skills ${res.status}`);
  return res.json();
}

export async function getSessionTimeline(sessionId: string): Promise<TimelineSegment[]> {
  const res = await fetch(`/api/sessions/${sessionId}/timeline`);
  if (!res.ok) throw new Error(`Timeline ${res.status}`);
  return res.json();
}

export async function getSystemStats(): Promise<SystemStats> {
  const res = await fetch(`/api/system`);
  if (!res.ok) throw new Error(`System ${res.status}`);
  return res.json();
}

export async function resetCircuit(workerId: string): Promise<void> {
  const res = await fetch(`/api/circuit-breaker/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ worker_id: workerId }),
  });
  if (!res.ok) throw new Error(`Reset ${res.status}`);
}

// SSE URLs use absolute BACKEND_URL because EventSource cannot be proxied through Next.js rewrites.
// credentials: 'include' is required to send auth cookies cross-origin.
export function sseUrl(path: string): string {
  return `${BACKEND_URL}${path}`;
}
```

### S5. Update `src/next.config.ts`

Add rewrites to proxy API requests to the unified backend:
```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
      { source: "/health", destination: "http://localhost:8000/health" },
    ];
  },
};

export default nextConfig;
```

### S6. Create `src/.env.example` (NOT .env.local)

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
SOVEREIGN_DEV_TOKEN=dev-token-change-in-production
```

**Note**: `src/.env.local` is NOT created by this plan. It is gitignored. Dev creates it locally from `.env.example`. (Panel M1 — accepted)

### S7. Update `src/package.json`

Ensure these dependencies are present (add if missing):
- `zustand` (state management)
- `lucide-react` (icons)

Verify `ruff` and `mypy` are in pyproject.toml dev dependencies. If not, add them. (Panel M4 — accepted)

### S8. Add backend tests for new endpoints

Add to `tests/test_ui_backend.py`. **Auth handling** (Panel S7): Use `app.dependency_overrides` or a test fixture that disables auth for test mode.

```python
# conftest.py addition (if not present):
# @pytest.fixture
def client_no_auth():
    # Override auth dependency for tests
    from web.server import app
    app.dependency_overrides[auth_dependency] = lambda: test_user
    # ... existing client fixture
    yield  # Rev3 L10 fix — yield for teardown
    # Teardown: restore original overrides to prevent global state leak
    app.dependency_overrides.pop(auth_dependency, None)

# 9 new tests:
def test_get_costs_summary(client_no_auth):
    res = client_no_auth.get("/api/costs/summary")
    assert res.status_code == 200
    data = res.json()
    assert "daily_spend" in data
    assert "daily_cap" in data

def test_get_costs_daily(client_no_auth):
    res = client_no_auth.get("/api/costs/daily")
    assert res.status_code == 200
    assert "total_usd" in res.json()

def test_get_circuit_breaker_status(client_no_auth):
    res = client_no_auth.get("/api/circuit-breaker/status")
    assert res.status_code == 200
    data = res.json()
    assert "workers" in data
    assert "degraded_ratio" in data

def test_post_circuit_breaker_reset(client_no_auth):
    res = client_no_auth.post("/api/circuit-breaker/reset", json={"worker_id": "test_worker"})
    assert res.status_code == 200
    # Rev5 L-B fix — stub now returns "not_implemented" instead of misleading "ok".
    # When the real method is implemented, this assertion should be updated to "ok".
    assert res.json()["status"] == "not_implemented"

def test_get_approvals_pending(client_no_auth):
    res = client_no_auth.get("/api/approvals/pending")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_post_approvals_respond(client_no_auth):
    res = client_no_auth.post("/api/approvals/test-id/respond", json={"approved": True})
    assert res.status_code in (200, 404)  # 404 if no pending approval exists

def test_get_memory_slots(client_no_auth):
    res = client_no_auth.get("/api/memory/slots")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_get_skills(client_no_auth):
    res = client_no_auth.get("/api/skills")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert "name" in data[0]
        assert "tier" in data[0]

def test_get_system_stats(client_no_auth):
    res = client_no_auth.get("/api/system")
    assert res.status_code == 200
    data = res.json()
    assert "cpu_percent" in data
    assert "memory_percent" in data
```

### S9. Verify build

Run in order:
1. `grep` verification from S0.3 — confirm Method Verification Table exists
2. `ruff check web/server.py` — 0 errors
3. `mypy web/server.py core/orchestrator.py core/schemas.py core/approval_gate.py --ignore-missing-imports` — 0 errors (Panel M7, Rev3 L5 fix — added approval_gate.py for C12 getter)
4. `pytest tests/test_ui_backend.py -v` — all 15 tests pass (6 existing + 9 new)
5. `cd src && npx tsc --noEmit` — confirm `lib/api.ts` compiles

### STOP condition
If merging `backend/main.py` into `web/server.py` causes any existing test to fail, STOP and report. Do not proceed until the merge is clean. If any method in the Method Verification Table is marked "missing" and cannot be added as a thin getter, STOP and report.

### Files WILL create
- `src/lib/api.ts`
- `src/.env.example`

### Files WILL edit
- `web/server.py` (major — merge + new endpoints)
- `core/orchestrator.py` (minor — add getter methods)
- `core/schemas.py` (minor — add response models)
- `core/approval_gate.py` (minor — add `list_pending()` public getter)
- `src/next.config.ts` (minor — add rewrites)
- `src/package.json` (minor — ensure deps)
- `tests/test_ui_backend.py` (moderate — 9 new tests)
- `pyproject.toml` (minor — remove backend package, ensure ruff/mypy present)

### Files will NOT edit
- `core/` logic modules (except thin getters in S3)
- `cli/`
- `skills/` logic
- `adapters/`
- `workers/`
- `memory/` internals (except via existing router methods)
- `system/` internals (except via existing cost_tracker/circuit_breaker)

### Closing

Run `/jarvis-close`. Tag `prompt-81`. CHANGELOG entry for Plan 81. Update PLANS.md (completed row, baseline shift).

---
