// API wrapper — all fetch calls go through here
const API = {
  // Get token from localStorage
  getToken() {
    return localStorage.getItem('sovereign_token');
  },

  // Clear stale token on 401
  clearToken() {
    localStorage.removeItem('sovereign_token');
    // Reload page to show token modal
    location.reload();
  },

  async get(path) {
    const token = this.getToken();
    if (!token) throw new Error('Auth token required');
    const res = await fetch(path, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 401) {
      this.clearToken();
      throw new Error('Unauthorized');
    }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  async post(path, body) {
    const token = this.getToken();
    if (!token) throw new Error('Auth token required');
    const res = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(body),
    });
    if (res.status === 401) {
      this.clearToken();
      throw new Error('Unauthorized');
    }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  async put(path, body) {
    const token = this.getToken();
    if (!token) throw new Error('Auth token required');
    const res = await fetch(path, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(body),
    });
    if (res.status === 401) {
      this.clearToken();
      throw new Error('Unauthorized');
    }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  async del(path) {
    const token = this.getToken();
    if (!token) throw new Error('Auth token required');
    const res = await fetch(path, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (res.status === 401) {
      this.clearToken();
      throw new Error('Unauthorized');
    }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  // Specific endpoints
  getStatus: () => API.get("/api/status"),
  getTasks: () => API.get("/api/tasks"),
  getWorkers: () => API.get("/api/workers"),
  getCosts: () => API.get("/api/costs/summary"),
  getCostPolicy: () => API.get("/api/costs/policy"),
  updateCostPolicy: (policy) => API.put("/api/costs/policy", policy),
  getApprovals: () => API.get("/api/approvals/pending"),
  respondApproval: (id, approved) => API.post(`/api/approvals/${id}/respond`, { approved }),
  getMemorySlots: () => API.get("/api/memory/slots"),
  getSkills: () => API.get("/api/skills"),
  getSystemStats: () => API.get("/api/system"),
  getResourceMonitor: () => API.get("/api/resources/monitor"),
  getCircuitBreaker: () => API.get("/api/circuit-breaker/status"),
  resetCircuit: (workerId) => API.post("/api/circuit-breaker/reset", { worker_id: workerId }),
  getModels: () => API.get("/api/models"),
  searchModels: (query) => API.get(`/api/models/search?query=${encodeURIComponent(query)}`),
  getAvailableAdapters: () => API.get("/api/adapters/available"),
  getFallbackChain: () => API.get("/api/adapters/fallback"),
  setFallbackChain: (chain) => API.put("/api/adapters/fallback", { chain }),
  createWorker: (description) => API.post("/api/workers/create", { description }),
  deleteWorker: (id) => API.del(`/api/workers/${id}`),
  getLogs: (source, tail, level) => {
    let url = `/api/logs?source=${source}&tail=${tail}`;
    if (level) url += `&level=${level}`;
    return API.get(url);
  },
  clearLogs: (source) => API.del(`/api/logs?source=${source}`),
  getLogSources: () => API.get("/api/logs/sources"),
  getVRAM: () => API.get("/api/vram/status"),
};
