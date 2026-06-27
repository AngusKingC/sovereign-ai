const Logs = {
  autoRefresh: true,
  interval: null,
  source: "all",
  tail: 100,
  level: "",

  init() {
    document.getElementById("panel-logs").innerHTML = `
      <h2>System Logs</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
        <select id="logs-source" onchange="Logs.source=this.value;Logs.refresh();">
          <option value="all">All Sources</option>
          <option value="web">Frontend Errors</option>
          <option value="agent">Backend Logs</option>
          <option value="system">System Traces</option>
        </select>
        <select id="logs-tail" onchange="Logs.tail=this.value;Logs.refresh();">
          <option value="50">Last 50</option>
          <option value="100" selected>Last 100</option>
          <option value="200">Last 200</option>
          <option value="500">Last 500</option>
        </select>
        <select id="logs-level" onchange="Logs.level=this.value;Logs.refresh();">
          <option value="">All Levels</option>
          <option value="ERROR">Errors Only</option>
          <option value="WARNING">Warnings+</option>
        </select>
        <label style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text-muted);">
          <input type="checkbox" id="logs-auto" checked onchange="Logs.toggleAuto(this.checked);"> Auto (5s)
        </label>
        <button class="btn btn-primary" onclick="Logs.refresh();">Refresh</button>
        <button class="btn btn-danger" onclick="Logs.clear();">Clear</button>
      </div>
      <div id="logs-content" style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:8px;font-family:var(--font-mono);font-size:12px;max-height:calc(100vh - 200px);overflow-y:auto;"></div>
    `;
    this.toggleAuto(true);
  },

  toggleAuto(on) {
    this.autoRefresh = on;
    if (this.interval) clearInterval(this.interval);
    if (on) this.interval = setInterval(() => this.refresh(), 5000);
  },

  async refresh() {
    try {
      const data = await API.getLogs(this.source, this.tail, this.level);
      const el = document.getElementById("logs-content");
      if (!el) return;
      if (!data.lines || data.lines.length === 0) {
        el.innerHTML = '<p class="muted" style="padding:12px;">No logs found.</p>';
        return;
      }
      const colors = { ERROR: "#ef4444", CRITICAL: "#dc262600", WARNING: "#f59e0b", WARN: "#f59e0b", INFO: "#94a3b8", DEBUG: "#64748b" };
      el.innerHTML = data.lines.map(l => {
        const color = colors[l.level] || "#94a3b8";
        return `<div style="padding:2px 0;border-bottom:1px solid #1a1a2e;">
          <span style="color:#475569;">${l.timestamp || ""}</span>
          <span style="color:${color};font-weight:${l.level === "ERROR" ? "bold" : "normal"};">[${l.level}]</span>
          ${l.source && l.source !== "all" ? `<span style="color:#3b82f6;">[${l.source}]</span>` : ""}
          ${l.component ? `<span style="color:#8b5cf6;">[${l.component}]</span>` : ""}
          <span style="color:#cbd5e1;">${l.message}</span>
        </div>`;
      }).join("");
      el.scrollTop = el.scrollHeight;
    } catch (e) {
      const el = document.getElementById("logs-content");
      if (el) el.innerHTML = `<p style="color:var(--error);">Failed to load: ${e.message}</p>`;
    }
  },

  async clear() {
    if (!confirm(`Clear ${this.source} logs?`)) return;
    try { await API.clearLogs(this.source); this.refresh(); } catch (e) { alert(`Failed: ${e.message}`); }
  },
};
