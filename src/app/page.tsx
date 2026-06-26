"use client";
import { useStatusPolling } from "@/hooks/useStatusPolling";
import { useWorkersPolling } from "@/hooks/useWorkersPolling";
import { useCostsPolling } from "@/hooks/useCostsPolling";
import { useApprovalsPolling } from "@/hooks/useApprovalsPolling";
import { useMemoryPolling } from "@/hooks/useMemoryPolling";
import { useUiStore, VIEWS } from "@/stores/uiStore";
import { TasksPanel } from "@/components/panels/TasksPanel";
import { WorkersPanel } from "@/components/panels/WorkersPanel";
import { ApprovalQueuePanel } from "@/components/panels/ApprovalQueuePanel";
import { CostDashboardPanel } from "@/components/panels/CostDashboardPanel";
import { SkillsPanel } from "@/components/panels/SkillsPanel";
import { HelpPanel } from "@/components/panels/HelpPanel";
import { TerminalPlaceholder } from "@/components/panels/TerminalPlaceholder";

export default function Home() {
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
      return <TerminalPlaceholder />;
    case VIEWS.TASKS:
      return <TasksPanel />;
    case VIEWS.WORKERS:
      return <WorkersPanel />;
    case VIEWS.APPROVALS:
      return <ApprovalQueuePanel />;
    case VIEWS.COSTS:
      return <CostDashboardPanel />;
    case VIEWS.TOOLS:
      return <SkillsPanel />;
    case VIEWS.HELP:
      return <HelpPanel />;
    default:
      return <TerminalPlaceholder />;
  }
}
