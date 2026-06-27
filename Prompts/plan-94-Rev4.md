# Plan 94 — Cost & Resource Controls (Phase 3)

**Tag**: `prompt-94` | **Depends on**: `prompt-93`

**Rev4 — Post-Round-Table Adjudication (6 panel responses consolidated across Rev2+Rev3 cycles)**

**Rev2 history**: Post-Round-Table Adjudication (4 panel responses consolidated)
**Rev3 history**: Post-Round-Table Re-Review (5 panel responses consolidated)

---

## Scope

Un-mock the SettingsDrawer cost settings and add real-time resource monitoring. This is Gap #4 from the UI/UX Gap Analysis (§3.4 — HIGH). Backend: `PUT /api/costs/policy` (editable caps/thresholds), `GET /api/resources/monitor` (real-time CPU/RAM/VRAM). Frontend: un-mock SettingsDrawer Cost Policy tab, `ResourceMonitorPanel.tsx` with live charts.

**Rev2 changes**: (1) Added `get_policy()` public method to CostTracker (was accessing `_policy` directly). (2) Added SystemProfiler.refresh() return type pre-verification + defensive accessors. (3) Guarded against empty storage list IndexError. (4) Fixed psutil fallback to use `interval=None` (non-blocking). (5) Added CostPolicyUpdate validation constraints. (6) Documented polling-vs-SSE deferral.

**Rev4 changes**: (1) Removed self-contradictory STOP condition (Rev3 C1 fix). (2) Added explicit "read-first-append" instruction for system_profiler injection (Rev3 H1 fix). (3) Added psutil dependency verification step (Rev3 N2 fix).

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §3.4, §6 Phase 3

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-93` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

### S0.5. Pre-verification: SystemProfiler and CostTracker signatures (Rev2 H8 — mandatory)

**Step 1**: Read `system/profiler.py` and confirm:
- `async def refresh() -> SystemProfile` — does it return an object (with `.cpu.percent`) or a dict (with `["cpu"]["percent"]`)?
- `SystemProfile` schema: `.cpu` (CPUInfo with `.percent`), `.ram` (RAMInfo with `.percent`), `.storage` (list of StorageInfo), `.gpu` (GPUInfo or None)
- If `refresh()` returns a dict, adapt S2 endpoint to use bracket notation

**Step 2**: Read `core/cost_tracker.py` and confirm:
- `_policy` attribute exists and is a `CostPolicy` dataclass
- `CostPolicy` fields: `daily_cap_usd`, `monthly_cap_usd`, `alert_threshold_pct`, `fallback_threshold_pct`, `fallback_model`, `enable_traces`
- Rev2 H2 fix: Add `get_policy()` public method (see S1)

**Step 3**: If any signature differs, adapt plan steps BEFORE coding.

---

## S1. Add `PUT /api/costs/policy` endpoint

**Rev2 H2 fix**: Add `get_policy()` public method to CostTracker instead of accessing `_policy` directly. This eliminates the private attribute access code smell.

**Step 1**: Add `get_policy()` and `update_policy()` methods to `core/cost_tracker.py`:

```python
class CostTracker:
    # ... existing code ...

    # Rev2 H2 fix — public getter for policy (was accessed via _policy directly)
    def get_policy(self) -> CostPolicy:
        """Get the current cost policy. Public accessor for _policy."""
        return self._policy

    def update_policy(self, policy: CostPolicy) -> None:
        """Update the cost policy at runtime.

        Allows UI to change caps and thresholds without restart.
        """
        self._policy = policy
        logger.info(f"Cost policy updated: daily_cap={policy.daily_cap_usd}, monthly_cap={policy.monthly_cap_usd}")
```

**Step 2** (Rev2 L2 fix — validation constraints): Add the endpoint to `web/server.py` with validated request model:

```python
from pydantic import BaseModel, Field
from core.cost_tracker import CostPolicy

# Rev2 L2 fix — validation constraints on thresholds and caps
class CostPolicyUpdate(BaseModel):
    """Request to update cost policy. Rev2 L2 fix — validated constraints."""
    daily_cap_usd: float | None = Field(None, ge=0)
    monthly_cap_usd: float | None = Field(None, ge=0)
    alert_threshold_pct: float | None = Field(None, ge=0, le=1)
    fallback_threshold_pct: float | None = Field(None, ge=0, le=1)
    fallback_model: str | None = None

@app.put("/api/costs/policy")
async def update_cost_policy(update: CostPolicyUpdate):
    """Update cost policy (caps, thresholds, fallback model)."""
    if not orchestrator or not hasattr(orchestrator, 'cost_tracker') or not orchestrator.cost_tracker:
        raise HTTPException(status_code=503, detail="Cost tracker not configured")

    # Rev2 H2 fix — use get_policy() instead of _policy
    current = orchestrator.cost_tracker.get_policy()

    # Rev2 L2 fix — validate alert <= fallback
    new_alert = update.alert_threshold_pct if update.alert_threshold_pct is not None else current.alert_threshold_pct
    new_fallback = update.fallback_threshold_pct if update.fallback_threshold_pct is not None else current.fallback_threshold_pct
    if new_alert > new_fallback:
        raise HTTPException(status_code=422, detail=f"alert_threshold ({new_alert}) cannot exceed fallback_threshold ({new_fallback})")

    # Apply updates (only non-None fields)
    new_policy = CostPolicy(
        daily_cap_usd=update.daily_cap_usd if update.daily_cap_usd is not None else current.daily_cap_usd,
        monthly_cap_usd=update.monthly_cap_usd if update.monthly_cap_usd is not None else current.monthly_cap_usd,
        alert_threshold_pct=new_alert,
        fallback_threshold_pct=new_fallback,
        fallback_model=update.fallback_model if update.fallback_model is not None else current.fallback_model,
        enable_traces=current.enable_traces,
    )

    orchestrator.cost_tracker.update_policy(new_policy)

    return {
        "status": "updated",
        "policy": {
            "daily_cap_usd": new_policy.daily_cap_usd,
            "monthly_cap_usd": new_policy.monthly_cap_usd,
            "alert_threshold_pct": new_policy.alert_threshold_pct,
            "fallback_threshold_pct": new_policy.fallback_threshold_pct,
            "fallback_model": new_policy.fallback_model,
        }
    }

@app.get("/api/costs/policy")
async def get_cost_policy():
    """Get current cost policy."""
    if not orchestrator or not hasattr(orchestrator, 'cost_tracker') or not orchestrator.cost_tracker:
        raise HTTPException(status_code=503, detail="Cost tracker not configured")

    # Rev2 H2 fix — use get_policy() instead of _policy
    p = orchestrator.cost_tracker.get_policy()
    return {
        "daily_cap_usd": p.daily_cap_usd,
        "monthly_cap_usd": p.monthly_cap_usd,
        "alert_threshold_pct": p.alert_threshold_pct,
        "fallback_threshold_pct": p.fallback_threshold_pct,
        "fallback_model": p.fallback_model,
    }
```

---

## S2. Add `GET /api/resources/monitor` endpoint

**Rev2 H8 fix**: Pre-verify `SystemProfiler.refresh()` return type per S0.5. Use defensive accessors. **Rev2 H11 fix**: Guard against empty storage list. **Rev2 H12 fix**: psutil fallback uses `interval=None` (non-blocking).

Wire to `system/profiler.py` for real-time resource monitoring:

```python
# Rev2 H12 fix — module-level import, not inside endpoint
import psutil

@app.get("/api/resources/monitor")
async def get_resource_monitor():
    """Get real-time system resource usage (CPU, RAM, VRAM, Disk).

    Rev2 H8 fix: Defensive accessors for SystemProfile fields.
    Rev2 H11 fix: Guard against empty storage list.
    Rev2 H12 fix: psutil fallback uses interval=None (non-blocking).
    """
    if not orchestrator or not hasattr(orchestrator, 'system_profiler') or not orchestrator.system_profiler:
        # Fallback: return basic psutil stats if profiler not configured
        # Rev2 H12 fix — interval=None is non-blocking (returns 0.0 on first call, then real %)
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "gpu_percent": None,
            "gpu_memory_used_mb": None,
            "gpu_memory_total_mb": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    profile = await orchestrator.system_profiler.refresh()

    # Rev2 H8 fix — handle both object and dict return types
    def _get(obj, attr, default=None):
        """Get attribute from object or key from dict."""
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    cpu = _get(profile, 'cpu', None)
    ram = _get(profile, 'ram', None)
    storage = _get(profile, 'storage', [])
    gpu = _get(profile, 'gpu', None)

    # Rev2 H11 fix — guard against empty storage list
    disk_percent = 0.0
    if storage and len(storage) > 0:
        disk_percent = _get(storage[0], 'percent', 0.0)

    return {
        "cpu_percent": _get(cpu, 'percent', 0.0) if cpu else 0.0,
        "memory_percent": _get(ram, 'percent', 0.0) if ram else 0.0,
        "disk_percent": disk_percent,
        "gpu_percent": _get(gpu, 'percent', None) if gpu else None,
        "gpu_memory_used_mb": _get(gpu, 'memory_used_mb', None) if gpu else None,
        "gpu_memory_total_mb": _get(gpu, 'memory_total_mb', None) if gpu else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

**Step 2**: Add `system_profiler` to Orchestrator as optional injection.

**Rev2 H1 fix — read-first-append pattern**: Read `core/orchestrator.py` FIRST. Find the existing `__init__` constructor. APPEND `system_profiler` to the existing parameter list — do NOT replace. Plans 91/92/93 may have already added `model_registry`, `model_acquisition`, `worker_factory`. Add `system_profiler` after them.

```python
# In Orchestrator.__init__ signature (APPEND to existing — Rev2 H1 fix):
system_profiler: Optional["SystemProfiler"] = None,

# In __init__ body (APPEND to existing — Rev2 H1 fix):
self.system_profiler = system_profiler
```

**Rev2 N2 fix — psutil dependency**: Verify `psutil` is in `requirements.txt`. If not, add it:
```
psutil>=5.9.0
```

**Rev2 L1 note** (polling vs SSE): The gap analysis §9 recommends SSE for push updates. This plan uses polling at 5s intervals. SSE migration is deferred to a future plan. Add this comment in `ResourceMonitorPanel.tsx`:
```typescript
// TODO: Migrate to SSE for push updates per gap analysis §9 recommendation
// Currently uses polling — acceptable for v1 single-user, but SSE is better for multi-user.
```

---

## S3. Add API functions to `src/lib/api.ts`

```typescript
export interface CostPolicy {
  daily_cap_usd: number;
  monthly_cap_usd: number;
  alert_threshold_pct: number;
  fallback_threshold_pct: number;
  fallback_model: string | null;
}

export interface ResourceMonitor {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  gpu_percent: number | null;
  gpu_memory_used_mb: number | null;
  gpu_memory_total_mb: number | null;
  timestamp: string;
}

export async function getCostPolicy(): Promise<CostPolicy> {
  const res = await fetch(`/api/costs/policy`);
  if (!res.ok) throw new Error(`Policy ${res.status}`);
  return res.json();
}

export async function updateCostPolicy(policy: Partial<CostPolicy>): Promise<CostPolicy> {
  const res = await fetch(`/api/costs/policy`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  if (!res.ok) throw new Error(`Update policy ${res.status}`);
  return res.json();
}

export async function getResourceMonitor(): Promise<ResourceMonitor> {
  const res = await fetch(`/api/resources/monitor`);
  if (!res.ok) throw new Error(`Resources ${res.status}`);
  return res.json();
}
```

---

## S4. Un-mock `src/components/panels/SettingsDrawer.tsx`

Remove all `opacity-50`, `data-mocked`, and `title="Coming in Plan 89"` attributes from the Cost Policy tab. Wire to real API:

```tsx
"use client";
import { useState, useEffect } from "react";
import { getCostPolicy, updateCostPolicy, CostPolicy } from "@/lib/api";

function CostPolicyTab() {
  const [policy, setPolicy] = useState<CostPolicy | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCostPolicy().then(setPolicy).catch((e) => setError(e.message));
  }, []);

  const handleSave = async () => {
    if (!policy) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await updateCostPolicy(policy);
      setPolicy(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  };

  if (!policy) return <div className="p-4">Loading policy...</div>;

  return (
    <div className="space-y-4 p-2">
      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div>
        <label className="text-sm text-slate-400 block mb-1">Daily Cap (USD)</label>
        <input
          type="number"
          step="0.01"
          value={policy.daily_cap_usd}
          onChange={(e) => setPolicy({ ...policy, daily_cap_usd: parseFloat(e.target.value) })}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
        />
      </div>

      <div>
        <label className="text-sm text-slate-400 block mb-1">Monthly Cap (USD)</label>
        <input
          type="number"
          step="0.01"
          value={policy.monthly_cap_usd}
          onChange={(e) => setPolicy({ ...policy, monthly_cap_usd: parseFloat(e.target.value) })}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
        />
      </div>

      <div>
        <label className="text-sm text-slate-400 block mb-1">Alert Threshold (%)</label>
        <input
          type="number"
          step="0.01"
          min="0"
          max="1"
          value={policy.alert_threshold_pct}
          onChange={(e) => setPolicy({ ...policy, alert_threshold_pct: parseFloat(e.target.value) })}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
        />
        <p className="text-xs text-slate-500 mt-1">Alert triggered at this % of cap (0.80 = 80%)</p>
      </div>

      <div>
        <label className="text-sm text-slate-400 block mb-1">Fallback Threshold (%)</label>
        <input
          type="number"
          step="0.01"
          min="0"
          max="1"
          value={policy.fallback_threshold_pct}
          onChange={(e) => setPolicy({ ...policy, fallback_threshold_pct: parseFloat(e.target.value) })}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
        />
        <p className="text-xs text-slate-500 mt-1">Fallback to cheaper model at this % of cap (0.90 = 90%)</p>
      </div>

      <div>
        <label className="text-sm text-slate-400 block mb-1">Fallback Model</label>
        <input
          type="text"
          value={policy.fallback_model || ""}
          onChange={(e) => setPolicy({ ...policy, fallback_model: e.target.value || null })}
          placeholder="e.g., llama3.2:1b"
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={isSaving}
        className="px-4 py-2 bg-emerald-600 rounded text-sm disabled:opacity-50"
      >
        {isSaving ? "Saving..." : "Save Policy"}
      </button>
    </div>
  );
}
```

**Remove ALL instances of**:
- `className="opacity-50"` (from Cost Policy tab divs only — leave other tabs mocked for now)
- `data-mocked` attribute (from Cost Policy tab only)
- `title="Coming in Plan 89"` (from Cost Policy tab only)

**Note**: Only un-mock the Cost Policy tab. Circuit Breaker, Sandbox, and Auth tabs remain mocked (future plans).

---

## S5. Create `src/components/panels/ResourceMonitorPanel.tsx`

Real-time resource monitoring with charts:

```tsx
"use client";
import { useState, useEffect, useRef } from "react";
import { usePolling } from "@/hooks/usePolling";
import { getResourceMonitor, ResourceMonitor } from "@/lib/api";

export function ResourceMonitorPanel() {
  const { data, isLoading } = usePolling<ResourceMonitor>(getResourceMonitor, 5000);
  const [history, setHistory] = useState<ResourceMonitor[]>([]);
  const maxHistory = 60; // 5 minutes at 5s intervals

  useEffect(() => {
    if (data) {
      setHistory((prev) => [...prev.slice(-maxHistory + 1), data]);
    }
  }, [data]);

  if (isLoading || !data) {
    return <div data-testid="resource-monitor-panel" className="p-4">Loading resources...</div>;
  }

  return (
    <div data-testid="resource-monitor-panel" className="p-4 space-y-6">
      <h2 className="text-lg font-semibold">Resource Monitor</h2>

      <div className="grid grid-cols-2 gap-4">
        <ResourceCard label="CPU" value={data.cpu_percent} unit="%" max={100} history={history.map((h) => h.cpu_percent)} />
        <ResourceCard label="Memory" value={data.memory_percent} unit="%" max={100} history={history.map((h) => h.memory_percent)} />
        <ResourceCard label="Disk" value={data.disk_percent} unit="%" max={100} history={history.map((h) => h.disk_percent)} />
        {data.gpu_percent !== null && (
          <ResourceCard
            label="GPU"
            value={data.gpu_percent}
            unit="%"
            max={100}
            history={history.map((h) => h.gpu_percent || 0)}
            subtitle={`${data.gpu_memory_used_mb || 0} / ${data.gpu_memory_total_mb || 0} MB`}
          />
        )}
      </div>

      <div className="text-xs text-slate-500">
        Last updated: {new Date(data.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}

function ResourceCard({ label, value, unit, max, history, subtitle }: { label: string; value: number; unit: string; max: number; history: number[]; subtitle?: string }) {
  const pct = (value / max) * 100;
  const color = pct > 80 ? "bg-red-500" : pct > 60 ? "bg-amber-500" : "bg-emerald-500";

  // Simple sparkline using SVG
  const sparklinePoints = history.length > 1
    ? history.map((v, i) => `${(i / (history.length - 1)) * 100},${100 - (v / max) * 100}`).join(" ")
    : "";

  return (
    <div className="border border-slate-700 rounded p-3 bg-slate-900">
      <div className="flex justify-between items-start mb-2">
        <div>
          <span className="font-medium">{label}</span>
          {subtitle && <div className="text-xs text-slate-500">{subtitle}</div>}
        </div>
        <span className="text-lg font-mono">{value.toFixed(1)}{unit}</span>
      </div>
      <div className="h-2 bg-slate-800 rounded mb-2">
        <div className={`h-full rounded ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {sparklinePoints && (
        <svg viewBox="0 0 100 100" className="w-full h-8" preserveAspectRatio="none">
          <polyline points={sparklinePoints} fill="none" stroke="currentColor" strokeWidth="1" className="text-slate-400" />
        </svg>
      )}
    </div>
  );
}
```

---

## S6. Add `VIEWS.RESOURCES` to `uiStore.ts`

```typescript
export const VIEWS = {
  // ... existing views ...
  RESOURCES: "resources",  // NEW — Plan 94
} as const;
```

---

## S7. Add Resources nav item to Sidebar + routing

In `src/components/shell/Sidebar.tsx`, add:
```typescript
{ view: VIEWS.RESOURCES, label: "Resources", icon: Activity },
```
Import `Activity` from `lucide-react`.

In `src/app/page.tsx`, add:
```tsx
case VIEWS.RESOURCES:
  return <ResourceMonitorPanel />;
```

---

## S8. Add backend tests

Create `tests/test_cost_policy_api.py`:
- test_get_cost_policy
- test_update_cost_policy_partial
- test_update_cost_policy_full
- test_get_resource_monitor

Create `tests/test_resource_monitor.py`:
- test_resource_monitor_returns_cpu
- test_resource_monitor_returns_gpu_if_available
- test_resource_monitor_fallback_no_profiler

Minimum 7 new tests.

---

## S9. Add Vitest tests

Add to `src/__tests__/components.test.tsx`:
- ResourceMonitorPanel renders resource cards
- CostPolicyTab renders editable fields (not mocked)

Minimum 2 new tests.

---

## S10. Verify build

```powershell
ruff check web/server.py core/cost_tracker.py
mypy web/server.py core/cost_tracker.py --ignore-missing-imports
python -m pytest tests/test_cost_policy_api.py tests/test_resource_monitor.py -vvv
cd src && npx tsc --noEmit && npm run build
python -m pytest tests/ -vvv
cd src && npm test
```

---

## STOP condition

**Rev2 C1 fix**: The original STOP condition referenced `_policy` private attribute access, which is self-contradictory — Rev2 already added `get_policy()` public method. The vestigial STOP is removed.

If `system/profiler.py` `refresh()` signature doesn't match S0.5 verification (returns unexpected type), STOP and report. If `psutil` is not in project dependencies, STOP and add it to `txt/requirements.txt`.

---

## Files WILL create (3)
- `src/components/panels/ResourceMonitorPanel.tsx`
- `tests/test_cost_policy_api.py`
- `tests/test_resource_monitor.py`

## Files WILL edit (6)
- `core/cost_tracker.py` (add update_policy method)
- `web/server.py` (add PUT/GET /api/costs/policy, GET /api/resources/monitor)
- `core/orchestrator.py` (add system_profiler injection — if not already present)
- `src/lib/api.ts` (add getCostPolicy, updateCostPolicy, getResourceMonitor)
- `src/stores/uiStore.ts` (add VIEWS.RESOURCES)
- `src/components/shell/Sidebar.tsx` (add Resources nav item)
- `src/app/page.tsx` (add view routing)
- `src/components/panels/SettingsDrawer.tsx` (un-mock Cost Policy tab — remove opacity-50, data-mocked, wire to API)
- `src/__tests__/components.test.tsx` (add ResourceMonitorPanel + CostPolicyTab tests)

## Files will NOT edit
- `system/profiler.py` (use as-is — refresh(), get_cached())
- `core/` logic modules (except cost_tracker.update_policy and orchestrator injection)
- `memory/`, `skills/`, `adapters/`, `workers/`
- `src/components/panels/CostDashboardPanel.tsx` (already displays costs — no changes needed)
- SettingsDrawer tabs other than Cost Policy (Circuit Breaker, Sandbox, Auth remain mocked)

---

## Closing

Run `/jarvis-close`. Tag `prompt-94`. CHANGELOG entry for Plan 94. Update PLANS.md with batch completion summary.
