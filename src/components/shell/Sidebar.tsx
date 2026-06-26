"use client";
import { Home, ListTodo, Users, Shield, DollarSign, Wrench, HelpCircle, Database, Settings, Terminal as TerminalIcon, Activity as ActivityIcon, Boxes } from "lucide-react";
import { useUiStore, VIEWS, DRAWERS } from "@/stores/uiStore";

const NAV_ITEMS = [
  { icon: Home, label: "Home", view: VIEWS.HOME },
  { icon: ListTodo, label: "Tasks", view: VIEWS.TASKS },
  { icon: Users, label: "Workers", view: VIEWS.WORKERS },
  { icon: Shield, label: "Approvals", view: VIEWS.APPROVALS },
  { icon: DollarSign, label: "Costs", view: VIEWS.COSTS },
  { icon: Wrench, label: "Tools", view: VIEWS.TOOLS },
  { icon: HelpCircle, label: "Help", view: VIEWS.HELP },
  { icon: TerminalIcon, label: "Terminal", view: VIEWS.TERMINAL },
  { icon: ActivityIcon, label: "System", view: VIEWS.SYSTEM },
  { icon: Users, label: "Subagents", view: VIEWS.SUBAGENTS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
  { icon: Boxes, label: "Models", view: VIEWS.MODELS },
];

export function Sidebar() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const openDrawer = useUiStore((s) => s.openDrawer);

  return (
    <nav className="sidebar flex h-full flex-col gap-1 border-r border-border bg-surface-raised p-2" data-testid="sidebar">
      <div className="mb-4 px-2 py-2 font-sans text-sm font-medium text-text-primary">JArvis</div>
      {NAV_ITEMS.map(({ icon: Icon, label, view }) => (
        <button
          key={label}
          onClick={() => setActiveView(view)}
          className={`flex items-center gap-3 rounded p-2 hover:bg-surface-overlay ${
            activeView === view ? "border-l-2 border-accent-amber bg-surface-overlay" : ""
          }`}
          aria-label={label}
        >
          <Icon size={20} className="shrink-0 text-text-secondary" />
          <span className="text-sm text-text-secondary">{label}</span>
        </button>
      ))}
      <div className="my-2 border-t border-border" />
      <button
        onClick={() => openDrawer(DRAWERS.MEMORY)}
        className="flex items-center gap-3 rounded p-2 hover:bg-surface-overlay"
        aria-label="Memory"
      >
        <Database size={20} className="shrink-0 text-text-secondary" />
        <span className="text-sm text-text-secondary">Memory</span>
      </button>
      <button
        onClick={() => openDrawer(DRAWERS.SETTINGS)}
        className="flex items-center gap-3 rounded p-2 hover:bg-surface-overlay"
        aria-label="Settings"
      >
        <Settings size={20} className="shrink-0 text-text-secondary" />
        <span className="text-sm text-text-secondary">Settings</span>
      </button>
    </nav>
  );
}
