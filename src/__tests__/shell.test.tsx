import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBar } from "@/components/shell/StatusBar";
import { Sidebar } from "@/components/shell/Sidebar";
import { BottomBar } from "@/components/shell/BottomBar";
import { RightPanel } from "@/components/shell/RightPanel";
import { useAgentStore } from "@/stores/agentStore";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";

describe("Sidebar", () => {
  beforeEach(() => {
    useUiStore.setState({
      activeView: VIEWS.HOME,
      activeDrawer: null,
      setActiveView: useUiStore.getState().setActiveView,
      openDrawer: useUiStore.getState().openDrawer,
      closeDrawer: useUiStore.getState().closeDrawer,
    });
  });

  it("renders 7 nav items + 2 drawer buttons", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Tasks")).toBeInTheDocument();
    expect(screen.getByText("Workers")).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    expect(screen.getByText("Costs")).toBeInTheDocument();
    expect(screen.getByText("Tools")).toBeInTheDocument();
    expect(screen.getByText("Help")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("sets active view on click", () => {
    render(<Sidebar />);
    const tasksButton = screen.getByRole("button", { name: "Tasks" });
    tasksButton.click();
    expect(useUiStore.getState().activeView).toBe(VIEWS.TASKS);
  });
});

describe("StatusBar", () => {
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

  it("renders phase badge", () => {
    render(<StatusBar />);
    expect(screen.getByTestId("status-bar")).toBeInTheDocument();
    expect(screen.getByText(/Sovereign/)).toBeInTheDocument();
  });
});

describe("BottomBar", () => {
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

  it("renders activation grid canvas", () => {
    render(<BottomBar />);
    expect(screen.getByTestId("bottom-bar")).toBeInTheDocument();
    expect(screen.getByText("Activation grid")).toBeInTheDocument();
  });
});

describe("RightPanel", () => {
  it("renders 3 tabs", () => {
    render(<RightPanel />);
    expect(screen.getByText("Tool inspector")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Reasoning")).toBeInTheDocument();
  });
});
