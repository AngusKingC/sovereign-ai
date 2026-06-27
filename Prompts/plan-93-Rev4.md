# Plan 93 — Worker Creation & Configuration (Phase 2)

**Tag**: `prompt-93` | **Depends on**: `prompt-92`

**Rev4 — Post-Round-Table Adjudication (6 panel responses consolidated across Rev2+Rev3 cycles)**

**Rev2 history**: Post-Round-Table Adjudication (4 panel responses consolidated)
**Rev3 history**: Post-Round-Table Re-Review (5 panel responses consolidated)

---

## Scope

Enable worker creation from natural language descriptions via UI. This is Gap #2 from the UI/UX Gap Analysis (§3.2 — CRITICAL). Backend: wire `api/workers.py` stubs to `core/worker_factory.py` (full implementation). Frontend: `WorkerCreator.tsx`, Worker Editor modal, Worker Detail View.

**Rev2 changes**: (1) Fixed Pydantic v2 `.dict()` → `.model_dump()`. (2) Added WorkerFactory.list_workers() return type pre-verification. (3) Use uuid4 for task_id instead of brittle description prefix. (4) Added worker persistence note.

**Rev4 changes**: (1) Added async I/O + atomic write for JSON persistence (Rev3 H1 fix). (2) Applied persistence to update_worker (Rev3 H2 fix). (3) Added safe profile-to-dict normalization.

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §3.2, §6 Phase 2

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-92` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

### S0.5. Pre-verification: WorkerFactory signatures (Rev2 H9 — mandatory)

**Step 1**: Read `core/worker_factory.py` and confirm:
- `async def list_workers() -> list[WorkerProfile]` — does it return `WorkerProfile` or `DynamicWorkerProfile`?
- `async def create_worker(description: str, task: Task) -> WorkerBase` — exact signature
- `async def deregister_worker(worker_id: str) -> None` — exact signature
- Does the factory have `_persistence` attribute for saving workers?

**Step 2**: Read `core/worker_base.py` and confirm:
- Does `WorkerBase` have a `.profile` attribute, or is the profile passed separately?
- What fields does `WorkerProfile` (base) have vs `DynamicWorkerProfile` (extended)?

**Step 3**: Read `system/worker_persistence.py` and confirm:
- Is worker persistence wired? Does `WorkerFactory` call `save_worker()` on creation?
- If not, workers are volatile across restarts — document this as a known gap.

**Step 4**: If `list_workers()` returns `WorkerProfile` (not `DynamicWorkerProfile`), adapt the response converter to use defaults for extended fields (`complexity_min=0.0`, `verbosity=0.5`, etc.).

**Step 5** (Rev2 M1 fix — worker persistence): If S0.5 Step 3 finds that `WorkerFactory` does NOT call `save_worker()` on creation, workers are volatile across restarts. This is a data-loss UX issue — users create workers via the UI, restart the server, and all workers disappear.

**Fix**: Add a minimal JSON-file persistence layer if `system/worker_persistence.py` is not wired.

**Rev3 H1 fix**: Use `asyncio.to_thread` for file I/O (was blocking event loop) and atomic write (write to temp file, then rename) to prevent corruption from concurrent writes.

```python
# In core/worker_factory.py __init__, add (if not already present):
import json
import asyncio
import tempfile
from pathlib import Path

class WorkerFactory:
    def __init__(self, ..., persistence=None):
        # ... existing init ...
        self._persistence = persistence
        # Rev2 M1 fix — fallback JSON persistence if no DB persistence wired
        self._json_persistence_path = Path("data/workers.json")
        self._json_persistence_path.parent.mkdir(exist_ok=True)

    async def create_worker(self, description: str, task: Task) -> WorkerBase:
        worker = await self._create_worker_internal(description, task)
        # Rev2 M1 fix — persist worker
        if self._persistence:
            await self._persistence.save_worker(worker.profile)
        else:
            await self._save_to_json(worker.profile)
        return worker

    async def _save_to_json(self, profile):
        """Minimal JSON persistence fallback. Rev3 H1 fix — async I/O + atomic write."""
        # Rev3 H1 fix — normalize profile to dict safely
        if hasattr(profile, 'model_dump'):
            profile_dict = profile.model_dump()
        elif hasattr(profile, 'dict'):
            profile_dict = profile.dict()
        elif isinstance(profile, dict):
            profile_dict = profile
        else:
            profile_dict = dict(profile)

        # Rev3 H1 fix — run blocking file I/O in thread pool
        def _write_atomic():
            workers = []
            if self._json_persistence_path.exists():
                workers = json.loads(self._json_persistence_path.read_text(encoding='utf-8'))
            workers.append(profile_dict)
            # Rev3 H1 fix — atomic write: write to temp file, then rename
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=str(self._json_persistence_path.parent),
                suffix='.tmp',
                delete=False,
                encoding='utf-8'
            ) as tmp:
                json.dump(workers, tmp, default=str, indent=2)
                tmp_path = Path(tmp.name)
            tmp_path.replace(self._json_persistence_path)  # Atomic on POSIX, near-atomic on Windows

        await asyncio.to_thread(_write_atomic)

    async def _load_from_json(self) -> list:
        """Load workers from JSON on startup. Rev3 H1 fix — async I/O."""
        def _read():
            if not self._json_persistence_path.exists():
                return []
            return json.loads(self._json_persistence_path.read_text(encoding='utf-8'))
        return await asyncio.to_thread(_read)
```

**Note**: If `system/worker_persistence.py` IS wired (DB-backed), skip this step. The JSON fallback is only for environments without Postgres. Add `data/workers.json` to `.gitignore`.

---

## S1. Wire `api/workers.py` stubs to WorkerFactory

Replace stubs in `api/workers.py`:

```python
"""API router for worker CRUD endpoints.
Wired to core.worker_factory.WorkerFactory in Plan 93.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/workers", tags=["workers"])


class CreateWorkerRequest(BaseModel):
    """Request to create a worker from natural language description."""
    description: str
    task_intent: str = ""  # Optional: the task the worker will handle


class WorkerProfileResponse(BaseModel):
    """API response model for a worker profile."""
    worker_id: str
    worker_type: str
    name: str
    description: str
    purpose: str
    capabilities: list[str]
    complexity_min: float
    complexity_max: float
    preferred_complexity: float
    depth_preference: float
    speculation_tolerance: float
    source_skepticism: float
    verbosity: float
    standing_instructions: list[str]
    preferred_model: str
    preferred_models: list[str]
    escalation_threshold: float
    tasks_completed: int
    avg_confidence: float
    performance_score: float
    active_tasks: int
    status: str


class UpdateWorkerRequest(BaseModel):
    """Request to update worker configuration."""
    complexity_min: float | None = None
    complexity_max: float | None = None
    preferred_complexity: float | None = None
    depth_preference: float | None = None
    speculation_tolerance: float | None = None
    source_skepticism: float | None = None
    verbosity: float | None = None
    standing_instructions: list[str] | None = None
    preferred_model: str | None = None
    preferred_models: list[str] | None = None
    escalation_threshold: float | None = None


def _profile_to_response(profile) -> WorkerProfileResponse:
    """Convert DynamicWorkerProfile to API response."""
    return WorkerProfileResponse(
        worker_id=profile.worker_id,
        worker_type=profile.worker_type,
        name=profile.name,
        description=profile.description,
        purpose=profile.purpose,
        capabilities=profile.capabilities,
        complexity_min=profile.complexity_min,
        complexity_max=profile.complexity_max,
        preferred_complexity=profile.preferred_complexity,
        depth_preference=profile.depth_preference,
        speculation_tolerance=profile.speculation_tolerance,
        source_skepticism=profile.source_skepticism,
        verbosity=profile.verbosity,
        standing_instructions=profile.standing_instructions,
        preferred_model=profile.preferred_model,
        preferred_models=profile.preferred_models,
        escalation_threshold=profile.escalation_threshold,
        tasks_completed=profile.tasks_completed,
        avg_confidence=profile.avg_confidence,
        performance_score=profile.performance_score,
        active_tasks=profile.active_tasks,
        status=profile.status.value if hasattr(profile.status, 'value') else str(profile.status),
    )


@router.post("/create")
async def create_worker(
    request: CreateWorkerRequest,
    factory=Depends(get_worker_factory),
) -> WorkerProfileResponse:
    """Create a worker from natural language description."""
    from core.schemas import Task
    from uuid import uuid4  # Rev2 H14 fix — use uuid4 instead of brittle description prefix

    task = Task(
        task_id=f"create-{uuid4().hex[:8]}",  # Rev2 H14 fix — was f"create-{request.description[:20]}" which could contain whitespace/special chars
        intent=request.task_intent or request.description,
        session_id="worker-creation",
    )
    try:
        worker = await factory.create_worker(request.description, task)
        # Return the profile (worker may have a .profile attribute or be the profile itself)
        profile = getattr(worker, 'profile', worker)
        return _profile_to_response(profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Worker creation failed: {e}")


@router.get("")
async def list_workers(factory=Depends(get_worker_factory)) -> list[WorkerProfileResponse]:
    """List all registered workers."""
    profiles = await factory.list_workers()
    return [_profile_to_response(p) for p in profiles]


@router.get("/{worker_id}")
async def get_worker(worker_id: str, factory=Depends(get_worker_factory)) -> WorkerProfileResponse:
    """Get worker details by ID."""
    profiles = await factory.list_workers()
    for p in profiles:
        if p.worker_id == worker_id:
            return _profile_to_response(p)
    raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")


@router.put("/{worker_id}")
async def update_worker(
    worker_id: str,
    request: UpdateWorkerRequest,
    factory=Depends(get_worker_factory),
) -> WorkerProfileResponse:
    """Update worker configuration."""
    profiles = await factory.list_workers()
    profile = next((p for p in profiles if p.worker_id == worker_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")

    # Rev2 H4 fix — use model_dump() for Pydantic v2 (was .dict() which raises AttributeError in v2)
    try:
        update_data = request.model_dump(exclude_none=True)
    except AttributeError:
        # Fallback for Pydantic v1
        update_data = request.dict(exclude_none=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    # Rev3 H2 fix — persist the updated profile (was only persisting on create, not update)
    if hasattr(factory, '_persistence') and factory._persistence:
        await factory._persistence.save_worker(profile)
    elif hasattr(factory, '_save_to_json'):
        # Rev3 H2 fix — use the JSON fallback persistence for updates too
        await factory._save_to_json(profile)

    return _profile_to_response(profile)


@router.delete("/{worker_id}")
async def delete_worker(worker_id: str, factory=Depends(get_worker_factory)) -> dict[str, Any]:
    """Delete/deregister a worker."""
    try:
        await factory.deregister_worker(worker_id)
        return {"status": "deleted", "worker_id": worker_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Worker deletion failed: {e}")
```

**Step 2**: Add `get_worker_factory` dependency to `web/server.py`:

```python
def get_worker_factory():
    if not orchestrator or not hasattr(orchestrator, 'worker_factory') or not orchestrator.worker_factory:
        raise HTTPException(status_code=503, detail="Worker factory not configured")
    return orchestrator.worker_factory
```

**Step 3**: Verify `orchestrator.worker_factory` exists. If not, add as optional injection.

---

## S2. Add API functions to `src/lib/api.ts`

```typescript
export interface WorkerProfile {
  worker_id: string;
  worker_type: string;
  name: string;
  description: string;
  purpose: string;
  capabilities: string[];
  complexity_min: number;
  complexity_max: number;
  preferred_complexity: number;
  depth_preference: number;
  speculation_tolerance: number;
  source_skepticism: number;
  verbosity: number;
  standing_instructions: string[];
  preferred_model: string;
  preferred_models: string[];
  escalation_threshold: number;
  tasks_completed: number;
  avg_confidence: number;
  performance_score: number;
  active_tasks: number;
  status: string;
}

export async function createWorker(description: string, taskIntent: string = ""): Promise<WorkerProfile> {
  const res = await fetch(`/api/workers/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, task_intent: taskIntent }),
  });
  if (!res.ok) throw new Error(`Create ${res.status}`);
  return res.json();
}

export async function getWorkers(): Promise<WorkerProfile[]> {
  const res = await fetch(`/api/workers`);
  if (!res.ok) throw new Error(`Workers ${res.status}`);
  return res.json();
}

export async function getWorker(workerId: string): Promise<WorkerProfile> {
  const res = await fetch(`/api/workers/${workerId}`);
  if (!res.ok) throw new Error(`Worker ${res.status}`);
  return res.json();
}

export async function updateWorker(workerId: string, config: Partial<WorkerProfile>): Promise<WorkerProfile> {
  const res = await fetch(`/api/workers/${workerId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(`Update ${res.status}`);
  return res.json();
}

export async function deleteWorker(workerId: string): Promise<void> {
  const res = await fetch(`/api/workers/${workerId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete ${res.status}`);
}
```

---

## S3. Extend `src/stores/workerStore.ts`

Add creation/editing actions:

```typescript
// Add to existing workerStore:
import { createWorker, updateWorker, deleteWorker, WorkerProfile } from "@/lib/api";

interface WorkerState {
  // ... existing fields ...
  createWorker: (description: string, taskIntent?: string) => Promise<void>;
  updateWorker: (workerId: string, config: Partial<WorkerProfile>) => Promise<void>;
  deleteWorker: (workerId: string) => Promise<void>;
  selectedWorkerId: string | null;
  setSelectedWorker: (id: string | null) => void;
}

// Add to store implementation:
createWorker: async (description, taskIntent = "") => {
  const worker = await createWorker(description, taskIntent);
  set((s) => ({ workers: [...s.workers, worker] }));
},
updateWorker: async (workerId, config) => {
  const updated = await updateWorker(workerId, config);
  set((s) => ({
    workers: s.workers.map((w) => w.worker_id === workerId ? updated : w),
  }));
},
deleteWorker: async (workerId) => {
  await deleteWorker(workerId);
  set((s) => ({ workers: s.workers.filter((w) => w.worker_id !== workerId) }));
},
selectedWorkerId: null,
setSelectedWorker: (id) => set({ selectedWorkerId: id }),
```

---

## S4. Create `src/components/panels/WorkerCreator.tsx`

Modal for creating workers from natural language:

```tsx
"use client";
import { useState } from "react";
import { useWorkerStore } from "@/stores/workerStore";

export function WorkerCreator({ onClose }: { onClose: () => void }) {
  const { createWorker } = useWorkerStore();
  const [description, setDescription] = useState("");
  const [taskIntent, setTaskIntent] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!description.trim()) return;
    setIsCreating(true);
    setError(null);
    try {
      await createWorker(description, taskIntent);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creation failed");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="worker-creator">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-lg">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Create Worker</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm text-slate-400 block mb-1">Description (natural language)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Create a Python code review worker that focuses on security and performance"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm h-24 resize-none"
            />
          </div>

          <div>
            <label className="text-sm text-slate-400 block mb-1">Task intent (optional)</label>
            <input
              type="text"
              value={taskIntent}
              onChange={(e) => setTaskIntent(e.target.value)}
              placeholder="What task will this worker handle?"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="px-4 py-2 bg-slate-700 rounded text-sm">Cancel</button>
            <button
              onClick={handleCreate}
              disabled={isCreating || !description.trim()}
              className="px-4 py-2 bg-emerald-600 rounded text-sm disabled:opacity-50"
            >
              {isCreating ? "Creating..." : "Create Worker"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## S5. Create `src/components/panels/WorkerEditor.tsx`

Modal for editing worker configuration:

```tsx
"use client";
import { useState, useEffect } from "react";
import { useWorkerStore } from "@/stores/workerStore";
import { WorkerProfile } from "@/lib/api";

export function WorkerEditor({ worker, onClose }: { worker: WorkerProfile; onClose: () => void }) {
  const { updateWorker, deleteWorker } = useWorkerStore();
  const [config, setConfig] = useState({
    complexity_min: worker.complexity_min,
    complexity_max: worker.complexity_max,
    preferred_complexity: worker.preferred_complexity,
    depth_preference: worker.depth_preference,
    verbosity: worker.verbosity,
    preferred_model: worker.preferred_model,
    standing_instructions: worker.standing_instructions.join("\n"),
  });
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateWorker(worker.worker_id, {
        ...config,
        standing_instructions: config.standing_instructions.split("\n").filter(Boolean),
      });
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete worker "${worker.name}"?`)) return;
    await deleteWorker(worker.worker_id);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="worker-editor">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Edit {worker.name}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        <div className="space-y-4">
          <SliderField label="Complexity Min" value={config.complexity_min} min={0} max={1} step={0.1} onChange={(v) => setConfig({ ...config, complexity_min: v })} />
          <SliderField label="Complexity Max" value={config.complexity_max} min={0} max={1} step={0.1} onChange={(v) => setConfig({ ...config, complexity_max: v })} />
          <SliderField label="Preferred Complexity" value={config.preferred_complexity} min={0} max={1} step={0.1} onChange={(v) => setConfig({ ...config, preferred_complexity: v })} />
          <SliderField label="Depth Preference" value={config.depth_preference} min={0} max={1} step={0.1} onChange={(v) => setConfig({ ...config, depth_preference: v })} />
          <SliderField label="Verbosity" value={config.verbosity} min={0} max={1} step={0.1} onChange={(v) => setConfig({ ...config, verbosity: v })} />

          <div>
            <label className="text-sm text-slate-400 block mb-1">Preferred Model</label>
            <input
              type="text"
              value={config.preferred_model}
              onChange={(e) => setConfig({ ...config, preferred_model: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            />
          </div>

          <div>
            <label className="text-sm text-slate-400 block mb-1">Standing Instructions (one per line)</label>
            <textarea
              value={config.standing_instructions}
              onChange={(e) => setConfig({ ...config, standing_instructions: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm h-24 resize-none"
            />
          </div>

          <div className="flex justify-between gap-2">
            <button onClick={handleDelete} className="px-4 py-2 bg-red-600 rounded text-sm">Delete Worker</button>
            <div className="flex gap-2">
              <button onClick={onClose} className="px-4 py-2 bg-slate-700 rounded text-sm">Cancel</button>
              <button onClick={handleSave} disabled={isSaving} className="px-4 py-2 bg-emerald-600 rounded text-sm disabled:opacity-50">
                {isSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SliderField({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="text-sm text-slate-400 block mb-1">{label}: {value.toFixed(2)}</label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
    </div>
  );
}
```

---

## S6. Update `src/components/panels/WorkersPanel.tsx`

Add Create button and Worker Detail View:

```tsx
// Add imports:
import { WorkerCreator } from "./WorkerCreator";
import { WorkerEditor } from "./WorkerEditor";
import { useWorkerStore } from "@/stores/workerStore";

// Add state:
const [showCreator, setShowCreator] = useState(false);
const [editingWorker, setEditingWorker] = useState<WorkerProfile | null>(null);
const { workers } = useWorkerStore();

// Add "Create Worker" button in the header:
<button onClick={() => setShowCreator(true)} className="px-3 py-1 bg-emerald-600 rounded text-sm">
  + Create Worker
</button>

// Make each worker card clickable to open editor:
<div
  key={worker.id}
  onClick={() => setEditingWorker(worker)}
  className="... cursor-pointer hover:border-slate-600"
>
  {/* ... existing card content ... */}
</div>

// Add at end of component:
{showCreator && <WorkerCreator onClose={() => setShowCreator(false)} />}
{editingWorker && <WorkerEditor worker={editingWorker} onClose={() => setEditingWorker(null)} />}
```

---

## S7. Add backend tests

Create `tests/test_worker_api.py`:
- test_create_worker_from_description
- test_list_workers
- test_get_worker_by_id
- test_get_worker_404_for_nonexistent
- test_update_worker_config
- test_delete_worker

Minimum 6 new tests.

---

## S8. Add Vitest tests

Add to `src/__tests__/components.test.tsx`:
- WorkerCreator renders form
- WorkerEditor renders config fields
- WorkersPanel shows create button

Minimum 3 new tests.

---

## S9. Verify build

```powershell
ruff check api/workers.py web/server.py
mypy api/workers.py --ignore-missing-imports
python -m pytest tests/test_worker_api.py -vvv
cd src && npx tsc --noEmit && npm run build
python -m pytest tests/ -vvv
cd src && npm test
```

---

## STOP condition

If `WorkerFactory.create_worker()` signature doesn't match `(description: str, task: Task)`, STOP and report. If `factory.list_workers()` returns `WorkerProfile` objects instead of `DynamicWorkerProfile`, adapt the response converter.

---

## Files WILL create (3)
- `src/components/panels/WorkerCreator.tsx`
- `src/components/panels/WorkerEditor.tsx`
- `tests/test_worker_api.py`

## Files WILL edit (5)
- `api/workers.py` (wire stubs to WorkerFactory)
- `web/server.py` (add get_worker_factory dependency)
- `core/orchestrator.py` (add worker_factory injection — if not already present)
- `src/lib/api.ts` (add createWorker, getWorkers, getWorker, updateWorker, deleteWorker)
- `src/stores/workerStore.ts` (add createWorker, updateWorker, deleteWorker, selectedWorkerId)
- `src/components/panels/WorkersPanel.tsx` (add Create button, click-to-edit)
- `src/__tests__/components.test.tsx` (add WorkerCreator/Editor tests)

## Files will NOT edit
- `core/worker_factory.py` (use as-is — create_worker, list_workers, deregister_worker)
- `core/worker_base.py` (use as-is)
- `system/worker_persistence.py` (use as-is — persistence is WorkerFactory's concern)
- `core/` logic modules (except orchestrator injection)
- `memory/`, `skills/`, `adapters/`

---

## Closing

Run `/jarvis-close`. Tag `prompt-93`. CHANGELOG entry for Plan 93. Update PLANS.md.
