"use client";

import { useState } from "react";
import { useWorkerStore } from "@/stores/workerStore";
import { WorkerCreator } from "./WorkerCreator";
import { WorkerEditor } from "./WorkerEditor";
import { WorkerProfile } from "@/lib/api";

export function WorkersPanel() {
  const workers = useWorkerStore((s) => s.workers);
  const resetCircuit = useWorkerStore((s) => s.resetCircuit);
  const [showCreator, setShowCreator] = useState(false);
  const [editingWorker, setEditingWorker] = useState<WorkerProfile | null>(null);

  const getCircuitStateColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === "closed") return "bg-emerald-500";
    if (s === "open") return "bg-red-500";
    if (s === "half_open") return "bg-amber-500";
    return "bg-gray-500";
  };

  const handleResetCircuit = async () => {
    try {
      const response = await fetch("/api/workers/reset-circuit", {
        method: "POST",
      });
      if (response.ok) {
        resetCircuit();
      }
    } catch (error) {
      console.error("Failed to reset circuit:", error);
    }
  };

  return (
    <div className="p-6" data-testid="workers-panel">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Workers</h1>
        <button onClick={() => setShowCreator(true)} className="px-3 py-1 bg-emerald-600 rounded text-sm">
          + Create Worker
        </button>
      </div>

      <div className="space-y-4">
        {workers.length === 0 ? (
          <p className="text-gray-500">No workers registered</p>
        ) : (
          workers.map((worker) => (
            <div
              key={worker.worker_id}
              onClick={() => setEditingWorker(worker)}
              className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm cursor-pointer hover:border-slate-600"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-semibold">{worker.name || worker.worker_id}</h3>
                  <p className="text-sm text-gray-600">Model: {worker.preferred_model}</p>
                </div>
                <span
                  className={`px-2 py-1 rounded-full text-xs text-white ${getCircuitStateColor(
                    worker.status
                  )}`}
                >
                  {worker.status.toUpperCase()}
                </span>
              </div>

              <div className="mb-3">
                <p className="text-xs text-gray-500 mb-1">Capabilities:</p>
                <div className="flex flex-wrap gap-1">
                  {worker.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleResetCircuit();
                }}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Reset Circuit
              </button>
            </div>
          ))
        )}
      </div>

      {showCreator && <WorkerCreator onClose={() => setShowCreator(false)} />}
      {editingWorker && <WorkerEditor worker={editingWorker} onClose={() => setEditingWorker(null)} />}
    </div>
  );
}
