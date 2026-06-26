import { create } from "zustand";

export interface CostSummary {
  total_cost_usd: number;
  daily_cost_usd: number;
  monthly_cost_usd: number;
  model_costs: Record<string, number>;
}

interface CostState {
  summary: CostSummary | null;
  setSummary: (summary: CostSummary) => void;
}

export const useCostStore = create<CostState>((set) => ({
  summary: null,
  setSummary: (summary) => set({ summary }),
}));
