import { create } from "zustand";

export interface Task {
  id: string;
  intent: string;
  priority: number;
  state: string;
  created_at: string;
}

interface TaskState {
  tasks: Task[];
  activeTask: Task | null;
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  setActiveTask: (task: Task | null) => void;
  clearTasks: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  activeTask: null,
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((s) => ({ tasks: [...s.tasks, task] })),
  updateTask: (id, updates) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),
  setActiveTask: (task) => set({ activeTask: task }),
  clearTasks: () => set({ tasks: [], activeTask: null }),
}));
