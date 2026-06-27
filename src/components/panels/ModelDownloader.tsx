"use client";
import { useState, useEffect } from "react";
import { searchModels, downloadModel, getDownloadStatus, ModelInfo, DownloadStatus } from "@/lib/api";

export function ModelDownloader({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelInfo | null>(null);
  const [quantisation, setQuantisation] = useState("default");
  const [download, setDownload] = useState<DownloadStatus | null>(null);
  const [approvalPending, setApprovalPending] = useState<{ requestId: string; modelId: string } | null>(null);

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
    const result = await downloadModel(selectedModel.model_id, quantisation);
    if (result.status === "approval_required") {
      setApprovalPending({
        requestId: (result as any).request_id || "unknown",
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
                placeholder="Search local model registry..."
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
