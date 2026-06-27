"use client";

import { useState, useEffect } from "react";
import { getFallbackChain, setFallbackChain, getAvailableAdapters } from "@/lib/api";

type Tab = "cost" | "circuit" | "sandbox" | "auth" | "fallback";

export function SettingsDrawer() {
  const [activeTab, setActiveTab] = useState<Tab>("cost");
  const [fallbackChain, setFallbackChainState] = useState<string[]>([]);
  const [availableAdapters, setAvailableAdapters] = useState<string[]>([]);
  const [selectedAdapter, setSelectedAdapter] = useState("");

  useEffect(() => {
    if (activeTab === "fallback") {
      loadFallbackChain();
      loadAvailableAdapters();
    }
  }, [activeTab]);

  const loadFallbackChain = async () => {
    const data = await getFallbackChain();
    setFallbackChainState(data.chain);
  };

  const loadAvailableAdapters = async () => {
    const data = await getAvailableAdapters();
    setAvailableAdapters(data.adapters);
  };

  const addToChain = () => {
    if (selectedAdapter && !fallbackChain.includes(selectedAdapter)) {
      const newChain = [...fallbackChain, selectedAdapter];
      setFallbackChainState(newChain);
      setFallbackChain(newChain);
    }
  };

  const removeFromChain = (adapter: string) => {
    const newChain = fallbackChain.filter((a) => a !== adapter);
    setFallbackChainState(newChain);
    setFallbackChain(newChain);
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "cost", label: "Cost Policy" },
    { key: "circuit", label: "Circuit Breaker" },
    { key: "sandbox", label: "Sandbox" },
    { key: "auth", label: "Auth" },
    { key: "fallback", label: "Fallback Chain" },
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

          {activeTab === "fallback" && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Add Adapter</label>
                <div className="flex gap-2">
                  <select
                    value={selectedAdapter}
                    onChange={(e) => setSelectedAdapter(e.target.value)}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
                  >
                    <option value="">Select adapter...</option>
                    {availableAdapters.map((adapter) => (
                      <option key={adapter} value={adapter}>
                        {adapter}
                      </option>
                    ))}
                  </select>
                  <button onClick={addToChain} className="px-4 py-2 bg-blue-500 text-white rounded text-sm">
                    Add
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Fallback Chain</label>
                <p className="text-xs text-gray-500 mb-2">
                  Adapters are tried in order when one fails. Drag to reorder (not implemented).
                </p>
                {fallbackChain.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No adapters in chain</p>
                ) : (
                  <div className="space-y-2">
                    {fallbackChain.map((adapter, index) => (
                      <div
                        key={adapter}
                        className="flex items-center justify-between p-2 bg-gray-50 border border-gray-200 rounded"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400 font-mono">{index + 1}.</span>
                          <span className="text-sm font-medium">{adapter}</span>
                        </div>
                        <button
                          onClick={() => removeFromChain(adapter)}
                          className="text-red-500 hover:text-red-700 text-sm"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
