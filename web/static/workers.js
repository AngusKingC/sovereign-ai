const Workers = {
  init() {
    document.getElementById("panel-workers").innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h2>Workers</h2>
        <button class="btn btn-success" onclick="Workers.create()">+ Create Worker</button>
      </div>
      <div id="workers-list"></div>
    `;
  },
  async update() {
    try {
      const workers = await API.getWorkers();
      const list = document.getElementById("workers-list");
      if (!workers || workers.length === 0) { list.innerHTML = '<p class="muted">No workers registered.</p>'; return; }
      list.innerHTML = workers.map(w => `
        <div class="card">
          <div style="display:flex;justify-content:space-between;">
            <div>
              <span class="mono">${w.worker_id || w.id || "unknown"}</span>
              <span class="badge ${w.status === "ACTIVE" ? "badge-success" : ""}" style="margin-left:8px;">${w.status || "unknown"}</span>
            </div>
            <button class="btn btn-danger" onclick="Workers.delete('${w.worker_id || w.id}')">Delete</button>
          </div>
          ${w.capabilities ? `<div style="margin-top:4px;font-size:12px;color:var(--text-muted);">${w.capabilities.join(", ")}</div>` : ""}
        </div>
      `).join("");
    } catch (e) {
      document.getElementById("workers-list").innerHTML = `<p class="muted">Failed to load: ${e.message}</p>`;
    }
  },
  async create() {
    const desc = prompt("Describe the worker to create:");
    if (!desc) return;
    try {
      await API.createWorker(desc);
      this.update();
    } catch (e) { alert(`Failed: ${e.message}`); }
  },
  async delete(id) {
    if (!confirm(`Delete worker ${id}?`)) return;
    try { await API.deleteWorker(id); this.update(); } catch (e) { alert(`Failed: ${e.message}`); }
  },
};
