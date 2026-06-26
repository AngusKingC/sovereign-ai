"use client";

import { useApprovalStore } from "@/stores/approvalStore";

export function ApprovalQueuePanel() {
  const pending = useApprovalStore((s) => s.pending);
  const respond = useApprovalStore((s) => s.respond);

  const getRiskColor = (description: string) => {
    const desc = description.toLowerCase();
    if (desc.includes("delete") || desc.includes("remove") || desc.includes("destroy")) {
      return "bg-red-500";
    }
    if (desc.includes("modify") || desc.includes("change") || desc.includes("update")) {
      return "bg-amber-500";
    }
    return "bg-emerald-500";
  };

  const getRiskLevel = (description: string) => {
    const desc = description.toLowerCase();
    if (desc.includes("delete") || desc.includes("remove") || desc.includes("destroy")) {
      return "high";
    }
    if (desc.includes("modify") || desc.includes("change") || desc.includes("update")) {
      return "medium";
    }
    return "low";
  };

  const handleRespond = async (id: string, approved: boolean) => {
    try {
      const response = await fetch(`/api/approvals/${id}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      });
      if (response.ok) {
        respond(id, approved);
      }
    } catch (error) {
      console.error("Failed to respond to approval:", error);
    }
  };

  const getTimeRemaining = (createdAt: string) => {
    const created = new Date(createdAt).getTime();
    const now = Date.now();
    const elapsed = (now - created) / 1000; // seconds
    const remaining = Math.max(0, 300 - elapsed); // 5 minutes = 300 seconds
    const minutes = Math.floor(remaining / 60);
    const seconds = Math.floor(remaining % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  return (
    <div className="p-6" data-testid="approval-queue-panel">
      <h1 className="text-2xl font-bold mb-6">Approval Queue</h1>

      <div className="space-y-4">
        {pending.length === 0 ? (
          <p className="text-gray-500">No pending approvals</p>
        ) : (
          pending.map((request) => (
            <div
              key={request.id}
              className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">{request.description}</span>
                <span
                  className={`px-2 py-1 rounded-full text-xs text-white ${getRiskColor(
                    request.description
                  )}`}
                >
                  {getRiskLevel(request.description).toUpperCase()}
                </span>
              </div>

              <div className="text-xs text-gray-500 mb-3">
                Task ID: {request.task_id} | Expires in: {getTimeRemaining(request.created_at)}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleRespond(request.id, true)}
                  className="px-3 py-1 bg-emerald-500 text-white text-xs rounded hover:bg-emerald-600"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleRespond(request.id, false)}
                  className="px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600"
                >
                  Deny
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
