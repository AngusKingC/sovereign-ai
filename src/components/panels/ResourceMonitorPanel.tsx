"use client";

import { useState, useEffect } from "react";
import { getResourceMonitor, ResourceMonitor } from "@/lib/api";

export function ResourceMonitorPanel() {
  const [monitor, setMonitor] = useState<ResourceMonitor | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");

  useEffect(() => {
    let mounted = true;

    const fetchMonitor = async () => {
      try {
        const data = await getResourceMonitor();
        if (mounted) {
          setMonitor(data);
          setLastUpdate(new Date().toLocaleTimeString());
          setError(null);
        }
      } catch (e) {
        if (mounted) {
          setError(e instanceof Error ? e.message : "Failed to fetch resource data");
        }
      }
    };

    fetchMonitor();
    const interval = setInterval(fetchMonitor, 5000); // Poll every 5 seconds

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (!monitor && !error) {
    return <div className="p-4">Loading resource monitor...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-500">Error: {error}</div>;
  }

  if (!monitor) return null;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">Resource Monitor</h2>
        <span className="text-sm text-gray-500">Last update: {lastUpdate}</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label="CPU"
          value={monitor.cpu_percent}
          unit="%"
          color={monitor.cpu_percent > 80 ? "red" : monitor.cpu_percent > 60 ? "yellow" : "green"}
        />
        <MetricCard
          label="Memory"
          value={monitor.memory_percent}
          unit="%"
          color={monitor.memory_percent > 80 ? "red" : monitor.memory_percent > 60 ? "yellow" : "green"}
        />
        <MetricCard
          label="Disk"
          value={monitor.disk_percent}
          unit="%"
          color={monitor.disk_percent > 90 ? "red" : monitor.disk_percent > 75 ? "yellow" : "green"}
        />
        {monitor.gpu_percent !== null ? (
          <MetricCard
            label="GPU"
            value={monitor.gpu_percent}
            unit="%"
            color={monitor.gpu_percent > 80 ? "red" : monitor.gpu_percent > 60 ? "yellow" : "green"}
          />
        ) : (
          <MetricCard label="GPU" value={null} unit="N/A" color="gray" />
        )}
      </div>

      {monitor.gpu_memory_used_mb !== null && monitor.gpu_memory_total_mb !== null && (
        <div className="p-4 bg-gray-50 rounded">
          <h3 className="text-sm font-medium mb-2">GPU Memory</h3>
          <div className="text-2xl font-bold">
            {monitor.gpu_memory_used_mb} / {monitor.gpu_memory_total_mb} MB
          </div>
          <div className="text-sm text-gray-500">
            {((monitor.gpu_memory_used_mb / monitor.gpu_memory_total_mb) * 100).toFixed(1)}% used
          </div>
        </div>
      )}

      <div className="text-xs text-gray-400">
        Timestamp: {new Date(monitor.timestamp).toLocaleString()}
      </div>
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: number | null;
  unit: string;
  color: "green" | "yellow" | "red" | "gray";
}

function MetricCard({ label, value, unit, color }: MetricCardProps) {
  const colorClasses = {
    green: "bg-green-50 border-green-200 text-green-800",
    yellow: "bg-yellow-50 border-yellow-200 text-yellow-800",
    red: "bg-red-50 border-red-200 text-red-800",
    gray: "bg-gray-50 border-gray-200 text-gray-800",
  };

  return (
    <div className={`p-4 rounded border ${colorClasses[color]}`}>
      <h3 className="text-sm font-medium mb-1">{label}</h3>
      <div className="text-2xl font-bold">
        {value !== null ? `${value.toFixed(1)}${unit}` : unit}
      </div>
    </div>
  );
}
