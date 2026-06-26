import { create } from "zustand";

type SubagentStatus = "running" | "waiting" | "complete" | "failed";

interface Subagent {
  id: string;
  task: string;
  status: SubagentStatus;
  tokenCost: number;
}

interface SubagentState {
  subagents: Subagent[];
  setSubagents: (subs: Subagent[]) => void;
  killSubagent: (id: string) => void;
}

export const useSubagentStore = create<SubagentState>((set) => ({
  subagents: [],
  setSubagents: (subagents) => set({ subagents }),
  killSubagent: (id) =>
    set((state) => ({
      subagents: state.subagents.filter((s) => s.id !== id),
    })),
}));
