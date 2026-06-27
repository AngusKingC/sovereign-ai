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
