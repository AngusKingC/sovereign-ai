"use client";

import { useState } from "react";
import { useMemoryStore } from "@/stores/memoryStore";

export function MemoryDrawer() {
  const slots = useMemoryStore((s) => s.slots);
  const searchQuery = useMemoryStore((s) => s.searchQuery);
  const setSearchQuery = useMemoryStore((s) => s.setSearchQuery);
  const sortColumn = useMemoryStore((s) => s.sortColumn);
  const sortDirection = useMemoryStore((s) => s.sortDirection);
  const setSort = useMemoryStore((s) => s.setSort);

  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const filteredSlots = slots.filter(
    (slot) =>
      slot.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      slot.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedSlots = [...filteredSlots].sort((a, b) => {
    if (!sortColumn) return 0;
    const aVal = a[sortColumn];
    const bVal = b[sortColumn];
    if (aVal < bVal) return sortDirection === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  const handleSort = (column: keyof typeof slots[0]) => {
    const newDirection =
      sortColumn === column && sortDirection === "asc" ? "desc" : "asc";
    setSort(column, newDirection);
  };

  const handleExport = async () => {
    try {
      const response = await fetch("/api/memory/slots/export");
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "memory-export.json";
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error("Failed to export memory:", error);
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/api/memory/slots/import", {
        method: "POST",
        body: formData,
      });
      if (response.ok) {
        const result = await response.json();
        console.log("Import successful:", result);
      }
    } catch (error) {
      console.error("Failed to import memory:", error);
    }
  };

  const handleClearSlot = async (index: number) => {
    try {
      const response = await fetch(`/api/memory/slots/${index}`, {
        method: "DELETE",
      });
      if (response.ok) {
        setExpandedRow(null);
      }
    } catch (error) {
      console.error("Failed to clear slot:", error);
    }
  };

  return (
    <div className="drawer-overlay" data-open={true} data-testid="memory-drawer">
      <div className="w-[480px] h-full bg-white shadow-xl p-6 overflow-y-auto">
        <h2 className="text-xl font-bold mb-4">Memory</h2>

        <div className="mb-4 flex gap-2">
          <input
            type="text"
            placeholder="Search by key or value..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
          />
        </div>

        <div className="mb-4 flex gap-2">
          <button
            onClick={handleExport}
            className="px-3 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600"
          >
            Export
          </button>
          <label className="px-3 py-1 bg-green-500 text-white text-sm rounded hover:bg-green-600 cursor-pointer">
            Import
            <input type="file" accept=".json" onChange={handleImport} className="hidden" />
          </label>
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th
                className="text-left py-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort("index")}
              >
                Index {sortColumn === "index" && (sortDirection === "asc" ? "↑" : "↓")}
              </th>
              <th
                className="text-left py-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort("key")}
              >
                Key {sortColumn === "key" && (sortDirection === "asc" ? "↑" : "↓")}
              </th>
              <th
                className="text-left py-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort("lastWritten")}
              >
                Last Written {sortColumn === "lastWritten" && (sortDirection === "asc" ? "↑" : "↓")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedSlots.map((slot) => (
              <>
                <tr
                  key={slot.index}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpandedRow(expandedRow === slot.index ? null : slot.index)}
                >
                  <td className="py-2">{slot.index}</td>
                  <td className="py-2 truncate max-w-[150px]">{slot.key}</td>
                  <td className="py-2">{new Date(slot.lastWritten).toLocaleString()}</td>
                </tr>
                {expandedRow === slot.index && (
                  <tr>
                    <td colSpan={3} className="py-4 bg-gray-50">
                      <div className="mb-2">
                        <strong>Value:</strong>
                        <pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                          {slot.value}
                        </pre>
                      </div>
                      <div className="mb-2">
                        <strong>Activation:</strong>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                          <div
                            className="bg-blue-500 h-2 rounded-full"
                            style={{ width: `${slot.activation * 100}%` }}
                          />
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleClearSlot(slot.index);
                        }}
                        className="text-xs text-red-600 hover:text-red-800"
                      >
                        Clear Slot
                      </button>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>

        {sortedSlots.length === 0 && (
          <p className="text-gray-500 text-center py-4">No memory slots found</p>
        )}
      </div>
    </div>
  );
}
