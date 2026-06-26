"use client";
import { useMemoryStore } from "@/stores/memoryStore";
import { useAgentStore } from "@/stores/agentStore";

export function BottomBar({ className }: { className?: string }) {
  const activeSlots = useMemoryStore((s) => s.activeSlots);
  const totalSlots = useMemoryStore((s) => s.totalSlots);
  const tokenCount = useAgentStore((s) => s.tokenCount);
  const contextLimit = useAgentStore((s) => s.contextLimit);

  return (
    <footer className={`flex h-16 items-center gap-4 border-t border-border bg-surface-raised px-4 ${className ?? ""}`}>
      <div className="flex items-center gap-2">
        <div className="font-mono text-xs text-text-muted">Activation grid placeholder</div>
        <div className="text-xs text-text-secondary">
          {activeSlots}/{totalSlots} active
        </div>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 font-mono text-xs">
        <span className="text-text-muted">Tokens:</span>
        <span className="text-text-primary">{tokenCount.toLocaleString()}</span>
        <span className="text-text-muted">/ {contextLimit.toLocaleString()}</span>
      </div>
    </footer>
  );
}
