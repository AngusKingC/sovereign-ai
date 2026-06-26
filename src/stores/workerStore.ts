import { create } from "zustand";

export interface Worker {
  worker_id: string;
  model: string;
  capabilities: string[];
  status: string;
}

interface WorkerState {
  workers: Worker[];
  degradedRatio: number;
  setWorkers: (workers: Worker[]) => void;
  setDegradedRatio: (ratio: number) => void;
  resetCircuit: () => void;
}

export const useWorkerStore = create<WorkerState>((set) => ({
  workers: [],
  degradedRatio: 0,
  setWorkers: (workers) => set({ workers }),
  setDegradedRatio: (degradedRatio) => set({ degradedRatio }),
  resetCircuit: () => set({ degradedRatio: 0 }),
}));
