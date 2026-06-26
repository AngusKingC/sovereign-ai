import { usePolling } from "./usePolling";
import { useMemoryStore } from "@/stores/memoryStore";

interface MemoryResponse {
  slots: Array<{
    index: number;
    key: string;
    value: string;
    activation: number;
    lastWritten: number;
  }>;
}

export function useMemoryPolling() {
  const setSlots = useMemoryStore((s) => s.setSlots);

  const fetcher = async (): Promise<MemoryResponse> => {
    const response = await fetch("http://localhost:8000/api/memory");
    if (!response.ok) throw new Error("Failed to fetch memory");
    return response.json();
  };

  const { data, error, isLoading } = usePolling(fetcher, 10000, {
    enabled: true,
    onError: (err) => console.error("Memory polling error:", err),
  });

  // Update store when data changes
  if (data && !isLoading) {
    setSlots(data.slots);
  }

  return { data, error, isLoading };
}
