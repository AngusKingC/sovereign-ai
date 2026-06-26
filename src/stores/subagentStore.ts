import { create } from "zustand";

export interface Subagent {
  id: string;
  task: string;
  status: "running" | "waiting" | "complete" | "failed";
  tokenCost: number;
  startedAt?: string;
  completedAt?: string;
  error?: string;
}

interface SubagentState {
  subagents: Subagent[];
  setSubagents: (subagents: Subagent[]) => void;
  addSubagent: (subagent: Subagent) => void;
  updateStatus: (id: string, status: Subagent["status"], error?: string) => void;
  updateTokenCost: (id: string, cost: number) => void;
  killSubagent: (id: string) => Promise<void>;  // Rev2 L1 fix — async (calls backend)
  clearCompleted: () => void;
}

export const useSubagentStore = create<SubagentState>((set) => ({
  subagents: [],
  setSubagents: (subagents) => set({ subagents }),
  addSubagent: (subagent) =>
    set((s) => ({ subagents: [...s.subagents, subagent] })),
  updateStatus: (id, status, error) =>
    set((s) => ({
      subagents: s.subagents.map((sa) =>
        sa.id === id
          ? {
              ...sa,
              status,
              error,
              completedAt: status === "complete" || status === "failed" ? new Date().toISOString() : sa.completedAt,
            }
          : sa
      ),
    })),
  updateTokenCost: (id, cost) =>
    set((s) => ({
      subagents: s.subagents.map((sa) =>
        sa.id === id ? { ...sa, tokenCost: cost } : sa
      ),
    })),
  killSubagent: async (id: string) => {
    // Rev2 L1 fix — call backend to terminate subagent before removing from store.
    // The original code only removed the subagent from local state, leaving it
    // running on the backend (consuming tokens and VRAM).
    try {
      await fetch(`http://localhost:8000/api/subagents/${id}`, { method: 'DELETE' });
    } catch (err) {
      console.error(`Failed to kill subagent ${id}:`, err);
      // Still remove from store even if backend call fails — user intent is clear
    }
    set((s) => ({ subagents: s.subagents.filter((sa) => sa.id !== id) }));
  },
  clearCompleted: () =>
    set((s) => ({
      subagents: s.subagents.filter(
        (sa) => sa.status !== "complete" && sa.status !== "failed"
      ),
    })),
}));
