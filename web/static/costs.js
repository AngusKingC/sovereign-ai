const Costs = {
  init() {
    document.getElementById("panel-costs").innerHTML = `
      <h2>Cost Dashboard</h2>
      <div id="costs-content"></div>
      <h2 style="margin-top:24px;">System Resources</h2>
      <div id="resources-content"></div>
    `;
  },
  async update() {
    try {
      const costs = await API.getCosts();
      const el = document.getElementById("costs-content");
      const dailyPct = costs.daily_cap ? (costs.daily_spend / costs.daily_cap * 100) : 0;
      const monthlyPct = costs.monthly_cap ? (costs.monthly_spend / costs.monthly_cap * 100) : 0;
      el.innerHTML = `
        <div class="card">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span>Daily Spend</span><span class="mono">$${(costs.daily_spend || 0).toFixed(4)} / $${(costs.daily_cap || 0).toFixed(2)}</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:${Math.min(dailyPct,100)}%;background:${dailyPct > 80 ? "var(--error)" : dailyPct > 60 ? "var(--warning)" : "var(--success)"};"></div></div>
        </div>
        <div class="card">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span>Monthly Spend</span><span class="mono">$${(costs.monthly_spend || 0).toFixed(4)} / $${(costs.monthly_cap || 0).toFixed(2)}</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:${Math.min(monthlyPct,100)}%;background:${monthlyPct > 80 ? "var(--error)" : monthlyPct > 60 ? "var(--warning)" : "var(--success)"};"></div></div>
        </div>
      `;
    } catch (e) {
      document.getElementById("costs-content").innerHTML = `<p class="muted">Failed to load costs: ${e.message}</p>`;
    }
    this.updateResources();
  },
  async updateResources() {
    try {
      const res = await API.getResourceMonitor();
      const el = document.getElementById("resources-content");
      if (!el) return;
      const cpuColor = res.cpu_percent > 80 ? "var(--error)" : res.cpu_percent > 60 ? "var(--warning)" : "var(--success)";
      const memColor = res.memory_percent > 80 ? "var(--error)" : res.memory_percent > 60 ? "var(--warning)" : "var(--success)";
      el.innerHTML = `
        <div class="card">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>CPU</span><span class="mono">${(res.cpu_percent || 0).toFixed(1)}%</span></div>
          <div class="progress-bar"><div class="progress-fill" style="width:${res.cpu_percent || 0}%;background:${cpuColor};"></div></div>
        </div>
        <div class="card">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Memory</span><span class="mono">${(res.memory_percent || 0).toFixed(1)}%</span></div>
          <div class="progress-bar"><div class="progress-fill" style="width:${res.memory_percent || 0}%;background:${memColor};"></div></div>
        </div>
        ${res.gpu_percent !== null && res.gpu_percent !== undefined ? `
        <div class="card">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>GPU</span><span class="mono">${(res.gpu_percent || 0).toFixed(1)}%</span></div>
          <div class="progress-bar"><div class="progress-fill" style="width:${res.gpu_percent || 0}%;background:var(--accent);"></div></div>
        </div>` : ""}
        <div style="font-size:12px;color:var(--text-muted);margin-top:8px;">Uptime: ${Math.floor((res.uptime_seconds || 0) / 3600)}h ${Math.floor(((res.uptime_seconds || 0) % 3600) / 60)}m | Active Workers: ${res.active_workers || 0}</div>
      `;
    } catch (e) {
      const el = document.getElementById("resources-content");
      if (el) el.innerHTML = `<p class="muted">Failed to load resources: ${e.message}</p>`;
    }
  },
};
