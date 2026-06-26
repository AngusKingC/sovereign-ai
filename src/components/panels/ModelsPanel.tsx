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
