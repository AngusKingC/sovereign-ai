import { usePolling } from "./usePolling";
import { useWorkerStore } from "@/stores/workerStore";

interface WorkerResponse {
  workers: Array<{
    worker_id: string;
    model: string;
    capabilities: string[];
    status: string;
  }>;
  degraded_ratio: number;
}

export function useWorkersPolling() {
  const setWorkers = useWorkerStore((s) => s.setWorkers);
  const setDegradedRatio = useWorkerStore((s) => s.setDegradedRatio);

  const fetcher = async (): Promise<WorkerResponse> => {
    const response = await fetch("http://localhost:8000/api/workers");
    if (!response.ok) throw new Error("Failed to fetch workers");
    return response.json();
  };

  const { data, error, isLoading } = usePolling(fetcher, 5000, {
    enabled: true,
    onError: (err) => console.error("Workers polling error:", err),
  });

  // Update store when data changes
  if (data && !isLoading) {
    setWorkers(data.workers);
    setDegradedRatio(data.degraded_ratio);
  }

  return { data, error, isLoading };
}
