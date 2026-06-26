import { usePolling } from "./usePolling";
import { useAgentStore } from "@/stores/agentStore";

interface StatusResponse {
  phase: string;
  latency: number;
  is_running: boolean;
  token_count: number;
}

export function useStatusPolling() {
  const setPhase = useAgentStore((s) => s.setPhase);
  const setLatency = useAgentStore((s) => s.setLatency);
  const addTokens = useAgentStore((s) => s.addTokens);

  const fetcher = async (): Promise<StatusResponse> => {
    const response = await fetch("http://localhost:8000/api/status");
    if (!response.ok) throw new Error("Failed to fetch status");
    return response.json();
  };

  const { data, error, isLoading } = usePolling(fetcher, 2000, {
    enabled: true,
    onError: (err) => console.error("Status polling error:", err),
  });

  // Update store when data changes
  if (data && !isLoading) {
    setPhase(data.phase as any);
    setLatency(data.latency);
    addTokens(data.token_count);
  }

  return { data, error, isLoading };
}
