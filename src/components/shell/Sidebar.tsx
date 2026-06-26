"use client";
import { Terminal, MemoryStick, Users, Wrench, Settings, HelpCircle } from "lucide-react";
import { useState } from "react";

const NAV_ITEMS = [
  { icon: Terminal, label: "Terminal" },
  { icon: MemoryStick, label: "Memory" },
  { icon: Users, label: "Subagents" },
  { icon: Wrench, label: "Tools" },
  { icon: Settings, label: "Settings" },
  { icon: HelpCircle, label: "Help" },
];

export function Sidebar() {
  const [hovered, setHovered] = useState(false);

  return (
    <nav
      className="flex h-full flex-col gap-1 border-r border-border bg-surface-raised p-2 transition-all duration-200"
      style={{ width: hovered ? "200px" : "64px" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="mb-4 px-2 py-2 font-sans text-sm font-medium text-text-primary">
        {hovered ? "Sovereign" : "S"}
      </div>
      {NAV_ITEMS.map(({ icon: Icon, label }) => (
        <button
          key={label}
          className="flex items-center gap-3 rounded p-2 hover:bg-surface-overlay"
          aria-label={label}
        >
          <Icon size={20} className="shrink-0 text-text-secondary" />
          {hovered && <span className="text-sm text-text-secondary">{label}</span>}
        </button>
      ))}
    </nav>
  );
}
