import { create } from "zustand";

export interface ApprovalRequest {
  id: string;
  task_id: string;
  description: string;
  proposed_action: string;
  created_at: string;
}

interface ApprovalState {
  pending: ApprovalRequest[];
  setPending: (requests: ApprovalRequest[]) => void;
  respond: (id: string, approved: boolean) => void;
  remove: (id: string) => void;
}

export const useApprovalStore = create<ApprovalState>((set) => ({
  pending: [],
  setPending: (pending) => set({ pending }),
  respond: (id, approved) =>
    set((s) => ({
      pending: s.pending.filter((r) => r.id !== id),
    })),
  remove: (id) =>
    set((s) => ({
      pending: s.pending.filter((r) => r.id !== id),
    })),
}));
