import { usePolling } from "./usePolling";
import { useWorkerStore } from "@/stores/workerStore";
import { logHttpError } from "./useErrorLogger";

interface WorkerProfile {
  worker_id: string;
  worker_type: string;
  name: string;
  description: string;
  purpose: string;
  capabilities: string[];
  complexity_min: number;
  complexity_max: number;
  preferred_complexity: number;
  depth_preference: number;
  speculation_tolerance: number;
  source_skepticism: number;
  verbosity: number;
  standing_instructions: string[];
  preferred_model: string;
  preferred_models: string[];
  escalation_threshold: number;
  tasks_completed: number;
  avg_confidence: number;
  performance_score: number;
  active_tasks: number;
  version: number;
  status: string;
  creation_date: string;
  instruction_file_ref: string | null;
}

interface WorkerResponse {
  workers: WorkerProfile[];
  degraded_ratio: number;
}

export function useWorkersPolling() {
  const setWorkers = useWorkerStore((s) => s.setWorkers);
  const setDegradedRatio = useWorkerStore((s) => s.setDegradedRatio);

  const fetcher = async (): Promise<WorkerResponse> => {
    const response = await fetch("http://localhost:8000/api/workers");
    if (!response.ok) {
      logHttpError("http://localhost:8000/api/workers", response.status, "Failed to fetch workers");
      throw new Error("Failed to fetch workers");
    }
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
