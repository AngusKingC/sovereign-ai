import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TasksPanel } from "@/components/panels/TasksPanel";
import { WorkersPanel } from "@/components/panels/WorkersPanel";
import { ApprovalQueuePanel } from "@/components/panels/ApprovalQueuePanel";
import { CostDashboardPanel } from "@/components/panels/CostDashboardPanel";
import { MemoryDrawer } from "@/components/panels/MemoryDrawer";
import { SettingsDrawer } from "@/components/panels/SettingsDrawer";
import { useTaskStore } from "@/stores/taskStore";
import { useWorkerStore } from "@/stores/workerStore";
import { useApprovalStore } from "@/stores/approvalStore";
import { useCostStore } from "@/stores/costStore";
import { useMemoryStore } from "@/stores/memoryStore";

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
      remove: useApprovalStore.getState().remove,
    });

    render(<ApprovalQueuePanel />);
    expect(screen.getByTestId("approval-queue-panel")).toBeInTheDocument();
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
