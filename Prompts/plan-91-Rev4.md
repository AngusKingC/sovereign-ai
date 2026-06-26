# Plan 91 â€” Model & Adapter Management (Phase 1a)

**Tag**: `prompt-91` | **Depends on**: `prompt-90`

**Rev4 â€” Post-Round-Table Adjudication (6 panel responses consolidated across Rev2+Rev3 cycles)**

**Rev2 history**: Post-Round-Table Adjudication (4 panel responses consolidated)
**Rev3 history**: Post-Round-Table Re-Review (5 panel responses consolidated)

---

## Scope

Expose the 15 LLM adapters and Model Registry via Web UI. This is Gap #1 from the UI/UX Gap Analysis (Â§3.1 â€” CRITICAL). Backend: wire `api/models.py` stubs to `system/model_registry.py` (full implementation). Frontend: create `modelStore.ts`, `ModelsPanel.tsx`. Remove the hardcoded `modelSlug` and "Coming in Plan 89" tooltip.

**Rev2 changes**: (1) Fixed route shadowing â€” static routes before parameterized. (2) Added ModelRegistry initialization step. (3) Made ModelResponse fields optional with defaults. (4) Deferred Adapter Selector dropdown to Plan 92 (api/adapters.py is Plan 92 scope). (5) Documented that StatusBar model click sets activeModelId only â€” runtime model switching is future plan scope.

**Rev4 changes**: (1) Replaced deprecated `@app.on_event("startup")` with `lifespan` context manager. (2) Added explicit "read-first-append" instruction for orchestrator.py injection. (3) StatusBar now reflects selected model from modelStore (Rev3 M1 fix).

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` Â§3.1, Â§6 Phase 1

---

## S0. Opening

S0.1. Run `/jarvis-open` â€” verifies `prompt-90` tag on origin, working copy clean on master.
S0.2. Read AGENTS.md in full. Read CONTEXT.md for domain vocabulary.
S0.3. No new AGENTS.md rules this prompt.

### S0.5. Pre-verification: Read backend API signatures (Rev2 H6/H7/H9 â€” mandatory before coding)

**Purpose**: Plans 91â€“94 wire to backend modules marked "use as-is." Verify exact signatures BEFORE writing any code to avoid STOP conditions at build time.

**Step 1**: Read `system/model_registry.py` and confirm:
- `async def list_all() -> list[ModelEntry]` exists
- `async def get(model_id: str) -> ModelEntry | None` exists
- `async def initialize(system_profile: SystemProfile | None = None) -> None` exists
- `ModelEntry` fields: `model_id`, `name`, `source`, `adapter_compatibility`, `task_tags`, `download_status`, `downloaded_quantisation`, `license`, `description`

**Step 2**: Read `system/model_acquisition.py` and confirm (for Plan 92):
- `async def request_download(...)` signature â€” is it async? What does it return?
- Does `get_download_status()` exist? (Plan 92 may need to add it)

**Step 3**: Read `core/worker_factory.py` and confirm (for Plan 93):
- `async def list_workers() -> list[WorkerProfile]` â€” returns `WorkerProfile` or `DynamicWorkerProfile`?
- `async def create_worker(description: str, task: Task) -> WorkerBase` signature

**Step 4**: Read `system/profiler.py` and confirm (for Plan 94):
- `async def refresh() -> SystemProfile` â€” returns object or dict?
- `SystemProfile` fields: `.cpu.percent`, `.ram.percent`, `.storage` (list), `.gpu`

**Step 5**: Read `core/cost_tracker.py` and confirm (for Plan 94):
- `_policy` attribute exists and is a `CostPolicy` dataclass
- `CostPolicy` fields: `daily_cap_usd`, `monthly_cap_usd`, `alert_threshold_pct`, `fallback_threshold_pct`, `fallback_model`, `enable_traces`

**Document findings**: Write a "Backend API Verification" note in the plan's working notes. If any signature differs from assumptions, adapt the plan steps accordingly BEFORE coding. This eliminates reactive STOP conditions.

---

## S1. Wire `api/models.py` stubs to ModelRegistry

The stubs were created in Plan 90. Replace the stub implementations with real calls to `system/model_registry.py`.

**Step 1**: Read `api/models.py` (stub) and `system/model_registry.py` (full API). Verify signatures per S0.5.

**Step 2**: Replace stubs in `api/models.py`. **Rev2 H1 fix â€” route order matters**: static routes (`/search`, `/download`, `/download/{id}/status` in Plan 92) MUST be defined BEFORE the parameterized `/{model_id}` route, or FastAPI captures them as model_id values.

```python
"""API router for model registry endpoints.
Wired to system.model_registry.ModelRegistry in Plan 91.
Rev2 H1 fix: static routes defined before parameterized routes.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Any
from pydantic import BaseModel

router = APIRouter(prefix="/api/models", tags=["models"])


# Rev2 H13 fix â€” fields made optional with defaults to avoid ValidationError
# if ModelEntry doesn't populate them.
class ModelResponse(BaseModel):
    """API response model for a single model."""
    model_id: str
    name: str
    source: str = ""
    adapter_compatibility: list[str] = []
    task_tags: list[str] = []
    download_status: str = "unknown"
    downloaded_quantisation: str | None = None
    license: str = ""
    description: str = ""


def _entry_to_response(entry) -> ModelResponse:
    """Convert ModelEntry to API response. Uses getattr defaults for safety."""
    def _safe_attr(obj, attr, default=None):
        val = getattr(obj, attr, default)
        if hasattr(val, 'value'):  # Enum
            return val.value
        return val if val is not None else default

    return ModelResponse(
        model_id=entry.model_id,
        name=entry.name,
        source=_safe_attr(entry, 'source', ''),
        adapter_compatibility=getattr(entry, 'adapter_compatibility', []),
        task_tags=getattr(entry, 'task_tags', []),
        download_status=_safe_attr(entry, 'download_status', 'unknown'),
        downloaded_quantisation=getattr(entry, 'downloaded_quantisation', None),
        license=getattr(entry, 'license', ''),
        description=getattr(entry, 'description', ''),
    )


# Rev2 H1 fix â€” /search MUST come before /{model_id}
@router.get("/search")
async def search_models(query: str = "", registry=Depends(get_model_registry)) -> list[ModelResponse]:
    """Search models by name, tag, or adapter compatibility.
    Note: This searches the LOCAL registry only. HuggingFace/Ollama search
    is Plan 92 scope (Model Downloader).
    """
    all_models = await registry.list_all()
    if not query:
        return [_entry_to_response(e) for e in all_models]

    query_lower = query.lower()
    filtered = [
        e for e in all_models
        if query_lower in e.name.lower()
        or query_lower in e.model_id.lower()
        or any(query_lower in tag.lower() for tag in getattr(e, 'task_tags', []))
        or any(query_lower in adapter.lower() for adapter in getattr(e, 'adapter_compatibility', []))
    ]
    return [_entry_to_response(e) for e in filtered]


# Rev2 H1 fix â€” /{model_id} MUST come AFTER all static routes
@router.get("")
async def list_models(registry=Depends(get_model_registry)) -> list[ModelResponse]:
    """List all registered models."""
    entries = await registry.list_all()
    return [_entry_to_response(e) for e in entries]


@router.get("/{model_id}")
async def get_model(model_id: str, registry=Depends(get_model_registry)) -> ModelResponse:
    """Get model details by ID."""
    entry = await registry.get(model_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return _entry_to_response(entry)
```

**Step 3**: Add `get_model_registry` dependency to `web/server.py`:

```python
# In web/server.py, add a dependency provider:
def get_model_registry():
    """Dependency: return the orchestrator's model registry.
    Raises 503 if model registry is not configured.
    """
    if not orchestrator or not hasattr(orchestrator, 'model_registry') or not orchestrator.model_registry:
        raise HTTPException(status_code=503, detail="Model registry not configured")
    return orchestrator.model_registry
```

**Step 4** (Rev2 H6 fix â€” MANDATORY): Verify the orchestrator has a `model_registry` attribute. If not, add it to `core/orchestrator.py` as an optional injection.

**Rev2 H1 fix â€” read-first-append pattern**: Read `core/orchestrator.py` FIRST. Find the existing `__init__` constructor. APPEND `model_registry` to the existing parameter list â€” do NOT replace the constructor. If the constructor already has optional parameters (`approval_gate`, `worker_circuit_breaker`, etc.), add `model_registry` after them.

```python
# In Orchestrator.__init__ signature (APPEND to existing â€” Rev2 H1 fix):
model_registry: Optional["ModelRegistry"] = None,

# In __init__ body (APPEND to existing â€” Rev2 H1 fix):
self.model_registry = model_registry
```

**Step 5** (Rev2 H6 fix â€” MANDATORY): Add ModelRegistry initialization to `web/server.py` startup. Without this, `list_all()` returns 0 models and Plan 91 appears broken.

**Rev2 N1 fix**: Use `lifespan` context manager instead of deprecated `@app.on_event("startup")`.

```python
# In web/server.py â€” use lifespan pattern (FastAPI >= 0.93, Starlette >= 0.20)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if orchestrator and orchestrator.model_registry:
        try:
            system_profile = None
            if orchestrator.system_profiler:
                system_profile = await orchestrator.system_profiler.refresh()
            await orchestrator.model_registry.initialize(system_profile)
            logger.info("Model registry initialized")
        except Exception as e:
            logger.error(f"Failed to initialize model registry: {e}")
    yield
    # Shutdown (if needed in future plans)

# When creating the app:
app = FastAPI(lifespan=lifespan)
```

**Note**: If the app already uses `@app.on_event("startup")` for other initialization (e.g., Telegram polling from Plan 89), migrate ALL startup events to the `lifespan` pattern in one edit. Do NOT mix patterns.

**Step 6**: Update the stub tests in `tests/test_api_stubs.py` to expect real responses:

```python
def test_list_models_returns_list(client_no_auth):
    res = client_no_auth.get("/api/models")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_get_model_404_for_nonexistent(client_no_auth):
    res = client_no_auth.get("/api/models/nonexistent")
    assert res.status_code == 404

def test_search_models_filters_by_query(client_no_auth):
    res = client_no_auth.get("/api/models/search?query=code")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

# Rev2 H1 fix â€” verify /search is not captured by /{model_id}
def test_search_route_not_shadowed(client_no_auth):
    """Verify /api/models/search returns 200, not 404 (which would indicate
    /{model_id} captured 'search' as a model_id)."""
    res = client_no_auth.get("/api/models/search?query=test")
    assert res.status_code == 200
```

**STOP condition**: If `ModelRegistry.list_all()` still returns 0 models after S0.5 verification and S5 initialization, STOP â€” the registry's seed data may be missing. Report to user.

---

## S2. Create `src/stores/modelStore.ts`

New Zustand store for model state:

```typescript
import { create } from "zustand";

export interface ModelInfo {
  model_id: string;
  name: string;
  source: string;
  adapter_compatibility: string[];
  task_tags: string[];
  download_status: string;
  downloaded_quantisation: string | null;
  license: string;
  description: string;
}

interface ModelState {
  models: ModelInfo[];
  activeModelId: string | null;
  searchQuery: string;
  filterTag: string | null;
  filterAdapter: string | null;
  isLoading: boolean;
  error: string | null;
  setModels: (models: ModelInfo[]) => void;
  setActiveModel: (modelId: string) => void;
  setSearchQuery: (query: string) => void;
  setFilterTag: (tag: string | null) => void;
  setFilterAdapter: (adapter: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useModelStore = create<ModelState>((set) => ({
  models: [],
  activeModelId: null,
  searchQuery: "",
  filterTag: null,
  filterAdapter: null,
  isLoading: false,
  error: null,
  setModels: (models) => set({ models }),
  setActiveModel: (modelId) => set({ activeModelId: modelId }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setFilterTag: (tag) => set({ filterTag: tag }),
  setFilterAdapter: (adapter) => set({ filterAdapter: adapter }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));
```

---

## S3. Add API functions to `src/lib/api.ts`

```typescript
export interface ModelInfo {
  model_id: string;
  name: string;
  source: string;
  adapter_compatibility: string[];
  task_tags: string[];
  download_status: string;
  downloaded_quantisation: string | null;
  license: string;
  description: string;
}

export async function getModels(): Promise<ModelInfo[]> {
  const res = await fetch(`/api/models`);
  if (!res.ok) throw new Error(`Models ${res.status}`);
  return res.json();
}

export async function getModel(modelId: string): Promise<ModelInfo> {
  const res = await fetch(`/api/models/${modelId}`);
  if (!res.ok) throw new Error(`Model ${res.status}`);
  return res.json();
}

export async function searchModels(query: string): Promise<ModelInfo[]> {
  const res = await fetch(`/api/models/search?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Search ${res.status}`);
  return res.json();
}
```

---

## S4. Create `src/components/panels/ModelsPanel.tsx`

Model browser panel with filtering, compatibility badges, and model selection:

```tsx
"use client";
import { useState, useMemo } from "react";
import { usePolling } from "@/hooks/usePolling";
import { getModels, ModelInfo } from "@/lib/api";
import { useModelStore } from "@/stores/modelStore";

export function ModelsPanel() {
  const { data, isLoading } = usePolling<ModelInfo[]>(getModels, 30000);
  const { activeModelId, setActiveModel, setSearchQuery, searchQuery, filterTag, setFilterTag, filterAdapter, setFilterAdapter } = useModelStore();
  const [localSearch, setLocalSearch] = useState("");

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((m) => {
      if (localSearch && !m.name.toLowerCase().includes(localSearch.toLowerCase()) && !m.model_id.toLowerCase().includes(localSearch.toLowerCase())) return false;
      if (filterTag && !m.task_tags.includes(filterTag)) return false;
      if (filterAdapter && !m.adapter_compatibility.includes(filterAdapter)) return false;
      return true;
    });
  }, [data, localSearch, filterTag, filterAdapter]);

  const allTags = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.flatMap((m) => m.task_tags))].sort();
  }, [data]);

  const allAdapters = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.flatMap((m) => m.adapter_compatibility))].sort();
  }, [data]);

  if (isLoading || !data) {
    return <div data-testid="models-panel" className="p-4">Loading models...</div>;
  }

  return (
    <div data-testid="models-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">Models</h2>

      <div className="space-y-2">
        <input
          type="text"
          placeholder="Search models..."
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
        />
        <div className="flex gap-2">
          <select
            value={filterTag || ""}
            onChange={(e) => setFilterTag(e.target.value || null)}
            className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs"
          >
            <option value="">All tags</option>
            {allTags.map((tag) => <option key={tag} value={tag}>{tag}</option>)}
          </select>
          <select
            value={filterAdapter || ""}
            onChange={(e) => setFilterAdapter(e.target.value || null)}
            className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs"
          >
            <option value="">All adapters</option>
            {allAdapters.map((adapter) => <option key={adapter} value={adapter}>{adapter}</option>)}
          </select>
        </div>
      </div>

      <div className="space-y-2">
        {filtered.length === 0 && <p className="text-slate-500 text-sm">No models found.</p>}
        {filtered.map((model) => (
          <div
            key={model.model_id}
            className={`border rounded p-3 cursor-pointer ${
              activeModelId === model.model_id
                ? "border-amber-500 bg-amber-950/20"
                : "border-slate-700 bg-slate-900 hover:border-slate-600"
            }`}
            onClick={() => setActiveModel(model.model_id)}
          >
            <div className="flex justify-between items-start">
              <div>
                <span className="font-medium">{model.name}</span>
                <span className="ml-2 text-xs text-slate-500 font-mono">{model.model_id}</span>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${
                model.download_status === "downloaded" ? "bg-emerald-900" : "bg-slate-700"
              }`}>
                {model.download_status}
              </span>
            </div>
            <div className="flex gap-1 mt-2 flex-wrap">
              {model.task_tags.map((tag) => (
                <span key={tag} className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">{tag}</span>
              ))}
            </div>
            <div className="flex gap-1 mt-1 flex-wrap">
              {model.adapter_compatibility.map((adapter) => (
                <span key={adapter} className="text-xs px-1.5 py-0.5 bg-blue-900/30 rounded">{adapter}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## S5. Update `src/stores/uiStore.ts` â€” add MODELS view

```typescript
export const VIEWS = {
  HOME: "home",
  TASKS: "tasks",
  WORKERS: "workers",
  APPROVALS: "approvals",
  COSTS: "costs",
  TOOLS: "tools",
  HELP: "help",
  TERMINAL: "terminal",
  SYSTEM: "system",
  SUBAGENTS: "subagents",
  MODELS: "models",  // NEW â€” Plan 91
} as const;
```

---

## S6. Update `src/components/shell/Sidebar.tsx` â€” add Models nav item

Add to NAV_ITEMS array (after Subagents, before drawer buttons):
```typescript
{ view: VIEWS.MODELS, label: "Models", icon: Boxes },
```

Import `Boxes` from `lucide-react`.

---

## S7. Update `src/app/page.tsx` â€” add view routing

Add to the switch statement:
```tsx
case VIEWS.MODELS:
  return <ModelsPanel />;
```

Import `ModelsPanel` at top of file.

---

## S8. Update `src/components/shell/StatusBar.tsx` â€” wire model selector

**Rev2 H15 fix**: The Adapter Selector dropdown is deferred to Plan 92 (api/adapters.py is Plan 92 scope). Plan 91 only makes the model slug clickable to navigate to ModelsPanel.

**Rev2 H16 documentation**: Setting `activeModelId` in `modelStore` is the UI contract. Actual runtime model switching (changing which LLM the orchestrator uses) is **future plan scope** â€” Plan 91 only establishes the selection UI. Do not claim runtime switching works.

**Rev3 M1 fix**: StatusBar should display the selected model from `modelStore.activeModelId` (if set) instead of the hardcoded `agentStore.modelSlug`. This provides visual feedback that a selection was made, even though runtime switching is deferred. If no model is selected in `modelStore`, fall back to `agentStore.modelSlug`.

Replace the hardcoded model button with a click that opens ModelsPanel and reflects the selected model:

```tsx
// Replace the existing model button:
import { useModelStore } from "@/stores/modelStore";  // Add this import

const { modelSlug } = useAgentStore();
const { activeModelId, models } = useModelStore();  // Rev3 M1 fix
const { setActiveView } = useUiStore();

// Rev3 M1 fix â€” show selected model name if activeModelId is set, otherwise show modelSlug
const displayName = activeModelId
  ? models.find((m) => m.model_id === activeModelId)?.name || modelSlug
  : modelSlug;

// In the JSX, replace the button:
<button
  className="font-mono text-xs text-text-secondary hover:text-text-primary"
  onClick={() => setActiveView(VIEWS.MODELS)}
  aria-label="Browse models"
  title="Click to browse and select models"
>
  {displayName}
</button>
```

Remove the `title="Coming in Plan 89"` tooltip â€” it's now functional (opens ModelsPanel).

**Note**: The Adapter Selector dropdown (switching between Ollama/OpenAI/Anthropic/etc.) is **Plan 92 scope** â€” it requires `api/adapters.py` which doesn't exist yet. Do not build the dropdown in Plan 91.

---

## S9. Add Vitest tests

Add to `src/__tests__/stores.test.ts`:
```typescript
describe("modelStore", () => {
  it("sets models", () => { /* ... */ });
  it("sets active model", () => { /* ... */ });
  it("sets search query", () => { /* ... */ });
  it("sets filter tag", () => { /* ... */ });
});
```

Add to `src/__tests__/components.test.tsx`:
```typescript
describe("ModelsPanel", () => {
  it("renders models list", () => { /* ... */ });
  it("filters by search query", () => { /* ... */ });
  it("filters by tag", () => { /* ... */ });
});
```

Minimum 7 new tests.

---

## S10. Verify build

```powershell
# Python
ruff check api/models.py web/server.py
mypy api/models.py web/server.py --ignore-missing-imports
python -m pytest tests/test_api_stubs.py -vvv

# TypeScript
cd src && npx tsc --noEmit && npm run build

# Full test suite
python -m pytest tests/ -vvv
cd src && npm test
```

---

## STOP condition

If `npx tsc --noEmit` reports errors, STOP and fix. If `npm run build` fails, STOP and fix. If `ModelRegistry.list_all()` returns 0 models, STOP â€” registry not initialized.

---

## Files WILL create (2)
- `src/stores/modelStore.ts`
- `src/components/panels/ModelsPanel.tsx`

## Files WILL edit (6)
- `api/models.py` (wire stubs to ModelRegistry)
- `web/server.py` (add get_model_registry dependency)
- `core/orchestrator.py` (add model_registry optional injection â€” if not already present)
- `src/stores/uiStore.ts` (add VIEWS.MODELS)
- `src/components/shell/Sidebar.tsx` (add Models nav item)
- `src/app/page.tsx` (add view routing)
- `src/components/shell/StatusBar.tsx` (wire model selector, remove "Coming in Plan 89")
- `src/lib/api.ts` (add getModels, getModel, searchModels functions)
- `tests/test_api_stubs.py` (update stub tests for real responses)
- `src/__tests__/stores.test.ts` (add modelStore tests)
- `src/__tests__/components.test.tsx` (add ModelsPanel tests)

## Files will NOT edit
- `system/model_registry.py` (use as-is)
- `system/model_acquisition.py` (Plan 92 scope)
- `core/adapter_fallback.py` (Plan 92 scope)
- `core/` logic modules (except orchestrator injection)
- `memory/`, `skills/`, `adapters/`, `workers/`

---

## Closing

Run `/jarvis-close`. Tag `prompt-91`. CHANGELOG entry for Plan 91. Update PLANS.md.
