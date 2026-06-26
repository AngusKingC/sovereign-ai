import { create } from "zustand";

type Phase = "idle" | "planning" | "acting" | "reflecting";

interface AgentState {
  sessionId: string;
  phase: Phase;
  modelSlug: string;
  latency: number;
  isRunning: boolean;
  tokenCount: number;
  contextLimit: number;
  setPhase: (phase: Phase) => void;
  setLatency: (ms: number) => void;
  setModel: (slug: string) => void;
  toggleRun: () => void;
  addTokens: (count: number) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  sessionId: "SES-8f2a",
  phase: "idle",
  modelSlug: "GLM-4.5 Flash",
  latency: 0,
  isRunning: false,
  tokenCount: 0,
  contextLimit: 128000,
  setPhase: (phase) => set({ phase }),
  setLatency: (latency) => set({ latency }),
  setModel: (modelSlug) => set({ modelSlug }),
  toggleRun: () => set((s) => ({ isRunning: !s.isRunning })),
  addTokens: (count) => set((s) => ({ tokenCount: s.tokenCount + count })),
}));
