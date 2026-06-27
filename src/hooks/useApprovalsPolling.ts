import { usePolling } from "./usePolling";
import { useApprovalStore } from "@/stores/approvalStore";
import { logHttpError } from "./useErrorLogger";

interface ApprovalResponse {
  pending: Array<{
    id: string;
    task_id: string;
    description: string;
    proposed_action: string;
    created_at: string;
  }>;
}

export function useApprovalsPolling() {
  const setPending = useApprovalStore((s) => s.setPending);

  const fetcher = async (): Promise<ApprovalResponse> => {
    const response = await fetch("http://localhost:8000/api/approvals");
    if (!response.ok) {
      logHttpError("http://localhost:8000/api/approvals", response.status, "Failed to fetch approvals");
      throw new Error("Failed to fetch approvals");
    }
    return response.json();
  };

  const { data, error, isLoading } = usePolling(fetcher, 2000, {
    enabled: true,
    onError: (err) => console.error("Approvals polling error:", err),
  });

  // Update store when data changes
  if (data && !isLoading) {
    setPending(data.pending);
  }

  return { data, error, isLoading };
}
