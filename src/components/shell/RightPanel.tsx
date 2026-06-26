"use client";
import { useState } from "react";
import { Wrench, Clock, Brain } from "lucide-react";
import { ToolInspector } from "@/components/panels/ToolInspector";

const TABS = [
  { id: "tools", label: "Tool inspector", icon: Wrench },
  { id: "timeline", label: "Timeline", icon: Clock },
  { id: "reasoning", label: "Reasoning", icon: Brain },
] as const;

type TabId = typeof TABS[number]["id"];

export function RightPanel() {
  const [activeTab, setActiveTab] = useState<TabId>("tools");

  return (
    <aside className="flex flex-col border-l border-border bg-surface-raised">
      <div className="flex border-b border-border">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              activeTab === id
                ? "border-b-2 border-accent-amber text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === "tools" && <ToolInspector />}
        {activeTab === "timeline" && (
          <div className="p-4 font-mono text-xs text-text-muted">
            Session timeline — placeholder. Full implementation deferred to follow-on plan.
          </div>
        )}
        {activeTab === "reasoning" && (
          <div className="p-4 font-mono text-xs text-text-muted">
            Reasoning stream — placeholder. Full implementation deferred to follow-on plan.
          </div>
        )}
      </div>
    </aside>
  );
}
