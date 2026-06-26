export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// All regular API functions use RELATIVE paths (/api/...) so they route through Next.js rewrites.
// Auth is handled by backend middleware via same-origin cookies.
// BACKEND_URL is reserved for SSE EventSource URLs only.

export interface AgentStatus {
  phase: "idle" | "planning" | "acting" | "reflecting";
  session_id: string;
  model: string;
  latency_ms: number;
  is_running: boolean;
}

export interface Task {
  id: string;
  intent: string;
  worker_id: string;
  status: "RECEIVED" | "EXECUTING" | "VALIDATING" | "COMPLETE" | "FAILED" | "CANCELLED" | "QUEUED";
  confidence: number;
  cost_usd: number;
  token_count: number;
  created_at: string;
  completed_at?: string;
}

export interface Worker {
  id: string;
  type: string;
  capabilities: string[];
  circuit_state: "CLOSED" | "OPEN" | "HALF_OPEN";
  failures: number;
  threshold: number;
  last_used?: string;
  task_count: number;
}

export interface CostSummary {
  daily_spend: number;
  daily_cap: number;
  monthly_spend: number;
  monthly_cap: number;
  alert_threshold: number;
  fallback_threshold: number;
  model_breakdown: Record<string, number>;
}

export interface ApprovalRequest {
  id: string;
  type: string;
  description: string;
  risk: "low" | "medium" | "high";
  expires_at: string;
}

export interface MemorySlot {
  index: number;
  key?: string;
  value_preview?: string;
  last_written?: string;
  activation: number;
}

export interface SkillInfo {
  name: string;
  tier: "USER_INVOKED" | "AGENT_INVOKED" | "HYBRID";
  enabled: boolean;
  methods: string[];
  requires: string[];
}

export interface TimelineSegment {
  phase: string;
  start: string;
  end: string;
  confidence: number;
}

export interface SystemStats {
  cpu_percent: number;
  memory_percent: number;
  gpu_percent?: number;
  uptime_seconds: number;
  active_workers: number;
}

export interface ToolCallEvent {
  id: string;
  tool: string;
  status: "running" | "success" | "warning" | "error";
  args: Record<string, unknown>;
  output?: string;
  durationMs?: number;
}

export async function getStatus(): Promise<AgentStatus> {
  const res = await fetch(`/api/status`);
  if (!res.ok) throw new Error(`Status ${res.status}`);
  return res.json();
}

export async function getTasks(status?: string): Promise<Task[]> {
  const url = status ? `/api/tasks?status=${status}` : `/api/tasks`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Tasks ${res.status}`);
  return res.json();
}

export async function getWorkers(): Promise<Worker[]> {
  const res = await fetch(`/api/workers`);
  if (!res.ok) throw new Error(`Workers ${res.status}`);
  return res.json();
}

export async function getCostsSummary(): Promise<CostSummary> {
  const res = await fetch(`/api/costs/summary`);
  if (!res.ok) throw new Error(`Costs ${res.status}`);
  return res.json();
}

export async function getPendingApprovals(): Promise<ApprovalRequest[]> {
  const res = await fetch(`/api/approvals/pending`);
  if (!res.ok) throw new Error(`Approvals ${res.status}`);
  return res.json();
}

export async function respondApproval(id: string, approved: boolean): Promise<void> {
  const res = await fetch(`/api/approvals/${id}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  if (!res.ok) throw new Error(`Respond ${res.status}`);
}

export async function getMemorySlots(limit = 100, offset = 0): Promise<MemorySlot[]> {
  const res = await fetch(`/api/memory/slots?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Memory ${res.status}`);
  return res.json();
}

export async function exportMemory(): Promise<Blob> {
  const res = await fetch(`/api/memory/slots/export`);
  if (!res.ok) throw new Error(`Export ${res.status}`);
  return res.blob();
}

export async function importMemory(slots: Array<{key: string; value: unknown; scope?: string}>): Promise<void> {
  const res = await fetch(`/api/memory/slots/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(slots),
  });
  if (!res.ok) throw new Error(`Import ${res.status}`);
}

export async function getSkills(): Promise<SkillInfo[]> {
  const res = await fetch(`/api/skills`);
  if (!res.ok) throw new Error(`Skills ${res.status}`);
  return res.json();
}

export async function getSessionTimeline(sessionId: string): Promise<TimelineSegment[]> {
  const res = await fetch(`/api/sessions/${sessionId}/timeline`);
  if (!res.ok) throw new Error(`Timeline ${res.status}`);
  return res.json();
}

export async function getSystemStats(): Promise<SystemStats> {
  const res = await fetch(`/api/system`);
  if (!res.ok) throw new Error(`System ${res.status}`);
  return res.json();
}

export async function resetCircuit(workerId: string): Promise<void> {
  const res = await fetch(`/api/circuit-breaker/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ worker_id: workerId }),
  });
  if (!res.ok) throw new Error(`Reset ${res.status}`);
}

export async function login(): Promise<void> {
  const res = await fetch(`/api/auth/login`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Login ${res.status}`);
}

// SSE URLs use absolute BACKEND_URL because EventSource cannot be proxied through Next.js rewrites.
// credentials: 'include' is required to send auth cookies cross-origin.
export function sseUrl(path: string): string {
  return `${BACKEND_URL}${path}`;
}

export interface ModelInfo {
  model_id: string;
  name: string;
  source: string;
  adapter_compatibility: string[];
  task_tags: string[];
  download_status: string;
  downloaded_quantisation: string | null;
  license: string;
  description: string;
}

export async function getModels(): Promise<ModelInfo[]> {
  const res = await fetch(`/api/models`);
  if (!res.ok) throw new Error(`Models ${res.status}`);
  return res.json();
}

export async function getModel(modelId: string): Promise<ModelInfo> {
  const res = await fetch(`/api/models/${modelId}`);
  if (!res.ok) throw new Error(`Model ${res.status}`);
  return res.json();
}

export async function searchModels(query: string): Promise<ModelInfo[]> {
  const res = await fetch(`/api/models/search?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Search ${res.status}`);
  return res.json();
}
