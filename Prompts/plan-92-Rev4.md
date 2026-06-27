# Plan 92 — Model Downloader + Fallback Chain (Phase 1b)

**Tag**: `prompt-92` | **Depends on**: `prompt-91`

**Rev4 — Post-Round-Table Adjudication (6 panel responses consolidated across Rev2+Rev3 cycles)**

**Rev2 history**: Post-Round-Table Adjudication (4 panel responses consolidated)
**Rev3 history**: Post-Round-Table Re-Review (5 panel responses consolidated)

---

## Scope

Enable model search/download from HuggingFace/Ollama and fallback chain configuration via UI. This completes Gap #1 from the UI/UX Gap Analysis (§3.1 — CRITICAL). Backend: wire download endpoints to `system/model_acquisition.py`, add fallback chain endpoints. Frontend: `ModelDownloader.tsx` modal, Fallback Chain Editor in SettingsDrawer.

**Rev2 changes**: (1) Added approval gate for downloads >1GB. (2) Fixed FastAPI `list[str]` body parameter — use Pydantic model. (3) Added ModelAcquisition signature pre-verification. (4) Fixed ModelDownloader search placeholder — clarifies local-only search. (5) Added adapter selector dropdown to StatusBar (deferred from Plan 91).

**Rev4 changes**: (1) Replaced `alert()` with proper approval pending UI state (Rev3 C1 fix). (2) Added "Go to Approval Queue" navigation button.

**Gap Analysis ref**: `docs/UI-UX-Gap-Analysis-Remediation-Roadmap.md` §3.1, §6 Phase 1, §7.2

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-91` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

### S0.5. Pre-verification: ModelAcquisition and adapter_factory signatures (Rev2 H7 — mandatory)

**Step 1**: Read `system/model_acquisition.py` and confirm:
- `async def request_download(...)` — is it async? What parameters does it accept?
- What does it return? (string download_id? DownloadResult object? None?)
- Does `get_download_status(download_id)` exist? If not, Plan 92 S1 Step 4 adds it.

**Step 2**: Read `cli/adapter_factory.py` and confirm:
- Does `create_adapter(name: str)` exist as a function?
- Does `ADAPTER_TYPES` exist as a dict or list of available adapter names?
- If neither exists, document the actual adapter discovery mechanism and adapt Plan 92 S2.

**Step 3**: If any signature differs from Plan 92's assumptions, adapt the plan steps BEFORE coding. Document findings in working notes.

---

## S1. Wire model download endpoints to ModelAcquisition

**Rev2 H3 fix**: Added approval gate for downloads >1GB per gap analysis §9. **Rev2 H7 fix**: Pre-verify `request_download()` signature per S0.5.

Add download endpoints to `api/models.py`. **Rev2 H1 fix**: `/download` and `/download/{id}/status` MUST be defined before `/{model_id}` (already handled in Plan 91 by placing `/search` first — Plan 92 adds these in the same position).

```python
# Rev2 H3 fix — size estimate for approval gate
LARGE_DOWNLOAD_THRESHOLD_BYTES = 1_000_000_000  # 1 GB


@router.post("/download")
async def download_model(
    model_id: str,
    quantisation: str = "default",
    acquisition=Depends(get_model_acquisition),
    registry=Depends(get_model_registry),
    approval_gate=Depends(get_approval_gate),
) -> dict[str, Any]:
    """Download a model from HuggingFace or Ollama.

    Rev2 H3 fix: Uses approval gate for downloads >1GB (per gap analysis §9).
    Returns download_id for status polling.
    """
    # Check if already downloaded
    entry = await registry.get(model_id)
    if entry and getattr(getattr(entry, 'download_status', None), 'value', str(getattr(entry, 'download_status', ''))) == "downloaded":
        return {"status": "already_downloaded", "model_id": model_id}

    # Rev2 H3 fix — estimate size and require approval for large downloads
    estimated_size = await _estimate_download_size(entry, model_id)
    if estimated_size and estimated_size > LARGE_DOWNLOAD_THRESHOLD_BYTES:
        from core.approval_gate import ApprovalRequest, ApprovalActionType
        from datetime import datetime, timezone, timedelta

        approval_request = ApprovalRequest(
            request_id=f"model-download-{model_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            task_id=f"download-{model_id}",
            session_id="model-download",
            action_type=ApprovalActionType.MODEL_DOWNLOAD,
            action_description=f"Download model '{model_id}' ({estimated_size / 1e9:.1f} GB)",
            action_parameters={"model_id": model_id, "estimated_size_bytes": estimated_size},
            risk_level="medium",
            reason_for_approval=f"Large model download: {estimated_size / 1e9:.1f} GB",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
        response = await approval_gate.request_approval(approval_request)
        if not response.approved:
            return {"status": "approval_required", "request_id": approval_request.request_id}

    # Initiate download (async — returns immediately with download_id)
    # Rev2 H7 fix — verify request_download() return type per S0.5
    download_result = await acquisition.request_download(
        model_id=model_id,
        quantisation=quantisation,
        registry=registry,
    )

    # Handle both string download_id and DownloadResult object
    if isinstance(download_result, str):
        download_id = download_result
    else:
        download_id = getattr(download_result, 'download_id', str(download_result))

    return {"download_id": download_id, "model_id": model_id, "status": "initiated"}


async def _estimate_download_size(entry, model_id: str) -> int | None:
    """Estimate download size from registry entry. Returns bytes or None if unknown."""
    if not entry:
        return None
    variants = getattr(entry, 'quantisation_variants', [])
    if variants:
        # Take the first variant's size as estimate
        first = variants[0]
        return getattr(first, 'size_bytes', None) or getattr(first, 'size_mb', None) and getattr(first, 'size_mb', 0) * 1_000_000
    return None


@router.get("/download/{download_id}/status")
async def get_download_status(
    download_id: str,
    acquisition=Depends(get_model_acquisition),
) -> dict[str, Any]:
    """Poll download progress by download_id."""
    status = await acquisition.get_download_status(download_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Download '{download_id}' not found")
    return status
```

**Step 2**: Add `get_model_acquisition` and `get_approval_gate` dependencies to `web/server.py`:

```python
def get_model_acquisition():
    if not orchestrator or not hasattr(orchestrator, 'model_acquisition') or not orchestrator.model_acquisition:
        raise HTTPException(status_code=503, detail="Model acquisition not configured")
    return orchestrator.model_acquisition

def get_approval_gate():
    if not orchestrator or not hasattr(orchestrator, 'approval_gate') or not orchestrator.approval_gate:
        raise HTTPException(status_code=503, detail="Approval gate not configured")
    return orchestrator.approval_gate
```

**Step 3** (Rev2 H7 fix — mandatory): Add `model_acquisition` to Orchestrator as optional injection. **Read orchestrator.py first** — Plan 91 may have already added `model_registry`. Append `model_acquisition` to the existing constructor, do NOT overwrite.

**Step 4**: Verify `ModelAcquisition.request_download()` and `get_download_status()` signatures per S0.5. If `get_download_status()` doesn't exist, add it as a thin wrapper that tracks in-flight downloads in a dict (see Rev1 code).

---

## S2. Add fallback chain endpoints

**Rev2 H5 fix**: Use Pydantic model for request body instead of bare `list[str]` (FastAPI treats bare list as query param, not body).

Create `api/adapters.py`:

```python
"""API router for adapter fallback chain management.
Rev2 H5 fix: Uses Pydantic model for request body.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/adapters", tags=["adapters"])


# Rev2 H5 fix — Pydantic model for request body
class FallbackChainRequest(BaseModel):
    """Request to set the fallback chain."""
    chain: list[str]


@router.get("/fallback")
async def get_fallback_chain(orchestrator=Depends(get_orchestrator)) -> dict[str, Any]:
    """Get the current adapter fallback chain."""
    if not hasattr(orchestrator, 'fallback_chain') or not orchestrator.fallback_chain:
        return {"chain": []}
    return {"chain": [a.model_name if hasattr(a, 'model_name') else str(a) for a in orchestrator.fallback_chain]}


@router.put("/fallback")
async def set_fallback_chain(
    request: FallbackChainRequest,  # Rev2 H5 fix — Pydantic model, not bare list
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Set the adapter fallback chain by adapter name.

    Accepts a JSON body: {"chain": ["ollama", "openai", "anthropic"]}
    Resolves names to adapter instances via cli/adapter_factory.py.
    """
    from cli.adapter_factory import create_adapter  # Rev2 H7 fix — verify import per S0.5

    resolved = []
    for name in request.chain:
        try:
            adapter = create_adapter(name)
            resolved.append(adapter)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create adapter '{name}': {e}")

    orchestrator.fallback_chain = resolved
    return {"chain": request.chain, "resolved_count": len(resolved)}


@router.get("/available")
async def list_available_adapters() -> dict[str, Any]:
    """List all adapter types that can be created."""
    # Rev2 H7 fix — verify ADAPTER_TYPES exists per S0.5
    try:
        from cli.adapter_factory import ADAPTER_TYPES
        if hasattr(ADAPTER_TYPES, 'keys'):
            return {"adapters": list(ADAPTER_TYPES.keys())}
        return {"adapters": list(ADAPTER_TYPES)}
    except ImportError:
        # Fallback: hardcoded list of known adapters
        return {"adapters": ["ollama", "openai", "anthropic", "gemini", "groq", "mistral", "cohere", "together", "deepseek", "lm_studio", "llama_cpp", "prism_llama", "huggingface", "mcp"]}
```

Wire into `web/server.py`:
```python
from api.adapters import router as adapters_router
app.include_router(adapters_router)
```

**Rev2 H5 fix**: Update `setFallbackChain` in `src/lib/api.ts` to send JSON body:
```typescript
export async function setFallbackChain(chain: string[]): Promise<{ chain: string[]; resolved_count: number }> {
  const res = await fetch(`/api/adapters/fallback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chain }),  // Rev2 H5 fix — wrap in object
  });
  if (!res.ok) throw new Error(`Set fallback ${res.status}`);
  return res.json();
}
```

---

## S3. Add API functions to `src/lib/api.ts`

```typescript
export interface DownloadStatus {
  download_id: string;
  model_id: string;
  status: "initiated" | "downloading" | "complete" | "failed";
  progress_pct: number;
  started_at: string;
  error?: string;
}

export async function downloadModel(modelId: string, quantisation: string = "default"): Promise<{ download_id: string; status: string }> {
  const res = await fetch(`/api/models/download?model_id=${encodeURIComponent(modelId)}&quantisation=${encodeURIComponent(quantisation)}`, { method: "POST" });
  if (!res.ok) throw new Error(`Download ${res.status}`);
  return res.json();
}

export async function getDownloadStatus(downloadId: string): Promise<DownloadStatus> {
  const res = await fetch(`/api/models/download/${downloadId}/status`);
  if (!res.ok) throw new Error(`Status ${res.status}`);
  return res.json();
}

export async function getFallbackChain(): Promise<{ chain: string[] }> {
  const res = await fetch(`/api/adapters/fallback`);
  if (!res.ok) throw new Error(`Fallback ${res.status}`);
  return res.json();
}

export async function setFallbackChain(chain: string[]): Promise<{ chain: string[]; resolved_count: number }> {
  const res = await fetch(`/api/adapters/fallback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(chain),
  });
  if (!res.ok) throw new Error(`Set fallback ${res.status}`);
  return res.json();
}

export async function getAvailableAdapters(): Promise<{ adapters: string[] }> {
  const res = await fetch(`/api/adapters/available`);
  if (!res.ok) throw new Error(`Adapters ${res.status}`);
  return res.json();
}
```

---

## S4. Create `src/components/panels/ModelDownloader.tsx`

**Rev2 H10 fix**: Search placeholder now says "Search local model registry..." instead of "Search HuggingFace/Ollama..." — Plan 91's `searchModels()` only searches the local registry. Remote HuggingFace/Ollama search is deferred to a future plan.

**Rev2 H3 fix**: Added size check and confirmation dialog for large downloads (>1GB).

Modal component for searching and downloading models:

```tsx
"use client";
import { useState, useEffect } from "react";
import { searchModels, downloadModel, getDownloadStatus, ModelInfo, DownloadStatus } from "@/lib/api";

export function ModelDownloader({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelInfo | null>(null);
  const [quantisation, setQuantisation] = useState("default");
  const [download, setDownload] = useState<DownloadStatus | null>(null);

  useEffect(() => {
    if (!download || download.status === "complete" || download.status === "failed") return;
    const interval = setInterval(async () => {
      const status = await getDownloadStatus(download.download_id);
      setDownload(status);
      if (status.status === "complete" || status.status === "failed") {
        clearInterval(interval);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [download]);

  const handleSearch = async () => {
    const models = await searchModels(query);
    setResults(models);
  };

  const handleDownload = async () => {
    if (!selectedModel) return;
    // Rev2 H3 fix — confirmation for large downloads (approval gate handles backend side)
    const result = await downloadModel(selectedModel.model_id, quantisation);
    if (result.status === "approval_required") {
      // Rev3 C1 fix — use proper UI feedback instead of alert()
      setApprovalPending({
        requestId: result.request_id,
        modelId: selectedModel.model_id,
      });
      return;
    }
    setDownload({
      download_id: result.download_id,
      model_id: selectedModel.model_id,
      status: "initiated",
      progress_pct: 0,
      started_at: new Date().toISOString(),
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="model-downloader">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Download Model</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        {/* Rev3 C1 fix — approval pending state instead of alert() */}
        {approvalPending ? (
          <div className="space-y-4">
            <h3 className="font-medium text-amber-400">Approval Required</h3>
            <p className="text-sm text-slate-300">
              This is a large download (&gt;1GB). Approval request has been submitted.
            </p>
            <div className="bg-slate-800 rounded p-3 text-sm">
              <div><span className="text-slate-500">Request ID:</span> <span className="font-mono">{approvalPending.requestId}</span></div>
              <div><span className="text-slate-500">Model:</span> <span className="font-mono">{approvalPending.modelId}</span></div>
            </div>
            <p className="text-sm text-slate-400">
              Approve or deny this download via the Approval Queue panel.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  // Navigate to approvals panel
                  window.location.hash = "#approvals";
                  onClose();
                }}
                className="px-4 py-2 bg-amber-600 rounded text-sm"
              >
                Go to Approval Queue
              </button>
              <button onClick={onClose} className="px-4 py-2 bg-slate-700 rounded text-sm">Close</button>
            </div>
          </div>
        ) : !download ? (
          <>
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                placeholder="Search local model registry..."  {/* Rev2 H10 fix — was "Search HuggingFace/Ollama..." */}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
              />
              <button onClick={handleSearch} className="px-4 py-2 bg-blue-600 rounded text-sm">Search</button>
            </div>

            {results.length > 0 && (
              <div className="space-y-2 mb-4">
                {results.map((model) => (
                  <div
                    key={model.model_id}
                    className={`border rounded p-3 cursor-pointer ${
                      selectedModel?.model_id === model.model_id ? "border-amber-500" : "border-slate-700"
                    }`}
                    onClick={() => setSelectedModel(model)}
                  >
                    <div className="font-medium">{model.name}</div>
                    <div className="text-xs text-slate-500 font-mono">{model.model_id}</div>
                    <div className="text-xs text-slate-400 mt-1">{model.description}</div>
                  </div>
                ))}
              </div>
            )}

            {selectedModel && (
              <div className="border-t border-slate-700 pt-4">
                <h3 className="font-medium mb-2">Download {selectedModel.name}</h3>
                <div className="mb-3">
                  <label className="text-sm text-slate-400 block mb-1">Quantisation</label>
                  <select
                    value={quantisation}
                    onChange={(e) => setQuantisation(e.target.value)}
                    className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
                  >
                    <option value="default">Default</option>
                    <option value="q4_0">Q4_0 (smallest)</option>
                    <option value="q4_1">Q4_1</option>
                    <option value="q5_0">Q5_0</option>
                    <option value="q5_1">Q5_1</option>
                    <option value="q8_0">Q8_0 (largest)</option>
                  </select>
                </div>
                <button onClick={handleDownload} className="px-4 py-2 bg-emerald-600 rounded text-sm">
                  Start Download
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-4">
            <h3 className="font-medium">Downloading {download.model_id}</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Status: {download.status}</span>
                <span>{download.progress_pct.toFixed(1)}%</span>
              </div>
              <div className="h-2 bg-slate-800 rounded">
                <div
                  className={`h-full rounded ${download.status === "failed" ? "bg-red-500" : "bg-emerald-500"}`}
                  style={{ width: `${download.progress_pct}%` }}
                />
              </div>
              {download.error && <p className="text-red-400 text-sm">{download.error}</p>}
              {(download.status === "complete" || download.status === "failed") && (
                <button onClick={onClose} className="px-4 py-2 bg-slate-700 rounded text-sm">Close</button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

## S5. Create Fallback Chain Editor in SettingsDrawer

Add a new tab or section to `src/components/panels/SettingsDrawer.tsx`:

```tsx
// Add to the SettingsDrawer component:
import { getFallbackChain, setFallbackChain, getAvailableAdapters } from "@/lib/api";

function FallbackChainEditor() {
  const [chain, setChain] = useState<string[]>([]);
  const [available, setAvailable] = useState<string[]>([]);
  const [newAdapter, setNewAdapter] = useState("");

  useEffect(() => {
    Promise.all([getFallbackChain(), getAvailableAdapters()]).then(([fb, av]) => {
      setChain(fb.chain);
      setAvailable(av.adapters);
    });
  }, []);

  const handleAdd = () => {
    if (newAdapter && !chain.includes(newAdapter)) {
      setChain([...chain, newAdapter]);
      setNewAdapter("");
    }
  };

  const handleRemove = (adapter: string) => {
    setChain(chain.filter((a) => a !== adapter));
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    const newChain = [...chain];
    [newChain[index - 1], newChain[index]] = [newChain[index], newChain[index - 1]];
    setChain(newChain);
  };

  const handleMoveDown = (index: number) => {
    if (index === chain.length - 1) return;
    const newChain = [...chain];
    [newChain[index], newChain[index + 1]] = [newChain[index + 1], newChain[index]];
    setChain(newChain);
  };

  const handleSave = async () => {
    await setFallbackChain(chain);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-400">Adapters are tried in order. If one fails, the next is used.</p>

      <div className="space-y-2">
        {chain.map((adapter, index) => (
          <div key={adapter} className="flex items-center gap-2 bg-slate-800 rounded p-2">
            <span className="text-xs text-slate-500">{index + 1}.</span>
            <span className="flex-1 font-mono text-sm">{adapter}</span>
            <button onClick={() => handleMoveUp(index)} className="text-xs text-slate-400 hover:text-slate-200">↑</button>
            <button onClick={() => handleMoveDown(index)} className="text-xs text-slate-400 hover:text-slate-200">↓</button>
            <button onClick={() => handleRemove(adapter)} className="text-xs text-red-400 hover:text-red-300">✕</button>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <select
          value={newAdapter}
          onChange={(e) => setNewAdapter(e.target.value)}
          className="flex-1 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm"
        >
          <option value="">Add adapter...</option>
          {available.filter((a) => !chain.includes(a)).map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <button onClick={handleAdd} className="px-3 py-1 bg-blue-600 rounded text-sm">Add</button>
      </div>

      <button onClick={handleSave} className="px-4 py-2 bg-emerald-600 rounded text-sm">Save Chain</button>
    </div>
  );
}
```

Add a "Fallback" tab to the SettingsDrawer that renders `<FallbackChainEditor />`.

---

## S6. Add "Download Model" button to ModelsPanel

In `src/components/panels/ModelsPanel.tsx` (from Plan 91), add:

```tsx
import { ModelDownloader } from "./ModelDownloader";

// Add state:
const [showDownloader, setShowDownloader] = useState(false);

// Add button in the header:
<button
  onClick={() => setShowDownloader(true)}
  className="px-3 py-1 bg-blue-600 rounded text-sm"
>
  Download New
</button>

// Add at the end of the component:
{showDownloader && <ModelDownloader onClose={() => setShowDownloader(false)} />}
```

---

## S7. Add backend tests

Create `tests/test_model_download.py`:
- test_download_model_initiates
- test_get_download_status_returns_progress
- test_download_already_downloaded_returns_early

Create `tests/test_fallback_chain.py`:
- test_get_fallback_chain_empty
- test_set_fallback_chain_resolves_adapters
- test_set_fallback_chain_invalid_adapter_returns_400

Minimum 6 new tests.

---

## S8. Verify build

```powershell
ruff check api/models.py api/adapters.py web/server.py
mypy api/models.py api/adapters.py --ignore-missing-imports
python -m pytest tests/test_model_download.py tests/test_fallback_chain.py -vvv
cd src && npx tsc --noEmit && npm run build
python -m pytest tests/ -vvv
cd src && npm test
```

---

## STOP condition

If `ModelAcquisition.request_download()` signature doesn't match, STOP and report. If `cli/adapter_factory.py` doesn't expose `create_adapter()` or `ADAPTER_TYPES`, STOP and report.

---

## Files WILL create (4)
- `api/adapters.py`
- `src/components/panels/ModelDownloader.tsx`
- `tests/test_model_download.py`
- `tests/test_fallback_chain.py`

## Files WILL edit (5)
- `api/models.py` (add download endpoints)
- `web/server.py` (add get_model_acquisition dependency, include adapters router)
- `system/model_acquisition.py` (add get_download_status + _execute_download if missing)
- `core/orchestrator.py` (add model_acquisition injection — if not already from Plan 91)
- `src/lib/api.ts` (add downloadModel, getDownloadStatus, getFallbackChain, setFallbackChain, getAvailableAdapters)
- `src/components/panels/SettingsDrawer.tsx` (add Fallback tab with FallbackChainEditor)
- `src/components/panels/ModelsPanel.tsx` (add Download New button + modal)

## Files will NOT edit
- `system/model_registry.py` (use as-is)
- `core/adapter_fallback.py` (read-only — orchestrator.fallback_chain is the integration point)
- `cli/adapter_factory.py` (read-only — use create_adapter())
- `core/` logic modules (except orchestrator injection)
- `memory/`, `skills/`, `workers/`

---

## Closing

Run `/jarvis-close`. Tag `prompt-92`. CHANGELOG entry for Plan 92. Update PLANS.md.
