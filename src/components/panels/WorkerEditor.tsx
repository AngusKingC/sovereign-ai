"use client";
import { useState } from "react";
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
