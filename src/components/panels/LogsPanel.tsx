"use client";
import { useState, useEffect, useRef, useCallback } from "react";

interface LogLine {
  source: string;
  timestamp: string;
  level: string;
  message: string;
  stack?: string;
  component?: string;
}

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "#ef4444",
  CRITICAL: "#dc2626",
  WARNING: "#f59e0b",
  WARN: "#f59e0b",
  INFO: "#94a3b8",
  DEBUG: "#64748b",
};

const TAIL_OPTIONS = [50, 100, 200, 500];

export function LogsPanel() {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [source, setSource] = useState("all");
  const [tail, setTail] = useState(100);
  const [level, setLevel] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [wrap, setWrap] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchLogs = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("source", source);
      params.set("tail", String(tail));
      if (level) params.set("level", level);

      const res = await fetch(`/api/logs?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLogs(data.lines || []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch logs");
    } finally {
      setIsLoading(false);
    }
  }, [source, tail, level]);

  useEffect(() => {
    setIsLoading(true);
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(fetchLogs, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, fetchLogs]);

  const handleClear = async () => {
    if (!confirm(`Clear ${source} logs?`)) return;
    try {
      await fetch(`/api/logs?source=${source}`, { method: "DELETE" });
      await fetchLogs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear logs");
    }
  };

  const handleCopy = () => {
    const text = logs.map(l => `[${l.timestamp}] [${l.level}] [${l.source}] ${l.message}`).join("\n");
    navigator.clipboard.writeText(text);
  };

  const errorCount = logs.filter(l => l.level === "ERROR" || l.level === "CRITICAL").length;
  const warnCount = logs.filter(l => l.level === "WARNING" || l.level === "WARN").length;

  return (
    <div data-testid="logs-panel" className="p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">System Logs</h2>
        <div className="flex gap-2 text-xs">
          {errorCount > 0 && <span className="text-red-400">● {errorCount} errors</span>}
          {warnCount > 0 && <span className="text-amber-400">● {warnCount} warnings</span>}
          <span className="text-slate-500">{logs.length} lines</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-2 mb-3 flex-wrap">
        <select value={source} onChange={(e) => setSource(e.target.value)} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs">
          <option value="all">All Sources</option>
          <option value="web">Frontend Errors</option>
          <option value="agent">Backend Logs</option>
          <option value="system">System Traces</option>
        </select>

        <select value={String(tail)} onChange={(e) => setTail(Number(e.target.value))} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs">
          {TAIL_OPTIONS.map(n => <option key={n} value={n}>Last {n}</option>)}
        </select>

        <select value={level} onChange={(e) => setLevel(e.target.value)} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs">
          <option value="">All Levels</option>
          <option value="ERROR">Errors Only</option>
          <option value="WARNING">Warnings+</option>
          <option value="INFO">Info+</option>
          <option value="DEBUG">Debug+</option>
        </select>

        <label className="flex items-center gap-1 text-xs text-slate-400">
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="accent-blue-600" />
          Auto-refresh (5s)
        </label>

        <label className="flex items-center gap-1 text-xs text-slate-400">
          <input type="checkbox" checked={wrap} onChange={(e) => setWrap(e.target.checked)} className="accent-blue-600" />
          Wrap
        </label>

        <button onClick={fetchLogs} className="px-3 py-1 bg-blue-600 rounded text-xs">Refresh</button>
        <button onClick={handleCopy} className="px-3 py-1 bg-slate-700 rounded text-xs">Copy All</button>
        <button onClick={handleClear} className="px-3 py-1 bg-red-900 rounded text-xs">Clear</button>
      </div>

      {error && <p className="text-red-400 text-sm mb-2">{error}</p>}

      {/* Log lines */}
      <div ref={containerRef} className="flex-1 overflow-y-auto bg-slate-950 border border-slate-700 rounded p-2 font-mono text-xs">
        {logs.length === 0 && !isLoading && (
          <p className="text-slate-600 italic p-4">No logs found. Errors will appear here when they occur.</p>
        )}
        {logs.map((log, i) => (
          <div key={i} className={`py-0.5 border-b border-slate-900 ${wrap ? "break-all" : "whitespace-nowrap overflow-x-auto"}`}>
            <span className="text-slate-600">{log.timestamp}</span>{" "}
            <span style={{ color: LEVEL_COLORS[log.level] || "#94a3b8", fontWeight: log.level === "ERROR" ? "bold" : "normal" }}>
              [{log.level}]
            </span>{" "}
            {log.source && log.source !== "all" && <span className="text-blue-400">[{log.source}]</span>}{" "}
            {log.component && <span className="text-purple-400">[{log.component}]</span>}{" "}
            <span className="text-slate-300">{log.message}</span>
            {log.stack && (
              <details className="mt-1 ml-4">
                <summary className="text-slate-600 cursor-pointer text-xs">Stack</summary>
                <pre className="text-slate-600 text-xs mt-1 whitespace-pre-wrap">{log.stack}</pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
