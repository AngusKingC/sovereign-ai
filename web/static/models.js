// Models panel
const Models = {
  init() {
    const panel = document.getElementById("panel-models");
    panel.innerHTML = `
      <h2>Models</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input id="models-search" type="text" placeholder="Search models..." style="flex:1;">
        <button class="btn btn-primary" onclick="Models.search()">Search</button>
      </div>
      <div id="models-list"></div>
    `;
    document.getElementById("models-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.search();
    });
  },

  async refresh() {
    try {
      const models = await API.getModels();
      this.render(models);
    } catch (e) {
      document.getElementById("models-list").innerHTML = `<p class="muted">Failed to load models: ${e.message}</p>`;
    }
  },

  async search() {
    const query = document.getElementById("models-search").value;
    try {
      const models = query ? await API.searchModels(query) : await API.getModels();
      this.render(models);
    } catch (e) {
      document.getElementById("models-list").innerHTML = `<p class="muted">Search failed: ${e.message}</p>`;
    }
  },

  render(models) {
    const list = document.getElementById("models-list");
    if (!models || models.length === 0) {
      list.innerHTML = '<p class="muted">No models found.</p>';
      return;
    }
    list.innerHTML = models.map(m => `
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:start;">
          <div>
            <span style="font-weight:500;">${m.name}</span>
            <span class="mono" style="color:var(--text-muted);margin-left:8px;">${m.model_id}</span>
          </div>
          <span class="badge ${m.download_status === "downloaded" ? "badge-success" : ""}">${m.download_status}</span>
        </div>
        ${m.task_tags && m.task_tags.length ? `<div style="margin-top:4px;">${m.task_tags.map(t => `<span class="badge" style="background:var(--surface);margin-right:4px;">${t}</span>`).join("")}</div>` : ""}
        ${m.adapter_compatibility && m.adapter_compatibility.length ? `<div style="margin-top:2px;font-size:11px;color:var(--accent);">${m.adapter_compatibility.join(", ")}</div>` : ""}
      </div>
    `).join("");
  },
};
