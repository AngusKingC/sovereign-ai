# Plan 97 — Debate & Expert Panel UI (Phase 4)

**Tag**: `prompt-97` | **Depends on**: `prompt-96`

---

## Scope

Expose the PEMADS debate system (built in Plans 87–88) via Web UI. Backend: debate/expert CRUD endpoints. Frontend: Expert Panel Configurator, Debate Trigger, Debate Viewer (real-time rounds + judge scores), Implementation Gate UI.

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §3.3 Gap #3 (CRITICAL), §6 Phase 4

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-96` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

S0.4. **Post-Plan 95 scan state** (verified clean):
- `test_list_workers` is FIXED (no longer skipped). AsyncMock return_value corrected in Plan 95.
- Governance files are updated: jarvis-close has C9 (concrete templates) + C16 (Git Bash cleanup), AI_HANDOFF says "Git Bash on Windows", jarvis-open uses `test -f`.
- `.txt` files moved to `txt/` folder during Plan 95 scan. Use `txt/requirements.txt` not `requirements.txt`.
- Vitest: 7 tests skipped (WorkerCreator, WorkerEditor, ModelsPanel not yet implemented).
- Playwright E2E deferred (web server startup issue — not blocking).

S0.5. **Pre-verification** (mandatory before coding):
- Read `memory/debate_pool.py` — confirm `DebatePool` API: `get_debate_history(debate_id)`, `get_solutions(debate_id, round_num)`, `get_critiques(debate_id, round_num)`.
- Read `core/expert_panel_manager.py` — confirm `_experts` dict is accessible (may be private). If so, add a `list_experts()` public method.
- Read `core/pemads_judge.py` — confirm `JudgeVerdict` fields: `debate_id`, `winning_expert_id`, `winning_quality_pct`, `threshold`, `passed`, `all_scores`, `feedback`.
- Read `core/implementation_gate.py` — confirm `GateDecision` fields: `debate_id`, `approved`, `requires_human_approval`, `pending`, `reason`, `approved_by`.
- Verify `orchestrator.expert_panel_manager`, `orchestrator.pemads_judge`, `orchestrator.implementation_gate` exist as optional attributes.

---

## S1. Add debate API endpoints

Create `api/debates.py`:

```python
"""API router for PEMADS debate system."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/debates", tags=["debates"])

class DebateTriggerRequest(BaseModel):
    task_intent: str
    max_rounds: int = 3

@router.get("")
async def list_debates() -> list[dict[str, Any]]:
    """List all debate pools (scan debate_pools/ directory)."""
    import os
    debate_pools_dir = "debate_pools"
    if not os.path.exists(debate_pools_dir):
        return []
    debates = []
    for d in os.listdir(debate_pools_dir):
        path = os.path.join(debate_pools_dir, d)
        if os.path.isdir(path):
            debates.append({"debate_id": d, "path": path})
    return debates

@router.get("/{debate_id}")
async def get_debate(debate_id: str) -> dict[str, Any]:
    """Get debate details — rounds, solutions, critiques, scores."""
    from memory.debate_pool import DebatePool
    dp = DebatePool()
    try:
        history = dp.get_debate_history(debate_id)
        return {"debate_id": debate_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Debate '{debate_id}' not found: {e}")

@router.get("/{debate_id}/verdict")
async def get_verdict(debate_id: str) -> dict[str, Any]:
    """Get judge verdict for a debate (if judged)."""
    # Query orchestrator's PEMADSJudge if available
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'pemads_judge') or not orchestrator.pemads_judge:
        raise HTTPException(status_code=503, detail="PEMADS judge not configured")
    try:
        # Re-judge or return cached verdict
        # For now, return placeholder — full implementation needs cached verdicts
        return {"debate_id": debate_id, "status": "verdict_not_cached"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/experts")
async def list_experts() -> list[dict[str, Any]]:
    """List registered experts."""
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'expert_panel_manager') or not orchestrator.expert_panel_manager:
        raise HTTPException(status_code=503, detail="Expert panel not configured")
    experts = orchestrator.expert_panel_manager._experts
    return [
        {"worker_id": eid, "specialty": e.specialty, "adapter": getattr(e.adapter, 'model_name', str(e.adapter))}
        for eid, e in experts.items()
    ]
```

Wire into `web/server.py`:
```python
from api.debates import router as debates_router
app.include_router(debates_router)
```

---

## S2. Create `src/stores/debateStore.ts`

```typescript
import { create } from "zustand";

export interface ExpertInfo {
  worker_id: string;
  specialty: string;
  adapter: string;
}

export interface DebateInfo {
  debate_id: string;
  status: string;
}

export interface JudgeVerdict {
  debate_id: string;
  winning_expert_id: string;
  winning_quality_pct: number;
  threshold: number;
  passed: boolean;
  all_scores: Record<string, number>;
  feedback: string;
}

interface DebateState {
  debates: DebateInfo[];
  experts: ExpertInfo[];
  selectedDebateId: string | null;
  verdict: JudgeVerdict | null;
  isLoading: boolean;
  error: string | null;
  setDebates: (debates: DebateInfo[]) => void;
  setExperts: (experts: ExpertInfo[]) => void;
  setSelectedDebate: (id: string | null) => void;
  setVerdict: (verdict: JudgeVerdict | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useDebateStore = create<DebateState>((set) => ({
  debates: [],
  experts: [],
  selectedDebateId: null,
  verdict: null,
  isLoading: false,
  error: null,
  setDebates: (debates) => set({ debates }),
  setExperts: (experts) => set({ experts }),
  setSelectedDebate: (id) => set({ selectedDebateId: id }),
  setVerdict: (verdict) => set({ verdict }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));
```

---

## S3. Add API functions to `src/lib/api.ts`

```typescript
export async function getDebates(): Promise<any[]> {
  const res = await fetch(`/api/debates`);
  if (!res.ok) throw new Error(`Debates ${res.status}`);
  return res.json();
}

export async function getDebate(debateId: string): Promise<any> {
  const res = await fetch(`/api/debates/${debateId}`);
  if (!res.ok) throw new Error(`Debate ${res.status}`);
  return res.json();
}

export async function getDebateVerdict(debateId: string): Promise<any> {
  const res = await fetch(`/api/debates/${debateId}/verdict`);
  if (!res.ok) throw new Error(`Verdict ${res.status}`);
  return res.json();
}

export async function getExperts(): Promise<any[]> {
  const res = await fetch(`/api/debates/experts`);
  if (!res.ok) throw new Error(`Experts ${res.status}`);
  return res.json();
}
```

---

## S4. Create `src/components/panels/DebatePanel.tsx`

Main debate panel with 3 sections: Expert list, Debate list, Debate detail viewer:

```tsx
"use client";
import { useState, useEffect } from "react";
import { getDebates, getDebate, getDebateVerdict, getExperts } from "@/lib/api";
import { useDebateStore } from "@/stores/debateStore";

export function DebatePanel() {
  const { debates, experts, selectedDebateId, setSelectedDebate, setDebates, setExperts } = useDebateStore();
  const [debateDetail, setDebateDetail] = useState<any>(null);
  const [verdict, setVerdict] = useState<any>(null);

  useEffect(() => {
    Promise.all([getDebates(), getExperts()]).then(([d, e]) => { setDebates(d); setExperts(e); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedDebateId) return;
    getDebate(selectedDebateId).then(setDebateDetail).catch(() => {});
    getDebateVerdict(selectedDebateId).then(setVerdict).catch(() => {});
  }, [selectedDebateId]);

  return (
    <div data-testid="debate-panel" className="p-4 space-y-6">
      <h2 className="text-lg font-semibold">PEMADS Debate System</h2>

      {/* Experts section */}
      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">Registered Experts ({experts.length})</h3>
        <div className="grid grid-cols-2 gap-2">
          {experts.map((e) => (
            <div key={e.worker_id} className="border border-slate-700 rounded p-2 bg-slate-900 text-sm">
              <div className="font-mono">{e.worker_id}</div>
              <div className="text-xs text-slate-500">Specialty: {e.specialty} | Model: {e.adapter}</div>
            </div>
          ))}
          {experts.length === 0 && <p className="text-slate-500 text-sm">No experts registered.</p>}
        </div>
      </div>

      {/* Debate list */}
      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-2">Past Debates ({debates.length})</h3>
        <div className="space-y-2">
          {debates.map((d) => (
            <div key={d.debate_id}
              className={`border rounded p-2 cursor-pointer ${selectedDebateId === d.debate_id ? "border-amber-500" : "border-slate-700"} bg-slate-900 hover:border-slate-600`}
              onClick={() => setSelectedDebate(d.debate_id)}>
              <span className="font-mono text-sm">{d.debate_id}</span>
            </div>
          ))}
          {debates.length === 0 && <p className="text-slate-500 text-sm">No debates yet. Debates trigger automatically on COMPLEX tasks.</p>}
        </div>
      </div>

      {/* Debate detail */}
      {selectedDebateId && debateDetail && (
        <div className="border border-slate-700 rounded p-4 bg-slate-900">
          <h3 className="font-medium mb-2">Debate: {selectedDebateId}</h3>
          <pre className="text-xs text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">{debateDetail.history || "No history available"}</pre>
          {verdict && verdict.status !== "verdict_not_cached" && (
            <div className="mt-4 pt-4 border-t border-slate-700">
              <h4 className="text-sm font-medium mb-1">Judge Verdict</h4>
              <div className="text-xs space-y-1">
                <div>Winner: <span className="text-emerald-400">{verdict.winning_expert_id}</span> ({verdict.winning_quality_pct?.toFixed(1)}%)</div>
                <div>Threshold: {verdict.threshold?.toFixed(1)}% | Passed: {verdict.passed ? "✓" : "✗"}</div>
                {verdict.all_scores && Object.entries(verdict.all_scores).map(([eid, score]) => (
                  <div key={eid} className="text-slate-500">{eid}: {(score as number).toFixed(1)}%</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## S5. Update uiStore, Sidebar, page.tsx

Add `VIEWS.DEBATES: "debates"` to uiStore.
Add nav item to Sidebar (icon: `Users` from lucide-react).
Add routing to page.tsx: `case VIEWS.DEBATES: return <DebatePanel />;`

---

## S6. Add backend tests

Create `tests/test_debate_api.py`:
- test_list_debates_empty
- test_list_debates_with_data
- test_get_debate_404
- test_get_debate_verdict_not_configured
- test_list_experts_not_configured
- test_list_experts_with_data

Minimum 6 tests.

---

## S7. Add Vitest tests

Add to `src/__tests__/components.test.tsx`:
- DebatePanel renders expert list
- DebatePanel renders debate list
- DebatePanel shows debate detail when selected

Minimum 3 tests.

---

## S8. Verify build

```bash
ruff check api/debates.py
mypy api/debates.py --ignore-missing-imports
python -m pytest tests/test_debate_api.py -vvv
cd src && npx tsc --noEmit && npm run build
cd src && npm test
python -m pytest tests/ -vvv
```

---

## STOP condition

If `ExpertPanelManager` or `PEMADSJudge` not configured in orchestrator, endpoints return 503 (expected). Do NOT try to configure them in this plan — that's a deployment concern.

---

## Files WILL create (3)
- `api/debates.py`
- `src/stores/debateStore.ts`
- `src/components/panels/DebatePanel.tsx`
- `tests/test_debate_api.py`

## Files WILL edit (4)
- `web/server.py` (include debates router)
- `src/lib/api.ts` (add getDebates, getDebate, getDebateVerdict, getExperts)
- `src/stores/uiStore.ts` (add VIEWS.DEBATES)
- `src/components/shell/Sidebar.tsx` (add Debates nav item)
- `src/app/page.tsx` (add view routing)
- `src/__tests__/components.test.tsx` (add DebatePanel tests)

## Files will NOT edit
- `core/expert_panel_manager.py` (use as-is)
- `core/pemads_judge.py` (use as-is)
- `core/implementation_gate.py` (use as-is)
- `memory/debate_pool.py` (use as-is)

---

## Closing

Run `/jarvis-close`. Tag `prompt-97`. CHANGELOG entry. Update PLANS.md.
