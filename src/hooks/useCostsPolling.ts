import { usePolling } from "./usePolling";
import { useCostStore } from "@/stores/costStore";

interface CostResponse {
  total_cost_usd: number;
  daily_cost_usd: number;
  monthly_cost_usd: number;
  model_costs: Record<string, number>;
}

export function useCostsPolling() {
  const setSummary = useCostStore((s) => s.setSummary);

  const fetcher = async (): Promise<CostResponse> => {
    const response = await fetch("http://localhost:8000/api/costs");
    if (!response.ok) throw new Error("Failed to fetch costs");
    return response.json();
  };

  const { data, error, isLoading } = usePolling(fetcher, 10000, {
    enabled: true,
    onError: (err) => console.error("Costs polling error:", err),
  });

  // Update store when data changes
  if (data && !isLoading) {
    setSummary(data);
  }

  return { data, error, isLoading };
}
