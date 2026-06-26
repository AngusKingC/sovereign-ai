"use client";

import { useState } from "react";

type Tab = "cost" | "circuit" | "sandbox" | "auth";

export function SettingsDrawer() {
  const [activeTab, setActiveTab] = useState<Tab>("cost");

  const tabs: { key: Tab; label: string }[] = [
    { key: "cost", label: "Cost Policy" },
    { key: "circuit", label: "Circuit Breaker" },
    { key: "sandbox", label: "Sandbox" },
    { key: "auth", label: "Auth" },
  ];

  return (
    <div className="drawer-overlay" data-open={true} data-testid="settings-drawer">
      <div className="w-[480px] h-full bg-white shadow-xl flex flex-col">
        <div className="p-4 border-b">
          <h2 className="text-xl font-bold mb-4">Settings</h2>
          <div className="flex gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-3 py-1 text-sm rounded ${
                  activeTab === tab.key
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 p-4 overflow-y-auto">
          {activeTab === "cost" && (
            <div className="space-y-4">
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Daily Cap ($)</label>
                <input
                  type="number"
                  defaultValue={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Monthly Cap ($)</label>
                <input
                  type="number"
                  defaultValue={100}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Alert Threshold (%)</label>
                <input
                  type="number"
                  defaultValue={80}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
            </div>
          )}

          {activeTab === "circuit" && (
            <div className="space-y-4">
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Failure Threshold</label>
                <input
                  type="number"
                  defaultValue={5}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Reset Timeout (s)</label>
                <input
                  type="number"
                  defaultValue={60}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
            </div>
          )}

          {activeTab === "sandbox" && (
            <div className="space-y-4">
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Docker Image</label>
                <input
                  type="text"
                  defaultValue="python:3.12-slim"
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Memory Limit (MB)</label>
                <input
                  type="number"
                  defaultValue={512}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Timeout (s)</label>
                <input
                  type="number"
                  defaultValue={30}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
            </div>
          )}

          {activeTab === "auth" && (
            <div className="space-y-4">
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">API Key</label>
                <input
                  type="password"
                  defaultValue="••••••••"
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
              <div className="opacity-50" data-mocked title="Coming in Plan 89">
                <label className="block text-sm font-medium mb-1">Session Timeout (min)</label>
                <input
                  type="number"
                  defaultValue={30}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                  disabled
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
