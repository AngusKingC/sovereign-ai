// Core UI: panel switching, sidebar, polling, status bar

const UI = {
  currentPanel: "terminal",
  pollIntervals: {},

  init() {
    // Sidebar clicks
    document.querySelectorAll(".sidebar-item").forEach(item => {
      item.addEventListener("click", () => {
        const panel = item.dataset.panel;
        this.switchPanel(panel);
      });
    });

    // Right panel tabs
    document.querySelectorAll(".rp-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        const tabName = tab.dataset.tab;
        document.querySelectorAll(".rp-tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".rp-tab-content").forEach(c => c.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(`rp-${tabName}`).classList.add("active");
      });
    });

    // Start polling
    this.startPolling("status", () => this.updateStatus(), 2000);
    this.startPolling("workers", () => Workers.update(), 5000);
    this.startPolling("costs", () => Costs.update(), 10000);
    this.startPolling("approvals", () => Approvals.update(), 2000);

    // Initialize panels
    Chat.init();
    Models.init();
    Workers.init();
    Approvals.init();
    Costs.init();
    Memory.init();
    Logs.init();

    // Start activation grid animation
    this.initActivationGrid();

    console.log("[UI] Initialized");
  },

  switchPanel(name) {
    this.currentPanel = name;
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".sidebar-item").forEach(i => i.classList.remove("active"));
    const panel = document.getElementById(`panel-${name}`);
    const item = document.querySelector(`.sidebar-item[data-panel="${name}"]`);
    if (panel) panel.classList.add("active");
    if (item) item.classList.add("active");

    // Trigger panel-specific refresh
    if (name === "logs") Logs.refresh();
    if (name === "models") Models.refresh();
    if (name === "workers") Workers.update();
    if (name === "resources") Costs.updateResources();
  },

  startPolling(name, fn, intervalMs) {
    if (this.pollIntervals[name]) clearInterval(this.pollIntervals[name]);
    fn(); // Initial call
    this.pollIntervals[name] = setInterval(fn, intervalMs);
  },

  stopPolling(name) {
    if (this.pollIntervals[name]) {
      clearInterval(this.pollIntervals[name]);
      delete this.pollIntervals[name];
    }
  },

  async updateStatus() {
    try {
      const status = await API.getStatus();
      const phaseEl = document.getElementById("status-phase");
      phaseEl.textContent = status.phase || "idle";
      phaseEl.className = `badge badge-${status.phase || "idle"}`;
      document.getElementById("status-model").textContent = status.model || "No model";
      document.getElementById("status-latency").textContent = status.latency_ms ? `${status.latency_ms}ms` : "";
      document.getElementById("status-session").textContent = status.session_id || "No session";
      document.getElementById("status-tokens").textContent = `${status.token_count || 0} tokens`;
      document.getElementById("bottom-tokens").textContent = `${status.token_count || 0} / ${status.context_limit || 128000}`;
    } catch (e) {
      // Silent fail — don't spam console for polling errors
    }
  },

  initActivationGrid() {
    const canvas = document.getElementById("activation-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const cols = 32, rows = 4;
    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    setInterval(() => {
      ctx.fillStyle = "#0c0c0f";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const val = Math.random();
          if (val > 0.7) {
            const hue = val > 0.9 ? 0 : val > 0.8 ? 30 : 60;
            ctx.fillStyle = `hsl(${hue}, 70%, 50%)`;
            ctx.fillRect(c * cellW + 1, r * cellH + 1, cellW - 2, cellH - 2);
          }
        }
      }
    }, 500);
  },

  // Utility: create element with class and content
  el(tag, className, content) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (content) e.innerHTML = content;
    return e;
  },

  // Utility: format timestamp
  formatTime(ts) {
    if (!ts) return "";
    try { return new Date(ts).toLocaleTimeString(); } catch { return ts; }
  },
};

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => UI.init());
