// API wrapper — all fetch calls go through here
const API = {
  async get(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  async put(path, body) {
    const res = await fetch(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  async del(path) {
    const res = await fetch(path, { method: "DELETE" });
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
