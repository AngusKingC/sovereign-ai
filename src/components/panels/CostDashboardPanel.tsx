"use client";

import { useCostStore } from "@/stores/costStore";

export function CostDashboardPanel() {
  const summary = useCostStore((s) => s.summary);

  const DAILY_CAP = 10;
  const MONTHLY_CAP = 100;
  const ALERT_THRESHOLD = 0.8;
  const FALLBACK_THRESHOLD = 0.9;

  if (!summary) {
    return (
      <div className="p-6" data-testid="cost-dashboard-panel">
        <h1 className="text-2xl font-bold mb-6">Cost Dashboard</h1>
        <p className="text-gray-500">Loading cost data...</p>
      </div>
    );
  }

  const dailyRatio = summary.daily_cost_usd / DAILY_CAP;
  const monthlyRatio = summary.monthly_cost_usd / MONTHLY_CAP;
  const dailyWidth = Math.min(dailyRatio * 100, 100);
  const monthlyWidth = Math.min(monthlyRatio * 100, 100);

  const getBarColor = (ratio: number) => {
    if (ratio >= FALLBACK_THRESHOLD) return "bg-red-500";
    if (ratio >= ALERT_THRESHOLD) return "bg-amber-500";
    return "bg-emerald-500";
  };

  return (
    <div className="p-6" data-testid="cost-dashboard-panel">
      <h1 className="text-2xl font-bold mb-6">Cost Dashboard</h1>

      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-3">Daily Spend</h2>
          <div className="bg-gray-200 rounded-full h-4 mb-2">
            <div
              className={`h-4 rounded-full transition-all ${getBarColor(dailyRatio)}`}
              style={{ width: `${dailyWidth}%` }}
            />
          </div>
          <div className="flex justify-between text-sm text-gray-600">
            <span>${summary.daily_cost_usd.toFixed(2)} / ${DAILY_CAP}</span>
            <span>{(dailyRatio * 100).toFixed(1)}%</span>
          </div>
          {dailyRatio >= ALERT_THRESHOLD && (
            <p className="text-xs text-amber-600 mt-1">
              {dailyRatio >= FALLBACK_THRESHOLD ? "FALLBACK THRESHOLD REACHED" : "ALERT THRESHOLD REACHED"}
            </p>
          )}
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3">Monthly Spend</h2>
          <div className="bg-gray-200 rounded-full h-4 mb-2">
            <div
              className={`h-4 rounded-full transition-all ${getBarColor(monthlyRatio)}`}
              style={{ width: `${monthlyWidth}%` }}
            />
          </div>
          <div className="flex justify-between text-sm text-gray-600">
            <span>${summary.monthly_cost_usd.toFixed(2)} / ${MONTHLY_CAP}</span>
            <span>{(monthlyRatio * 100).toFixed(1)}%</span>
          </div>
          {monthlyRatio >= ALERT_THRESHOLD && (
            <p className="text-xs text-amber-600 mt-1">
              {monthlyRatio >= FALLBACK_THRESHOLD ? "FALLBACK THRESHOLD REACHED" : "ALERT THRESHOLD REACHED"}
            </p>
          )}
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3">Per-Model Breakdown</h2>
          <div className="space-y-2">
            {Object.entries(summary.model_costs).map(([model, cost]) => {
              const modelRatio = cost / summary.total_cost_usd;
              const modelWidth = modelRatio * 100;
              return (
                <div key={model}>
                  <div className="flex justify-between text-sm text-gray-600 mb-1">
                    <span>{model}</span>
                    <span>${cost.toFixed(2)}</span>
                  </div>
                  <div className="bg-gray-200 rounded-full h-2">
                    <div
                      className="h-2 rounded-full bg-blue-500"
                      style={{ width: `${modelWidth}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="pt-4 border-t">
          <div className="flex justify-between text-lg font-semibold">
            <span>Total Spend</span>
            <span>${summary.total_cost_usd.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
