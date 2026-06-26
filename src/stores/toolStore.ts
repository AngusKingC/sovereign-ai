import { create } from "zustand";

type ToolStatus = "running" | "success" | "warning" | "error";

export interface ToolCall {
  id: string;
  tool: string;
  status: ToolStatus;
  args: Record<string, unknown>;
  output?: string;
  durationMs?: number;
  startedAt: number;
}

interface ToolState {
  calls: ToolCall[];
  addCall: (call: ToolCall) => void;
  patchCall: (id: string, patch: Partial<ToolCall>) => void;
  upsertCall: (call: ToolCall) => void;
  clearCalls: () => void;
}

const MAX_CALLS = 50;

export const useToolStore = create<ToolState>((set) => ({
  calls: [],
  addCall: (call) =>
    set((state) => {
      const calls = [call, ...state.calls].slice(0, MAX_CALLS);
      return { calls };
    }),
  patchCall: (id, patch) =>
    set((state) => ({
      calls: state.calls.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    })),
  upsertCall: (call) =>
    set((state) => {
      const existing = state.calls.find((c) => c.id === call.id);
      if (existing) {
        return {
          calls: state.calls.map((c) =>
            c.id === call.id ? { ...c, ...call } : c
          ),
        };
      }
      return { calls: [call, ...state.calls].slice(0, MAX_CALLS) };
    }),
  clearCalls: () => set({ calls: [] }),
}));
