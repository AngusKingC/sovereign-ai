"use client";
import { usePolling } from "@/hooks/usePolling";
import { getSystemStats, SystemStats } from "@/lib/api";

export function SystemStatsPanel() {
  const { data, isLoading } = usePolling<SystemStats>(getSystemStats, 5000);

  if (isLoading || !data) {
    return <div data-testid="system-stats-panel" className="p-4">Loading...</div>;
  }

  return (
    <div data-testid="system-stats-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">System Stats</h2>

      <div className="space-y-2">
        <StatBar label="CPU" value={data.cpu_percent} unit="%" max={100} />
        <StatBar label="Memory" value={data.memory_percent} unit="%" max={100} />
        {data.gpu_percent !== undefined && (
          <StatBar label="GPU" value={data.gpu_percent} unit="%" max={100} />
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-slate-500">Uptime:</span>{" "}
          {Math.floor(data.uptime_seconds / 3600)}h {Math.floor((data.uptime_seconds % 3600) / 60)}m
        </div>
        <div>
          <span className="text-slate-500">Active Workers:</span> {data.active_workers}
        </div>
      </div>
    </div>
  );
}

function StatBar({ label, value, unit, max }: { label: string; value: number; unit: string; max: number }) {
  const pct = (value / max) * 100;
  const color = pct > 80 ? "bg-red-500" : pct > 60 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span>{value.toFixed(1)}{unit}</span>
      </div>
      <div className="h-2 bg-slate-800 rounded">
        <div className={`h-full rounded ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
