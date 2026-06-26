import { describe, it, expect, beforeEach } from "vitest";
import { useAgentStore } from "@/stores/agentStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useToolStore } from "@/stores/toolStore";
import { useTaskStore } from "@/stores/taskStore";
import { useWorkerStore } from "@/stores/workerStore";
import { useCostStore } from "@/stores/costStore";
import { useApprovalStore } from "@/stores/approvalStore";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";
import { useModelStore } from "@/stores/modelStore";

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

describe("modelStore", () => {
  beforeEach(() => {
    useModelStore.setState({
      models: [],
      activeModelId: null,
      searchQuery: "",
      filterTag: null,
      filterAdapter: null,
      isLoading: false,
      error: null,
      setModels: useModelStore.getState().setModels,
      setActiveModel: useModelStore.getState().setActiveModel,
      setSearchQuery: useModelStore.getState().setSearchQuery,
      setFilterTag: useModelStore.getState().setFilterTag,
      setFilterAdapter: useModelStore.getState().setFilterAdapter,
      setLoading: useModelStore.getState().setLoading,
      setError: useModelStore.getState().setError,
    });
  });

  it("initializes with default values", () => {
    const state = useModelStore.getState();
    expect(state.models).toEqual([]);
    expect(state.activeModelId).toBeNull();
    expect(state.searchQuery).toBe("");
    expect(state.filterTag).toBeNull();
    expect(state.filterAdapter).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("sets models", () => {
    const models = [
      { model_id: "model-1", name: "Test Model", source: "ollama", adapter_compatibility: ["ollama"], task_tags: ["code"], download_status: "downloaded", downloaded_quantisation: "Q4", license: "MIT", description: "Test" },
    ];
    useModelStore.getState().setModels(models);
    const state = useModelStore.getState();
    expect(state.models).toEqual(models);
  });

  it("sets active model", () => {
    useModelStore.getState().setActiveModel("model-1");
    const state = useModelStore.getState();
    expect(state.activeModelId).toBe("model-1");
  });

  it("sets search query", () => {
    useModelStore.getState().setSearchQuery("test");
    const state = useModelStore.getState();
    expect(state.searchQuery).toBe("test");
  });

  it("sets filter tag", () => {
    useModelStore.getState().setFilterTag("code");
    const state = useModelStore.getState();
    expect(state.filterTag).toBe("code");
  });

  it("sets filter adapter", () => {
    useModelStore.getState().setFilterAdapter("ollama");
    const state = useModelStore.getState();
    expect(state.filterAdapter).toBe("ollama");
  });

  it("sets loading state", () => {
    useModelStore.getState().setLoading(true);
    const state = useModelStore.getState();
    expect(state.isLoading).toBe(true);
  });

  it("sets error", () => {
    useModelStore.getState().setError("Test error");
    const state = useModelStore.getState();
    expect(state.error).toBe("Test error");
  });

  it("clears error", () => {
    useModelStore.getState().setError("Test error");
    useModelStore.getState().setError(null);
    const state = useModelStore.getState();
    expect(state.error).toBeNull();
  });
});

describe("taskStore", () => {
  beforeEach(() => {
    useTaskStore.setState({
      tasks: [],
      activeTask: null,
      addTask: useTaskStore.getState().addTask,
      setActiveTask: useTaskStore.getState().setActiveTask,
      updateTask: useTaskStore.getState().updateTask,
      clearTasks: useTaskStore.getState().clearTasks,
    });
  });

  it("adds task", () => {
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
