"use client";
import { useEffect } from "react";
import { useStatusPolling } from "@/hooks/useStatusPolling";
import { useWorkersPolling } from "@/hooks/useWorkersPolling";
import { useCostsPolling } from "@/hooks/useCostsPolling";
import { useApprovalsPolling } from "@/hooks/useApprovalsPolling";
import { useMemoryPolling } from "@/hooks/useMemoryPolling";
import { useUiStore, VIEWS } from "@/stores/uiStore";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { startErrorLogging } from "@/hooks/useErrorLogger";
import { TasksPanel } from "@/components/panels/TasksPanel";
import { WorkersPanel } from "@/components/panels/WorkersPanel";
import { ApprovalQueuePanel } from "@/components/panels/ApprovalQueuePanel";
import { CostDashboardPanel } from "@/components/panels/CostDashboardPanel";
import { SkillsPanel } from "@/components/panels/SkillsPanel";
import { HelpPanel } from "@/components/panels/HelpPanel";
import { SystemStatsPanel } from "@/components/panels/SystemStatsPanel";
import { SubagentPanel } from "@/components/panels/SubagentPanel";
import { ModelsPanel } from "@/components/panels/ModelsPanel";
import { ResourceMonitorPanel } from "@/components/panels/ResourceMonitorPanel";
import { LogsPanel } from "@/components/panels/LogsPanel";
import dynamic from "next/dynamic";

const TerminalPanel = dynamic(() => import("@/components/panels/TerminalPanel").then(m => m.TerminalPanel), { ssr: false });

export default function Home() {
  useEffect(() => {
    const cleanup = startErrorLogging();
    return cleanup;
  }, []);

  useStatusPolling();
  useWorkersPolling();
  useCostsPolling();
  useApprovalsPolling();
  useMemoryPolling();

  const activeView = useUiStore((s) => s.activeView);

  // Rev3 L8 fix — use VIEWS constants, not raw string literals.
  // Rev3 H7 fix — drawers are NOT rendered here; they render in ShellClient.tsx.
  switch (activeView) {
    case VIEWS.HOME:
      return <ErrorBoundary componentName="TerminalPanel"><TerminalPanel /></ErrorBoundary>;
    case VIEWS.TASKS:
      return <ErrorBoundary componentName="TasksPanel"><TasksPanel /></ErrorBoundary>;
    case VIEWS.WORKERS:
      return <ErrorBoundary componentName="WorkersPanel"><WorkersPanel /></ErrorBoundary>;
    case VIEWS.APPROVALS:
      return <ErrorBoundary componentName="ApprovalQueuePanel"><ApprovalQueuePanel /></ErrorBoundary>;
    case VIEWS.COSTS:
      return <ErrorBoundary componentName="CostDashboardPanel"><CostDashboardPanel /></ErrorBoundary>;
    case VIEWS.TOOLS:
      return <ErrorBoundary componentName="SkillsPanel"><SkillsPanel /></ErrorBoundary>;
    case VIEWS.HELP:
      return <ErrorBoundary componentName="HelpPanel"><HelpPanel /></ErrorBoundary>;
    case VIEWS.TERMINAL:
      return <ErrorBoundary componentName="TerminalPanel"><TerminalPanel /></ErrorBoundary>;
    case VIEWS.SYSTEM:
      return <ErrorBoundary componentName="SystemStatsPanel"><SystemStatsPanel /></ErrorBoundary>;
    case VIEWS.SUBAGENTS:
      return <ErrorBoundary componentName="SubagentPanel"><SubagentPanel /></ErrorBoundary>;
    case VIEWS.MODELS:
      return <ErrorBoundary componentName="ModelsPanel"><ModelsPanel /></ErrorBoundary>;
    case VIEWS.RESOURCES:
      return <ErrorBoundary componentName="ResourceMonitorPanel"><ResourceMonitorPanel /></ErrorBoundary>;
    case VIEWS.LOGS:
      return <ErrorBoundary componentName="LogsPanel"><LogsPanel /></ErrorBoundary>;
    default:
      return <ErrorBoundary componentName="TerminalPanel"><TerminalPanel /></ErrorBoundary>;
  }
}
