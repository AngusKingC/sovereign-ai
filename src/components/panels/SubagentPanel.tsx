"use client";
import { useSubagentStore } from "@/stores/subagentStore";

const STATUS_BADGES: Record<string, { label: string; class: string }> = {
  running: { label: "Running", class: "bg-emerald-500/20 text-emerald-400" },
  waiting: { label: "Waiting", class: "bg-amber-500/20 text-amber-400" },
  complete: { label: "Complete", class: "bg-blue-500/20 text-blue-400" },
  failed: { label: "Failed", class: "bg-red-500/20 text-red-400" },
};

export function SubagentPanel() {
  const { subagents, killSubagent, clearCompleted } = useSubagentStore();

  const running = subagents.filter((s) => s.status === "running");
  const waiting = subagents.filter((s) => s.status === "waiting");
  const done = subagents.filter((s) => s.status === "complete" || s.status === "failed");

  return (
    <div data-testid="subagent-panel" className="p-4 space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Subagents</h2>
        {done.length > 0 && (
          <button onClick={clearCompleted} className="text-sm text-slate-400 hover:text-slate-200">
            Clear completed
          </button>
        )}
      </div>

      {subagents.length === 0 && (
        <p className="text-slate-500 text-sm">No subagents running.</p>
      )}

      {running.length > 0 && (
        <Section title="Running" count={running.length}>
          {running.map((sa) => (
            <SubagentCard key={sa.id} subagent={sa} onKill={() => killSubagent(sa.id)} />
          ))}
        </Section>
      )}

      {waiting.length > 0 && (
        <Section title="Waiting" count={waiting.length}>
          {waiting.map((sa) => (
            <SubagentCard key={sa.id} subagent={sa} onKill={() => killSubagent(sa.id)} />
          ))}
        </Section>
      )}

      {done.length > 0 && (
        <Section title="Completed" count={done.length}>
          {done.map((sa) => (
            <SubagentCard key={sa.id} subagent={sa} />
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-slate-400 mb-2">{title} ({count})</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function SubagentCard({ subagent, onKill }: { subagent: import("@/stores/subagentStore").Subagent; onKill?: () => void }) {
  const badge = STATUS_BADGES[subagent.status];
  return (
    <div className="border border-slate-700 rounded p-3 bg-slate-900">
      <div className="flex justify-between items-start">
        <div>
          <span className="font-mono text-sm">{subagent.id}</span>
          <span className={`ml-2 text-xs px-2 py-0.5 rounded ${badge.class}`}>{badge.label}</span>
        </div>
        {onKill && subagent.status === "running" && (
          <button onClick={onKill} className="text-xs text-red-400 hover:text-red-300">Kill</button>
        )}
      </div>
      <p className="text-sm text-slate-300 mt-1">{subagent.task}</p>
      <div className="text-xs text-slate-500 mt-1">
        Tokens: {subagent.tokenCost}
        {subagent.error && <span className="text-red-400 ml-2">Error: {subagent.error}</span>}
      </div>
    </div>
  );
}
