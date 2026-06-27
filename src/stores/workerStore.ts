import { create } from "zustand";
import { createWorker, updateWorker, deleteWorker, getWorkersList, WorkerProfile } from "@/lib/api";

export interface Worker {
  worker_id: string;
  model: string;
  capabilities: string[];
  status: string;
}

interface WorkerState {
  workers: WorkerProfile[];
  degradedRatio: number;
  selectedWorkerId: string | null;
  setWorkers: (workers: WorkerProfile[]) => void;
  setDegradedRatio: (ratio: number) => void;
  resetCircuit: () => void;
  createWorker: (description: string, taskIntent?: string) => Promise<void>;
  updateWorker: (workerId: string, config: Partial<WorkerProfile>) => Promise<void>;
  deleteWorker: (workerId: string) => Promise<void>;
  setSelectedWorker: (id: string | null) => void;
  loadWorkers: () => Promise<void>;
}

export const useWorkerStore = create<WorkerState>((set, get) => ({
  workers: [],
  degradedRatio: 0,
  selectedWorkerId: null,
  setWorkers: (workers) => set({ workers }),
  setDegradedRatio: (degradedRatio) => set({ degradedRatio }),
  resetCircuit: () => set({ degradedRatio: 0 }),
  setSelectedWorker: (id) => set({ selectedWorkerId: id }),
  loadWorkers: async () => {
    const workers = await getWorkersList();
    set({ workers });
  },
  createWorker: async (description, taskIntent = "") => {
    const worker = await createWorker(description, taskIntent);
    set((s) => ({ workers: [...s.workers, worker] }));
  },
  updateWorker: async (workerId, config) => {
    const updated = await updateWorker(workerId, config);
    set((s) => ({
      workers: s.workers.map((w) => w.worker_id === workerId ? updated : w),
    }));
  },
  deleteWorker: async (workerId) => {
    await deleteWorker(workerId);
    set((s) => ({ workers: s.workers.filter((w) => w.worker_id !== workerId) }));
  },
}));
