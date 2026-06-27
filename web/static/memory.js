const Memory = {
  init() {
    document.getElementById("panel-memory").innerHTML = `
      <h2>Memory Slots</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input id="memory-search" type="text" placeholder="Search memory..." style="flex:1;">
        <button class="btn btn-primary" onclick="Memory.search()">Search</button>
      </div>
      <div id="memory-list"></div>
    `;
  },
  async update() {
    try {
      const slots = await API.getMemorySlots();
      this.render(slots);
    } catch (e) {
      document.getElementById("memory-list").innerHTML = `<p class="muted">Failed to load: ${e.message}</p>`;
    }
  },
  async search() {
    await this.update(); // API doesn't have search yet — just refresh
  },
  render(slots) {
    const list = document.getElementById("memory-list");
    if (!slots || slots.length === 0) { list.innerHTML = '<p class="muted">No memory slots.</p>'; return; }
    list.innerHTML = slots.map(s => `
      <div class="card">
        <div style="display:flex;justify-content:space-between;">
          <span class="mono">#${s.index}</span>
          <span style="font-size:11px;color:var(--text-muted);">Activation: ${(s.activation || 0).toFixed(2)}</span>
        </div>
        ${s.key ? `<div style="font-weight:500;margin-top:4px;">${s.key}</div>` : ""}
        ${s.value_preview ? `<div style="font-size:12px;color:var(--text-muted);margin-top:2px;">${s.value_preview.slice(0,200)}</div>` : ""}
      </div>
    `).join("");
  },
};
