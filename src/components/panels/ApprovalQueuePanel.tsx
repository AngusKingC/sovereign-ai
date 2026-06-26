"use client";
import { useState, useEffect } from "react";
import { useApprovalStore } from "@/stores/approvalStore";

export function ApprovalQueuePanel() {
  const { pending, setPending, removeRequest } = useApprovalStore();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<string[]>([]);

  const handleRespond = async (id: string, approved: boolean, alwaysApprove = false) => {
    try {
      const response = await fetch(`/api/approvals/${id}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, always_approve: alwaysApprove }),
      });
      if (response.ok) {
        removeRequest(id);
        setToasts([`${approved ? "Approved" : "Denied"}: ${id.slice(0, 8)}`]);
        setTimeout(() => setToasts([]), 3000);
      }
    } catch (error) {
      console.error("Failed to respond to approval:", error);
    }
  };

  const handleBatch = async (approved: boolean) => {
    for (const id of selected) {
      await handleRespond(id, approved);
    }
    setSelected(new Set());
  };

  return (
    <div data-testid="approvals-panel" className="p-4 space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Approval Queue</h2>
        {selected.size > 0 && (
          <div className="space-x-2">
            <button onClick={() => handleBatch(true)} className="px-3 py-1 bg-emerald-600 rounded text-sm">
              Approve {selected.size}
            </button>
            <button onClick={() => handleBatch(false)} className="px-3 py-1 bg-red-600 rounded text-sm">
              Deny {selected.size}
            </button>
          </div>
        )}
      </div>

      {pending.length === 0 && (
        <p className="text-slate-500 text-sm">No pending approvals.</p>
      )}

      {pending.map((req) => (
        <ApprovalCard
          key={req.id}
          request={req}
          selected={selected.has(req.id)}
          onSelect={(checked: boolean) => {
            const next = new Set(selected);
            if (checked) next.add(req.id);
            else next.delete(req.id);
            setSelected(next);
          }}
          onRespond={(approved: boolean, always: boolean) => handleRespond(req.id, approved, always)}
        />
      ))}

      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 space-y-2">
          {toasts.map((t, i) => (
            <div key={i} className="bg-slate-800 border border-slate-600 rounded px-4 py-2 text-sm">
              {t}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ApprovalCard({ request, selected, onSelect, onRespond }: any) {
  // Rev2 L2 fix — initialize countdown from request.expires_at, not hardcoded 300s.
  // The original code used useState(300) for every request, which was misleading
  // (refreshing the page reset the timer, giving a false sense of remaining time).
  const [remaining, setRemaining] = useState(() => {
    if (request.expires_at) {
      const expiryMs = new Date(request.expires_at).getTime();
      const nowMs = Date.now();
      return Math.max(0, Math.floor((expiryMs - nowMs) / 1000));
    }
    return 300; // Fallback if expires_at is missing
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining((r) => Math.max(0, r - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;

  return (
    <div className="border border-slate-700 rounded p-3 bg-slate-900">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-2">
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => onSelect(e.target.checked)}
            className="mt-1"
          />
          <div>
            <span className="font-mono text-sm">{request.id.slice(0, 8)}</span>
            <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
              request.risk === "high" ? "bg-red-900" : request.risk === "medium" ? "bg-amber-900" : "bg-emerald-900"
            }`}>
              {request.risk}
            </span>
          </div>
        </div>
        <span className="text-xs text-slate-400">{mins}:{secs.toString().padStart(2, "0")}</span>
      </div>
      <p className="text-sm text-slate-300 mt-2">{request.description}</p>
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-500">Channels:</span>
          <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">Web</span>
          {request.channels?.telegram && <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">TG</span>}
          {request.channels?.email && <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded">Email</span>}
        </div>
        <div className="space-x-2">
          <button
            onClick={() => onRespond(true, false)}
            className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-sm"
          >
            Approve
          </button>
          <button
            onClick={() => onRespond(false, false)}
            className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm"
          >
            Deny
          </button>
          <label className="text-xs text-slate-400 ml-2">
            <input type="checkbox" onChange={(e) => e.target.checked && onRespond(true, true)} />
            Always
          </label>
        </div>
      </div>
    </div>
  );
}
