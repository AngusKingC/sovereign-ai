import { describe, it, expect, beforeEach } from "vitest";
import { useAgentStore } from "@/stores/agentStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useToolStore } from "@/stores/toolStore";
import { useTaskStore } from "@/stores/taskStore";
import { useWorkerStore } from "@/stores/workerStore";
import { useCostStore } from "@/stores/costStore";
import { useApprovalStore } from "@/stores/approvalStore";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";

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
      slots: [],
      searchQuery: "",
      sortColumn: null,
      sortDirection: "asc",
      setSlots: useMemoryStore.getState().setSlots,
      setSearchQuery: useMemoryStore.getState().setSearchQuery,
      setSort: useMemoryStore.getState().setSort,
    });
  });

  it("initializes with empty slots", () => {
    const state = useMemoryStore.getState();
    expect(state.slots).toEqual([]);
    expect(state.searchQuery).toBe("");
  });

  it("sets slots", () => {
    const testSlots = [
      { index: 0, key: "test", value: "test", activation: 0.5, lastWritten: 0 },
    ];
    useMemoryStore.getState().setSlots(testSlots);
    const state = useMemoryStore.getState();
    expect(state.slots).toEqual(testSlots);
  });

  it("sets search query", () => {
    useMemoryStore.getState().setSearchQuery("test query");
    const state = useMemoryStore.getState();
    expect(state.searchQuery).toBe("test query");
  });

  it("sets sort", () => {
    useMemoryStore.getState().setSort("activation", "desc");
    const state = useMemoryStore.getState();
    expect(state.sortColumn).toBe("activation");
    expect(state.sortDirection).toBe("desc");
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

describe("taskStore", () => {
  beforeEach(() => {
    useTaskStore.setState({
      tasks: [],
      activeTask: null,
      setTasks: useTaskStore.getState().setTasks,
      addTask: useTaskStore.getState().addTask,
      updateTask: useTaskStore.getState().updateTask,
      setActiveTask: useTaskStore.getState().setActiveTask,
      clearTasks: useTaskStore.getState().clearTasks,
    });
  });

  it("adds a task", () => {
    const task = {
      id: "task-1",
      intent: "test task",
      priority: 1,
      state: "pending",
      created_at: "2024-01-01T00:00:00Z",
    };
    useTaskStore.getState().addTask(task);
    const state = useTaskStore.getState();
    expect(state.tasks).toHaveLength(1);
    expect(state.tasks[0].id).toBe("task-1");
  });

  it("updates task by id", () => {
    const task = {
      id: "task-1",
      intent: "test task",
      priority: 1,
      state: "pending",
      created_at: "2024-01-01T00:00:00Z",
    };
    useTaskStore.getState().addTask(task);
    useTaskStore.getState().updateTask("task-1", { state: "completed" });
    const state = useTaskStore.getState();
    expect(state.tasks[0].state).toBe("completed");
  });

  it("sets active task", () => {
    const task = {
      id: "task-1",
      intent: "test task",
      priority: 1,
      state: "pending",
      created_at: "2024-01-01T00:00:00Z",
    };
    useTaskStore.getState().setActiveTask(task);
    const state = useTaskStore.getState();
    expect(state.activeTask).toEqual(task);
  });

  it("clears all tasks", () => {
    const task = {
      id: "task-1",
      intent: "test task",
      priority: 1,
      state: "pending",
      created_at: "2024-01-01T00:00:00Z",
    };
    useTaskStore.getState().addTask(task);
    useTaskStore.getState().setActiveTask(task);
    useTaskStore.getState().clearTasks();
    const state = useTaskStore.getState();
    expect(state.tasks).toEqual([]);
    expect(state.activeTask).toBeNull();
  });
});

describe("workerStore", () => {
  beforeEach(() => {
    useWorkerStore.setState({
      workers: [],
      degradedRatio: 0,
      setWorkers: useWorkerStore.getState().setWorkers,
      setDegradedRatio: useWorkerStore.getState().setDegradedRatio,
      resetCircuit: useWorkerStore.getState().resetCircuit,
    });
  });

  it("sets workers", () => {
    const workers = [
      { worker_id: "worker-1", model: "GLM-4.5", capabilities: ["code"], status: "active" },
    ];
    useWorkerStore.getState().setWorkers(workers);
    const state = useWorkerStore.getState();
    expect(state.workers).toEqual(workers);
  });

  it("sets degraded ratio", () => {
    useWorkerStore.getState().setDegradedRatio(0.5);
    const state = useWorkerStore.getState();
    expect(state.degradedRatio).toBe(0.5);
  });

  it("resets circuit for worker", () => {
    useWorkerStore.getState().setDegradedRatio(0.8);
    useWorkerStore.getState().resetCircuit();
    const state = useWorkerStore.getState();
    expect(state.degradedRatio).toBe(0);
  });

  it("preserves other workers on reset", () => {
    const workers = [
      { worker_id: "worker-1", model: "GLM-4.5", capabilities: ["code"], status: "active" },
      { worker_id: "worker-2", model: "GLM-4.5", capabilities: ["chat"], status: "active" },
    ];
    useWorkerStore.getState().setWorkers(workers);
    useWorkerStore.getState().setDegradedRatio(0.8);
    useWorkerStore.getState().resetCircuit();
    const state = useWorkerStore.getState();
    expect(state.workers).toEqual(workers);
    expect(state.degradedRatio).toBe(0);
  });
});

describe("costStore", () => {
  beforeEach(() => {
    useCostStore.setState({
      summary: null,
      setSummary: useCostStore.getState().setSummary,
    });
  });

  it("sets summary", () => {
    const summary = {
      total_cost_usd: 100,
      daily_cost_usd: 10,
      monthly_cost_usd: 50,
      model_costs: { "GLM-4.5": 100 },
    };
    useCostStore.getState().setSummary(summary);
    const state = useCostStore.getState();
    expect(state.summary).toEqual(summary);
  });

  it("handles null summary", () => {
    const summary = {
      total_cost_usd: 100,
      daily_cost_usd: 10,
      monthly_cost_usd: 50,
      model_costs: { "GLM-4.5": 100 },
    };
    useCostStore.getState().setSummary(summary);
    useCostStore.getState().setSummary(null as any);
    const state = useCostStore.getState();
    expect(state.summary).toBeNull();
  });
});

describe("approvalStore", () => {
  beforeEach(() => {
    useApprovalStore.setState({
      pending: [],
      setPending: useApprovalStore.getState().setPending,
      respond: useApprovalStore.getState().respond,
      removeRequest: useApprovalStore.getState().removeRequest,
    });
  });

  it("sets pending requests", () => {
    const requests = [
      {
        id: "req-1",
        task_id: "task-1",
        description: "test request",
        proposed_action: "approve",
        created_at: "2024-01-01T00:00:00Z",
      },
    ];
    useApprovalStore.getState().setPending(requests);
    const state = useApprovalStore.getState();
    expect(state.pending).toEqual(requests);
  });

  it("removes responded request", () => {
    const requests = [
      {
        id: "req-1",
        task_id: "task-1",
        description: "test request",
        proposed_action: "approve",
        created_at: "2024-01-01T00:00:00Z",
      },
    ];
    useApprovalStore.getState().setPending(requests);
    useApprovalStore.getState().respond("req-1", true);
    const state = useApprovalStore.getState();
    expect(state.pending).toHaveLength(0);
  });

  it("removes by id", () => {
    const requests = [
      {
        id: "req-1",
        task_id: "task-1",
        description: "test request",
        proposed_action: "approve",
        created_at: "2024-01-01T00:00:00Z",
      },
    ];
    useApprovalStore.getState().setPending(requests);
    useApprovalStore.getState().removeRequest("req-1");
    const state = useApprovalStore.getState();
    expect(state.pending).toHaveLength(0);
  });
});

describe("memoryStore", () => {
  it("filters by search query", () => {
    const testSlots = [
      { index: 0, key: "test", value: "test", activation: 0.5, lastWritten: 0 },
      { index: 1, key: "other", value: "other", activation: 0.3, lastWritten: 0 },
    ];
    useMemoryStore.getState().setSlots(testSlots);
    useMemoryStore.getState().setSearchQuery("test");
    const state = useMemoryStore.getState();
    expect(state.searchQuery).toBe("test");
  });
});

describe("uiStore", () => {
  beforeEach(() => {
    useUiStore.setState({
      activeView: VIEWS.HOME,
      activeDrawer: null,
      setActiveView: useUiStore.getState().setActiveView,
      openDrawer: useUiStore.getState().openDrawer,
      closeDrawer: useUiStore.getState().closeDrawer,
    });
  });

  it("sets active view", () => {
    useUiStore.getState().setActiveView(VIEWS.TASKS);
    const state = useUiStore.getState();
    expect(state.activeView).toBe(VIEWS.TASKS);
  });

  it("opens drawer", () => {
    useUiStore.getState().openDrawer(DRAWERS.MEMORY);
    const state = useUiStore.getState();
    expect(state.activeDrawer).toBe(DRAWERS.MEMORY);
  });

  it("closes drawer", () => {
    useUiStore.getState().openDrawer(DRAWERS.SETTINGS);
    useUiStore.getState().closeDrawer();
    const state = useUiStore.getState();
    expect(state.activeDrawer).toBeNull();
  });
});
