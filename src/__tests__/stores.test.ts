import { describe, it, expect, beforeEach } from "vitest";
import { useAgentStore } from "@/stores/agentStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useToolStore } from "@/stores/toolStore";

describe("agentStore", () => {
  beforeEach(() => {
    useAgentStore.setState({
      sessionId: "SES-8f2a",
      phase: "idle",
      modelSlug: "GLM-4.5 Flash",
      latency: 0,
      isRunning: false,
      tokenCount: 0,
      contextLimit: 128000,
      setPhase: useAgentStore.getState().setPhase,
      setLatency: useAgentStore.getState().setLatency,
      setModel: useAgentStore.getState().setModel,
      toggleRun: useAgentStore.getState().toggleRun,
      addTokens: useAgentStore.getState().addTokens,
    });
  });

  it("initializes with default values", () => {
    const state = useAgentStore.getState();
    expect(state.sessionId).toBe("SES-8f2a");
    expect(state.phase).toBe("idle");
    expect(state.isRunning).toBe(false);
  });

  it("toggles run state", () => {
    useAgentStore.getState().toggleRun();
    expect(useAgentStore.getState().isRunning).toBe(true);
    useAgentStore.getState().toggleRun();
    expect(useAgentStore.getState().isRunning).toBe(false);
  });

  it("adds tokens", () => {
    useAgentStore.getState().addTokens(100);
    expect(useAgentStore.getState().tokenCount).toBe(100);
    useAgentStore.getState().addTokens(50);
    expect(useAgentStore.getState().tokenCount).toBe(150);
  });
});

describe("memoryStore", () => {
  beforeEach(() => {
    useMemoryStore.setState({
      slots: new Map(),
      totalSlots: 512,
      activeSlots: 0,
      setActivation: useMemoryStore.getState().setActivation,
      getSlot: useMemoryStore.getState().getSlot,
    });
  });

  it("initializes with empty slots", () => {
    const state = useMemoryStore.getState();
    expect(state.slots.size).toBe(0);
    expect(state.activeSlots).toBe(0);
  });

  it("sets activation", () => {
    // First create a slot (memoryStore doesn't auto-create slots in this stub)
    useMemoryStore.setState({
      slots: new Map([[0, { index: 0, key: "test", value: "test", activation: 0, lastWritten: 0 }]]),
      totalSlots: 512,
      activeSlots: 0,
      setActivation: useMemoryStore.getState().setActivation,
      getSlot: useMemoryStore.getState().getSlot,
    });
    useMemoryStore.getState().setActivation(0, 0.5);
    const slot = useMemoryStore.getState().getSlot(0);
    expect(slot?.activation).toBe(0.5);
    expect(useMemoryStore.getState().activeSlots).toBe(1);
  });
});

describe("toolStore", () => {
  beforeEach(() => {
    useToolStore.setState({
      calls: [],
      addCall: useToolStore.getState().addCall,
      patchCall: useToolStore.getState().patchCall,
      upsertCall: useToolStore.getState().upsertCall,
      clearCalls: useToolStore.getState().clearCalls,
    });
  });

  it("initializes with empty calls", () => {
    const state = useToolStore.getState();
    expect(state.calls).toEqual([]);
  });

  it("adds a call", () => {
    useToolStore.getState().addCall({
      id: "call-1",
      tool: "web_search",
      status: "running",
      args: { query: "test" },
      startedAt: Date.now(),
    });
    const state = useToolStore.getState();
    expect(state.calls).toHaveLength(1);
    expect(state.calls[0].id).toBe("call-1");
  });

  it("upserts a call (add new)", () => {
    useToolStore.getState().upsertCall({
      id: "call-2",
      tool: "memory_write",
      status: "success",
      args: { key: "test" },
      output: "ok",
      durationMs: 100,
      startedAt: Date.now(),
    });
    const state = useToolStore.getState();
    expect(state.calls).toHaveLength(1);
    expect(state.calls[0].id).toBe("call-2");
  });

  it("upserts a call (patch existing)", () => {
    useToolStore.getState().upsertCall({
      id: "call-2",
      tool: "memory_write",
      status: "success",
      args: { key: "test" },
      output: "ok",
      durationMs: 100,
      startedAt: Date.now(),
    });
    useToolStore.getState().upsertCall({
      id: "call-2",
      tool: "memory_write",
      status: "success",
      args: { key: "test" },
      output: "updated",
      durationMs: 150,
      startedAt: Date.now(),
    });
    const state = useToolStore.getState();
    expect(state.calls).toHaveLength(1);
    expect(state.calls[0].output).toBe("updated");
    expect(state.calls[0].durationMs).toBe(150);
  });
});
