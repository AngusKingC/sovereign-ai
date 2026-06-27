import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TasksPanel } from "@/components/panels/TasksPanel";
import { WorkersPanel } from "@/components/panels/WorkersPanel";
import { ApprovalQueuePanel } from "@/components/panels/ApprovalQueuePanel";
import { CostDashboardPanel } from "@/components/panels/CostDashboardPanel";
import { MemoryDrawer } from "@/components/panels/MemoryDrawer";
import { SettingsDrawer } from "@/components/panels/SettingsDrawer";
import { ModelsPanel } from "@/components/panels/ModelsPanel";
import { ResourceMonitorPanel } from "@/components/panels/ResourceMonitorPanel";
import { useTaskStore } from "@/stores/taskStore";
import { useWorkerStore } from "@/stores/workerStore";
import { useApprovalStore } from "@/stores/approvalStore";
import { useCostStore } from "@/stores/costStore";
import { useMemoryStore } from "@/stores/memoryStore";
import { useModelStore } from "@/stores/modelStore";

// Mock API functions for Plan 94 tests
vi.mock("@/lib/api", () => ({
  getCostPolicy: vi.fn(() => Promise.resolve({
    daily_cap_usd: 10.0,
    monthly_cap_usd: 100.0,
    alert_threshold_pct: 0.80,
    fallback_threshold_pct: 0.90,
    fallback_model: null,
  })),
  updateCostPolicy: vi.fn(() => Promise.resolve({
    daily_cap_usd: 20.0,
    monthly_cap_usd: 200.0,
    alert_threshold_pct: 0.80,
    fallback_threshold_pct: 0.90,
    fallback_model: null,
  })),
  getResourceMonitor: vi.fn(() => Promise.resolve({
    cpu_percent: 50.0,
    memory_percent: 60.0,
    disk_percent: 70.0,
    gpu_percent: null,
    gpu_memory_used_mb: null,
    gpu_memory_total_mb: null,
    timestamp: new Date().toISOString(),
  })),
}));

describe("TasksPanel", () => {
  it("renders active tasks section", () => {
    useTaskStore.setState({
      tasks: [
        {
          id: "task-1",
          intent: "test task",
          priority: 1,
          state: "pending",
          created_at: "2024-01-01T00:00:00Z",
        },
      ],
      activeTask: null,
      setTasks: useTaskStore.getState().setTasks,
      addTask: useTaskStore.getState().addTask,
      updateTask: useTaskStore.getState().updateTask,
      setActiveTask: useTaskStore.getState().setActiveTask,
      clearTasks: useTaskStore.getState().clearTasks,
    });

    render(<TasksPanel />);
    expect(screen.getByTestId("tasks-panel")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });
});

describe("WorkersPanel", () => {
  it("renders worker cards with circuit status", () => {
    useWorkerStore.setState({
      workers: [
        {
          worker_id: "worker-1",
          model: "GLM-4.5",
          capabilities: ["code"],
          status: "closed",
        },
      ],
      degradedRatio: 0,
      setWorkers: useWorkerStore.getState().setWorkers,
      setDegradedRatio: useWorkerStore.getState().setDegradedRatio,
      resetCircuit: useWorkerStore.getState().resetCircuit,
    });

    render(<WorkersPanel />);
    expect(screen.getByTestId("workers-panel")).toBeInTheDocument();
    expect(screen.getByText("worker-1")).toBeInTheDocument();
    expect(screen.getByText("CLOSED")).toBeInTheDocument();
  });
});

describe("ApprovalQueuePanel", () => {
  it("renders pending approvals", () => {
    useApprovalStore.setState({
      pending: [
        {
          id: "req-1",
          task_id: "task-1",
          description: "test request",
          proposed_action: "approve",
          created_at: "2024-01-01T00:00:00Z",
        },
      ],
      setPending: useApprovalStore.getState().setPending,
      respond: useApprovalStore.getState().respond,
      removeRequest: useApprovalStore.getState().removeRequest,
    });

    render(<ApprovalQueuePanel />);
    expect(screen.getByTestId("approvals-panel")).toBeInTheDocument();
    expect(screen.getByText("test request")).toBeInTheDocument();
  });
});

describe("CostDashboardPanel", () => {
  it("renders daily progress bar", () => {
    useCostStore.setState({
      summary: {
        total_cost_usd: 100,
        daily_cost_usd: 10,
        monthly_cost_usd: 50,
        model_costs: { "GLM-4.5": 100 },
      },
      setSummary: useCostStore.getState().setSummary,
    });

    render(<CostDashboardPanel />);
    expect(screen.getByTestId("cost-dashboard-panel")).toBeInTheDocument();
    expect(screen.getByText("Daily Spend")).toBeInTheDocument();
  });
});

describe("MemoryDrawer", () => {
  it("renders slot table", () => {
    useMemoryStore.setState({
      slots: [
        { index: 0, key: "test", value: "test", activation: 0.5, lastWritten: 0 },
      ],
      searchQuery: "",
      sortColumn: null,
      sortDirection: "asc",
      setSlots: useMemoryStore.getState().setSlots,
      setSearchQuery: useMemoryStore.getState().setSearchQuery,
      setSort: useMemoryStore.getState().setSort,
    });

    render(<MemoryDrawer />);
    expect(screen.getByTestId("memory-drawer")).toBeInTheDocument();
    expect(screen.getByText("Index")).toBeInTheDocument();
    expect(screen.getByText("Key")).toBeInTheDocument();
  });
});

describe("SettingsDrawer", () => {
  it("renders 4 tabs", () => {
    render(<SettingsDrawer />);
    expect(screen.getByTestId("settings-drawer")).toBeInTheDocument();
    expect(screen.getByText("Cost Policy")).toBeInTheDocument();
    expect(screen.getByText("Circuit Breaker")).toBeInTheDocument();
    expect(screen.getByText("Sandbox")).toBeInTheDocument();
    expect(screen.getByText("Auth")).toBeInTheDocument();
  });
});

describe("ModelsPanel", () => {
  it("renders models panel", () => {
    useModelStore.setState({
      models: [
        { model_id: "model-1", name: "Test Model", source: "ollama", adapter_compatibility: ["ollama"], task_tags: ["code"], download_status: "downloaded", downloaded_quantisation: "Q4", license: "MIT", description: "Test" },
      ],
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

    render(<ModelsPanel />);
    expect(screen.getByTestId("models-panel")).toBeInTheDocument();
    expect(screen.getByText("Models")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    useModelStore.setState({
      models: [],
      activeModelId: null,
      searchQuery: "",
      filterTag: null,
      filterAdapter: null,
      isLoading: true,
      error: null,
      setModels: useModelStore.getState().setModels,
      setActiveModel: useModelStore.getState().setActiveModel,
      setSearchQuery: useModelStore.getState().setSearchQuery,
      setFilterTag: useModelStore.getState().setFilterTag,
      setFilterAdapter: useModelStore.getState().setFilterAdapter,
      setLoading: useModelStore.getState().setLoading,
      setError: useModelStore.getState().setError,
    });

    render(<ModelsPanel />);
    expect(screen.getByTestId("models-panel")).toBeInTheDocument();
    expect(screen.getByText("Loading models...")).toBeInTheDocument();
  });

  it("renders model cards", () => {
    useModelStore.setState({
      models: [
        { model_id: "model-1", name: "Test Model", source: "ollama", adapter_compatibility: ["ollama"], task_tags: ["code"], download_status: "downloaded", downloaded_quantisation: "Q4", license: "MIT", description: "Test" },
      ],
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

    render(<ModelsPanel />);
    expect(screen.getByText("Test Model")).toBeInTheDocument();
    expect(screen.getByText("model-1")).toBeInTheDocument();
  });
});

describe("WorkerCreator", () => {
  it("renders form with description and task intent fields", () => {
    render(<WorkerCreator onClose={() => {}} />);
    expect(screen.getByTestId("worker-creator")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e.g., Create a Python code review worker/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/What task will this worker handle?/)).toBeInTheDocument();
  });

  it("shows Create Worker button", () => {
    render(<WorkerCreator onClose={() => {}} />);
    expect(screen.getByText("Create Worker")).toBeInTheDocument();
  });
});

describe("WorkerEditor", () => {
  it("renders config fields for worker", () => {
    const mockWorker: WorkerProfile = {
      worker_id: "test-worker",
      worker_type: "code_worker",
      name: "Test Worker",
      description: "A test worker",
      purpose: "Testing",
      capabilities: ["code"],
      complexity_min: 0.3,
      complexity_max: 0.8,
      preferred_complexity: 0.5,
      depth_preference: 0.6,
      speculation_tolerance: 0.4,
      source_skepticism: 0.5,
      verbosity: 0.7,
      standing_instructions: ["Be thorough"],
      preferred_model: "gpt-4",
      preferred_models: ["gpt-4"],
      escalation_threshold: 0.8,
      tasks_completed: 10,
      avg_confidence: 0.85,
      performance_score: 0.9,
      active_tasks: 2,
      status: "active",
    };

    render(<WorkerEditor worker={mockWorker} onClose={() => {}} />);
    expect(screen.getByTestId("worker-editor")).toBeInTheDocument();
    expect(screen.getByText("Edit Test Worker")).toBeInTheDocument();
    expect(screen.getByText("Complexity Min")).toBeInTheDocument();
    expect(screen.getByText("Verbosity")).toBeInTheDocument();
    expect(screen.getByText("Preferred Model")).toBeInTheDocument();
  });

  it("shows Save and Delete buttons", () => {
    const mockWorker: WorkerProfile = {
      worker_id: "test-worker",
      worker_type: "code_worker",
      name: "Test Worker",
      description: "A test worker",
      purpose: "Testing",
      capabilities: ["code"],
      complexity_min: 0.3,
      complexity_max: 0.8,
      preferred_complexity: 0.5,
      depth_preference: 0.6,
      speculation_tolerance: 0.4,
      source_skepticism: 0.5,
      verbosity: 0.7,
      standing_instructions: ["Be thorough"],
      preferred_model: "gpt-4",
      preferred_models: ["gpt-4"],
      escalation_threshold: 0.8,
      tasks_completed: 10,
      avg_confidence: 0.85,
      performance_score: 0.9,
      active_tasks: 2,
      status: "active",
    };

    render(<WorkerEditor worker={mockWorker} onClose={() => {}} />);
    expect(screen.getByText("Delete Worker")).toBeInTheDocument();
    expect(screen.getByText("Save")).toBeInTheDocument();
  });
});

describe("WorkersPanel with Create Button", () => {
  it("shows Create Worker button in header", () => {
    useWorkerStore.setState({
      workers: [],
      degradedRatio: 0,
      setWorkers: useWorkerStore.getState().setWorkers,
      setDegradedRatio: useWorkerStore.getState().setDegradedRatio,
      resetCircuit: useWorkerStore.getState().resetCircuit,
      createWorker: useWorkerStore.getState().createWorker,
      updateWorker: useWorkerStore.getState().updateWorker,
      deleteWorker: useWorkerStore.getState().deleteWorker,
      setSelectedWorker: useWorkerStore.getState().setSelectedWorker,
      selectedWorkerId: null,
      loadWorkers: useWorkerStore.getState().loadWorkers,
    });

    render(<WorkersPanel />);
    expect(screen.getByText("+ Create Worker")).toBeInTheDocument();
  });
});


describe("WorkerCreator", () => {
  it("renders form with description and task intent fields", () => {
    render(<WorkerCreator onClose={() => {}} />);
    expect(screen.getByTestId("worker-creator")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e.g., Create a Python code review worker/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/What task will this worker handle?/)).toBeInTheDocument();
  });

  it("shows Create Worker button", () => {
    render(<WorkerCreator onClose={() => {}} />);
    expect(screen.getByText("Create Worker")).toBeInTheDocument();
  });
});

describe("WorkerEditor", () => {
  it("renders config fields for worker", () => {
    const mockWorker: WorkerProfile = {
      worker_id: "test-worker",
      worker_type: "code_worker",
      name: "Test Worker",
      description: "A test worker",
      purpose: "Testing",
      capabilities: ["code"],
      complexity_min: 0.3,
      complexity_max: 0.8,
      preferred_complexity: 0.5,
      depth_preference: 0.6,
      speculation_tolerance: 0.4,
      source_skepticism: 0.5,
      verbosity: 0.7,
      standing_instructions: ["Be thorough"],
      preferred_model: "gpt-4",
      preferred_models: ["gpt-4"],
      escalation_threshold: 0.8,
      tasks_completed: 10,
      avg_confidence: 0.85,
      performance_score: 0.9,
      active_tasks: 2,
      status: "active",
    };

    render(<WorkerEditor worker={mockWorker} onClose={() => {}} />);
    expect(screen.getByTestId("worker-editor")).toBeInTheDocument();
    expect(screen.getByText("Edit Test Worker")).toBeInTheDocument();
    expect(screen.getByText("Complexity Min")).toBeInTheDocument();
    expect(screen.getByText("Verbosity")).toBeInTheDocument();
    expect(screen.getByText("Preferred Model")).toBeInTheDocument();
  });

  it("shows Save and Delete buttons", () => {
    const mockWorker: WorkerProfile = {
      worker_id: "test-worker",
      worker_type: "code_worker",
      name: "Test Worker",
      description: "A test worker",
      purpose: "Testing",
      capabilities: ["code"],
      complexity_min: 0.3,
      complexity_max: 0.8,
      preferred_complexity: 0.5,
      depth_preference: 0.6,
      speculation_tolerance: 0.4,
      source_skepticism: 0.5,
      verbosity: 0.7,
      standing_instructions: ["Be thorough"],
      preferred_model: "gpt-4",
      preferred_models: ["gpt-4"],
      escalation_threshold: 0.8,
      tasks_completed: 10,
      avg_confidence: 0.85,
      performance_score: 0.9,
      active_tasks: 2,
      status: "active",
    };

    render(<WorkerEditor worker={mockWorker} onClose={() => {}} />);
    expect(screen.getByText("Delete Worker")).toBeInTheDocument();
    expect(screen.getByText("Save")).toBeInTheDocument();
  });
});

describe("WorkersPanel with Create Button", () => {
  it("shows Create Worker button in header", () => {
    useWorkerStore.setState({
      workers: [],
      degradedRatio: 0,
      setWorkers: useWorkerStore.getState().setWorkers,
      setDegradedRatio: useWorkerStore.getState().setDegradedRatio,
      resetCircuit: useWorkerStore.getState().resetCircuit,
      createWorker: useWorkerStore.getState().createWorker,
      updateWorker: useWorkerStore.getState().updateWorker,
      deleteWorker: useWorkerStore.getState().deleteWorker,
      setSelectedWorker: useWorkerStore.getState().setSelectedWorker,
      selectedWorkerId: null,
      loadWorkers: useWorkerStore.getState().loadWorkers,
    });

    render(<WorkersPanel />);
    expect(screen.getByText("+ Create Worker")).toBeInTheDocument();
  });
});

describe("SettingsDrawer Cost Policy Tab (Plan 94)", () => {
  it("renders cost policy inputs when cost tab is active", async () => {
    render(<SettingsDrawer />);
    expect(screen.getByText("Daily Cap ($)")).toBeInTheDocument();
    expect(screen.getByText("Monthly Cap ($)")).toBeInTheDocument();
    expect(screen.getByText("Alert Threshold (%)")).toBeInTheDocument();
  });

  it("renders Save Policy button", async () => {
    render(<SettingsDrawer />);
    expect(screen.getByText("Save Policy")).toBeInTheDocument();
  });
});

describe("ResourceMonitorPanel (Plan 94)", () => {
  it("renders resource monitor with metric cards", async () => {
    render(<ResourceMonitorPanel />);
    expect(screen.getByText("Resource Monitor")).toBeInTheDocument();
    expect(screen.getByText("CPU")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Disk")).toBeInTheDocument();
  });

  it("renders GPU metric when GPU data available", async () => {
    render(<ResourceMonitorPanel />);
    expect(screen.getByText("GPU")).toBeInTheDocument();
  });
});
