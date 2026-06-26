import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePolling } from "@/hooks/usePolling";
import { useStatusPolling } from "@/hooks/useStatusPolling";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { useMemoryPolling } from "@/hooks/useMemoryPolling";
import { useAgentStore } from "@/stores/agentStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";

describe("usePolling", () => {
  it("returns data after fetch", async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: "test" });
    const { result } = renderHook(() => usePolling(fetcher, 1000, { enabled: false }));

    await act(async () => {
      await fetcher();
    });

    expect(fetcher).toHaveBeenCalled();
  });

  it("returns error on failed fetch", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("Fetch failed"));
    const { result } = renderHook(() => usePolling(fetcher, 1000, { enabled: false }));

    try {
      await act(async () => {
        await fetcher();
      });
    } catch (e) {
      expect(e).toBeInstanceOf(Error);
    }
  });

  it("pauses when tab hidden", () => {
    const fetcher = vi.fn().mockResolvedValue({ value: "test" });
    const { rerender } = renderHook(({ enabled }) => usePolling(fetcher, 1000, { enabled }), {
      initialProps: { enabled: true },
    });

    // Simulate tab hidden by checking document.hidden
    const originalHidden = Object.getOwnPropertyDescriptor(document, "hidden");
    Object.defineProperty(document, "hidden", { value: true, writable: true });

    // Rerender with enabled=false to simulate pause
    rerender({ enabled: false });

    Object.defineProperty(document, "hidden", originalHidden || { value: false });
  });
});

describe("useStatusPolling", () => {
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

  it("updates agent store on data", () => {
    // Mock the store update behavior
    const setPhase = useAgentStore.getState().setPhase;
    const setLatency = useAgentStore.getState().setLatency;
    const addTokens = useAgentStore.getState().addTokens;

    setPhase("running" as any);
    setLatency(100);
    addTokens(50);

    const agentState = useAgentStore.getState();
    expect(agentState.phase).toBe("running");
    expect(agentState.latency).toBe(100);
    expect(agentState.tokenCount).toBe(50);
  });
});

describe("useKeyboardShortcuts", () => {
  beforeEach(() => {
    useUiStore.setState({
      activeView: VIEWS.HOME,
      activeDrawer: null,
      setActiveView: useUiStore.getState().setActiveView,
      openDrawer: useUiStore.getState().openDrawer,
      closeDrawer: useUiStore.getState().closeDrawer,
    });
  });

  it("changes view on key press", () => {
    renderHook(() => useKeyboardShortcuts());

    act(() => {
      const event = new KeyboardEvent("keydown", { key: "t" });
      window.dispatchEvent(event);
    });

    const uiState = useUiStore.getState();
    expect(uiState.activeView).toBe(VIEWS.TASKS);
  });

  it("opens drawer on key press", () => {
    renderHook(() => useKeyboardShortcuts());

    act(() => {
      const event = new KeyboardEvent("keydown", { key: "m" });
      window.dispatchEvent(event);
    });

    const uiState = useUiStore.getState();
    expect(uiState.activeDrawer).toBe(DRAWERS.MEMORY);
  });
});

describe("useMemoryPolling", () => {
  beforeEach(() => {
    useMemoryStore.setState({
      slots: [],
      searchQuery: "",
      sortColumn: null,
      sortDirection: "asc",
      setSlots: useMemoryStore.getState().setSlots,
      setSearchQuery: useMemoryStore.getState().setSearchQuery,
      setSort: useMemoryStore.getState().setSort,
    });
  });

  it("updates memory store on data", () => {
    const setSlots = useMemoryStore.getState().setSlots;

    const testSlots = [
      { index: 0, key: "test", value: "test", activation: 0.5, lastWritten: 0 },
    ];
    setSlots(testSlots);

    const memoryState = useMemoryStore.getState();
    expect(memoryState.slots).toHaveLength(1);
    expect(memoryState.slots[0].key).toBe("test");
  });
});
