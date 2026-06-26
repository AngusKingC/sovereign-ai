"use client";
import { useState } from "react";
import { useToolStore } from "@/stores/toolStore";
import { useSSE } from "@/hooks/useSSE";
import { sseUrl } from "@/lib/api";
import { ChevronDown, ChevronRight } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-accent-violet animate-pulse",
  success: "bg-accent-emerald",
  warning: "bg-accent-amber",
  error: "bg-accent-red",
};

const LATENCY_COLORS: Record<string, string> = {
  fast: "bg-accent-emerald",
  medium: "bg-accent-amber",
  slow: "bg-accent-red",
};

function getLatencyClass(ms: number | undefined): string {
  if (ms === undefined) return LATENCY_COLORS.fast;
  if (ms < 200) return LATENCY_COLORS.fast;
  if (ms < 500) return LATENCY_COLORS.medium;
  return LATENCY_COLORS.slow;
}

function ToolCallCard({
  call,
}: {
  call: import("@/stores/toolStore").ToolCall;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="border-b border-border bg-surface-raised transition-colors hover:bg-surface-overlay"
      role="button"
      tabIndex={0}
      onClick={() => setExpanded(!expanded)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") setExpanded(!expanded);
      }}
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <span
          className={`h-2 w-2 rounded-full ${STATUS_COLORS[call.status] ?? STATUS_COLORS.running}`}
          aria-label={`Status: ${call.status}`}
        />
        <span className="font-mono text-xs text-text-primary">{call.tool}</span>
        <div className="flex-1" />
        {call.durationMs !== undefined && (
          <span className="font-mono text-xs text-text-muted">{call.durationMs}ms</span>
        )}
        {expanded ? (
          <ChevronDown size={14} className="text-text-muted" />
        ) : (
          <ChevronRight size={14} className="text-text-muted" />
        )}
      </div>
      {expanded && (
        <div className="border-t border-border px-3 py-2">
          <div className="mb-2">
            <div className="mb-1 text-xs text-text-muted">Arguments</div>
            <div className="grid grid-cols-2 gap-1">
              {Object.entries(call.args).map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <span className="text-xs text-text-muted">{key}:</span>
                  <code className="rounded bg-surface-base px-1 font-mono text-xs text-text-primary">
                    {JSON.stringify(value)}
                  </code>
                </div>
              ))}
            </div>
          </div>
          {call.output && (
            <div className="mb-2">
              <div className="mb-1 text-xs text-text-muted">Output</div>
              <pre className="max-h-40 overflow-y-auto rounded bg-surface-base p-2 font-mono text-xs text-text-primary">
                {call.output}
              </pre>
            </div>
          )}
          {call.durationMs !== undefined && (
            <div>
              <div className="mb-1 text-xs text-text-muted">Latency</div>
              <div className="h-1 w-full overflow-hidden rounded bg-surface-base">
                <div
                  className={`h-full ${getLatencyClass(call.durationMs)}`}
                  style={{ width: `${Math.min(100, (call.durationMs / 1000) * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolInspector() {
  const calls = useToolStore((s) => s.calls);
  const upsertCall = useToolStore((s) => s.upsertCall);

  useSSE({
    url: sseUrl("/api/tools/stream"),
    onMessage: (data) => {
      const event = data as import("@/lib/api").ToolCallEvent;
      upsertCall({
        id: event.id,
        tool: event.tool,
        status: event.status,
        args: event.args,
        output: event.output,
        durationMs: event.durationMs,
        startedAt: Date.now(),
      });
    },
  });

  return (
    <div
      className="flex h-full flex-col"
      aria-live="polite"
      aria-label="Tool call inspector — live updates"
    >
      <div className="border-b border-border px-3 py-2 text-xs text-text-muted">
        {calls.length} call{calls.length !== 1 ? "s" : ""} (max 50 retained)
      </div>
      <div className="flex-1 overflow-y-auto">
        {calls.length === 0 ? (
          <div className="p-4 font-mono text-xs text-text-muted">
            Waiting for tool call events...
          </div>
        ) : (
          calls.map((call) => <ToolCallCard key={call.id} call={call} />)
        )}
      </div>
    </div>
  );
}
