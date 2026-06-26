"use client";

import { useTaskStore } from "@/stores/taskStore";

export function TasksPanel() {
  const tasks = useTaskStore((s) => s.tasks);

  const activeTasks = tasks.filter((t) =>
    ["pending", "running", "in_progress"].includes(t.state.toLowerCase())
  );
  const completedTasks = tasks.filter((t) =>
    ["completed", "done"].includes(t.state.toLowerCase())
  );
  const failedTasks = tasks.filter((t) =>
    ["failed", "error"].includes(t.state.toLowerCase())
  );

  const getStatusColor = (state: string) => {
    const s = state.toLowerCase();
    if (["pending", "running", "in_progress"].includes(s)) return "bg-blue-500";
    if (["completed", "done"].includes(s)) return "bg-emerald-500";
    if (["failed", "error"].includes(s)) return "bg-red-500";
    return "bg-gray-500";
  };

  const TaskCard = ({ task }: { task: typeof tasks[0] }) => (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{task.intent}</span>
        <span
          className={`px-2 py-1 rounded-full text-xs text-white ${getStatusColor(
            task.state
          )}`}
        >
          {task.state}
        </span>
      </div>
      <div className="text-xs text-gray-500 mb-2">
        Priority: {task.priority} | Created: {new Date(task.created_at).toLocaleString()}
      </div>
      <button
        className="text-xs text-red-600 hover:text-red-800"
        title={task.state === "running" ? "Cancel task" : "Coming in Plan 89"}
      >
        Cancel
      </button>
    </div>
  );

  return (
    <div className="p-6" data-testid="tasks-panel">
      <h1 className="text-2xl font-bold mb-6">Tasks</h1>

      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-3 text-blue-600">Active</h2>
          <div className="space-y-2">
            {activeTasks.length === 0 ? (
              <p className="text-gray-500 text-sm">No active tasks</p>
            ) : (
              activeTasks.map((task) => <TaskCard key={task.id} task={task} />)
            )}
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3 text-emerald-600">Completed</h2>
          <div className="space-y-2">
            {completedTasks.length === 0 ? (
              <p className="text-gray-500 text-sm">No completed tasks</p>
            ) : (
              completedTasks.map((task) => <TaskCard key={task.id} task={task} />)
            )}
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3 text-red-600">Failed</h2>
          <div className="space-y-2">
            {failedTasks.length === 0 ? (
              <p className="text-gray-500 text-sm">No failed tasks</p>
            ) : (
              failedTasks.map((task) => <TaskCard key={task.id} task={task} />)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
