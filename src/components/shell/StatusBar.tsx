"use client";
import { useAgentStore } from "@/stores/agentStore";
import { useUiStore, DRAWERS } from "@/stores/uiStore";
import { Play, Pause, Settings, Copy } from "lucide-react";
import { useState } from "react";

const PHASE_COLORS: Record<string, string> = {
  idle: "bg-accent-slate",
  planning: "bg-accent-amber",
  acting: "bg-accent-emerald",
  reflecting: "bg-accent-violet",
};

export function StatusBar({ className }: { className?: string }) {
  const { sessionId, phase, modelSlug, latency, isRunning, toggleRun } = useAgentStore();
  const openDrawer = useUiStore((s) => s.openDrawer);
  const [copied, setCopied] = useState(false);

  const copySessionId = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  return (
    <header
      className={`status-bar sticky top-0 z-50 flex h-12 items-center gap-4 border-b border-border bg-surface-raised px-4 ${className ?? ""}`}
      data-testid="status-bar"
    >
      <button
        onClick={copySessionId}
        className="font-mono text-xs text-text-secondary hover:text-text-primary"
        aria-label="Copy session ID"
      >
        {copied ? "Copied!" : sessionId}
      </button>
      <span
        className={`rounded px-2 py-0.5 text-xs text-surface-base transition-colors duration-300 ${PHASE_COLORS[phase] ?? PHASE_COLORS.idle}`}
      >
        Sovereign · {phase.charAt(0).toUpperCase() + phase.slice(1)}
      </span>
      <button className="font-mono text-xs text-text-secondary hover:text-text-primary" aria-label="Open model picker" title="Coming in Plan 89">
        {modelSlug}
      </button>
      <span className="font-mono text-xs text-text-muted">{latency}ms</span>
      <div className="flex-1" />
      <button
        onClick={toggleRun}
        className="rounded p-1.5 hover:bg-surface-overlay"
        aria-label={isRunning ? "Pause" : "Run"}
      >
        {isRunning ? <Pause size={16} /> : <Play size={16} />}
      </button>
      <button
        onClick={() => openDrawer(DRAWERS.SETTINGS)}
        className="rounded p-1.5 hover:bg-surface-overlay"
        aria-label="Open settings"
      >
        <Settings size={16} />
      </button>
    </header>
  );
}
