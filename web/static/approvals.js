const Approvals = {
  init() {
    document.getElementById("panel-approvals").innerHTML = `<h2>Approval Queue</h2><div id="approvals-list"></div>`;
  },
  async update() {
    try {
      const approvals = await API.getApprovals();
      const list = document.getElementById("approvals-list");
      if (!approvals || approvals.length === 0) { list.innerHTML = '<p class="muted">No pending approvals.</p>'; return; }
      list.innerHTML = approvals.map(a => `
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:start;">
            <div>
              <span class="mono">${(a.id || a.request_id || "").slice(0,12)}</span>
              <span class="badge ${a.risk === "high" ? "badge-error" : a.risk === "medium" ? "badge-warning" : "badge-success"}" style="margin-left:8px;">${a.risk || "low"}</span>
            </div>
            <div style="display:flex;gap:4px;">
              <button class="btn btn-success" onclick="Approvals.respond('${a.id || a.request_id}', true)">Approve</button>
              <button class="btn btn-danger" onclick="Approvals.respond('${a.id || a.request_id}', false)">Deny</button>
            </div>
          </div>
          <p style="margin-top:8px;font-size:13px;">${a.description || a.action_description || a.reason_for_approval || ""}</p>
        </div>
      `).join("");
    } catch (e) {
      document.getElementById("approvals-list").innerHTML = `<p class="muted">Failed to load: ${e.message}</p>`;
    }
  },
  async respond(id, approved) {
    try { await API.respondApproval(id, approved); this.update(); } catch (e) { alert(`Failed: ${e.message}`); }
  },
};
